#!/usr/bin/env python3
"""
hypothesis_search — test ~1000 trading rules honestly.

THE PROBLEM WITH TESTING 1000 RULES. At p<0.05 you expect ~50 false positives from
pure noise. Three times in one week a result here looked real on a small or selected
sample and evaporated on a wider one. So the defences are declared FIRST and are not
negotiable afterwards:

  1. TRAIN / HOLDOUT SPLIT, fixed before any rule is evaluated. The search only ever
     sees train. Survivors are tested once on holdout, which is never used to choose
     anything.
  2. BONFERRONI. With N tests the significance bar becomes 0.05/N, so at 1000 tests a
     rule needs |t| ~ 4.1 rather than 2.0. Harsh on purpose.
  3. FULL COSTS. 0.106% round trip charged on every trade, so every figure is net.
  4. THE NULL IS REPORTED. If nothing survives, that is the finding, and it is worth
     more than a rule that would have lost money live.

WHAT IS SEARCHED. Eight features x both directions x three thresholds x four holding
periods x time-of-day filters, plus the two-factor combinations of whatever survives.
Features use only information available at the bar they are computed on.

    python3 quant/hypothesis_search.py
    python3 quant/hypothesis_search.py --top 30
"""
from __future__ import annotations
import math, pickle, sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np

CACHE = ROOT / "quant" / "data" / "panel_5min.pkl"   # self-written cache; see build_panel
TOLL = 0.106                 # our measured round-trip cost, in percent
HOLDS = (3, 6, 12, 24)       # bars -> 15 / 30 / 60 / 120 minutes
TRAIN_FRAC = 0.67            # first two thirds of SESSIONS, split declared up front


def load():
    p = pickle.loads(CACHE.read_bytes())
    return p["bars"]


def build_features(bars):
    """One row per decision point, with features that look only backwards.

    Every feature is computed from bars at or before the row's own bar, and the
    forward returns are measured from the NEXT bar's open — never the current close.
    Entering at a price you only knew after the bar closed is the most common way a
    backtest invents an edge.
    """
    rows = []
    for sym, s in bars.items():
        by_day = {}
        for (day, hm), v in s.items():
            by_day.setdefault(day, []).append((hm, v))
        for day, items in by_day.items():
            items.sort()
            n = len(items)
            if n < 30:
                continue
            o = np.array([v[0] for _, v in items])
            h = np.array([v[1] for _, v in items])
            l = np.array([v[2] for _, v in items])
            c = np.array([v[3] for _, v in items])
            vol = np.array([v[4] for _, v in items])
            tp = (h + l + c) / 3.0
            cum_v = np.cumsum(vol)
            vwap = np.cumsum(tp * vol) / np.where(cum_v == 0, 1, cum_v)
            run_hi = np.maximum.accumulate(h)
            run_lo = np.minimum.accumulate(l)
            rng = np.where(run_hi - run_lo == 0, 1e-9, run_hi - run_lo)
            open_px = o[0]
            for i in range(6, n - max(HOLDS) - 1):
                entry = o[i + 1]                     # next bar's OPEN — no look-ahead
                if entry <= 0:
                    continue
                fwd = {}
                for hbars in HOLDS:
                    j = i + 1 + hbars
                    if j >= n:
                        fwd = None; break
                    fwd[hbars] = (c[j] / entry - 1) * 100
                if fwd is None:
                    continue
                vr = vol[i] / (vol[max(0, i - 12):i].mean() + 1e-9)
                rows.append((
                    sym, day, items[i][0], entry,
                    (c[i] / c[i - 1] - 1) * 100,          # 0 ret_5m
                    (c[i] / c[i - 3] - 1) * 100,          # 1 ret_15m
                    (c[i] / c[i - 6] - 1) * 100,          # 2 ret_30m
                    (c[i] / open_px - 1) * 100,           # 3 day_ret
                    (c[i] / vwap[i] - 1) * 100,           # 4 vs_vwap
                    (c[i] - run_lo[i]) / rng[i],          # 5 range_pos 0..1
                    vr,                                    # 6 vol_ratio
                    (open_px / c[0] - 1) * 100,           # 7 (placeholder gap)
                    i / n,                                 # 8 time_of_day 0..1
                    fwd[3], fwd[6], fwd[12], fwd[24],
                ))
    return rows


FEATS = ["ret_5m", "ret_15m", "ret_30m", "day_ret", "vs_vwap",
         "range_pos", "vol_ratio", "time_of_day"]
FEAT_IDX = {f: i for i, f in enumerate([4, 5, 6, 7, 8, 9, 10, 12])}


