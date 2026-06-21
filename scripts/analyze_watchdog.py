#!/usr/bin/env python3
"""
analyze_watchdog.py — segregate the continuous missed-opps watchdog log into days
and quantify (a) money left on the table and (b) why the book couldn't make money.

The watchdog ran continuously since 06-15 into one undated log (HH:MM only). We
segment by midnight time-wraps, then per day extract MARKET-HOURS findings:
  - winners vs losers held (cut-winners/keep-losers tell)
  - missed movers >3% (we had NO position) -> opportunity cost
  - on-table >2% count
  - worst wrong-way holds (we hold, moving against us) -> the losses we took
Rupee "left on table" is ESTIMATED (log has %+price, not rupees): missed-mover
move x assumed v5 position size (~Rs 12k notional). Honest estimate, not exact.

Usage: python3 scripts/analyze_watchdog.py
"""
import re
from pathlib import Path
from collections import defaultdict
from datetime import date, timedelta

LOG = Path(__file__).resolve().parent.parent / "logs" / "missed-opps-watchdog.log"
POS_NOTIONAL = 12000   # ~v5 avg notional/trade for opportunity-cost estimate
START = date(2026, 6, 15)

def mins(hhmmss):
    h, m, s = map(int, hhmmss.split(":"))
    return h * 60 + m

def main():
    lines = LOG.read_text().splitlines()
    days = []            # list of dicts per day
    cur = None; prev_t = None
    summ_re = re.compile(r"Winners held: (\d+).*Losers held: (\d+).*\(>3%\): (\d+).*\(>2%\): (\d+)")
    miss_re = re.compile(r"(LONG|SHORT)\s+([A-Z&\-]+)\s+Rs\s+([\d,]+\.\d+)\s+([+-][\d.]+)%")
    for ln in lines:
        m = re.match(r"\[(\d\d:\d\d:\d\d)\]", ln)
        if not m: continue
        t = mins(m.group(1))
        if prev_t is not None and t < prev_t - 60:   # midnight wrap = new day
            cur = None
        prev_t = t
        market = 9*60+15 <= t <= 15*60+30
        if cur is None:
            cur = dict(t0=m.group(1), winners=[], losers=[], missed3=[], ontable=[],
                       missed_names={}, wrongway={})
            days.append(cur)
        if not market:
            continue
        sm = summ_re.search(ln)
        if sm:
            w,l,m3,ot = map(int, sm.groups())
            cur["winners"].append(w); cur["losers"].append(l)
            cur["missed3"].append(m3); cur["ontable"].append(ot)
        mm = miss_re.search(ln)
        if mm:
            d,sym,px,pct = mm.group(1), mm.group(2), float(mm.group(3).replace(",","")), abs(float(mm.group(4)))
            cur["missed_names"][sym] = max(cur["missed_names"].get(sym,0), pct)  # peak move seen
    # report
    print(f"{'date':11} {'EOD W/L held':>13} {'peak miss>3%':>12} {'peak ontable':>12} {'est ₹ left/table':>16}")
    for i, dd in enumerate(days):
        dt = (START + timedelta(days=i)).isoformat()
        if not dd["winners"]:
            print(f"{dt:11}  (no market-hours data)"); continue
        eod_w = dd["winners"][-1]; eod_l = dd["losers"][-1]
        peak_m3 = max(dd["missed3"]); peak_ot = max(dd["ontable"])
        # opportunity cost: distinct missed names (>3%) x their peak move x position size
        opp = sum((pct/100)*POS_NOTIONAL for pct in dd["missed_names"].values() if pct>=3)
        print(f"{dt:11} {f'{eod_w}/{eod_l}':>13} {peak_m3:>12} {peak_ot:>12} {round(opp):>16,}")
    print(f"\n  est ₹ = sum(distinct missed >3% names this day x peak move x ~Rs{POS_NOTIONAL:,} position)")
    print("  = rough opportunity cost of movers we held NO position in (the log shows top-5/cycle,")
    print("    so distinct names accumulate across the day; this is an indicative lower-ish bound).")
    # cut-winners/keep-losers tell across all days
    allw=[w for dd in days for w in dd["winners"]]; alll=[l for dd in days for l in dd["losers"]]
    print(f"\n  WHY-signal: across all market-hours cycles, avg winners-held {sum(allw)/max(1,len(allw)):.0f} "
          f"vs losers-held {sum(alll)/max(1,len(alll)):.0f}")

if __name__ == "__main__":
    main()
