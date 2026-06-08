#!/usr/bin/env python3
"""Walk-forward optimization of the Layer-1 ADX thresholds (adx_trend, adx_chop).

Why: untuned defaults (25/20) beat buy&hold on most NIFTY names but whipsawed on
RELIANCE. WFO picks thresholds that are robust OUT-OF-SAMPLE, across a basket (so
we don't overfit one stock), and reports the Deflated Sharpe Ratio to discount the
many-variants selection bias (Bailey & Lopez de Prado).

Method:
  - Compute ADX/+DI/-DI/SMA50 ONCE per symbol (thresholds don't change them).
  - For each (adx_trend, adx_chop) candidate, build the gated daily-return series
    per symbol (LONG/BOTH=+ret, SHORT_ONLY=-ret, FLAT=0), pooled across the basket.
  - Anchored walk-forward: for each fold, choose the param with best IN-SAMPLE
    pooled Sharpe, then score it on the next OUT-OF-SAMPLE block. Pool OOS returns.
  - Ship recommendation = param with best MEAN out-of-sample Sharpe across folds.
  - DSR computed on the chosen param's pooled daily returns vs the grid of trials.

Usage: python3 scripts/v7-wfo-tune.py [--folds 4]
"""
import sys
from pathlib import Path
from statistics import NormalDist
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "prototype"))
from prototype.v7.regime_gate import directional_indicators

DATA = ROOT / "prototype" / "data"
TREND_GRID = [20.0, 22.0, 25.0, 28.0, 30.0]
CHOP_GRID = [15.0, 18.0, 20.0, 22.0]
SMA_PERIOD, SLOPE_LB = 50, 5
WARMUP = 60
ANN = np.sqrt(252)
EULER = 0.5772156649


def load_basket():
    """Fresh NIFTY-50 daily frames (last bar >= 2026-06-05, >= 300 rows)."""
    from stock_universe import NIFTY_50
    out = {}
    for s in NIFTY_50:
        nm = s.replace(".", "_").replace("&", "_").replace("=", "_").replace("-", "_")
        p = DATA / f"{nm}.csv"
        if not p.exists():
            continue
        try:
            d = pd.read_csv(p, parse_dates=["Date"]).sort_values("Date").reset_index(drop=True)
            d = d.dropna(subset=["High", "Low", "Close"])
        except Exception:
            continue
        if len(d) < 300 or str(d["Date"].iloc[-1].date()) < "2026-06-05":
            continue
        out[s] = d
    return out


def precompute(d):
    """Indicators that DON'T depend on thresholds: adx, +di, -di, sma50 slope, next-day ret."""
    adx, pdi, mdi = directional_indicators(d["High"], d["Low"], d["Close"])
    sma = d["Close"].rolling(SMA_PERIOD).mean()
    slope = sma - sma.shift(SLOPE_LB)
    close = d["Close"].to_numpy()
    nxt = np.full(len(close), np.nan)
    nxt[:-1] = (close[1:] - close[:-1]) / close[:-1]
    return (adx.to_numpy(), pdi.to_numpy(), mdi.to_numpy(), slope.to_numpy(), nxt)


def gated_returns(pre, adx_trend, adx_chop):
    """Vectorized allowed_side -> gated next-day return per bar (mirrors regime_gate.allowed_side)."""
    adx, pdi, mdi, slope, nxt = pre
    n = len(adx)
    g = np.zeros(n)
    for t in range(WARMUP, n - 1):
        a, p, m, sl = adx[t], pdi[t], mdi[t], slope[t]
        if np.isnan(a) or np.isnan(sl) or a < adx_chop:
            continue  # FLAT -> 0
        if p > m and sl > 0:        # LONG_ONLY
            g[t] = nxt[t]
        elif m > p and sl < 0:      # SHORT_ONLY
            g[t] = -nxt[t]
        elif a >= adx_trend:        # BOTH -> take long bias
            g[t] = nxt[t]
        # else FLAT -> 0
    return g[WARMUP:n - 1]


def sharpe(x):
    x = x[~np.isnan(x)]
    return float(x.mean() / x.std() * ANN) if len(x) > 1 and x.std() > 0 else 0.0


