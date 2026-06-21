#!/usr/bin/env python3
"""
quant/fetch_bhavcopy.py — survivorship-bias-FREE EOD layer from NSE daily bhavcopy.

yfinance only has currently-listed names (survivorship bias ~4%/yr that inflated our
momentum backtest). NSE's daily bhavcopy is a snapshot of EVERY stock that traded
that day — including names later delisted/removed — so assembling ~5y of bhavcopies
gives a point-in-time, survivorship-free universe. This is the research's #1
highest-leverage fix (user-directed 2026-06-16).

Saves one CSV per trading day (resumable; skips weekends/holidays/already-saved).
Next step (separate): assemble these into a panel and re-run the momentum validation
on the UNBIASED universe = the definitive honest number.

Usage: python3 quant/fetch_bhavcopy.py [--years N]
"""
import sys, time, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
from datetime import date, timedelta
from jugaad_data.nse import bhavcopy_save

OUT = Path(__file__).resolve().parent / "data" / "bhavcopy"
OUT.mkdir(parents=True, exist_ok=True)
YEARS = int(sys.argv[sys.argv.index("--years") + 1]) if "--years" in sys.argv else 5

def main():
    end = date.today()
    start = end - timedelta(days=YEARS * 365)
    d = start
    ok = skip = miss = 0
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri only
            # bhavcopy_save writes a file named like cm<DD><MON><YYYY>bhav.csv (or .csv)
            existing = list(OUT.glob(f"*{d.strftime('%d%b%Y').upper()}*")) + list(OUT.glob(f"*{d.isoformat()}*"))
            if existing:
                skip += 1
            else:
                try:
                    bhavcopy_save(d, str(OUT))
                    ok += 1
                    if ok % 50 == 0:
                        print(f"  {d}: saved ({ok} fetched, {skip} skip, {miss} holiday)", flush=True)
                    time.sleep(0.4)  # gentle on NSE
                except Exception:
                    miss += 1  # holiday / no trading / transient
                    time.sleep(0.2)
        d += timedelta(days=1)
    print(f"DONE: {ok} saved, {skip} skipped, {miss} holiday/miss; files in {OUT}", flush=True)

if __name__ == "__main__":
    main()
