#!/usr/bin/env python3
"""
quant/fetch_fo_nifty_only.py — disk-safe F&O bhavcopy fetcher, NIFTY rows ONLY.

WHY THIS EXISTS AND NOT fetch_fo_bhavcopy.py
The full F&O bhavcopy is ~20MB/day uncompressed. Two years is ~10GB, which is more
than the free space on this disk and is exactly what caused the outage. Every day
the archive carries ~200k rows across every underlying; we need ~3k of them.
So: download the zip to MEMORY, filter to TckrSymb == NIFTY, write only that.
Measured result: ~250KB/day instead of ~20MB/day, an ~80x reduction.

We keep FUTIDX rows as well as options — the delta hedge is executed in NIFTY
futures, so the futures close is part of the P&L path, not a nice-to-have.

DISK GUARD
Free space is checked before EVERY write. Below MIN_FREE_GB the process aborts
loudly rather than filling the disk. This is a hard stop, not a warning.

UDiFF format only (2024-07-08 onward). The legacy format lacks UndrlygPric, so
mixing them would silently change the spot source mid-sample.

Usage: python3 quant/fetch_fo_nifty_only.py --start YYYY-MM-DD --end YYYY-MM-DD
"""
import sys, io, os, zipfile, time, shutil
from pathlib import Path
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
import requests
import pandas as pd

OUT = Path(__file__).resolve().parent / "data" / "fo_nifty"
OUT.mkdir(parents=True, exist_ok=True)

MIN_FREE_GB = 2.0
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Referer": "https://www.nseindia.com/",
        "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}

KEEP = ["TradDt", "XpryDt", "StrkPric", "OptnTp", "FinInstrmTp", "ClsPric",
        "SttlmPric", "UndrlygPric", "OpnIntrst", "TtlTradgVol", "OpnPric",
        "HghPric", "LwPric", "TtlTrfVal", "TtlNbOfTxsExctd"]

_bytes = [0]


def free_gb():
    return shutil.disk_usage(str(OUT)).free / 1e9


def fetch_day(d: date):
    dest = OUT / f"nifty_{d.isoformat()}.csv"
    if dest.exists():
        return "skip"
    if free_gb() < MIN_FREE_GB:
        return "ABORT_DISK"
    url = ("https://nsearchives.nseindia.com/content/fo/"
           f"BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip")
    try:
        r = requests.get(url, headers=HDRS, timeout=30)
        if r.status_code != 200 or len(r.content) < 5000:
            time.sleep(0.1)
            return "miss"
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        df = pd.read_csv(io.BytesIO(zf.read(zf.namelist()[0])), low_memory=False)
        if "TckrSymb" not in df.columns:
            return "miss"
        df = df[df.TckrSymb == "NIFTY"]
        if df.empty:
            return "miss"
        cols = [c for c in KEEP if c in df.columns]
        if free_gb() < MIN_FREE_GB:
            return "ABORT_DISK"
        buf = df[cols].to_csv(index=False)
        dest.write_text(buf)
        _bytes[0] += len(buf)
        time.sleep(0.25)
        return "ok"
    except Exception:
        time.sleep(0.1)
        return "miss"


def main():
    a = sys.argv
    start = date.fromisoformat(a[a.index("--start") + 1]) if "--start" in a else date(2024, 7, 8)
    end = date.fromisoformat(a[a.index("--end") + 1]) if "--end" in a else date.today()
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    print(f"{len(days)} weekdays {start}..{end}  free={free_gb():.1f}GB", flush=True)
    if free_gb() < MIN_FREE_GB:
        sys.exit(f"REFUSING: only {free_gb():.1f}GB free, need {MIN_FREE_GB}GB")
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = list(ex.map(fetch_day, days))
    tot = sum(f.stat().st_size for f in OUT.glob("nifty_*.csv"))
    print(f"DONE ok={res.count('ok')} skip={res.count('skip')} miss={res.count('miss')} "
          f"abort={res.count('ABORT_DISK')}", flush=True)
    print(f"ON DISK {tot/1e6:.1f} MB in {len(list(OUT.glob('nifty_*.csv')))} files "
          f"| free now {free_gb():.1f}GB", flush=True)


if __name__ == "__main__":
    main()
