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

src = sys.argv[1] if len(sys.argv) > 1 else max(
    glob.glob("/Users/soumyaswain/Downloads/MW-Pre-Open-Market-*.csv"), default=None)
if not src:
    print("  no pre-open CSV found"); sys.exit(1)
rows = {}
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
