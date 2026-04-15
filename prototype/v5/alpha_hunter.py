"""
TradePilot v5 -- Bear Day Alpha Hunter
=======================================
Turns bear days from "survive with Rs 14K" to "thrive with Rs 35K+".

Problem: On bear days (Nifty -0.5% to -2%), v5 deploys only 30% of capital
and leaves 70% idle. Meanwhile, 20+ stocks go UP 2-5% due to sector rotation
(power/renewables/infra on Apr 13 despite Nifty -0.95%).

Solution: Scan for sectors outperforming a weak market, hunt individual stocks
with confirmed momentum within those sectors, deploy additional capital into
counter-trend winners with tight risk controls.

Pipeline:
  Phase 1: scan_sector_rotation()   -- 10:00 AM, after 45 min of data
  Phase 2: hunt_alpha_stocks()      -- find strongest movers in winning sectors
  Phase 3: generate_alpha_signals() -- size positions, set SL/target, emit signals

Usage:
    from prototype.v5.alpha_hunter import generate_alpha_signals
    signals = generate_alpha_signals("BEAR", 0.30)
CLI:
    python3 -m prototype.v5.alpha_hunter
"""

import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("tradepilot.v5.alpha_hunter")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# yfinance import with fallback
# ---------------------------------------------------------------------------
try:
    import yfinance as yf
    _HAS_YF = True
except ImportError:
    _HAS_YF = False
    logger.warning("yfinance not available -- alpha hunter will use cached data only")

# ---------------------------------------------------------------------------
# Sector Index Symbols (NSE sectoral indices via Yahoo Finance)
# ---------------------------------------------------------------------------
SECTOR_INDICES = {
    "Energy":   "^CNXENERGY",
    "Infra":    "^CNXINFRA",
    "Metal":    "^CNXMETAL",
    "Pharma":   "^CNXPHARMA",
    "IT":       "^CNXIT",
    "FMCG":     "^CNXFMCG",
    "Auto":     "^CNXAUTO",
    "Realty":   "^CNXREALTY",
    "Bank":     "^NSEBANK",
    "PSU Bank": "^CNXPSUBANK",
}

# ---------------------------------------------------------------------------
# Sector-Stock Mapping (Nifty 200 universe, grouped by sector)
# ---------------------------------------------------------------------------
SECTOR_STOCKS: Dict[str, List[str]] = {
    "Energy": [
        "RELIANCE", "ONGC", "BPCL", "IOC", "GAIL", "NTPC", "POWERGRID",
        "TATAPOWER", "ADANIPOWER", "ADANIGREEN", "NHPC", "SJVN", "JSWENERGY",
        "TORNTPOWER", "CESC", "SUZLON", "IREDA",
    ],
    "Metal": [
        "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NATIONALUM", "NMDC",
        "COALINDIA", "SAIL", "JINDALSTEL", "APLAPOLLO",
    ],
    "Infra": [
        "LT", "ADANIENT", "ADANIPORTS", "IRFC", "RECLTD", "PFC", "IRCON",
        "NBCC", "RVNL", "BEL", "HAL", "BHEL", "CGPOWER", "ABB", "SIEMENS",
        "CUMMINSIND", "POWERINDIA",
    ],
    "Bank": [
        "HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
        "BANDHANBNK", "FEDERALBNK", "IDFCFIRSTB", "PNB", "BANKBARODA", "CANBK",
    ],
    "IT": [
        "TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "MPHASIS",
        "COFORGE", "PERSISTENT", "LTTS",
    ],
    "Pharma": [
        "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "AUROPHARMA", "BIOCON",
        "TORNTPHARM", "LUPIN", "ZYDUSLIFE", "ALKEM",
    ],
    "Auto": [
        "MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT",
        "ASHOKLEY", "BHARATFORG", "MOTHERSON", "BOSCHLTD",
    ],
    "FMCG": [
        "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO",
        "GODREJCP", "COLPAL", "TATACONSUM", "VBL",
    ],
    "Realty": [
        "DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE", "SOBHA",
        "PHOENIXLTD",
    ],
    "PSU Bank": [
        "SBIN", "PNB", "BANKBARODA", "CANBK", "UNIONBANK", "IOB",
        "CENTRALBK", "INDIANB", "MAHABANK", "BANKINDIA",
    ],
}

