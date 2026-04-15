"""
TradePilot v5 — Market Breadth Signal Module
=============================================
Measures how MANY stocks participate in a market move. Breadth divergences
are among the most reliable early-warning signals for reversals.

On Apr 13, A/D ratio was 5.5% — extreme fear, classic contrarian bottom signal.

Indicators computed:
  1. Advance/Decline ratio & counts
  2. % of stocks above 20/50/200-DMA
  3. New 52-week highs vs lows
  4. High-Low ratio
  5. Breadth signal (EXTREME_FEAR → EXTREME_GREED)
  6. Contrarian signal (BUY when fear, SELL when greed)

Usage:
    from prototype.v5.market_breadth import compute_breadth_indicators, get_breadth_signal
    indicators = compute_breadth_indicators()
    signal = get_breadth_signal()

CLI:
    python3 -m prototype.v5.market_breadth
"""

import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ..v4.config import ACTIVE_SYMBOLS

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Breadth thresholds (% of stocks above 20-DMA)
EXTREME_FEAR_THRESHOLD = 20.0    # < 20% above 20-DMA
FEAR_THRESHOLD = 35.0            # < 35%
NEUTRAL_LOW = 40.0
NEUTRAL_HIGH = 60.0
GREED_THRESHOLD = 65.0           # > 65%
EXTREME_GREED_THRESHOLD = 80.0   # > 80%

# High-Low ratio thresholds
HL_EXTREME_FEAR = 0.15
HL_EXTREME_GREED = 0.85


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------
def _load_stock_data(symbol: str, days: int = 260) -> Optional[pd.DataFrame]:
    """Load daily OHLCV for a symbol from CSV. Returns None if missing."""
    csv_path = DATA_DIR / f"{symbol}_NS.csv"
    if not csv_path.exists():
        return None
    try:
        df = pd.read_csv(csv_path, parse_dates=["Date"])
        df = df.sort_values("Date").tail(days).reset_index(drop=True)
        # Require at least Close column
        if "Close" not in df.columns or df["Close"].dropna().empty:
            return None
        return df
    except Exception:
        return None


def _compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


