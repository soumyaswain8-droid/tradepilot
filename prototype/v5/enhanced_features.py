"""
TradePilot v5 -- Enhanced Features (Calendar + Advanced Technicals)
====================================================================
Calendar effects and expanded technical indicators used by Kaggle
winners and quant funds that the base ml_engine doesn't compute.

Usage:
    from prototype.v5.enhanced_features import compute_calendar_features, compute_enhanced_technicals
CLI:
    python3 -m prototype.v5.enhanced_features
"""
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("tradepilot.v5.enhanced_features")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# NSE weekly expiry moved from Thursday to Tuesday (Nov 2024 onwards).
# ---------------------------------------------------------------------------
EXPIRY_WEEKDAY = 1  # 0=Mon, 1=Tue

# RBI MPC meeting dates for 2026 (announce day; week = Mon-Fri around it)
RBI_MPC_DATES_2026 = [
    date(2026, 2, 7), date(2026, 4, 9), date(2026, 6, 6),
    date(2026, 8, 8), date(2026, 10, 3), date(2026, 12, 5),
]


# ===========================  CALENDAR FEATURES  ===========================

def _next_expiry(d: date) -> date:
    """Return the next weekly expiry (Tuesday) on or after *d*."""
    days_ahead = (EXPIRY_WEEKDAY - d.weekday()) % 7
    if days_ahead == 0 and d.weekday() == EXPIRY_WEEKDAY:
        return d  # today is expiry
    return d + timedelta(days=days_ahead if days_ahead else 7)


def _is_rbi_week(d: date) -> bool:
    """True if *d* falls in the Mon-Fri week containing an RBI MPC date."""
    week_start = d - timedelta(days=d.weekday())  # Monday
    week_end = week_start + timedelta(days=4)      # Friday
    return any(week_start <= mpc <= week_end for mpc in RBI_MPC_DATES_2026)


def compute_calendar_features(dt: Optional[Union[date, str]] = None) -> Dict[str, float]:
    """
    Calendar-based features that affect Indian equity market behaviour.

    Parameters
    ----------
    dt : date, str (YYYY-MM-DD) or None (defaults to today)

    Returns
    -------
    dict with 12 features (all numeric, ML-friendly).
    """
    if dt is None:
        d = date.today()
    elif isinstance(dt, str):
        d = datetime.strptime(dt, "%Y-%m-%d").date()
    else:
        d = dt

    dow = d.weekday()  # 0=Mon .. 4=Fri
    dom = d.day
    month = d.month
    days_in_month = (d.replace(month=month % 12 + 1, day=1) - timedelta(days=1)).day \
        if month < 12 else 31

    next_exp = _next_expiry(d)
    days_to_exp = (next_exp - d).days

    return {
        "is_monday":        int(dow == 0),
        "is_friday":        int(dow == 4),
        "day_of_week":      dow,
        "is_month_start":   int(dom <= 3),
        "is_month_end":     int(dom >= days_in_month - 2),
        "is_expiry_week":   int(days_to_exp <= (4 - dow) if dow <= EXPIRY_WEEKDAY else days_to_exp <= 7),
        "is_expiry_day":    int(d == next_exp),
        "days_to_expiry":   days_to_exp,
        "is_quarter_end":   int(month in (3, 6, 9, 12) and dom >= days_in_month - 4),
        "is_budget_month":  int(month == 2),
        "is_rbi_week":      int(_is_rbi_week(d)),
        "month_of_year":    month,
    }


# ========================  ENHANCED TECHNICALS  ============================

def _williams_r(high: pd.Series, low: pd.Series, close: pd.Series,
                period: int = 14) -> float:
    """Williams %R: (HH - Close) / (HH - LL) * -100."""
    hh = high.rolling(period).max()
    ll = low.rolling(period).min()
    wr = (hh - close) / (hh - ll) * -100
    return round(float(wr.iloc[-1]), 2)


def _cmf(high: pd.Series, low: pd.Series, close: pd.Series,
         volume: pd.Series, period: int = 20) -> float:
    """Chaikin Money Flow over *period* bars."""
    mfm = ((close - low) - (high - close)) / (high - low + 1e-9)
    mfv = mfm * volume
    cmf = mfv.rolling(period).sum() / (volume.rolling(period).sum() + 1e-9)
    return round(float(cmf.iloc[-1]), 4)


def _cci(high: pd.Series, low: pd.Series, close: pd.Series,
         period: int = 20) -> float:
    """Commodity Channel Index."""
    tp = (high + low + close) / 3
    sma_tp = tp.rolling(period).mean()
    mad = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - x.mean())), raw=True)
    cci = (tp - sma_tp) / (0.015 * mad + 1e-9)
    return round(float(cci.iloc[-1]), 2)


