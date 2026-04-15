"""
TradePilot v4 — Intraday Feature Engineering
=============================================
Compute intraday trading features from OHLCV candle data:
  - Opening Range Breakout (ORB)
  - VWAP position
  - Gap analysis
  - Intraday momentum
  - Relative strength vs Nifty
"""

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Opening Range Breakout (ORB)
# ---------------------------------------------------------------------------

def compute_orb(intraday_df: pd.DataFrame) -> dict:
    """
    Opening Range Breakout from first 15-min candle after market open (9:15 AM IST).

    Args:
        intraday_df: DataFrame with OHLCV columns and a datetime index
                     (from yfinance 5m/15m candles, timezone-aware or naive).

    Returns:
        dict with keys: orb_high, orb_low, orb_range_pct,
                        current_vs_orb, breakout_direction, breakout_strength
    """
    defaults = {
        "orb_high": np.nan,
        "orb_low": np.nan,
        "orb_range_pct": 0.0,
        "current_vs_orb": 0.5,
        "breakout_direction": 0,
        "breakout_strength": 0.0,
    }

    if intraday_df is None or intraday_df.empty or len(intraday_df) < 1:
        return defaults

    df = intraday_df.copy()

    # Normalise column names to lowercase
    df.columns = [c.lower() for c in df.columns]
    for needed in ("high", "low", "close"):
        if needed not in df.columns:
            return defaults

    # Identify the first candle (opening range candle)
    # If the index is tz-aware, try to find the 9:15-9:30 window;
    # otherwise just use the first row.
    first_candle = None
    idx = df.index

    if hasattr(idx, "hour"):
        # Filter for candles in the first 15 min after 9:15
        mask = (idx.hour == 9) & (idx.minute >= 15) & (idx.minute < 30)
        if mask.any():
            first_candle = df.loc[mask]
        else:
            # Market may have started later or data doesn't have 9:15;
            # fall back to the first candle of the day.
            first_candle = df.iloc[:1]
    else:
        first_candle = df.iloc[:1]

    if first_candle is None or first_candle.empty:
        return defaults

    orb_high = float(first_candle["high"].max())
    orb_low = float(first_candle["low"].min())
    orb_range = orb_high - orb_low

    # Avoid division by zero
    if orb_low == 0 or orb_range == 0:
        return {
            "orb_high": orb_high,
            "orb_low": orb_low,
            "orb_range_pct": 0.0,
            "current_vs_orb": 0.5,
            "breakout_direction": 0,
            "breakout_strength": 0.0,
        }

    orb_range_pct = (orb_range / orb_low) * 100.0
    current_price = float(df["close"].iloc[-1])

    # Position within ORB: 0 = at low, 1 = at high, >1 = above, <0 = below
    current_vs_orb = (current_price - orb_low) / orb_range

    # Breakout direction
    if current_price > orb_high:
        breakout_direction = 1
        breakout_strength = (current_price - orb_high) / orb_range
    elif current_price < orb_low:
        breakout_direction = -1
        breakout_strength = (orb_low - current_price) / orb_range
    else:
        breakout_direction = 0
        breakout_strength = 0.0

    return {
        "orb_high": orb_high,
        "orb_low": orb_low,
        "orb_range_pct": round(orb_range_pct, 4),
        "current_vs_orb": round(current_vs_orb, 4),
        "breakout_direction": breakout_direction,
        "breakout_strength": round(breakout_strength, 4),
    }


# ---------------------------------------------------------------------------
# VWAP Position
# ---------------------------------------------------------------------------