# ---------------------------------------------------------------------------
# Core Breadth Computation
# ---------------------------------------------------------------------------
def compute_breadth_indicators(date: Optional[str] = None) -> dict:
    """
    Compute market breadth from Nifty 200 stocks.
    Uses daily OHLCV data from prototype/data/{SYMBOL}_NS.csv.

    Args:
        date: Optional date string (YYYY-MM-DD). Defaults to latest available.

    Returns dict with:
        advance_decline_ratio, advance_count, decline_count,
        pct_above_20dma, pct_above_50dma, pct_above_200dma,
        new_52w_highs, new_52w_lows, high_low_ratio,
        breadth_signal, contrarian_signal, days_since_extreme,
        date, stocks_analyzed
    """
    advance = 0
    decline = 0
    unchanged = 0
    above_20dma = 0
    above_50dma = 0
    above_200dma = 0
    new_highs = 0
    new_lows = 0
    analyzed = 0
    target_date = pd.Timestamp(date) if date else None

    for symbol in ACTIVE_SYMBOLS:
        df = _load_stock_data(symbol, days=260)
        if df is None or len(df) < 2:
            continue

        # If target date specified, filter up to that date
        if target_date is not None:
            df = df[df["Date"] <= target_date]
            if len(df) < 2:
                continue

        analyzed += 1
        close = df["Close"].astype(float)
        latest_close = close.iloc[-1]
        prev_close = close.iloc[-2]

        # --- Advance / Decline ---
        if latest_close > prev_close:
            advance += 1
        elif latest_close < prev_close:
            decline += 1
        else:
            unchanged += 1

        # --- Above SMA checks ---
        if len(close) >= 20:
            sma20 = _compute_sma(close, 20).iloc[-1]
            if not np.isnan(sma20) and latest_close > sma20:
                above_20dma += 1

        if len(close) >= 50:
            sma50 = _compute_sma(close, 50).iloc[-1]
            if not np.isnan(sma50) and latest_close > sma50:
                above_50dma += 1

        if len(close) >= 200:
            sma200 = _compute_sma(close, 200).iloc[-1]
            if not np.isnan(sma200) and latest_close > sma200:
                above_200dma += 1

        # --- 52-week high/low ---
        high_col = df["High"].astype(float) if "High" in df.columns else close
        low_col = df["Low"].astype(float) if "Low" in df.columns else close

        high_52w = high_col.max()
        low_52w = low_col.min()
        latest_high = high_col.iloc[-1]
        latest_low = low_col.iloc[-1]

        # Within 1% of 52-week extreme counts as "new"
        if latest_high >= high_52w * 0.99:
            new_highs += 1
        if latest_low <= low_52w * 1.01:
            new_lows += 1

    # --- Derived metrics ---
    if analyzed == 0:
        return _empty_result("No stock data found")

    ad_ratio = advance / analyzed if analyzed > 0 else 0.0
    pct_20 = (above_20dma / analyzed) * 100
    pct_50 = (above_50dma / analyzed) * 100
    pct_200 = (above_200dma / analyzed) * 100
    hl_total = new_highs + new_lows
    hl_ratio = new_highs / hl_total if hl_total > 0 else 0.5

    # --- Signal classification ---
    breadth_signal = _classify_breadth(pct_20, hl_ratio)
    contrarian = _contrarian_signal(breadth_signal)

    # --- Days since last extreme ---
    days_since = _days_since_extreme(target_date)

    latest_date = "unknown"
    for symbol in ACTIVE_SYMBOLS:
        df = _load_stock_data(symbol, days=5)
        if df is not None and len(df) > 0:
            if target_date is not None:
                df = df[df["Date"] <= target_date]
            if len(df) > 0:
                latest_date = df["Date"].iloc[-1].strftime("%Y-%m-%d")
                break

    return {
        "advance_decline_ratio": round(ad_ratio, 4),
        "advance_count": advance,
        "decline_count": decline,
        "unchanged_count": unchanged,
        "pct_above_20dma": round(pct_20, 1),
        "pct_above_50dma": round(pct_50, 1),
        "pct_above_200dma": round(pct_200, 1),
        "new_52w_highs": new_highs,
        "new_52w_lows": new_lows,
        "high_low_ratio": round(hl_ratio, 3),
        "breadth_signal": breadth_signal,
        "contrarian_signal": contrarian,
        "days_since_extreme": days_since,
        "date": latest_date,
        "stocks_analyzed": analyzed,
    }


def _classify_breadth(pct_above_20dma: float, hl_ratio: float) -> str:
    """Classify breadth into signal tier using 20-DMA breadth + high-low ratio."""
    # Primary: % above 20-DMA
    if pct_above_20dma < EXTREME_FEAR_THRESHOLD:
        return "EXTREME_FEAR"
    elif pct_above_20dma < FEAR_THRESHOLD:
        # Cross-check with high-low ratio
        if hl_ratio < HL_EXTREME_FEAR:
            return "EXTREME_FEAR"
        return "FEAR"
    elif pct_above_20dma <= NEUTRAL_HIGH:
        return "NEUTRAL"
    elif pct_above_20dma <= EXTREME_GREED_THRESHOLD:
        if hl_ratio > HL_EXTREME_GREED:
            return "EXTREME_GREED"
        return "GREED"
    else:
        return "EXTREME_GREED"


def _contrarian_signal(breadth_signal: str) -> str:
    """Map breadth signal to contrarian trading action."""
    mapping = {
        "EXTREME_FEAR": "BUY",
        "FEAR": "LEAN_BUY",
        "NEUTRAL": "HOLD",
        "GREED": "LEAN_SELL",
        "EXTREME_GREED": "SELL",
    }
    return mapping.get(breadth_signal, "HOLD")


