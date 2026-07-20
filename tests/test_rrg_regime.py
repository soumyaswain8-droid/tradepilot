"""RRG rotation-count regime sensor — pure-function tests.

Mirrors tests/test_trend_mode.py's structure. Verifies prototype/v5/rrg_regime.py
encodes the Gate-1 WINNING config exactly (form=count, set=extended, N=1,
threshold=-0.2143 — docs/research/2026-07-20_gate1-rrg-sensor-backtest.md,
"Data-repair re-run" section, commit d23726e, PASS pc85/lc73), and that
fail-closed behavior matches scripts/backtest-rrg-sensor.py's
_day_signal_inputs() verbatim (source of truth).

Run: python3 -m pytest tests/test_rrg_regime.py -v
"""
import sys, unittest
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.v5.rrg_regime import (
    rotation_signal, rrg_score, THRESHOLD, N, BENCHMARK,
    DEFENSIVE, CYCLICAL_BASE, CYCLICAL_EXT_ADD, CYCLICAL_EXTENDED,
)


def _bench(prev, latest):
    return {BENCHMARK: [prev, latest]}


def _full_closes(def_pairs, cyc_pairs, bench_pair=(100.0, 101.0)):
    """def_pairs / cyc_pairs: dict of ticker -> (prev, latest). Only tickers
    present in the dict are "present" that day (mirrors backtest fail-closed
    exclusion of missing sectors)."""
    out = {BENCHMARK: list(bench_pair)}
    for t, (p, l) in def_pairs.items():
        out[t] = [p, l]
    for t, (p, l) in cyc_pairs.items():
        out[t] = [p, l]
    return out


class TestConfigEncodedExactly(unittest.TestCase):
    """Gate-1 winning config must match the backtest script verbatim."""

    def test_threshold(self):
        self.assertEqual(THRESHOLD, -0.2143)

    def test_lookback_is_1(self):
        self.assertEqual(N, 1)

    def test_benchmark(self):
        self.assertEqual(BENCHMARK, "^NSEI")

    def test_defensive_set_includes_dead_healthcare_ticker(self):
        # Kept in the list per house convention -- fail-closed skip, self-heals
        # if yfinance coverage returns (spec: do not substitute a different index).
        self.assertIn("NIFTY_HEALTHCARE.NS", DEFENSIVE)
        self.assertIn("^CNXPHARMA", DEFENSIVE)
        self.assertIn("^CNXFMCG", DEFENSIVE)
        self.assertEqual(len(DEFENSIVE), 3)

    def test_cyclical_base_set(self):
        self.assertEqual(CYCLICAL_BASE, ["^NSEBANK", "^CNXAUTO", "^CNXMETAL", "^CNXREALTY"])

    def test_cyclical_extended_adds_repaired_pvt_bank(self):
        # NIFTY_PVT_BANK.NS (repaired 2026-07-20), NOT the dead NIFTYPVTBANK.NS.
        self.assertIn("NIFTY_PVT_BANK.NS", CYCLICAL_EXT_ADD)
        self.assertNotIn("NIFTYPVTBANK.NS", CYCLICAL_EXT_ADD)
        self.assertEqual(CYCLICAL_EXTENDED, CYCLICAL_BASE + CYCLICAL_EXT_ADD)
        self.assertEqual(len(CYCLICAL_EXTENDED), 7)


