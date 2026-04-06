#!/usr/bin/env python3
"""
TradePilot Full Market Data Download
Downloads ALL stock data, ETFs, commodities, currencies, indices.

Usage:
    python3 scripts/download-all-data.py              # Download everything
    python3 scripts/download-all-data.py --tier nifty100  # Specific tier only
    python3 scripts/download-all-data.py --status     # Check what's downloaded
"""

import sys
import os
import time
from datetime import datetime
from pathlib import Path

# Add prototype to path
sys.path.insert(0, str(Path(__file__).parent.parent / "prototype"))

from stock_universe import (
    NIFTY_50, NIFTY_100, NIFTY_200, NIFTY_500, NIFTY_NEXT_50,
    NSE_ETFS, MF_PROXIES, FNO_ACTIVE, COMMODITIES, CURRENCY_PAIRS,
    MARKET_INDICES, FULL_UNIVERSE, ALL_NSE,
    NIFTY_BANK, NIFTY_IT, NIFTY_PHARMA, NIFTY_AUTO, NIFTY_FMCG,
    NIFTY_METAL, NIFTY_ENERGY, NIFTY_REALTY,
)

DATA_DIR = Path(__file__).parent.parent / "prototype" / "data"
DATA_DIR.mkdir(exist_ok=True)


def count_downloaded():
    """Count how many stocks have data downloaded."""
    return len(list(DATA_DIR.glob("*.csv")))


def check_status():
    """Show download status."""
    downloaded = set()
    for f in DATA_DIR.glob("*.csv"):
        sym = f.stem.replace("_NS", ".NS").replace("_BO", ".BO").replace("_F", "=F")
        downloaded.add(sym)

    total = count_downloaded()
    categories = {
        "NIFTY 50": NIFTY_50,
        "NIFTY Next 50": NIFTY_NEXT_50,
        "NIFTY 100": NIFTY_100,
        "NIFTY 200": NIFTY_200,
        "NIFTY 500": NIFTY_500,
        "NSE ETFs": NSE_ETFS,
        "MF Proxies": MF_PROXIES,
        "F&O Active": FNO_ACTIVE,
        "Commodities": list(COMMODITIES.values()),
        "Currencies": list(CURRENCY_PAIRS.values()),
        "Indices": list(MARKET_INDICES.values()),
    }

    print(f"TradePilot Data Status — {total} files in {DATA_DIR}")
    print("=" * 55)
    for name, symbols in categories.items():
        have = sum(1 for s in symbols if s in downloaded or
                   s.replace(".", "_").replace("=", "_").replace("-", "_") + ".csv"
                   in [f.name for f in DATA_DIR.glob("*.csv")])
        pct = round(have / len(symbols) * 100) if symbols else 0
        bar = "#" * (pct // 5) + "." * (20 - pct // 5)
        status = "DONE" if pct == 100 else f"{pct}%"
        print(f"  {name:18s} [{bar}] {have:3d}/{len(symbols):3d} {status}")


def download_batch(symbols, label, period="1y"):
    """Download a batch of symbols with progress."""
    import yfinance as yf

    print(f"\n{'='*55}")
    print(f"  Downloading: {label} ({len(symbols)} symbols)")
    print(f"{'='*55}")

    success = 0
    failed = []
    skipped = 0

    for i, symbol in enumerate(symbols):
        safe_name = symbol.replace(".", "_").replace("&", "_").replace("=", "_").replace("-", "_")
        csv_path = DATA_DIR / f"{safe_name}.csv"

        # Skip if already downloaded and recent (within 24h)
        if csv_path.exists():
            mtime = csv_path.stat().st_mtime
            age_hours = (time.time() - mtime) / 3600
            if age_hours < 24:
                skipped += 1
                continue

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval="1d")
            if len(df) > 20:
                df.index = df.index.tz_localize(None)
                df.to_csv(csv_path)
                success += 1
                if (i + 1) % 10 == 0 or i == len(symbols) - 1:
                    print(f"  [{i+1}/{len(symbols)}] {success} downloaded, {skipped} skipped, {len(failed)} failed")
            else:
                failed.append(symbol)
        except Exception as e:
            failed.append(symbol)

        # Rate limit: yfinance can get throttled
        if (i + 1) % 20 == 0:
            time.sleep(1)

    print(f"  Result: {success} new + {skipped} cached = {success + skipped} total, {len(failed)} failed")
    if failed:
        print(f"  Failed: {', '.join(failed[:10])}")
    return success, skipped, failed


def download_all():
    """Download everything in priority order."""
    start = time.time()
    total_new = 0
    total_cached = 0
    total_failed = []

    # Priority order: most important first
    batches = [
        (NIFTY_50, "NIFTY 50 (Core)", "2y"),
        (NIFTY_NEXT_50, "NIFTY Next 50", "1y"),
        ([s for s in NIFTY_200 if s not in NIFTY_100], "NIFTY 200 (101-200)", "1y"),
        ([s for s in NIFTY_500 if s not in NIFTY_200], "NIFTY 500 (201-500)", "1y"),
        (NSE_ETFS, "NSE ETFs", "1y"),
        (MF_PROXIES, "Mutual Fund Proxies", "1y"),
        (list(COMMODITIES.values()), "Commodities", "1y"),
        (list(CURRENCY_PAIRS.values()), "Currency Pairs", "1y"),
        (list(MARKET_INDICES.values()), "Market Indices", "1y"),
    ]

    for symbols, label, period in batches:
        new, cached, failed = download_batch(symbols, label, period)
        total_new += new
        total_cached += cached
        total_failed.extend(failed)

    elapsed = round(time.time() - start)
    minutes = elapsed // 60
    seconds = elapsed % 60

    print(f"\n{'='*55}")
    print(f"  DOWNLOAD COMPLETE")
    print(f"{'='*55}")
    print(f"  New downloads:  {total_new}")
    print(f"  From cache:     {total_cached}")
    print(f"  Failed:         {len(total_failed)}")
    print(f"  Total files:    {count_downloaded()}")
    print(f"  Time:           {minutes}m {seconds}s")
    print(f"  Data dir:       {DATA_DIR}")

    if total_failed:
        failed_path = DATA_DIR / "_failed_symbols.txt"
        with open(failed_path, "w") as f:
            f.write("\n".join(total_failed))
        print(f"  Failed list:    {failed_path}")

    # Now retrain the AI model with all data
    print(f"\n  Next: Restart TradePilot to score all {count_downloaded()} assets")
    print(f"  python3 prototype/app.py")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--all"

    if mode == "--status":
        check_status()
    elif mode == "--tier":
        tier = sys.argv[2] if len(sys.argv) > 2 else "nifty50"
        from stock_universe import get_stocks_by_tier
        symbols = get_stocks_by_tier(tier)
        download_batch(symbols, tier.upper(), "1y")
    else:
        download_all()


if __name__ == "__main__":
    main()
