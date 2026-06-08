"""Layer 1 — daily allowed-side regime gate (see docs/research/2026-06-08_long-short-flip-spec.md)."""
import numpy as np
import pandas as pd


def _atr(high, low, close, period=14):
    prev_close = close.shift(1)
    tr = pd.concat([(high - low),
                    (high - prev_close).abs(),
                    (low - prev_close).abs()], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def directional_indicators(high, low, close, period=14):
    """Return (adx, plus_di, minus_di) as pd.Series (Wilder DMI)."""
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    plus_dm[plus_dm < minus_dm] = 0
    minus_dm[minus_dm < plus_dm] = 0
    atr = _atr(high, low, close, period)
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr.replace(0, np.nan))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    adx = dx.rolling(period).mean()
    return adx, plus_di, minus_di


def allowed_side(daily, adx_trend=25.0, adx_chop=20.0, sma_period=50, slope_lookback=5):
    """daily: DataFrame with High/Low/Close in chronological order.
    Returns one of LONG_ONLY / SHORT_ONLY / BOTH / FLAT.

    ADX gates PERMISSION (non-negotiable: <chop => FLAT); +DI/-DI + SMA50 slope
    give DIRECTION. This is the rule that stops longing fallers / shorting risers.
    """
    if daily is None or len(daily) < max(sma_period + slope_lookback, 30):
        return "FLAT"
    adx, pdi, mdi = directional_indicators(daily["High"], daily["Low"], daily["Close"])
    a, p, m = adx.iloc[-1], pdi.iloc[-1], mdi.iloc[-1]
    if np.isnan(a) or a < adx_chop:
        return "FLAT"
    sma = daily["Close"].rolling(sma_period).mean()
    if np.isnan(sma.iloc[-1]) or np.isnan(sma.iloc[-1 - slope_lookback]):
        return "FLAT"
    slope = sma.iloc[-1] - sma.iloc[-1 - slope_lookback]
    bullish = (p > m) and (slope > 0)
    bearish = (m > p) and (slope < 0)
    if bullish:
        return "LONG_ONLY"
    if bearish:
        return "SHORT_ONLY"
    return "BOTH" if a >= adx_trend else "FLAT"
