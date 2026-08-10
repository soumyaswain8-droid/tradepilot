"""Short-confirmation AND-gate (Variant C) -- unit tests.

Backtest: 1cr-roadmap/research/2026-07-24_short-confirm-backtest.md (base commit
4f129bd) recommends the red-day (existing Fix #1 change_pct leg) AND
below-VWAP AND-gate at prototype/v5/signal_engine.py's `actually_weak` gate
(~lines 196-199). VWAP-only (Variant B) backtested net-negative; the
AND-gate (Variant C) backtested net-positive (+Rs1,859/10d, catches
46/230 SHORTED_RISER).

Mocks v4.composite_scorer.score_all_stocks and v4.data_nse.get_nifty_index_level
so generate_signals() is exercised end-to-end with no network calls. Passes
regime= explicitly to bypass detect_regime().

Run: python3 -m pytest tests/test_short_vwap_gate.py -v
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.v5 import signal_engine


def _mkstock(symbol, score, change_pct, above_vwap=True, price=100.0, drop_vwap_key=False):
    """Minimal v4-scorer-shaped stock dict, sortable by score DESC."""
    d = {
        "symbol": symbol,
        "score": score,
        "change_pct": change_pct,
        "price": price,
        "high": price * 1.01,
        "low": price * 0.99,
        "orb_breakout": True,
        "composite_breakdown": {},
        "rs_today": 0.0,
        "stopLoss": 1.5,
        "target": 2.0,
        "riskReward": 1.5,
        "reasons": [],
    }
    if not drop_vwap_key:
        d["above_vwap"] = above_vwap
    return d


def _stocks_with_bottom_two(bottom_two):
    """8 filler stocks ranked above two bottom-rank SHORT candidates.

    n=10, regime=BEAR -> sell_count = max(1, int(10*0.10)) = 1... use n=10 with
    _SELL_BOT_PCT semantics from SIDEWAYS (0.10) is BEAR's buy pct, not sell.
    BEAR sell_count = max(1, int(n * _SELL_BOT_PCT)) with _SELL_BOT_PCT=0.20 -> 2.
    """
    fillers = [_mkstock(f"FILL{i}", score=90 - i * 5, change_pct=0.5) for i in range(8)]
    return fillers + bottom_two


class ShortVwapGateTests(unittest.TestCase):
    def setUp(self):
        self._nifty_patch = mock.patch.object(
            signal_engine, "get_nifty_index_level", return_value={"change_pct": 0.0})
        self._nifty_patch.start()
        self.addCleanup(self._nifty_patch.stop)

    def _run(self, stocks, regime="BEAR"):
        with mock.patch.object(signal_engine, "score_all_stocks", return_value=stocks):
            return signal_engine.generate_signals(regime=regime)

    def _by_symbol(self, signals):
        return {s["symbol"]: s for s in signals}

    # ---- gate ON (default) ----

    def test_red_and_below_vwap_passes(self):
        bottom = [
            _mkstock("WEAK1", score=25, change_pct=-1.0, above_vwap=True),   # rank 9, filtered by rank cut
            _mkstock("WEAK2", score=20, change_pct=-1.0, above_vwap=False),  # rank 10, red + below VWAP
        ]
        signals = self._run(_stocks_with_bottom_two(bottom))
        sig = self._by_symbol(signals)["WEAK2"]
        self.assertEqual(sig["direction"], "SELL")
        self.assertEqual(sig["position_type"], "SHORT")

    def test_red_but_above_vwap_blocked_even_though_weak_scored(self):
        bottom = [
            _mkstock("WEAK1", score=25, change_pct=-1.0, above_vwap=False),
            _mkstock("WEAK2", score=20, change_pct=-1.0, above_vwap=True),  # red + weak score, but above VWAP
        ]
        signals = self._run(_stocks_with_bottom_two(bottom))
        sig = self._by_symbol(signals)["WEAK2"]
        self.assertEqual(sig["direction"], "HOLD")
        self.assertEqual(sig["position_type"], "NONE")

    def test_vwap_unknown_blocked_fail_safe(self):
        bottom = [
            _mkstock("WEAK1", score=25, change_pct=-1.0, above_vwap=False),
            _mkstock("WEAK2", score=20, change_pct=-1.0, drop_vwap_key=True),  # above_vwap missing entirely
        ]
        signals = self._run(_stocks_with_bottom_two(bottom))
        sig = self._by_symbol(signals)["WEAK2"]
        self.assertEqual(sig["direction"], "HOLD")

    def test_gate_only_evaluated_once_fix1_already_passed(self):
        """Not-weak (Fix #1 fails) + below VWAP still stays HOLD -- gate never widens eligibility."""
        bottom = [
            _mkstock("WEAK1", score=25, change_pct=-1.0, above_vwap=False),
            _mkstock("NOTWEAK", score=50, change_pct=-1.0, above_vwap=False),  # score too high for Fix #1
        ]
        signals = self._run(_stocks_with_bottom_two(bottom))
        sig = self._by_symbol(signals)["NOTWEAK"]
        self.assertEqual(sig["direction"], "HOLD")

    # ---- kill switch OFF ----

    def test_kill_switch_off_restores_old_behavior(self):
        bottom = [
            _mkstock("WEAK1", score=25, change_pct=-1.0, above_vwap=False),
            _mkstock("WEAK2", score=20, change_pct=-1.0, above_vwap=True),  # would be blocked with gate ON
        ]
        with mock.patch.object(signal_engine, "SHORT_VWAP_GATE", False):
            signals = self._run(_stocks_with_bottom_two(bottom))
        sig = self._by_symbol(signals)["WEAK2"]
        self.assertEqual(sig["direction"], "SELL")
        self.assertEqual(sig["position_type"], "SHORT")

    def test_kill_switch_off_unknown_vwap_also_restores_old_behavior(self):
        bottom = [
            _mkstock("WEAK1", score=25, change_pct=-1.0, above_vwap=False),
            _mkstock("WEAK2", score=20, change_pct=-1.0, drop_vwap_key=True),
        ]
        with mock.patch.object(signal_engine, "SHORT_VWAP_GATE", False):
            signals = self._run(_stocks_with_bottom_two(bottom))
        sig = self._by_symbol(signals)["WEAK2"]
        self.assertEqual(sig["direction"], "SELL")

    # ---- LONG candidates never affected ----

    def test_long_candidates_never_affected_by_vwap_gate(self):
        bottom = [
            _mkstock("WEAK1", score=25, change_pct=-1.0, above_vwap=False),
            _mkstock("WEAK2", score=20, change_pct=-1.0, above_vwap=True),
        ]
        stocks = _stocks_with_bottom_two(bottom)
        signals_gate_on = self._run(stocks)
        with mock.patch.object(signal_engine, "SHORT_VWAP_GATE", False):
            signals_gate_off = self._run(stocks)

        buys_on = {s["symbol"]: s["direction"] for s in signals_gate_on if s["symbol"].startswith("FILL")}
        buys_off = {s["symbol"]: s["direction"] for s in signals_gate_off if s["symbol"].startswith("FILL")}
        self.assertEqual(buys_on, buys_off)
        # top-ranked filler must be BUY in both cases regardless of the short gate
        self.assertEqual(self._by_symbol(signals_gate_on)["FILL0"]["direction"], "BUY")
        self.assertEqual(self._by_symbol(signals_gate_off)["FILL0"]["direction"], "BUY")


if __name__ == "__main__":
    unittest.main()
