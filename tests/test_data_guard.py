"""DATA-GUARD — unit tests for the live-tape freshness gate (TP outage 2026-07-08/10).

Root cause being guarded: on 07-08 and 07-10 the network was down from market open;
signals were generated off cached CSVs and deploy_signals opened positions the engine
could never price again (exit=None, Rs 0 audits). The guard blocks NEW entries when
the live 1-minute NIFTY tape is missing or stale. Exits are unaffected.

Run with: python3 -m pytest tests/test_data_guard.py -v
"""
import sys
import unittest
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "v5_paper_trade", str(PROJECT_ROOT / "scripts" / "v5-paper-trade.py")
)
v5 = importlib.util.module_from_spec(_spec)
sys.modules["v5_paper_trade"] = v5
try:
    _spec.loader.exec_module(v5)
except Exception as e:
    print(f"[warn] partial module load: {e}")

IST = "Asia/Kolkata"


def _df_with_last_bar(ts: pd.Timestamp) -> pd.DataFrame:
    idx = pd.DatetimeIndex([ts - pd.Timedelta(minutes=1), ts])
    return pd.DataFrame({"Close": [100.0, 101.0]}, index=idx)


class TestTapeIsFresh(unittest.TestCase):
    def setUp(self):
        self.now = pd.Timestamp("2026-07-13 10:30:00", tz=IST)

    def test_none_df_is_not_fresh(self):
        self.assertFalse(v5._tape_is_fresh(None, now=self.now))

    def test_empty_df_is_not_fresh(self):
        self.assertFalse(v5._tape_is_fresh(pd.DataFrame(), now=self.now))

    def test_stale_bar_is_not_fresh(self):
        # last bar 40 min old — an outage mid-session leaves exactly this shape
        df = _df_with_last_bar(self.now - pd.Timedelta(minutes=40))
        self.assertFalse(v5._tape_is_fresh(df, now=self.now, max_age_min=15))

    def test_recent_bar_is_fresh(self):
        df = _df_with_last_bar(self.now - pd.Timedelta(minutes=3))
        self.assertTrue(v5._tape_is_fresh(df, now=self.now, max_age_min=15))

    def test_tz_naive_index_still_works(self):
        # yfinance normally returns tz-aware, but never crash on naive
        naive_now = pd.Timestamp("2026-07-13 10:30:00")
        df = _df_with_last_bar(naive_now - pd.Timedelta(minutes=3))
        self.assertTrue(v5._tape_is_fresh(df, now=self.now, max_age_min=15))


if __name__ == "__main__":
    unittest.main()
