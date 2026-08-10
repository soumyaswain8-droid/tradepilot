"""RISK_GATE_LOG wiring in scripts/v5-paper-trade.py -- integration tests
(Phase 0, spec 1cr-roadmap/research/2026-07-20_risk_gate_three_state_verdict.md S5).

Uses the importlib pattern from tests/test_chop_ladder.py / test_data_guard.py
(the engine script has a hyphen in its filename). Network-touching helpers are
never invoked here (DATA_GUARD=0, no yfinance calls in this path once tape
freshness is bypassed). All file writes are redirected to a temp dir by
monkeypatching v5.TRADE_DIR -- never touches the real docs/paper-trades tree.

Proves the three HARD requirements from the task:
  (a) deployments are byte-identical with RISK_GATE_LOG on vs off
  (b) a gate that raises does not affect deployments (fail-open)
  (c) the verdicts file is written with plan + verdict + inline_outcome rows

Run: python3 -m pytest tests/test_risk_gate_wiring.py -v
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
    "v5_paper_trade", str(PROJECT_ROOT / "scripts" / "v5-paper-trade.py"))
v5 = importlib.util.module_from_spec(_spec)
sys.modules["v5_paper_trade"] = v5
try:
    _spec.loader.exec_module(v5)
except Exception as e:
    print(f"[warn] partial module load: {e}")


class StubPool:
    """Doubles as both the PoolManager AND the single pool it exposes,
    mirroring tests/test_chop_ladder.py's StubPool."""
    def __init__(self):
        self.deployed = []

    def deploy(self, pool, sym, qty, price, sl, tgt):
        self.deployed.append((sym, qty))
        return True

    def get_pool_budget(self, pool):
        return 100_000

    @property
    def pools(self):
        return {"INTRADAY": self}


class FakeRM:
    """Minimal RiskManager double: clean pass on every check RiskGate reads,
    and the surface deploy_signals itself calls (check_can_trade,
    get_position_size)."""
    def __init__(self):
        self.kill_switch_tripped = False
        self.session_pnl_rs = 0.0
        self.pm = None  # set to the StubPool instance by tests that need it

    def check_can_trade(self, pool_name, symbol, position_type=None):
        return True, "OK"

    def get_position_size(self, pool_name, base):
        return base

    def check_position_size(self, cost_or_margin, pool_name):
        return True, "OK"

    def get_risk_dashboard(self):
        return {"vix_multiplier": 1.0}


def _state():
    return {"pools": {"INTRADAY": {"positions": []}}, "trend_mode": "CHOP",
            "trend_pending": None, "premarket": {}, "regime": "SIDEWAYS",
            "summary": {"rescore_count": 0}}


def _signals(n):
    return [{"symbol": f"S{i}", "direction": "BUY", "score": 50.0 + i, "pool": "INTRADAY",
             "entry_price": 100.0, "sl_price": 98.5, "target_price": 102.0,
             "position_type": "LONG", "rank": i, "change_pct": 0.5,
             "reasons": ["momentum"]} for i in range(1, n + 1)]


class _TmpTradeDir(unittest.TestCase):
    """Base: redirect v5.TRADE_DIR to a scratch dir for the duration of the test."""
    def setUp(self):
        os.environ["DATA_GUARD"] = "0"
        os.environ["CHOP_FILTER"] = "0"
        self.addCleanup(os.environ.pop, "DATA_GUARD", None)
        self.addCleanup(os.environ.pop, "CHOP_FILTER", None)
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self._patch_dir = mock.patch.object(v5, "TRADE_DIR", Path(self._tmpdir.name))
        self._patch_dir.start()
        self.addCleanup(self._patch_dir.stop)


class TestByteIdenticalDeployments(_TmpTradeDir):
    """(a) HARD REQUIREMENT: deployments are byte-identical with
    RISK_GATE_LOG on vs off."""

    def test_deployments_identical_gate_on_vs_off(self):
        rm_on, rm_off = FakeRM(), FakeRM()
        pm_on, pm_off = StubPool(), StubPool()
        rm_on.pm, rm_off.pm = pm_on, pm_off
        sigs_on, sigs_off = _signals(8), _signals(8)

        os.environ["RISK_GATE_LOG"] = "1"
        count_on = v5.deploy_signals(_state(), pm_on, rm_on, sigs_on)

        os.environ["RISK_GATE_LOG"] = "0"
        count_off = v5.deploy_signals(_state(), pm_off, rm_off, sigs_off)
        os.environ.pop("RISK_GATE_LOG", None)

        self.assertEqual(count_on, count_off)
        self.assertEqual(pm_on.deployed, pm_off.deployed)

    def test_default_is_gate_on(self):
        # RISK_GATE_LOG unset -> defaults ON, but must still match the
        # explicit-off run byte-for-byte.
        os.environ.pop("RISK_GATE_LOG", None)
        rm_default, rm_off = FakeRM(), FakeRM()
        pm_default, pm_off = StubPool(), StubPool()
        rm_default.pm, rm_off.pm = pm_default, pm_off
        sigs_default, sigs_off = _signals(5), _signals(5)

        count_default = v5.deploy_signals(_state(), pm_default, rm_default, sigs_default)
        os.environ["RISK_GATE_LOG"] = "0"
        count_off = v5.deploy_signals(_state(), pm_off, rm_off, sigs_off)
        os.environ.pop("RISK_GATE_LOG", None)

        self.assertEqual(count_default, count_off)
        self.assertEqual(pm_default.deployed, pm_off.deployed)


