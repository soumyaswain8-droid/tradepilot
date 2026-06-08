"""Wiring tests: Layer 2 must flip on INTRADAY bars, with graceful daily fallback.

We load the engine script by path (its filename has a hyphen) and monkeypatch the
two bar loaders so we can prove WHICH timeframe drove the decision.
"""
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "scripts" / "v7_regime-paper-trade.py"


def _load_engine():
    spec = importlib.util.spec_from_file_location("v7_engine_under_test", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["v7_engine_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


def _uptrend_daily(n=80):
    c = pd.Series([100 + i for i in range(n)], dtype="float64")
    return pd.DataFrame({"High": c + 1.0, "Low": c - 1.0, "Close": c})


def _downtrend_5m(n=40):
    c = pd.Series([200 - i for i in range(n)], dtype="float64")
    return pd.DataFrame({"High": c + 0.5, "Low": c - 0.5, "Close": c})


def test_intraday_candles_registered():
    eng = _load_engine()
    assert "intraday_candles" in eng._mod_imports


def test_intraday_bars_drive_the_flip(monkeypatch):
    """Daily=uptrend (allowed=LONG_ONLY) but intraday=downtrend (Supertrend=SHORT).
    A SHORT under LONG_ONLY collapses to FLAT. If the engine had (wrongly) used the
    DAILY uptrend for Supertrend it would return LONG, so FLAT proves intraday won.
    change_pct=+1.0 keeps the green/red guard out of the way."""
    eng = _load_engine()
    monkeypatch.setattr(eng, "_v7_load_daily", lambda s: _uptrend_daily())
    monkeypatch.setattr(eng, "_v7_load_intraday", lambda s: _downtrend_5m())
    assert eng._v7_direction_for("TEST", change_pct=1.0) == "FLAT"


def test_falls_back_to_daily_when_intraday_missing(monkeypatch):
    """Intraday missing -> Supertrend runs on the daily uptrend -> LONG (allowed)."""
    eng = _load_engine()
    monkeypatch.setattr(eng, "_v7_load_daily", lambda s: _uptrend_daily())
    monkeypatch.setattr(eng, "_v7_load_intraday", lambda s: None)
    assert eng._v7_direction_for("TEST", change_pct=1.0) == "LONG"
