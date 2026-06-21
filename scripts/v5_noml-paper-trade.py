#!/usr/bin/env python3
"""
v5_noml — SHADOW A/B engine (TP-CLN-009).

Identical to v5 EXCEPT ml_score composite weight = 0 (the dead-weight ML; TP-CLN-008
proved zeroing it is selection-neutral, IC=0.006). Runs ALONGSIDE live v5 with its own
state dir (docs/paper-trades/v5_noml) and log (logs/v5_noml-paper-trade.log) so we can
compare net P&L / alpha over ~5-10 sessions before committing weight=0 to config.py.

Same code, one parameter differs — the cleanest possible A/B. Telegram silenced so it
doesn't double-notify.
"""
import os, sys, runpy
from pathlib import Path

os.environ["ENGINE_NAME"]      = "v5_noml"   # -> own state dir + log
os.environ["ML_SCORE_WEIGHT"]  = "0"         # -> renormalize other 6 factors to sum 1
os.environ["TELEGRAM_DISABLE"] = "1"         # -> shadow stays silent

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
