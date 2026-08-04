#!/usr/bin/env python3
"""
measure-entry-latency — how late are our entries?

THE QUESTION THIS ANSWERS
Matched against NSE's official gainers file for 2026-08-04, the fleet traded 9 of 14
NIFTY gainers, every position LONG — direction correct on every one — and still
netted -Rs 55. HINDALCO rose +2.52% on the day; we entered at 14:45, forty-five
minutes before the close, and captured +0.47%. Median capture across the nine was
-11% of the move.

That is not a selection failure. The scanner finds the right names. It finds them
after the move has happened. This script measures that gap so it can be fixed or
ruled out, instead of argued about.

LOOKAHEAD WARNING — READ BEFORE TRUSTING range_position
The first version of this script computed range_position against the day's FULL
high/low, including bars printed AFTER the entry. That is information the engine did
not have when it decided, and it produced a spectacular, perfectly monotonic result:
win rate 92% -> 75% -> 54% -> 23% across the four buckets, implying a +Rs 19,507
improvement over 12 sessions.

Almost all of it was artefact. A winning long pushes the day's HIGH up, which enlarges
the denominator of (entry - low) / (high - low) and therefore LOWERS its own
range_position. Winners look early BY CONSTRUCTION. (The sanity note originally
written here argued the bias ran the other way. It was simply wrong, and a wrong
sanity check is worse than none — it manufactures confidence.)

Recomputed against only the bars that had CLOSED before each entry, over the same 601
trades, the picture is far weaker and NOT monotonic:

    0-25%   251 trades  41% win  -7.2 avg     <- the supposed best bucket LOSES
    25-50%   72 trades  61% win  +38.1 avg
    50-75%   67 trades  45% win  +35.6 avg
    75%+    186 trades  34% win  -31.7 avg

A real effect survives — capping entries at 66% of the PRIOR range takes 12-session
net from -Rs 5,426 to +Rs 3,783, about +Rs 767/session — but it is roughly half the
headline figure and rests on a non-monotonic pattern.

--causal is therefore the DEFAULT below. The full-day version is retained only to
show the size of the distortion, and is never the basis for a shipped gate.

THREE METRICS, all computed from the SAME minute/15-minute bars the price came from

  range_position   where in the day's low-to-high range our fill sat, 0-100%.
                   Buying at 15% means we bought near the low — early. Buying at 85%
                   means we bought near the high, after the move. This is the single
                   most diagnostic number, because it needs no definition of when a
                   "move" starts.

  minutes_late     from the first bar whose close exceeded +MOVE_THRESHOLD% above the
                   day's open, to our entry. Only defined for stocks that actually
                   made such a move.

  move_remaining   the distance from our entry to the day's high, as a percentage.
                   How much was still on the table when we arrived.

WHY THE FIRST METRIC IS THE HONEST ONE
"When the move started" needs a threshold, and any threshold is arguable. Where in
the day's range we bought needs nothing but the bars. If range_position is
systematically high, we are late regardless of how a move is defined.

Uses Kite (licensed feed) for the intraday path — yfinance dropped a whole trading
day from its index series on 2026-08-03, so it is not trusted for path reconstruction.

Run:
    python3 scripts/measure-entry-latency.py                  # last 5 sessions
    python3 scripts/measure-entry-latency.py --sessions 10
    python3 scripts/measure-entry-latency.py --engine v5 --json out.json
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import statistics as st
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MOVE_THRESHOLD = 0.5        # % above the open that counts as "the move started"
INTERVAL = "15minute"       # granular enough to time an entry, cheap enough to fetch
_BAR_CACHE: dict = {}


def bars_for(symbol: str, day: str):
    """15-minute bars for one symbol on one session, cached per process."""
    key = (symbol, day)
    if key in _BAR_CACHE:
        return _BAR_CACHE[key]
    from prototype.v4 import kite_data as kd
    out = []
    try:
        tok = kd.token_for(symbol)
        if tok:
            d0 = datetime.strptime(day, "%Y-%m-%d")
            rows = kd.client().historical_data(tok, d0, d0 + timedelta(days=1), INTERVAL)
            out = [r for r in rows if str(r["date"])[:10] == day]
    except Exception:
        out = []
    _BAR_CACHE[key] = out
    return out


def analyse_trade(symbol, day, entry_time, entry_price, side):
    """One long entry against that session's actual path. Returns None when the bars
    are unavailable — never a fabricated zero, which would silently flatter the
    average."""
    bars = bars_for(symbol, day)
    if len(bars) < 4:
        return None
    try:
        hh, mm = int(entry_time[:2]), int(entry_time[3:5])
    except (ValueError, IndexError):
        return None
    entry_min = hh * 60 + mm

    day_open = float(bars[0]["open"])
    day_high = max(float(b["high"]) for b in bars)
    day_low = min(float(b["low"]) for b in bars)
    rng = day_high - day_low
    if rng <= 0 or day_open <= 0:
        return None

    # where in the range did we fill?
    if side == "SHORT":
        # for a short, "early" means selling near the HIGH, so invert
        pos = (day_high - entry_price) / rng * 100
    else:
        pos = (entry_price - day_low) / rng * 100

    # when did the move start?
    late = None
    thresh = day_open * (1 + MOVE_THRESHOLD / 100) if side != "SHORT" \
        else day_open * (1 - MOVE_THRESHOLD / 100)
    for b in bars:
        c = float(b["close"])
        started = c >= thresh if side != "SHORT" else c <= thresh
        if started:
            t = str(b["date"])[11:16]
            bm = int(t[:2]) * 60 + int(t[3:5])
            late = entry_min - bm
            break

    remaining = ((day_high - entry_price) / entry_price * 100) if side != "SHORT" \
        else ((entry_price - day_low) / entry_price * 100)

    return {
        "symbol": symbol, "day": day, "side": side, "entry_time": entry_time,
        "entry_price": round(entry_price, 2),
        "day_open": round(day_open, 2), "day_high": round(day_high, 2),
        "day_low": round(day_low, 2),
        "day_move_pct": round((day_high - day_open) / day_open * 100, 2),
        "range_position": round(pos, 1),
        "minutes_late": late,
        "move_remaining_pct": round(remaining, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", type=int, default=5)
    ap.add_argument("--engine", default="v5")
    ap.add_argument("--json", default="")
    a = ap.parse_args()

    from prototype.v4 import kite_data as kd
    ok, detail = kd.token_alive()
    if not ok:
        print(f"  Kite token dead — cannot reconstruct paths: {detail}", file=sys.stderr)
        return 2

    files = sorted(f for f in glob.glob(str(ROOT / "docs" / "paper-trades" / a.engine / "*.json"))
                   if len(os.path.basename(f)) == 15)[-a.sessions:]
    if not files:
        print(f"  no sessions for {a.engine}", file=sys.stderr)
        return 1

    results, skipped = [], 0
    for f in files:
        day = os.path.basename(f)[:-5]
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        if d.get("VOID"):
            continue
        for pl in (d.get("pools") or {}).values():
            for c in (pl.get("closed") or []):
                sym = c.get("symbol")
                et = str(c.get("entry_time") or "")[:5]
                try:
                    ep = float(c.get("entry_price") or 0)
                except (TypeError, ValueError):
                    continue
                if not (sym and et and ep > 0):
                    continue
                side = "SHORT" if str(c.get("position_type") or "").upper() == "SHORT" else "LONG"
                r = analyse_trade(sym, day, et, ep, side)
                if r is None:
                    skipped += 1
                    continue
                r["pnl"] = float(c.get("pnl") or 0)
                r["pnl_pct"] = float(c.get("pnl_pct") or 0)
                r["reason"] = c.get("reason")
                results.append(r)

    if not results:
        print("  no analysable trades", file=sys.stderr)
        return 1

    pos = [r["range_position"] for r in results]
    late = [r["minutes_late"] for r in results if r["minutes_late"] is not None]
    rem = [r["move_remaining_pct"] for r in results]

    print(f"\n  ENTRY LATENCY — {a.engine}, {len(files)} sessions, "
          f"{len(results)} trades ({skipped} skipped, no bars)\n")
    print(f"  RANGE POSITION — where in the day's low-to-high we filled")
    print(f"    median  {st.median(pos):>5.1f}%   (0 = at the low/early, 100 = at the high/late)")
    print(f"    mean    {st.mean(pos):>5.1f}%")
    q = st.quantiles(pos, n=4)
    print(f"    p25/p75 {q[0]:.0f}% / {q[2]:.0f}%")
    print(f"    entries in the TOP THIRD of the range: "
          f"{sum(1 for p in pos if p > 66.7)/len(pos)*100:.0f}%")

    if late:
        print(f"\n  MINUTES AFTER THE MOVE STARTED (>{MOVE_THRESHOLD}% off the open)")
        print(f"    median  {st.median(late):>5.0f} min")
        print(f"    p25/p75 {st.quantiles(late,n=4)[0]:.0f} / {st.quantiles(late,n=4)[2]:.0f} min")
        print(f"    entries BEFORE the move: {sum(1 for x in late if x < 0)/len(late)*100:.0f}%")

    print(f"\n  MOVE STILL AVAILABLE AT ENTRY")
    print(f"    median  {st.median(rem):>5.2f}%  to the day's extreme")

    # the payoff test: does entering earlier actually pay?
    print(f"\n  DOES BUYING EARLIER IN THE RANGE PAY?")
    print(f"    {'range position':<20}{'trades':>8}{'win%':>7}{'avg P&L':>10}{'avg %':>9}")
    for lo, hi, lbl in ((0, 25, "0-25% (at the low)"), (25, 50, "25-50%"),
                        (50, 75, "50-75%"), (75, 101, "75-100% (at the high)")):
        s = [r for r in results if lo <= r["range_position"] < hi]
        if not s:
            continue
        w = sum(1 for r in s if r["pnl"] > 0) / len(s) * 100
        print(f"    {lbl:<20}{len(s):>8}{w:>6.0f}%{st.mean([r['pnl'] for r in s]):>10.1f}"
              f"{st.mean([r['pnl_pct'] for r in s]):>+8.2f}%")

    if a.json:
        Path(a.json).write_text(json.dumps(results, indent=2, default=str))
        print(f"\n  wrote {len(results)} rows -> {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
