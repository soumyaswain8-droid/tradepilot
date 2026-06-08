import pandas as pd
from prototype.v7.supertrend_flip import supertrend

def _series(vals): return pd.Series(vals, dtype="float64")

def test_supertrend_is_long_in_uptrend():
    close = _series([100 + i for i in range(50)])
    high, low = close + 0.5, close - 0.5
    state = supertrend(high, low, close, period=10, multiplier=3.0)
    assert state.iloc[-1] == 1   # +1 = long

def test_supertrend_flips_short_when_price_breaks_down():
    up = [100 + i for i in range(40)]
    down = [140 - 3 * i for i in range(1, 15)]  # sharp reversal
    close = _series(up + down)
    high, low = close + 0.5, close - 0.5
    state = supertrend(high, low, close, period=10, multiplier=3.0)
    assert state.iloc[-1] == -1  # flipped to short

from prototype.v7.supertrend_flip import flip_states

def test_short_signal_under_long_only_becomes_flat():
    assert flip_states([-1], ["LONG_ONLY"]) == ["FLAT"]

def test_long_signal_under_short_only_becomes_flat():
    assert flip_states([1], ["SHORT_ONLY"]) == ["FLAT"]

def test_flat_regime_forces_flat():
    assert flip_states([1, -1], ["FLAT", "FLAT"]) == ["FLAT", "FLAT"]

def test_both_regime_follows_supertrend():
    assert flip_states([1, -1, 1], ["BOTH", "BOTH", "BOTH"]) == ["LONG", "SHORT", "LONG"]
