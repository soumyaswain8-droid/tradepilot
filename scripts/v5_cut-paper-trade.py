#!/usr/bin/env python3
"""
v5_cut — profit-improvement engine (TP-QUANT, 2026-06-21), built from this week's
watchdog findings. Same v5 code, four enhancements (all env-gated, others untouched):

  1. DEAD ML REMOVED        — ml_score now 0 in config (committed; A/B 5/5 validated).
  2. FASTER WRONG-WAY CUT    — WRONGWAY_CUT_PCT=1.0: cut any position >1% underwater
                               intraday (stops the "hold the loser all day" bleed —
                               watchdog: ADANIENT held wrong-way 82 cycles on 06-19).
  3. TIGHTER SHORT-GATE      — only short clearly-weak names (down >1% AND score <30),
                               so we stop shorting strength (Adani complex / BIOCON).
  4. WIDER SCAN UNIVERSE     — ~450 most-liquid NSE names (vs NIFTY-200) for more
                               opportunities + learnings. (Not "all 3000" — yfinance
                               would 429; 450 liquid names is the sane max.)

Runs as a shadow alongside v5 / v5_noml / v5_apr; own state/log, telegram silent.
Compare risk-adjusted vs v5 to see if it lifts the profit margin.
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]         = "v5_cut"
os.environ["WRONGWAY_CUT_PCT"]    = "1.0"     # cut >1% underwater intraday
os.environ["SHORT_REQ_CHG_PCT"]   = "-1.0"    # short only if down >1% (was -0.5)
os.environ["SHORT_REQ_MAX_SCORE"] = "30"      # short only if score <30 (was 35)
os.environ["UNIVERSE_FILE"]       = str(ROOT / "quant" / "universe_expanded.txt")
os.environ["TELEGRAM_DISABLE"]    = "1"
# ML is already 0 in the committed config — no ML_SCORE_WEIGHT env needed.

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
