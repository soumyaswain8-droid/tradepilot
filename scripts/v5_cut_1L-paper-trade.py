#!/usr/bin/env python3
"""
v5_cut_1L — small-account shadow at Rs 1,00,000 total capital.

SIZING RATIONALE (2026-08-03). The ask was "give each vertical Rs 10,000". Pool
weights are HARDCODED in prototype/v5/pool_manager.py AND shift by regime, and that
module is shared by all live engines — so they cannot be equalised without changing
every engine. Instead the TOTAL is sized so each vertical clears Rs 10,000 in the
WORST regime. Binding case is BEAR's POSITIONAL at 10% => Rs 1,00,000 total.

  SIDEWAYS  INTRADAY 35,000  SWING 20,000  POSITIONAL 20,000  INVESTMENT 15,000
  BULL      INTRADAY 30,000  SWING 30,000  POSITIONAL 25,000  INVESTMENT 15,000
  BEAR      INTRADAY 25,000  SWING 15,000  POSITIONAL 10,000  INVESTMENT 20,000

WHY NOT Rs 10,000 TOTAL: tried first, and all three shadows opened ZERO positions.
Rs 10,000 splits to roughly Rs 300-600 per slot against a median NIFTY-200 share
price of Rs 1,267, so qty always floored to 0. The engine has an implicit minimum
viable capital of roughly Rs 40,000; below it, it silently does nothing.

PARAMS ARE INLINED, NOT CHAINED: the parent script sets ENGINE_NAME itself and would
clobber this shadow, writing small-capital state into the LIVE directory. Caught
before launch on 2026-08-03. If the parent's params change, mirror them here.
"""
import os, sys, runpy
from pathlib import Path

os.environ["WRONGWAY_CUT_PCT"]    = "1.0"
os.environ["SHORT_REQ_CHG_PCT"]   = "-1.0"
os.environ["SHORT_REQ_MAX_SCORE"] = "30"
# --- shadow overrides, set LAST so nothing can clobber them ---
os.environ["ENGINE_NAME"]   = "v5_cut_1L"
os.environ["TOTAL_CAPITAL"] = "100000"
os.environ["TELEGRAM_DISABLE"] = "1"

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
