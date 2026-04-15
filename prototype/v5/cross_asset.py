"""
TradePilot v5 -- Cross-Asset Signal Features
==============================================
Fetches global market data (DXY, US 10Y, crude, gold, BTC, S&P 500)
and computes features that predict Indian market (Nifty) direction.

Cross-asset correlations with Nifty (from research):
  - DXY drop        -> FII inflows   -> Nifty up    (inverse)
  - US 10Y yield up -> capital to US  -> Nifty down  (inverse)
  - Crude oil up    -> import bill up -> Nifty down  (inverse, except energy)
  - Gold up + equity down = risk-off signal
  - BTC leads Nifty by 1-2 days (Granger causality, same direction)
  - S&P 500 strong positive correlation (US up overnight -> India opens up)

Usage:
    from prototype.v5.cross_asset import compute_cross_asset_features, get_cross_asset_signal
    features = compute_cross_asset_features()
    signal   = get_cross_asset_signal()

CLI:
    python3 -m prototype.v5.cross_asset
"""

import logging
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Optional

logger = logging.getLogger("tradepilot.v5.cross_asset")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# yfinance (lazy import -- graceful failure)
# ---------------------------------------------------------------------------
try:
    import yfinance as yf
except ImportError:
    yf = None
    logger.warning("yfinance not installed. pip install yfinance")

# ---------------------------------------------------------------------------
# Tickers & metadata
# ---------------------------------------------------------------------------
CROSS_ASSETS = {
    "dxy":   {"ticker": "DX-Y.NYB", "label": "US Dollar Index",  "corr": "inverse"},
    "us10y": {"ticker": "^TNX",     "label": "US 10Y Yield",     "corr": "inverse"},
    "crude": {"ticker": "BZ=F",     "label": "Brent Crude",      "corr": "inverse"},
    "gold":  {"ticker": "GC=F",     "label": "Gold Futures",     "corr": "risk-off"},
    "btc":   {"ticker": "BTC-USD",  "label": "Bitcoin",          "corr": "positive"},
    "sp500": {"ticker": "^GSPC",    "label": "S&P 500",          "corr": "positive"},
}

# ---------------------------------------------------------------------------
# Cache (1-hour TTL)
# ---------------------------------------------------------------------------
_cache: Dict[str, dict] = {}
_cache_ts: float = 0.0
CACHE_TTL_SEC = 3600  # 1 hour


def _cache_valid() -> bool:
    return bool(_cache) and (time.time() - _cache_ts < CACHE_TTL_SEC)


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------
def get_cross_asset_data() -> dict:
    """
    Fetch latest data for all cross-asset indicators via yfinance.

    Returns dict keyed by asset name, each containing:
        - close: latest close price
        - prev_close: previous day close
        - change_pct: 1-day % change
        - label: human-readable name
    """
    global _cache, _cache_ts

    if _cache_valid():
        logger.debug("Returning cached cross-asset data")
        return _cache

    if yf is None:
        logger.error("yfinance not available -- cannot fetch cross-asset data")
        return {}

    result = {}
    # Fetch 5 trading days to ensure we get at least 2 valid rows
    end = datetime.now()
    start = end - timedelta(days=10)

    tickers_str = " ".join(v["ticker"] for v in CROSS_ASSETS.values())
    try:
        data = yf.download(
            tickers_str,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            progress=False,
            threads=True,
        )
    except Exception as e:
        logger.error(f"yfinance bulk download failed: {e}")
        data = None

    for name, meta in CROSS_ASSETS.items():
        ticker = meta["ticker"]
        try:
            if data is not None and not data.empty:
                # yfinance multi-ticker returns MultiIndex columns
                if isinstance(data.columns, __import__("pandas").MultiIndex):
                    closes = data["Close"][ticker].dropna()
                else:
                    closes = data["Close"].dropna()
            else:
                closes = None

            # Fallback: individual fetch if bulk missed this ticker
            if closes is None or len(closes) < 2:
                t = yf.Ticker(ticker)
                hist = t.history(period="5d")
                if hist.empty:
                    logger.warning(f"No data for {name} ({ticker})")
                    result[name] = _empty_entry(meta["label"])
                    continue
                closes = hist["Close"].dropna()

            if len(closes) < 2:
                result[name] = _empty_entry(meta["label"])
                continue

            close = float(closes.iloc[-1])
            prev = float(closes.iloc[-2])
            pct = ((close - prev) / prev) * 100 if prev != 0 else 0.0

            result[name] = {
                "close": round(close, 4),
                "prev_close": round(prev, 4),
                "change_pct": round(pct, 4),
                "label": meta["label"],
            }
        except Exception as e:
            logger.warning(f"Failed to fetch {name} ({ticker}): {e}")
            result[name] = _empty_entry(meta["label"])

    _cache = result
    _cache_ts = time.time()
    return result


