#!/usr/bin/env python3
"""v5_gate — Risk Gate DRIVES execution shadow (Gate-2, spec 2026-07-20).

Same v5 code, NO regime throttle (CHOP_FILTER unset — this isolates the gate
effect on its own, keeping four-way attribution clean across v5 / v5_chop /
v5_rrg / v5_gate). RISK_GATE_DRIVE=1 makes prototype/v5/risk_gate.py's
RiskGate ACTUALLY decide deployment instead of only logging it (that log-only
Phase 0 shipped 2026-07-20, commits df90250/5682b22, and keeps running here
too via RISK_GATE_LOG=1 for the audit trail): REJECTED candidates are
skipped, WATCHLIST candidates defer to the next scan cycle (fresh
re-evaluation, no capital reserved, expires with daily state — spec S7 Q1/Q2),
APPROVED deploys. INVALIDATION_MONITOR=1 adds Phase 2: scan_positions checks
each open position's TradePlan invalidation string and exits on trigger with
reason INVALIDATED (distinct from STOP/TARGET/AGED) — only the
score_drop_below:<n> form is enforced (state["last_signals"] rescore data,
already in hand); close_below:<ind> and rrg_quadrant_exit:<sector> have no
data source in that loop and are recorded not_enforced per position, not
invented. ML-free (ML_SCORE_WEIGHT=0).

Spec: docs/research/2026-07-20_risk_gate_three_state_verdict.md S4.2
(decision rule), S5 Phases 1-2.

Phase-1 pass criteria (spec S5, verbatim):
  - Fewer trades on chop days with equal-or-better P&L capture ratio
  - Zero APPROVED trades that inline logic would have blocked (gate is
    never *looser* than inline)
  - `INVALIDATED` exits show better avg exit price than the eventual stop
    would have

Gate 2 (same window/kill conventions as v5_chop/v5_rrg): 2-week shadow vs
live v5 — promote only on better net AND lower cost drag AND no worse max
drawdown. Early-kill if trailing live v5 by more than Rs 5,000 after week 1.

Runs alongside the roster; own state/log; re-comment in launch-market to end.
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]          = "v5_gate"
os.environ["RISK_GATE_DRIVE"]      = "1"
os.environ["INVALIDATION_MONITOR"] = "1"
os.environ["RISK_GATE_LOG"]        = "1"
os.environ["ML_SCORE_WEIGHT"]      = "0"
os.environ["TELEGRAM_DISABLE"]     = "1"   # shadow: only live v5 alerts
# Deliberately NOT set: CHOP_FILTER — v5_gate tests the gate's effect alone.

# MAX_POSITION_PCT 0.16 (2026-08-04) — makes the gate SATISFIABLE.
#
# v5_gate took zero trades in every session from 2026-07-21 to 08-04: 4,270 gate
# evaluations, 0 approved, 0 watchlisted. Not market conditions — a contradiction
# between two constants. The sizer asks for 15% of pool budget; the cap allowed 10%.
# 15% > 10% always, so every candidate was rejected on check_position_size.
#
# 0.16 sits just above the sizer's maximum ask (15% x an effective multiplier of at
# most 1.0) and well below KELLY_CAP's 25%. So normal sizing passes while a genuinely
# oversized position — the VEDL incident this cap was promoted for on 2026-05-01 —
# is still blocked. Setting it at or below 0.15 would keep the engine mute; setting
# it at 0.25 would make the check a no-op. This is the narrow band that leaves the
# guard meaningful AND lets the engine trade.
#
# Scoped to THIS engine only. risk_manager still defaults to 0.10, so the other ten
# engines are untouched and their logged gate verdicts stay comparable with history.
os.environ["MAX_POSITION_PCT"]     = "0.16"

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
