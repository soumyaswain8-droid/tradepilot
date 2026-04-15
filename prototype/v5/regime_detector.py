"""
TradePilot v5 — Market Regime Detector
=======================================
Classifies the market as BULL / BEAR / SIDEWAYS using a 6-indicator
scoring system + optional HMM (hmmlearn). Built after v4 lost Rs 30,816
on 2026-04-09 by going long on a bear day.

Indicators (each votes +1 bull, 0 neutral, -1 bear):
  1. Nifty vs 50-DMA
  2. Nifty vs 200-DMA
  3. India VIX level
  4. Advance/Decline ratio (% of Nifty 50 green)
  5. FII 5-day net flow direction
  6. Nifty 5-day momentum

Usage:
    from prototype.v5.regime_detector import detect_regime
    regime = detect_regime()

CLI:
    python3 -m prototype.v5.regime_detector
"""

import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_NIFTY_CSV = _DATA_DIR / "^NSEI.csv"
_VIX_CSV = _DATA_DIR / "^INDIAVIX.csv"

# ---------------------------------------------------------------------------
# HMM (optional)
# ---------------------------------------------------------------------------
try:
    from hmmlearn.hmm import GaussianHMM
    _HAS_HMM = True
except ImportError:
    _HAS_HMM = False


# ===================================================================
# Indicator scoring
# ===================================================================

def _load_csv(path: Path, days: int = 300) -> pd.DataFrame:
    """Load a yfinance-format CSV, return last N rows with clean Close."""
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    # Use Adj Close if available, fallback to Close
    if "Adj Close" in df.columns:
        df["Close"] = df["Adj Close"].combine_first(df["Close"])
    df = df.dropna(subset=["Close"])
    return df.tail(days).reset_index(drop=True)


def _score_dma(nifty_df: pd.DataFrame, window: int) -> tuple[float, int]:
    """Score Nifty vs N-day moving average. Returns (dma_value, vote)."""
    if len(nifty_df) < window:
        return (np.nan, 0)
    dma = nifty_df["Close"].rolling(window).mean().iloc[-1]
    last_close = nifty_df["Close"].iloc[-1]
    pct_above = (last_close - dma) / dma * 100
    if pct_above > 1.0:
        return (round(dma, 1), +1)
    elif pct_above < -1.0:
        return (round(dma, 1), -1)
    else:
        return (round(dma, 1), 0)


def _score_vix(vix_df: pd.DataFrame) -> tuple[float, int]:
    """Score India VIX level. <15 = calm/bull, 15-20 = neutral, >20 = fear/bear."""
    if vix_df.empty:
        return (np.nan, 0)
    vix = vix_df["Close"].iloc[-1]
    if np.isnan(vix):
        return (np.nan, 0)
    if vix < 15:
        return (round(vix, 2), +1)
    elif vix > 20:
        return (round(vix, 2), -1)
    else:
        return (round(vix, 2), 0)


def _score_advance_decline(nifty50_changes: Optional[pd.Series]) -> tuple[float, int]:
    """Score based on % of Nifty 50 stocks green today.
    >60% green = bull, <40% = bear, else neutral.
    If no per-stock data, try to estimate from Nifty intraday range."""
    if nifty50_changes is None or nifty50_changes.empty:
        return (np.nan, 0)
    pct_green = (nifty50_changes > 0).mean() * 100
    if pct_green > 60:
        vote = +1
    elif pct_green < 40:
        vote = -1
    else:
        vote = 0
    return (round(pct_green, 1), vote)


def _score_fii_flow(fii_data: Optional[dict]) -> tuple[float, int]:
    """Score FII 5-day net flow. Positive = bull, negative = bear.
    fii_data should have 'net_5d' key in crores."""
    if fii_data is None or "net_5d" not in fii_data:
        return (np.nan, 0)
    net = fii_data["net_5d"]
    if net > 500:       # Rs 500 Cr+ net buying over 5 days
        return (round(net, 0), +1)
    elif net < -500:
        return (round(net, 0), -1)
    else:
        return (round(net, 0), 0)


def _score_momentum(nifty_df: pd.DataFrame, days: int = 5) -> tuple[float, int]:
    """Score Nifty 5-day momentum. >1% up = bull, >1% down = bear."""
    if len(nifty_df) < days + 1:
        return (np.nan, 0)
    current = nifty_df["Close"].iloc[-1]
    past = nifty_df["Close"].iloc[-(days + 1)]
    pct = (current - past) / past * 100
    if pct > 1.0:
        return (round(pct, 2), +1)
    elif pct < -1.0:
        return (round(pct, 2), -1)
    else:
        return (round(pct, 2), 0)


# ===================================================================
# Nifty 50 stock data for advance/decline
# ===================================================================

