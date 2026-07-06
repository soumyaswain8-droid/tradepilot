#!/usr/bin/env python3
"""
v5_long — RC-1: the long-only shadow (TP-RCA, 2026-06-26).

WHY THIS EXISTS (root-cause finding, 11-agent investigation + watchdog validation):
  The short book is the ENTIRE net bleed. Over 06-16..25 (454 trades):
    LONG  213 trades  net +1,149  @ 41.8% WR
    SHORT 241 trades  net -3,611  @ 34.4% WR  <- shorts hit TARGET only 4.1% of the time;
                                                 they short into an up-drift/sideways tape
                                                 and die on STOPLOSS (36% = -9,107, the single
                                                 biggest loss bucket in the dataset).
  If the short book were merely flat, v5 would be net POSITIVE. The original April engine
  that made money was long-only -- that is the whole explanation.

WHAT THIS IS:
  Same v5 code, run with shorts DISABLED via the existing short-gate env (zero code change
  to the live engine). Universe kept at NIFTY-200 (the dashboard universe) per the owner's
  goal of covering the broad Indian market -- NOT the old NIFTY-50. So this is a true
  apples-to-apples test: "v5 minus the short book", same names, same stops/targets/sizing.

HOW LONG-ONLY IS ENFORCED:
  signal_engine.py opens a SHORT only when (change_pct < SHORT_REQ_CHG_PCT AND
  score < SHORT_REQ_MAX_SCORE). Setting SHORT_REQ_MAX_SCORE = -1 makes that condition
  impossible (scores are 0-100), so every short candidate is downgraded to HOLD.
  SHORT_REQ_CHG_PCT = -999 is belt-and-suspenders. Result: BUY/LONG + HOLD only.

  Side effects (both desirable): the SIDEWAYS short slots free up for longs, and the
  capital that was being sprayed on losing shorts now concentrates on the profitable
  long book -- directly addressing the under-deployment finding.

Runs as a shadow alongside v5; own state/log, telegram silent. Compare risk-adjusted
P&L and win-rate vs live v5 over ~2 weeks. Hypothesis: v5_long >= v5 on net P&L and WR.
Re-comment its line in launch-market.sh to end the experiment.
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]         = "v5_long"
os.environ["SHORT_REQ_MAX_SCORE"] = "-1"     # no score < -1 -> zero shorts -> long-only
os.environ["SHORT_REQ_CHG_PCT"]   = "-999"   # belt-and-suspenders: never "weak enough" to short
os.environ["TELEGRAM_DISABLE"]    = "1"
# NO UNIVERSE_FILE -> stays on NIFTY-200 (dashboard universe), per owner's broad-market goal.

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
