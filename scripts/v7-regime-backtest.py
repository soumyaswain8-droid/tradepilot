#!/usr/bin/env python3
"""Backtest Layer 1 alone: for each day, allowed_side() decides the side; we take
the index's next-day return on the allowed side (LONG_ONLY=+ret, SHORT_ONLY=-ret,
FLAT=0, BOTH=+ret). Reports annualised Sharpe vs buy-and-hold. NO look-ahead:
allowed_side(t) uses bars up to and including t; return is t->t+1.

Usage: python3 scripts/v7-regime-backtest.py <daily_csv> [--adx-trend 25 --adx-chop 20]
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v7.regime_gate import allowed_side

def run(csv_path, adx_trend=25.0, adx_chop=20.0):
    df = pd.read_csv(csv_path)
    df = df.rename(columns={c: c.capitalize() for c in df.columns})
    df = df[["High", "Low", "Close"]].dropna().reset_index(drop=True)
    rets, gated = [], []
    for t in range(60, len(df) - 1):
        side = allowed_side(df.iloc[: t + 1], adx_trend, adx_chop)
        nxt = (df["Close"].iloc[t + 1] - df["Close"].iloc[t]) / df["Close"].iloc[t]
        if side in ("LONG_ONLY", "BOTH"):
            gated.append(nxt)
        elif side == "SHORT_ONLY":
            gated.append(-nxt)
        else:
            gated.append(0.0)
        rets.append(nxt)
    g, b = np.array(gated), np.array(rets)
    def sharpe(x):
        return (x.mean() / x.std() * np.sqrt(252)) if x.std() > 0 else 0.0
    print(f"{Path(csv_path).stem}: gated Sharpe={sharpe(g):.2f}  buy&hold Sharpe={sharpe(b):.2f}  "
          f"gated cum={g.sum()*100:.1f}%  b&h cum={b.sum()*100:.1f}%")

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    run(args[0])
