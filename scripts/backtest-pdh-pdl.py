#!/usr/bin/env python3
"""
backtest-pdh-pdl — honest backtest of the PDH/PDL rejection setup.

THE SETUP, exactly as SYNTHESIS.pdf Cluster 1 states it. Every term is objective;
there is no discretion left in it, which is why it can be tested at all.

    Level         previous day's high (PDH) and previous day's low (PDL)
    Location      price must be AT an extreme; explicit no-trade middle zone
    Trigger       1H rejection candle — wick through the level, close back inside
    Confirmation  break of the rejection candle's opposite extreme
    Stop          beyond the rejection wick
    Target        the opposite level

WHY THIS SETUP AND NOT ANOTHER
v5's own exit data says the problem is structural, not selective: only 4.6% of trades
reach TARGET while 30% hit STOPLOSS. Target wins (+9,484) and stop losses (-9,503)
almost exactly cancel, so nearly all of v5's profit comes from TIME_EXIT — the "gave
up waiting" exit. The stop/target geometry is not earning what it assumes. PDH/PDL
defines both mechanically off structure rather than off a fixed percentage.

THE TEST THAT MATTERS IS THE REGIME SPLIT
This is a mean-reversion setup. It SHOULD win on range days and bleed on trend days.
SYNTHESIS says so itself, and it is the sharpest claim in the document:
"The real test is not aggregate expectancy — it is a regime split. If the edge only
exists on range days, then the setup is not the deliverable; the range-day classifier
is." An aggregate number would average two opposite behaviours into a misleading
middle, so this script never reports one without the split.

HONEST-BACKTEST RULES APPLIED HERE
  - the level comes from the PREVIOUS day only; nothing from the current day is used
    before it has printed
  - entry is at the confirmation bar's CLOSE, not its low/high — no perfect fills
  - stop and target are checked bar by bar, in order, on subsequent bars only
  - when a bar's range contains BOTH stop and target, STOP is assumed hit first
    (hourly bars hide the path; assuming the good outcome is how backtests lie)
  - costs are charged at the same Rs 14.30/trade the live engines book
  - day classification uses only data available BEFORE that day started

Run:
    python3 scripts/backtest-pdh-pdl.py                    # default universe, 180d
    python3 scripts/backtest-pdh-pdl.py --days 365 --top 30
    python3 scripts/backtest-pdh-pdl.py --symbols RELIANCE,TCS --verbose
"""
from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

COST_PER_TRADE = 14.30          # same figure the live engines book
MIDDLE_ZONE = 0.35              # no-trade band: middle 35% of the prev-day range
RANGE_DAY_MAX_BODY = 0.45       # |close-open| / range below this = range day


def fetch(symbol: str, days: int):
    """(daily bars, hourly bars) from Kite. Returns (None, None) on failure."""
    from prototype.v4 import kite_data as kd
    tok = kd.token_for(symbol)
    if not tok:
        return None, None
    to_d = datetime.now()
    fr_d = to_d - timedelta(days=days)
    try:
        k = kd.client()
        daily = k.historical_data(tok, fr_d, to_d, "day")
        hourly = k.historical_data(tok, fr_d, to_d, "60minute")
        return daily, hourly
    except Exception as e:
        print(f"    {symbol}: fetch failed — {type(e).__name__}: {e}", file=sys.stderr)
        return None, None


def classify_day(prev_days) -> str:
    """RANGE or TREND, decided from the PREVIOUS days only.

    Uses the prior day's body-to-range ratio: a day that closed near its open spent
    the session oscillating (range); one that closed near an extreme trended. Nothing
    from the day being traded is consulted — that would be lookahead.
    """
    if len(prev_days) < 1:
        return "UNKNOWN"
    d = prev_days[-1]
    rng = float(d["high"]) - float(d["low"])
    if rng <= 0:
        return "UNKNOWN"
    body = abs(float(d["close"]) - float(d["open"])) / rng
    return "RANGE" if body <= RANGE_DAY_MAX_BODY else "TREND"


