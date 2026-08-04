#!/usr/bin/env python3
"""v5_kite — v5 with Kite Connect as the data feed. Migration canary.

THE EXPERIMENT
Exactly ONE variable differs from v5: NSE_DATA_SOURCE=kite. Same strategy, same
capital, same risk settings, same universe, same session. So any divergence in
results is attributable to the data feed and nothing else. Migrating all eleven
engines at once would leave no control, and a bad session afterwards would have
eleven candidate causes.

WHY MIGRATE AT ALL
yfinance scrapes an unofficial endpoint with no SLA. Verified 2026-08-04: its daily
series for ^NSEI and ^BSESN is silently MISSING Monday 2026-08-03 — no error, no
null, a clean well-formed series with a completed trading day absent. Anything
computing a previous close off it got the wrong baseline; the index read +0.00% on a
day it actually moved -0.64%. Equities were unaffected, so the hole is index-only,
but an index feed drives regime detection and relative strength.

MEASURED BEFORE SWITCHING (2026-08-04, after close)
  prices      200/200 NIFTY symbols, worst divergence 0.000%
  speed       200 quotes in 0.40s vs 9.00s on yfinance (22x)
  index       kite -0.64% (prev 24,774.30) vs yfinance +0.00% (prev == level)
So this is a reliability and correctness upgrade, not a change of numbers.

WHAT TO WATCH
Trade count and P&L should track v5 closely. A large divergence means the feed
changed behaviour, not that the strategy improved — investigate before promoting.
kite_data.health() counts every fallback to yfinance; a session with fallbacks is
NOT a clean comparison, because the engine silently ran on the control's feed.

Kite access tokens expire 06:00 daily. Without a fresh token this engine falls back
to yfinance — loudly, logged at ERROR — so a token lapse degrades the experiment
rather than halting the session.

Run:
    python3 scripts/v5_kite-paper-trade.py
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]      = "v5_kite"
os.environ["NSE_DATA_SOURCE"]  = "kite"    # THE one variable under test
os.environ["TELEGRAM_DISABLE"] = "1"       # shadow: only live v5 alerts

# Deliberately NOT set, so this stays a single-variable experiment against v5:
#   CHOP_FILTER, RISK_GATE_DRIVE, MAX_POSITION_PCT, ML_SCORE_WEIGHT
# Everything else inherits v5's defaults by chaining to the base script, which reads
# ENGINE_NAME from the environment for its trade directory and log file.

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
