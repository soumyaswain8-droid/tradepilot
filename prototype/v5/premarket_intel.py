"""
TradePilot v5 — Pre-Market Intelligence Module
================================================
Generates signals BEFORE market open (9:15 AM IST) so the system
can adjust position sizing and strategy bias.

Signals:
  1. GIFT Nifty gap prediction (vs previous Nifty close)
  2. FII flow direction (3d/5d rolling net, streak detection)
  3. Global overnight sentiment (S&P 500, Hang Seng, Nikkei)
  4. Combined bias + size multiplier

Usage:
    from prototype.v5.premarket_intel import get_premarket_intel
    intel = get_premarket_intel()

CLI:
    python3 -m prototype.v5.premarket_intel
"""

import datetime as dt
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
NSEI_CSV = DATA_DIR / "^NSEI.csv"

# ---------- thresholds ----------
GAP_THRESHOLD_PCT = 0.3       # |gap| > 0.3% counts as directional
FII_HEAVY_SELL_CR = -2000     # crores, per day
FII_STREAK_BEARISH = 3        # consecutive sell days for bearish
FII_REVERSAL_DAYS = 10        # sell streak length before reversal is "strong"
GLOBAL_DROP_PCT = -1.0        # both US+Asia down >1% = strong bear

# ---------- helpers ----------

