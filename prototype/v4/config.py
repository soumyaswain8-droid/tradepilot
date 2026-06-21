"""
TradePilot v4 — Central Configuration
======================================
All weights, feature lists, thresholds, and stock universe in one place.
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Try importing NIFTY_50 from existing stock_universe, fallback to hardcoded
# ---------------------------------------------------------------------------
try:
    import sys
    _proto_dir = str(Path(__file__).resolve().parent.parent)
    if _proto_dir not in sys.path:
        sys.path.insert(0, _proto_dir)
    from stock_universe import NIFTY_50 as _NIFTY_50_RAW
    # stock_universe uses "RELIANCE.NS" format — strip .NS for NSE-native symbols
    NIFTY_50_SYMBOLS = [s.replace(".NS", "") for s in _NIFTY_50_RAW]
except ImportError:
    NIFTY_50_SYMBOLS = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
        "HINDUNILVR", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT",
        "ITC", "AXISBANK", "BAJFINANCE", "MARUTI", "HCLTECH",
        "ASIANPAINT", "SUNPHARMA", "TITAN", "WIPRO", "ULTRACEMCO",
        "ONGC", "NTPC", "POWERGRID", "M&M", "TATAMOTORS",
        "JSWSTEEL", "TATASTEEL", "ADANIENT", "ADANIPORTS", "TECHM",
        "INDUSINDBK", "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "NESTLEIND",
        "DRREDDY", "DIVISLAB", "CIPLA", "COALINDIA", "GRASIM",
        "BRITANNIA", "EICHERMOT", "APOLLOHOSP", "TATACONSUM", "HEROMOTOCO",
        "BAJAJ-AUTO", "BPCL", "UPL", "HINDALCO", "SHRIRAMFIN",
    ]

# yfinance-compatible symbols (with .NS suffix)
NIFTY_50_YF = [f"{s}.NS" for s in NIFTY_50_SYMBOLS]

# ---------------------------------------------------------------------------
# Nifty 200 Universe (Nifty 50 + Nifty Next 50 + Nifty Midcap 100)
# Source: NSE Indices — ind_nifty200list.csv (updated 2026-04-08)
# ---------------------------------------------------------------------------
NIFTY_200_SYMBOLS = [
    # --- Nifty 50 core (included in Nifty 200) ---
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    "HINDUNILVR", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT",
    "ITC", "AXISBANK", "BAJFINANCE", "MARUTI", "HCLTECH",
    "ASIANPAINT", "SUNPHARMA", "TITAN", "WIPRO", "ULTRACEMCO",
    "ONGC", "NTPC", "POWERGRID", "M&M", "TATASTEEL",
    "JSWSTEEL", "ADANIENT", "ADANIPORTS", "TECHM", "INDUSINDBK",
    "BAJAJFINSV", "HDFCLIFE", "SBILIFE", "NESTLEIND", "DRREDDY",
    "DIVISLAB", "CIPLA", "COALINDIA", "GRASIM", "BRITANNIA",
    "EICHERMOT", "APOLLOHOSP", "TATACONSUM", "HEROMOTOCO", "BAJAJ-AUTO",
    "BPCL", "UPL", "HINDALCO", "SHRIRAMFIN",
    # --- Nifty Next 50 + Midcap 100 additions ---
    "360ONE", "ABB", "ABCAPITAL", "ADANIENSOL", "ADANIGREEN",
    "ADANIPOWER", "ALKEM", "AMBUJACEM", "APLAPOLLO", "ASHOKLEY",
    "ASTRAL", "ATGL", "AUBANK", "AUROPHARMA", "BAJAJHLDNG",
    "BANKBARODA", "BANKINDIA", "BDL", "BEL", "BHARATFORG",
    "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD", "BSE",
    "CANBK", "CGPOWER", "CHOLAFIN", "COCHINSHIP", "COFORGE",
    "COLPAL", "CONCOR", "COROMANDEL", "CUMMINSIND", "DABUR",
    "DIXON", "DLF", "DMART", "ENRIN", "ETERNAL",
    "EXIDEIND", "FEDERALBNK", "FORTIS", "GAIL", "GLENMARK",
    "GMRAIRPORT", "GODFRYPHLP", "GODREJCP", "GODREJPROP", "GROWW",
    "GVT&D", "HAL", "HAVELLS", "HDFCAMC", "HINDPETRO",
    "HINDZINC", "HUDCO", "HYUNDAI", "ICICIAMC", "ICICIGI",
    "IDEA", "IDFCFIRSTB", "INDHOTEL", "INDIANB", "INDIGO",
    "INDUSTOWER", "IOC", "IRCTC", "IREDA", "IRFC",
    "JINDALSTEL", "JIOFIN", "JSWENERGY", "JUBLFOOD", "KALYANKJIL",
    "KEI", "KPITTECH", "LAURUSLABS", "LENSKART", "LGEINDIA",
    "LICHSGFIN", "LODHA", "LTF", "LTM", "LUPIN",
    "M&MFIN", "MANKIND", "MARICO", "MAXHEALTH", "MAZDOCK",
    "MCX", "MFSL", "MOTHERSON", "MOTILALOFS", "MPHASIS",
    "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI", "NHPC",
    "NMDC", "NYKAA", "OBEROIRLTY", "OFSS", "OIL",
    "PAGEIND", "PATANJALI", "PAYTM", "PERSISTENT", "PFC",
    "PHOENIXLTD", "PIDILITIND", "PIIND", "PNB", "POLICYBZR",
    "POLYCAB", "POWERINDIA", "PREMIERENE", "PRESTIGE", "RADICO",
    "RECLTD", "RVNL", "SAIL", "SBICARD", "SHREECEM",
    "SIEMENS", "SOLARINDS", "SRF", "SUPREMEIND", "SUZLON",
    "SWIGGY", "TATACAP", "TATACOMM", "TATAELXSI", "TATAINVEST",
    "TATAPOWER", "TIINDIA", "TMCV", "TMPV", "TORNTPHARM",
    "TRENT", "TVSMOTOR", "UNIONBANK", "UNITDSPR", "VBL",
    "VEDL", "VMM", "VOLTAS", "WAAREEENER", "YESBANK",
    "ZYDUSLIFE", "TATAMOTORS",
]

# De-duplicate (Nifty 50 core appears in both sections)
NIFTY_200_SYMBOLS = sorted(set(NIFTY_200_SYMBOLS))

NIFTY_200_YF = [f"{s}.NS" for s in NIFTY_200_SYMBOLS]

# ---------------------------------------------------------------------------
# Trading Universe Selection
# ---------------------------------------------------------------------------
# Options: "NIFTY_50", "NIFTY_200"
TRADING_UNIVERSE = "NIFTY_200"

ACTIVE_SYMBOLS = NIFTY_200_SYMBOLS if TRADING_UNIVERSE == "NIFTY_200" else NIFTY_50_SYMBOLS

# Env override: a UNIVERSE_FILE (one symbol/line) expands the scan universe for a
# single engine (e.g. v5_cut) without touching the others. Used to scan more names
# for more opportunities + learnings. Falls back to NIFTY_200 if file missing/empty.
import os as _os
_uf = _os.environ.get("UNIVERSE_FILE")
if _uf and _os.path.exists(_uf):
    try:
        _syms = [l.strip().upper() for l in open(_uf) if l.strip() and not l.startswith("#")]
        if len(_syms) >= 50:
            ACTIVE_SYMBOLS = _syms
    except Exception:
        pass
ACTIVE_SYMBOLS_YF = [f"{s}.NS" for s in ACTIVE_SYMBOLS]

# ---------------------------------------------------------------------------
# V4 Feature Columns (19 features)
# ---------------------------------------------------------------------------
# 9 Daily Context features
DAILY_CONTEXT_FEATURES = [
    "nifty_change_pct",       # Nifty 50 index % change
    "fii_net_crores",         # FII net buy/sell (crores)
    "dii_net_crores",         # DII net buy/sell (crores)
    "stock_change_pct",       # Stock's daily % change
    "stock_volume_ratio",     # Today's volume / 20-day avg volume
    "sector_change_pct",      # Sector index % change (proxy)
    "advance_decline_ratio",  # Market breadth
    "india_vix",              # Volatility index
    "prev_day_range_pct",     # Previous day's (H-L)/C as %
]

# 5 Intraday features
INTRADAY_FEATURES = [
    "vwap_deviation_pct",     # (LTP - VWAP) / VWAP * 100
    "orb_signal",             # Opening Range Breakout: 1=above, -1=below, 0=inside
    "orb_range_pct",          # First 15min range as % of open
    "intraday_trend",         # Linear regression slope of 5min closes (normalized)
    "volume_surge_ratio",     # Last 15min volume / avg 15min volume
]

# 3 Institutional features
INSTITUTIONAL_FEATURES = [
    "pcr",                    # Put-Call Ratio from options chain
    "max_pain_distance_pct",  # (LTP - max_pain) / max_pain * 100
    "oi_buildup_signal",      # +1 long buildup, -1 short buildup, 0 neutral
]

# 2 Relative Strength features
RELATIVE_STRENGTH_FEATURES = [
    "rs_vs_nifty_5d",         # 5-day relative strength vs Nifty 50
    "rs_vs_nifty_20d",        # 20-day relative strength vs Nifty 50
]

# Combined: all 19 features
V4_FEATURE_COLS = (
    DAILY_CONTEXT_FEATURES
    + INTRADAY_FEATURES
    + INSTITUTIONAL_FEATURES
    + RELATIVE_STRENGTH_FEATURES
)

assert len(V4_FEATURE_COLS) == 19, f"Expected 19 features, got {len(V4_FEATURE_COLS)}"

# ---------------------------------------------------------------------------
# Composite Score Weights (must sum to 1.0)
# ---------------------------------------------------------------------------
COMPOSITE_WEIGHTS = {
    "ml_score":   0.0,     # REMOVED 2026-06-21: dead weight (walk-forward IC 0.006); shadow A/B
                           # v5_noml beat v5 5/5 days, +5940 cumulative. Affects all engines.
    "rs_score":   0.2667,  # Relative strength (renormalized from 0.20 / 0.75)
    "orb_score":  0.20,    # Opening Range Breakout (from 0.15 / 0.75)
    "vwap_score": 0.1333,  # VWAP position (from 0.10 / 0.75)
    "fii_score":  0.1333,  # FII/DII flow
    "oi_score":   0.1333,  # Open Interest / options
    "vol_score":  0.1334,  # Volume analysis (absorbs rounding to keep sum = 1.0)
}

assert abs(sum(COMPOSITE_WEIGHTS.values()) - 1.0) < 1e-6, "Weights must sum to 1.0"

# ---------------------------------------------------------------------------
# Classification Thresholds (percentile-based)
# ---------------------------------------------------------------------------
CLASSIFICATION_THRESHOLDS = {
    "BUY":  0.80,   # Top 20% composite score → BUY
    "HOLD": 0.50,   # Next 30% (50th-80th percentile) → HOLD
    "AVOID": 0.0,   # Bottom 50% → AVOID
}

# Alternate: absolute score thresholds (use when percentile isn't available)
ABSOLUTE_THRESHOLDS = {
    "STRONG_BUY": 0.75,
    "BUY":        0.60,
    "HOLD":       0.40,
    "AVOID":      0.25,
    "STRONG_SELL": 0.0,
}

# ---------------------------------------------------------------------------
# Cache Configuration
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = _PROJECT_ROOT / "data" / "cache"

# Ensure cache dir exists on import
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# NSE / API Configuration
# ---------------------------------------------------------------------------
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

# yfinance download settings
YF_THREADS = True          # Use threading for batch downloads
YF_TIMEOUT = 30            # Seconds per request
YF_RETRY_COUNT = 3         # Retries on failure

# Intraday intervals supported
INTRADAY_INTERVALS = ["1m", "5m", "15m", "30m", "1h"]
DEFAULT_INTRADAY_INTERVAL = "15m"

# ORB (Opening Range Breakout) settings
ORB_MINUTES = 15           # First N minutes define the opening range
ORB_CANDLE_INTERVAL = "5m" # Candle size for ORB detection

# ---------------------------------------------------------------------------
# Index Symbols (yfinance format)
# ---------------------------------------------------------------------------
INDEX_SYMBOLS = {
    "NIFTY50":    "^NSEI",
    "BANKNIFTY":  "^NSEBANK",
    "NIFTYIT":    "^CNXIT",
    "NIFTYPHARMA": "^CNXPHARMA",
    "INDIA_VIX":  "^INDIAVIX",
}