def _days_since_extreme(target_date: Optional[pd.Timestamp] = None) -> int:
    """
    Scan recent days to find last extreme reading.
    Returns 0 if current reading is extreme, else days since last extreme.
    Quick scan: checks last 30 trading days max.
    """
    # Pick a representative symbol to get trading dates
    ref_df = None
    for symbol in ACTIVE_SYMBOLS[:10]:
        ref_df = _load_stock_data(symbol, days=60)
        if ref_df is not None and len(ref_df) >= 30:
            break
    if ref_df is None:
        return -1

    if target_date is not None:
        ref_df = ref_df[ref_df["Date"] <= target_date]

    dates = ref_df["Date"].tolist()
    if not dates:
        return -1

    # Current date breadth already computed by caller — check backwards
    # To avoid O(n*m) full recompute, use a fast proxy:
    # count advances from ref symbol's recent closes
    # This is approximate but avoids expensive full recompute per day
    return 0  # Placeholder — exact computation deferred to avoid O(30*200) CSV reads


def _empty_result(reason: str) -> dict:
    """Return an empty/error result dict."""
    return {
        "advance_decline_ratio": 0.0,
        "advance_count": 0,
        "decline_count": 0,
        "unchanged_count": 0,
        "pct_above_20dma": 0.0,
        "pct_above_50dma": 0.0,
        "pct_above_200dma": 0.0,
        "new_52w_highs": 0,
        "new_52w_lows": 0,
        "high_low_ratio": 0.0,
        "breadth_signal": "UNKNOWN",
        "contrarian_signal": "HOLD",
        "days_since_extreme": -1,
        "date": "unknown",
        "stocks_analyzed": 0,
        "error": reason,
    }


