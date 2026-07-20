"""RiskGate three-state verdict — unit tests (Phase 0, spec 2026-07-20).

Mirrors tests/test_rrg_regime.py / tests/test_chop_ladder.py style: a small
stub stands in for RiskManager so the gate is tested in isolation, with no
network and no real pool/risk state. The gate ORCHESTRATES the existing
RiskManager surface (check_can_trade, check_position_size, get_risk_dashboard,
kill_switch_tripped) — it must never reimplement risk_manager.py's logic and
must never raise, even when the wrapped RiskManager misbehaves.

Run: python3 -m pytest tests/test_risk_gate.py -v
"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.v5.risk_gate import TradePlan, Verdict, GateResult, RiskGate


# ─────────────────────────── stubs ───────────────────────────

class _StubPool:
    def __init__(self, cash=100_000.0):
        self.cash = cash


class _StubPoolManager:
    def __init__(self, pools=None):
        self.pools = pools or {"INTRADAY": _StubPool()}


class _StubRiskManager:
    """Configurable stand-in for prototype.v5.risk_manager.RiskManager.

    Only implements the surface RiskGate is allowed to touch. Defaults to a
    fully clean state (everything passes).
    """

    def __init__(self, *, can_trade=(True, "OK"), size_ok=(True, "OK"),
                 kill_switch_tripped=False, session_pnl_rs=0.0,
                 vix_multiplier=1.0, pools=None):
        self._can_trade = can_trade
        self._size_ok = size_ok
        self.kill_switch_tripped = kill_switch_tripped
        self.session_pnl_rs = session_pnl_rs
        self._vix_multiplier = vix_multiplier
        self.pm = _StubPoolManager(pools)

    def check_can_trade(self, pool_name, symbol, position_type=None):
        return self._can_trade

    def check_position_size(self, cost_or_margin, pool_name):
        return self._size_ok

    def get_risk_dashboard(self):
        return {"vix_multiplier": self._vix_multiplier}


class _RaisingRiskManager(_StubRiskManager):
    """Every method raises -- used to prove evaluate() never propagates."""

    def check_can_trade(self, pool_name, symbol, position_type=None):
        raise RuntimeError("boom")

    def check_position_size(self, cost_or_margin, pool_name):
        raise RuntimeError("boom")

    def get_risk_dashboard(self):
        raise RuntimeError("boom")


def _plan(**overrides):
    base = dict(
        symbol="RELIANCE", side="LONG", entry=2500.0, target=2550.0,
        stop=2470.0, invalidation="score_drop_below:50.0", size_rs=15000.0,
        pool="INTRADAY", score=62.0, rationale="BUY rank=3 score=62.0",
    )
    base.update(overrides)
    return TradePlan(**base)


# ─────────────────────────── TradePlan / GateResult shape ───────────────────────────

class TestTradePlanShape(unittest.TestCase):
    def test_fields_match_spec_4_1(self):
        p = _plan()
        for field in ("symbol", "side", "entry", "target", "stop", "invalidation",
                      "size_rs", "pool", "score", "rationale"):
            self.assertTrue(hasattr(p, field))

    def test_invalidation_is_score_drop_below_form(self):
        p = _plan()
        self.assertTrue(p.invalidation.startswith("score_drop_below:"))


class TestVerdictEnum(unittest.TestCase):
    def test_three_states(self):
        self.assertEqual(Verdict.APPROVED.value, "approved")
        self.assertEqual(Verdict.WATCHLIST.value, "watchlist")
        self.assertEqual(Verdict.REJECTED.value, "rejected")


# ─────────────────────────── decision paths ───────────────────────────

class TestApprovedPath(unittest.TestCase):
    def test_clean_pass_is_approved(self):
        rm = _StubRiskManager(vix_multiplier=1.0)
        gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
        result = gate.evaluate(_plan(score=90.0))
        self.assertEqual(result.verdict, Verdict.APPROVED)
        self.assertIsInstance(result, GateResult)

    def test_result_is_self_contained(self):
        rm = _StubRiskManager()
        gate = RiskGate(rm)
        plan = _plan()
        result = gate.evaluate(plan)
        self.assertEqual(result.symbol, plan.symbol)
        self.assertEqual(result.plan, plan)


class TestRejectedPath(unittest.TestCase):
    def test_hard_breaker_fail_rejects(self):
        rm = _StubRiskManager(can_trade=(False, "ALL-STOP active (tier 5): Portfolio monthly loss > 7%"))
        gate = RiskGate(rm)
        result = gate.evaluate(_plan(score=90.0))
        self.assertEqual(result.verdict, Verdict.REJECTED)
        self.assertTrue(any("ALL-STOP" in r for r in result.reasons))

    def test_blacklist_fail_rejects(self):
        rm = _StubRiskManager(can_trade=(False, "RELIANCE banned until 2026-07-25: blacklisted"))
        gate = RiskGate(rm)
        result = gate.evaluate(_plan())
        self.assertEqual(result.verdict, Verdict.REJECTED)

    def test_position_size_fail_rejects(self):
        rm = _StubRiskManager(size_ok=(False, "Position size Rs 50,000 > 10% of INTRADAY capital"))
        gate = RiskGate(rm)
        result = gate.evaluate(_plan(score=90.0))
        self.assertEqual(result.verdict, Verdict.REJECTED)
        self.assertTrue(any("check_position_size" in r and "FAIL" in r for r in result.reasons))

    def test_pool_cash_fail_rejects(self):
        rm = _StubRiskManager(pools={"INTRADAY": _StubPool(cash=1000.0)})
        gate = RiskGate(rm)
        result = gate.evaluate(_plan(score=90.0, size_rs=15000.0, pool="INTRADAY"))
        self.assertEqual(result.verdict, Verdict.REJECTED)
        self.assertTrue(any("pool_cash" in r and "FAIL" in r for r in result.reasons))

    def test_session_loss_kill_switch_rejects(self):
        rm = _StubRiskManager(kill_switch_tripped=True, session_pnl_rs=-6000.0)
        gate = RiskGate(rm)
        result = gate.evaluate(_plan(score=90.0))
        self.assertEqual(result.verdict, Verdict.REJECTED)
        self.assertTrue(any("session_loss_kill_switch" in r and "FAIL" in r for r in result.reasons))

    def test_hard_fail_wins_over_soft_signal(self):
        # score is near threshold (soft) AND breaker active (hard) -> still REJECTED
        rm = _StubRiskManager(can_trade=(False, "Pool INTRADAY breaker active (tier 1)"))
        gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
        result = gate.evaluate(_plan(score=52.0))
        self.assertEqual(result.verdict, Verdict.REJECTED)


class TestWatchlistPath(unittest.TestCase):
    def test_score_near_threshold_is_watchlist(self):
        rm = _StubRiskManager(vix_multiplier=1.0)
        gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
        result = gate.evaluate(_plan(score=53.0))
        self.assertEqual(result.verdict, Verdict.WATCHLIST)
        self.assertTrue(any("soft:score_near_threshold" in r and "FIRED" in r for r in result.reasons))

    def test_score_far_from_threshold_does_not_fire_that_signal(self):
        rm = _StubRiskManager(vix_multiplier=1.0)
        gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
        result = gate.evaluate(_plan(score=90.0))
        self.assertTrue(any("soft:score_near_threshold" in r and "clear" in r for r in result.reasons))

    def test_vix_multiplier_below_one_is_watchlist(self):
        rm = _StubRiskManager(vix_multiplier=0.60)
        gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
        result = gate.evaluate(_plan(score=90.0))
        self.assertEqual(result.verdict, Verdict.WATCHLIST)
        self.assertTrue(any("soft:vix_multiplier" in r and "FIRED" in r for r in result.reasons))

    def test_data_guard_degraded_is_watchlist(self):
        rm = _StubRiskManager(vix_multiplier=1.0)
        gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
        result = gate.evaluate(_plan(score=90.0), data_guard_ok=False)
        self.assertEqual(result.verdict, Verdict.WATCHLIST)
        self.assertTrue(any("soft:data_guard_degraded" in r for r in result.reasons))


# ─────────────────────────── reasons completeness ───────────────────────────

class TestReasonsCompleteness(unittest.TestCase):
    def test_all_checks_recorded_regardless_of_outcome(self):
        rm = _StubRiskManager(vix_multiplier=1.0)
        gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
        result = gate.evaluate(_plan(score=90.0))
        joined = " | ".join(result.reasons)
        for check in ("check_can_trade", "check_position_size", "pool_cash",
                      "session_loss_kill_switch", "soft:score_near_threshold",
                      "soft:vix_multiplier", "soft:data_guard"):
            self.assertIn(check, joined, f"missing check in reasons: {check}")

    def test_checked_at_is_set(self):
        rm = _StubRiskManager()
        gate = RiskGate(rm)
        result = gate.evaluate(_plan())
        self.assertTrue(result.checked_at)


# ─────────────────────────── fail-safe: evaluate() never raises ───────────────────────────

class TestNeverRaises(unittest.TestCase):
    def test_raising_risk_manager_is_caught_per_check(self):
        # Each RiskManager call is individually guarded, so a raising
        # RiskManager degrades to explicit FAIL reasons (and a REJECTED
        # verdict, since check_can_trade/check_position_size fail closed)
        # rather than the coarser outer gate_error catch.
        rm = _RaisingRiskManager()
        gate = RiskGate(rm)
        try:
            result = gate.evaluate(_plan())
        except Exception as e:
            self.fail(f"evaluate() raised: {e}")
        self.assertIsInstance(result, GateResult)
        self.assertEqual(result.verdict, Verdict.REJECTED)
        joined = " | ".join(result.reasons)
        self.assertIn("check_can_trade raised", joined)
        self.assertIn("check_position_size raised", joined)

    def test_outer_guard_catches_unexpected_plan_errors(self):
        # A malformed plan (non-numeric score) blows up arithmetic outside
        # the per-check try/excepts -- the outer evaluate() guard must still
        # catch it and return a GateResult instead of propagating.
        rm = _StubRiskManager()
        gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
        bad_plan = _plan(score="not-a-number")
        try:
            result = gate.evaluate(bad_plan)
        except Exception as e:
            self.fail(f"evaluate() raised: {e}")
        self.assertIsInstance(result, GateResult)
        self.assertEqual(result.verdict, Verdict.WATCHLIST)
        self.assertTrue(any("gate_error" in r for r in result.reasons))

    def test_missing_pm_attribute_does_not_raise(self):
        rm = _StubRiskManager()
        del rm.pm
        gate = RiskGate(rm)
        try:
            result = gate.evaluate(_plan())
        except Exception as e:
            self.fail(f"evaluate() raised: {e}")
        self.assertIsInstance(result, GateResult)


if __name__ == "__main__":
    unittest.main()