class TestFailOpen(_TmpTradeDir):
    """(b) HARD REQUIREMENT: a gate that raises does not affect deployments."""

    def test_raising_gate_logger_does_not_affect_deployments(self):
        pm_raising, pm_clean = StubPool(), StubPool()
        rm_raising, rm_clean = FakeRM(), FakeRM()
        rm_raising.pm, rm_clean.pm = pm_raising, pm_clean
        sigs_raising, sigs_clean = _signals(6), _signals(6)

        os.environ["RISK_GATE_LOG"] = "1"
        with mock.patch.object(v5, "_log_risk_gate_verdicts",
                                side_effect=RuntimeError("boom")):
            count_raising = v5.deploy_signals(_state(), pm_raising, rm_raising, sigs_raising)

        count_clean = v5.deploy_signals(_state(), pm_clean, rm_clean, sigs_clean)
        os.environ.pop("RISK_GATE_LOG", None)

        self.assertEqual(count_raising, count_clean)
        self.assertEqual(pm_raising.deployed, pm_clean.deployed)

    def test_raising_gate_logger_does_not_propagate(self):
        pm = StubPool()
        rm = FakeRM()
        rm.pm = pm
        os.environ["RISK_GATE_LOG"] = "1"
        with mock.patch.object(v5, "_log_risk_gate_verdicts",
                                side_effect=RuntimeError("boom")):
            try:
                v5.deploy_signals(_state(), pm, rm, _signals(3))
            except Exception as e:
                self.fail(f"deploy_signals raised despite fail-open wrapping: {e}")
        os.environ.pop("RISK_GATE_LOG", None)

    def test_none_risk_manager_is_safely_skipped(self):
        # rm=None is a real code path (RiskManager import failed / unavailable).
        pm = StubPool()
        os.environ["RISK_GATE_LOG"] = "1"
        try:
            count = v5.deploy_signals(_state(), pm, None, _signals(4))
        except Exception as e:
            self.fail(f"deploy_signals raised with rm=None: {e}")
        os.environ.pop("RISK_GATE_LOG", None)
        self.assertEqual(count, 4)
        self.assertFalse(v5._verdicts_file().exists())  # nothing to log without an rm


class TestVerdictsArtifact(_TmpTradeDir):
    """(c) verdicts file is written with plan + verdict + inline_outcome rows."""

    def test_verdicts_file_written_with_expected_rows(self):
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        os.environ["RISK_GATE_LOG"] = "1"
        v5.deploy_signals(_state(), pm, rm, _signals(3))
        os.environ.pop("RISK_GATE_LOG", None)

        path = v5._verdicts_file()
        self.assertTrue(path.exists())
        data = json.loads(path.read_text())
        self.assertEqual(data["engine"], v5.ENGINE)
        self.assertEqual(len(data["verdicts"]), 3)
        for row in data["verdicts"]:
            self.assertIn("symbol", row)
            self.assertIn("plan", row)
            for f in ("symbol", "side", "entry", "target", "stop", "invalidation",
                      "size_rs", "pool", "score", "rationale"):
                self.assertIn(f, row["plan"])
            self.assertIn(row["verdict"], ("approved", "watchlist", "rejected"))
            self.assertIn("reasons", row)
            self.assertIn("checked_at", row)
            self.assertIn(row["inline_outcome"], ("deployed", "filtered"))

    def test_verdicts_append_across_multiple_scans(self):
        pm1, rm1 = StubPool(), FakeRM(); rm1.pm = pm1
        pm2, rm2 = StubPool(), FakeRM(); rm2.pm = pm2
        os.environ["RISK_GATE_LOG"] = "1"
        v5.deploy_signals(_state(), pm1, rm1, _signals(2))
        v5.deploy_signals(_state(), pm2, rm2, _signals(2))
        os.environ.pop("RISK_GATE_LOG", None)

        data = json.loads(v5._verdicts_file().read_text())
        self.assertEqual(len(data["verdicts"]), 4)  # 2 scans x 2 candidates, appended not overwritten

    def test_deployed_candidate_marked_inline_outcome_deployed(self):
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        os.environ["RISK_GATE_LOG"] = "1"
        v5.deploy_signals(_state(), pm, rm, _signals(2))
        os.environ.pop("RISK_GATE_LOG", None)

        data = json.loads(v5._verdicts_file().read_text())
        outcomes = {row["symbol"]: row["inline_outcome"] for row in data["verdicts"]}
        deployed_syms = {sym for sym, _ in pm.deployed}
        for sym, outcome in outcomes.items():
            expected = "deployed" if sym in deployed_syms else "filtered"
            self.assertEqual(outcome, expected)

    def test_disabled_by_kill_switch(self):
        pm, rm = StubPool(), FakeRM()
        rm.pm = pm
        os.environ["RISK_GATE_LOG"] = "0"
        v5.deploy_signals(_state(), pm, rm, _signals(2))
        os.environ.pop("RISK_GATE_LOG", None)
        self.assertFalse(v5._verdicts_file().exists())


if __name__ == "__main__":
    unittest.main()
