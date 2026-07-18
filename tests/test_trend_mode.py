"""TrendScore sensor — pure-function tests (spec §1).
Run: python3 -m pytest tests/test_trend_mode.py -v
"""
import sys, unittest
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.v5.trend_mode import tape_efficiency, breadth_strength, trend_score, mode_for


class TestTapeEfficiency(unittest.TestCase):
    def test_pure_trend_is_100(self):
        self.assertAlmostEqual(tape_efficiency([100, 101, 102, 103, 104]), 100.0)

    def test_pure_whipsaw_near_zero(self):
        closes = [100, 101, 100, 101, 100]  # net 0, path 4
        self.assertAlmostEqual(tape_efficiency(closes), 0.0)

    def test_half_efficient(self):
        closes = [100, 102, 101, 103]  # net 3, path 2+1+2=5
        self.assertAlmostEqual(tape_efficiency(closes), 60.0)

    def test_too_few_bars_is_zero(self):
        self.assertEqual(tape_efficiency([100]), 0.0)
        self.assertEqual(tape_efficiency([]), 0.0)

    def test_flat_tape_is_zero(self):
        self.assertEqual(tape_efficiency([100, 100, 100]), 0.0)


class TestBreadthStrength(unittest.TestCase):
    def test_neutral_breadth_is_zero(self):
        self.assertEqual(breadth_strength(50.0, 50.0), 0.0)

    def test_strong_breadth_level(self):
        # 80% above 20-SMA, unchanged: |80-50|*2 = 60
        self.assertAlmostEqual(breadth_strength(80.0, 80.0), 60.0)

    def test_breadth_delta_contributes(self):
        # 55 today from 45 yesterday: |55-50|*2 + |10|*5 = 60
        self.assertAlmostEqual(breadth_strength(55.0, 45.0), 60.0)

    def test_caps_at_100(self):
        self.assertEqual(breadth_strength(100.0, 0.0), 100.0)

    def test_none_inputs_fail_closed(self):
        self.assertEqual(breadth_strength(None, 50.0), 0.0)
        self.assertEqual(breadth_strength(50.0, None), 0.0)


class TestTrendScore(unittest.TestCase):
    def test_weights(self):
        # 0.4*50 + 0.4*50 + 0.2*(3/6*100) = 20+20+10 = 50
        self.assertAlmostEqual(trend_score(50.0, 50.0, 3), 50.0)

    def test_regime_sign_ignored(self):
        self.assertEqual(trend_score(0, 0, -6), trend_score(0, 0, 6))

    def test_clamped(self):
        self.assertLessEqual(trend_score(100, 100, 6), 100.0)
        self.assertGreaterEqual(trend_score(0, 0, 0), 0.0)


class TestModeHysteresis(unittest.TestCase):
    def test_no_flip_on_single_scan(self):
        mode, pending = mode_for(80.0, None, "CHOP")
        self.assertEqual(mode, "CHOP")       # not yet
        self.assertEqual(pending, "TREND")

    def test_flip_on_second_consecutive_scan(self):
        mode, pending = mode_for(80.0, "TREND", "CHOP")
        self.assertEqual(mode, "TREND")
        self.assertIsNone(pending)

    def test_pending_resets_on_disagreement(self):
        mode, pending = mode_for(20.0, "TREND", "CHOP")  # pending TREND, raw now CHOP
        self.assertEqual(mode, "CHOP")
        self.assertIsNone(pending)

    def test_stable_mode_keeps_no_pending(self):
        mode, pending = mode_for(20.0, None, "CHOP")
        self.assertEqual(mode, "CHOP")
        self.assertIsNone(pending)

    def test_thresholds(self):
        self.assertEqual(mode_for(34.9, None, "NEUTRAL")[1], "CHOP")
        self.assertEqual(mode_for(35.0, "X", "NEUTRAL")[0], "NEUTRAL")
        self.assertEqual(mode_for(65.0, None, "NEUTRAL")[1], "TREND")


if __name__ == "__main__":
    unittest.main()