def _obv_slope(close: pd.Series, volume: pd.Series, period: int = 10) -> float:
    """Linear regression slope of OBV over *period* bars."""
    direction = np.sign(close.diff())
    obv = (direction * volume).cumsum()
    obv_tail = obv.iloc[-period:].values
    if len(obv_tail) < period:
        return 0.0
    x = np.arange(period, dtype=float)
    slope = np.polyfit(x, obv_tail, 1)[0]
    # Normalise by mean OBV magnitude so the feature is scale-free
    mean_obv = np.mean(np.abs(obv_tail)) + 1e-9
    return round(float(slope / mean_obv), 6)


def _keltner_position(high: pd.Series, low: pd.Series, close: pd.Series,
                      ema_period: int = 20, atr_period: int = 10,
                      multiplier: float = 2.0) -> float:
    """Price position within Keltner Channel (0 = lower band, 1 = upper)."""
    mid = close.ewm(span=ema_period, adjust=False).mean()
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    upper = mid + multiplier * atr
    lower = mid - multiplier * atr
    band_width = upper - lower + 1e-9
    pos = (close - lower) / band_width
    return round(float(pos.iloc[-1]), 4)


def _atr_percentile(high: pd.Series, low: pd.Series, close: pd.Series,
                    atr_period: int = 14, lookback: int = 252) -> float:
    """Percentile rank of current ATR vs trailing *lookback* ATR values."""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(atr_period).mean()
    tail = atr.dropna().iloc[-lookback:]
    if len(tail) < 20:
        return 50.0
    current = float(tail.iloc[-1])
    pct = (tail < current).sum() / len(tail) * 100
    return round(float(pct), 1)


def _consecutive_days(close: pd.Series) -> tuple:
    """Return (consecutive_up_days, consecutive_down_days)."""
    changes = close.diff().dropna()
    up, down = 0, 0
    for chg in reversed(changes.values):
        if chg > 0 and down == 0:
            up += 1
        elif chg < 0 and up == 0:
            down += 1
        else:
            break
    return up, down


def _distance_from_extremes(close: pd.Series, lookback: int = 252) -> tuple:
    """% distance from 52-week high and low."""
    tail = close.iloc[-lookback:]
    hi = float(tail.max())
    lo = float(tail.min())
    cur = float(close.iloc[-1])
    dist_high = round((cur - hi) / hi * 100, 2)
    dist_low = round((cur - lo) / lo * 100, 2)
    return dist_high, dist_low


def compute_enhanced_technicals(stock_df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute advanced technical indicators from an OHLCV DataFrame.

    Parameters
    ----------
    stock_df : DataFrame with columns Date, Open, High, Low, Close, Volume
               (or Adj Close instead of Close).

    Returns
    -------
    dict with 10 features (all numeric).
    """
    df = stock_df.copy()

    # Normalise column names (yfinance style)
    col_map = {c: c.strip().title().replace(" ", "") for c in df.columns}
    df.rename(columns=col_map, inplace=True)
    if "AdjClose" in df.columns and "Close" not in df.columns:
        df["Close"] = df["AdjClose"]

    for col in ("High", "Low", "Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    h, l, c, v = df["High"], df["Low"], df["Close"], df["Volume"]

    up, down = _consecutive_days(c)
    dist_high, dist_low = _distance_from_extremes(c)

    return {
        "williams_r":              _williams_r(h, l, c),
        "cmf_20":                  _cmf(h, l, c, v),
        "cci_20":                  _cci(h, l, c),
        "obv_slope":               _obv_slope(c, v),
        "keltner_position":        _keltner_position(h, l, c),
        "atr_percentile":          _atr_percentile(h, l, c),
        "consecutive_up_days":     up,
        "consecutive_down_days":   down,
        "distance_from_52w_high":  dist_high,
        "distance_from_52w_low":   dist_low,
    }


# ===========================  CLI ENTRYPOINT  ==============================

def main():
    """Print today's calendar + technical features for NIFTY index."""
    data_dir = Path(__file__).resolve().parent.parent / "data"
    nsei_path = data_dir / "^NSEI.csv"

    print("=" * 60)
    print("  TradePilot v5 -- Enhanced Features Demo")
    print("=" * 60)

    # --- Calendar ---
    today = date.today()
    cal = compute_calendar_features(today)
    print(f"\n--- Calendar Features ({today}) ---")
    for k, v in cal.items():
        print(f"  {k:25s} = {v}")

    # --- Technicals ---
    if not nsei_path.exists():
        print(f"\n[WARN] NIFTY data not found at {nsei_path}; skipping technicals.")
        return

    df = pd.read_csv(nsei_path, parse_dates=["Date"])
    df.sort_values("Date", inplace=True)
    df.reset_index(drop=True, inplace=True)

    tech = compute_enhanced_technicals(df)
    last_date = df["Date"].iloc[-1].strftime("%Y-%m-%d")
    last_close = df["Close"].iloc[-1]
    print(f"\n--- Enhanced Technicals (NIFTY, last bar {last_date}, close {last_close:.1f}) ---")
    for k, v in tech.items():
        print(f"  {k:25s} = {v}")

    print()


if __name__ == "__main__":
    main()
