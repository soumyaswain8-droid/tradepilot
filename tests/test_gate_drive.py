"""RISK_GATE_DRIVE + INVALIDATION_MONITOR integration tests (Phase 1+2,
spec 1cr-roadmap/research/2026-07-20_risk_gate_three_state_verdict.md S5).

Mirrors the importlib pattern + StubPool/FakeRM doubles from
tests/test_risk_gate_wiring.py and tests/test_chop_ladder.py. No network:
DATA_GUARD=0, get_prices_batch monkeypatched, _in_flat_exit_window forced
False.

Run: python3 -m pytest tests/test_gate_drive.py -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "v5_paper_trade_gate", str(PROJECT_ROOT / "scripts" / "v5-paper-trade.py"))
v5 = importlib.util.module_from_spec(_spec)
sys.modules["v5_paper_trade_gate"] = v5
try:
    _spec.loader.exec_module(v5)
except Exception as e:
    print(f"[warn] partial module load: {e}")


class StubPool:
    """Doubles as PoolManager and the single pool it exposes."""
    def __init__(self):
        self.deployed = []
        self.closed = []

    def deploy(self, pool, sym, qty, price, sl, tgt):
        self.deployed.append((sym, qty))
        return True

    def close_position(self, pool, sym, exit_price, reason):
        self.closed.append((sym, exit_price, reason))
        return True

    def get_pool_budget(self, pool):
        return 100_000

    @property
    def pools(self):
        return {"INTRADAY": self}


class FakeRM:
    """Minimal RiskManager double: clean pass on every check by default;
    `reject_syms` lets a test force a HARD fail on specific symbols."""
    def __init__(self, reject_syms=None):
        self.kill_switch_tripped = False
        self.session_pnl_rs = 0.0
        self.pm = None
        self.reject_syms = reject_syms or set()

    def check_can_trade(self, pool_name, symbol, position_type=None):
        if symbol in self.reject_syms:
            return False, "blacklisted (test)"
        return True, "OK"

    def get_position_size(self, pool_name, base):
        return base

    def check_position_size(self, cost_or_margin, pool_name):
        return True, "OK"

    def get_risk_dashboard(self):
        return {"vix_multiplier": 1.0}

    def check_all_breakers(self):
        return {}

    def record_trade_result(self, pool_name, symbol, pnl):
        pass


def _state():
    return {"pools": {"INTRADAY": {"positions": [], "closed": [], "pnl": 0}},
            "trend_mode": "CHOP", "trend_pending": None, "premarket": {},
            "regime": "SIDEWAYS", "last_signals": [],
            "summary": {"rescore_count": 0, "scan_count": 0, "total_pnl": 0,
                        "trades": 0, "wins": 0, "losses": 0, "longs": 0,
                        "shorts": 0, "total_pnl_net": 0, "total_cost": 0}}


def _sig(sym, score, **kw):
    d = {"symbol": sym, "direction": "BUY", "score": score, "pool": "INTRADAY",
         "entry_price": 100.0, "sl_price": 98.5, "target_price": 102.0,
         "position_type": "LONG", "rank": 1, "change_pct": 0.5, "reasons": ["momentum"]}
    d.update(kw)
    return d


class _TmpTradeDir(unittest.TestCase):
    def setUp(self):
        os.environ["DATA_GUARD"] = "0"
        os.environ["CHOP_FILTER"] = "0"
        os.environ["RISK_GATE_LOG"] = "0"  # isolate: not re-testing Phase 0 logging here
        self.addCleanup(os.environ.pop, "DATA_GUARD", None)
        self.addCleanup(os.environ.pop, "CHOP_FILTER", None)
        self.addCleanup(os.environ.pop, "RISK_GATE_LOG", None)
        self.addCleanup(os.environ.pop, "RISK_GATE_DRIVE", None)
        self.addCleanup(os.environ.pop, "INVALIDATION_MONITOR", None)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._patch_dir = mock.patch.object(v5, "TRADE_DIR", Path(self._tmpdir.name))
        self._patch_dir.start()
        self.addCleanup(self._patch_dir.stop)


# ═══════════════════════════ TASK 1: RISK_GATE_DRIVE ═══════════════════════════

class TestDriveFlagOffIsVanilla(_TmpTradeDir):
    """Flag-off proof: RISK_GATE_DRIVE unset -> deployments byte-identical to
    a run where the gate would have rejected/watchlisted a candidate."""

    def test_flag_off_deploys_everything_inline_would(self):
        os.environ.pop("RISK_GATE_DRIVE", None)
        pm, rm = StubPool(), FakeRM(reject_syms={"WOULDREJECT"})
        rm.pm = pm
        sigs = [_sig("WOULDREJECT", 90), _sig("WATCHY", 50), _sig("STRONG", 90)]
        count = v5.deploy_signals(_state(), pm, rm, sigs)
        # inline check_can_trade DOES still block WOULDREJECT (existing inline
        # path, unaffected by the gate) -- but WATCHY (a gate-soft-signal case)
        # deploys same as always since the gate isn't driving.
        deployed_syms = {s for s, _ in pm.deployed}
        self.assertIn("WATCHY", deployed_syms)
        self.assertIn("STRONG", deployed_syms)
        self.assertNotIn("WOULDREJECT", deployed_syms)  # inline path still blocks this


class TestDriveRejectsHardFail(_TmpTradeDir):
    def test_gate_rejected_symbol_never_deploys(self):
        os.environ["RISK_GATE_DRIVE"] = "1"
        pm, rm = StubPool(), FakeRM(reject_syms={"BADSTOCK"})
        rm.pm = pm
        sigs = [_sig("BADSTOCK", 50), _sig("GOODSTOCK", 90)]
        v5.deploy_signals(_state(), pm, rm, sigs)
        deployed_syms = {s for s, _ in pm.deployed}
        self.assertNotIn("BADSTOCK", deployed_syms)
        self.assertIn("GOODSTOCK", deployed_syms)


class TestDriveWatchlistDefersAndPromotes(_TmpTradeDir):
    def test_watchlist_symbol_deferred_then_promoted(self):
        os.environ["RISK_GATE_DRIVE"] = "1"
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        state = _state()

        # Scan 1: WATCH sits exactly at the batch's score threshold (min of
        # the batch) -> soft "near threshold" signal fires -> WATCHLIST.
        v5.deploy_signals(state, pm, rm, [_sig("WATCH", 50), _sig("ANCHOR", 90)])
        deployed_1 = {s for s, _ in pm.deployed}
        self.assertNotIn("WATCH", deployed_1)
        self.assertIn("WATCH", state["gate_watchlist"])
        self.assertEqual(state["gate_watchlist"]["WATCH"]["times_deferred"], 1)

        # Scan 2: WATCH's score has since improved well clear of this batch's
        # (lower) threshold -> APPROVED -> promoted off the watchlist.
        state["summary"]["scan_count"] += 1
        v5.deploy_signals(state, pm, rm, [_sig("WATCH", 90), _sig("FLOOR", 50)])
        deployed_2 = {s for s, _ in pm.deployed}
        self.assertIn("WATCH", deployed_2)
        self.assertNotIn("WATCH", state["gate_watchlist"])  # promoted -> removed


class TestDriveNoWatchlistCapitalReservation(_TmpTradeDir):
    """Spec S7 Q2: WATCHLIST reserves no capital -- a deferred symbol simply
    doesn't count against anything; nothing to assert beyond "it didn't
    deploy and no budget/slot bookkeeping references it"."""

    def test_deferred_symbol_leaves_no_position(self):
        os.environ["RISK_GATE_DRIVE"] = "1"
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        state = _state()
        v5.deploy_signals(state, pm, rm, [_sig("WATCH", 50), _sig("ANCHOR", 90)])
        self.assertEqual(len(state["pools"]["INTRADAY"]["positions"]), 1)  # only ANCHOR


