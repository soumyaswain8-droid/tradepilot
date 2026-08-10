#!/usr/bin/env python3
"""v5_rrg — RRG rotation-sensor chop-filter shadow (RRG Gate-1 PASS, 2026-07-20).

Same v5 code, same 2-tier CHOP-throttle machinery as v5_chop
(spec 2026-07-17), but with the score producer swapped: instead of
TrendScore (tape efficiency + breadth + premarket regime, which failed
Gate-1 at profit-capture 70% / loss-capture 54%), the mode ladder is driven
by prototype/v5/rrg_regime.py's daily defensive-vs-cyclical rotation COUNT
signal (form=count, set=extended, N=1, threshold=-0.2143) -- the sensor
that just PASSED Gate-1 at profit-capture 85% / loss-capture 73% (data-repair
re-run, report 1cr-roadmap/research/2026-07-20_gate1-rrg-sensor-backtest.md, commit
d23726e). The score is daily-bar-driven and computed ONCE per session
(premarket tilt held constant intraday, not recomputed per scan) -- per the
design doc's "tilt, not trigger" framing (docs/superpowers/specs/2026-07-20-
rrg-regime-sensor-design.md §5/§7, citing docs/research/regime-switching-
daily/2026-07-13.md, "tilt input, not trading trigger").

WHY: TrendScore's own Gate-1 could not clear 70/70 for a clean TREND leg
(best joint combo 70/54), so v5_chop shipped as a CHOP-only 2-tier throttle
on a sensor that never cleared the bar. RRG's rotation-count sensor DID
clear 70/70 outright (85/73) -- this shadow tests whether that Gate-1 edge
translates into better live Gate-2 economics on the SAME ladder mechanics
(mode_for hysteresis, apply_ladder CHOP/NEUTRAL/TREND multipliers) v5_chop
already uses, isolating the sensor swap as the only variable.

Gate-2 (same criteria as v5_chop): 2-week shadow vs v5 -- promote only on
better net AND lower cost drag AND no worse max drawdown. Early-kill if
trailing live v5 by more than Rs 5,000 after week 1.

Runs alongside the roster; own state/log; re-comment in launch-market to end.
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]     = "v5_rrg"
os.environ["CHOP_FILTER"]     = "1"
os.environ["REGIME_SENSOR"]   = "rrg"
os.environ["ML_SCORE_WEIGHT"] = "0"
os.environ["TELEGRAM_DISABLE"] = "1"   # shadow: only live v5 alerts

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
