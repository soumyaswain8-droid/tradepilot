#!/usr/bin/env python3
"""
bars — historical price data that does NOT require a Kite token.

WHY THIS EXISTS. NSE is closed at weekends, which is when research and development
actually happen, and Kite access tokens expire daily. So the natural time to run a
backtest is exactly the time there is no valid credential — and refreshing one buys
nothing, because on a non-trading day Kite serves stale Friday closes anyway.

Worse, Kite's quote() returns an EMPTY DICT on a non-trading day rather than raising.
A pipeline built on it reports a confident zero that looks exactly like a measurement.
On 2026-08-29 that nearly cost an hour of debugging a system behaving correctly.

Daily OHLCV for the whole NSE is already on disk in quant/data/bhavcopy (1,300+ daily
files, five years). Nothing about a historical backtest needs the network. This module
makes that the default path and reaches for Kite only when the request genuinely is
not covered offline.

THE ONE RULE THIS MODULE ENFORCES: it always says which source answered. The recurring
defect in this codebase is silent substitution — a broken or degraded component
returning something shaped like a real answer. An offline run must announce it is
offline rather than quietly resembling a live one.

    from quant.bars import daily, coverage

    df = daily("HFCL", "2026-01-01", "2026-06-30")     # offline, no token needed
    print(df.attrs["source"])                          # -> "bhavcopy (offline)"

Cache: the first call consolidates the bhavcopy CSVs into a single parquet, which takes
about a minute. Every later call is a fast filtered read.
"""
from __future__ import annotations

import glob
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
BHAV = ROOT / "quant" / "data" / "bhavcopy"
CACHE = ROOT / "quant" / "data" / "bhavcopy_daily.parquet"

# Only EQ carries the ordinary equity session. BE is the trade-for-trade segment, where
# every order settles individually and the price series is not comparable.
SERIES_KEEP = {"EQ"}

_MEM: pd.DataFrame | None = None


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    """NSE ships these headers with leading spaces — ' SERIES', ' CLOSE_PRICE'."""
    df.columns = [c.strip().upper() for c in df.columns]
    return df


def build_cache(verbose: bool = True) -> Path:
    """Consolidate the daily bhavcopy CSVs into one parquet. Idempotent."""
    from quant.diskguard import require_free
    require_free(2.0, "consolidating ~1,300 bhavcopy files")

    files = sorted(glob.glob(str(BHAV / "*.csv")) + glob.glob(str(BHAV / "*.CSV")))
    if not files:
        raise FileNotFoundError(f"no bhavcopy files in {BHAV}")
    if verbose:
        print(f"  building daily cache from {len(files)} bhavcopy files...", flush=True)

    frames = []
    for i, f in enumerate(files):
        try:
            d = _norm(pd.read_csv(f))
        except Exception:
            continue                      # a truncated download must not kill the build
        if "SERIES" not in d.columns:
            continue
        d = d[d["SERIES"].astype(str).str.strip().isin(SERIES_KEEP)]
        if d.empty:
            continue
        keep = {"SYMBOL": "symbol", "DATE1": "date", "OPEN_PRICE": "open",
                "HIGH_PRICE": "high", "LOW_PRICE": "low", "CLOSE_PRICE": "close",
                "PREV_CLOSE": "prev_close", "TTL_TRD_QNTY": "volume",
                "TURNOVER_LACS": "turnover_lakh"}
        have = {k: v for k, v in keep.items() if k in d.columns}
        d = d[list(have)].rename(columns=have)
        d["symbol"] = d["symbol"].astype(str).str.strip()
        frames.append(d)
        if verbose and i and i % 300 == 0:
            print(f"    {i}/{len(files)}", flush=True)

    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"].astype(str).str.strip(),
                                 format="mixed", dayfirst=True, errors="coerce")
    out = out.dropna(subset=["date"]).sort_values(["symbol", "date"])
    out["symbol"] = out["symbol"].astype("category")
    out.to_parquet(CACHE, index=False)
    if verbose:
        print(f"  cached {len(out):,} rows -> {CACHE.name} "
              f"({CACHE.stat().st_size/1e6:.0f} MB)", flush=True)
    return CACHE


def _load() -> pd.DataFrame:
    global _MEM
    if _MEM is None:
        if not CACHE.exists():
            build_cache()
        _MEM = pd.read_parquet(CACHE)
    return _MEM


def coverage() -> dict:
    """What the offline store actually holds — check this before assuming a gap."""
    d = _load()
    return {"rows": len(d), "symbols": int(d["symbol"].nunique()),
            "first": str(d["date"].min().date()), "last": str(d["date"].max().date()),
            "source": str(CACHE)}


def daily(symbol: str, start=None, end=None, allow_kite: bool = True) -> pd.DataFrame:
    """Daily OHLCV for one symbol. Offline first; Kite only if genuinely uncovered.

    The returned frame carries df.attrs["source"], and callers are expected to surface
    it. `allow_kite=False` forces a hard offline run, which is what a weekend backtest
    should use — it fails loudly rather than silently reaching for a dead credential.
    """
    d = _load()
    sym = symbol.strip().upper().replace(".NS", "")
    out = d[d["symbol"] == sym]
    if start is not None:
        out = out[out["date"] >= pd.Timestamp(start)]
    if end is not None:
        out = out[out["date"] <= pd.Timestamp(end)]
    out = out.reset_index(drop=True)

    # Is the request actually covered? "Covered" means the store reaches the requested
    # end date, not merely that some rows came back — a partial answer presented as a
    # whole one is the silent-substitution failure this module exists to prevent.
    store_last = d["date"].max()
    wants_recent = end is not None and pd.Timestamp(end) > store_last
    if not out.empty and not wants_recent:
        out.attrs["source"] = "bhavcopy (offline)"
        return out

    if not allow_kite:
        raise LookupError(
            f"{sym}: offline store covers {d['date'].min().date()} to "
            f"{store_last.date()}"
            + (f", but {pd.Timestamp(end).date()} was requested" if wants_recent else
               " and holds no rows for this symbol")
            + ". Refresh the bhavcopy, or pass allow_kite=True to go live.")

    from prototype.v4 import kite_data as kd
    tok = kd.token_for(sym)
    if not tok:
        raise LookupError(f"{sym}: not in the offline store and no Kite instrument token")
    rows = kd.client().historical_data(
        tok, pd.Timestamp(start or store_last).to_pydatetime(),
        pd.Timestamp(end or datetime.now()).to_pydatetime(), "day")
    live = pd.DataFrame(rows)
    if not live.empty:
        live = live.rename(columns={"date": "date"})
        live["symbol"] = sym
    live.attrs["source"] = "kite (live)"
    return live


def main() -> int:
    if "--build" in sys.argv:
        build_cache()
    c = coverage()
    print(f"  offline daily store: {c['rows']:,} rows, {c['symbols']:,} symbols, "
          f"{c['first']} to {c['last']}")
    print("  no Kite token required for anything inside that range.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
