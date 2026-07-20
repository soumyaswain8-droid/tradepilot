"""TrendScore sensor — pure-function tests (spec §1).
Run: python3 -m pytest tests/test_trend_mode.py -v
"""
import sys, unittest
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.v5.trend_mode import tape_efficiency, breadth_strength, trend_score, mode_for, apply_ladder


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
        # Gate-1 sweep's best CHOP-separating combo (td=1.0, bm=1.0, rd=6):
        # 0.4*min(100,50/1.0) + 0.4*min(100,50*1.0) + 0.2*min(100,3/6*100)
        #           = 0.4*50 + 0.4*50 + 0.2*50 = 20+20+10 = 50
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
        # CHOP_TH=45, TREND_TH=55 (Gate-1 joint sweep, 2026-07-20 calibration).
        self.assertEqual(mode_for(44.9, None, "NEUTRAL")[1], "CHOP")
        self.assertEqual(mode_for(45.0, "X", "NEUTRAL")[0], "NEUTRAL")
        self.assertEqual(mode_for(55.0, None, "NEUTRAL")[1], "TREND")


def _sigs(scores):
    return [{"symbol": f"S{i}", "score": s} for i, s in enumerate(scores)]


class TestApplyLadder(unittest.TestCase):
    def test_trend_passes_through(self):
        sigs = _sigs([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        allowed, size_m, alloc_m = apply_ladder(sigs, "TREND")
        self.assertEqual(len(allowed), 10)
        self.assertEqual((size_m, alloc_m), (1.0, 1.0))

    def test_chop_top_quartile_max3(self):
        sigs = _sigs(list(range(1, 13)))  # scores 1..12, quartile floor = 9.25
        allowed, size_m, alloc_m = apply_ladder(sigs, "CHOP")
        self.assertLessEqual(len(allowed), 3)
        self.assertTrue(all(float(s["score"]) >= 9.25 for s in allowed))
        self.assertEqual((size_m, alloc_m), (0.40, 0.5))
        self.assertEqual([s["score"] for s in allowed], sorted([s["score"] for s in allowed], reverse=True))

    def test_neutral_passes_through(self):
        # 2-tier design (approved 2026-07-20): Gate-1 killed the TREND leg,
        # so only CHOP throttles — NEUTRAL is vanilla v5, same as TREND.
        sigs = _sigs(list(range(1, 21)))  # 1..20
        allowed, size_m, alloc_m = apply_ladder(sigs, "NEUTRAL")
        self.assertEqual(len(allowed), 20)
        self.assertEqual((size_m, alloc_m), (1.0, 1.0))

    def test_unknown_mode_fails_closed_as_chop(self):
        sigs = _sigs([5, 6, 7, 8])
        allowed, size_m, alloc_m = apply_ladder(sigs, "???")
        self.assertEqual((size_m, alloc_m), (0.40, 0.5))

    def test_empty_signals_ok(self):
        allowed, _, _ = apply_ladder([], "CHOP")
        self.assertEqual(allowed, [])


if __name__ == "__main__":
    unittest.main()