def _empty_entry(label: str) -> dict:
    return {"close": None, "prev_close": None, "change_pct": 0.0, "label": label}


# ---------------------------------------------------------------------------
# Feature computation
# ---------------------------------------------------------------------------
def compute_cross_asset_features() -> dict:
    """
    Compute ML features from cross-asset data.

    All features use yesterday's data (lagged 1 day) to avoid look-ahead bias.
    The yfinance "latest close" IS yesterday's close for most global assets
    since we fetch before US market close on the current day.

    Returns dict of float features ready for ML model input.
    """
    data = get_cross_asset_data()
    if not data:
        return _empty_features()

    def _pct(name: str) -> float:
        return data.get(name, {}).get("change_pct", 0.0)

    dxy_chg   = _pct("dxy")
    us10y_chg = _pct("us10y")
    crude_chg = _pct("crude")
    gold_chg  = _pct("gold")
    btc_chg   = _pct("btc")
    sp500_chg = _pct("sp500")

    # --- Composite: risk-off score ---
    # Gold up AND equities (S&P) down = risk-off environment (-1 to +1 scale)
    # +1 = strong risk-off, -1 = strong risk-on
    risk_off = 0.0
    if gold_chg > 0 and sp500_chg < 0:
        risk_off = min((gold_chg + abs(sp500_chg)) / 4.0, 1.0)
    elif gold_chg < 0 and sp500_chg > 0:
        risk_off = max(-(abs(gold_chg) + sp500_chg) / 4.0, -1.0)

    # --- Composite: FII flow predictor ---
    # DXY down + US yield down = capital likely flows to EMs (India)
    # Score from -1 (outflow) to +1 (inflow)
    fii_pred = 0.0
    dxy_signal   = -dxy_chg / 2.0     # DXY down -> positive for India
    yield_signal = -us10y_chg / 1.0    # yield down -> positive for India
    fii_pred = max(-1.0, min(1.0, (dxy_signal + yield_signal) / 2.0))

    return {
        "dxy_change_1d":      round(dxy_chg, 4),
        "us10y_change_1d":    round(us10y_chg, 4),
        "crude_change_1d":    round(crude_chg, 4),
        "gold_change_1d":     round(gold_chg, 4),
        "btc_change_1d":      round(btc_chg, 4),
        "sp500_change_1d":    round(sp500_chg, 4),
        "risk_off_score":     round(risk_off, 4),
        "fii_flow_predictor": round(fii_pred, 4),
    }


def _empty_features() -> dict:
    return {
        "dxy_change_1d": 0.0, "us10y_change_1d": 0.0, "crude_change_1d": 0.0,
        "gold_change_1d": 0.0, "btc_change_1d": 0.0, "sp500_change_1d": 0.0,
        "risk_off_score": 0.0, "fii_flow_predictor": 0.0,
    }


