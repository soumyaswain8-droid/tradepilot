"""
TradePilot v4 — Real NSE Data Pipeline
=======================================
Fetches live market data from NSE (via nsepython) and yfinance.

Data sources:
    - nsepython: FII/DII flows, equity quotes, options chain
    - yfinance:  Intraday candles, batch quotes, index levels

All functions cache to prototype/data/cache/YYYY-MM-DD/ as JSON.
All functions return sensible defaults on error (never crash).
"""

import json
import logging
import os
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np

from .config import (
    NIFTY_50_SYMBOLS,
    NIFTY_50_YF,
    ACTIVE_SYMBOLS,
    ACTIVE_SYMBOLS_YF,
    CACHE_DIR,
    INDEX_SYMBOLS,
    DEFAULT_INTRADAY_INTERVAL,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("tradepilot.v4.data_nse")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Lazy imports (nsepython is slow to import)
# ---------------------------------------------------------------------------
_nsepython = None
_yfinance = None


def _get_nsepython():
    """Lazy-load nsepython to avoid import overhead when not needed."""
    global _nsepython
    if _nsepython is None:
        try:
            import nsepython
            _nsepython = nsepython
        except ImportError:
            logger.error("nsepython not installed. Run: pip install nsepython")
            raise
    return _nsepython


def _get_yfinance():
    """Lazy-load yfinance."""
    global _yfinance
    if _yfinance is None:
        try:
            import yfinance as yf
            _yfinance = yf
        except ImportError:
            logger.error("yfinance not installed. Run: pip install yfinance")
            raise
    return _yfinance


# ---------------------------------------------------------------------------
# Cache Helpers
# ---------------------------------------------------------------------------
def _cache_dir_today() -> Path:
    """Return today's cache directory, creating it if needed."""
    today = date.today().isoformat()  # YYYY-MM-DD
    d = CACHE_DIR / today
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_cache(filename: str) -> Optional[dict]:
    """Read cached JSON file from today's cache dir. Returns None if missing/stale."""
    path = _cache_dir_today() / filename
    if path.exists():
        try:
            with open(path, "r") as f:
                data = json.load(f)
            logger.debug(f"Cache hit: {filename}")
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Cache read error for {filename}: {e}")
    return None


def _write_cache(filename: str, data: dict) -> None:
    """Write data as JSON to today's cache dir."""
    path = _cache_dir_today() / filename
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.debug(f"Cached: {filename}")
    except IOError as e:
        logger.warning(f"Cache write error for {filename}: {e}")


# ---------------------------------------------------------------------------
# 1. FII / DII Daily Flows
# ---------------------------------------------------------------------------
def get_fii_dii_daily() -> dict:
    """
    Fetch FII and DII daily buy/sell data from NSE.

    Returns:
        {
            "fii_net": float (crores),
            "dii_net": float (crores),
            "fii_buy": float,
            "fii_sell": float,
            "dii_buy": float,
            "dii_sell": float,
            "date": str (YYYY-MM-DD),
        }
    """
    cache_file = "fii_dii_daily.json"
    cached = _read_cache(cache_file)
    if cached:
        return cached

    result = {
        "fii_net": 0.0, "dii_net": 0.0,
        "fii_buy": 0.0, "fii_sell": 0.0,
        "dii_buy": 0.0, "dii_sell": 0.0,
        "date": date.today().isoformat(),
    }

    try:
        nse = _get_nsepython()
        df = nse.nse_fiidii()

        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            logger.warning("nse_fiidii() returned empty data")
            return result

        # nse_fiidii() returns DataFrame with columns:
        # category, date, buyValue, sellValue, netValue
        for _, row in df.iterrows():
            cat = str(row.get("category", "")).upper()
            buy_val = _safe_float(row.get("buyValue", 0))
            sell_val = _safe_float(row.get("sellValue", 0))
            net_val = _safe_float(row.get("netValue", 0))

            if "FII" in cat or "FPI" in cat:
                result["fii_buy"] = buy_val
                result["fii_sell"] = sell_val
                result["fii_net"] = net_val
            elif "DII" in cat:
                result["dii_buy"] = buy_val
                result["dii_sell"] = sell_val
                result["dii_net"] = net_val

        # Extract date from data if available
        if "date" in df.columns and len(df) > 0:
            result["date"] = str(df["date"].iloc[0])

        _write_cache(cache_file, result)
        logger.info(f"FII/DII: FII net={result['fii_net']:.0f}cr, DII net={result['dii_net']:.0f}cr")

    except Exception as e:
        logger.error(f"Error fetching FII/DII data: {e}")

    return result


# ---------------------------------------------------------------------------
# 2. Options Chain
# ---------------------------------------------------------------------------
def get_options_chain(symbol: str) -> dict:
    """
    Fetch options chain data for a stock/index.

    NSE blocks direct stock option chain scraping for most symbols.
    Strategy: try nsepython first, fallback to computing PCR from
    available data or return defaults.

    Returns:
        {
            "pcr": float,           # Put-Call Ratio
            "max_pain": float,      # Max pain strike price
            "total_ce_oi": int,     # Total Call OI
            "total_pe_oi": int,     # Total Put OI
            "ce_oi_change": int,    # Call OI change
            "pe_oi_change": int,    # Put OI change
            "symbol": str,
        }
    """
    cache_file = f"options_chain_{symbol}.json"
    cached = _read_cache(cache_file)
    if cached:
        return cached

    result = {
        "pcr": 1.0,  # Neutral default
        "max_pain": 0.0,
        "total_ce_oi": 0,
        "total_pe_oi": 0,
        "ce_oi_change": 0,
        "pe_oi_change": 0,
        "symbol": symbol,
    }

    # Strategy 1: Try nsepython nse_optionchain_scrapper
    try:
        nse = _get_nsepython()
        oc_data = nse.nse_optionchain_scrapper(symbol)

        if oc_data and isinstance(oc_data, dict) and "records" in oc_data:
            records = oc_data["records"]
            data_rows = records.get("data", [])

            total_ce_oi = 0
            total_pe_oi = 0
            ce_oi_change = 0
            pe_oi_change = 0
            strike_pain = {}  # strike -> pain value for max pain calc

            for row in data_rows:
                ce = row.get("CE", {})
                pe = row.get("PE", {})
                strike = row.get("strikePrice", 0)

                ce_oi = int(ce.get("openInterest", 0))
                pe_oi = int(pe.get("openInterest", 0))
                total_ce_oi += ce_oi
                total_pe_oi += pe_oi
                ce_oi_change += int(ce.get("changeinOpenInterest", 0))
                pe_oi_change += int(pe.get("changeinOpenInterest", 0))

                # Max pain: strike where total loss to option writers is minimum
                # Simplified: sum of ITM OI * distance for each strike
                if strike > 0:
                    strike_pain[strike] = ce_oi + pe_oi  # placeholder

            if total_ce_oi > 0:
                result["pcr"] = round(total_pe_oi / total_ce_oi, 3)
            result["total_ce_oi"] = total_ce_oi
            result["total_pe_oi"] = total_pe_oi
            result["ce_oi_change"] = ce_oi_change
            result["pe_oi_change"] = pe_oi_change

            # Max pain: strike with highest combined OI (simplified)
            if strike_pain:
                result["max_pain"] = max(strike_pain, key=strike_pain.get)

            _write_cache(cache_file, result)
            logger.info(f"Options {symbol}: PCR={result['pcr']}, MaxPain={result['max_pain']}")
            return result

    except Exception as e:
        logger.debug(f"nsepython options chain failed for {symbol}: {e}")

    # Strategy 2: Try oi_chain_builder (nsepython alternative)
    try:
        nse = _get_nsepython()
        if hasattr(nse, "oi_chain_builder"):
            oi_data = nse.oi_chain_builder(symbol, "latest", "full")
            if isinstance(oi_data, pd.DataFrame) and not oi_data.empty:
                if "CALLS_OI" in oi_data.columns and "PUTS_OI" in oi_data.columns:
                    total_ce = oi_data["CALLS_OI"].sum()
                    total_pe = oi_data["PUTS_OI"].sum()
                    if total_ce > 0:
                        result["pcr"] = round(total_pe / total_ce, 3)
                    result["total_ce_oi"] = int(total_ce)
                    result["total_pe_oi"] = int(total_pe)
                    _write_cache(cache_file, result)
                    logger.info(f"Options {symbol} (oi_chain_builder): PCR={result['pcr']}")
                    return result
    except Exception as e:
        logger.debug(f"oi_chain_builder failed for {symbol}: {e}")

    # Strategy 3: Use NIFTY index options as market-wide proxy
    if symbol != "NIFTY":
        try:
            nifty_oc = get_options_chain("NIFTY")
            if nifty_oc.get("total_ce_oi", 0) > 0:
                result["pcr"] = nifty_oc["pcr"]
                logger.info(f"Options {symbol}: using NIFTY proxy PCR={result['pcr']}")
        except Exception:
            pass

    _write_cache(cache_file, result)
    return result


# ---------------------------------------------------------------------------
# 3. Intraday Candles (via yfinance)
# ---------------------------------------------------------------------------
def get_intraday_candles(
    symbol: str,
    interval: str = DEFAULT_INTRADAY_INTERVAL,
) -> pd.DataFrame:
    """
    Fetch intraday OHLCV candles for a symbol.

    Args:
        symbol: NSE symbol (e.g. "RELIANCE") — .NS suffix added automatically
        interval: Candle interval ("1m", "5m", "15m", "30m", "1h")

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
        DatetimeIndex in IST.
        Empty DataFrame on error.
    """
    yf_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol

    try:
        yf = _get_yfinance()
        df = yf.download(
            yf_symbol,
            period="1d",
            interval=interval,
            progress=False,
            timeout=15,
        )

        if df is None or df.empty:
            logger.warning(f"No intraday data for {symbol} @ {interval}")
            return pd.DataFrame()

        # yfinance may return MultiIndex columns for single ticker — flatten
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Keep only OHLCV
        expected_cols = ["Open", "High", "Low", "Close", "Volume"]
        available = [c for c in expected_cols if c in df.columns]
        df = df[available]

        logger.debug(f"Intraday {symbol} @ {interval}: {len(df)} candles")
        return df

    except Exception as e:
        logger.error(f"Error fetching intraday for {symbol}: {e}")
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# 4. VWAP Computation
# ---------------------------------------------------------------------------
def compute_vwap(intraday_df: pd.DataFrame) -> float:
    """
    Compute Volume Weighted Average Price from intraday candles.

    VWAP = sum(typical_price * volume) / sum(volume)
    where typical_price = (High + Low + Close) / 3

    Args:
        intraday_df: DataFrame with High, Low, Close, Volume columns

    Returns:
        VWAP as float, or 0.0 if computation fails
    """
    if intraday_df is None or intraday_df.empty:
        return 0.0

    try:
        required = ["High", "Low", "Close", "Volume"]
        if not all(c in intraday_df.columns for c in required):
            logger.warning(f"VWAP: missing columns. Have: {list(intraday_df.columns)}")
            return 0.0

        typical_price = (
            intraday_df["High"] + intraday_df["Low"] + intraday_df["Close"]
        ) / 3.0

        volume = intraday_df["Volume"].astype(float)
        total_volume = volume.sum()

        if total_volume == 0:
            return 0.0

        vwap = (typical_price * volume).sum() / total_volume
        return round(float(vwap), 2)

    except Exception as e:
        logger.error(f"VWAP computation error: {e}")
        return 0.0


# ---------------------------------------------------------------------------
# 5. Equity Quote (single stock)
# ---------------------------------------------------------------------------
def get_equity_quote(symbol: str) -> dict:
    """
    Fetch current equity quote for a single NSE stock.

    Tries nsepython.nse_eq() first (real-time NSE data),
    falls back to yfinance.

    Returns:
        {
            "last_price": float,
            "open": float,
            "high": float,
            "low": float,
            "prev_close": float,
            "change_pct": float,
            "volume": int,
            "symbol": str,
        }
    """
    cache_file = f"quote_{symbol}.json"
    cached = _read_cache(cache_file)
    if cached:
        return cached

    result = {
        "last_price": 0.0, "open": 0.0, "high": 0.0, "low": 0.0,
        "prev_close": 0.0, "change_pct": 0.0, "volume": 0,
        "symbol": symbol,
    }

    # Strategy 1: nsepython nse_eq()
    try:
        nse = _get_nsepython()
        eq_data = nse.nse_eq(symbol)

        if eq_data and isinstance(eq_data, dict):
            price_info = eq_data.get("priceInfo", {})
            if price_info:
                result["last_price"] = _safe_float(price_info.get("lastPrice", 0))
                result["open"] = _safe_float(price_info.get("open", 0))
                result["high"] = _safe_float(price_info.get("intraDayHighLow", {}).get("max", 0))
                result["low"] = _safe_float(price_info.get("intraDayHighLow", {}).get("min", 0))
                result["prev_close"] = _safe_float(price_info.get("previousClose", 0))
                result["change_pct"] = _safe_float(price_info.get("pChange", 0))

            # Volume from preOpenMarket or securityInfo
            sec_info = eq_data.get("securityInfo", {})
            result["volume"] = int(_safe_float(sec_info.get("tradedVolume", 0)))

            if result["last_price"] > 0:
                _write_cache(cache_file, result)
                logger.debug(f"Quote {symbol}: {result['last_price']} ({result['change_pct']:+.2f}%)")
                return result

    except Exception as e:
        logger.debug(f"nse_eq() failed for {symbol}: {e}")

    # Strategy 2: yfinance fallback
    try:
        yf = _get_yfinance()
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.fast_info

        result["last_price"] = round(float(getattr(info, "last_price", 0)), 2)
        result["open"] = round(float(getattr(info, "open", 0)), 2)
        result["prev_close"] = round(float(getattr(info, "previous_close", 0)), 2)
        result["volume"] = int(getattr(info, "last_volume", 0))

        if result["prev_close"] > 0 and result["last_price"] > 0:
            result["change_pct"] = round(
                (result["last_price"] - result["prev_close"]) / result["prev_close"] * 100, 2
            )

        if result["last_price"] > 0:
            _write_cache(cache_file, result)
            logger.debug(f"Quote {symbol} (yf): {result['last_price']}")

    except Exception as e:
        logger.error(f"yfinance quote failed for {symbol}: {e}")

    return result


# ---------------------------------------------------------------------------
# 6. Batch Nifty 50 Quotes (yfinance batch download for speed)
# ---------------------------------------------------------------------------
def get_all_nifty50_quotes() -> dict:
    """
    Batch fetch quotes for all Nifty 50 stocks using yfinance.

    Returns:
        {
            "RELIANCE": {"last_price": ..., "change_pct": ..., ...},
            "TCS": {...},
            ...
        }
    """
    cache_file = "nifty50_quotes_batch.json"
    cached = _read_cache(cache_file)
    if cached:
        return cached

    result = {}

    try:
        yf = _get_yfinance()
        # Batch download today's data for all Nifty 50
        yf_symbols = " ".join(ACTIVE_SYMBOLS_YF)
        df = yf.download(
            yf_symbols,
            period="2d",     # 2 days to get prev close
            interval="1d",
            group_by="ticker",
            progress=False,
            timeout=30,
            threads=True,
        )

        if df is None or df.empty:
            logger.warning("Batch download returned empty. Falling back to individual quotes.")
            return _fallback_individual_quotes()

        for symbol in ACTIVE_SYMBOLS:
            yf_sym = f"{symbol}.NS"
            try:
                if isinstance(df.columns, pd.MultiIndex) and yf_sym in df.columns.get_level_values(0):
                    stock_df = df[yf_sym]
                else:
                    # Single ticker case or flat columns
                    stock_df = df

                if stock_df.empty or len(stock_df) < 1:
                    continue

                last_row = stock_df.iloc[-1]
                prev_row = stock_df.iloc[-2] if len(stock_df) >= 2 else last_row

                last_price = _safe_float(last_row.get("Close", 0))
                prev_close = _safe_float(prev_row.get("Close", 0))
                change_pct = 0.0
                if prev_close > 0 and last_price > 0:
                    change_pct = round((last_price - prev_close) / prev_close * 100, 2)

                result[symbol] = {
                    "last_price": round(last_price, 2),
                    "open": round(_safe_float(last_row.get("Open", 0)), 2),
                    "high": round(_safe_float(last_row.get("High", 0)), 2),
                    "low": round(_safe_float(last_row.get("Low", 0)), 2),
                    "prev_close": round(prev_close, 2),
                    "change_pct": change_pct,
                    "volume": int(_safe_float(last_row.get("Volume", 0))),
                    "symbol": symbol,
                }

            except Exception as e:
                logger.debug(f"Error parsing batch data for {symbol}: {e}")
                continue

        if result:
            _write_cache(cache_file, result)
            logger.info(f"Batch quotes: {len(result)}/{len(ACTIVE_SYMBOLS)} stocks fetched")

    except Exception as e:
        logger.error(f"Batch download failed: {e}. Falling back to individual quotes.")
        return _fallback_individual_quotes()

    return result


def _fallback_individual_quotes() -> dict:
    """Fallback: fetch quotes one by one (slower but more reliable)."""
    result = {}
    for symbol in ACTIVE_SYMBOLS:
        try:
            quote = get_equity_quote(symbol)
            if quote.get("last_price", 0) > 0:
                result[symbol] = quote
        except Exception:
            continue
        time.sleep(0.3)  # Rate limit for NSE
    return result


# ---------------------------------------------------------------------------
# 7. Nifty 50 Index Level
# ---------------------------------------------------------------------------
def get_nifty_index_level() -> dict:
    """
    Fetch current Nifty 50 index level and change %.

    Returns:
        {
            "level": float,         # Current index value
            "change_pct": float,    # % change from previous close
            "prev_close": float,
            "open": float,
            "high": float,
            "low": float,
        }
    """
    cache_file = "nifty_index_level.json"
    cached = _read_cache(cache_file)
    if cached:
        return cached

    result = {
        "level": 0.0, "change_pct": 0.0,
        "prev_close": 0.0, "open": 0.0,
        "high": 0.0, "low": 0.0,
    }

    try:
        yf = _get_yfinance()
        nifty = yf.download(
            INDEX_SYMBOLS["NIFTY50"],
            period="2d",
            interval="1d",
            progress=False,
            timeout=15,
        )

        if nifty is None or nifty.empty:
            logger.warning("Could not fetch Nifty 50 index data")
            return result

        # Flatten MultiIndex if present
        if isinstance(nifty.columns, pd.MultiIndex):
            nifty.columns = nifty.columns.get_level_values(0)

        last_row = nifty.iloc[-1]
        prev_row = nifty.iloc[-2] if len(nifty) >= 2 else last_row

        result["level"] = round(_safe_float(last_row.get("Close", 0)), 2)
        result["prev_close"] = round(_safe_float(prev_row.get("Close", 0)), 2)
        result["open"] = round(_safe_float(last_row.get("Open", 0)), 2)
        result["high"] = round(_safe_float(last_row.get("High", 0)), 2)
        result["low"] = round(_safe_float(last_row.get("Low", 0)), 2)

        if result["prev_close"] > 0:
            result["change_pct"] = round(
                (result["level"] - result["prev_close"]) / result["prev_close"] * 100, 2
            )

        _write_cache(cache_file, result)
        logger.info(f"Nifty 50: {result['level']} ({result['change_pct']:+.2f}%)")

    except Exception as e:
        logger.error(f"Error fetching Nifty index: {e}")

    return result


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------
def _safe_float(val, default: float = 0.0) -> float:
    """Safely convert any value to float."""
    if val is None:
        return default
    try:
        # Handle strings with commas (e.g. "1,234.56")
        if isinstance(val, str):
            val = val.replace(",", "").strip()
            if val == "" or val == "-":
                return default
        return float(val)
    except (ValueError, TypeError):
        return default
