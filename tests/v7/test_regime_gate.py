import numpy as np, pandas as pd
from prototype.v7.regime_gate import directional_indicators

def _series(vals): return pd.Series(vals, dtype="float64")

def test_uptrend_has_plus_di_above_minus_di():
    n = 60
    close = _series([100 + i for i in range(n)])
    high = close + 1.0
    low = close - 1.0
    adx, pdi, mdi = directional_indicators(high, low, close, period=14)
    assert pdi.iloc[-1] > mdi.iloc[-1]
    assert adx.iloc[-1] > 25


from prototype.v7.regime_gate import allowed_side

def _df(closes):
    c = _series(closes)
    return pd.DataFrame({"High": c + 1.0, "Low": c - 1.0, "Close": c})

def test_strong_uptrend_is_long_only():
    df = _df([100 + i for i in range(80)])
    assert allowed_side(df) == "LONG_ONLY"

def test_strong_downtrend_is_short_only():
    df = _df([200 - i for i in range(80)])
    assert allowed_side(df) == "SHORT_ONLY"

def test_flat_choppy_is_flat():
    closes = [100 + (1 if i % 2 == 0 else -1) for i in range(80)]
    assert allowed_side(_df(closes)) == "FLAT"