# ---------------------------------------------------------------------------
# High-level signal
# ---------------------------------------------------------------------------
def get_cross_asset_signal() -> dict:
    """
    Aggregate cross-asset features into a directional signal for Nifty.

    Scoring logic (each asset votes):
      - DXY down      -> +1 bullish (inverse)
      - US 10Y down   -> +1 bullish (inverse)
      - Crude down    -> +1 bullish (inverse)
      - Gold up alone -> 0 neutral; Gold up + equity down -> -1 bearish
      - BTC up        -> +1 bullish (leads Nifty)
      - S&P 500 up    -> +1 bullish (correlated)

    Returns:
        {"direction": "BULLISH"|"BEARISH"|"NEUTRAL",
         "confidence": 0.0-1.0,
         "score": int,
         "reasons": [str]}
    """
    features = compute_cross_asset_features()
    score = 0
    reasons = []

    # DXY (inverse)
    if features["dxy_change_1d"] < -0.1:
        score += 1
        reasons.append(f"DXY fell {features['dxy_change_1d']:.2f}% (FII inflow likely)")
    elif features["dxy_change_1d"] > 0.1:
        score -= 1
        reasons.append(f"DXY rose {features['dxy_change_1d']:.2f}% (FII outflow risk)")

    # US 10Y (inverse)
    if features["us10y_change_1d"] < -0.5:
        score += 1
        reasons.append(f"US 10Y yield fell {features['us10y_change_1d']:.2f}% (capital to EMs)")
    elif features["us10y_change_1d"] > 0.5:
        score -= 1
        reasons.append(f"US 10Y yield rose {features['us10y_change_1d']:.2f}% (capital to US)")

    # Crude (inverse for India)
    if features["crude_change_1d"] < -0.5:
        score += 1
        reasons.append(f"Crude fell {features['crude_change_1d']:.2f}% (lower import bill)")
    elif features["crude_change_1d"] > 0.5:
        score -= 1
        reasons.append(f"Crude rose {features['crude_change_1d']:.2f}% (higher import bill)")

    # Risk-off (gold + equity divergence)
    if features["risk_off_score"] > 0.3:
        score -= 1
        reasons.append(f"Risk-off signal: {features['risk_off_score']:.2f} (gold up, equity down)")
    elif features["risk_off_score"] < -0.3:
        score += 1
        reasons.append(f"Risk-on signal: {features['risk_off_score']:.2f} (gold down, equity up)")

    # BTC (leads Nifty 1-2 days)
    if features["btc_change_1d"] > 1.0:
        score += 1
        reasons.append(f"BTC up {features['btc_change_1d']:.2f}% (leads Nifty by 1-2 days)")
    elif features["btc_change_1d"] < -1.0:
        score -= 1
        reasons.append(f"BTC down {features['btc_change_1d']:.2f}% (leads Nifty by 1-2 days)")

    # S&P 500 (positive correlation)
    if features["sp500_change_1d"] > 0.3:
        score += 1
        reasons.append(f"S&P 500 up {features['sp500_change_1d']:.2f}% (positive for Nifty)")
    elif features["sp500_change_1d"] < -0.3:
        score -= 1
        reasons.append(f"S&P 500 down {features['sp500_change_1d']:.2f}% (negative for Nifty)")

    # Determine direction and confidence
    max_score = 6  # 6 possible votes
    confidence = min(abs(score) / max_score, 1.0)

    if score >= 2:
        direction = "BULLISH"
    elif score <= -2:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    if not reasons:
        reasons.append("No significant cross-asset moves detected")

    return {
        "direction": direction,
        "confidence": round(confidence, 2),
        "score": score,
        "reasons": reasons,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_report():
    """Pretty-print cross-asset signals for CLI usage."""
    print("\n" + "=" * 60)
    print("  TradePilot v5 -- Cross-Asset Signal Report")
    print("=" * 60)

    data = get_cross_asset_data()
    if not data:
        print("\n  [ERROR] Could not fetch cross-asset data.\n")
        return

    print(f"\n  {'Asset':<20} {'Close':>10} {'Change':>10}")
    print("  " + "-" * 42)
    for name, info in data.items():
        close = f"{info['close']:.2f}" if info["close"] is not None else "N/A"
        chg = f"{info['change_pct']:+.2f}%" if info["change_pct"] else "N/A"
        print(f"  {info['label']:<20} {close:>10} {chg:>10}")

    features = compute_cross_asset_features()
    print(f"\n  {'Feature':<25} {'Value':>10}")
    print("  " + "-" * 37)
    for k, v in features.items():
        print(f"  {k:<25} {v:>10.4f}")

    signal = get_cross_asset_signal()
    print(f"\n  Signal: {signal['direction']}  "
          f"(confidence: {signal['confidence']:.0%}, score: {signal['score']:+d})")
    print("\n  Reasons:")
    for r in signal["reasons"]:
        print(f"    - {r}")
    print()


if __name__ == "__main__":
    _print_report()
