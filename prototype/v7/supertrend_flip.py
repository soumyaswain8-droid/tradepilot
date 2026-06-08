"""Layer 2 — Supertrend stop-and-reverse + gate-constrained flip machine."""
import numpy as np
import pandas as pd
from prototype.v7.regime_gate import _atr


def supertrend(high, low, close, period=10, multiplier=3.0):
    """Return a state Series: +1 (long/green) or -1 (short/red).
    Flips when close crosses the path-dependent final band (acts as trailing stop).
    """
    atr = _atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    upper = hl2 + multiplier * atr
    lower = hl2 - multiplier * atr

    final_upper = upper.copy()
    final_lower = lower.copy()
    for i in range(1, len(close)):
        if close.iloc[i - 1] <= final_upper.iloc[i - 1]:
            final_upper.iloc[i] = min(upper.iloc[i], final_upper.iloc[i - 1])
        if close.iloc[i - 1] >= final_lower.iloc[i - 1]:
            final_lower.iloc[i] = max(lower.iloc[i], final_lower.iloc[i - 1])

    state = pd.Series(1, index=close.index, dtype="int64")
    for i in range(1, len(close)):
        prev = state.iloc[i - 1]
        if prev == 1:
            state.iloc[i] = -1 if close.iloc[i] < final_lower.iloc[i] else 1
        else:
            state.iloc[i] = 1 if close.iloc[i] > final_upper.iloc[i] else -1
    return state


def flip_states(supertrend_states, allowed_sides):
    """Constrain the Supertrend signal by Layer 1's allowed_side, per bar.
    supertrend_states: iterable of +1/-1.  allowed_sides: iterable of
    LONG_ONLY/SHORT_ONLY/BOTH/FLAT.  Returns list of LONG/SHORT/FLAT.

    This is the guard that makes shorting-a-riser / longing-a-faller impossible:
    a side the regime forbids collapses to FLAT.
    """
    out = []
    for s, allowed in zip(supertrend_states, allowed_sides):
        want = "LONG" if s > 0 else "SHORT"
        if allowed == "FLAT":
            out.append("FLAT")
        elif allowed == "LONG_ONLY":
            out.append("LONG" if want == "LONG" else "FLAT")
        elif allowed == "SHORT_ONLY":
            out.append("SHORT" if want == "SHORT" else "FLAT")
        else:  # BOTH
            out.append(want)
    return out
