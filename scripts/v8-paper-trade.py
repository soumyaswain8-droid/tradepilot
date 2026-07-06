#!/usr/bin/env python3
"""
v8 — the April-recipe replica (control twin). TP-V8, 2026-07-06.

WHY: DEGRADATION_ANALYSIS_Apr-Jul_2026 shows v5 decayed from +1.35%/day @ 77% WR (April)
to -0.24%/day @ 46% (July) via a complexity cascade. This is a clean-room revert to the
proven April engine — NIFTY-50, top-5, long-only, +1.5/-0.75 FIXED bracket, early entry,
flat by EOD. All params are env-gated on the shared v5 engine (zero change to live v5).

Twin: v8_ml is identical except ML_SCORE_WEIGHT=0.10 (5-tree tilt). v8 - v8_ml isolates
the ML's marginal effect. Target: recover +1%/day, 65%+ WR on Rs10L.
Compare vs live v5 over >=2 weeks incl. >=1 green + >=1 red day.
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]          = "v8"
os.environ["UNIVERSE_FILE"]        = str(ROOT / "quant" / "universe_nifty50.txt")  # NIFTY-50
os.environ["MAX_POSITIONS_TOTAL"]  = "5"        # top-5 concentration (binds before slot split)
os.environ["TARGET_PCT"]           = "1.5"      # April fixed target
os.environ["STOP_PCT"]             = "0.75"     # April fixed stop
os.environ["STOP_MODE"]            = "fixed"    # no trailing — hold the fixed bracket
os.environ["SHORT_REQ_MAX_SCORE"]  = "-1"       # long-only (score never < -1)
os.environ["SHORT_REQ_CHG_PCT"]    = "-999"     # belt-and-suspenders long-only
os.environ["RESCORE_INTERVAL_MIN"] = "999"      # enter early on first scan, hold to bracket
os.environ["ML_SCORE_WEIGHT"]      = "0"        # control twin: no ML
os.environ["TELEGRAM_DISABLE"]     = "1"

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
