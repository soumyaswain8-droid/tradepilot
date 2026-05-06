"""
TradePilot v4 — Candle Pattern Revival Gate
============================================
Used by v4 to decide whether to RE-ENTER a stock that just exited at a loss.

The "watch and confirm" pattern from pro-trader research (Linda Raschke, SMB
Capital, Brett Steenbarger): after cutting a loser, don't re-enter on the
next BUY signal blindly. Wait for a structural reversal signal (bullish
candle + volume + price near the post-drop low) before re-deploying.

Implements 4 gates that ALL must pass for re-entry:
  1. Bullish Engulfing pattern on last 2 5-min bars
  2. Volume on the engulfing bar >= 1.5x 20-bar SMA (confirms real buying)
  3. Time of day in 11:15-14:45 IST sweet spot (avoid open/close noise)
  4. Current price within 0.5% of the post-drop low (catching turn, not falling knife)

Sources informing the design (see docs/research/2026-05-06_revival_research.md):
- Quantified Strategies backtest: Bullish Engulfing 65-75% with volume confirm
- LuxAlgo: volume >= 1.5x SMA lifts pattern accuracy 15-20pp
- TraderRahulPal / JM Financial: NSE 11:15-14:45 IST is the highest-reliability
  reversal window; opening 30 min and last 45 min are noisy

Phase 2 (deferred): replace this rule-based gate with a LightGBM model trained
on historical drawdown-recovery labels. Realistic accuracy expectation per
research: 57-62% AUC for single-stock retail. Rule-based ships TONIGHT;
ML ships next sprint.
"""
from __future__ import annotations
from datetime import datetime, time
from typing import Tuple, Optional


# ---- Tunable thresholds ----------------------------------------------------

VOLUME_CONFIRM_RATIO = 1.5      # signal-bar volume must be >= 1.5x 20-bar SMA
VOLUME_LOOKBACK_BARS = 20       # rolling-average lookback
PRICE_NEAR_LOW_PCT   = 0.5      # current price must be within 0.5% of post-drop low
REVIVAL_WINDOW_START = time(11, 15)  # IST — sweet spot per research
REVIVAL_WINDOW_END   = time(14, 45)  # IST — avoid closing-auction noise


# ---- Candle pattern detectors ----------------------------------------------

def is_bullish_engulfing(bars) -> bool:
    """Last 2 bars: prior red, current green, current body engulfs prior body.

    Geometry per Quantified Strategies / Bulkowski reference:
      - bar[-2] is a red candle: close < open
      - bar[-1] is a green candle: close > open
      - bar[-1] open <= bar[-2] close (current opens at or below prior close)
      - bar[-1] close >= bar[-2] open (current closes at or above prior open)

    Returns False if fewer than 2 bars or any condition fails.
    """
    if bars is None or len(bars) < 2:
        return False
    prev = bars.iloc[-2]
    curr = bars.iloc[-1]
    try:
        prev_red = prev['Close'] < prev['Open']
        curr_green = curr['Close'] > curr['Open']
        opens_below = curr['Open'] <= prev['Close']
        closes_above = curr['Close'] >= prev['Open']
        return bool(prev_red and curr_green and opens_below and closes_above)
    except (KeyError, ValueError, TypeError):
        return False


def volume_confirmed(bars, n_lookback: int = VOLUME_LOOKBACK_BARS,
                     min_ratio: float = VOLUME_CONFIRM_RATIO) -> bool:
    """Last bar volume >= min_ratio * SMA(volume, n_lookback)."""
    if bars is None or len(bars) < n_lookback + 1:
        return False
    try:
        last_vol = float(bars.iloc[-1]['Volume'])
        avg_vol = float(bars.iloc[-(n_lookback + 1):-1]['Volume'].mean())
        if avg_vol <= 0:
            return False
        return last_vol >= min_ratio * avg_vol
    except (KeyError, ValueError, TypeError):
        return False


def is_revival_window(now: Optional[datetime] = None) -> bool:
    """11:15-14:45 IST is the sweet-spot window for reversal signals on NSE.

    Outside this window: opening volatility (09:15-09:45) creates fake hammers,
    lunch lull (12:30-14:00) has low validity, closing auction noise (14:45+)
    unwinds reversals before close.
    """
    now = now or datetime.now()
    t = now.time()
    return REVIVAL_WINDOW_START <= t <= REVIVAL_WINDOW_END


