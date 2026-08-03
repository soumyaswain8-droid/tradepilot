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

import hashlib
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

# COMPLETENESS GUARD (added 2026-08-03) ---------------------------------------
# On 2026-08-03 the coverage panel reported 12,716 missing cells on a 25-symbol /
# 3-year window that returns 0 on every repeat. The transient was never reproduced.
# What the incident DID prove is the real defect: get_history() rejected only an
# EMPTY frame, so a partially-filled one flowed straight into signals_us and got
# scored. history_stats() measured nan_cells and acted on nothing. The only
# component that noticed was a dashboard, after the fact, needing a human to look.
#
# The distinction that makes this guard correct: a NaN BEFORE a symbol's first
# real print is legitimate (a 2024 listing has no 2023 prices), while a NaN
# BETWEEN two real prints is a hole. A flat NaN threshold cannot tell them apart —
# it would drop every recent listing while still passing a partial megacap fetch.
# So we measure leading absence and interior gaps separately, and only interior
# gaps count against data quality.
MAX_SYMBOL_INTERIOR_GAP_PCT = 0.02   # per symbol: >2% holes after listing -> drop it
MIN_SYMBOL_COVERAGE_PCT = 0.60       # per symbol: <60% of window present -> drop it
MAX_FRAME_INTERIOR_GAP_PCT = 0.05    # whole frame: >5% holes -> partial fetch, retry

# EXTENT GUARD. The gap checks above measure DENSITY — holes inside the window.
# They say nothing about the window's LENGTH, and a truncated fetch has no holes
# at all. On 2026-08-03 the UI rendered "TRADING DAYS 2 / 2026-07-31 -> 2026-08-03"
# with gaps 0 and dropped 0 — every density check green on a frame holding two days
# of a three-year request. Density and extent are independent failure modes and
# each needs its own assertion.
TRADING_DAYS_PER_YEAR = 252
MIN_EXTENT_PCT = 0.80                # <80% of the expected span -> truncated, retry

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

def close_block(df):
    """The Close columns as a symbol-per-column DataFrame.

    yfinance changes shape with symbol count: many symbols give a MultiIndex
    (field, symbol); one symbol gives flat columns and a Series. Callers that
    assume one shape break silently on the other, so normalise here once.
    """
    import pandas as pd
    if df is None or getattr(df, "empty", True):
        return None
    close = df["Close"] if "Close" in df else df
    if isinstance(close, pd.Series):
        close = close.to_frame()
    return close


def audit_frame(df) -> dict:
    """Per-symbol data-quality report, splitting leading absence from interior gaps.

    leading  — NaNs before the symbol's first real print. Legitimate: the stock had
               not listed yet. Never counted as a defect.
    interior — NaNs after the first real print. A hole in data that should exist,
               which is what a partial or throttled fetch looks like.
    """
    close = close_block(df)
    if close is None or close.empty:
        return {"ok": False, "reason": "empty", "symbols": {}}

    rows = len(close)
    report, interior_total, expected_total = {}, 0, 0
    for sym in close.columns:
        col = close[sym]
        first = col.first_valid_index()
        if first is None:
            report[str(sym)] = {"rows": 0, "coverage_pct": 0.0,
                                "interior_gaps": 0, "interior_pct": 1.0, "first": None}
            continue
        live = col.loc[first:]
        gaps = int(live.isna().sum())
        interior_total += gaps
        expected_total += len(live)
        report[str(sym)] = {
            "rows": int(len(live)),
            "coverage_pct": round(len(live) / rows, 4),
            "interior_gaps": gaps,
            "interior_pct": round(gaps / len(live), 4) if len(live) else 1.0,
            "first": str(first)[:10],
        }
    return {
        "ok": True,
        "trading_days": rows,
        "symbols": report,
        "interior_gaps": interior_total,
        "interior_pct": round(interior_total / expected_total, 4) if expected_total else 0.0,
    }


def _download(syms: list, years: int, interval: str):
    import yfinance as yf
    return yf.download(syms, period=f"{years}y", interval=interval,
                       progress=False, auto_adjust=False,
                       group_by="column", threads=True)


