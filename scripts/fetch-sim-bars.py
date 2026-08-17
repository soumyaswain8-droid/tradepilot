#!/usr/bin/env python3
"""
fetch-sim-bars — build the full-simulation bar cache from Kite.

3.5 months of 5m bars (2026-05-01 → today) for the NIFTY-200 + index, two chunked
requests per symbol (Kite caps ~100 days per 5minute request). Written to
prototype/data/simcache/ as parquet, tz-aware IST, one file per symbol.

This exists because the falsification cache (waterfall/) is yfinance-fed and capped
at 60 days — the strategy-search simulation wants the longer window and the
licensed feed. Verified before writing: Kite serves 5minute back to at least March.
"""
import sys, time, warnings
warnings.filterwarnings("ignore")
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v4 import kite_data as kd
from prototype.v4.config import ACTIVE_SYMBOLS_YF

OUT = ROOT / "prototype" / "data" / "simcache"
OUT.mkdir(parents=True, exist_ok=True)
START = datetime(2026, 5, 1)

def fetch(sym: str):
    tok = kd.token_for(sym)
    if not tok:
        return None
    rows = []
    lo = START
    while lo < datetime.now():
        hi = min(lo + timedelta(days=99), datetime.now())
        try:
            rows += kd.client().historical_data(tok, lo, hi, "5minute")
        except Exception as e:
            print(f"  {sym}: {type(e).__name__} {str(e)[:50]}", flush=True)
            return None
        lo = hi + timedelta(days=1)
        time.sleep(0.25)          # stay far under Kite's rate limit
    if not rows:
        return None
    df = pd.DataFrame([{"dt": r["date"], "Open": r["open"], "High": r["high"],
                        "Low": r["low"], "Close": r["close"], "Volume": r["volume"]}
                       for r in rows]).drop_duplicates("dt").set_index("dt").sort_index()
    return df

def main():
    syms = [s.replace(".NS", "") for s in ACTIVE_SYMBOLS_YF] + ["NIFTY 50"]
    done = skip = 0
    for i, s in enumerate(syms, 1):
        name = "NIFTY50" if s == "NIFTY 50" else s
        f = OUT / f"{name}_5m.parquet"
        if f.exists() and f.stat().st_size > 10000:
            skip += 1
            continue
        if s == "NIFTY 50":
            try:
                tok = 256265   # NIFTY 50 index token
                rows = []
                lo = START
                while lo < datetime.now():
                    hi = min(lo + timedelta(days=99), datetime.now())
                    rows += kd.client().historical_data(tok, lo, hi, "5minute")
                    lo = hi + timedelta(days=1)
                df = pd.DataFrame([{"dt": r["date"], "Open": r["open"], "High": r["high"],
                                    "Low": r["low"], "Close": r["close"],
                                    "Volume": r.get("volume", 0)} for r in rows]
                                  ).drop_duplicates("dt").set_index("dt").sort_index()
            except Exception as e:
                print(f"  NIFTY50: {e}", flush=True); continue
        else:
            df = fetch(s)
        if df is None or df.empty:
            continue
        df.to_parquet(f)
        done += 1
        if i % 20 == 0:
            print(f"  {i}/{len(syms)} ({done} fetched, {skip} cached)", flush=True)
    print(f"DONE: {done} fetched, {skip} already cached", flush=True)

if __name__ == "__main__":
    main()
