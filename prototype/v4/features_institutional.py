"""
TradePilot v4 — Institutional Feature Engineering
===================================================
Compute institutional-flow features:
  - FII/DII net flow score
  - Options OI buildup classification
"""

import numpy as np


# ---------------------------------------------------------------------------
# FII / DII Flow Score
# ---------------------------------------------------------------------------

def compute_fii_dii_score(fii_dii_data: dict) -> float:
    """
    Convert FII/DII flow data to a -1 to +1 score.

    Args:
        fii_dii_data: dict with keys ``fii_net`` and ``dii_net`` (in crores).

    Logic:
        - Both buying:  base +1.0 (strong bullish)
        - FII buying, DII selling: +0.3 (moderate bullish, FII leads)
        - DII buying, FII selling: +0.1 (weak bullish, DII defensive)
        - Both selling: -1.0 (bearish)
        - Magnitude scaling: larger flows amplify the base score.

    Returns:
        float between -1 and +1.
    """
    if fii_dii_data is None:
        return 0.0

    fii_net = fii_dii_data.get("fii_net", 0.0)
    dii_net = fii_dii_data.get("dii_net", 0.0)

    if fii_net is None:
        fii_net = 0.0
    if dii_net is None:
        dii_net = 0.0

    fii_buying = fii_net > 0
    dii_buying = dii_net > 0

    # Base directional score
    if fii_buying and dii_buying:
        base = 1.0
    elif fii_buying and not dii_buying:
        base = 0.3
    elif not fii_buying and dii_buying:
        base = 0.1
    else:
        # Both selling
        base = -1.0

    # Magnitude multiplier: scale by combined absolute flow.
    # Use a soft-clamp: 1000 crore combined = full magnitude (1.0).
    combined = abs(fii_net) + abs(dii_net)
    # Normalise: 500 Cr → 0.5x, 1000 Cr → ~0.76x, 2000 Cr → ~0.95x (tanh curve)
    magnitude = float(np.tanh(combined / 1500.0))
    # Ensure minimum magnitude of 0.2 so even small flows register
    magnitude = max(magnitude, 0.2)

    score = base * magnitude
    return round(float(np.clip(score, -1.0, 1.0)), 4)


# ---------------------------------------------------------------------------
# OI Buildup Classification
# ---------------------------------------------------------------------------

def compute_oi_buildup(options_data: dict, price_change_pct: float) -> dict:
    """
    Classify options OI buildup pattern.

    Args:
        options_data: dict with keys:
            - pcr: float (put-call ratio)
            - total_ce_oi: float (total call OI)
            - total_pe_oi: float (total put OI)
            - ce_oi_change: float (change in call OI)
            - pe_oi_change: float (change in put OI)
        price_change_pct: today's stock price change %.

    Returns:
        dict with keys: oi_sentiment, oi_score, pcr, pcr_signal

    Buildup logic:
        Price UP + OI UP   = long buildup   (+1.0)
        Price UP + OI DOWN = short covering  (+0.3)
        Price DOWN + OI UP = short buildup   (-1.0)
        Price DOWN + OI DOWN = long unwinding (-0.3)
    """
    defaults = {
        "oi_sentiment": "neutral",
        "oi_score": 0.0,
        "pcr": 1.0,
        "pcr_signal": "neutral",
    }

    if options_data is None:
        return defaults

    if price_change_pct is None:
        price_change_pct = 0.0

    pcr = options_data.get("pcr", None)
    ce_oi_change = options_data.get("ce_oi_change", 0.0)
    pe_oi_change = options_data.get("pe_oi_change", 0.0)

    if ce_oi_change is None:
        ce_oi_change = 0.0
    if pe_oi_change is None:
        pe_oi_change = 0.0

    # Net OI change (positive = new positions added, negative = unwinding)
    net_oi_change = ce_oi_change + pe_oi_change
    price_up = price_change_pct > 0.05  # small threshold to avoid noise
    oi_up = net_oi_change > 0

    if price_up and oi_up:
        oi_sentiment = "long_buildup"
        oi_score = 1.0
    elif price_up and not oi_up:
        oi_sentiment = "short_covering"
        oi_score = 0.3
    elif not price_up and oi_up:
        oi_sentiment = "short_buildup"
        oi_score = -1.0
    else:
        oi_sentiment = "long_unwinding"
        oi_score = -0.3

    # Handle flat / near-zero price change as neutral
    if abs(price_change_pct) < 0.05 and abs(net_oi_change) < 100:
        oi_sentiment = "neutral"
        oi_score = 0.0

    # --- PCR signal ---
    if pcr is None or pcr == 0:
        # Try to compute from raw OI
        total_ce = options_data.get("total_ce_oi", 0)
        total_pe = options_data.get("total_pe_oi", 0)
        if total_ce and total_ce > 0:
            pcr = (total_pe or 0) / total_ce
        else:
            pcr = 1.0

    if pcr > 1.2:
        pcr_signal = "bullish"
    elif pcr < 0.7:
        pcr_signal = "bearish"
    else:
        pcr_signal = "neutral"

    return {
        "oi_sentiment": oi_sentiment,
        "oi_score": round(float(oi_score), 4),
        "pcr": round(float(pcr), 4),
        "pcr_signal": pcr_signal,
    }


# ---------------------------------------------------------------------------
# Convenience: all institutional features
# ---------------------------------------------------------------------------

def compute_all_institutional_features(
    fii_dii_data: dict,
    options_data: dict,
    price_change_pct: float,
) -> dict:
    """
    Compute all institutional features.

    Args:
        fii_dii_data:     dict with fii_net, dii_net (in crores).
        options_data:     dict with pcr, OI fields.
        price_change_pct: today's stock price change %.

    Returns:
        Flat dict merging FII/DII score and OI buildup features.
    """
    features: dict = {}

    features["fii_dii_score"] = compute_fii_dii_score(fii_dii_data)
    features.update(compute_oi_buildup(options_data, price_change_pct))

    return features
