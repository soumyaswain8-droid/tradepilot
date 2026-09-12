#!/usr/bin/env python3
"""
build_universe_engine — the Floor's universe = the engines' universe.

WHY. The Floor's scouts default to scanning the whole NSE cash universe
(universe_full.txt), while the trading engines only ever act on
prototype/data_engine.NIFTY_STOCKS. An escalation the Floor raises on a name
no engine can trade is a veto with nothing to veto. This file is the bridge:
it derives quant/universe_engine.txt directly from NIFTY_STOCKS, so pointing
the scouts at it (see prototype/agents/scouts.py, FLOOR_UNIVERSE) makes every
escalation land on a stock the engines actually hold.

NIFTY_STOCKS carries a handful of ".BO" (BSE) entries alongside the ".NS"
(NSE) majority; the scouts' universe files are NSE-only bare symbols, so BO
entries are dropped here rather than mistranslated.

Rebuild whenever prototype/data_engine.py's stock lists change:
    python3 quant/build_universe_engine.py
"""
import os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
# prototype/data_engine.py does a bare `from stock_universe import (...)`, which
# only resolves with prototype/ itself on sys.path (the same reason
# prototype/app.py inserts its own directory at import time) -- ROOT alone
# is not enough.
sys.path.insert(0, os.path.join(ROOT, "prototype"))
from prototype.data_engine import NIFTY_STOCKS  # noqa: E402

syms = sorted({s.replace(".NS", "") for s in NIFTY_STOCKS if s.endswith(".NS")})
out = os.path.join(ROOT, "quant", "universe_engine.txt")
with open(out, "w") as f:
    f.write("\n".join(syms) + "\n")
print(f"wrote {out}: {len(syms)} symbols")
