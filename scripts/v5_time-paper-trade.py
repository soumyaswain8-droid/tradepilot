#!/usr/bin/env python3
"""v5_time — v5 with the opening hour closed to new entries.

THE FINDING (v5's last 30 sessions, 504 closed trades carrying entry times)

    hour   trades  win%       net   net/trade
    09:00     121   40%    -2,550       -21.1   <- worst hour, by a wide margin
    10:00      52   38%      -687       -13.2
    11:00      63   49%      -318        -5.0
    12:00      57   37%      -414        -7.3
    13:00      92   45%    +1,503       +16.3   <- the only profitable hour
    14:00      95   51%      -546        -5.7
    15:00      24   54%      -414       -17.3

Skipping the 09:00 hour alone: 504 -> 383 trades, net -3,425 -> -875, a Rs 2,550
improvement, purely by not taking the trades that lose the most.

EVIDENCE STRENGTH — stated plainly, because it is thinner than the headline
Only 9 of 30 sessions traded the 09:00 hour at all. Six of those nine were net
negative, median -Rs 363, so the DIRECTION is consistent. But one session at
-Rs 2,253 supplies much of the total, so the MAGNITUDE is not established. This is a
hypothesis worth a live shadow, not a proven result, and it is deliberately not
applied to v5.

WHY IT IS THE RIGHT SHAPE OF CHANGE
The SYNTHESIS research (2026-08-04, 16 independent captures) reaches the same
conclusion this stack reached from its own history: win rate fell 82% -> 48% as trade
count rose 17 -> 45. Its stated rule is that any candidate whose effect is "take more
trades" is rejected on that basis alone, and that "one hard pre-trade gate applied
without exception preserves edge better than a richer signal applied inconsistently."
A time-of-day gate is exactly that: mechanical, no discretion, and it can only
subtract. It is also the cheapest of the five actions that document ranks.

THE ONE VARIABLE: NO_ENTRY_HOURS=9. Same strategy, capital, risk, universe, feed,
score floor. Exits are untouched — a position opened at 08:5x still manages itself
normally; only NEW entries in the 09:00-09:59 window are refused.

WATCH: net P&L vs v5, and specifically whether the trades v5 takes at 09:00 that this
engine skips turn out to be winners. If they do, the 9-session sample was noise.

Run:
    python3 scripts/v5_time-paper-trade.py
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]     = "v5_time"
os.environ["NO_ENTRY_HOURS"]  = "9"        # THE one variable under test
os.environ["TELEGRAM_DISABLE"] = "1"       # shadow: only live v5 alerts

# Deliberately NOT set, to keep this single-variable against v5:
#   MIN_ENTRY_SCORE (v5_pick), POOL_ALLOC (v5_deploy), NSE_DATA_SOURCE (v5_kite),
#   CHOP_FILTER, RISK_GATE_DRIVE.

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
