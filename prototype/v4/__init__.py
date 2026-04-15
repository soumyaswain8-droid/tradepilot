"""
TradePilot v4 — Composite Scoring Engine
=========================================
Multi-signal intraday scoring with real NSE data.

Modules:
    config                  - Central configuration
    data_nse                - NSE data fetching (FII/DII, options, VWAP)
    features_intraday       - ORB, VWAP position, gap, momentum
    features_institutional  - FII/DII score, OI buildup
    ml_engine               - LightGBM regression
    composite_scorer        - Weighted composite + ranking
    position_sizer          - Kelly criterion sizing
"""

__version__ = "4.0.0"

# Config always available
from .config import (
    V4_FEATURE_COLS,
    COMPOSITE_WEIGHTS,
    CLASSIFICATION_THRESHOLDS,
    NIFTY_50_SYMBOLS,
    NIFTY_200_SYMBOLS,
    ACTIVE_SYMBOLS,
    ACTIVE_SYMBOLS_YF,
    TRADING_UNIVERSE,
    CACHE_DIR,
)

# Lazy imports — modules loaded on demand, don't crash if one is missing
_AVAILABLE = {}

try:
    from .data_nse import (
        get_fii_dii_daily,
        get_options_chain,
        get_intraday_candles,
        compute_vwap,
        get_equity_quote,
        get_all_nifty50_quotes,
        get_nifty_index_level,
    )
    _AVAILABLE["data_nse"] = True
except ImportError:
    _AVAILABLE["data_nse"] = False

try:
    from .features_intraday import (
        compute_orb,
        compute_vwap_position,
        compute_gap_analysis,
        compute_intraday_momentum,
        compute_relative_strength,
        compute_all_intraday_features,
    )
    _AVAILABLE["features_intraday"] = True
except ImportError:
    _AVAILABLE["features_intraday"] = False

try:
    from .features_institutional import (
        compute_fii_dii_score,
        compute_oi_buildup,
        compute_all_institutional_features,
    )
    _AVAILABLE["features_institutional"] = True
except ImportError:
    _AVAILABLE["features_institutional"] = False

try:
    from .ml_engine import predict_ml_score, predict_batch, get_model_info
    _AVAILABLE["ml_engine"] = True
except ImportError:
    _AVAILABLE["ml_engine"] = False

try:
    from .composite_scorer import score_all_stocks
    _AVAILABLE["composite_scorer"] = True
except ImportError:
    _AVAILABLE["composite_scorer"] = False
