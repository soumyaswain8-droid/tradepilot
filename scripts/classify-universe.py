#!/usr/bin/env python3
"""Classify all CSVs in prototype/data/ into tiers.

Tiers:
  elite      — Nifty 50 stocks
  large_cap  — Nifty 200 minus Nifty 50 (~150 stocks)
  mid_cap    — Non-Nifty-200 stocks that pass quality filters
  broad      — Remaining stocks with decent data
  unfit      — Too short / stale / delisted / penny stock

Quality filters:
  - Must have ≥ 250 rows (roughly 1 year history)
  - Last data within 30 days of latest file in repo
  - Close price > Rs 10 (exclude penny stocks)

Output:
  prototype/v4/config/tiers.json  — symbol → tier mapping + stats
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "prototype" / "data"
OUT_DIR = ROOT / "prototype" / "v4" / "config"
OUT_FILE = OUT_DIR / "tiers.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Show classification summary but don't write tiers.json")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from prototype.v4.config import NIFTY_50_SYMBOLS, NIFTY_200_SYMBOLS

    n50 = set(NIFTY_50_SYMBOLS)
    n200 = set(NIFTY_200_SYMBOLS)

    # Scan all .csv files under prototype/data/
    csvs = sorted(DATA_DIR.glob("*.csv"))
    print(f"Scanning {len(csvs)} CSVs in {DATA_DIR}/...")

    # Find the latest date across any file — reference for staleness
    latest_date_seen = None
    stats_per_file = {}

    for csv_path in csvs:
        name = csv_path.stem
        # Skip index files (^INDEX, ^SENSEX etc.) and non-NSE
        if name.startswith("^") or name.startswith("_"):
            continue

        # Symbol extraction: strip _NS or _BO suffix
        if name.endswith("_NS"):
            sym = name[:-3]
        elif name.endswith("_BO"):
            sym = name[:-3]
            continue  # prefer NSE; skip BSE duplicates
        else:
            sym = name

        try:
            last_row = None
            row_count = 0
            last_close = 0
            with open(csv_path, newline="") as f:
                reader = csv.DictReader(f)
                date_col = None
                for r in reader:
                    if date_col is None:
                        for k in ("Date", "date", "Datetime", "datetime"):
                            if k in r:
                                date_col = k
                                break
                    row_count += 1
                    last_row = r
                if last_row and date_col:
                    last_date_str = last_row.get(date_col, "")
                    last_close = float(last_row.get("Close", last_row.get("close", 0)) or 0)
                    try:
                        last_date = datetime.strptime(last_date_str[:10], "%Y-%m-%d")
                        if latest_date_seen is None or last_date > latest_date_seen:
                            latest_date_seen = last_date
                    except Exception:
                        last_date = None
                else:
                    last_date = None

            stats_per_file[sym] = {
                "rows": row_count,
                "last_date": last_date.strftime("%Y-%m-%d") if last_date else None,
                "last_close": last_close,
            }
        except Exception as e:
            stats_per_file[sym] = {"error": str(e)}

    if latest_date_seen is None:
        print("ERROR: could not parse any date — aborting")
        return 1

    staleness_cutoff = latest_date_seen.timestamp() - (30 * 86400)
    print(f"Latest data seen: {latest_date_seen.strftime('%Y-%m-%d')}")
    print(f"Staleness cutoff: 30 days before that\n")

    # Classify
    tiers = defaultdict(dict)
    reject_reasons = defaultdict(int)

    for sym, s in stats_per_file.items():
        if "error" in s:
            tiers["unfit"][sym] = {"reason": f"parse error: {s['error'][:50]}"}
            reject_reasons["parse_error"] += 1
            continue
        rows = s.get("rows", 0)
        last_date_str = s.get("last_date")
        last_close = s.get("last_close", 0)

        # 200 rows = ~9.5 months trading — enough for ML training.
        # Most non-elite stocks have ~246 rows (just under 1 year).
        if rows < 200:
            tiers["unfit"][sym] = {"reason": f"too short: {rows} rows"}
            reject_reasons["too_short"] += 1
            continue
        if last_date_str is None:
            tiers["unfit"][sym] = {"reason": "no valid date"}
            reject_reasons["bad_date"] += 1
            continue

        last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
        if last_date.timestamp() < staleness_cutoff:
            tiers["unfit"][sym] = {"reason": f"stale: last {last_date_str}"}
            reject_reasons["stale"] += 1
            continue

        if last_close < 10:
            tiers["unfit"][sym] = {"reason": f"penny stock: Rs {last_close:.2f}"}
            reject_reasons["penny"] += 1
            continue

        # Tier assignment
        base_info = {
            "rows": rows,
            "last_date": last_date_str,
            "last_close": round(last_close, 2),
        }

        if sym in n50:
            tiers["elite"][sym] = base_info
        elif sym in n200:
            tiers["large_cap"][sym] = base_info
        elif rows >= 240 and last_close >= 50:
            # non-Nifty-200, but has decent history & price → mid_cap
            tiers["mid_cap"][sym] = base_info
        else:
            tiers["broad"][sym] = base_info

    # Summary
    print("Tier classification:")
    for tier in ["elite", "large_cap", "mid_cap", "broad", "unfit"]:
        print(f"  {tier:10s} {len(tiers[tier]):5d} stocks")
    print(f"\nReject reasons:")
    for r, n in reject_reasons.items():
        print(f"  {r:15s} {n}")

    if args.dry_run:
        print(f"\n[DRY-RUN] Would write to: {OUT_FILE}")
        print("[DRY-RUN] No files written.")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    output = {
        "generated_at": datetime.now().isoformat(),
        "latest_data_date": latest_date_seen.strftime("%Y-%m-%d"),
        "staleness_cutoff_days": 30,
        "counts": {tier: len(tiers[tier]) for tier in ["elite", "large_cap", "mid_cap", "broad", "unfit"]},
        "tiers": {tier: tiers[tier] for tier in ["elite", "large_cap", "mid_cap", "broad", "unfit"]},
    }
    OUT_FILE.write_text(json.dumps(output, indent=2))
    print(f"\nWritten: {OUT_FILE}  ({OUT_FILE.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
