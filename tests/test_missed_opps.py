"""Regression tests for scripts/missed-opportunities-watchdog.py (TP-BUG 2026-07-24).

Root cause being guarded: prototype/data/missed-opportunities.json showed an
all-zero summary at 12:45 on 2026-07-23 (a strong rally day where zeros were
implausible). Two independent bugs were found:

1. fetch_movers() ran a threads=True 200-symbol yfinance batch on top of ~10
   other concurrently-running paper-trade engines also hitting yfinance. This
   self-inflicted DNS/thread contention (curl "getaddrinfo() thread failed to
   start") routinely collapsed the batch to 1-5 successful symbols out of 201,
   and the watchdog published that near-empty result as if it were a real
   snapshot. Fix: bounded thread count + retry-with-backoff, and snapshot()
   now skips writing (keeps the last good file) when post-retry coverage of
   the configured universe is still below MIN_COVERAGE_RATIO.

2. load_our_positions() read a hardcoded engine list
   ["v5", "v5_classic", "v5_6", "v5_7", "v5_8", "v6"] that went stale as new
   engines (v5_cut, v5_flip, v5_gate, v5_long, v5_chop, v5_rrg, v7_regime, v8)
   were added under docs/paper-trades/. Their held positions were silently
   dropped and mis-classified as "on the table" opportunities. Fix: discover
   any docs/paper-trades/<engine>/positions_active.json instead of a fixed list.

Run with: python3 -m pytest tests/test_missed_opps.py -v
"""
import json
import sys
import types
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "missed_opps_watchdog", str(PROJECT_ROOT / "scripts" / "missed-opportunities-watchdog.py")
)
watchdog = importlib.util.module_from_spec(_spec)
sys.modules["missed_opps_watchdog"] = watchdog
_spec.loader.exec_module(watchdog)


class TestCategorize(unittest.TestCase):
    """Pure aggregation logic — was never actually broken, but pin it down."""

    def test_long_position_moving_up_is_a_winner(self):
        movers = [("TCS", 100.0, 95.0, 5.26)]
        positions = {"TCS": [{"engine": "v5", "direction": "LONG"}]}
        cats = watchdog.categorize(movers, positions)
        self.assertEqual(len(cats["winners_held"]), 1)
        self.assertEqual(cats["winners_held"][0]["engine"], "v5")
        self.assertEqual(len(cats["losers_held"]), 0)

    def test_short_position_moving_up_is_a_loser(self):
        movers = [("TCS", 100.0, 95.0, 5.26)]
        positions = {"TCS": [{"engine": "v5", "direction": "SHORT"}]}
        cats = watchdog.categorize(movers, positions)
        self.assertEqual(len(cats["losers_held"]), 1)

    def test_unheld_big_mover_is_missed_and_on_table(self):
        movers = [("SWIGGY", 240.0, 260.0, -7.7)]
        cats = watchdog.categorize(movers, {})
        self.assertEqual(len(cats["on_table"]), 1)
        self.assertEqual(len(cats["winners_missed"]), 1)
        self.assertEqual(cats["on_table"][0]["suggested"], "SHORT")

    def test_unheld_small_mover_is_ignored(self):
        movers = [("ITC", 100.5, 100.0, 0.5)]
        cats = watchdog.categorize(movers, {})
        self.assertEqual(len(cats["on_table"]), 0)
        self.assertEqual(len(cats["winners_missed"]), 0)


