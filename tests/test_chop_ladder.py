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


if __name__ == "__main__":
    unittest.main()