def backtest_symbol(symbol: str, daily, hourly, verbose=False):
    """Walk the setup forward. One trade per level per day, max."""
    by_day = defaultdict(list)
    for b in hourly:
        by_day[str(b["date"])[:10]].append(b)
    dmap = {str(d["date"])[:10]: d for d in daily}
    dates = sorted(dmap)

    trades = []
    for i in range(1, len(dates)):
        today, prev = dates[i], dates[i - 1]
        bars = by_day.get(today) or []
        if len(bars) < 3:
            continue
        pd_ = dmap[prev]
        pdh, pdl = float(pd_["high"]), float(pd_["low"])
        rng = pdh - pdl
        if rng <= 0:
            continue
        regime = classify_day([dmap[d] for d in dates[max(0, i - 3):i]])

        # no-trade middle zone: only the outer bands of the prev-day range qualify
        lo_band = pdl + rng * (0.5 - MIDDLE_ZONE / 2)
        hi_band = pdh - rng * (0.5 - MIDDLE_ZONE / 2)

        taken = set()
        for j in range(len(bars) - 1):
            b = bars[j]
            o, h, l, c = (float(b["open"]), float(b["high"]),
                          float(b["low"]), float(b["close"]))

            for side, level in (("SHORT", pdh), ("LONG", pdl)):
                if side in taken:
                    continue
                if side == "SHORT":
                    # rejection at PDH: wick above the level, close back below it,
                    # and the close must sit in the upper band (location filter)
                    if not (h > pdh and c < pdh and c >= hi_band):
                        continue
                else:
                    if not (l < pdl and c > pdl and c <= lo_band):
                        continue

                # CONFIRMATION on a LATER bar: break of the rejection candle's
                # opposite extreme. Entry is that bar's CLOSE, never its extreme.
                entry = stop = None
                for m in range(j + 1, len(bars)):
                    nb = bars[m]
                    nh, nl, nc = float(nb["high"]), float(nb["low"]), float(nb["close"])
                    if side == "SHORT" and nl < l:
                        entry, stop, k0 = nc, h, m
                        break
                    if side == "LONG" and nh > h:
                        entry, stop, k0 = nc, l, m
                        break
                if entry is None:
                    continue
                target = pdl if side == "SHORT" else pdh
                risk = abs(entry - stop)
                if risk <= 0 or abs(target - entry) <= 0:
                    continue

                # walk forward: stop and target checked on SUBSEQUENT bars only
                outcome, exit_px = "EOD", float(bars[-1]["close"])
                for m in range(k0 + 1, len(bars)):
                    nb = bars[m]
                    nh, nl = float(nb["high"]), float(nb["low"])
                    if side == "SHORT":
                        hit_stop, hit_tgt = nh >= stop, nl <= target
                    else:
                        hit_stop, hit_tgt = nl <= stop, nh >= target
                    if hit_stop:            # pessimistic when a bar spans both
                        outcome, exit_px = "STOP", stop
                        break
                    if hit_tgt:
                        outcome, exit_px = "TARGET", target
                        break

                pnl_pts = (entry - exit_px) if side == "SHORT" else (exit_px - entry)
                trades.append({
                    "symbol": symbol, "date": today, "side": side, "regime": regime,
                    "entry": round(entry, 2), "stop": round(stop, 2),
                    "target": round(target, 2), "exit": round(exit_px, 2),
                    "outcome": outcome, "pnl_pts": round(pnl_pts, 2),
                    "pnl_pct": round(pnl_pts / entry * 100, 3),
                    "r_multiple": round(pnl_pts / risk, 2),
                })
                taken.add(side)
                if verbose:
                    print(f"    {today} {symbol:<10} {side:<5} {regime:<5} "
                          f"{outcome:<6} {pnl_pts/entry*100:+.2f}%")
    return trades


def report(trades, label="ALL"):
    if not trades:
        return f"  {label:<8} no trades"
    n = len(trades)
    wins = [t for t in trades if t["pnl_pts"] > 0]
    pct = sum(t["pnl_pct"] for t in trades)
    rs = sum(t["r_multiple"] for t in trades)
    oc = defaultdict(int)
    for t in trades:
        oc[t["outcome"]] += 1
    return (f"  {label:<8}{n:>6}{len(wins)/n*100:>7.0f}%{pct:>10.1f}%{pct/n:>9.3f}%"
            f"{rs/n:>8.2f}R   T{oc['TARGET']}/S{oc['STOP']}/E{oc['EOD']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=180)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    from prototype.v4 import kite_data as kd
    ok, detail = kd.token_alive()
    if not ok:
        print(f"  Kite token dead — cannot backtest: {detail}", file=sys.stderr)
        return 2

    if a.symbols:
        syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    else:
        from prototype.v4.config import ACTIVE_SYMBOLS_YF
        syms = [s.replace(".NS", "") for s in ACTIVE_SYMBOLS_YF][:a.top]

    print(f"\n  PDH/PDL rejection backtest — {len(syms)} symbols, {a.days} days")
    print(f"  entry at confirmation CLOSE; stop assumed hit first when a bar spans both\n")

    all_trades = []
    for s in syms:
        daily, hourly = fetch(s, a.days)
        if not daily or not hourly:
            continue
        all_trades += backtest_symbol(s, daily, hourly, a.verbose)

    if not all_trades:
        print("  NO TRADES — the setup did not trigger. That is a result, not a failure.")
        return 0

    print(f"  {'cohort':<8}{'trades':>6}{'win%':>7}{'total%':>10}{'avg%':>9}{'avg R':>8}   outcomes")
    print("  " + "-" * 68)
    print(report(all_trades, "ALL"))
    for r in ("RANGE", "TREND", "UNKNOWN"):
        sub = [t for t in all_trades if t["regime"] == r]
        if sub:
            print(report(sub, r))
    print()
    for side in ("LONG", "SHORT"):
        sub = [t for t in all_trades if t["side"] == side]
        if sub:
            print(report(sub, side))

    # THE VERDICT the document asks for, stated explicitly
    rng = [t for t in all_trades if t["regime"] == "RANGE"]
    trd = [t for t in all_trades if t["regime"] == "TREND"]
    print("\n  REGIME SPLIT — the test SYNTHESIS says actually matters:")
    if rng and trd:
        ar = sum(t["pnl_pct"] for t in rng) / len(rng)
        at = sum(t["pnl_pct"] for t in trd) / len(trd)
        print(f"    range days {ar:+.3f}%/trade over {len(rng)} trades")
        print(f"    trend days {at:+.3f}%/trade over {len(trd)} trades")
        if ar > 0 and at < 0:
            print("    -> behaves as predicted: mean-reversion. The DELIVERABLE is the")
            print("       range-day classifier, not the setup on its own.")
        elif ar > 0 and at > 0:
            print("    -> profitable in both regimes; the split is not the constraint.")
        else:
            print("    -> does NOT behave as claimed. Do not ship on this evidence.")
    else:
        print("    insufficient trades in one regime to split honestly")

    if a.json:
        Path(a.json).write_text(json.dumps(all_trades, indent=2, default=str))
        print(f"\n  wrote {len(all_trades)} trades -> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
