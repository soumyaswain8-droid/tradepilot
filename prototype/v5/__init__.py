"""
TradePilot v5 — Multi-Horizon Regime-Aware Trading Engine
==========================================================
v5 builds on v4's composite scorer and adds:
  1. Regime detection (HMM: bull/bear/sideways)
  2. Multi-horizon pools (intraday/swing/positional/investment)
  3. Short signals (profit on bear days)
  4. Pre-market intelligence (GIFT Nifty, FII prediction)
  5. ML ensemble (LightGBM + TFT + LSTM)
  6. Circuit breakers + risk budgeting per pool

Modules:
    regime_detector     - HMM 3-state market regime
    premarket_intel     - GIFT Nifty gap, FII flow prediction
    pool_manager        - 4-pool capital allocation + rebalancing
    signal_engine       - Enhanced scorer with short signals
    ml_ensemble         - Multi-model ensemble (LightGBM + TFT + LSTM)
    risk_manager        - Per-pool drawdown limits, circuit breakers
    comparator          - v4 vs v5 daily comparison
    options_signals     - PCR, IV skew, max pain contrarian signals
"""

__version__ = "5.0.0-alpha"

# Re-export v4 components we're building on
from ..v4.config import (
    NIFTY_50_SYMBOLS, NIFTY_50_YF,
    NIFTY_200_SYMBOLS, NIFTY_200_YF,
    ACTIVE_SYMBOLS, ACTIVE_SYMBOLS_YF,
    TRADING_UNIVERSE, CACHE_DIR,
)

# v5 modules loaded lazily
_AVAILABLE = {}

try:
    from . import regime_detector
    _AVAILABLE["regime_detector"] = True
except ImportError:
    _AVAILABLE["regime_detector"] = False

try:
    from . import premarket_intel
    _AVAILABLE["premarket_intel"] = True
except ImportError:
    _AVAILABLE["premarket_intel"] = False

try:
    from . import pool_manager
    _AVAILABLE["pool_manager"] = True
except ImportError:
    _AVAILABLE["pool_manager"] = False

try:
    from . import signal_engine
    _AVAILABLE["signal_engine"] = True
except ImportError:
    _AVAILABLE["signal_engine"] = False

try:
    from . import risk_manager
    _AVAILABLE["risk_manager"] = True
except ImportError:
    _AVAILABLE["risk_manager"] = False

try:
    from . import comparator
    _AVAILABLE["comparator"] = True
except ImportError:
    _AVAILABLE["comparator"] = False

try:
    from . import market_breadth
    _AVAILABLE["market_breadth"] = True
except ImportError:
    _AVAILABLE["market_breadth"] = False

try:
    from . import enhanced_features
    _AVAILABLE["enhanced_features"] = True
except ImportError:
    _AVAILABLE["enhanced_features"] = False

try:
    from . import options_signals
    _AVAILABLE["options_signals"] = True
except ImportError:
    _AVAILABLE["options_signals"] = False
