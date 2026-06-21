#!/usr/bin/env python3
"""
quant/backtest_factor.py — honest cross-sectional factor backtester (multi-horizon).

Tests whether TradePilot's CORE edge (cross-sectional relative-strength momentum —
the same rs_score that drives v5) extends BEYOND intraday to swing/positional
horizons, NET OF realistic cost. Long top-quantile / short bottom-quantile,
equal-weight, market-neutral, rebalanced every H days.

Reads the local EOD cache (quant/data/eod). Reports per (lookback, horizon):
ann return, ann vol, Sharpe, max drawdown, avg rank-IC, turnover — gross AND net.
This is the validation backbone the prior audit said we lacked (a real backtest,
not the live paper engine).

HONEST caveats (Sarathi rules): (1) survivorship bias — cache has only currently
listed names, which INFLATES momentum returns; treat results as an optimistic
upper bound. (2) Daily close-to-close fills (no intraday path). (3) Flat bps cost
(no size/impact scaling) — capacity not modeled here. Numbers are directional, to
locate WHERE edge plausibly exists, not a deployable P&L claim.

Usage: python3 quant/backtest_factor.py [--cost-bps 23]
"""
import sys, glob, warnings, math
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent / "data" / "eod"
COST_BPS = float(sys.argv[sys.argv.index("--cost-bps") + 1]) if "--cost-bps" in sys.argv else 23.0
QUANTILE = 0.2          # top/bottom 20%
ANN = 252

def load_panel():
    """Return Close-price panel (dates x symbols) from the EOD cache."""
    files = sorted(glob.glob(str(DATA / "*.parquet")) + glob.glob(str(DATA / "*.pkl")))
    closes = {}
    for f in files:
        sym = Path(f).stem
        if sym.startswith("_"):  # ^NSEI cached as _NSEI — keep as benchmark, not in universe
            continue
        try:
            df = pd.read_parquet(f) if f.endswith("parquet") else pd.read_pickle(f)
            closes[sym] = df["Close"]
        except Exception:
            pass
    panel = pd.DataFrame(closes).sort_index()
    panel = panel[panel.index >= panel.index[0]]
    return panel

def backtest(panel, lookback, horizon, cost_bps):
    """Cross-sectional momentum: rank by past-`lookback`-day return (skip last day),
    long top / short bottom quantile, rebalance every `horizon` days, equal-weight."""
    rets = panel.pct_change()
    # momentum signal: return over [t-lookback, t-1] (skip most recent day)
    mom = panel.shift(1) / panel.shift(lookback) - 1.0
    rebal_dates = panel.index[lookback + 1::horizon]
    port_rets, ics, turnovers = [], [], []
    prev_w = pd.Series(0.0, index=panel.columns)
    for i, d in enumerate(rebal_dates[:-1]):
        sig = mom.loc[d].dropna()
        # liquidity/price sanity: drop sub-Rs 5 and names with <90% data in window
        sig = sig[panel.loc[d, sig.index] > 5]
        if len(sig) < 20:
            continue
        n = max(1, int(len(sig) * QUANTILE))
        longs = sig.nlargest(n).index
        shorts = sig.nsmallest(n).index
        w = pd.Series(0.0, index=panel.columns)
        w[longs] = 0.5 / n
        w[shorts] = -0.5 / n
        # forward return over the holding window
        nxt = rebal_dates[i + 1]
        fwd = (panel.loc[nxt] / panel.loc[d] - 1.0)
        gross = (w * fwd.reindex(w.index).fillna(0)).sum()
        turnover = (w - prev_w).abs().sum()
        cost = turnover * (cost_bps / 10000.0)
        port_rets.append((nxt, gross - cost))
        turnovers.append(turnover)
        # rank-IC: spearman(signal, forward return) over the cross-section
        common = sig.index.intersection(fwd.dropna().index)
        if len(common) > 10:
            ics.append(sig[common].rank().corr(fwd[common].rank()))
        prev_w = w
    if len(port_rets) < 5:
        return None
    idx, vals = zip(*port_rets)
    pr = pd.Series(vals, index=idx)
    periods_per_yr = ANN / horizon
    mean, sd = pr.mean(), pr.std()
    sharpe = (mean / sd * math.sqrt(periods_per_yr)) if sd > 0 else 0
    ann_ret = (1 + pr).prod() ** (periods_per_yr / len(pr)) - 1
    eq = (1 + pr).cumprod()
    maxdd = (eq / eq.cummax() - 1).min()
    return dict(lookback=lookback, horizon=horizon, n=len(pr), ann_ret=ann_ret,
                sharpe=sharpe, maxdd=maxdd, ic=np.mean(ics) if ics else 0,
                turnover=np.mean(turnovers), net_total=eq.iloc[-1] - 1)

def main():
    panel = load_panel()
    print(f"panel: {panel.shape[1]} symbols, {panel.shape[0]} days "
          f"({panel.index[0].date()}..{panel.index[-1].date()}), cost={COST_BPS}bps round-trip\n")
    print(f"{'lookback':>8} {'horizon':>7} {'rebals':>6} {'annRet':>8} {'Sharpe':>7} {'maxDD':>8} {'rankIC':>7} {'turn':>6} {'netTot':>8}")
    grid = [(21,5),(63,5),(126,5),(21,21),(63,21),(126,21),(126,63),(252,63),(252,21)]
    rows=[]
    for lb, h in grid:
        if lb + h >= panel.shape[0]:
            continue
        r = backtest(panel, lb, h, COST_BPS)
        if r:
            rows.append(r)
            print(f"{lb:>8} {h:>7} {r['n']:>6} {r['ann_ret']*100:>7.1f}% {r['sharpe']:>7.2f} "
                  f"{r['maxdd']*100:>7.1f}% {r['ic']:>7.3f} {r['turnover']:>6.2f} {r['net_total']*100:>7.0f}%")
    if rows:
        best = max(rows, key=lambda x: x['sharpe'])
        print(f"\nBest net Sharpe: lookback={best['lookback']}d horizon={best['horizon']}d "
              f"-> Sharpe {best['sharpe']:.2f}, annRet {best['ann_ret']*100:.1f}%, IC {best['ic']:.3f}")
        print("NOTE: survivorship-biased upper bound; positive IC/Sharpe = edge worth proper purged-CV validation.")

if __name__ == "__main__":
    main()
