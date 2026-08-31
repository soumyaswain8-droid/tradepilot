#!/usr/bin/env python3
"""
kite_data — Kite Connect backing for the India data layer.

WHY SWITCH OFF YFINANCE
yfinance scrapes an unofficial endpoint with no SLA. On 2026-08-03 it returned 30
NSE tickers into the US module's cache, and separately a 2-day frame for a 3-year
request. Kite is a licensed feed tied to our own broker account. Measured the same
day across 15 NSE symbols at the close: worst divergence 0.00%, so this is a
reliability upgrade, not a change of numbers.

WHAT THIS MODULE IS NOT
It is not a rewrite of data_nse. It provides Kite-backed implementations returning
the EXACT dict schema data_nse already returns, so callers are untouched. data_nse
delegates here when NSE_DATA_SOURCE=kite and the token is healthy.

THE FALLBACK IS LOUD, ON PURPOSE
Kite access tokens die at 06:00 every day. A silent fallback to yfinance on token
expiry would mean the engines quietly change data source mid-fleet and nobody would
know which feed produced a given day's trades — the fleet's provenance would be
unknowable after the fact. Every fallback logs at ERROR and is counted; health()
exposes the counters so a monitor can page on them.

KITE QUOTE SEMANTICS, verified live 2026-08-04 rather than assumed:
  ohlc.close   is the PREVIOUS day's close, not today's  (RELIANCE 1319 = Aug-3 close)
  ohlc.open    is today's open
  last_price   is the live price
  net_change   came back 0.0 on a stock that had clearly moved — DO NOT TRUST IT.
               change_pct is computed here from last_price vs ohlc.close.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]

# Kite allows up to 500 instruments per quote() call; stay well under it.
QUOTE_BATCH = 200

# RLock, NOT Lock. token_for() holds this while calling client(), which takes it
# again — and threading.Lock is not reentrant, so the thread blocks forever waiting
# for itself. That deadlock hung the first test for 5 minutes and I misdiagnosed it
# as "instruments('NSE') is slow"; measured, that call takes 0.17s.
# RLock alone is not the whole fix: network I/O must not happen while holding it
# either, or 11 engines serialise behind one HTTP request. See token_for().
_lock = threading.RLock()
_kite = None
_kite_day = None            # the date the client was built for
_kite_tok = None
_token_map: dict = {}       # "RELIANCE" -> instrument_token
_token_map_day = None

_stats = {"kite_calls": 0, "kite_ok": 0, "fallbacks": 0, "token_failures": 0,
          "last_error": None, "last_fallback_at": None}


class KiteUnavailable(Exception):
    """Kite cannot serve this request. Raised so callers fall back EXPLICITLY."""


def enabled() -> bool:
    """Kite is opt-in. Default off, so nothing changes until the switch is thrown."""
    return os.environ.get("NSE_DATA_SOURCE", "").strip().lower() == "kite"


def _creds() -> dict:
    """Kite credentials, os.environ taking precedence over .env.

    Delegates to prototype.envcfg, the single .env reader. This function used to carry
    its own parser; so did kite_broker and Floor.start, all slightly different — which
    is how the safety rails ended up honouring .env in one place and ignoring it in
    another. Behaviour here is unchanged; the duplication is not.

    Still read fresh on every call: the access token is rewritten each morning while
    long-running processes are up, and caching it is how a process serves a credential
    that expired hours ago.
    """
    try:
        from prototype.envcfg import get as _cfg
    except ImportError:                       # when imported as top-level v4.kite_data
        from envcfg import get as _cfg        # noqa: F401
    out = {}
    for k in ("KITE_API_KEY", "KITE_API_SECRET", "KITE_ACCESS_TOKEN"):
        v = _cfg(k)
        if v:
            out[k] = v
    return out


def client():
    """Cached KiteConnect, rebuilt whenever the TOKEN CHANGES — not merely daily.

    A daily rebuild is not enough, and this cost a live session to learn. Measured
    2026-08-27: Flask served a request at 08:40, before the morning login. client()
    saw a new calendar day, rebuilt with the PREVIOUS day's dead token, and cached
    that for the rest of the day. The 09:00 login wrote a fresh token to .env and
    nothing noticed. Every quote failed with "Incorrect api_key or access_token"
    until the process was restarted.

    Worse, the failure was invisible: callers fall back to their last good cache, so
    the console showed two stale prices from yesterday next to eighteen blanks —
    which reads as a quiet market rather than a dead credential.

    Keying the cache on the token itself means a refreshed .env is picked up on the
    next call by every long-running process, with no restart.
    """
    global _kite, _kite_day, _kite_tok
    today = datetime.now().date()
    with _lock:
        cur = _creds().get("KITE_ACCESS_TOKEN")
        if _kite is not None and _kite_day == today and _kite_tok == cur:
            return _kite
        c = _creds()
        if not c.get("KITE_API_KEY") or not c.get("KITE_ACCESS_TOKEN"):
            raise KiteUnavailable("KITE_API_KEY / KITE_ACCESS_TOKEN missing from .env")
        try:
            from kiteconnect import KiteConnect
        except ImportError:
            raise KiteUnavailable("kiteconnect not installed")
        k = KiteConnect(api_key=c["KITE_API_KEY"])
        k.set_access_token(c["KITE_ACCESS_TOKEN"])
        _kite, _kite_day, _kite_tok = k, today, c["KITE_ACCESS_TOKEN"]
        return k


def invalidate() -> None:
    """Drop the cached client so the next client() call rebuilds it from .env.

    Defensive, and deliberately blunt. client() already re-keys on the token and that
    logic is verified correct against a controlled rotation — yet on 2026-08-29 a Flask
    process that had been running across a token refresh kept failing every sweep with
    "Incorrect `api_key` or `access_token`" while a freshly started process, reading the
    same .env, succeeded. Five candidate mechanisms were tested and eliminated
    (os.environ override, duplicate kite_data modules, module identity, the re-key
    comparison itself, duplicate Flask processes). The cause is still UNKNOWN.

    Rather than guess, callers that see an auth-shaped failure can call this and get a
    guaranteed rebuild on the next attempt. It costs one wasted client construction in
    the rare case the token really is dead, and it removes a class of failure that
    otherwise needs a human to restart a process.
    """
    global _kite, _kite_day, _kite_tok
    with _lock:
        _kite, _kite_day, _kite_tok = None, None, None


def is_auth_error(e: BaseException) -> bool:
    """Does this exception look like Kite rejecting our credentials?

    Matched on message text because kiteconnect raises TokenException for several
    unrelated conditions and a bare class check would also catch a genuinely expired
    session, which a rebuild cannot fix and should not retry aggressively.
    """
    s = str(e).lower()
    return ("api_key" in s or "access_token" in s or "incorrect" in s
            or "token" in s and "expired" in s)


def _call(fn, what: str):
    """Run a Kite call, classifying failures. A dead token is not the same event as
    a bad symbol, and conflating them is how 'TOKEN DEAD' got printed for a margins
    error on 2026-08-03."""
    _stats["kite_calls"] += 1
    try:
        r = fn()
        _stats["kite_ok"] += 1
        return r
    except Exception as e:
        name = type(e).__name__
        msg = f"{name}: {e}"
        _stats["last_error"] = f"{what}: {msg}"
        if "Token" in name or "token" in str(e).lower() or "api_key" in str(e):
            _stats["token_failures"] += 1
            raise KiteUnavailable(f"kite token rejected on {what} — {msg}")
        raise KiteUnavailable(f"kite {what} failed — {msg}")


def note_fallback(what: str, reason: str) -> None:
    """Record and SHOUT. Silent degradation is the failure mode this whole module
    is meant to remove; a fallback nobody sees is worse than an outage."""
    _stats["fallbacks"] += 1
    _stats["last_fallback_at"] = datetime.now().isoformat(timespec="seconds")
    logger.error(f"DATA FALLBACK to yfinance for {what} — {reason}")


def health() -> dict:
    return {
        "enabled": enabled(),
        "kite_calls": _stats["kite_calls"],
        "kite_ok": _stats["kite_ok"],
        "fallbacks": _stats["fallbacks"],
        "token_failures": _stats["token_failures"],
        "last_error": _stats["last_error"],
        "last_fallback_at": _stats["last_fallback_at"],
    }


def token_alive() -> tuple:
    """(ok, detail). Makes a REAL call — presence of a token string proves nothing,
    which this project has now learned from launchd, from Alpaca, and from Kite."""
    try:
        p = _call(lambda: client().profile(), "profile")
        return True, f"{p.get('user_name')} ({p.get('user_id')})"
    except KiteUnavailable as e:
        return False, str(e)


# ── instrument tokens ───────────────────────────────────────────────────────

def _token_cache_file() -> Path:
    return (ROOT / "prototype" / "data" / "kite_cache" /
            f"instruments_nse_{datetime.now():%Y-%m-%d}.json")


def token_for(symbol: str) -> Optional[int]:
    """NSE symbol -> instrument_token.

    Three layers, cheapest first: process memory, then a per-day disk cache, then
    the API. The disk cache is what makes this viable across 11 engine processes —
    each is a separate interpreter with its own empty memory, so without it every
    engine refetches ~10k rows at startup.

    THE NETWORK CALL DELIBERATELY HAPPENS OUTSIDE THE LOCK. Holding a mutex across
    HTTP means every other thread waits out the request; worse, the first version
    also called client() while holding a non-reentrant Lock, which deadlocked
    against itself. Read state under the lock, do I/O unlocked, publish under the
    lock again.
    """
    global _token_map, _token_map_day
    sym = symbol.upper()
    today = datetime.now().date()

    with _lock:
        if _token_map_day == today and _token_map:
            return _token_map.get(sym)

    # -- unlocked from here: disk read, then network if needed --
    m = {}
    cache = _token_cache_file()
    if cache.exists():
        try:
            import json
            m = {k: int(v) for k, v in json.loads(cache.read_text()).items()}
            logger.info(f"kite: instrument map from disk cache ({len(m)} symbols)")
        except Exception as e:
            logger.warning(f"kite: instrument cache unreadable ({e}); refetching")
            m = {}

    if not m:
        rows = _call(lambda: client().instruments("NSE"), "instruments")
        for r in rows:
            if r.get("segment") == "NSE" and r.get("instrument_type") == "EQ":
                m[str(r.get("tradingsymbol"))] = int(r.get("instrument_token"))
        logger.info(f"kite: fetched {len(m)} NSE equity instruments")
        try:
            import json
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_suffix(".tmp")
            tmp.write_text(json.dumps(m))
            tmp.replace(cache)          # atomic: 11 engines may write concurrently
        except Exception as e:
            logger.warning(f"kite: could not write instrument cache: {e}")

    with _lock:
        _token_map, _token_map_day = m, today
    return m.get(sym)


# ── quotes ──────────────────────────────────────────────────────────────────

def _map_quote(symbol: str, q: dict) -> dict:
    """Kite quote -> data_nse's schema. Field-for-field, no invention."""
    ohlc = q.get("ohlc") or {}
    last = float(q.get("last_price") or 0)
    prev = float(ohlc.get("close") or 0)          # Kite: close == PREVIOUS close
    # net_change is unreliable (observed 0.0 on a stock that had moved), so derive it.
    chg = ((last - prev) / prev * 100) if prev else 0.0
    return {
        "last_price": round(last, 2),
        "open": round(float(ohlc.get("open") or 0), 2),
        "high": round(float(ohlc.get("high") or 0), 2),
        "low": round(float(ohlc.get("low") or 0), 2),
        "prev_close": round(prev, 2),
        "change_pct": round(chg, 2),
        "volume": int(q.get("volume") or 0),
        "symbol": symbol,
        "source": "kite",
    }


