#!/usr/bin/env python3
"""v5_chop — chop-filter shadow (spec 2026-07-17).

Same v5 code with CHOP_FILTER=1. TrendScore (tape efficiency 40% + breadth
40% + premarket regime 20%, calibrated td=1.0/bm=1.0/rd=6 — the Gate-1 joint
sweep's best CHOP-separating combo, loss-capture 85% in the June-July
backtest) drives a 2-tier ladder: CHOP days (TrendScore < 45) get max-3
top-quartile entries at 0.4x size in 0.5x budget; ALL non-CHOP days (NEUTRAL
and TREND alike) trade vanilla v5, unfiltered (2-scan hysteresis on mode
changes). ML-free (proven selection-neutral, IC 0.006).

WHY: Jun16-Jul16 v5 lost Rs766/day on the 19 SIDEWAYS days and made money only
on trend days; Rs211k of Rs359k on-table was symmetric whipsaw. Gate 1 could
not clear the 70/70 profit/loss-capture bar for a clean TREND leg (best joint
combo: profit-capture 70%, loss-capture 54%), so the design was cut to 2
tiers -- CHOP-only throttle, since the sensor's best-in-class skill is
flagging bleed days, not flagging green ones. Gate 2: 2-week shadow vs v5 --
promote only on better net AND lower cost drag AND no worse DD.
Runs alongside the roster; own state/log; re-comment in launch-market to end.
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]     = "v5_chop"
os.environ["CHOP_FILTER"]     = "1"
os.environ["ML_SCORE_WEIGHT"] = "0"

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