def get_history(symbols: Iterable[str], years: int = 3, interval: str = "1d",
                strict: bool = True):
    """Daily (or other-interval) OHLCV for `symbols` over `years`.

    Returns a pandas DataFrame or None if the fetch fails. auto_adjust=False keeps
    raw closes AND gives us Adj Close, so corporate actions can be handled
    explicitly — the India stack's corp-action gap is a known open problem and this
    module should not inherit it.

    With strict=True (the default) the frame is audited before it is returned:
      - symbols with too many interior gaps, or too little history, are DROPPED
        (never filled — a fabricated price is how bad fills happen)
      - a frame whose overall interior-gap rate is too high is treated as a partial
        fetch and retried ONCE; if it fails again the call returns None
    strict=False bypasses the audit and is for diagnostics only — never for the
    engine, which must not trade on unvalidated data.
    """
    syms = [s.upper() for s in symbols]
    if not syms:
        return None
    try:
        import yfinance as yf  # noqa: F401  (import here so absence is a clean error)
    except ImportError:
        logger.error("yfinance not installed")
        return None

    for attempt in (1, 2):
        try:
            df = _download(syms, years, interval)
        except Exception as e:
            logger.error(f"get_history failed: {type(e).__name__}: {e}")
            return None
        if df is None or df.empty:
            logger.error("yfinance returned empty history")
            return None
        if not strict:
            return df

        audit = audit_frame(df)
        if not audit.get("ok"):
            logger.error("get_history: frame failed audit (empty close block)")
            return None

        # EXTENT first: a truncated frame is uniformly short, so every density
        # metric on it reads perfect. Check length before believing anything else.
        if interval == "1d":
            expected = int(years * TRADING_DAYS_PER_YEAR)
            got_days = int(audit["trading_days"])
            if got_days < expected * MIN_EXTENT_PCT:
                logger.warning(
                    f"get_history: truncated fetch — {got_days} trading days for a "
                    f"{years}y request (expected ~{expected}), attempt {attempt}/2")
                if attempt == 1:
                    continue
                logger.error("get_history: truncated fetch persisted after retry — "
                             "refusing data")
                return None

        # A frame-wide gap rate means the FETCH was partial, not that these
        # particular symbols are bad. Retry the whole thing rather than
        # amputating symbols that are probably fine.
        if audit["interior_pct"] > MAX_FRAME_INTERIOR_GAP_PCT:
            logger.warning(
                f"get_history: partial fetch — {audit['interior_gaps']} interior gaps "
                f"({audit['interior_pct']:.1%} > {MAX_FRAME_INTERIOR_GAP_PCT:.0%}), "
                f"attempt {attempt}/2")
            if attempt == 1:
                continue
            logger.error("get_history: partial fetch persisted after retry — refusing data")
            return None

        bad = [s for s, r in audit["symbols"].items()
               if r["interior_pct"] > MAX_SYMBOL_INTERIOR_GAP_PCT
               or r["coverage_pct"] < MIN_SYMBOL_COVERAGE_PCT]
        if bad:
            logger.warning(f"get_history: dropping {len(bad)} symbol(s) on data quality: "
                           f"{', '.join(sorted(bad)[:10])}"
                           f"{' …' if len(bad) > 10 else ''}")
            try:
                keep = [s for s in syms if s not in bad]
                if not keep:
                    logger.error("get_history: every symbol failed the quality gate")
                    return None
                if hasattr(df.columns, "levels") and df.columns.nlevels > 1:
                    df = df.loc[:, df.columns.get_level_values(1).isin(keep)]
                elif len(syms) > 1:
                    df = df[[c for c in df.columns if c in keep]]
            except Exception as e:
                logger.error(f"get_history: could not drop bad symbols: "
                             f"{type(e).__name__}: {e} — refusing data")
                return None
        return df
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
    # CACHE KEY: sha1, NOT hash(). ------------------------------------------
    # This was `abs(hash(tuple(syms))) % 10**10`. Python randomises str hashing per
    # process (PYTHONHASHSEED), so that key was a function of (symbols, process
    # instance) — not of the symbols. Two consequences, found live on 2026-08-03:
    #   benign    same symbols after a restart -> different key -> pointless refetch
    #   DANGEROUS different symbols -> colliding key -> the WRONG payload served
    # The second one actually fired: /api/us/quotes returned 30 of 30 NSE tickers
    # (ADANIGREEN.NS, ALKEM.NS ...) priced in "$" on the US tab, because two files
    # in the US cache dir held India data under hash-derived names.
    key = f"quotes_{hashlib.sha1(','.join(syms).encode()).hexdigest()[:16]}.json"
    cached = _read_cache(key, QUOTE_TTL_SECONDS)
    # A stable key is necessary but NOT sufficient: a cache file is a claim about
    # its contents, and this module's whole premise is that claims get verified.
    # Anything the cache returns that was not asked for is treated as poisoned.
    if cached is not None:
        stray = [k for k in cached if k.upper() not in set(syms)]
        if stray:
            logger.error(f"us_cache POISONED — {key} holds {len(stray)} symbol(s) that "
                         f"were not requested ({', '.join(map(str, stray[:5]))}); "
                         f"discarding and refetching")
            try:
                (_cache_dir_today() / key).unlink()
            except Exception:
                pass
        else:
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
    requested = len([s for s in symbols])
    df = get_history(symbols, years=years)
    if df is None:
        return {"ok": False, "error": "fetch failed or failed the completeness gate",
                "requested": requested}
    close = close_block(df)
    if close is None or close.empty:
        return {"ok": False, "error": "no usable close data", "requested": requested}

    audit = audit_frame(df)
    returned = int(close.shape[1])
    # Report leading absence and interior gaps SEPARATELY. A raw nan_cells count
    # conflates "this stock listed in 2024" with "the feed gave us holes", and the
    # second is the only one that means anything is wrong.
    return {
        "ok": True,
        "symbols": returned,
        "requested": requested,
        "dropped": max(0, requested - returned),   # surfaced, never silent
        "trading_days": int(len(close)),
        "start": str(close.index.min())[:10],
        "end": str(close.index.max())[:10],
        "nan_cells": int(close.isna().sum().sum()),       # kept for continuity
        "interior_gaps": audit.get("interior_gaps", 0),   # the number that matters
        "interior_pct": audit.get("interior_pct", 0.0),
        "short_history": sum(1 for r in audit.get("symbols", {}).values()
                             if r["coverage_pct"] < 0.99),
        "source": "yfinance",
        "session_ist": US_SESSION_IST,
    }
