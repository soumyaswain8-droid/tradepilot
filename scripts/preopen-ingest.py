#!/usr/bin/env python3
"""
preopen-ingest — validate + snapshot an NSE pre-open CSV for today's session.

THE TRAP THIS GUARDS (found 2026-08-20): NSE's download stamps TODAY'S date in the
filename but serves the LAST COMPLETED auction when fetched before 09:00 — a file
named 20-Aug carried the 19-Aug auction (PREV. CLOSE matched 08-18 closes). A stale
auction used as today's gaps is stale-price trading with extra steps.

VALIDATION: the file's PREV. CLOSE for a probe symbol must match YESTERDAY'S actual
close (Kite daily). Mismatch -> refused loudly, nothing written.

Output: prototype/data/preopen/YYYY-MM-DD.json  {symbol: auction_gap_pct}
Usage:  python3 scripts/preopen-ingest.py [path.csv]   (defaults to newest Downloads match)
"""
import csv, glob, json, sys, warnings
warnings.filterwarnings("ignore")
from datetime import datetime, timedelta
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v4 import kite_data as kd

def fetch_live():
    """Pull the auction straight from NSE — no manual download.

    NSE answers 403 to a bare request, so a session must first load the pre-open page
    to collect cookies; the JSON endpoint then returns all ~2,360 rows. Verified
    2026-08-25: warm-up 200 with 3 cookies, api 200, 2359 rows.

    Why this is worth automating: the auction that runs 09:00-09:08 SETS the opening
    price. Measured on Monday's file, the indicative price equalled the actual open
    exactly for 119 of 120 liquid names. So fetching at 09:09 hands us every opening
    gap in the market six minutes before the market opens.
    """
    import requests
    H = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
         "Accept": "*/*", "Accept-Language": "en-US,en;q=0.9",
         "Referer": "https://www.nseindia.com/market-data/"
                    "pre-open-market-cm-and-emerge-market"}
    s = requests.Session()
    s.headers.update(H)
    s.get("https://www.nseindia.com/market-data/pre-open-market-cm-and-emerge-market",
          timeout=15)
    r = s.get("https://www.nseindia.com/api/market-data-pre-open?key=ALL", timeout=15)
    r.raise_for_status()
    out = {}
    for row in r.json().get("data", []):
        m = row.get("metadata") or {}
        sym = m.get("symbol")
        prev, chg = m.get("previousClose"), m.get("pChange")
        if sym and prev:
            out[sym] = {"prev_close": float(prev), "gap_pct": float(chg or 0)}
    return out


rows = {}
if "--fetch" in sys.argv:
    try:
        rows = fetch_live()
        print(f"  fetched {len(rows)} symbols live from NSE")
    except Exception as e:
        print(f"  live fetch failed ({str(e)[:70]}) — falling back to a CSV")
if not rows:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = args[0] if args else max(
        glob.glob("/Users/soumyaswain/Downloads/MW-Pre-Open-Market-*.csv"), default=None)
    if not src:
        print("  no pre-open CSV found"); sys.exit(1)
    with open(src, encoding="utf-8-sig") as f:
        r = csv.reader(f)
        hdr = [h.strip().strip('"').replace("\n", "").strip() for h in next(r)]
        for line in r:
            if len(line) != len(hdr):
                continue
            d = dict(zip(hdr, [x.strip() for x in line]))
            try:
                rows[d["SYMBOL"]] = {"prev_close": float(d["PREV. CLOSE"].replace(",", "")),
                                     "gap_pct": float(d["%CHNG"].replace(",", ""))}
            except Exception:
                pass
# validate against yesterday's actual close
probe = "RELIANCE"
tok = kd.token_for(probe)
raw = kd.client().historical_data(tok, datetime.now() - timedelta(days=6),
                                  datetime.now(), "day")
closed = [b for b in raw if str(b["date"])[:10] != datetime.now().strftime("%Y-%m-%d")]
ycl = float(closed[-1]["close"])
fcl = rows.get(probe, {}).get("prev_close")
if fcl is None or abs(fcl - ycl) / ycl > 0.001:
    print(f"  REFUSED: file prev_close for {probe} = {fcl}, but yesterday's close = {ycl}.")
    print(f"  This file is a STALE auction (the filename lies before 09:00). Re-download after 09:08.")
    sys.exit(2)
out = ROOT / "prototype" / "data" / "preopen"
out.mkdir(parents=True, exist_ok=True)
p = out / f"{datetime.now():%Y-%m-%d}.json"
p.write_text(json.dumps({s: v["gap_pct"] for s, v in rows.items()}, indent=1))
print(f"  VALID for today ({len(rows)} symbols) -> {p}")