def compute_vwap_position(intraday_df: pd.DataFrame) -> dict:
    """
    Where current price sits relative to VWAP.

    VWAP = cumulative(typical_price * volume) / cumulative(volume)
    typical_price = (High + Low + Close) / 3

    Returns:
        dict with keys: vwap, price_vs_vwap_pct, above_vwap, vwap_score
    """
    defaults = {
        "vwap": np.nan,
        "price_vs_vwap_pct": 0.0,
        "above_vwap": False,
        "vwap_score": 0.0,
    }

    if intraday_df is None or intraday_df.empty:
        return defaults

    df = intraday_df.copy()
    df.columns = [c.lower() for c in df.columns]

    for needed in ("high", "low", "close", "volume"):
        if needed not in df.columns:
            return defaults

    typical_price = (df["high"] + df["low"] + df["close"]) / 3.0
    cum_vol = df["volume"].cumsum()

    # Guard against zero cumulative volume
    if cum_vol.iloc[-1] == 0:
        return defaults

    cum_tp_vol = (typical_price * df["volume"]).cumsum()
    vwap_series = cum_tp_vol / cum_vol.replace(0, np.nan)
    vwap = float(vwap_series.iloc[-1])

    if np.isnan(vwap) or vwap == 0:
        return defaults

    current_price = float(df["close"].iloc[-1])
    deviation_pct = (current_price - vwap) / vwap * 100.0
    above = current_price > vwap

    # Normalise to -1..+1 score.  Clamp at +/- 2% deviation → +/- 1.0
    vwap_score = np.clip(deviation_pct / 2.0, -1.0, 1.0)

    return {
        "vwap": round(vwap, 2),
        "price_vs_vwap_pct": round(deviation_pct, 4),
        "above_vwap": bool(above),
        "vwap_score": round(float(vwap_score), 4),
    }


# ---------------------------------------------------------------------------
# Gap Analysis
# ---------------------------------------------------------------------------

def compute_gap_analysis(open_price: float, prev_close: float) -> dict:
    """
    Gap up/down analysis.

    Args:
        open_price:  Today's open price.
        prev_close:  Previous trading day's close price.

    Returns:
        dict with keys: gap_pct, gap_type, gap_magnitude
    """
    defaults = {
        "gap_pct": 0.0,
        "gap_type": "flat",
        "gap_magnitude": "small",
    }

    if prev_close is None or open_price is None:
        return defaults
    if prev_close == 0 or np.isnan(prev_close) or np.isnan(open_price):
        return defaults

    gap_pct = (open_price - prev_close) / prev_close * 100.0

    # Type
    if gap_pct > 0.1:
        gap_type = "gap_up"
    elif gap_pct < -0.1:
        gap_type = "gap_down"
    else:
        gap_type = "flat"

    # Magnitude
    abs_gap = abs(gap_pct)
    if abs_gap < 0.5:
        gap_magnitude = "small"
    elif abs_gap < 1.5:
        gap_magnitude = "medium"
    else:
        gap_magnitude = "large"

    return {
        "gap_pct": round(gap_pct, 4),
        "gap_type": gap_type,
        "gap_magnitude": gap_magnitude,
    }


# ---------------------------------------------------------------------------
# Intraday Momentum
# ---------------------------------------------------------------------------

def compute_intraday_momentum(intraday_df: pd.DataFrame) -> dict:
    """
    Intraday momentum indicators.

    Returns:
        dict with keys: first_hour_return, volume_acceleration,
                        price_momentum, intraday_range_pct
    """
    defaults = {
        "first_hour_return": 0.0,
        "volume_acceleration": 1.0,
        "price_momentum": 0.0,
        "intraday_range_pct": 0.0,
    }

    if intraday_df is None or intraday_df.empty:
        return defaults

    df = intraday_df.copy()
    df.columns = [c.lower() for c in df.columns]

    for needed in ("high", "low", "close", "open", "volume"):
        if needed not in df.columns:
            return defaults

    # --- First hour return (9:15 → 10:15 IST) ---
    open_price = float(df["open"].iloc[0])
    first_hour_close = open_price  # fallback

    if hasattr(df.index, "hour"):
        mask_first_hour = (df.index.hour == 10) & (df.index.minute <= 15)
        if mask_first_hour.any():
            first_hour_close = float(df.loc[mask_first_hour, "close"].iloc[-1])
        else:
            # Use the last available candle in the first ~12 rows as proxy
            end_idx = min(12, len(df))
            first_hour_close = float(df["close"].iloc[end_idx - 1])
    else:
        end_idx = min(12, len(df))
        first_hour_close = float(df["close"].iloc[end_idx - 1])

    if open_price != 0:
        first_hour_return = (first_hour_close - open_price) / open_price * 100.0
    else:
        first_hour_return = 0.0

    # --- Volume acceleration (first 30 min volume vs avg candle volume) ---
    total_volume = df["volume"].sum()
    n_candles = len(df)
    avg_candle_vol = total_volume / n_candles if n_candles > 0 else 1.0

    # First 30 min ≈ first 6 five-min candles or first 2 fifteen-min candles
    first_30_count = max(1, min(6, n_candles))
    first_30_vol = df["volume"].iloc[:first_30_count].mean()

    if avg_candle_vol > 0:
        volume_acceleration = first_30_vol / avg_candle_vol
    else:
        volume_acceleration = 1.0

    # --- Price momentum (exponentially-weighted recent candle returns) ---
    closes = df["close"].values.astype(float)
    if len(closes) > 1:
        returns = np.diff(closes) / np.where(closes[:-1] == 0, 1.0, closes[:-1])
        n = len(returns)
        # Exponential weights: more recent → heavier
        weights = np.exp(np.linspace(-1, 0, n))
        weights /= weights.sum()
        price_momentum = float(np.dot(returns, weights)) * 100.0
    else:
        price_momentum = 0.0

    # --- Intraday range ---
    day_high = float(df["high"].max())
    day_low = float(df["low"].min())
    if day_low > 0:
        intraday_range_pct = (day_high - day_low) / day_low * 100.0
    else:
        intraday_range_pct = 0.0

    return {
        "first_hour_return": round(first_hour_return, 4),
        "volume_acceleration": round(volume_acceleration, 4),
        "price_momentum": round(price_momentum, 4),
        "intraday_range_pct": round(intraday_range_pct, 4),
    }


