"""Tiered ML scorer — routes each stock to the right model by tier.

Phase 1 scaffold (2026-04-21):
  - Module exists, can be imported
  - Not yet wired into any engine (intentional — Week 3 flip)
  - When wired, each symbol gets scored by its tier-specific model
    instead of the single monolithic `lgbm_intraday.txt`

Why tiered:
  - Nifty 50 stocks have different feature weights than small caps
  - Mixing them diluted the signal (see forensic report 2026-04-21)
  - Tiered models isolate signal per market-cap segment

Expected usage (future):
    from prototype.v4.tiered_scorer import score_symbol

    score = score_symbol("RELIANCE", features)  # -> routes to 'elite' model
    score = score_symbol("ZYDUSWELL", features) # -> routes to 'broad' model
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

_V4_DIR = Path(__file__).resolve().parent
_TIERED_DIR = _V4_DIR / "models" / "tiered"

# Tier mapping — which stocks belong to which tier.
# Empty for now; populated after data backfill + tier definition step.
TIER_MEMBERSHIP: dict[str, str] = {
    # "RELIANCE": "elite",
    # "TCS": "elite",
    # ... populated in Week 3
}

# Tier → model path
TIER_MODEL_PATH = {
    "elite":     _TIERED_DIR / "elite_lgbm.txt",
    "large_cap": _TIERED_DIR / "large_cap_lgbm.txt",
    "mid_cap":   _TIERED_DIR / "mid_cap_lgbm.txt",
    "broad":     _TIERED_DIR / "broad_lgbm.txt",
}

# Fallback when tier is unknown — use the legacy monolithic model
FALLBACK_MODEL = _V4_DIR / "models" / "lgbm_intraday.txt"


def get_tier(symbol: str) -> str:
    """Return the tier name for a symbol. Falls back to 'fallback' if unknown."""
    return TIER_MEMBERSHIP.get(symbol.upper(), "fallback")


def get_model_path(symbol: str) -> Path:
    """Return the model file path for a symbol's tier."""
    tier = get_tier(symbol)
    return TIER_MODEL_PATH.get(tier, FALLBACK_MODEL)


def score_symbol(symbol: str, features) -> Optional[float]:
    """Score a symbol using its tier's model.

    PHASE 1 SCAFFOLD — returns None (not wired up).
    Will be activated in Week 3 after tier membership is loaded and
    tiered models are trained.

    Args:
        symbol: stock symbol (e.g. "RELIANCE")
        features: feature vector (n_features,) as numpy array

    Returns:
        predicted intraday return, or None if tier model not available
    """
    # Scaffold — intentionally returns None so existing code paths
    # are never silently redirected through this module.
    return None


def is_wired() -> bool:
    """Whether tiered scoring is active. Currently always False (scaffold)."""
    return False
