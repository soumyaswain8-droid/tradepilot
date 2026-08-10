"""TradePilot v5 -- Risk Gate + Three-State Verdict (Phase 0)
================================================================
Spec: 1cr-roadmap/research/2026-07-20_risk_gate_three_state_verdict.md (S4).

Phase 0 scope ONLY: schema (`TradePlan`, `Verdict`, `GateResult`) + the
`RiskGate` orchestrator. This module wraps an EXISTING `prototype.v5.
risk_manager.RiskManager` instance -- it never reimplements or mutates its
drawdown/breaker/blacklist logic. It is log-only: nothing in this file
changes what gets deployed (that wiring lives in scripts/v5-paper-trade.py
and is itself log-only for Phase 0 -- see spec S5).

Decision rule (spec S4.2):
  REJECTED  -- any HARD check fails.
  WATCHLIST -- no hard fail, but any SOFT signal fires.
  APPROVED  -- clean pass on every check.

Hard checks (mapped to what RiskManager actually exposes):
  * check_can_trade(pool, symbol, position_type) -- this single call already
    covers portfolio ALL-STOP, the baseline session-loss kill-switch, pool
    breaker state, pool-paused, the stock blacklist/ban list, the
    per-direction slot cap, and the same-sector guard. We deliberately do
    NOT call `RiskManager.check_all_breakers()` directly from the gate:
    that method has side effects (it can fire a NEW pool/portfolio breaker,
    pause a pool, or set `pool.reduced = True`). The live engine's MONITOR
    phase (`scan_positions`) already calls `check_all_breakers()` every scan
    cycle before any redeploy happens, so `check_can_trade()` always reflects
    whatever `check_all_breakers()` most recently decided -- reading it here
    is faithful to spec's "breakers via check_all_breakers" intent without
    giving a log-only audit module the power to trip a breaker itself.
  * check_position_size(cost_or_margin, pool) -- position-size fail.
  * pool cash -- plan.size_rs compared against RiskManager.pm.pools[pool].cash
    (spec's "pool cash fail"; RiskManager has no dedicated method for this,
    so the gate reads the pool's `cash` property directly -- read-only).
  * session-loss limit -- RiskManager.kill_switch_tripped /
    session_pnl_rs, surfaced as its own reason line even though
    check_can_trade() already gates on it (spec calls it out separately).

Soft signals implemented (spec S4.2):
  * score within `soft_band` points of the signal threshold in use.
  * VIX multiplier < 1.0, read from RiskManager.get_risk_dashboard()
    ["vix_multiplier"] (the isolated VIX-only multiplier RiskManager
    already computes and exposes -- NOT the combined VIX*recovery*regime
    `get_effective_multiplier()`).
  * DATA-GUARD degraded feed -- caller-supplied `data_guard_ok` flag (the
    v5 engine already computes tape freshness via `_live_tape_ok()` before
    this point; the gate does not re-fetch network data itself).

Soft signals from spec S4.2 NOT observable in the current codebase --
recorded here, per spec instruction, rather than invented:
  * "sector already at exposure cap" (soft/near-cap warning) -- NOT
    IMPLEMENTED. RiskManager's same-sector guard (MAX_SAME_SECTOR) is a
    HARD block inside check_can_trade(); there is no intermediate
    "approaching the cap" state exposed to read as a soft signal.
  * "breaker in warning tier" -- NOT IMPLEMENTED. `BreakerState` only has
    `active` (bool) and `tier` (the already-fired tier, 1-5); RiskManager
    exposes no pre-trigger "approaching a breaker" signal to read.

`evaluate()` is internally guarded: it never raises. Any internal error is
recorded as a reason and defaults the verdict to WATCHLIST (never a silent
APPROVED, never an alarm-triggering REJECTED for what is only an audit
module's own bug).
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional


@dataclass
class TradePlan:
    """First-class plan object (spec S4.1). Built from a signal BEFORE any
    risk logic runs -- every candidate that clears the signal threshold
    becomes a TradePlan."""
    symbol: str
    side: str                    # LONG / SHORT
    entry: float
    target: float
    stop: float
    invalidation: str            # machine-checkable thesis falsifier, e.g.
                                  # "score_drop_below:55" (Phase 0 default form)
    size_rs: float
    pool: str
    score: float                 # scorer output that produced this plan
    rationale: str                # one line, for audit trail


class Verdict(Enum):
    APPROVED = "approved"
    WATCHLIST = "watchlist"
    REJECTED = "rejected"


@dataclass
class GateResult:
    """Spec S4.2 fields (verdict, reasons, checked_at) plus `symbol`/`plan`
    so each artifact row is self-contained without a join back to the
    signal batch."""
    verdict: Verdict
    reasons: List[str]           # every check that fired, pass or fail
    checked_at: str
    symbol: str
    plan: TradePlan


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class RiskGate:
    """Orchestrates an existing RiskManager instance -- see module docstring
    for exactly which RiskManager methods/attributes are read and why."""

    def __init__(self, risk_manager, score_threshold: float = 50.0,
                 soft_band: float = 5.0):
        self.rm = risk_manager
        self.score_threshold = score_threshold
        self.soft_band = soft_band

    def evaluate(self, plan: TradePlan, *, position_type: Optional[str] = None,
                 cost_or_margin: Optional[float] = None,
                 data_guard_ok: bool = True) -> GateResult:
        """Never raises. Returns a GateResult even if the wrapped
        RiskManager throws."""
        reasons: List[str] = []
        try:
            hard_fail = self._run_hard_checks(plan, position_type, cost_or_margin, reasons)
            soft_hit = self._run_soft_checks(plan, data_guard_ok, reasons)

            if hard_fail:
                verdict = Verdict.REJECTED
            elif soft_hit:
                verdict = Verdict.WATCHLIST
            else:
                verdict = Verdict.APPROVED

            return GateResult(verdict=verdict, reasons=reasons,
                               checked_at=_now_iso(), symbol=plan.symbol, plan=plan)
        except Exception as e:
            reasons.append(f"gate_error: {type(e).__name__}: {e}")
            # Fail toward review, not toward a silent all-clear or an
            # over-alarming reject -- this failure is in the AUDIT module,
            # not necessarily in the trade itself.
            return GateResult(verdict=Verdict.WATCHLIST, reasons=reasons,
                               checked_at=_now_iso(),
                               symbol=getattr(plan, "symbol", "?"), plan=plan)

    # --- hard checks (any fail -> REJECTED) ---

    def _run_hard_checks(self, plan: TradePlan, position_type: Optional[str],
                          cost_or_margin: Optional[float], reasons: List[str]) -> bool:
        hard_fail = False

        pt = position_type or ("SHORT" if str(plan.side).upper() == "SHORT" else "LONG")
        try:
            ok, reason = self.rm.check_can_trade(plan.pool, plan.symbol, pt)
        except Exception as e:
            ok, reason = False, f"check_can_trade raised: {e}"
        if ok:
            reasons.append("check_can_trade: OK")
        else:
            reasons.append(f"check_can_trade: FAIL — {reason}")
            hard_fail = True

        cost = cost_or_margin if cost_or_margin is not None else plan.size_rs
        try:
            size_ok, size_reason = self.rm.check_position_size(cost, plan.pool)
        except Exception as e:
            size_ok, size_reason = False, f"check_position_size raised: {e}"
        if size_ok:
            reasons.append("check_position_size: OK")
        else:
            reasons.append(f"check_position_size: FAIL — {size_reason}")
            hard_fail = True

        cash_result = self._pool_cash_check(plan)
        reasons.append(cash_result[1])
        if not cash_result[0]:
            hard_fail = True

        kill_tripped = bool(getattr(self.rm, "kill_switch_tripped", False))
        if kill_tripped:
            pnl = getattr(self.rm, "session_pnl_rs", None)
            reasons.append(f"session_loss_kill_switch: FAIL — session P&L Rs {pnl}")
            hard_fail = True
        else:
            reasons.append("session_loss_kill_switch: OK")

        return hard_fail

    def _pool_cash_check(self, plan: TradePlan):
        """Read-only comparison of plan.size_rs against the pool's available
        cash (RiskManager.pm.pools[pool].cash). Not evaluable (treated as a
        pass, noted as such) if the pool/pm surface isn't present."""
        pm = getattr(self.rm, "pm", None)
        if pm is None:
            return True, "pool_cash: not evaluable (no pool manager on RiskManager)"
        pool = getattr(pm, "pools", {}).get(plan.pool)
        if pool is None:
            return True, f"pool_cash: not evaluable (unknown pool '{plan.pool}')"
        cash = getattr(pool, "cash", None)
        if cash is None:
            return True, "pool_cash: not evaluable (pool has no cash attribute)"
        if plan.size_rs > cash:
            return False, (f"pool_cash: FAIL — plan size Rs {plan.size_rs:,.0f} > "
                            f"{plan.pool} cash Rs {cash:,.0f}")
        return True, "pool_cash: OK"

    # --- soft checks (any fire -> WATCHLIST, unless a hard check already failed) ---

    def _run_soft_checks(self, plan: TradePlan, data_guard_ok: bool, reasons: List[str]) -> bool:
        soft_hit = False

        near_threshold = abs(float(plan.score) - self.score_threshold) <= self.soft_band
        if near_threshold:
            reasons.append(f"soft:score_near_threshold: FIRED — score {plan.score} within "
                            f"{self.soft_band} of threshold {self.score_threshold}")
            soft_hit = True
        else:
            reasons.append(f"soft:score_near_threshold: clear (score {plan.score}, "
                            f"threshold {self.score_threshold})")

        vix_mult = None
        try:
            dashboard = self.rm.get_risk_dashboard()
            vix_mult = dashboard.get("vix_multiplier")
        except Exception as e:
            reasons.append(f"soft:vix_multiplier: not evaluable ({e})")
        if vix_mult is not None:
            if vix_mult < 1.0:
                reasons.append(f"soft:vix_multiplier: FIRED — {vix_mult} < 1.0")
                soft_hit = True
            else:
                reasons.append(f"soft:vix_multiplier: clear ({vix_mult})")

        if not data_guard_ok:
            reasons.append("soft:data_guard_degraded: FIRED — live tape unavailable/stale")
            soft_hit = True
        else:
            reasons.append("soft:data_guard_degraded: clear")

        return soft_hit
