"""CHOP_FILTER integration: deploy_signals honors ladder + budget throttle.
Uses the importlib pattern from tests/test_track_a.py. Network-touching
helpers are monkeypatched; deploy_signals is exercised with a stub pool
manager to observe filtering and sizing.
Run: python3 -m pytest tests/test_chop_ladder.py -v
"""
import os, sys, unittest
from unittest import mock
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT)); sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

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
    def __init__(self): self.deployed = []
    def deploy(self, pool, sym, qty, price, sl, tgt):
        self.deployed.append((sym, qty)); return True
    def get_pool_budget(self, pool): return 100_000
    @property
    def pools(self): return {"INTRADAY": self}


def _state():
    return {"pools": {"INTRADAY": {"positions": []}}, "trend_mode": "CHOP",
            "trend_pending": None, "premarket": {}, "regime": "SIDEWAYS",
            "summary": {"rescore_count": 0}}


def _signals(n):
    return [{"symbol": f"S{i}", "direction": "BUY", "score": i, "pool": "INTRADAY",
             "entry_price": 100.0, "position_type": "LONG"} for i in range(1, n + 1)]


class TestChopFilter(unittest.TestCase):
    def setUp(self):
        os.environ["CHOP_FILTER"] = "1"
        os.environ["DATA_GUARD"] = "0"          # isolate: not testing the tape guard here
        self.addCleanup(os.environ.pop, "CHOP_FILTER", None)
        self.addCleanup(os.environ.pop, "DATA_GUARD", None)

    def test_chop_mode_caps_entries_at_3(self):
        pm = StubPool()
        with mock.patch.object(v5, "_update_trend_mode", lambda state: None):  # keep CHOP
            n = v5.deploy_signals(_state(), pm, None, _signals(12))
        self.assertLessEqual(len(pm.deployed), 3)

    def test_flag_off_is_vanilla(self):
        os.environ["CHOP_FILTER"] = "0"
        pm = StubPool()
        n = v5.deploy_signals(_state(), pm, None, _signals(12))
        self.assertGreater(len(pm.deployed), 3)   # no ladder cap applied

    def test_chop_reduces_qty(self):
        pm_chop, pm_off = StubPool(), StubPool()
        sigs = _signals(3)
        with mock.patch.object(v5, "_update_trend_mode", lambda state: None):
            v5.deploy_signals(_state(), pm_chop, None, [dict(s) for s in sigs])
        os.environ["CHOP_FILTER"] = "0"
        v5.deploy_signals(_state(), pm_off, None, [dict(s) for s in sigs])
        got = dict(pm_chop.deployed); base = dict(pm_off.deployed)
        for sym in got:
            self.assertLess(got[sym], base[sym])  # 0.4 size × 0.5 alloc < 1.0


class TestRegimeSensorSwap(unittest.TestCase):
    """REGIME_SENSOR (2026-07-20, design doc §5 'swap the score producer, not
    the consumer'): default stays trendscore; REGIME_SENSOR=rrg routes
    through _rrg_score_for_session instead. No network in tests -- fetches
    mocked."""

    def setUp(self):
        os.environ["CHOP_FILTER"] = "1"
        self.addCleanup(os.environ.pop, "CHOP_FILTER", None)
        self.addCleanup(os.environ.pop, "REGIME_SENSOR", None)

    def test_default_is_trendscore(self):
        os.environ.pop("REGIME_SENSOR", None)
        state = _state()
        with mock.patch.object(v5, "_rrg_score_for_session") as rrg_mock, \
             mock.patch("yfinance.download", side_effect=Exception("no network in tests")):
            v5._update_trend_mode(state)
        rrg_mock.assert_not_called()
        self.assertIn("trend_components", state)  # trendscore path persists this key

    def test_regime_sensor_rrg_routes_to_rrg_producer(self):
        os.environ["REGIME_SENSOR"] = "rrg"
        state = _state()
        with mock.patch.object(v5, "_rrg_score_for_session", return_value=100.0) as rrg_mock:
            v5._update_trend_mode(state)
        rrg_mock.assert_called_once_with(state)
        self.assertEqual(state["trend_mode"], "CHOP")   # 1st scan: hysteresis holds, TREND pending
        self.assertEqual(state["trend_pending"], "TREND")
        self.assertEqual(state["trend_score_last"], 100.0)

    def test_regime_sensor_rrg_chop_score_flows_through_hysteresis(self):
        os.environ["REGIME_SENSOR"] = "rrg"
        state = _state()
        with mock.patch.object(v5, "_rrg_score_for_session", return_value=0.0):
            v5._update_trend_mode(state)
        self.assertEqual(state["trend_mode"], "CHOP")
        self.assertIsNone(state["trend_pending"])

    def test_rrg_score_producer_fail_closed_on_fetch_error(self):
        # _rrg_score_for_session itself: yfinance import/download blows up ->
        # rotation_signal never gets real data -> None -> rrg_score -> 0.0.
        state = _state()
        with mock.patch("yfinance.download", side_effect=Exception("network down")):
            score = v5._rrg_score_for_session(state)
        self.assertEqual(score, 0.0)
        self.assertIsNone(state["rrg_signal"]["signal"])

    def test_rrg_score_cached_per_session_date(self):
        from datetime import datetime
        state = _state()
        state["_rrg_score_cache"] = {"date": datetime.now().strftime("%Y-%m-%d"), "score": 100.0}
        with mock.patch("yfinance.download") as dl:
            score = v5._rrg_score_for_session(state)
        self.assertEqual(score, 100.0)
        dl.assert_not_called()  # cache hit for today's date, no re-fetch


if __name__ == "__main__":
    unittest.main()