def get_quotes(symbols) -> dict:
    """Batch quotes. Symbols that Kite does not return are OMITTED, never zero-filled
    — a silent 0.0 price is how bad fills happen."""
    syms = [str(s).upper().replace(".NS", "") for s in symbols]
    out = {}
    for i in range(0, len(syms), QUOTE_BATCH):
        chunk = syms[i:i + QUOTE_BATCH]
        keys = [f"NSE:{s}" for s in chunk]
        res = _call(lambda: client().quote(keys), "quote")
        for s in chunk:
            q = res.get(f"NSE:{s}")
            if not q:
                continue
            m = _map_quote(s, q)
            if m["last_price"] <= 0:      # a zero price is absence, not a price
                continue
            out[s] = m
    return out


def get_index(name: str = "NIFTY 50", exchange: str = "NSE") -> dict:
    """Index level. The EXCHANGE matters and is not cosmetic: SENSEX is a BSE index,
    so "NSE:SENSEX" raises KeyError. Getting this wrong on 2026-08-04 pushed SENSEX
    onto the yfinance fallback, which reported +0.47% against a 2026-07-31 baseline
    when the real move was -0.29%. A wrong exchange prefix does not fail loudly — it
    fails over to a worse source.
    """
    key = f"{exchange}:{name}"
    q = _call(lambda: client().quote([key]), "index quote")
    d = q.get(key)
    if not d:
        raise KiteUnavailable(f"kite returned no data for index {key}")
    ohlc = d.get("ohlc") or {}
    last = float(d.get("last_price") or 0)
    prev = float(ohlc.get("close") or 0)
    if last <= 0:
        raise KiteUnavailable(f"kite returned a non-positive level for {name}")
    return {
        "last_price": round(last, 2),
        "prev_close": round(prev, 2),
        "change_pct": round(((last - prev) / prev * 100) if prev else 0.0, 2),
        "open": round(float(ohlc.get("open") or 0), 2),
        "high": round(float(ohlc.get("high") or 0), 2),
        "low": round(float(ohlc.get("low") or 0), 2),
        "symbol": name,
        "source": "kite",
    }


def get_candles(symbol: str, interval: str = "5minute", days: int = 1):
    """Intraday OHLCV as a DataFrame with data_nse's column names.

    Kite's historical API needs an instrument_token and dates, not a period string.
    Returns None (never an empty frame) when there is nothing, so callers can tell
    'no data' from 'a frame of zeros'.
    """
    from datetime import timedelta
    import pandas as pd

    tok = token_for(symbol)
    if not tok:
        raise KiteUnavailable(f"no NSE instrument token for {symbol}")
    to_d = datetime.now()
    from_d = to_d - timedelta(days=max(1, days))
    rows = _call(lambda: client().historical_data(tok, from_d, to_d, interval),
                 f"historical {symbol}")
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df = df.rename(columns={"date": "Datetime", "open": "Open", "high": "High",
                            "low": "Low", "close": "Close", "volume": "Volume"})
    if "Datetime" in df.columns:
        df = df.set_index("Datetime")
    return df
