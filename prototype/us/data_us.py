#!/usr/bin/env python3
"""
data_us — US equity data layer for the TradePilot US Market module.

DELIBERATELY ISOLATED from the India stack:
  - own cache dir  : prototype/data/us_cache/YYYY-MM-DD/   (never prototype/data/cache/)
  - own universe   : prototype/us/universe/
  - own history    : docs/us-market/history/
The India engines' shared cache was the vector for a fleet-wide poisoning incident
(2026-05-08) and again nearly caused one on 2026-07-28. A separate namespace means a
bug here can never corrupt prices the 9 live India engines read.

SOURCE (v1): yfinance. Verified 2026-08-02 — 3y daily for AAPL/MSFT/NVDA returned
753 trading days, 2023-08-01 -> 2026-07-31, zero NaN cells. yfinance is a scraper of
a free endpoint, NOT a licensed feed: fine for paper trading and research, must be
re-evaluated before any real-money use. Alternative sources are being researched
separately; this module keeps the fetch behind get_history()/get_quotes() so the
backend can be swapped without touching callers.

STALENESS GUARD is mandatory here, mirroring the guards data_nse gained on
2026-05-08. Cache entries carry a fetched_at stamp and are refused past TTL.

Usage:
    from prototype.us.data_us import get_history, get_quotes, load_universe
    df = get_history(["AAPL","MSFT"], years=3)
"""
from __future__ import annotations

import json
import logging
import os
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
US_CACHE_DIR = ROOT / "prototype" / "data" / "us_cache"
UNIVERSE_DIR = Path(__file__).resolve().parent / "universe"
HISTORY_DIR = ROOT / "docs" / "us-market" / "history"

QUOTE_TTL_SECONDS = 300      # 5 min, same as data_nse's CACHE_TTL_SECONDS
HISTORY_TTL_HOURS = 20       # daily bars: refetch once per session

# US market hours in IST (the reason this module cannot share the India cadence):
#   regular session 09:30-16:00 ET  ->  19:00-01:30 IST (20:00-02:30 during IST/EDT drift)
US_SESSION_IST = "19:00-01:30 (EDT) / 20:00-02:30 (EST)"


def _cache_dir_today() -> Path:
    d = US_CACHE_DIR / datetime.now().strftime("%Y-%m-%d")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _read_cache(name: str, ttl_seconds: int) -> Optional[dict]:
    """Read a cache entry, refusing anything older than ttl_seconds.

    The staleness check is the whole point — data_nse served pre-market NaN data
    all day before it got one. Never return an unstamped or expired entry.
    """
    p = _cache_dir_today() / name
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text())
    except Exception as e:
        logger.info(f"us_cache unreadable, refetching: {name} ({e})")
        return None
    stamp = blob.get("fetched_at")
    if not stamp:
        logger.info(f"us_cache entry has no fetched_at, refusing: {name}")
        return None
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(stamp)).total_seconds()
    if age > ttl_seconds:
        logger.info(f"us_cache stale ({age:.0f}s > {ttl_seconds}s), refetching: {name}")
        return None
    return blob.get("data")


def _write_cache(name: str, data) -> None:
    p = _cache_dir_today() / name
    p.write_text(json.dumps(
        {"fetched_at": datetime.now(timezone.utc).isoformat(), "data": data},
        indent=2, default=str))


# ---------------------------------------------------------------- universe

def load_universe(name: str = "sp500") -> list:
    """Load a ticker universe. Falls back to a small built-in list so the UI can
    always render something rather than erroring."""
    f = UNIVERSE_DIR / f"{name}.txt"
    if f.exists():
        syms = [l.strip().upper() for l in f.read_text().splitlines()
                if l.strip() and not l.startswith("#")]
        if syms:
            return syms
    logger.warning(f"universe {name} missing/empty — using built-in fallback")
    return ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO",
            "JPM", "V", "UNH", "XOM", "MA", "COST", "HD"]


# ---------------------------------------------------------------- prices

def get_history(symbols: Iterable[str], years: int = 3, interval: str = "1d"):
    """Daily (or other-interval) OHLCV for `symbols` over `years`.

    Returns a pandas DataFrame or None if the fetch fails. auto_adjust=False keeps
    raw closes AND gives us Adj Close, so corporate actions can be handled
    explicitly — the India stack's corp-action gap is a known open problem and this
    module should not inherit it.
    """
    syms = [s.upper() for s in symbols]
    if not syms:
        return None
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed")
        return None
    try:
        df = yf.download(syms, period=f"{years}y", interval=interval,
                         progress=False, auto_adjust=False,
                         group_by="column", threads=True)
        if df is None or df.empty:
            logger.error("yfinance returned empty history")
            return None
        return df
    except Exception as e:
        logger.error(f"get_history failed: {type(e).__name__}: {e}")
        return None


def get_quotes(symbols: Iterable[str]) -> dict:
    """Latest price + day change per symbol, cached with a 5-min staleness guard.

    Returns {SYM: {price, change, change_pct, prev_close}}. Symbols that fail are
    omitted rather than returned as zeros — a silent 0.0 price is how bad fills
    happen.
    """
    syms = sorted({s.upper() for s in symbols})
    if not syms:
        return {}
    key = f"quotes_{abs(hash(tuple(syms))) % (10**10)}.json"
    cached = _read_cache(key, QUOTE_TTL_SECONDS)
    if cached is not None:
        return cached

    out: dict = {}
    try:
        import yfinance as yf
        df = yf.download(syms, period="5d", interval="1d",
                         progress=False, auto_adjust=False, group_by="column")
        if df is None or df.empty:
            return {}
        close = df["Close"] if "Close" in df else df
        if hasattr(close, "columns"):
            cols = list(close.columns)
        else:                                  # single symbol -> Series
            cols = syms[:1]
            close = close.to_frame(name=cols[0])
        for c in cols:
            s = close[c].dropna()
            if len(s) < 2:
                continue                        # not enough data — omit, never fake
            last, prev = float(s.iloc[-1]), float(s.iloc[-2])
            if prev <= 0:
                continue
            out[str(c)] = {
                "price": round(last, 2),
                "prev_close": round(prev, 2),
                "change": round(last - prev, 2),
                "change_pct": round((last - prev) / prev * 100, 2),
            }
    except Exception as e:
        logger.error(f"get_quotes failed: {type(e).__name__}: {e}")
        return {}

    if out:
        _write_cache(key, out)
    return out


def history_stats(symbols: Iterable[str], years: int = 3) -> dict:
    """Summary of what history we actually hold — powers the UI's data-coverage
    panel so the depth claim is shown, not asserted."""
    df = get_history(symbols, years=years)
    if df is None:
        return {"ok": False, "error": "fetch failed"}
    close = df["Close"] if "Close" in df else df
    return {
        "ok": True,
        "symbols": int(getattr(close, "shape", [0, 0])[1]) if hasattr(close, "shape") else 1,
        "trading_days": int(len(close)),
        "start": str(close.index.min())[:10],
        "end": str(close.index.max())[:10],
        "nan_cells": int(close.isna().sum().sum()),
        "source": "yfinance",
        "session_ist": US_SESSION_IST,
    }
