#!/usr/bin/env python3
"""
winners_scan — every big winner on the NSE over five years, and what they looked
like BEFORE they moved.

THE POINT, stated so it does not get lost. "When should we have entered and exited"
has a trivial answer — at the low, out at the high — and it is worth nothing, because
you cannot know either at the time. That number is computed here as a CEILING, to say
how much was theoretically on the table.

The question that pays is the one next to it: on the day BEFORE a stock ran, what was
observable? Every feature below is computed from data available at the previous
close. If winners look different from non-winners on the day before, that is a signal.
If they look identical, the winners are unforecastable and the ceiling is unreachable.

Universe is the survivorship-free panel — 3046 symbols including the 417 that stopped
trading — so this covers everything from Nifty 50 down to pennies, and does not quietly
drop the ones that died.

    python3 quant/winners_scan.py                 # build the dataset
    python3 quant/winners_scan.py --topn 50       # winners per day
"""
from __future__ import annotations
import json, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd

OUT = ROOT / "docs" / "research" / "overnight"
TOPN = 50


def main():
    topn = TOPN
    if "--topn" in sys.argv:
        topn = int(sys.argv[sys.argv.index("--topn") + 1])

    # This script is the one that filled the volume on 2026-08-28 — a 183 MB panel plus
    # pandas headroom, run alongside other jobs doing the same. Check before building
    # anything: at zero bytes even the cleanup command cannot run.
    from quant.diskguard import report
    report(2.0, "the winners panel is ~200MB and pandas needs working room")

    R = pd.read_parquet(ROOT / "quant/data/sf_ret.parquet").sort_index()
    T = pd.read_parquet(ROOT / "quant/data/sf_turn.parquet").sort_index()
    PX = (1 + R.fillna(0)).cumprod()
    print(f"  {R.shape[0]} sessions x {R.shape[1]} symbols")

    # ── features observable at the PREVIOUS close, for every stock-day ───────
    ret1 = R.shift(1)
    ret5 = PX.shift(1) / PX.shift(6) - 1
    ret21 = PX.shift(1) / PX.shift(22) - 1
    ret63 = PX.shift(1) / PX.shift(64) - 1
    vol20 = R.shift(1).rolling(20).std()
    turn20 = T.shift(1).rolling(20).mean()
    turn_ratio = T.shift(1) / turn20
    hi252 = PX.shift(1).rolling(252, min_periods=60).max()
    lo252 = PX.shift(1).rolling(252, min_periods=60).min()
    pos52 = (PX.shift(1) - lo252) / (hi252 - lo252).replace(0, np.nan)
    sma20 = PX.shift(1).rolling(20).mean()
    vs_sma = PX.shift(1) / sma20 - 1

    rows = []
    dates = R.index
    for i in range(70, len(dates)):
        d = dates[i]
        today = R.loc[d].dropna()
        if len(today) < 200:
            continue
        liq = turn20.loc[d]
        # rank of the day, and the CONTROL: everything else that traded
        winners = set(today.nlargest(topn).index)
        for sym in today.index:
            t = float(turn20.loc[d].get(sym, np.nan))
            rows.append({
                "date": str(d.date()), "sym": sym,
                "win": int(sym in winners),
                "ret_today": float(today[sym]) * 100,
                # ---- all observable at yesterday's close ----
                "ret1": _f(ret1.loc[d].get(sym)), "ret5": _f(ret5.loc[d].get(sym)),
                "ret21": _f(ret21.loc[d].get(sym)), "ret63": _f(ret63.loc[d].get(sym)),
                "vol20": _f(vol20.loc[d].get(sym)), "turn20": t,
                "turn_ratio": _f(turn_ratio.loc[d].get(sym)),
                "pos52": _f(pos52.loc[d].get(sym)), "vs_sma20": _f(vs_sma.loc[d].get(sym)),
            })
        if i % 200 == 0:
            print(f"    {i}/{len(dates)}  ({len(rows):,} rows)", flush=True)

    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT / "winners_panel.parquet")
    w = df[df.win == 1]
    print(f"\n  {len(df):,} stock-days, {len(w):,} winner-days "
          f"({len(w)/len(df)*100:.1f}%)")
    print(f"  winner mean move: {w.ret_today.mean():+.2f}%   "
          f"everyone else: {df[df.win==0].ret_today.mean():+.2f}%")
    print(f"  written -> {OUT/'winners_panel.parquet'}")

    # ── the honest comparison: winners vs the rest, on PRIOR-DAY features ────
    print(f"\n  WHAT DID WINNERS LOOK LIKE THE DAY BEFORE?")
    print(f"  {'feature':<12}{'winners':>12}{'others':>12}{'diff':>10}{'t':>9}")
    for f in ("ret1", "ret5", "ret21", "ret63", "vol20", "turn_ratio",
              "pos52", "vs_sma20"):
        a = df.loc[df.win == 1, f].dropna()
        b = df.loc[df.win == 0, f].dropna()
        if len(a) < 100 or len(b) < 100:
            continue
        t = (a.mean() - b.mean()) / np.sqrt(a.var()/len(a) + b.var()/len(b))
        print(f"  {f:<12}{a.mean():>12.4f}{b.mean():>12.4f}"
              f"{a.mean()-b.mean():>+10.4f}{t:>9.1f}")
    print("\n  NOTE: these t-stats are inflated — stock-days within a date are")
    print("  correlated. Treat the SIGN and the RANKING as the signal, and verify")
    print("  anything promising with a date-clustered test.")


def _f(x):
    try:
        v = float(x)
        return v if np.isfinite(v) else np.nan
    except Exception:
        return np.nan


if __name__ == "__main__":
    sys.exit(main())