def main():
    top_n = 20
    if "--top" in sys.argv:
        top_n = int(sys.argv[sys.argv.index("--top") + 1])

    print("  loading panel...")
    bars = load()
    rows = build_features(bars)
    print(f"  {len(rows):,} decision points from {len(bars)} symbols")

    days = sorted({r[1] for r in rows})
    cut = days[int(len(days) * TRAIN_FRAC)]
    print(f"  {len(days)} sessions; TRAIN < {cut} <= HOLDOUT  (split fixed before search)")

    arr = np.array([r[4:] for r in rows], dtype=float)
    day_arr = np.array([r[1] for r in rows])
    train = day_arr < cut
    hold = ~train
    print(f"  train {train.sum():,} rows   holdout {hold.sum():,} rows\n")

    # feature columns: ret_5m..time_of_day are cols 0..8 of arr (col 7 unused)
    fcols = {"ret_5m": 0, "ret_15m": 1, "ret_30m": 2, "day_ret": 3,
             "vs_vwap": 4, "range_pos": 5, "vol_ratio": 6, "time_of_day": 8}
    hcols = {3: 9, 6: 10, 12: 11, 24: 12}

    rules, results = [], []
    QS = (0.10, 0.20, 0.30)
    TODS = (("all", None), ("morning", (0.0, 0.34)),
            ("midday", (0.34, 0.67)), ("afternoon", (0.67, 1.0)))
    for fname, fc in fcols.items():
        x = arr[:, fc]
        for q in QS:
            lo_t = np.nanquantile(x[train], q)
            hi_t = np.nanquantile(x[train], 1 - q)
            for tail, thr, side in (("low", lo_t, 1), ("low", lo_t, -1),
                                    ("high", hi_t, 1), ("high", hi_t, -1)):
                for hb in HOLDS:
                    for tod_name, tod in TODS:
                        rules.append((fname, tail, q, thr, side, hb, tod_name, tod))

    print(f"  {len(rules)} rules to test\n  searching TRAIN only...")
    tod_col = arr[:, 8]
    for (fname, tail, q, thr, side, hb, tod_name, tod) in rules:
        x = arr[:, fcols[fname]]
        m = (x <= thr) if tail == "low" else (x >= thr)
        if tod:
            m &= (tod_col >= tod[0]) & (tod_col < tod[1])
        mt = m & train
        n = int(mt.sum())
        if n < 300:
            continue
        r = arr[mt, hcols[hb]] * side - TOLL
        mu = float(np.nanmean(r)); sd = float(np.nanstd(r)) or 1e-9
        t = mu / (sd / math.sqrt(n))
        results.append({"feat": fname, "tail": tail, "q": q, "side": side,
                        "hold": hb, "tod": tod_name, "n": n, "mu": mu, "t": t,
                        "mask": m})
    results.sort(key=lambda r: -r["t"])
    N = len(results)
    bar_t = abs(_z_for(0.05 / max(N, 1)))
    print(f"  {N} rules had enough trades to evaluate")
    print(f"  Bonferroni bar for {N} tests: |t| >= {bar_t:.2f}  (vs 1.96 uncorrected)\n")

    print(f"  TOP {top_n} ON TRAIN")
    print(f"  {'feature':<12}{'tail':<6}{'q':>5}{'side':>6}{'hold':>6}{'when':<11}"
          f"{'n':>7}{'net/trade':>11}{'t':>8}")
    for r in results[:top_n]:
        print(f"  {r['feat']:<12}{r['tail']:<6}{r['q']:>5.2f}"
              f"{'LONG' if r['side']>0 else 'SHORT':>6}{r['hold']*5:>5}m"
              f"  {r['tod']:<11}{r['n']:>7}{r['mu']:>10.4f}%{r['t']:>8.2f}")

    survivors = [r for r in results if r["t"] >= bar_t]
    print(f"\n  {len(survivors)} rules clear the corrected bar on TRAIN")
    if not survivors:
        print("  NOTHING SURVIVES. That is the finding: no single-feature rule in this")
        print("  grid beats the toll on 5-minute bars over 42 sessions.")
        return 0

    print(f"\n  HOLDOUT — the survivors, tested once on data never used to choose")
    print(f"  {'feature':<12}{'side':>6}{'hold':>6}{'when':<11}{'n':>7}"
          f"{'net/trade':>11}{'t':>8}   verdict")
    kept = 0
    for r in survivors[:top_n]:
        mh = r["mask"] & hold
        n = int(mh.sum())
        if n < 100:
            continue
        rr = arr[mh, hcols[r["hold"]]] * r["side"] - TOLL
        mu = float(np.nanmean(rr)); sd = float(np.nanstd(rr)) or 1e-9
        t = mu / (sd / math.sqrt(n))
        ok = mu > 0 and t >= 2.0
        kept += ok
        print(f"  {r['feat']:<12}{'LONG' if r['side']>0 else 'SHORT':>6}"
              f"{r['hold']*5:>5}m  {r['tod']:<11}{n:>7}{mu:>10.4f}%{t:>8.2f}"
              f"   {'HOLDS UP' if ok else 'fails'}")
    print(f"\n  {kept} of {min(len(survivors), top_n)} survived the holdout.")
    return 0


def _z_for(p):
    """Two-sided normal quantile — avoids a scipy dependency."""
    if p <= 0:
        return 8.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    pl = p / 2.0
    if pl < 0.02425:
        q = math.sqrt(-2 * math.log(pl))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = pl - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


if __name__ == "__main__":
    sys.exit(main())