def near_post_drop_low(current_price: float, post_drop_low: float,
                       tolerance_pct: float = PRICE_NEAR_LOW_PCT) -> bool:
    """Current price within tolerance% of post-drop low.

    Catches the stock turning UP from a confirmed bottom rather than catching
    a falling knife mid-decline.
    """
    if post_drop_low <= 0 or current_price <= 0:
        return False
    return abs(current_price - post_drop_low) / post_drop_low * 100 <= tolerance_pct


# ---- Master gate -----------------------------------------------------------

def revival_signal(bars, current_price: float, post_drop_low: float,
                   now: Optional[datetime] = None) -> Tuple[bool, str]:
    """Run all 4 gates. ALL must pass. Returns (allowed, reason).

    Caller is responsible for fetching bars (typically last 22 5-min bars from
    yfinance for the symbol). bars is a pandas DataFrame with columns
    ['Open', 'High', 'Low', 'Close', 'Volume'].
    """
    if not is_revival_window(now):
        return False, "outside time window (11:15-14:45 IST)"
    if bars is None or len(bars) < VOLUME_LOOKBACK_BARS + 1:
        return False, f"insufficient bars ({0 if bars is None else len(bars)} < {VOLUME_LOOKBACK_BARS + 1})"
    if not is_bullish_engulfing(bars):
        return False, "no bullish engulfing pattern on last 2 bars"
    if not volume_confirmed(bars):
        return False, f"volume below {VOLUME_CONFIRM_RATIO}x SMA({VOLUME_LOOKBACK_BARS})"
    if not near_post_drop_low(current_price, post_drop_low):
        return False, f"price Rs {current_price:.2f} too far from drop-low Rs {post_drop_low:.2f} (>{PRICE_NEAR_LOW_PCT}%)"
    return True, "engulfing + volume + window + near-low all confirmed"


# ---- Convenience: yfinance fetch helper -----------------------------------

def fetch_recent_bars(symbol: str, n_bars: int = 22):
    """Pull last n 5-min bars from yfinance. Returns DataFrame or None.

    The default 22 covers the 20-bar SMA lookback + 2-bar pattern window with
    one bar of safety. Indian symbols only (auto-appends .NS).
    """
    try:
        import yfinance as yf
    except ImportError:
        return None
    yf_sym = symbol if symbol.endswith('.NS') else symbol + '.NS'
    try:
        df = yf.download(yf_sym, period='1d', interval='5m',
                         progress=False, auto_adjust=False, threads=False)
    except Exception:
        return None
    if hasattr(df.columns, 'levels') and len(df.columns.levels) > 1:
        df.columns = df.columns.droplevel(1)
    df = df.dropna(subset=['Open', 'Close', 'Volume'])
    return df.tail(n_bars) if len(df) >= 2 else None


# ---- Self-test --------------------------------------------------------------

def _demo():
    """Quick smoke test with synthetic bars."""
    import pandas as pd
    # Fabricate a 22-bar series ending in a bullish engulfing on big volume
    rows = []
    base = 100.0
    for i in range(20):
        # Down-trend bars (red candles, normal volume)
        o = base - i * 0.3
        c = o - 0.4
        rows.append({'Open': o, 'High': o + 0.1, 'Low': c - 0.1,
                     'Close': c, 'Volume': 100_000})
    # Bar -2: small red
    rows.append({'Open': 94.5, 'High': 94.6, 'Low': 93.8,
                 'Close': 94.0, 'Volume': 90_000})
    # Bar -1: bullish engulfing on 2x volume
    rows.append({'Open': 93.8, 'High': 95.5, 'Low': 93.7,
                 'Close': 95.2, 'Volume': 220_000})

    bars = pd.DataFrame(rows)
    print(f"is_bullish_engulfing: {is_bullish_engulfing(bars)}")
    print(f"volume_confirmed (1.5x): {volume_confirmed(bars)}")
    print(f"near_post_drop_low (95.2 vs 95.0): {near_post_drop_low(95.2, 95.0)}")

    # Force time check for 12:00 IST
    forced_time = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    print(f"is_revival_window (12:00): {is_revival_window(forced_time)}")

    ok, reason = revival_signal(bars, current_price=95.2, post_drop_low=95.0,
                                now=forced_time)
    print(f"revival_signal: ok={ok} reason={reason!r}")


if __name__ == "__main__":
    _demo()
