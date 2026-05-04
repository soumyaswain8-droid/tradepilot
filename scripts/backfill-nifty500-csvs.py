#!/usr/bin/env python3
"""Backfill 2-year daily OHLCV CSVs for Nifty 500 stocks not in our current universe.

Safe by default:
  - Writes ONLY to prototype/data/{SYMBOL}_NS.csv for NEW symbols
  - Skips symbols that already have a CSV (won't overwrite Nifty 200 files)
  - --dry-run mode lists what it WOULD do without writing anything
  - Gentle rate limiting (3s between Yahoo calls)

Usage:
    python3 scripts/backfill-nifty500-csvs.py --dry-run     # list only
    python3 scripts/backfill-nifty500-csvs.py               # full backfill
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "prototype" / "data"

# Nifty 500 extras — symbols in Nifty 500 but NOT in our current Nifty 200
# Seed list: top 30 most-liquid Nifty 500 extras for initial coverage.
# Full list can be expanded after first run proves safe.
NIFTY_500_EXTRAS = [
    "ZYDUSWELL", "VENKEYS", "RBLBANK", "IEX", "SOBHA",
    "IBREALEST", "SADBHAV", "RAJESHEXPO", "GRANULES", "LTIM",
    "KAYNES", "DALBHARAT", "BANDHANBNK", "GODREJCP", "HAVELLS",
    "DEEPAKNTR", "DIXON", "ESCORTS", "GSPL", "HONAUT",
    "IDFCFIRSTB", "IRCTC", "JUBLFOOD", "LALPATHLAB", "METROPOLIS",
    "MRF", "NAM-INDIA", "OBEROIRLTY", "PAGEIND", "PNB",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be done, make no writes")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit to N symbols (0 = all)")
    parser.add_argument("--delay", type=float, default=3.0,
                        help="Seconds between API calls (default 3s)")
    args = parser.parse_args()

    symbols = NIFTY_500_EXTRAS
    if args.limit > 0:
        symbols = symbols[: args.limit]

    # Check which symbols already have CSVs (we NEVER overwrite)
    existing = set()
    for csv in DATA_DIR.glob("*_NS.csv"):
        existing.add(csv.stem.replace("_NS", ""))

    to_fetch = [s for s in symbols if s not in existing]
    already = [s for s in symbols if s in existing]

    print(f"Target universe: {len(symbols)} Nifty 500 extras")
    print(f"Already present: {len(already)}  ({'' if args.dry_run else 'will skip'})")
    print(f"To fetch:        {len(to_fetch)}")
    if already:
        print(f"  skip list: {already[:10]}{'...' if len(already) > 10 else ''}")

    if args.dry_run:
        print("\n[DRY-RUN] Would write:")
        for s in to_fetch[:20]:
            target = DATA_DIR / f"{s}_NS.csv"
            print(f"  would create: {target}")
        if len(to_fetch) > 20:
            print(f"  ...and {len(to_fetch)-20} more")
        print(f"\n[DRY-RUN] No files written. Estimated time for full run: {len(to_fetch)*args.delay/60:.1f} min")
        return 0

    # Real run
    try:
        import yfinance as yf
    except ImportError:
        print("ERROR: yfinance not installed. pip install yfinance")
        return 1

    end = datetime.now()
    start = end - timedelta(days=730)

    success = 0
    fail = 0
    for i, sym in enumerate(to_fetch, 1):
        yf_ticker = f"{sym}.NS"
        target = DATA_DIR / f"{sym}_NS.csv"
        try:
            print(f"[{i}/{len(to_fetch)}] {sym}...", end=" ", flush=True)
            df = yf.download(yf_ticker, start=start.strftime("%Y-%m-%d"),
                             end=end.strftime("%Y-%m-%d"), progress=False,
                             auto_adjust=False)
            if df.empty:
                print("no data")
                fail += 1
            else:
                # Match existing format: flatten multi-index if present
                if hasattr(df.columns, 'levels'):
                    df.columns = df.columns.get_level_values(0)
                df.to_csv(target)
                print(f"{len(df)} rows -> {target.name}")
                success += 1
        except Exception as e:
            print(f"error: {e}")
            fail += 1
        time.sleep(args.delay)

    print(f"\nDone. Success: {success}, Failed: {fail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
