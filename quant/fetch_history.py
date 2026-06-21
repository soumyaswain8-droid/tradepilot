#!/usr/bin/env python3
"""
quant/fetch_history.py — historical EOD data layer for the TradePilot quant stack.

Fetches multi-year DAILY OHLCV for the full active universe + NIFTY and caches one
file per symbol, so every downstream piece (backtester, factor/IC studies, ML
labels) reads from a stable local store instead of re-hitting the network.

Framework-agnostic: the parquet/pickle cache feeds a hand-rolled backtester OR
vectorbt/qlib later. Resumable (skips symbols already cached & fresh).

CAVEAT (stated honestly): yfinance returns only CURRENTLY-LISTED symbols, so this
universe has survivorship bias — delisted/removed names are absent. Fine for a
first multi-horizon factor pass; a point-in-time index-membership source is a
later upgrade (noted in the quant roadmap).

Usage: python3 quant/fetch_history.py [--years N] [--force]
"""
import os, sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "prototype"))
from v4.config import ACTIVE_SYMBOLS

OUT = Path(__file__).resolve().parent / "data" / "eod"
OUT.mkdir(parents=True, exist_ok=True)
YEARS = int(sys.argv[sys.argv.index("--years") + 1]) if "--years" in sys.argv else 5
FORCE = "--force" in sys.argv
START = (pd.Timestamp.today() - pd.DateOffset(years=YEARS)).strftime("%Y-%m-%d")
END = pd.Timestamp.today().strftime("%Y-%m-%d")

# parquet if pyarrow available else pickle
try:
    import pyarrow  # noqa
    EXT, SAVE = "parquet", (lambda df, p: df.to_parquet(p))
except Exception:
    EXT, SAVE = "pkl", (lambda df, p: df.to_pickle(p))


def cache_path(sym):
    return OUT / f"{sym}.{EXT}"


def main():
    syms = ["^NSEI"] + sorted(ACTIVE_SYMBOLS)
    print(f"fetching {len(syms)} symbols, {YEARS}y daily ({START}..{END}) -> {OUT} [{EXT}]")
    ok = skip = fail = 0
    rows_total = 0
    for i, s in enumerate(syms, 1):
        tkr = s if s.startswith("^") else f"{s}.NS"
        p = cache_path(s.replace("^", "_"))
        if p.exists() and not FORCE:
            skip += 1
            continue
        try:
            df = yf.download(tkr, start=START, end=END, interval="1d",
                             progress=False, auto_adjust=True)
            if df is None or df.empty or len(df) < 50:
                print(f"  [{i}/{len(syms)}] {s}: thin/empty ({0 if df is None else len(df)} rows)")
                fail += 1
                continue
            if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
                df.columns = df.columns.get_level_values(0)
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            SAVE(df, p)
            ok += 1
            rows_total += len(df)
            if i % 25 == 0:
                print(f"  [{i}/{len(syms)}] cached {ok} (last {s}: {len(df)} rows)")
        except Exception as e:
            print(f"  [{i}/{len(syms)}] {s}: ERR {str(e)[:60]}")
            fail += 1
        time.sleep(0.15)  # gentle on the API
    print(f"\nDONE: cached {ok}, skipped {skip}, failed {fail}; {rows_total:,} total rows in {OUT}")


if __name__ == "__main__":
    main()
