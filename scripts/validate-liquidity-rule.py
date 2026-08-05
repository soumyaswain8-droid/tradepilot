#!/usr/bin/env python3
"""
validate-liquidity-rule — does the liquidity screen actually predict outcomes?

THE QUESTION SOUMYA ASKED
"are we applying our rules before arriving at any result?" — i.e. is the screen a
rule tested against evidence, or a rule asserted and then decorated with numbers?

The only honest answer comes from our own trade history: 18,053 closed trades across
427 symbols and 73 trading days (2026-04-10 .. 2026-08-05). If the screen has real
predictive value, trades in stocks it would have PASSED should out-earn trades in
stocks it would have FAILED. If they earn the same, the screen is theatre.

STRICTLY CAUSAL, because the naive version of this test is worthless
Screening a symbol with today's 60-day window and applying that verdict to an April
trade uses data from AFTER the trade — the same lookahead that produced a fake
+Rs 19,507 range-position finding yesterday, and the circular MANIPALHOS check that
compared a spike against itself.

So for EVERY trade, the screen is recomputed using ONLY daily bars that closed
strictly BEFORE that trade's entry date. A verdict for a 2026-04-15 trade sees
2026-02-14..2026-04-14 and nothing else. Trades without enough prior history are
reported as UNKNOWN, never silently counted as a pass.

WHAT WOULD FALSIFY THE RULE
If PASS and FAIL trades show the same net per trade, the screen does not work and the
837-name universe rests on nothing. That outcome is reported as plainly as a positive
one — the point is to find out, not to confirm.

Run:
    python3 scripts/validate-liquidity-rule.py
    python3 scripts/validate-liquidity-rule.py --json out.json
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import statistics as st
import sys
import time
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

COST_PER_TRADE = 14.30
LOOKBACK = 60
MIN_BARS = 20
POSITION_SIZE = 1_000_000 * 0.30 * 0.15

# identical thresholds to scripts/screen-liquidity.py — if these drift apart the
# validation stops describing the rule it claims to validate
MIN_MEDIAN_TURNOVER = 5e7
MIN_TRADED_RATIO = 0.95
MAX_IMPACT_PCT = 0.5
MIN_PRICE = 10.0
MIN_SHARES = 10
MAX_SPIKE_RATIO = 3.0


def load_trades():
    """Every closed trade with a symbol, entry date and P&L. VOID sessions skipped."""
    out = []
    for f in glob.glob(str(ROOT / "docs" / "paper-trades" / "*" / "*.json")):
        base = os.path.basename(f)[:-5]
        if len(base) != 10 or "_" in base:
            continue
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        if d.get("VOID"):
            continue
        eng = os.path.basename(os.path.dirname(f))
        for pl in (d.get("pools") or {}).values():
            for c in (pl.get("closed") or []):
                sym, pnl = c.get("symbol"), c.get("pnl")
                if not sym or pnl is None:
                    continue
                ed = str(c.get("entry_date") or base)[:10]
                if len(ed) != 10:
                    ed = base
                out.append({"symbol": sym, "entry_date": ed, "session": base,
                            "engine": eng, "pnl": float(pnl),
                            "pnl_pct": float(c.get("pnl_pct") or 0)})
    return out


def fetch_all(symbols, first_day):
    """One daily-history call per symbol, covering the lookback before the first
    trade through today. Fetched once and reused for every trade in that symbol."""
    from prototype.v4 import kite_data as kd
    start = datetime.strptime(first_day, "%Y-%m-%d") - timedelta(days=LOOKBACK + 30)
    end = datetime.now()
    hist, missing = {}, []
    for i, s in enumerate(sorted(symbols), 1):
        try:
            tok = kd.token_for(s)
            if not tok:
                missing.append(s)
                continue
            bars = kd.client().historical_data(tok, start, end, "day")
            hist[s] = [(str(b["date"])[:10], float(b["close"]), int(b["volume"]))
                       for b in bars]
        except Exception:
            missing.append(s)
        if i % 100 == 0:
            print(f"    ...{i}/{len(symbols)} symbols", file=sys.stderr)
    return hist, missing


def verdict_as_of(bars, entry_date):
    """Screen verdict using ONLY bars strictly before entry_date."""
    prior = [b for b in bars if b[0] < entry_date][-LOOKBACK:]
    if len(prior) < MIN_BARS:
        return "UNKNOWN", None
    tv = [c * v for _, c, v in prior]
    vols = [v for _, _, v in prior]
    med = st.median(tv)
    mean = st.mean(tv)
    price = prior[-1][1]
    traded = sum(1 for v in vols if v > 0) / len(vols)
    impact = (POSITION_SIZE / med * 100) if med > 0 else 999.0
    spike = (mean / med) if med > 0 else 0.0
    shares = int(POSITION_SIZE / price) if price > 0 else 0

    ok = (med >= MIN_MEDIAN_TURNOVER and traded >= MIN_TRADED_RATIO
          and impact <= MAX_IMPACT_PCT and price >= MIN_PRICE
          and shares >= MIN_SHARES and spike <= MAX_SPIKE_RATIO)
    return ("PASS" if ok else "FAIL"), {"median_cr": med / 1e7, "spike": spike,
                                        "price": price, "shares": shares}


def summarise(rows, label):
    if not rows:
        return f"  {label:<10} no trades"
    n = len(rows)
    gross = sum(r["pnl"] for r in rows)
    cost = n * COST_PER_TRADE
    wins = sum(1 for r in rows if r["pnl"] > 0)
    return (f"  {label:<10}{n:>7,}{wins/n*100:>7.0f}%{gross:>12,.0f}{cost:>11,.0f}"
            f"{gross-cost:>12,.0f}{(gross-cost)/n:>11.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    from prototype.v4 import kite_data as kd
    ok, detail = kd.token_alive()
    if not ok:
        print(f"  Kite token dead: {detail}", file=sys.stderr)
        return 2

    trades = load_trades()
    days = sorted({t["session"] for t in trades})
    syms = {t["symbol"] for t in trades}
    print(f"\n  VALIDATING THE LIQUIDITY RULE AGAINST OUR OWN TRADE HISTORY")
    print(f"  {len(trades):,} closed trades | {len(syms)} symbols | {len(days)} sessions "
          f"| {days[0]} .. {days[-1]}")
    print(f"  every verdict uses ONLY bars that closed BEFORE that trade's entry\n")

    t0 = time.time()
    hist, missing = fetch_all(syms, days[0])
    print(f"  fetched history for {len(hist)}/{len(syms)} symbols in {time.time()-t0:.0f}s"
          f"{f' ({len(missing)} unavailable)' if missing else ''}\n")

    buckets = defaultdict(list)
    for t in trades:
        bars = hist.get(t["symbol"])
        if not bars:
            buckets["UNKNOWN"].append(t)
            continue
        v, _ = verdict_as_of(bars, t["entry_date"])
        buckets[v].append(t)

    print(f"  {'verdict':<10}{'trades':>7}{'win%':>7}{'gross Rs':>12}{'costs Rs':>11}"
          f"{'NET Rs':>12}{'net/trade':>11}")
    print("  " + "-" * 70)
    for k in ("PASS", "FAIL", "UNKNOWN"):
        print(summarise(buckets[k], k))
    allrows = [t for v in buckets.values() for t in v]
    print("  " + "-" * 70)
    print(summarise(allrows, "ALL"))

    p, f = buckets["PASS"], buckets["FAIL"]
    print("\n  THE VERDICT ON THE RULE ITSELF")
    if p and f:
        pn = (sum(r["pnl"] for r in p) - len(p) * COST_PER_TRADE) / len(p)
        fn = (sum(r["pnl"] for r in f) - len(f) * COST_PER_TRADE) / len(f)
        print(f"    PASS trades net Rs {pn:+.2f}/trade")
        print(f"    FAIL trades net Rs {fn:+.2f}/trade")
        print(f"    difference        Rs {pn-fn:+.2f}/trade")
        would = sum(r["pnl"] for r in p) - len(p) * COST_PER_TRADE
        actual = sum(r["pnl"] for r in allrows) - len(allrows) * COST_PER_TRADE
        print(f"\n    actual net, all {len(allrows):,} trades      : Rs {actual:+,.0f}")
        print(f"    net if we had traded only PASS   : Rs {would:+,.0f}  "
              f"({len(p):,} trades)")
        print(f"    difference                       : Rs {would-actual:+,.0f}")
        if abs(pn - fn) < 1.0:
            print(f"\n    -> PASS and FAIL earn the same. The screen does NOT predict")
            print(f"       outcomes and the 837-name universe rests on nothing.")
        elif pn > fn:
            print(f"\n    -> the screen separates outcomes in the direction claimed.")
        else:
            print(f"\n    -> the screen is BACKWARDS: rejected stocks did better.")
    else:
        print("    one bucket is empty — cannot compare")

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"trades": len(allrows),
             "buckets": {k: len(v) for k, v in buckets.items()},
             "net": {k: sum(r["pnl"] for r in v) - len(v) * COST_PER_TRADE
                     for k, v in buckets.items()}},
            indent=2, default=str))
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
