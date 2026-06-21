#!/usr/bin/env python3
"""
v5_apr — SHADOW A/B engine (TP-CLN-011): v5 with "April settings" restored.

The 2026-05-04 Track A fixes capped v5's right tail: TARGET-reached exits fell
48%->7% while TIME/FLAT exits rose 6%->52%, collapsing mean P&L 13.7k->0.7k/day.
This shadow reverses the TWO highest-impact dampeners (forensic-ranked) via env:
  - FLAT_EXIT_THRESHOLD_PCT=0  -> disables the 13:30-14:00 flat-force-exit
                                  (lets winners run to target like April)
  - WINNER_REARM_MAX=6         -> restores re-entry compounding into trends (was 3)

Runs ALONGSIDE live v5 and v5_noml with its own state/log, telegram silenced, on
an independent paper book. Compare RISK-ADJUSTED return (alpha/Sharpe), NOT raw
P&L — restoring the right tail also restores variance/drawdown. Same code as v5,
only params differ. Re-comment in launch-market.sh to end the experiment.
"""
import os, sys, runpy
from pathlib import Path

os.environ["ENGINE_NAME"]             = "v5_apr"
os.environ["FLAT_EXIT_THRESHOLD_PCT"] = "0"    # disable flat-force-exit (let winners run)
os.environ["WINNER_REARM_MAX"]        = "6"    # restore re-entry compounding (was 3)
os.environ["TELEGRAM_DISABLE"]        = "1"    # stay silent (no double-notify)

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
