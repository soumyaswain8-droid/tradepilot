"""
TradePilot v5.3 — Staged Entry Engine
======================================
Instead of deploying 100% capital at 09:35 in one shot, v5.3 uses a
3-stage entry system that WAITS for confirmation before committing capital.

Conviction Tiers:
    Tier 1 (HIGH):   score>75 + BULL regime → 50% at open, +50% after ORB confirms
    Tier 2 (MEDIUM): score 60-75 → wait for ORB at 10:15, enter 100%
    Tier 3 (LOW):    score 50-60 → wait for midday rescore at 11:30
    Tier 4 (SKIP):   score<50 → don't enter

Key difference from v5:
    v5  → deploys everything at 09:35 with potentially stale prices
    v5.3 → deploys in stages with LIVE confirmed prices, cancels unconfirmed entries

Imports:
    - Regime from v5:  prototype.v5.regime_detector.detect_regime
    - Signals from v5: prototype.v5.signal_engine.generate_signals
    - ORB from v4:     prototype.v4.features_intraday.compute_orb
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("tradepilot.v5_3.staged_entry")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Lazy imports (avoid circular / missing deps)
# ---------------------------------------------------------------------------
_detect_regime = None
_generate_signals = None
_compute_orb = None
_score_all_stocks = None


def _lazy_import_regime():
    global _detect_regime
    if _detect_regime is None:
        try:
            from prototype.v5.regime_detector import detect_regime
            _detect_regime = detect_regime
        except ImportError:
            logger.warning("v5 regime_detector not available; defaulting to SIDEWAYS")
            _detect_regime = lambda: {"regime": "SIDEWAYS", "score": 0, "allocation": 0.75}
    return _detect_regime


def _lazy_import_signals():
    global _generate_signals
    if _generate_signals is None:
        try:
            from prototype.v5.signal_engine import generate_signals
            _generate_signals = generate_signals
        except ImportError:
            logger.warning("v5 signal_engine not available; using v4 scorer fallback")
            try:
                from prototype.v4.composite_scorer import score_all_stocks
                _generate_signals = lambda regime: score_all_stocks()
            except ImportError:
                logger.error("Neither v5 signal_engine nor v4 composite_scorer available")
                _generate_signals = lambda regime: []
    return _generate_signals


def _lazy_import_scorer():
    global _score_all_stocks
    if _score_all_stocks is None:
        try:
            from prototype.v4.composite_scorer import score_all_stocks
            _score_all_stocks = score_all_stocks
        except ImportError:
            logger.warning("v4 composite_scorer not available; rescore disabled")
            _score_all_stocks = lambda: []
    return _score_all_stocks


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Conviction tier thresholds
TIER1_MIN_SCORE = 75
TIER2_MIN_SCORE = 60
TIER3_MIN_SCORE = 50

# Stage timing (IST hours)
STAGE1_HOUR, STAGE1_MIN = 9, 35   # Initial deployment
STAGE2_HOUR, STAGE2_MIN = 10, 15  # ORB confirmation
STAGE3_HOUR, STAGE3_MIN = 11, 30  # Midday rescore

# Confirmation parameters
ORB_CONFIRM_BUFFER_PCT = 0.001  # Price must exceed ORB high/low by this much
VOLUME_MULTIPLIER_THRESHOLD = 0.8  # Volume must exceed 0.8x avg for Tier 2 (lowered from 1.2 — was blocking all signals Apr 13)
RESCORE_IMPROVEMENT_MIN = 5  # New score must be at least 5 points higher for Tier 3
MAX_WAIT_MINUTES_DEFAULT = 45

# Position sizing
TIER1_INITIAL_PCT = 0.50
TIER1_CONFIRM_PCT = 0.50
TIER2_FULL_PCT = 1.00
TIER3_FULL_PCT = 1.00
MAX_POSITION_PCT = 0.15  # Max 15% of pool per stock


# ═══════════════════════════════════════════════════════════════════
# CONVICTION CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════

def classify_conviction(signal: dict, regime: str) -> dict:
    """
    Classify a signal into a conviction tier based on composite score + regime.

    Args:
        signal: Dict with at least 'score', 'direction', 'symbol'.
        regime: Market regime string ('BULL', 'BEAR', 'SIDEWAYS').

    Returns:
        Dict with tier info:
            tier (1-4), label, entry_stage, initial_pct, confirm_pct,
            confirm_condition, max_wait_minutes, original_score
    """
    score = signal.get("score", 0)
    direction = signal.get("direction", "HOLD")
    is_short = direction == "SELL"

    # --- Tier 1: HIGH conviction ---
    if score > TIER1_MIN_SCORE and not is_short:
        if regime == "BULL":
            return {
                "tier": 1,
                "label": "HIGH",
                "entry_stage": 1,
                "initial_pct": TIER1_INITIAL_PCT,
                "confirm_pct": TIER1_CONFIRM_PCT,
                "confirm_condition": "price_above_orb_high",
                "max_wait_minutes": MAX_WAIT_MINUTES_DEFAULT,
                "original_score": score,
            }
        # High score but not BULL regime → downgrade to Tier 2
        return {
            "tier": 2,
            "label": "MEDIUM",
            "entry_stage": 2,
            "initial_pct": 0.0,
            "confirm_pct": TIER2_FULL_PCT,
            "confirm_condition": "price_above_vwap_with_volume",
            "max_wait_minutes": MAX_WAIT_MINUTES_DEFAULT,
            "original_score": score,
        }

    # --- Shorts: always wait for ORB breakdown ---
    if is_short:
        if score > TIER2_MIN_SCORE and regime in ("BEAR", "SIDEWAYS"):
            return {
                "tier": 2,
                "label": "MEDIUM",
                "entry_stage": 2,
                "initial_pct": 0.0,
                "confirm_pct": TIER2_FULL_PCT,
                "confirm_condition": "price_below_orb_low",
                "max_wait_minutes": MAX_WAIT_MINUTES_DEFAULT,
                "original_score": score,
            }
        if score > TIER3_MIN_SCORE:
            return {
                "tier": 3,
                "label": "LOW",
                "entry_stage": 3,
                "initial_pct": 0.0,
                "confirm_pct": TIER3_FULL_PCT,
                "confirm_condition": "rescore_and_orb_breakdown",
                "max_wait_minutes": 120,
                "original_score": score,
            }
        return _skip_tier(score)

    # --- Tier 2: MEDIUM conviction (longs) ---
    if score >= TIER2_MIN_SCORE:
        return {
            "tier": 2,
            "label": "MEDIUM",
            "entry_stage": 2,
            "initial_pct": 0.0,
            "confirm_pct": TIER2_FULL_PCT,
            "confirm_condition": "price_above_vwap_with_volume",
            "max_wait_minutes": MAX_WAIT_MINUTES_DEFAULT,
            "original_score": score,
        }

    # --- Tier 3: LOW conviction ---
    if score >= TIER3_MIN_SCORE:
        return {
            "tier": 3,
            "label": "LOW",
            "entry_stage": 3,
            "initial_pct": 0.0,
            "confirm_pct": TIER3_FULL_PCT,
            "confirm_condition": "rescore_strengthened",
            "max_wait_minutes": 120,
            "original_score": score,
        }

    # --- Tier 4: SKIP ---
    return _skip_tier(score)


def _skip_tier(score: float) -> dict:
    return {
        "tier": 4,
        "label": "SKIP",
        "entry_stage": 0,
        "initial_pct": 0.0,
        "confirm_pct": 0.0,
        "confirm_condition": "none",
        "max_wait_minutes": 0,
        "original_score": score,
    }


# ═══════════════════════════════════════════════════════════════════
# CONFIRMATION CHECKS
# ═══════════════════════════════════════════════════════════════════

def check_confirmation(
    symbol: str,
    conviction: dict,
    current_price: float,
    orb_high: float,
    orb_low: float,
    vwap: float,
    volume_ratio: float = 1.0,
    new_score: Optional[float] = None,
) -> dict:
    """
    Check if the confirmation condition for this conviction tier is met.

    Args:
        symbol:        Stock symbol.
        conviction:    Dict from classify_conviction().
        current_price: Live price right now.
        orb_high:      First 15-min high (ORB).
        orb_low:       First 15-min low (ORB).
        vwap:          Current VWAP.
        volume_ratio:  Current volume / avg volume (default 1.0).
        new_score:     Re-scored value (for Tier 3 midday check).

    Returns:
        Dict: {confirmed: bool, reason: str, entry_price: float}
    """
    cond = conviction.get("confirm_condition", "none")
    tier = conviction.get("tier", 4)

    # Tier 1 LONG: price must break above ORB high
    if cond == "price_above_orb_high":
        threshold = orb_high * (1 + ORB_CONFIRM_BUFFER_PCT)
        if current_price > threshold:
            return {
                "confirmed": True,
                "reason": f"ORB breakout confirmed ({current_price:.2f} > {orb_high:.2f})",
                "entry_price": current_price,
            }
        return {
            "confirmed": False,
            "reason": f"Waiting for ORB breakout ({current_price:.2f} < {orb_high:.2f})",
            "entry_price": 0.0,
        }

    # Tier 2 LONG: price above VWAP + volume confirmation
    if cond == "price_above_vwap_with_volume":
        price_ok = current_price > vwap
        vol_ok = volume_ratio >= VOLUME_MULTIPLIER_THRESHOLD
        if price_ok and vol_ok:
            return {
                "confirmed": True,
                "reason": f"VWAP+Volume confirmed (px={current_price:.2f}>{vwap:.2f}, vol={volume_ratio:.1f}x)",
                "entry_price": current_price,
            }
        parts = []
        if not price_ok:
            parts.append(f"below VWAP ({current_price:.2f}<{vwap:.2f})")
        if not vol_ok:
            parts.append(f"low volume ({volume_ratio:.1f}x<{VOLUME_MULTIPLIER_THRESHOLD}x)")
        return {
            "confirmed": False,
            "reason": f"Waiting: {', '.join(parts)}",
            "entry_price": 0.0,
        }

    # SHORT: price must break below ORB low
    if cond == "price_below_orb_low":
        threshold = orb_low * (1 - ORB_CONFIRM_BUFFER_PCT)
        if current_price < threshold:
            return {
                "confirmed": True,
                "reason": f"ORB breakdown confirmed ({current_price:.2f} < {orb_low:.2f})",
                "entry_price": current_price,
            }
        return {
            "confirmed": False,
            "reason": f"Waiting for breakdown ({current_price:.2f} > {orb_low:.2f})",
            "entry_price": 0.0,
        }

    # Tier 3 LONG: midday rescore must show improvement
    if cond == "rescore_strengthened":
        orig = conviction.get("original_score", 0)
        if new_score is not None and new_score >= orig + RESCORE_IMPROVEMENT_MIN:
            return {
                "confirmed": True,
                "reason": f"Signal strengthened ({new_score:.0f} vs {orig:.0f}, +{new_score-orig:.0f})",
                "entry_price": current_price,
            }
        if new_score is not None:
            return {
                "confirmed": False,
                "reason": f"Signal weak ({new_score:.0f} vs {orig:.0f}, need +{RESCORE_IMPROVEMENT_MIN})",
                "entry_price": 0.0,
            }
        return {
            "confirmed": False,
            "reason": "Awaiting midday rescore",
            "entry_price": 0.0,
        }

    # Tier 3 SHORT: rescore + ORB breakdown
    if cond == "rescore_and_orb_breakdown":
        threshold = orb_low * (1 - ORB_CONFIRM_BUFFER_PCT)
        price_ok = current_price < threshold
        score_ok = (new_score is not None and
                    new_score >= conviction.get("original_score", 0) + RESCORE_IMPROVEMENT_MIN)
        if price_ok and score_ok:
            return {
                "confirmed": True,
                "reason": f"Breakdown+rescore confirmed (px={current_price:.2f}<{orb_low:.2f}, score+{new_score-conviction.get('original_score',0):.0f})",
                "entry_price": current_price,
            }
        parts = []
        if not price_ok:
            parts.append(f"no breakdown ({current_price:.2f}>{orb_low:.2f})")
        if not score_ok:
            parts.append("score not strengthened" if new_score is not None else "awaiting rescore")
        return {
            "confirmed": False,
            "reason": f"Waiting: {', '.join(parts)}",
            "entry_price": 0.0,
        }

    # Tier 4 / unknown: never confirm
    return {"confirmed": False, "reason": "SKIP tier", "entry_price": 0.0}


# ═══════════════════════════════════════════════════════════════════
# POSITION SIZING
# ═══════════════════════════════════════════════════════════════════

def calculate_staged_size(
    conviction: dict,
    pool_capital: float,
    stage: int,
    already_deployed: float = 0.0,
) -> float:
    """
    Calculate the capital to deploy for the current stage.

    Args:
        conviction:       Dict from classify_conviction().
        pool_capital:     Total capital available for this pool.
        stage:            Current stage (1, 2, or 3).
        already_deployed: Capital already deployed for this position.

    Returns:
        Float: capital amount to deploy at this stage (0 if nothing to do).
    """
    tier = conviction.get("tier", 4)
    max_alloc = pool_capital * MAX_POSITION_PCT

    if tier == 4:
        return 0.0

    if tier == 1:
        if stage == 1:
            # Initial 50% deployment
            return max_alloc * conviction.get("initial_pct", TIER1_INITIAL_PCT)
        elif stage == 2:
            # Confirmation add: remaining 50%
            remaining = max_alloc - already_deployed
            return max(0.0, remaining * conviction.get("confirm_pct", TIER1_CONFIRM_PCT) /
                       (conviction.get("confirm_pct", TIER1_CONFIRM_PCT) or 1.0))
        else:
            # Stage 3: nothing more for Tier 1 (already fully deployed or cancelled)
            return 0.0

    if tier == 2:
        if stage == 2:
            # Full deployment on ORB confirmation
            return max_alloc
        elif stage == 3:
            # Last chance if Stage 2 didn't confirm
            if already_deployed == 0:
                return max_alloc
            return 0.0
        return 0.0

    if tier == 3:
        if stage == 3:
            return max_alloc
        return 0.0

    return 0.0


# ═══════════════════════════════════════════════════════════════════
# SIGNAL GENERATION WITH STAGED ENTRIES
# ═══════════════════════════════════════════════════════════════════

def generate_staged_signals(regime: str = None) -> List[dict]:
    """
    Generate signals with conviction tier and staged entry instructions.

    Uses v5 signal engine (which wraps v4 composite scorer) for base signals,
    then adds conviction classification for each actionable signal.

    Args:
        regime: Market regime ('BULL', 'BEAR', 'SIDEWAYS'). Auto-detected if None.

    Returns:
        List of signal dicts with added fields:
            conviction (dict from classify_conviction), tier, entry_stage, confirm_condition
    """
    # Detect regime if not provided
    if regime is None:
        detect_fn = _lazy_import_regime()
        try:
            ri = detect_fn()
            regime = ri.get("regime", "SIDEWAYS")
        except Exception:
            regime = "SIDEWAYS"
    regime = regime.upper().replace("NEUTRAL", "SIDEWAYS")

    # Generate base signals
    sig_fn = _lazy_import_signals()
    try:
        base_signals = sig_fn(regime)
    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        return []

    if not base_signals:
        return []

    # Add conviction classification to actionable signals
    staged = []
    for sig in base_signals:
        direction = sig.get("direction", "HOLD")
        if direction not in ("BUY", "SELL"):
            continue  # Only classify actionable signals

        conv = classify_conviction(sig, regime)
        if conv["tier"] == 4:
            continue  # Skip tier 4

        sig_copy = dict(sig)
        sig_copy["conviction"] = conv
        sig_copy["tier"] = conv["tier"]
        sig_copy["tier_label"] = conv["label"]
        sig_copy["entry_stage"] = conv["entry_stage"]
        sig_copy["confirm_condition"] = conv["confirm_condition"]
        staged.append(sig_copy)

    # Sort: Tier 1 first, then by score descending
    staged.sort(key=lambda s: (-s.get("tier", 4), -s.get("score", 0)))
    # Reverse tier sort so Tier 1 comes first (lowest number = highest priority)
    staged.sort(key=lambda s: (s.get("tier", 4), -s.get("score", 0)))

    logger.info(
        f"Staged signals: {len(staged)} actionable "
        f"(T1:{sum(1 for s in staged if s['tier']==1)} "
        f"T2:{sum(1 for s in staged if s['tier']==2)} "
        f"T3:{sum(1 for s in staged if s['tier']==3)})"
    )
    return staged


def rescore_symbols(symbols: List[str]) -> Dict[str, float]:
    """
    Re-score a list of symbols using v4 composite scorer.

    Returns:
        Dict mapping symbol -> new score.
    """
    scorer = _lazy_import_scorer()
    try:
        results = scorer(symbols) if symbols else scorer()
    except Exception as e:
        logger.error(f"Rescore failed: {e}")
        return {}

    scores = {}
    for r in results:
        sym = r.get("symbol", "")
        if sym in symbols:
            scores[sym] = r.get("score", 0)
    return scores