# ---------------------------------------------------------------------------
# Relative Strength vs Nifty
# ---------------------------------------------------------------------------

def compute_relative_strength(
    stock_change_pct: float,
    nifty_change_pct: float,
    stock_5d_return: float,
    nifty_5d_return: float,
) -> dict:
    """
    Relative strength vs Nifty index.

    Args:
        stock_change_pct: Stock's % change today.
        nifty_change_pct: Nifty 50 index % change today.
        stock_5d_return:  Stock's 5-day cumulative return %.
        nifty_5d_return:  Nifty 50 5-day cumulative return %.

    Returns:
        dict with keys: rs_today, rs_5d, rs_rank_score
    """
    # Safe defaults for None inputs
    stock_change_pct = stock_change_pct if stock_change_pct is not None else 0.0
    nifty_change_pct = nifty_change_pct if nifty_change_pct is not None else 0.0
    stock_5d_return = stock_5d_return if stock_5d_return is not None else 0.0
    nifty_5d_return = nifty_5d_return if nifty_5d_return is not None else 0.0

    rs_today = stock_change_pct - nifty_change_pct
    rs_5d = stock_5d_return - nifty_5d_return

    return {
        "rs_today": round(rs_today, 4),
        "rs_5d": round(rs_5d, 4),
        "rs_rank_score": 0.0,  # filled by composite scorer (percentile among 50 stocks)
    }


# ---------------------------------------------------------------------------
# Convenience: all intraday features for one stock
# ---------------------------------------------------------------------------

def compute_all_intraday_features(
    intraday_df: pd.DataFrame,
    open_price: float,
    prev_close: float,
    nifty_change_pct: float,
    stock_change_pct: float = 0.0,
    stock_5d_return: float = 0.0,
    nifty_5d_return: float = 0.0,
) -> dict:
    """
    Compute ALL intraday features for one stock.

    Args:
        intraday_df:      5m/15m OHLCV DataFrame.
        open_price:       Today's open price.
        prev_close:       Previous day's close.
        nifty_change_pct: Nifty 50 % change today.
        stock_change_pct: Stock's % change today (optional, derived if 0).
        stock_5d_return:  Stock's 5-day return % (optional).
        nifty_5d_return:  Nifty's 5-day return % (optional).

    Returns:
        Flat dict merging ORB, VWAP, gap, momentum, and relative-strength features.
    """
    # Derive stock_change_pct from data if not provided
    if stock_change_pct == 0.0 and prev_close and prev_close != 0:
        if intraday_df is not None and not intraday_df.empty:
            cols = [c.lower() for c in intraday_df.columns]
            close_col = "close" if "close" in cols else None
            if close_col:
                current = float(intraday_df.iloc[-1][
                    intraday_df.columns[cols.index("close")]
                ])
                stock_change_pct = (current - prev_close) / prev_close * 100.0

    features: dict = {}
    features.update(compute_orb(intraday_df))
    features.update(compute_vwap_position(intraday_df))
    features.update(compute_gap_analysis(open_price, prev_close))
    features.update(compute_intraday_momentum(intraday_df))
    features.update(compute_relative_strength(
        stock_change_pct, nifty_change_pct, stock_5d_return, nifty_5d_return
    ))

    return features
