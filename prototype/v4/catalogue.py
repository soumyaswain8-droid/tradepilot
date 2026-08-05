#!/usr/bin/env python3
"""
catalogue — every NSE-listed stock, for BROWSING. Not for trading.

THE DISTINCTION THIS FILE EXISTS TO ENFORCE
Soumya: "our motto is to make profit, if we have to have all the listed stocks in our
platform to offer to the users". Those are two different universes and conflating
them is how a platform loses money being helpful:

  BROWSE universe   every listed stock, so a user searching for anything finds it.
                    Completeness is the whole point. A missing stock makes the
                    platform look broken. This file.

  TRADE universe    what the engines are allowed to buy. Liquidity is the whole
                    point, because a fill you cannot get at the price you modelled
                    is a loss. prototype/v4/config.py ACTIVE_SYMBOLS_YF (NIFTY 200)
                    and quant/universe_expanded.txt (446). NOT this file.

WHY THE SPLIT IS NOT TIMIDITY — measured on 2026-08-05 across all 4,353 main-board
NSE equities:

    median turnover    Rs   0.13 Cr      <- the typical listed stock
    p75                Rs   2.64 Cr
    p90                Rs  15.52 Cr
    p99                Rs 185.07 Cr
    871 stocks (27%)   ZERO turnover — did not trade even once today

Half the market moves under Rs 13 lakh a day. An engine that "found a signal" in a
stock with no buyers on the other side has found a way to lose money slowly. So the
catalogue serves the user's search box and the engines keep their liquidity gate.

Every record carries `tradeable` and `tier` so the UI can say WHY a stock is
browse-only rather than silently offering something the engines will never touch.

TIERS ARE A SINGLE-DAY SNAPSHOT — do not size a universe change off them alone.
Turnover is today's, so a stock having an unusual day is ranked as if that were
normal. Checked against 10-day average volume on 2026-08-05: NIACL showed Rs 307 Cr
on 6.4x its usual volume and MOREPENLAB Rs 427 Cr on 3.5x — both one-off, while
MANIPALHOS, RBA and OLAELEC were genuinely at their normal level. Good enough to
label a search result; NOT good enough to promote a stock into the trading universe.
That decision needs an average over weeks, which is a separate job.

A full refresh of all 4,353 symbols takes ~2 seconds against Kite, so this is cached
by day rather than precomputed into a file that would go stale.
"""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "prototype" / "data" / "catalogue"

# NSE series codes that are NOT ordinary main-board equity. A hyphen alone means
# nothing — BAJAJ-AUTO and NAM-INDIA are perfectly normal symbols, and an earlier
# filter that keyed on "-" flagged a NIFTY 50 constituent as delisted.
SERIES_SUFFIXES = {"BE", "BZ", "SM", "SG", "ST", "GS", "TB", "SF", "GB", "IV", "ND"}

# Turnover tiers, in rupees. Chosen against the measured distribution above, not
# picked round: TIER1 sits near our own trading book's median, TIER2 near the
# market's p90, TIER3 near p75. Below that a stock is browse-only.
TIER1 = 15e7      # Rs 15 Cr+   liquid enough for the engines
TIER2 = 3e7       # Rs 3 Cr+    tradeable with care
TIER3 = 0.5e7     # Rs 0.5 Cr+  thin
_lock = threading.Lock()
_cache = {"day": None, "rows": None}


def _tier(turnover: float) -> tuple:
    if turnover >= TIER1:
        return "liquid", True
    if turnover >= TIER2:
        return "moderate", True
    if turnover >= TIER3:
        return "thin", False
    return "illiquid", False


def _trade_universe() -> set:
    """Symbols the engines may actually trade — read from the real config, never
    duplicated here. A hardcoded copy would drift the moment either list changed."""
    out = set()
    try:
        from prototype.v4.config import ACTIVE_SYMBOLS_YF
        out |= {s.replace(".NS", "").upper() for s in ACTIVE_SYMBOLS_YF}
    except Exception as e:
        logger.warning(f"catalogue: could not read ACTIVE_SYMBOLS_YF: {e}")
    f = ROOT / "quant" / "universe_expanded.txt"
    if f.exists():
        out |= {l.strip().replace(".NS", "").upper() for l in f.read_text().splitlines()
                if l.strip() and not l.startswith("#")}
    return out


