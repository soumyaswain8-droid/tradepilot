#!/usr/bin/env python3
"""
test-timeframe — does the SAME signal clear the toll if held for days instead of minutes?

THE QUESTION
Measured 2026-08-05 on v5 since June:
    per-trade edge   +0.0685%
    per-trade cost   -0.1200%   (verified percentage-based: exactly 0.12% at every
                                 position size from Rs 5k to Rs 50k)
    net              -0.0515%
The signal is NOT broken. It produces a real, positive edge with a 46.9% win rate
against a 42% break-even. It simply does not clear a 12 bps toll.

The toll is paid ONCE per trade regardless of how long the position is held. So the
same signal that loses 5 bps intraday could clear comfortably if each trade captured
a multi-day move instead of a 40-minute one. That is the hypothesis, and it costs
nothing to test because the data already exists.

THE METHOD
Take every entry v5 actually made — same symbol, same date, same direction, same
signal that fired at the time — and instead of exiting the way v5 did, hold for N
trading days and exit at that day's close. Compare net after the identical 12 bps.

WHAT THIS DELIBERATELY DOES NOT DO
It does not re-pick trades. The entries are exactly the ones the live signal chose,
so this isolates HOLDING PERIOD as the only variable. Changing selection and horizon
together would produce a number nobody could attribute.

HONEST LIMITS, stated before the results
  - No stop-loss is modelled in the held variants. A real multi-day book would have
    one, and a stop can only reduce the tail. So these figures are an UPPER bound on
    the hold benefit, not a forecast.
  - Overnight gaps are real: measured 960 gaps on 8 large caps, median 0.46%, 90th
    percentile 1.58%, worst 8.66%. Holding overnight accepts that exposure, and the
    daily bars used here contain the gaps, so the returns include them.
  - Multi-day positions carry different margin treatment than intraday, which
    matters when real money follows.

Run:
    python3 scripts/test-timeframe.py
    python3 scripts/test-timeframe.py --from 2026-04-01 --engine v5
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
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

COST_PCT = 0.12          # 12 bps round trip — the engines' own booked rate
HOLDS = [1, 2, 3, 5, 10, 20]


def load_entries(engine: str, since: str):
    """Every entry v5 actually made. Deduplicated per (symbol, date, direction) —
    the engine often opens the same name across pools, and counting it three times
    would triple-weight one decision."""
    seen, out = set(), []
    for f in sorted(glob.glob(str(ROOT / "docs" / "paper-trades" / engine / "*.json"))):
        b = os.path.basename(f)[:-5]
        if len(b) != 10 or b < since:
            continue
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        if d.get("VOID"):
            continue
        for pl in (d.get("pools") or {}).values():
            for c in (pl.get("closed") or []):
                sym = c.get("symbol")
                if not sym or c.get("pnl_pct") is None:
                    continue
                side = ("SHORT" if str(c.get("position_type") or "").upper() == "SHORT"
                        else "LONG")
                ed = str(c.get("entry_date") or b)[:10]
                key = (sym, ed, side)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"symbol": sym, "date": ed, "side": side,
                            "actual_pct": float(c["pnl_pct"])})
    return out


def daily_map(symbols, first_day, last_day):
    """Daily closes per symbol, once. 20 trading days of headroom past the last entry
    so a 20-day hold has somewhere to exit."""
    from prototype.v4 import kite_data as kd
    start = datetime.strptime(first_day, "%Y-%m-%d") - timedelta(days=5)
    end = datetime.strptime(last_day, "%Y-%m-%d") + timedelta(days=40)
    end = min(end, datetime.now())
    out = {}
    for i, s in enumerate(sorted(symbols), 1):
        try:
            tok = kd.token_for(s)
            if not tok:
                continue
            bars = kd.client().historical_data(tok, start, end, "day")
            out[s] = [(str(b["date"])[:10], float(b["open"]), float(b["close"]))
                      for b in bars]
        except Exception:
            pass
        if i % 100 == 0:
            print(f"    ...{i}/{len(symbols)} symbols", file=sys.stderr)
    return out


def hold_return(bars, entry_date, side, days):
    """Enter at entry_date's CLOSE (conservative — the signal fired during that day,
    so the close is the last price it could plausibly have got). Exit N trading days
    later at the close. Returns None when there is not enough forward data, never 0 —
    a missing exit is unknown, not flat."""
    idx = next((i for i, b in enumerate(bars) if b[0] == entry_date), None)
    if idx is None or idx + days >= len(bars):
        return None
    entry = bars[idx][2]
    exit_ = bars[idx + days][2]
    if entry <= 0:
        return None
    r = (exit_ - entry) / entry * 100
    return r if side == "LONG" else -r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="v5")
    ap.add_argument("--from", dest="since", default="2026-06-01")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    from prototype.v4 import kite_data as kd
    ok, detail = kd.token_alive()
    if not ok:
        print(f"  Kite token dead: {detail}", file=sys.stderr)
        return 2

    entries = load_entries(a.engine, a.since)
    if not entries:
        print("  no entries found", file=sys.stderr)
        return 1
    days = sorted({e["date"] for e in entries})
    syms = {e["symbol"] for e in entries}

    print(f"\n  TIMEFRAME TEST — {a.engine}, entries from {a.since}")
    print(f"  {len(entries):,} unique entries | {len(syms)} symbols | "
          f"{days[0]} .. {days[-1]}")
    print(f"  same entries, only the HOLDING PERIOD changes. Cost {COST_PCT}% per trade.\n")

    t0 = time.time()
    bars = daily_map(syms, days[0], days[-1])
    print(f"  fetched {len(bars)}/{len(syms)} symbols in {time.time()-t0:.0f}s\n")

    actual = [e["actual_pct"] for e in entries]
    n_a = len(actual)
    print(f"  {'holding':<16}{'trades':>8}{'win%':>7}{'gross%':>10}{'cost%':>9}"
          f"{'NET%':>10}{'net/trade':>11}")
    print("  " + "-" * 71)
    g = sum(actual)
    print(f"  {'v5 ACTUAL':<16}{n_a:>8}"
          f"{sum(1 for x in actual if x>0)/n_a*100:>6.0f}%{g:>10.1f}"
          f"{n_a*COST_PCT:>9.1f}{g-n_a*COST_PCT:>10.1f}{(g-n_a*COST_PCT)/n_a:>11.4f}")

    results = {}
    for h in HOLDS:
        rs = []
        for e in entries:
            b = bars.get(e["symbol"])
            if not b:
                continue
            r = hold_return(b, e["date"], e["side"], h)
            if r is not None:
                rs.append(r)
        if len(rs) < 50:
            print(f"  {'hold ' + str(h) + 'd':<16}{len(rs):>8}   too few with forward data")
            continue
        gr = sum(rs)
        net = gr - len(rs) * COST_PCT
        results[h] = {"n": len(rs), "gross": gr, "net": net, "per": net / len(rs),
                      "win": sum(1 for x in rs if x > 0) / len(rs) * 100}
        print(f"  {'hold ' + str(h) + 'd':<16}{len(rs):>8}"
              f"{results[h]['win']:>6.0f}%{gr:>10.1f}{len(rs)*COST_PCT:>9.1f}"
              f"{net:>10.1f}{results[h]['per']:>11.4f}")

    print(f"\n  DOES ANY HOLD CLEAR THE {COST_PCT}% TOLL?")
    winners = {h: v for h, v in results.items() if v["per"] > 0}
    if not winners:
        print(f"    No. Every holding period loses after costs. The edge does not")
        print(f"    survive at any horizon tested, so the timeframe is NOT the fix.")
    else:
        best = max(winners, key=lambda h: winners[h]["per"])
        v = winners[best]
        # significance — a positive mean on few trades is not a finding
        rs = []
        for e in entries:
            b = bars.get(e["symbol"])
            if b:
                r = hold_return(b, e["date"], e["side"], best)
                if r is not None:
                    rs.append(r - COST_PCT)
        se = st.pstdev(rs) / (len(rs) ** 0.5) if len(rs) > 2 else 0
        t = st.mean(rs) / se if se else 0
        print(f"    Best is {best}-day: {v['per']:+.4f}%/trade net, t = {t:+.2f}")
        print(f"    {'STATISTICALLY REAL' if abs(t) > 2 else 'NOT significant — could be noise'}")
        print(f"    vs v5 actual {(g-n_a*COST_PCT)/n_a:+.4f}%/trade")

    if a.json:
        Path(a.json).write_text(json.dumps(
            {"engine": a.engine, "since": a.since, "entries": len(entries),
             "cost_pct": COST_PCT, "results": results}, indent=2, default=str))
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