def _safe_fetch(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    """Fetch recent data from yfinance, return empty df on failure."""
    try:
        df = yf.download(ticker, period=period, interval=interval,
                         progress=False, timeout=10)
        if df is not None and not df.empty:
            # yfinance >=0.2.31 returns MultiIndex columns for single tickers
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            return df
    except Exception as e:
        log.warning("yfinance fetch failed for %s: %s", ticker, e)
    return pd.DataFrame()


def _previous_nifty_close() -> float | None:
    """Get the previous trading day's Nifty 50 closing price (not today's)."""
    # yfinance daily data — take second-to-last row (previous close)
    df = _safe_fetch("^NSEI", period="5d")
    if not df.empty and len(df) >= 2:
        val = float(df["Close"].iloc[-2])
        if not np.isnan(val):
            return val

    # Fallback: local CSV
    if NSEI_CSV.exists():
        try:
            csv_df = pd.read_csv(NSEI_CSV, parse_dates=["Date"])
            if len(csv_df) >= 2:
                return float(csv_df.iloc[-2]["Close"])
            if not csv_df.empty:
                return float(csv_df.iloc[-1]["Close"])
        except Exception:
            pass

    # Last resort: if we only got 1 row from yfinance
    if not df.empty:
        val = float(df["Close"].iloc[-1])
        if not np.isnan(val):
            return val
    return None


def _gift_nifty_price() -> float | None:
    """
    Attempt to get GIFT Nifty / SGX Nifty current level.
    yfinance doesn't have a reliable GIFT Nifty ticker, so we try
    multiple approaches.  Returns the latest available Nifty price
    (intraday if market is open, else last daily close).
    """
    # Attempt 1: dedicated GIFT Nifty ticker (usually unavailable)
    df = _safe_fetch("NIFTY_GS.NS", period="1d", interval="1m")
    if not df.empty:
        val = float(df["Close"].dropna().iloc[-1])
        if not np.isnan(val):
            return val

    # Attempt 2: latest Nifty 50 intraday tick
    df = _safe_fetch("^NSEI", period="1d", interval="1m")
    if not df.empty:
        val = float(df["Close"].dropna().iloc[-1])
        if not np.isnan(val):
            return val

    # Attempt 3: latest Nifty daily close (same-day or most recent)
    df = _safe_fetch("^NSEI", period="5d")
    if not df.empty:
        val = float(df["Close"].dropna().iloc[-1])
        if not np.isnan(val):
            return val

    return None


# ---------- 1. Gap prediction ----------

def predict_gap() -> dict[str, Any]:
    """
    Compare GIFT Nifty (or proxy) to previous Nifty close.
    Returns gap direction, magnitude, and confidence.
    """
    prev_close = _previous_nifty_close()
    gift_price = _gift_nifty_price()

    # Fallback: use S&P 500 overnight change as proxy
    if gift_price is None or prev_close is None:
        sp = _safe_fetch("^GSPC", period="5d")
        if sp.empty or prev_close is None:
            return {"direction": "FLAT", "magnitude_pct": 0.0,
                    "confidence": 0.2, "source": "unavailable"}

        sp_change = (float(sp["Close"].iloc[-1]) / float(sp["Close"].iloc[-2]) - 1) * 100
        # Indian market correlates ~0.4-0.6 with S&P overnight
        estimated_gap = sp_change * 0.5
        direction = "UP" if estimated_gap > GAP_THRESHOLD_PCT else (
            "DOWN" if estimated_gap < -GAP_THRESHOLD_PCT else "FLAT")
        return {"direction": direction, "magnitude_pct": round(estimated_gap, 2),
                "confidence": 0.45, "source": "sp500_proxy"}

    gap_pct = (gift_price / prev_close - 1) * 100

    if gap_pct > GAP_THRESHOLD_PCT:
        direction = "UP"
        confidence = min(0.75 + (gap_pct - GAP_THRESHOLD_PCT) * 0.05, 0.92)
    elif gap_pct < -GAP_THRESHOLD_PCT:
        direction = "DOWN"
        confidence = min(0.75 + (abs(gap_pct) - GAP_THRESHOLD_PCT) * 0.05, 0.92)
    else:
        direction = "FLAT"
        confidence = 0.6

    return {"direction": direction, "magnitude_pct": round(gap_pct, 2),
            "confidence": round(confidence, 2), "source": "gift_nifty"}


# ---------- 2. FII flow signal ----------

def get_fii_signal() -> dict[str, Any]:
    """
    Analyze FII net flow trend from recent data.
    Uses yfinance as proxy: when FIIs sell heavily, Nifty tends to
    underperform vs global peers. We approximate via volume + price action.

    For production: integrate nsepython or NSDL bulk data.
    """
    df = _safe_fetch("^NSEI", period="1mo")
    if df.empty or len(df) < 5:
        return {"direction": "NEUTRAL", "fii_3d_net": 0.0,
                "fii_5d_net": 0.0, "streak_days": 0, "source": "unavailable"}

    # Proxy: daily returns as sentiment indicator
    # Negative returns with high volume suggest institutional selling
    df = df.copy()
    df["return"] = df["Close"].pct_change()
    df["vol_z"] = (df["Volume"] - df["Volume"].rolling(20, min_periods=5).mean()) / \
                   df["Volume"].rolling(20, min_periods=5).std().replace(0, 1)

    # FII proxy: big down days with above-avg volume = FII selling
    df["fii_proxy"] = np.where(
        (df["return"] < -0.003) & (df["vol_z"] > 0.3), -1,
        np.where((df["return"] > 0.003) & (df["vol_z"] > 0.3), 1, 0)
    )

    recent_3d = float(df["fii_proxy"].iloc[-3:].sum())
    recent_5d = float(df["fii_proxy"].iloc[-5:].sum())

    # Count consecutive sell days (proxy)
    streak = 0
    for val in reversed(df["fii_proxy"].values):
        if val == -1:
            streak += 1
        else:
            break

    if recent_3d <= -2 or streak >= FII_STREAK_BEARISH:
        direction = "BEARISH"
    elif streak >= FII_REVERSAL_DAYS and recent_3d > 0:
        direction = "BULLISH"  # reversal after long sell streak
    elif recent_3d >= 2:
        direction = "BULLISH"
    else:
        direction = "NEUTRAL"

    return {"direction": direction, "fii_3d_net": recent_3d,
            "fii_5d_net": recent_5d, "streak_days": streak,
            "source": "volume_price_proxy"}


# ---------- 3. Global overnight sentiment ----------

def get_global_sentiment() -> dict[str, Any]:
    """
    Check S&P 500 (prev close), Hang Seng, and Nikkei for overnight direction.
    """
    results: dict[str, float | None] = {}

    for name, ticker in [("sp500", "^GSPC"), ("hangseng", "^HSI"), ("nikkei", "^N225")]:
        df = _safe_fetch(ticker, period="5d")
        if df.empty or len(df) < 2:
            results[name] = None
            continue
        change = (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-2]) - 1) * 100
        results[name] = round(change, 2)

    sp = results.get("sp500")
    asia_vals = [v for v in [results.get("hangseng"), results.get("nikkei")] if v is not None]
    asia_avg = round(np.mean(asia_vals), 2) if asia_vals else None

    # Strong bearish: both US + Asia down > 1%
    if sp is not None and asia_avg is not None:
        if sp < GLOBAL_DROP_PCT and asia_avg < GLOBAL_DROP_PCT:
            direction = "BEARISH"
        elif sp > 0.5 and (asia_avg is None or asia_avg > -0.3):
            direction = "BULLISH"
        else:
            direction = "NEUTRAL"
    elif sp is not None:
        direction = "BEARISH" if sp < GLOBAL_DROP_PCT else (
            "BULLISH" if sp > 0.5 else "NEUTRAL")
    else:
        direction = "NEUTRAL"

    return {"direction": direction,
            "sp500_change": sp,
            "asia_change": asia_avg,
            "details": results}