def build(with_quotes: bool = True) -> list:
    """Every main-board NSE equity, with live price and turnover tier."""
    from prototype.v4 import kite_data as kd

    rows = kd._call(lambda: kd.client().instruments("NSE"), "instruments")
    eq = [r for r in rows
          if r.get("segment") == "NSE" and r.get("instrument_type") == "EQ"]
    main = [r for r in eq
            if not (("-" in r["tradingsymbol"])
                    and r["tradingsymbol"].rsplit("-", 1)[1] in SERIES_SUFFIXES)]

    quotes = {}
    if with_quotes:
        syms = [r["tradingsymbol"] for r in main]
        for i in range(0, len(syms), 200):
            try:
                quotes.update(kd.get_quotes(syms[i:i + 200]))
            except Exception as e:
                logger.warning(f"catalogue: quote batch failed: {e}")

    tradeable = _trade_universe()
    out = []
    for r in main:
        s = r["tradingsymbol"].upper()
        q = quotes.get(s) or {}
        px = float(q.get("last_price") or 0)
        vol = int(q.get("volume") or 0)
        tv = px * vol
        tier, liquid_enough = _tier(tv)
        out.append({
            "symbol": s,
            "name": r.get("name") or s,
            "token": r.get("instrument_token"),
            "lot_size": r.get("lot_size"),
            "price": round(px, 2),
            "change_pct": q.get("change_pct", 0),
            "volume": vol,
            "turnover": round(tv, 2),
            "tier": tier,
            # in_engines: the engines actually scan it today
            # tradeable  : liquid enough that trading it would be reasonable
            "in_engines": s in tradeable,
            "tradeable": liquid_enough,
        })
    out.sort(key=lambda r: -r["turnover"])
    return out


def all_stocks(refresh: bool = False) -> list:
    """Cached per calendar day. Cheap enough (~2s) that a daily rebuild is fine, and
    a day-keyed cache cannot serve yesterday's list after a delisting."""
    today = datetime.now().strftime("%Y-%m-%d")
    with _lock:
        if not refresh and _cache["day"] == today and _cache["rows"]:
            return _cache["rows"]
    rows = build()
    with _lock:
        _cache["day"], _cache["rows"] = today, rows
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_DIR / f".{today}.tmp"
        tmp.write_text(json.dumps(rows))
        tmp.replace(CACHE_DIR / f"{today}.json")
    except Exception as e:
        logger.warning(f"catalogue: could not persist: {e}")
    return rows


def search(q: str, limit: int = 50) -> list:
    """Symbol/name search. Exact symbol first, then prefix, then substring — so
    typing RELIANCE returns RELIANCE, not RELIANCEPOWER."""
    q = (q or "").strip().upper()
    rows = all_stocks()
    if not q:
        return rows[:limit]
    exact = [r for r in rows if r["symbol"] == q]
    pref = [r for r in rows if r["symbol"].startswith(q) and r["symbol"] != q]
    sub = [r for r in rows
           if q not in r["symbol"] and q in str(r.get("name", "")).upper()]
    inner = [r for r in rows if q in r["symbol"] and not r["symbol"].startswith(q)]
    seen, out = set(), []
    for group in (exact, pref, inner, sub):
        for r in group:
            if r["symbol"] not in seen:
                seen.add(r["symbol"])
                out.append(r)
    return out[:limit]


def stats() -> dict:
    rows = all_stocks()
    by_tier = {}
    for r in rows:
        by_tier[r["tier"]] = by_tier.get(r["tier"], 0) + 1
    return {
        "listed": len(rows),
        "with_price": sum(1 for r in rows if r["price"] > 0),
        "by_tier": by_tier,
        "tradeable": sum(1 for r in rows if r["tradeable"]),
        "in_engines": sum(1 for r in rows if r["in_engines"]),
        "as_of": datetime.now().isoformat(timespec="seconds"),
    }
