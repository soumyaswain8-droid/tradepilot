#!/usr/bin/env python3
"""
quant/validate_hi52_sf.py — the 52-week-high breakout on SURVIVORSHIP-FREE data.

WHY (2026-08-23): hi52_break was the campaign's first holdout survivor
(+1.97%/trade after 0.24% CNC, t=2.16, n=229) — but on today's NIFTY-200 applied
backward, and a new-highs system is the single most flattered strategy under
survivorship bias (today's members ARE yesterday's new-high makers). This rerun is
the pre-registered condition for the v5_hi52 paper lane.

HOW IT REMOVES THE BIAS (same machinery as validate_survivorship_free.py)
  - Panel from NSE bhavcopies: 3,046 symbols INCLUDING since-delisted names.
  - Point-in-time universe: at each ENTRY date, the top-N by trailing 60d average
    turnover as of that date — no knowledge of who survives.
  - Delisting handled: a position whose series ends is exited at its LAST available
    close. Optimistic for true delistings (real proceeds are often worse), so the
    result is still a mild upper bound — stated, not hidden.

STRATEGY (identical to the biased run — nothing retuned)
  Entry: close makes a fresh 250-session high (needs 250 prior sessions), price > 5,
         symbol in the point-in-time top-200 liquid. Enter at that close.
  Exit:  close <= 0.90 x peak close since entry (10% trail), or series end.
  One position per symbol at a time. Costs 0.24% CNC round trip.

GATE (unchanged): holdout (entries 2025-01-01+) net > 0, t > 2, n >= 100.
Usage: python3 quant/validate_hi52_sf.py [--topn 200]
"""
import math, statistics as st, sys, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_survivorship_free import build_panels

TOPN = int(sys.argv[sys.argv.index("--topn") + 1]) if "--topn" in sys.argv else 200
COST = 0.24
SPLIT = pd.Timestamp("2025-01-01")
TRAIL = 0.90
LOOKBACK = 250
GATE_T, GATE_N = 2.0, 100


def main():
    print("  building survivorship-free close/turnover panels from bhavcopies...")
    close, turn = build_panels()
    print(f"  panel: {close.shape[0]} days x {close.shape[1]} symbols "
          f"({str(close.index.min())[:10]}..{str(close.index.max())[:10]})")
    advn = turn.rolling(60).mean()
    hi250 = close.rolling(LOOKBACK, min_periods=LOOKBACK).max()

    trades = []          # (entry_date, ret_pct, delisted_exit)
    n_delist = 0
    days = close.index
    # precompute point-in-time universe membership per day (top-N by advn)
    print("  computing point-in-time top-liquidity universes...")
    univ_by_day = {}
    for d in days[LOOKBACK + 1:]:
        liq = advn.loc[d].dropna()
        liq = liq[liq > 0]
        univ_by_day[d] = set(liq.nlargest(TOPN).index)

    print("  walking entries symbol by symbol...")
    cols = close.columns
    for k, s in enumerate(cols):
        c = close[s].dropna()
        if len(c) < LOOKBACK + 10:
            continue
        h = hi250[s]
        in_pos = False
        entry_px = peak = 0.0
        entry_dt = None
        idx = c.index
        for i in range(LOOKBACK + 1, len(idx)):
            d = idx[i]
            px = float(c.iloc[i])
            if in_pos:
                peak = max(peak, px)
                if px <= peak * TRAIL:
                    trades.append((entry_dt, (px / entry_px - 1) * 100, False))
                    in_pos = False
                continue
            hv = h.get(d)
            hv_prev = h.get(idx[i - 1])
            if hv is None or hv_prev is None or not np.isfinite(hv) or not np.isfinite(hv_prev):
                continue
            if px >= hv and px > hv_prev and px > 5 and s in univ_by_day.get(d, ()):
                in_pos = True
                entry_px = peak = px
                entry_dt = d
        if in_pos:
            # series ended while held — delisting or end of data
            last_px = float(c.iloc[-1])
            end_of_data = idx[-1] >= days[-3]
            trades.append((entry_dt, (last_px / entry_px - 1) * 100, not end_of_data))
            if not end_of_data:
                n_delist += 1
        if (k + 1) % 500 == 0:
            print(f"    {k+1}/{len(cols)} symbols, {len(trades)} trades")

    print(f"\n  trades: {len(trades)} ({n_delist} exited by DELISTING at last close — "
          f"optimistic for those)")
    for name, sel in (("TRAIN  (<2025)", lambda dt: dt < SPLIT),
                      ("HOLDOUT (2025+)", lambda dt: dt >= SPLIT)):
        v = [r - COST for dt, r, _ in trades if sel(dt)]
        if len(v) < 3:
            print(f"  {name}: n={len(v)} — too few")
            continue
        m = st.mean(v); sd = st.pstdev(v)
        t = m / (sd / math.sqrt(len(v))) if sd else 0
        win = sum(1 for x in v if x > 0) / len(v) * 100
        print(f"  {name}: n={len(v):,}  net {m:+.3f}%/trade  t={t:+.2f}  win {win:.0f}%")
        if name.startswith("HOLDOUT"):
            ok = m > 0 and t > GATE_T and len(v) >= GATE_N
            print(f"\n  GATE (holdout net>0 after {COST}%, t>{GATE_T}, n>={GATE_N}): "
                  f"{'SURVIVES — v5_hi52 lane is licensed' if ok else 'FAILS — the biased run was the bias'}")
            biased = 1.97
            print(f"  vs biased-universe holdout: +{biased}% — survivorship cost "
                  f"{biased - m:+.2f}%/trade")


if __name__ == "__main__":
    main()
