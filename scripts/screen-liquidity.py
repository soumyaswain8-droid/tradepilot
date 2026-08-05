#!/usr/bin/env python3
"""
screen-liquidity — decide which stocks are genuinely tradeable, over weeks not days.

WHY A SINGLE DAY IS NOT ENOUGH
The catalogue tiers rank stocks on today's turnover. That ranked NIACL as the single
best candidate to add to the trading universe — it was trading at 6.4x its normal
volume that day. MOREPENLAB, ranked third, was at 3.5x. Both look excellent on a
snapshot and are ordinary the rest of the time. A universe sized off one session
would have bought exactly the stocks that were unusually busy the day we looked.

FOUR TESTS, and a stock must pass all of them

  1. MEDIAN daily turnover, not mean. One Rs 500 Cr day lifts a mean past any
     threshold; the median ignores it. This is the single most important choice in
     the file — it is what makes a spike-day stock fail.

  2. CONSISTENCY — the fraction of sessions with real volume. A stock that trades
     heavily on 6 days out of 60 is not liquid, it is episodic, and an engine that
     enters on day 7 cannot get out.

  3. OUR OWN IMPACT — position size as a share of median daily turnover. The
     INTRADAY pool is 30% of Rs 10L and the sizer asks 15%, so a position is about
     Rs 45,000. Being a large share of a stock's daily volume means WE move the
     price against ourselves, and the backtest that justified the trade assumed we
     did not.

  4. PRICE SANITY — a floor, because sub-Rs-10 stocks move in ticks that are large
     percentages, which wrecks percentage-based stops and targets.

  5. SIZING GRANULARITY — ADVISORY ONLY since 2026-08-05. The position buying few
     shares is A Rs 45,000
     position in 3MINDIA at Rs 35,830 buys ONE share, so int() rounding sets the real
     allocation to whatever that share costs and the sizer's 15% becomes fiction.
     a real problem, but validation against 18,053 trades showed that REJECTING on
     it costs money: the excluded stocks earned Rs 18/trade MORE (t=2.40). It was
     throwing out ABB, OFSS, EICHERMOT and KEI — Rs 4,800-9,900 shares doing
     Rs 166-400 Cr a day. Expensive is not illiquid. Now annotates, does not reject.

  6. EPISODIC LIQUIDITY — mean/median turnover above MAX_SPIKE_RATIO means a handful
     of enormous days are carrying the average while typical days are far thinner.
     NIACL passes a median test at Rs 19 Cr but its mean is Rs 182 Cr, a 9.5x ratio:
     it is occasionally enormous and usually ordinary. An engine cannot rely on the
     occasional day being the one it needs to exit on.

WHAT IT DOES NOT DO
It does not add anything to any universe. It writes a ranked, reasoned candidate
list. Widening a live shadow's universe mid-experiment is Soumya's call, and the
output says exactly what would change.

Run:
    python3 scripts/screen-liquidity.py                    # screen unscanned names
    python3 scripts/screen-liquidity.py --days 90
    python3 scripts/screen-liquidity.py --all              # screen everything
    python3 scripts/screen-liquidity.py --json out.json
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics as st
import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Thresholds. Every one is derived from something measured, not chosen round.
LOOKBACK_DAYS = 60           # ~12 trading weeks: long enough to average out spikes
MIN_MEDIAN_TURNOVER = 5e7    # Rs 5 Cr/day median
MIN_TRADED_RATIO = 0.95      # must trade on 95% of sessions
MAX_IMPACT_PCT = 0.5         # our position <= 0.5% of median daily turnover
# VALIDATED AGAINST 18,053 REAL TRADES on 2026-08-05 (validate-liquidity-rule.py),
# each screened using only bars that closed BEFORE its entry. Result:
#
#   bucket                      trades   net/trade   vs PASS      t
#   PASS (all six tests)        16,382       38.73         -      -
#   FAIL on liquidity              176       26.38    -12.35  -0.70   tests work
#   FAIL on price/shares ONLY    1,501       56.74    +18.02  +2.40   tests HARMFUL
#
# The four liquidity tests point the right way — stocks failing them earned Rs 12
# less per trade — though 176 trades is too few to call significant.
#
# The two SIZING tests were backwards and significantly so. They rejected ABB, OFSS,
# EICHERMOT and KEI: stocks at Rs 4,800-9,900 a share doing Rs 166-400 Cr of daily
# turnover. Among the most liquid names on the exchange, thrown out for being
# EXPENSIVE. Share count is a real problem, but it is a SIZING problem — the answer
# is to let the sizer buy a larger rupee position, not to refuse the stock.
#
# Both are now advisory: they annotate a result, they do not reject it.
MIN_PRICE = 10.0             # advisory only — see the validation note above
_ADVISORY = {"price-floor", "share-count"}
MIN_SHARES = 10              # a position must buy at least this many shares
MAX_SPIKE_RATIO = 3.0        # mean/median turnover — above this, liquidity is episodic

# Our per-position size: INTRADAY pool = 30% of Rs 10L, sizer asks 15% of that.
POSITION_SIZE = 1_000_000 * 0.30 * 0.15      # Rs 45,000


def daily_history(symbol: str, days: int):
    from prototype.v4 import kite_data as kd
    tok = kd.token_for(symbol)
    if not tok:
        return None
    try:
        to_d = datetime.now()
        return kd.client().historical_data(tok, to_d - timedelta(days=days), to_d, "day")
    except Exception:
        return None


def screen(symbol: str, days: int) -> dict | None:
    bars = daily_history(symbol, days)
    if not bars or len(bars) < 20:
        return {"symbol": symbol, "verdict": "NO DATA",
                "reason": f"only {len(bars) if bars else 0} sessions available"}

    turnovers = [float(b["close"]) * int(b["volume"]) for b in bars]
    vols = [int(b["volume"]) for b in bars]
    closes = [float(b["close"]) for b in bars]

    med = st.median(turnovers)
    mean = st.mean(turnovers)
    traded = sum(1 for v in vols if v > 0) / len(vols)
    impact = (POSITION_SIZE / med * 100) if med > 0 else 999.0
    price = closes[-1]
    # spike ratio: how much the mean exceeds the median. High = a few big days are
    # carrying the average, which is exactly the NIACL failure mode.
    spike = (mean / med) if med > 0 else 0.0

    fails = []
    if med < MIN_MEDIAN_TURNOVER:
        fails.append(f"median turnover Rs {med/1e7:.1f} Cr < Rs {MIN_MEDIAN_TURNOVER/1e7:.0f} Cr")
    if traded < MIN_TRADED_RATIO:
        fails.append(f"trades on only {traded*100:.0f}% of sessions")
    if impact > MAX_IMPACT_PCT:
        fails.append(f"our Rs {POSITION_SIZE:,.0f} position = {impact:.2f}% of daily turnover")
    shares = int(POSITION_SIZE / price) if price > 0 else 0
    # ADVISORY, not disqualifying — measured harmful, see the note at MIN_PRICE.
    notes = []
    if price < MIN_PRICE:
        notes.append(f"price Rs {price:.2f} below Rs {MIN_PRICE:.0f}")
    if shares < MIN_SHARES:
        notes.append(f"Rs {POSITION_SIZE:,.0f} buys only {shares} share(s) — size up, do not exclude")
    if spike > MAX_SPIKE_RATIO:
        fails.append(f"episodic: mean/median = {spike:.1f}x, typical day far thinner than the average")

    return {
        "symbol": symbol,
        "sessions": len(bars),
        "median_turnover_cr": round(med / 1e7, 2),
        "mean_turnover_cr": round(mean / 1e7, 2),
        "spike_ratio": round(spike, 2),
        "traded_pct": round(traded * 100, 1),
        "impact_pct": round(impact, 3),
        "price": round(price, 2),
        "shares_per_position": shares,
        "verdict": "PASS" if not fails else "FAIL",
        "reason": "; ".join(fails) if fails else "clears all four liquidity tests",
        "notes": "; ".join(notes),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=LOOKBACK_DAYS)
    ap.add_argument("--all", action="store_true", help="screen every listed stock")
    ap.add_argument("--symbols", default="")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    from prototype.v4 import kite_data as kd
    ok, detail = kd.token_alive()
    if not ok:
        print(f"  Kite token dead: {detail}", file=sys.stderr)
        return 2

    from prototype.v4 import catalogue as cat
    rows = cat.all_stocks()

    if a.symbols:
        cands = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    elif a.all:
        cands = [r["symbol"] for r in rows if r["price"] > 0]
    else:
        # default: the actionable set — has some liquidity today, not already scanned
        cands = [r["symbol"] for r in rows
                 if r["tradeable"] and not r["in_engines"]]

    print(f"\n  LIQUIDITY SCREEN — {len(cands)} candidates, {a.days}-day lookback")
    print(f"  a stock must pass ALL of:")
    print(f"    median turnover  >= Rs {MIN_MEDIAN_TURNOVER/1e7:.0f} Cr/day   (median, so a spike day cannot carry it)")
    print(f"    traded sessions  >= {MIN_TRADED_RATIO*100:.0f}%")
    print(f"    our impact       <= {MAX_IMPACT_PCT}% of daily turnover  (Rs {POSITION_SIZE:,.0f} position)")
    print(f"  advisory only (measured harmful as filters): price floor, share count")
    print(f"    mean/median      <= {MAX_SPIKE_RATIO}x                    (else liquidity is episodic)\n")

    t0 = time.time()
    out = []
    for i, s in enumerate(cands, 1):
        r = screen(s, a.days)
        if r:
            out.append(r)
        if i % 50 == 0:
            print(f"    ...{i}/{len(cands)}  ({time.time()-t0:.0f}s)", file=sys.stderr)

    passed = sorted([r for r in out if r["verdict"] == "PASS"],
                    key=lambda r: -r["median_turnover_cr"])
    failed = [r for r in out if r["verdict"] == "FAIL"]
    nodata = [r for r in out if r["verdict"] == "NO DATA"]

    print(f"  screened {len(out)} in {time.time()-t0:.0f}s: "
          f"{len(passed)} PASS, {len(failed)} FAIL, {len(nodata)} no data\n")

    if passed:
        print(f"  === PASS — genuinely tradeable ({len(passed)}) ===")
        print(f"  {'symbol':<14}{'med Cr':>9}{'spike':>7}{'traded':>8}"
              f"{'impact':>8}{'price':>10}{'shares':>8}")
        for r in passed:
            print(f"  {r['symbol']:<14}{r['median_turnover_cr']:>9,.1f}"
                  f"{r['spike_ratio']:>7.2f}{r['traded_pct']:>7.0f}%"
                  f"{r['impact_pct']:>7.2f}%{r['price']:>10,.2f}{r['shares_per_position']:>8}")

    # the interesting failures: looked good on a single day, fail over weeks
    spiky = sorted([r for r in failed if r.get("spike_ratio", 0) >= 1.5],
                   key=lambda r: -r.get("spike_ratio", 0))[:10]
    if spiky:
        print(f"\n  === REJECTED AS SPIKE-DRIVEN ({len(spiky)} shown) ===")
        print(f"  these look liquid on a snapshot; the median says otherwise")
        for r in spiky:
            print(f"  {r['symbol']:<14} median Rs {r['median_turnover_cr']:>7,.1f} Cr vs "
                  f"mean Rs {r['mean_turnover_cr']:>7,.1f} Cr  ({r['spike_ratio']:.1f}x)")

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"screened_at": datetime.now().isoformat(timespec="seconds"),
             "lookback_days": a.days,
             "thresholds": {"median_turnover": MIN_MEDIAN_TURNOVER,
                            "traded_ratio": MIN_TRADED_RATIO,
                            "max_impact_pct": MAX_IMPACT_PCT,
                            "min_price": MIN_PRICE,
                            "position_size": POSITION_SIZE},
             "pass": passed, "fail": failed, "no_data": nodata},
            indent=2, default=str))
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