# Reverse lookup: stock -> list of sectors
_STOCK_SECTOR: Dict[str, List[str]] = {}
for _sec, _stocks in SECTOR_STOCKS.items():
    for _sym in _stocks:
        _STOCK_SECTOR.setdefault(_sym, []).append(_sec)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ALPHA_THRESHOLD = 1.0        # sector must beat Nifty by >= 1% to be a winner
ROTATION_CONFIDENCE_MIN = 0.7
MIN_MORNING_RETURN = 0.0     # stock must be green since open
VOLUME_RATIO_MIN = 0.8       # bear days have lighter volume; 0.8x is enough
MAX_ALPHA_STOCKS = 15
IDLE_DEPLOY_FRACTION = 0.30  # deploy 30% of remaining idle capital
SL_PCT = 1.0                 # tight 1% SL for momentum plays
TARGET_PCT = 3.0             # let winners run in rotation
TRAILING_STOP_PCT = 0.7      # trail 0.7% below peak

# Cache dir for fallback data
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "alpha_cache"


# ===================================================================
# Phase 1: Sector Scanner
# ===================================================================

def _fetch_intraday_return(symbol: str, period: str = "1d",
                           interval: str = "5m") -> Optional[float]:
    """Fetch today's intraday return for a symbol via yfinance."""
    if not _HAS_YF:
        return None
    try:
        tick = yf.Ticker(symbol)
        hist = tick.history(period=period, interval=interval)
        if hist.empty or len(hist) < 2:
            return None
        open_price = hist["Open"].iloc[0]
        last_price = hist["Close"].iloc[-1]
        if open_price <= 0:
            return None
        return round((last_price - open_price) / open_price * 100, 2)
    except Exception as e:
        logger.debug(f"Failed to fetch {symbol}: {e}")
        return None


def _fetch_nifty_return() -> Optional[float]:
    """Get Nifty 50 morning return."""
    ret = _fetch_intraday_return("^NSEI")
    if ret is not None:
        return ret
    # Fallback: try daily data
    if not _HAS_YF:
        return None
    try:
        nifty = yf.Ticker("^NSEI")
        info = nifty.fast_info
        prev = info.previous_close
        curr = info.last_price
        if prev and prev > 0:
            return round((curr - prev) / prev * 100, 2)
    except Exception:
        pass
    return None


def scan_sector_rotation() -> dict:
    """
    Phase 1: At 10:00 AM, check which sectors outperform despite market weakness.

    Compares each Nifty sectoral index's morning return vs Nifty's morning return.
    Sectors beating Nifty by >1% = "rotation winners".

    Returns dict with market_return, winning/losing sectors, rotation_detected, confidence.
    """
    t0 = time.time()
    logger.info("Phase 1: Scanning for sector rotation...")

    market_return = _fetch_nifty_return()
    if market_return is None:
        logger.warning("Cannot fetch Nifty return -- using cached/dummy data")
        market_return = 0.0

    winning_sectors = []
    losing_sectors = []

    for name, symbol in SECTOR_INDICES.items():
        sector_ret = _fetch_intraday_return(symbol)
        if sector_ret is None:
            logger.debug(f"  {name} ({symbol}): no data, skipping")
            continue

        alpha = round(sector_ret - market_return, 2)

        entry = {
            "name": name,
            "symbol": symbol,
            "return": sector_ret,
            "alpha": alpha,
        }

        if alpha >= ALPHA_THRESHOLD:
            winning_sectors.append(entry)
            logger.info(f"  WINNER: {name:>10s} {sector_ret:+.2f}% (alpha {alpha:+.2f}%)")
        else:
            losing_sectors.append(entry)
            logger.debug(f"  {name:>10s} {sector_ret:+.2f}% (alpha {alpha:+.2f}%)")

    # Sort winners by alpha descending
    winning_sectors.sort(key=lambda x: x["alpha"], reverse=True)
    losing_sectors.sort(key=lambda x: x["alpha"])

    # Confidence: based on number of winning sectors and their alpha spread
    n_winners = len(winning_sectors)
    if n_winners == 0:
        confidence = 0.0
    elif n_winners == 1:
        confidence = 0.5 + min(winning_sectors[0]["alpha"] / 10, 0.3)
    else:
        avg_alpha = np.mean([s["alpha"] for s in winning_sectors])
        confidence = min(0.5 + n_winners * 0.1 + avg_alpha / 10, 1.0)
    confidence = round(confidence, 2)

    rotation_detected = n_winners >= 1 and confidence >= ROTATION_CONFIDENCE_MIN

    elapsed = round(time.time() - t0, 1)
    logger.info(
        f"Phase 1 done in {elapsed}s: market {market_return:+.2f}%, "
        f"{n_winners} winning sectors, rotation={'YES' if rotation_detected else 'NO'} "
        f"(confidence={confidence})"
    )

    return {
        "market_return": market_return,
        "winning_sectors": winning_sectors,
        "losing_sectors": losing_sectors,
        "rotation_detected": rotation_detected,
        "confidence": confidence,
        "scan_time": datetime.now().strftime("%H:%M:%S"),
    }