def _fetch_nifty50_changes() -> Optional[pd.Series]:
    """Fetch today's % change for Nifty 50 stocks via yfinance."""
    try:
        import yfinance as yf
        from ..v4.config import ACTIVE_SYMBOLS_YF
        # Get last 2 days to compute today's change
        data = yf.download(ACTIVE_SYMBOLS_YF, period="5d", progress=False, threads=True)
        if data.empty:
            return None
        closes = data["Close"] if "Close" in data.columns else data["Adj Close"]
        if closes.ndim == 1:
            return None
        changes = closes.pct_change().iloc[-1] * 100
        return changes.dropna()
    except Exception:
        return None


def _estimate_ad_from_nifty(nifty_df: pd.DataFrame) -> Optional[pd.Series]:
    """Rough proxy: if Nifty is up, assume ~60% stocks green; if down, ~40%.
    Returns a fake Series for scoring when live stock data isn't available."""
    if len(nifty_df) < 2:
        return None
    today_chg = (nifty_df["Close"].iloc[-1] - nifty_df["Close"].iloc[-2]) / nifty_df["Close"].iloc[-2] * 100
    # Simulate 50 stock changes centered around Nifty's move
    rng = np.random.default_rng(42)
    changes = rng.normal(loc=today_chg, scale=1.5, size=50)
    return pd.Series(changes)


# ===================================================================
# HMM regime detection
# ===================================================================

def _hmm_regime(nifty_df: pd.DataFrame) -> Optional[dict]:
    """Train a 3-state Gaussian HMM on (daily returns, daily volatility).
    Returns dict with state label and probabilities, or None if unavailable."""
    if not _HAS_HMM or len(nifty_df) < 60:
        return None

    try:
        closes = nifty_df["Close"].values
        returns = np.diff(np.log(closes))
        # Rolling 10-day volatility
        vol = pd.Series(returns).rolling(10).std().values
        # Align: drop first 10 rows (NaN vol)
        valid = ~np.isnan(vol)
        returns = returns[valid]
        vol = vol[valid]
        if len(returns) < 50:
            return None

        X = np.column_stack([returns, vol])

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            model = GaussianHMM(
                n_components=3, covariance_type="full",
                n_iter=200, random_state=42, verbose=False
            )
            model.fit(X)
            states = model.predict(X)
            probs = model.predict_proba(X)

        # Map states to regimes by mean return
        state_means = {}
        for s in range(3):
            mask = states == s
            state_means[s] = returns[mask].mean() if mask.sum() > 0 else 0

        sorted_states = sorted(state_means, key=state_means.get)
        label_map = {sorted_states[0]: "BEAR", sorted_states[1]: "SIDEWAYS", sorted_states[2]: "BULL"}

        current_state = states[-1]
        current_probs = probs[-1]

        return {
            "regime": label_map[current_state],
            "state_id": int(current_state),
            "probabilities": {
                label_map[s]: round(float(current_probs[s]), 3) for s in range(3)
            },
            "state_means": {
                label_map[s]: round(float(state_means[s]) * 100, 4) for s in range(3)
            },
        }
    except Exception as e:
        return {"error": str(e)}


# ===================================================================
# Main detection functions
# ===================================================================

def detect_regime_from_data(
    nifty_df: pd.DataFrame,
    vix_df: pd.DataFrame,
    fii_data: Optional[dict] = None,
    nifty50_changes: Optional[pd.Series] = None,
) -> dict:
    """Detect market regime from provided DataFrames (for backtesting).

    Args:
        nifty_df: DataFrame with Date, Close columns (sorted by date)
        vix_df: DataFrame with Date, Close columns
        fii_data: Optional dict with 'net_5d' key (Rs Crores)
        nifty50_changes: Optional Series of per-stock % changes

    Returns:
        dict with regime, score, indicators, allocation, confidence
    """
    indicators = {}

    # 1. Nifty vs 50-DMA
    val, vote = _score_dma(nifty_df, 50)
    indicators["nifty_vs_50dma"] = {"value": val, "vote": vote, "label": "Nifty vs 50-DMA"}

    # 2. Nifty vs 200-DMA
    val, vote = _score_dma(nifty_df, 200)
    indicators["nifty_vs_200dma"] = {"value": val, "vote": vote, "label": "Nifty vs 200-DMA"}

    # 3. India VIX
    val, vote = _score_vix(vix_df)
    indicators["india_vix"] = {"value": val, "vote": vote, "label": "India VIX"}

    # 4. Advance/Decline
    ad_data = nifty50_changes if nifty50_changes is not None else _estimate_ad_from_nifty(nifty_df)
    val, vote = _score_advance_decline(ad_data)
    indicators["advance_decline"] = {"value": val, "vote": vote, "label": "Advance/Decline %"}

    # 5. FII flow
    val, vote = _score_fii_flow(fii_data)
    indicators["fii_flow_5d"] = {"value": val, "vote": vote, "label": "FII 5-day Net Flow"}

    # 6. Nifty 5-day momentum
    val, vote = _score_momentum(nifty_df, 5)
    indicators["momentum_5d"] = {"value": val, "vote": vote, "label": "5-Day Momentum %"}

    # Aggregate score (only count indicators that voted)
    votes = [ind["vote"] for ind in indicators.values() if not np.isnan(ind.get("value", np.nan) or np.nan)]
    # Handle NaN values — treat as 0
    clean_votes = []
    for ind in indicators.values():
        v = ind.get("value")
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            clean_votes.append(ind["vote"])
    score = sum(clean_votes)
    max_possible = len(clean_votes) if clean_votes else 1

    # Regime classification
    if score >= 3:
        regime = "BULL"
    elif score <= -3:
        regime = "BEAR"
    else:
        regime = "SIDEWAYS"

    # Allocation multiplier
    alloc_map = {"BULL": 1.0, "SIDEWAYS": 0.75, "BEAR": 0.30}
    allocation = alloc_map[regime]

    # Confidence: how unanimous are the votes (0 to 1)
    confidence = round(abs(score) / max(max_possible, 1), 2)
    confidence = min(confidence, 1.0)

    # HMM overlay
    hmm_result = _hmm_regime(nifty_df)

    result = {
        "regime": regime,
        "score": score,
        "max_score": max_possible,
        "indicators": indicators,
        "allocation": allocation,
        "confidence": confidence,
        "timestamp": datetime.now().isoformat(),
        "nifty_close": round(float(nifty_df["Close"].iloc[-1]), 2),
    }
    if hmm_result:
        result["hmm"] = hmm_result

    return result