class TestDriveFailClosedFallback(_TmpTradeDir):
    """If RiskGate itself throws with DRIVE on, fall back to the inline path
    for that scan -- must not silently halt deployments."""

    def test_gate_construction_error_falls_back_to_inline(self):
        os.environ["RISK_GATE_DRIVE"] = "1"
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        sigs = [_sig("A", 90), _sig("B", 91)]
        with mock.patch.object(v5, "RiskGate", side_effect=RuntimeError("boom")):
            count = v5.deploy_signals(_state(), pm, rm, sigs)
        self.assertEqual(count, 2)
        deployed_syms = {s for s, _ in pm.deployed}
        self.assertEqual(deployed_syms, {"A", "B"})

    def test_gate_error_does_not_propagate(self):
        os.environ["RISK_GATE_DRIVE"] = "1"
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        with mock.patch.object(v5, "RiskGate", side_effect=RuntimeError("boom")):
            try:
                v5.deploy_signals(_state(), pm, rm, [_sig("A", 90)])
            except Exception as e:
                self.fail(f"deploy_signals raised despite fail-closed-to-inline fallback: {e}")


class TestDriveVerdictsAnnotation(_TmpTradeDir):
    def test_verdicts_rows_carry_drive_mode_and_promotion_flags(self):
        os.environ["RISK_GATE_DRIVE"] = "1"
        os.environ["RISK_GATE_LOG"] = "1"
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        state = _state()
        v5.deploy_signals(state, pm, rm, [_sig("WATCH", 50), _sig("ANCHOR", 90)])
        data = json.loads(v5._verdicts_file().read_text())
        for row in data["verdicts"]:
            self.assertIn("drive_mode", row)
            self.assertTrue(row["drive_mode"])
            self.assertIn("promoted_from_watchlist", row)


