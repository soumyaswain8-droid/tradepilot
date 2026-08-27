#!/usr/bin/env python3
"""
quant/fetch_fo_bhavcopy.py — NSE F&O (derivatives) daily bhavcopy fetcher.

Companion to fetch_bhavcopy.py (equity). NSE publishes EXPIRED contract closes in
the F&O bhavcopy, which is the only free source of point-in-time option chains
(Kite/broker APIs drop expired instruments). Two archive formats exist:

  LEGACY  (..2024-07):  /content/historical/DERIVATIVES/YYYY/MMM/foDDMMMYYYYbhav.csv.zip
      cols: INSTRUMENT,SYMBOL,EXPIRY_DT,STRIKE_PR,OPTION_TYP,OPEN,HIGH,LOW,CLOSE,
            SETTLE_PR,CONTRACTS,VAL_INLAKH,OPEN_INT,CHG_IN_OI,TIMESTAMP
  UDiFF   (2024-07..):  /content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip
      cols: TradDt,...,TckrSymb,XpryDt,StrkPric,OptnTp,ClsPric,SttlmPric,
            UndrlygPric,OpnIntrst,TtlTradgVol,...      <- UndrlygPric = exact spot

Neither format carries implied volatility. IV must be inverted from ClsPric.

Saves one .csv per trading day to quant/data/fo_bhavcopy/ (resumable).
Usage: python3 quant/fetch_fo_bhavcopy.py [--start YYYY-MM-DD] [--end YYYY-MM-DD]
"""
import sys, io, zipfile, time
from pathlib import Path
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
import requests

OUT = Path(__file__).resolve().parent / "data" / "fo_bhavcopy"
OUT.mkdir(parents=True, exist_ok=True)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
HDRS = {"User-Agent": UA, "Referer": "https://www.nseindia.com/",
        "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9"}
UDIFF_CUTOVER = date(2024, 7, 8)   # UDiFF became the live format around here


def urls_for(d: date):
    """Both candidate URLs, most-likely-first for the given date."""
    udiff = ("https://nsearchives.nseindia.com/content/fo/"
             f"BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip")
    legacy = ("https://nsearchives.nseindia.com/content/historical/DERIVATIVES/"
              f"{d:%Y}/{d:%b}/fo{d:%d}{d:%b}{d:%Y}bhav.csv.zip".replace(
                  f"/{d:%b}/", f"/{d:%b}/".upper()))
    # month dir + filename month are UPPERCASE in the legacy archive
    legacy = ("https://nsearchives.nseindia.com/content/historical/DERIVATIVES/"
              f"{d.year}/{d.strftime('%b').upper()}/"
              f"fo{d.strftime('%d%b%Y').upper()}bhav.csv.zip")
    return [udiff, legacy] if d >= UDIFF_CUTOVER else [legacy, udiff]


def fetch_day(d: date):
    dest = OUT / f"fo_{d.isoformat()}.csv"
    if dest.exists():
        return "skip"
    for u in urls_for(d):
        try:
            r = requests.get(u, headers=HDRS, timeout=30)
            if r.status_code != 200 or len(r.content) < 5000:
                continue
            zf = zipfile.ZipFile(io.BytesIO(r.content))
            name = zf.namelist()[0]
            dest.write_bytes(zf.read(name))
            time.sleep(0.25)          # throttle: be gentle on NSE
            return "ok"
        except Exception:
            continue
    time.sleep(0.1)
    return "miss"                     # holiday / not published


def main():
    a = sys.argv
    start = date.fromisoformat(a[a.index("--start") + 1]) if "--start" in a else date(2024, 7, 1)
    end = date.fromisoformat(a[a.index("--end") + 1]) if "--end" in a else date.today()
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    print(f"{len(days)} weekdays {start}..{end}", flush=True)
    with ThreadPoolExecutor(max_workers=5) as ex:   # small pool = polite
        res = list(ex.map(fetch_day, days))
    print(f"DONE ok={res.count('ok')} skip={res.count('skip')} "
          f"miss={res.count('miss')} -> {OUT}", flush=True)


if __name__ == "__main__":
    main()