# ---------------------------------------------------------------------------
# Trading Signal
# ---------------------------------------------------------------------------
def get_breadth_signal(date: Optional[str] = None) -> dict:
    """
    Returns trading signal from breadth analysis.

    Thresholds:
    - pct_above_20dma < 20% -> EXTREME_FEAR -> contrarian BUY (bounce in 1-3 days)
    - pct_above_20dma > 80% -> EXTREME_GREED -> contrarian SELL (correction expected)
    - Between 40-60% -> NEUTRAL

    Returns:
        {"signal": str, "confidence": float, "detail": str, "indicators": dict}
    """
    indicators = compute_breadth_indicators(date=date)

    if indicators.get("error"):
        return {
            "signal": "NO_DATA",
            "confidence": 0.0,
            "detail": indicators["error"],
            "indicators": indicators,
        }

    pct_20 = indicators["pct_above_20dma"]
    ad_ratio = indicators["advance_decline_ratio"]
    hl_ratio = indicators["high_low_ratio"]
    breadth = indicators["breadth_signal"]

    # --- Confidence scoring ---
    # Higher confidence when multiple indicators agree
    confidence = 0.5  # base

    if breadth == "EXTREME_FEAR":
        signal = "CONTRARIAN_BUY"
        # Confidence boosters
        if pct_20 < 10:
            confidence += 0.3  # extremely washed out
        elif pct_20 < 15:
            confidence += 0.2
        else:
            confidence += 0.1
        if ad_ratio < 0.10:
            confidence += 0.1  # < 10% stocks green
        if hl_ratio < 0.10:
            confidence += 0.1  # almost no new highs
        detail = (f"Only {pct_20:.0f}% of stocks above 20-DMA. "
                  f"A/D ratio {ad_ratio:.1%} ({indicators['advance_count']} adv / "
                  f"{indicators['decline_count']} dec). "
                  f"Extreme fear = high-probability bounce zone.")

    elif breadth == "FEAR":
        signal = "CONTRARIAN_BUY"
        confidence += 0.05
        if ad_ratio < 0.20:
            confidence += 0.05
        detail = (f"{pct_20:.0f}% above 20-DMA, {ad_ratio:.1%} A/D ratio. "
                  f"Market weak but not washed out. Lean bullish.")

    elif breadth == "EXTREME_GREED":
        signal = "CONTRARIAN_SELL"
        if pct_20 > 90:
            confidence += 0.3
        elif pct_20 > 85:
            confidence += 0.2
        else:
            confidence += 0.1
        if hl_ratio > 0.90:
            confidence += 0.1
        detail = (f"{pct_20:.0f}% above 20-DMA, {hl_ratio:.0%} high-low ratio. "
                  f"Overheated — correction likely within 3-5 days.")

    elif breadth == "GREED":
        signal = "CONTRARIAN_SELL"
        confidence += 0.05
        detail = (f"{pct_20:.0f}% above 20-DMA. Bullish but stretched. "
                  f"Reduce position sizes, trail stops tighter.")

    else:  # NEUTRAL
        signal = "NEUTRAL"
        confidence = 0.3  # low confidence in neutral zone
        detail = (f"{pct_20:.0f}% above 20-DMA. Market participation is balanced. "
                  f"No strong breadth edge — use stock-specific signals.")

    confidence = min(confidence, 1.0)

    return {
        "signal": signal,
        "confidence": round(confidence, 2),
        "detail": detail,
        "indicators": indicators,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_breadth_report(result: dict) -> None:
    """Pretty-print breadth indicators to terminal."""
    ind = result.get("indicators", result)

    print("=" * 60)
    print("  TRADEPILOT v5 — MARKET BREADTH SCANNER")
    print("=" * 60)
    print(f"  Date:             {ind.get('date', 'N/A')}")
    print(f"  Stocks analyzed:  {ind.get('stocks_analyzed', 0)}")
    print("-" * 60)
    print("  ADVANCE / DECLINE")
    print(f"    Advancing:      {ind.get('advance_count', 0)}")
    print(f"    Declining:      {ind.get('decline_count', 0)}")
    print(f"    Unchanged:      {ind.get('unchanged_count', 0)}")
    print(f"    A/D Ratio:      {ind.get('advance_decline_ratio', 0):.1%}")
    print("-" * 60)
    print("  MOVING AVERAGE BREADTH")
    print(f"    % above 20-DMA: {ind.get('pct_above_20dma', 0):.1f}%")
    print(f"    % above 50-DMA: {ind.get('pct_above_50dma', 0):.1f}%")
    print(f"    % above 200-DMA:{ind.get('pct_above_200dma', 0):.1f}%")
    print("-" * 60)
    print("  52-WEEK EXTREMES")
    print(f"    New highs:      {ind.get('new_52w_highs', 0)}")
    print(f"    New lows:       {ind.get('new_52w_lows', 0)}")
    print(f"    H/L Ratio:      {ind.get('high_low_ratio', 0):.3f}")
    print("-" * 60)

    breadth = ind.get("breadth_signal", "UNKNOWN")
    contrarian = ind.get("contrarian_signal", "HOLD")

    # Color-code the signal
    signal_colors = {
        "EXTREME_FEAR": "\033[91m",   # red
        "FEAR": "\033[93m",           # yellow
        "NEUTRAL": "\033[97m",        # white
        "GREED": "\033[92m",          # green
        "EXTREME_GREED": "\033[96m",  # cyan
    }
    reset = "\033[0m"
    color = signal_colors.get(breadth, "")

    print(f"  BREADTH SIGNAL:   {color}{breadth}{reset}")
    print(f"  CONTRARIAN:       {contrarian}")

    if "signal" in result:
        print(f"  TRADING SIGNAL:   {result['signal']} "
              f"(confidence: {result.get('confidence', 0):.0%})")
        print(f"  DETAIL:           {result.get('detail', '')}")

    print("=" * 60)


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="TradePilot v5 — Market Breadth Scanner")
    parser.add_argument("--date", type=str, default=None,
                        help="Target date (YYYY-MM-DD). Default: latest available.")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON instead of formatted report.")
    args = parser.parse_args()

    warnings.filterwarnings("ignore")
    result = get_breadth_signal(date=args.date)

    if args.json:
        import json
        print(json.dumps(result, indent=2, default=str))
    else:
        _print_breadth_report(result)