class TestVerdictsSurviveDataGuardBlock(_TmpTradeDir):
    """2026-07-24 bug: deploy_signals returned 0 the instant _live_tape_ok()
    failed, BEFORE all_candidates was ever built and BEFORE the RISK_GATE_LOG
    block at the tail of the function ran. Every candidate that scan (which
    DATA-GUARD legitimately vetoes from *deployment*) silently vanished from
    the Phase-0 divergence artifact instead of being logged as filtered --
    on 07-24 this cost v5_gate its first scan of the day (09:10:22, right at
    market open when the tape is still catching up) while sibling log-only
    engines that happened to scan a few minutes later logged fine. The audit
    trail must capture every candidate + verdict regardless of whether
    DATA-GUARD blocked that scan's entries; only actual deployment should be
    suppressed."""

    def test_data_guard_block_still_logs_verdicts(self):
        os.environ["DATA_GUARD"] = "1"  # override _TmpTradeDir's default off
        os.environ["RISK_GATE_LOG"] = "1"
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        state = _state()
        with mock.patch.object(v5, "_live_tape_ok", return_value=False):
            count = v5.deploy_signals(state, pm, rm, [_sig("A", 90), _sig("B", 70)])
        self.assertEqual(count, 0)
        self.assertEqual(pm.deployed, [])  # DATA-GUARD still vetoes real entries
        path = v5._verdicts_file()
        self.assertTrue(path.exists(),
                         "verdicts artifact was never written -- DATA-GUARD block "
                         "ate the whole scan's audit trail")
        data = json.loads(path.read_text())
        symbols = {row["symbol"] for row in data["verdicts"]}
        self.assertEqual(symbols, {"A", "B"})
        for row in data["verdicts"]:
            self.assertEqual(row["inline_outcome"], "filtered")

    def test_data_guard_block_accumulates_across_scans(self):
        """A later successful scan must not clobber the blocked scan's rows --
        multiple scans append, they never overwrite."""
        os.environ["DATA_GUARD"] = "1"
        os.environ["RISK_GATE_LOG"] = "1"
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        state = _state()
        with mock.patch.object(v5, "_live_tape_ok", return_value=False):
            v5.deploy_signals(state, pm, rm, [_sig("BLOCKED1", 90)])
        with mock.patch.object(v5, "_live_tape_ok", return_value=True):
            v5.deploy_signals(state, pm, rm, [_sig("LIVE1", 90)])
        data = json.loads(v5._verdicts_file().read_text())
        symbols = {row["symbol"] for row in data["verdicts"]}
        self.assertEqual(symbols, {"BLOCKED1", "LIVE1"})


# ═══════════════════════════ TASK 2: INVALIDATION_MONITOR ═══════════════════════════