class TestRotationSignalHandComputed(unittest.TestCase):
    """count form: frac(defensive rel>0) - frac(cyclical rel>0), set=extended, N=1."""

    def test_trend_side_defensive_lagging_cyclical_leading(self):
        # bench +1%. Defensive: PHARMA +5% (rel +4%>0), FMCG -5% (rel -6%<0) -> frac 1/2=0.5
        # Cyclical (all 7 present): every ticker +2% (rel +1%>0) -> frac 7/7=1.0
        # signal = 0.5 - 1.0 = -0.5, well below -0.2143 -> TREND
        def_pairs = {"^CNXPHARMA": (100.0, 105.0), "^CNXFMCG": (100.0, 95.0)}
        cyc_pairs = {t: (100.0, 102.0) for t in CYCLICAL_EXTENDED}
        closes = _full_closes(def_pairs, cyc_pairs, bench_pair=(100.0, 101.0))
        sig = rotation_signal(closes)
        self.assertAlmostEqual(sig, -0.5)
        self.assertLess(sig, THRESHOLD)
        self.assertEqual(rrg_score(sig), 100.0)

    def test_chop_side_both_sets_flat_negative(self):
        # bench +1%. Defensive both -2% (rel<0) -> frac 0/2=0.
        # Cyclical all -2% (rel<0) -> frac 0/7=0.
        # signal = 0 - 0 = 0.0 >= -0.2143 -> CHOP
        def_pairs = {"^CNXPHARMA": (100.0, 98.0), "^CNXFMCG": (100.0, 98.0)}
        cyc_pairs = {t: (100.0, 98.0) for t in CYCLICAL_EXTENDED}
        closes = _full_closes(def_pairs, cyc_pairs, bench_pair=(100.0, 101.0))
        sig = rotation_signal(closes)
        self.assertAlmostEqual(sig, 0.0)
        self.assertGreaterEqual(sig, THRESHOLD)
        self.assertEqual(rrg_score(sig), 0.0)

    def test_defensive_leadership_is_chop_classic_rotation(self):
        # Classic risk-off pattern: defensive rel>0 (leading), cyclical rel<0 (lagging).
        # frac_def=1.0, frac_cyc=0.0 -> signal=+1.0 >> -0.2143 -> CHOP
        def_pairs = {"^CNXPHARMA": (100.0, 103.0), "^CNXFMCG": (100.0, 103.0)}
        cyc_pairs = {t: (100.0, 97.0) for t in CYCLICAL_EXTENDED}
        closes = _full_closes(def_pairs, cyc_pairs, bench_pair=(100.0, 100.0))
        sig = rotation_signal(closes)
        self.assertAlmostEqual(sig, 1.0)
        self.assertEqual(rrg_score(sig), 0.0)

    def test_dead_healthcare_ticker_absent_still_scores(self):
        # NIFTY_HEALTHCARE.NS omitted entirely (simulates yfinance dead symbol) --
        # defensive set still has 2/3 present members, which clears the >=2 floor.
        def_pairs = {"^CNXPHARMA": (100.0, 105.0), "^CNXFMCG": (100.0, 105.0)}
        cyc_pairs = {t: (100.0, 99.0) for t in CYCLICAL_EXTENDED}
        closes = _full_closes(def_pairs, cyc_pairs)
        self.assertNotIn("NIFTY_HEALTHCARE.NS", closes)
        sig = rotation_signal(closes)
        self.assertIsNotNone(sig)


class TestFailClosed(unittest.TestCase):
    def test_missing_benchmark_is_no_data(self):
        closes = {"^CNXPHARMA": [100.0, 105.0], "^CNXFMCG": [100.0, 105.0]}
        for t in CYCLICAL_EXTENDED:
            closes[t] = [100.0, 99.0]
        self.assertIsNone(rotation_signal(closes))

    def test_benchmark_with_single_close_is_no_data(self):
        closes = _full_closes(
            {"^CNXPHARMA": (100.0, 105.0), "^CNXFMCG": (100.0, 105.0)},
            {t: (100.0, 99.0) for t in CYCLICAL_EXTENDED},
        )
        closes[BENCHMARK] = [101.0]  # only 1 point, N=1 needs 2
        self.assertIsNone(rotation_signal(closes))

    def test_defensive_set_below_2_members_is_no_data(self):
        # Only 1 defensive ticker present (healthcare AND fmcg both missing).
        closes = _full_closes(
            {"^CNXPHARMA": (100.0, 105.0)},
            {t: (100.0, 99.0) for t in CYCLICAL_EXTENDED},
        )
        self.assertIsNone(rotation_signal(closes))

    def test_cyclical_set_below_2_members_is_no_data(self):
        closes = _full_closes(
            {"^CNXPHARMA": (100.0, 105.0), "^CNXFMCG": (100.0, 105.0)},
            {"^NSEBANK": (100.0, 99.0)},
        )
        self.assertIsNone(rotation_signal(closes))

    def test_empty_input_is_no_data(self):
        self.assertIsNone(rotation_signal({}))
        self.assertIsNone(rotation_signal(None))

    def test_no_data_score_is_zero_fail_closed_to_chop(self):
        self.assertEqual(rrg_score(None), 0.0)


class TestBinaryScoreMapping(unittest.TestCase):
    def test_boundary_at_threshold_is_chop(self):
        # sig >= threshold -> CHOP (per backtest: `cls = "CHOP" if sig >= threshold else "TREND"`)
        self.assertEqual(rrg_score(THRESHOLD), 0.0)

    def test_just_below_threshold_is_trend(self):
        self.assertEqual(rrg_score(THRESHOLD - 0.0001), 100.0)

    def test_just_above_threshold_is_chop(self):
        self.assertEqual(rrg_score(THRESHOLD + 0.0001), 0.0)

    def test_score_is_always_binary(self):
        for sig in (-1.0, -0.5, -0.2143, 0.0, 0.5, 1.0, None):
            self.assertIn(rrg_score(sig), (0.0, 100.0))


if __name__ == "__main__":
    unittest.main()