def detect_regime() -> dict:
    """Detect current market regime using local CSV data + live yfinance.

    Returns:
        dict with regime, score, indicators, allocation, confidence
    """
    # Load Nifty data (need 250 days for 200-DMA)
    nifty_df = _load_csv(_NIFTY_CSV, days=300)

    # Load VIX data
    vix_df = _load_csv(_VIX_CSV, days=30)

    # Try to refresh with live data
    try:
        import yfinance as yf
        live = yf.download("^NSEI", period="1d", progress=False)
        if not live.empty and live["Close"].iloc[-1] is not None:
            last_date = nifty_df["Date"].iloc[-1]
            live_date = live.index[-1]
            if pd.Timestamp(live_date).date() > pd.Timestamp(last_date).date():
                new_row = pd.DataFrame({
                    "Date": [live_date],
                    "Close": [float(live["Close"].iloc[-1])],
                })
                nifty_df = pd.concat([nifty_df, new_row], ignore_index=True)
    except Exception:
        pass

    # Try fetching Nifty 50 stock changes for advance/decline
    nifty50_changes = _fetch_nifty50_changes()

    # FII data: real feed from nsepython / NSE API / cache
    fii_data = None
    try:
        from .fii_feed import compute_fii_signal
        fii_signal = compute_fii_signal()
        fii_data = {"net_5d": fii_signal["fii_5d_net"]}
    except Exception:
        pass

    return detect_regime_from_data(nifty_df, vix_df, fii_data, nifty50_changes)


# ===================================================================
# CLI
# ===================================================================

def _print_regime(result: dict) -> None:
    """Pretty-print regime detection result."""
    regime = result["regime"]
    score = result["score"]
    alloc = result["allocation"]
    conf = result["confidence"]

    color = {"BULL": "\033[92m", "BEAR": "\033[91m", "SIDEWAYS": "\033[93m"}
    reset = "\033[0m"
    c = color.get(regime, "")

    print(f"\n{'='*60}")
    print(f"  TradePilot v5 — Market Regime Detector")
    print(f"  {result.get('timestamp', '')[:19]}")
    print(f"{'='*60}")
    print(f"  Nifty Close:   {result.get('nifty_close', 'N/A')}")
    print(f"  Regime:        {c}{regime}{reset}  (score: {score}/{result.get('max_score', 6)})")
    print(f"  Allocation:    {alloc:.0%}")
    print(f"  Confidence:    {conf:.0%}")
    print(f"{'-'*60}")
    print(f"  {'Indicator':<25} {'Value':>10} {'Vote':>6}")
    print(f"  {'-'*43}")
    for key, ind in result.get("indicators", {}).items():
        val = ind["value"]
        vote = ind["vote"]
        vote_str = {1: " +1", -1: " -1", 0: "  0"}.get(vote, "  ?")
        val_str = f"{val}" if val is not None and not (isinstance(val, float) and np.isnan(val)) else "N/A"
        print(f"  {ind['label']:<25} {val_str:>10} {vote_str:>6}")

    if "hmm" in result and "regime" in result["hmm"]:
        hmm = result["hmm"]
        print(f"\n  HMM overlay:   {hmm['regime']}")
        if "probabilities" in hmm:
            probs = hmm["probabilities"]
            print(f"  Probabilities: BULL={probs.get('BULL',0):.1%}  "
                  f"SIDEWAYS={probs.get('SIDEWAYS',0):.1%}  "
                  f"BEAR={probs.get('BEAR',0):.1%}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    result = detect_regime()
    _print_regime(result)