class TestInvalidationMonitor(_TmpTradeDir):
    def _position(self, invalidation=""):
        return {"symbol": "HOLD1", "entry_price": 100.0, "qty": 10, "cost": 1000.0,
                "entry_time": "10:00:00", "entry_date": "2026-07-21",
                "sl_price": 90.0, "target_price": 120.0,  # far away -- won't fire
                "position_type": "LONG", "pool": "INTRADAY",
                "trailing_activated": False, "peak_price": 100.0, "trough_price": 100.0,
                "score": 80, "direction": "BUY", "reasons": [], "invalidation": invalidation}

    def _state_with_position(self, invalidation=""):
        state = _state()
        state["pools"]["INTRADAY"]["positions"] = [self._position(invalidation)]
        return state

    def _run_scan(self, state, pm, rm, price=101.0):
        with mock.patch.object(v5, "get_prices_batch", lambda syms: {"HOLD1": price}), \
             mock.patch.object(v5, "_in_flat_exit_window", lambda: False):
            v5.scan_positions(state, pm, rm)

    def test_triggered_invalidation_exits_with_reason(self):
        os.environ["INVALIDATION_MONITOR"] = "1"
        state = self._state_with_position("score_drop_below:60")
        state["last_signals"] = [{"symbol": "HOLD1", "score": 40}]
        pm, rm = StubPool(), FakeRM()
        self._run_scan(state, pm, rm)
        self.assertEqual(state["pools"]["INTRADAY"]["positions"], [])
        self.assertEqual(len(pm.closed), 1)
        self.assertEqual(pm.closed[0][2], "INVALIDATED")

    def test_non_triggered_invalidation_holds_position(self):
        os.environ["INVALIDATION_MONITOR"] = "1"
        state = self._state_with_position("score_drop_below:60")
        state["last_signals"] = [{"symbol": "HOLD1", "score": 80}]
        pm, rm = StubPool(), FakeRM()
        self._run_scan(state, pm, rm)
        self.assertEqual(len(state["pools"]["INTRADAY"]["positions"]), 1)
        self.assertEqual(pm.closed, [])
        self.assertIn("checked", state["pools"]["INTRADAY"]["positions"][0]["invalidation_check"])

    def test_malformed_invalidation_ignored_gracefully(self):
        os.environ["INVALIDATION_MONITOR"] = "1"
        state = self._state_with_position("garbage-no-colon")
        pm, rm = StubPool(), FakeRM()
        try:
            self._run_scan(state, pm, rm)
        except Exception as e:
            self.fail(f"scan_positions raised on malformed invalidation: {e}")
        self.assertEqual(len(state["pools"]["INTRADAY"]["positions"]), 1)
        self.assertTrue(
            state["pools"]["INTRADAY"]["positions"][0]["invalidation_check"].startswith("not_enforced"))

    def test_not_computable_form_recorded_not_enforced(self):
        os.environ["INVALIDATION_MONITOR"] = "1"
        state = self._state_with_position("close_below:20DMA")
        pm, rm = StubPool(), FakeRM()
        self._run_scan(state, pm, rm)
        self.assertEqual(len(state["pools"]["INTRADAY"]["positions"]), 1)
        pos = state["pools"]["INTRADAY"]["positions"][0]
        self.assertTrue(pos["invalidation_check"].startswith("not_enforced"))
        self.assertEqual(pm.closed, [])

    def test_flag_off_untouched(self):
        os.environ.pop("INVALIDATION_MONITOR", None)
        state = self._state_with_position("score_drop_below:60")
        state["last_signals"] = [{"symbol": "HOLD1", "score": 10}]  # would trigger if on
        pm, rm = StubPool(), FakeRM()
        self._run_scan(state, pm, rm)
        self.assertEqual(len(state["pools"]["INTRADAY"]["positions"]), 1)
        self.assertNotIn("invalidation_check", state["pools"]["INTRADAY"]["positions"][0])
        self.assertEqual(pm.closed, [])


class TestPlanSizeMirrorsRiskSizing(_TmpTradeDir):
    """Regression (2026-07-21): v5_gate's first drive day rejected 494/494
    candidates because TradePlan.size_rs carried the raw 15% base while
    check_position_size caps at 10% of pool capital. The plan must carry
    rm.get_position_size's clamped figure — the size the engine would
    actually request — not the pre-adjustment base."""

    class _ClampRM(FakeRM):
        CAP = 30000.0  # models 10% of a 3L pool

        def get_position_size(self, pool_name, base):
            return min(base, self.CAP)

        def check_position_size(self, cost_or_margin, pool_name):
            if cost_or_margin > self.CAP:
                return False, f"Position size Rs {cost_or_margin:,.0f} > 10% cap"
            return True, "OK"

    def test_build_trade_plan_uses_rm_clamped_size(self):
        plan = v5._build_trade_plan(_sig("ABC", 80), 300000.0, 55.0, rm=self._ClampRM())
        self.assertEqual(plan.size_rs, 30000.0)  # not 45000 (raw 15% base)

    def test_build_trade_plan_without_rm_keeps_base(self):
        plan = v5._build_trade_plan(_sig("ABC", 80), 300000.0, 55.0)
        self.assertEqual(plan.size_rs, 45000.0)

    def test_drive_filter_not_rejected_by_unclamped_base(self):
        class BigBudgetPool(StubPool):
            def get_pool_budget(self, pool):
                return 300000.0  # 15% base = 45k > cap; clamped size = 30k fits
        state = _state()
        # two candidates: the low scorer defines the threshold (and soft-flags
        # itself to WATCHLIST); ABC at +20 above it must clear APPROVED now
        # that size_rs carries the clamped figure instead of the 45k base
        approved, promoted, inv = v5._gate_drive_filter(
            state, BigBudgetPool(), self._ClampRM(),
            [_sig("ABC", 80), _sig("XYZ", 60)], 1.0)
        self.assertEqual([s["symbol"] for s in approved], ["ABC"])
        self.assertIn("XYZ", state["gate_watchlist"])


if __name__ == "__main__":
    unittest.main()