# ---------- 4. Combined pre-market intelligence ----------

def get_premarket_intel() -> dict[str, Any]:
    """
    Master function: fetches all signals and returns combined premarket dict.

    Returns:
        {
            "timestamp": str,
            "gap_prediction": {...},
            "fii_signal": {...},
            "global_sentiment": {...},
            "overall": {
                "bias": "BULLISH"/"BEARISH"/"NEUTRAL",
                "size_multiplier": 0.3-1.0,
                "reasons": [str]
            }
        }
    """
    gap = predict_gap()
    fii = get_fii_signal()
    glb = get_global_sentiment()

    # Score: +1 bullish, -1 bearish per signal
    score = 0
    reasons: list[str] = []

    # Gap signal
    if gap["direction"] == "UP":
        score += 1
        reasons.append(f"Gap-up {gap['magnitude_pct']:+.1f}% ({gap['source']})")
    elif gap["direction"] == "DOWN":
        score -= 1
        reasons.append(f"Gap-down {gap['magnitude_pct']:+.1f}% ({gap['source']})")

    # FII signal
    if fii["direction"] == "BULLISH":
        score += 1
        reasons.append(f"FII turning bullish (3d net: {fii['fii_3d_net']:+.0f})")
    elif fii["direction"] == "BEARISH":
        score -= 1
        reasons.append(f"FII bearish (streak: {fii['streak_days']}d)")

    # Global signal
    if glb["direction"] == "BULLISH":
        score += 1
        reasons.append(f"Global bullish (S&P {glb['sp500_change']:+.1f}%)")
    elif glb["direction"] == "BEARISH":
        score -= 1
        reasons.append(f"Global bearish (S&P {glb['sp500_change']:+.1f}%, Asia {glb['asia_change']:+.1f}%)")

    # Determine overall bias and position size multiplier
    if score >= 2:
        bias, multiplier = "BULLISH", 1.0
    elif score == 1:
        bias, multiplier = "BULLISH", 0.8
    elif score == 0:
        bias, multiplier = "NEUTRAL", 0.6
    elif score == -1:
        bias, multiplier = "BEARISH", 0.5
    else:
        bias, multiplier = "BEARISH", 0.3

    if not reasons:
        reasons.append("No strong signals — default neutral")

    return {
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
        "gap_prediction": gap,
        "fii_signal": fii,
        "global_sentiment": glb,
        "overall": {
            "bias": bias,
            "score": score,
            "size_multiplier": multiplier,
            "reasons": reasons,
        },
    }


# ---------- CLI ----------

def _print_intel(intel: dict) -> None:
    """Pretty-print premarket intelligence to terminal."""
    print(f"\n{'='*60}")
    print(f"  TradePilot v5 — Pre-Market Intelligence")
    print(f"  {intel['timestamp']}")
    print(f"{'='*60}\n")

    # Gap
    g = intel["gap_prediction"]
    arrow = {"UP": "^", "DOWN": "v", "FLAT": "-"}.get(g["direction"], "?")
    print(f"  [{arrow}] GAP: {g['direction']}  {g['magnitude_pct']:+.2f}%"
          f"  (conf: {g['confidence']:.0%}, src: {g['source']})")

    # FII
    f = intel["fii_signal"]
    print(f"  [{'$' if f['direction']=='BULLISH' else 'x' if f['direction']=='BEARISH' else '~'}]"
          f" FII: {f['direction']}  3d={f['fii_3d_net']:+.0f}  5d={f['fii_5d_net']:+.0f}"
          f"  streak={f['streak_days']}d  ({f['source']})")

    # Global
    s = intel["global_sentiment"]
    sp_str = f"{s['sp500_change']:+.1f}%" if s['sp500_change'] is not None else "N/A"
    asia_str = f"{s['asia_change']:+.1f}%" if s['asia_change'] is not None else "N/A"
    print(f"  [{'G' if s['direction']=='BULLISH' else 'R' if s['direction']=='BEARISH' else '~'}]"
          f" GLOBAL: {s['direction']}  S&P={sp_str}  Asia={asia_str}")

    # Overall
    o = intel["overall"]
    bar = "#" * int(o["size_multiplier"] * 20)
    print(f"\n  OVERALL: {o['bias']}  (score={o['score']:+d},"
          f" size={o['size_multiplier']:.1f}x)")
    print(f"  Size: [{bar:<20}]")
    for r in o["reasons"]:
        print(f"    - {r}")
    print()


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    intel = get_premarket_intel()
    _print_intel(intel)
