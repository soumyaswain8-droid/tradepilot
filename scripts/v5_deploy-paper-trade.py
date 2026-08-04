#!/usr/bin/env python3
"""v5_deploy — v5 with capital allocated only to pools that actually trade.

THE BRIEF
Soumya: "we are now experimenting on intraday, reallocate to INTRADAY 50 / SWING 30 /
POSITIONAL 20 — if POSITIONAL is not advisable, move it to intraday and swing", and
"I want the full 90% of the pool amount deployed every day if the market permits".

WHY POSITIONAL IS NOT ADVISABLE — it has never been used, ever
Measured 2026-08-04 across every engine's full history: POSITIONAL, INVESTMENT and
RESERVE hold 45% of capital and have received ZERO trades. Not few — zero. Every
signal defaults to INTRADAY (`sig.get("pool", "INTRADAY")`), and nothing in the
strategy ever assigns a longer-horizon pool. So allocating 20% to POSITIONAL would
park a fifth of the book somewhere no trade can reach it.

    engine     INTRADAY  SWING  POSITIONAL  INVESTMENT
    v5              122     36           0           0
    v5_cut          185    171           0           0
    v5_1L            87     15           0           0

That is also the whole explanation for the fleet looking "under-deployed". The
ceiling was INTRADAY 30% + SWING 25% = 55%, and the money was not idle by choice.

HOW 90% IS REACHED — WITHOUT touching position sizing
Simulated against the real constraints (Rs 10,000 pool floor, 20-position cap,
KELLY_CAP 25%), at the UNCHANGED sizer of 0.15:

    allocation                          deployed
    today (INTRADAY 30 / SWING 25)         52.9%
    50 / 30 / 20 with POSITIONAL idle      76.9%
    INTRADAY 60 / SWING 40                 96.1%   <- this engine

So the target is met by not parking capital in dead pools. Raising the sizer was
unnecessary: 0.15 -> 0.30 moves deployment 96.1% -> 98.3%, because bigger positions
just drain the pool in fewer trades. Leaving the sizer alone keeps this a
single-variable experiment.

THE RISK, STATED PLAINLY
96% deployed means ~2x today's exposure to a bad session. The stop-loss guard limits
each POSITION, not the book; a broad gap-down hits everything at once. That is the
trade being tested, and it is why this runs as a shadow beside v5 rather than as a
change to it.

WATCH: net P&L vs v5 on RED days especially, max drawdown, and whether deployment
actually reaches ~90% or stalls on the 20-position cap.

Run:
    python3 scripts/v5_deploy-paper-trade.py
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"] = "v5_deploy"
# THE one variable. POSITIONAL/INVESTMENT/RESERVE default to 0.0 and the override
# PINS the split, so a regime change cannot silently restore them mid-session.
os.environ["POOL_ALLOC"]  = '{"INTRADAY":0.60,"SWING":0.40}'
os.environ["TELEGRAM_DISABLE"] = "1"       # shadow: only live v5 alerts

# Deliberately NOT set, to keep this single-variable against v5:
#   MIN_ENTRY_SCORE (that is v5_pick), NSE_DATA_SOURCE (that is v5_kite),
#   CHOP_FILTER, RISK_GATE_DRIVE, and the sizer's 0.15 — unchanged, see above.

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