# ===================================================================
# Phase 2: Stock Hunter
# ===================================================================

def _fetch_stock_morning_data(symbol: str) -> Optional[dict]:
    """Fetch a stock's morning data: return, volume ratio, VWAP check, intraday high."""
    if not _HAS_YF:
        return None
    try:
        nse_sym = f"{symbol}.NS"
        tick = yf.Ticker(nse_sym)
        hist = tick.history(period="1d", interval="5m")
        if hist.empty or len(hist) < 3:
            return None

        open_price = hist["Open"].iloc[0]
        last_close = hist["Close"].iloc[-1]
        high = hist["High"].max()
        low = hist["Low"].min()
        total_vol = hist["Volume"].sum()

        if open_price <= 0:
            return None

        morning_return = round((last_close - open_price) / open_price * 100, 2)

        # VWAP: sum(price * volume) / sum(volume)
        typical = (hist["High"] + hist["Low"] + hist["Close"]) / 3
        vwap = (typical * hist["Volume"]).sum() / max(hist["Volume"].sum(), 1)
        above_vwap = last_close > vwap

        # Check if making new intraday high in last 3 candles (15 min)
        recent_high = hist["High"].iloc[-3:].max() if len(hist) >= 3 else high
        making_new_high = abs(recent_high - high) < 0.01

        # Volume ratio vs 20-day average (fetch daily data for comparison)
        vol_ratio = 1.0  # default if we can't compute
        try:
            daily = tick.history(period="1mo", interval="1d")
            if len(daily) >= 5:
                # Scale intraday volume to full-day estimate
                mkt_minutes_elapsed = max(
                    (datetime.now().hour - 9) * 60 + datetime.now().minute - 15, 30
                )
                full_day_est = total_vol * (375 / mkt_minutes_elapsed)
                avg_vol = daily["Volume"].iloc[-20:].mean()
                if avg_vol > 0:
                    vol_ratio = round(full_day_est / avg_vol, 2)
        except Exception:
            pass

        return {
            "symbol": symbol,
            "price": round(last_close, 2),
            "open": round(open_price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "morning_return": morning_return,
            "volume_ratio": vol_ratio,
            "above_vwap": above_vwap,
            "vwap": round(vwap, 2),
            "making_new_high": making_new_high,
        }
    except Exception as e:
        logger.debug(f"Failed stock data for {symbol}: {e}")
        return None


def hunt_alpha_stocks(winning_sectors: list,
                      universe: Optional[List[str]] = None) -> list:
    """
    Phase 2: Within winning sectors, find individual stocks with strongest momentum.

    For each stock in the sector universe:
    1. Must belong to a winning sector
    2. Morning return must be positive (green since open)
    3. Volume >= 0.8x average (bear days have lighter volume)
    4. Price above VWAP (institutional buying signal)
    5. Bonus: making new intraday high in last 15 min

    Returns top 10-15 stocks ranked by momentum_score with entry/SL/target.
    """
    t0 = time.time()
    logger.info("Phase 2: Hunting alpha stocks in winning sectors...")

    winning_names = {s["name"] for s in winning_sectors}
    winning_alpha = {s["name"]: s["alpha"] for s in winning_sectors}

    # Build candidate stock list from winning sectors
    if universe is None:
        candidates = set()
        for sec_name in winning_names:
            stocks = SECTOR_STOCKS.get(sec_name, [])
            candidates.update(stocks)
        candidates = sorted(candidates)
    else:
        # Filter universe to stocks in winning sectors
        candidates = [
            s for s in universe
            if any(sec in winning_names for sec in _STOCK_SECTOR.get(s, []))
        ]

    logger.info(f"  {len(candidates)} candidates across {len(winning_names)} winning sectors")

    scored = []
    for sym in candidates:
        data = _fetch_stock_morning_data(sym)
        if data is None:
            continue

        # Filter 1: must be green
        if data["morning_return"] < MIN_MORNING_RETURN:
            continue

        # Filter 2: volume confirmation
        if data["volume_ratio"] < VOLUME_RATIO_MIN:
            continue

        # Filter 3: above VWAP
        if not data["above_vwap"]:
            continue

        # Momentum score = morning_return * volume_factor * vwap_bonus * sector_alpha
        vol_factor = min(data["volume_ratio"], 3.0)  # cap at 3x
        vwap_bonus = 1.2 if data["above_vwap"] else 0.8
        new_high_bonus = 1.15 if data["making_new_high"] else 1.0

        # Get the strongest sector alpha for this stock
        stock_sectors = _STOCK_SECTOR.get(sym, [])
        best_sector = max(
            (sec for sec in stock_sectors if sec in winning_names),
            key=lambda s: winning_alpha.get(s, 0),
            default=stock_sectors[0] if stock_sectors else "Unknown",
        )
        sector_alpha = winning_alpha.get(best_sector, 1.0)

        momentum_score = round(
            data["morning_return"]
            * vol_factor
            * vwap_bonus
            * new_high_bonus
            * (1 + sector_alpha / 10),  # sector alpha boost
            2,
        )

        # Entry/SL/Target levels
        price = data["price"]
        entry_price = round(price, 2)
        sl_price = round(price * (1 - SL_PCT / 100), 2)
        target_price = round(price * (1 + TARGET_PCT / 100), 2)
        risk = entry_price - sl_price
        reward = target_price - entry_price
        rr = round(reward / risk, 1) if risk > 0 else 0.0

        scored.append({
            "symbol": sym,
            "sector": best_sector,
            "morning_return": data["morning_return"],
            "volume_ratio": data["volume_ratio"],
            "above_vwap": data["above_vwap"],
            "vwap": data["vwap"],
            "making_new_high": data["making_new_high"],
            "momentum_score": momentum_score,
            "price": price,
            "entry_price": entry_price,
            "sl_price": sl_price,
            "target_price": target_price,
            "riskReward": rr,
            "sector_alpha": sector_alpha,
        })

    # Rank by momentum score, take top N
    scored.sort(key=lambda x: x["momentum_score"], reverse=True)
    result = scored[:MAX_ALPHA_STOCKS]

    elapsed = round(time.time() - t0, 1)
    logger.info(
        f"Phase 2 done in {elapsed}s: {len(scored)} passed filters, "
        f"returning top {len(result)}"
    )
    return result


# ===================================================================
# Phase 3: Deployment Decision
# ===================================================================

def generate_alpha_signals(regime: str,
                           current_deployment_pct: float,
                           total_capital: float = 10_00_000) -> list:
    """
    Phase 3: End-to-end alpha hunt -- scan sectors, hunt stocks, emit signals.

    Only activates when:
    - Regime is BEAR or SIDEWAYS
    - Sector rotation is detected (confidence >= 0.7)
    - There is idle capital to deploy

    Capital logic:
    - Deploys 30% of REMAINING idle capital
    - If 30% already deployed by v5, alpha adds 30% of remaining 70% = 21% more
    - Total deployment: ~51% (not reckless, but not idle)

    Position sizing:
    - Equal weight across alpha stocks
    - 1% SL (tight -- momentum plays, cut quickly if wrong)
    - 3% target (let winners run in rotation)
    - 0.7% trailing stop below peak

    Returns list of signal dicts compatible with v5 signal format.
    """
    t0 = time.time()
    logger.info(
        f"Alpha Hunter: regime={regime}, deployed={current_deployment_pct:.0%}, "
        f"capital=Rs {total_capital:,.0f}"
    )

    # Gate 1: only on BEAR or SIDEWAYS days
    if regime.upper() not in ("BEAR", "SIDEWAYS"):
        logger.info("Alpha Hunter: BULL regime -- not needed, v5 handles it")
        return []

    # Gate 2: must have idle capital
    idle_pct = 1.0 - current_deployment_pct
    if idle_pct < 0.10:
        logger.info(f"Alpha Hunter: only {idle_pct:.0%} idle -- not enough to deploy")
        return []

    # Phase 1: Sector scan
    rotation = scan_sector_rotation()
    if not rotation["rotation_detected"]:
        logger.info(
            f"Alpha Hunter: no sector rotation detected "
            f"(confidence={rotation['confidence']})"
        )
        return []

    # Phase 2: Hunt stocks
    alpha_stocks = hunt_alpha_stocks(rotation["winning_sectors"])
    if not alpha_stocks:
        logger.info("Alpha Hunter: no stocks passed momentum filters")
        return []

    # Phase 3: Size and emit signals
    additional_deploy_pct = idle_pct * IDLE_DEPLOY_FRACTION
    additional_capital = total_capital * additional_deploy_pct
    n_stocks = min(len(alpha_stocks), MAX_ALPHA_STOCKS)
    per_stock_capital = additional_capital / n_stocks

    logger.info(
        f"Deploying {additional_deploy_pct:.1%} additional "
        f"(Rs {additional_capital:,.0f}) across {n_stocks} alpha stocks"
    )

    signals = []
    for stock in alpha_stocks[:n_stocks]:
        price = stock["price"]
        if price <= 0:
            continue

        qty = max(1, int(per_stock_capital / price))
        position_value = qty * price

        # Normalize momentum_score to 0-100 range for v5 compatibility
        raw_score = stock["momentum_score"]
        score = min(100, max(0, round(50 + raw_score * 5)))  # scale into 50-100 band

        signal = {
            "symbol": stock["symbol"],
            "direction": "BUY",
            "score": score,
            "pool": "INTRADAY",           # alpha plays close by EOD
            "entry_price": stock["entry_price"],
            "sl_price": stock["sl_price"],
            "target_price": stock["target_price"],
            "riskReward": stock["riskReward"],
            "position_type": "LONG",
            "source": "ALPHA_HUNTER",
            "sector": stock["sector"],
            "sector_alpha": stock["sector_alpha"],
            "morning_return": stock["morning_return"],
            "volume_ratio": stock["volume_ratio"],
            "above_vwap": stock["above_vwap"],
            "making_new_high": stock["making_new_high"],
            "momentum_score": stock["momentum_score"],
            "qty": qty,
            "position_value": round(position_value, 2),
            "trailing_stop_pct": TRAILING_STOP_PCT,
            "reason": (
                f"Sector rotation: {stock['sector']} "
                f"{stock['sector_alpha']:+.1f}% vs Nifty "
                f"{rotation['market_return']:+.2f}%"
            ),
        }
        signals.append(signal)

    elapsed = round(time.time() - t0, 1)
    total_deployed = sum(s["position_value"] for s in signals)
    logger.info(
        f"Alpha Hunter done in {elapsed}s: {len(signals)} signals, "
        f"Rs {total_deployed:,.0f} additional deployment"
    )

    return signals


# ===================================================================
# CLI Test
# ===================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TradePilot v5 Bear Day Alpha Hunter")
    parser.add_argument("--regime", default="BEAR", choices=["BULL", "BEAR", "SIDEWAYS"],
                        help="Market regime override (default: BEAR)")
    parser.add_argument("--deployed", type=float, default=0.30,
                        help="Current deployment fraction (default: 0.30)")
    parser.add_argument("--capital", type=float, default=10_00_000,
                        help="Total capital in Rs (default: 10,00,000)")
    parser.add_argument("--scan-only", action="store_true",
                        help="Only run sector scan, skip stock hunt")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    print("=" * 60)
    print("  TradePilot v5 -- Bear Day Alpha Hunter")
    print("=" * 60)

    # Phase 1: Sector Scan
    print("\n--- Phase 1: Sector Rotation Scan ---")
    rotation = scan_sector_rotation()
    print(f"Market return: {rotation['market_return']:+.2f}%")
    print(f"Rotation detected: {rotation['rotation_detected']} "
          f"(confidence: {rotation['confidence']})")

    if rotation["winning_sectors"]:
        print(f"\nWinning sectors ({len(rotation['winning_sectors'])}):")
        for s in rotation["winning_sectors"]:
            print(f"  {s['name']:>12s}: {s['return']:+.2f}% "
                  f"(alpha: {s['alpha']:+.2f}%)")
    else:
        print("\nNo winning sectors found.")

    if rotation["losing_sectors"]:
        print(f"\nLosing sectors ({len(rotation['losing_sectors'])}):")
        for s in rotation["losing_sectors"][:5]:
            print(f"  {s['name']:>12s}: {s['return']:+.2f}% "
                  f"(alpha: {s['alpha']:+.2f}%)")

    if args.scan_only:
        sys.exit(0)

    # Phase 2: Stock Hunt
    if rotation["rotation_detected"]:
        print("\n--- Phase 2: Alpha Stock Hunt ---")
        stocks = hunt_alpha_stocks(rotation["winning_sectors"])
        if stocks:
            print(f"\nTop alpha stocks ({len(stocks)}):")
            print(f"  {'Symbol':>12s}  {'Morning':>8s}  {'Vol':>5s}  "
                  f"{'VWAP':>4s}  {'Score':>6s}  {'Sector'}")
            print(f"  {'-'*12}  {'-'*8}  {'-'*5}  {'-'*4}  {'-'*6}  {'-'*10}")
            for s in stocks[:15]:
                print(
                    f"  {s['symbol']:>12s}  {s['morning_return']:+6.2f}%  "
                    f"{s['volume_ratio']:4.1f}x  "
                    f"{'Yes' if s['above_vwap'] else 'No':>4s}  "
                    f"{s['momentum_score']:6.1f}  "
                    f"{s['sector']}"
                )
        else:
            print("No stocks passed momentum filters.")

        # Phase 3: Signal Generation
        print("\n--- Phase 3: Alpha Signals ---")
        signals = generate_alpha_signals(
            args.regime, args.deployed, args.capital
        )
        if signals:
            total_value = sum(s["position_value"] for s in signals)
            print(f"\nAlpha signals: {len(signals)}")
            print(f"Additional deployment: Rs {total_value:,.0f} "
                  f"({total_value / args.capital:.1%} of capital)")
            print(f"Total deployment: {args.deployed + total_value / args.capital:.1%}")
            print(f"\n  {'Symbol':>12s}  {'Entry':>8s}  {'SL':>8s}  "
                  f"{'Target':>8s}  {'R:R':>4s}  {'Qty':>4s}  {'Sector'}")
            print(f"  {'-'*12}  {'-'*8}  {'-'*8}  {'-'*8}  {'-'*4}  "
                  f"{'-'*4}  {'-'*10}")
            for sig in signals[:15]:
                print(
                    f"  {sig['symbol']:>12s}  "
                    f"{sig['entry_price']:8.2f}  "
                    f"{sig['sl_price']:8.2f}  "
                    f"{sig['target_price']:8.2f}  "
                    f"{sig['riskReward']:4.1f}  "
                    f"{sig['qty']:4d}  "
                    f"{sig['sector']}"
                )
            print(f"\nSample signal dict:")
            import json
            print(json.dumps(signals[0], indent=2, default=str))
        else:
            print("No alpha signals generated.")
    else:
        print("\nNo rotation detected -- alpha hunter stays idle.")

    print("\n" + "=" * 60)
