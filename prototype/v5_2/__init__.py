"""
TradePilot v5.2 — F&O Options Experiment Engine
=================================================
Runs as a SEPARATE experiment alongside v4 (equity intraday) and v5
(multi-horizon regime-aware) with its own Rs 10L capital pool.

Strategies:
    1. Protective Puts     (BEAR regime — insurance)
    2. Straddle Selling    (SIDEWAYS regime — premium decay)
    3. Directional Options (high-confidence BULL/BEAR)
    4. Covered Calls       (on v5 SWING holdings — passive income)

Imports regime detection from v5 (detect_regime).
Uses nsepython for Nifty option chain, yfinance for VIX.
"""

__version__ = "5.2.0-alpha"
