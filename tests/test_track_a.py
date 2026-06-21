"""Track A — unit tests for Phase 1 tactical fixes (per IMPLEMENTATION_BRIEF_2026-04-27.md §6).

Run with: python3 -m pytest tests/test_track_a.py -v
or:        python3 tests/test_track_a.py  (uses unittest)
"""
import os
import sys
import unittest
from datetime import datetime
from unittest import mock
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Import the module under test. The script is named with hyphens so we use importlib.
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "v5_paper_trade", str(PROJECT_ROOT / "scripts" / "v5-paper-trade.py")
)
v5 = importlib.util.module_from_spec(_spec)
# Suppress side-effect imports we don't need for unit tests
sys.modules["v5_paper_trade"] = v5
try:
    _spec.loader.exec_module(v5)
except Exception as e:
    # Some imports (Yahoo, Rust bridge) may fail in a unit-test env. Continue with
    # the symbols that did load.
    print(f"[warn] partial module load: {e}")


# ───────────────────────── Task 1.1 — SHORT_BLOCK ─────────────────────────

class TestShortBlock(unittest.TestCase):
    def _state(self, bias="BULLISH", direction="UP", magnitude=0.75):
        return {
            "premarket": {
                "overall": {"bias": bias},
                "gap_prediction": {"direction": direction, "magnitude_pct": magnitude},
            }
        }

    def test_active_when_bullish_gap_up_in_window(self):
        """Within first 60 min after 09:15, bullish + gap-up > 0.5% → block active."""
        with mock.patch("v5_paper_trade.datetime") as mdt:
            mdt.now.return_value = datetime(2026, 4, 28, 9, 45)  # 30 min after open
            mdt.strptime = datetime.strptime  # preserve other usages
            self.assertTrue(v5._short_block_active(self._state()))

    def test_inactive_after_window_expires(self):
        """At 70 min after open, block expires even if bullish + gap-up."""
        with mock.patch("v5_paper_trade.datetime") as mdt:
            mdt.now.return_value = datetime(2026, 4, 28, 10, 25)  # 70 min after open
            mdt.strptime = datetime.strptime
            self.assertFalse(v5._short_block_active(self._state()))

    def test_inactive_when_gap_too_small(self):
        """Bullish but gap only +0.3% → below threshold → no block."""
        with mock.patch("v5_paper_trade.datetime") as mdt:
            mdt.now.return_value = datetime(2026, 4, 28, 9, 30)
            mdt.strptime = datetime.strptime
            self.assertFalse(v5._short_block_active(self._state(magnitude=0.3)))

    def test_inactive_when_bias_neutral(self):
        """Gap up but bias=NEUTRAL → no block."""
        with mock.patch("v5_paper_trade.datetime") as mdt:
            mdt.now.return_value = datetime(2026, 4, 28, 9, 30)
            mdt.strptime = datetime.strptime
            self.assertFalse(v5._short_block_active(self._state(bias="NEUTRAL")))

    def test_inactive_when_gap_direction_down(self):
        """Bullish bias but gap DOWN → no block."""
        with mock.patch("v5_paper_trade.datetime") as mdt:
            mdt.now.return_value = datetime(2026, 4, 28, 9, 30)
            mdt.strptime = datetime.strptime
            self.assertFalse(v5._short_block_active(self._state(direction="DOWN")))


# ───────────────────────── Task 1.2 — WINNER_RE_ARM ─────────────────────────

class TestRearm(unittest.TestCase):
    def test_consumes_slot_only_after_mark(self):
        state = {}
        # Without a prior mark_rearmable, consume returns False
        self.assertFalse(v5.consume_rearm(state, "SUZLON", "BUY"))

    def test_three_slots_then_block(self):
        state = {}
        v5.mark_rearmable(state, "SUZLON", "BUY", max_rearms=3)
        self.assertTrue(v5.consume_rearm(state, "SUZLON", "BUY"))
        self.assertTrue(v5.consume_rearm(state, "SUZLON", "BUY"))
        self.assertTrue(v5.consume_rearm(state, "SUZLON", "BUY"))
        self.assertFalse(v5.consume_rearm(state, "SUZLON", "BUY"))  # 4th attempt blocked

    def test_direction_mismatch_blocks(self):
        state = {}
        v5.mark_rearmable(state, "SUZLON", "BUY")
        self.assertFalse(v5.consume_rearm(state, "SUZLON", "SELL"))

    def test_mark_is_idempotent(self):
        state = {}
        v5.mark_rearmable(state, "SUZLON", "BUY", max_rearms=3)
        v5.mark_rearmable(state, "SUZLON", "BUY", max_rearms=99)  # second mark ignored
        # Still only 3 slots
        for _ in range(3):
            self.assertTrue(v5.consume_rearm(state, "SUZLON", "BUY"))
        self.assertFalse(v5.consume_rearm(state, "SUZLON", "BUY"))


# ───────────────────────── Task 1.3 — TIME_EXIT_TIGHTENING ─────────────────────────

class TestFlatExitWindow(unittest.TestCase):
    def test_in_window_at_1330(self):
        self.assertTrue(v5._in_flat_exit_window(datetime(2026, 4, 28, 13, 30)))

    def test_in_window_at_1359(self):
        self.assertTrue(v5._in_flat_exit_window(datetime(2026, 4, 28, 13, 59)))

    def test_out_of_window_at_1329(self):
        self.assertFalse(v5._in_flat_exit_window(datetime(2026, 4, 28, 13, 29)))

    def test_out_of_window_at_1400(self):
        self.assertFalse(v5._in_flat_exit_window(datetime(2026, 4, 28, 14, 0)))


# ───────────────────────── Task 1.4 — Cost modeling ─────────────────────────

class TestCostForTrade(unittest.TestCase):
    def test_typical_intraday_round_trip(self):
        """50 qty, entry ₹100, exit ₹100 at default 12 bps → notional 5000 × 12bps = ₹6."""
        cost = v5.cost_for_trade(qty=50, entry_price=100.0, exit_price=100.0)
        self.assertAlmostEqual(cost, 6.0, places=2)

    def test_uses_average_notional(self):
        """qty=10, entry=200, exit=220 → avg notional = 10 * 210 = 2100; 12bps → ₹2.52."""
        cost = v5.cost_for_trade(qty=10, entry_price=200.0, exit_price=220.0)
        self.assertAlmostEqual(cost, 2.52, places=2)

    def test_zero_qty_zero_cost(self):
        self.assertEqual(v5.cost_for_trade(qty=0, entry_price=100, exit_price=100), 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