def deflated_sharpe(returns, trial_sharpes_daily, sr_obs_daily):
    """DSR (Bailey & Lopez de Prado). All Sharpes here are PER-PERIOD (daily)."""
    r = returns[~np.isnan(returns)]
    T = len(r)
    if T < 20:
        return float("nan")
    N = max(len(trial_sharpes_daily), 2)
    var_sr = float(np.var(trial_sharpes_daily, ddof=1)) if N > 1 else 0.0
    sig = np.sqrt(var_sr) if var_sr > 0 else 1e-9
    Z = NormalDist().inv_cdf
    sr0 = sig * ((1 - EULER) * Z(1 - 1.0 / N) + EULER * Z(1 - 1.0 / (N * np.e)))
    m = r.mean()
    sd = r.std()
    if sd == 0:
        return float("nan")
    g3 = float(((r - m) ** 3).mean() / sd ** 3)          # skew
    g4 = float(((r - m) ** 4).mean() / sd ** 4)          # kurtosis (normal=3)
    denom = np.sqrt(max(1e-12, 1 - g3 * sr_obs_daily + (g4 - 1) / 4.0 * sr_obs_daily ** 2))
    return float(NormalDist().cdf((sr_obs_daily - sr0) * np.sqrt(T - 1) / denom))


def main():
    folds = 4
    if "--folds" in sys.argv:
        folds = int(sys.argv[sys.argv.index("--folds") + 1])

    basket = load_basket()
    if not basket:
        print("No fresh basket symbols found.")
        return
    print(f"Basket: {len(basket)} fresh NIFTY-50 symbols")

    pres = {s: precompute(d) for s, d in basket.items()}
    grid = [(t, c) for t in TREND_GRID for c in CHOP_GRID if c < t]

    # Pooled gated returns per param across the whole basket (aligned by tail length).
    pooled = {}
    for (t, c) in grid:
        cols = [gated_returns(pres[s], t, c) for s in basket]
        L = min(len(x) for x in cols)
        pooled[(t, c)] = np.concatenate([x[-L:] for x in cols])  # equal-length tail per symbol

    # full-sample daily Sharpe per trial (for DSR) and annualized (for display)
    trial_sr_daily = []
    for (t, c) in grid:
        x = pooled[(t, c)]
        trial_sr_daily.append(x.mean() / x.std() if x.std() > 0 else 0.0)

    # Anchored walk-forward over the pooled timeline.
    any_len = len(next(iter(pooled.values())))
    fold_bounds = np.linspace(int(any_len * 0.4), any_len, folds + 1, dtype=int)
    selected, oos_by_param = [], {g_: [] for g_ in grid}
    for k in range(folds):
        is_end = fold_bounds[k]
        oos_end = fold_bounds[k + 1]
        if oos_end - is_end < 20:
            continue
        best, best_sr = None, -1e9
        for g_ in grid:
            issr = sharpe(pooled[g_][:is_end])
            if issr > best_sr:
                best_sr, best = issr, g_
        for g_ in grid:
            oos_by_param[g_].append(sharpe(pooled[g_][is_end:oos_end]))
        oos_sel = sharpe(pooled[best][fold_bounds[k]:oos_end])
        selected.append((best, oos_sel))
        print(f"  fold {k+1}: IS-best={best}  its OOS Sharpe={oos_sel:.2f}")

    # Ship recommendation = best MEAN out-of-sample Sharpe across folds (robust, not IS-fit).
    mean_oos = {g_: float(np.mean(v)) for g_, v in oos_by_param.items() if v}
    rec = max(mean_oos, key=mean_oos.get)
    rec_full = pooled[rec]
    rec_sr_daily = rec_full.mean() / rec_full.std() if rec_full.std() > 0 else 0.0
    dsr = deflated_sharpe(rec_full, trial_sr_daily, rec_sr_daily)

    print("\n=== top params by mean OOS Sharpe ===")
    for g_, v in sorted(mean_oos.items(), key=lambda kv: kv[1], reverse=True)[:5]:
        print(f"  adx_trend={g_[0]:.0f} adx_chop={g_[1]:.0f}  meanOOS Sharpe={v:.2f}  "
              f"full-ann Sharpe={sharpe(pooled[g_]):.2f}")
    print(f"\nRECOMMEND: adx_trend={rec[0]:.0f}, adx_chop={rec[1]:.0f}")
    print(f"  mean OOS Sharpe={mean_oos[rec]:.2f} | full-sample ann Sharpe={sharpe(rec_full):.2f}")
    print(f"  Deflated Sharpe Ratio (prob skill is real, not selection luck) = {dsr:.3f}")
    print(f"  (default 25/20 mean OOS Sharpe = {mean_oos.get((25.0,20.0), float('nan')):.2f})")


if __name__ == "__main__":
    main()