class TestLoadOurPositionsAutoDiscovery(unittest.TestCase):
    """Guards bug #2: engine list must not be hardcoded/stale."""

    def _write_positions(self, base, engine, symbol, direction="LONG"):
        d = base / "docs" / "paper-trades" / engine
        d.mkdir(parents=True, exist_ok=True)
        (d / "positions_active.json").write_text(json.dumps({
            "positions": {"pool_a": [{"symbol": symbol, "direction": direction}]}
        }))

    def test_discovers_engine_absent_from_old_hardcoded_list(self, tmp_root=None):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            # "v5_cut" was NOT in the old hardcoded list — this is exactly what broke.
            self._write_positions(base, "v5_cut", "RELIANCE", "SHORT")
            self._write_positions(base, "v5", "TCS", "LONG")

            orig_root = watchdog.ROOT
            watchdog.ROOT = base
            try:
                positions = watchdog.load_our_positions()
            finally:
                watchdog.ROOT = orig_root

            self.assertIn("RELIANCE", positions)
            engines_holding_reliance = {p["engine"] for p in positions["RELIANCE"]}
            self.assertIn("v5_cut", engines_holding_reliance)
            self.assertIn("TCS", positions)

    def test_v4_directory_not_double_counted_via_glob(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            self._write_positions(base, "v5", "TCS", "LONG")
            # v4 uses a different (date-stamped) schema; make sure a stray
            # positions_active.json under v4/ (shouldn't exist) wouldn't be
            # double-read by both code paths.
            (base / "docs" / "paper-trades" / "v4").mkdir(parents=True, exist_ok=True)

            orig_root = watchdog.ROOT
            watchdog.ROOT = base
            try:
                positions = watchdog.load_our_positions()
            finally:
                watchdog.ROOT = orig_root

            self.assertIn("TCS", positions)


class TestFetchMoversCoverageRetry(unittest.TestCase):
    """Guards bug #1: transient partial-batch failures must retry, not silently
    publish a near-empty snapshot."""

    def setUp(self):
        self._orig_sleep = watchdog.time.sleep
        watchdog.time.sleep = lambda *_a, **_k: None  # don't actually wait in tests

    def tearDown(self):
        watchdog.time.sleep = self._orig_sleep
        sys.modules.pop("yfinance", None)
        sys.modules.pop("config", None)

    def _install_fake_yfinance(self, coverage_by_call):
        """coverage_by_call: list of ints — successful symbol count to return per call."""
        calls = {"n": 0}

        class _FakeDF:
            def __init__(self, symbols):
                import pandas as pd
                self.columns = pd.MultiIndex.from_product([symbols, ["Close"]])
                self._symbols = symbols

            def __getitem__(self, sym):
                import pandas as pd
                return pd.DataFrame({"Close": [100.0, 101.0]})

        fake_yf = types.ModuleType("yfinance")

        def _download(*_a, **kw):
            idx = min(calls["n"], len(coverage_by_call) - 1)
            n_ok = coverage_by_call[idx]
            calls["n"] += 1
            return _FakeDF([f"SYM{i}.NS" for i in range(n_ok)])

        fake_yf.download = _download
        fake_yf.set_tz_cache_location = lambda *_a, **_k: None
        sys.modules["yfinance"] = fake_yf

        fake_cfg = types.ModuleType("config")
        fake_cfg.ACTIVE_SYMBOLS_YF = [f"SYM{i}.NS" for i in range(10)]
        sys.modules["config"] = fake_cfg
        return calls

    def test_retries_until_coverage_threshold_met(self):
        # attempt 1: 2/10 (20%, below 50% threshold) -> retry
        # attempt 2: 7/10 (70%, meets threshold) -> stop
        calls = self._install_fake_yfinance([2, 7])
        movers, expected = watchdog.fetch_movers()
        self.assertEqual(expected, 10)
        self.assertEqual(calls["n"], 2)
        self.assertGreaterEqual(len(movers) / expected, watchdog.MIN_COVERAGE_RATIO)

    def test_gives_up_after_max_attempts_but_still_returns_partial(self):
        calls = self._install_fake_yfinance([1, 1, 1])
        movers, expected = watchdog.fetch_movers()
        self.assertEqual(calls["n"], watchdog.RETRY_ATTEMPTS)
        self.assertEqual(len(movers), 1)
        self.assertEqual(expected, 10)

    def test_snapshot_skips_write_when_coverage_stays_low(self):
        """The exact symptom from 2026-07-23: near-empty batch must not overwrite
        the last good missed-opportunities.json with a misleading all-zero summary."""
        import tempfile
        self._install_fake_yfinance([1, 1, 1])
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            out = base / "missed-opportunities.json"
            out.write_text(json.dumps({"summary": {"winners_held": 3}}))  # "last good" file

            orig_output = watchdog.OUTPUT_FILE
            orig_root = watchdog.ROOT
            watchdog.OUTPUT_FILE = out
            watchdog.ROOT = base
            try:
                watchdog.snapshot()
            finally:
                watchdog.OUTPUT_FILE = orig_output
                watchdog.ROOT = orig_root

            # File must be untouched — no misleading near-empty snapshot written.
            self.assertEqual(json.loads(out.read_text())["summary"]["winners_held"], 3)


if __name__ == "__main__":
    unittest.main()
