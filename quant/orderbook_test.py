#!/usr/bin/env python3
"""
orderbook_test — does order-flow imbalance predict, and does it beat the toll?

The last untested information source. Everything else this project has measured is
derived from OHLCV; the book is genuinely different data — resting intent rather
than completed trades. Order-flow imbalance is also one of the better-documented
short-horizon predictors in the microstructure literature, so unlike the rest of our
grid there is a prior reason to expect signal.

The catch, stated before looking: OFI decays in seconds to minutes, and our round
trip costs 0.106%. A signal that is real and lasts ninety seconds is still useless
if the move inside that window is smaller than the fee.

SAME DEFENCES AS EVERY OTHER TEST HERE
  - train/holdout split by DATE, fixed before evaluation
  - market-neutral returns as well as raw, because a book-wide tilt on a rising day
    is beta and we have already been fooled by that once today
  - full 0.106% charged
  - the null is reported

    python3 quant/orderbook_test.py
"""
from __future__ import annotations
import gzip, json, math, sys, warnings
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import numpy as np

BOOK = ROOT / "docs" / "research" / "orderbook"
TOLL = 0.106
HORIZONS = (2, 10, 30, 60)      # snapshots ~30s apart -> ~1, 5, 15, 30 minutes


def load_day(p):
    op = gzip.open if p.suffix == ".gz" else open
    out = []
    with op(p, "rt") as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            if not d.get("ltp"):
                continue
            out.append(d)
    return out


def build(days):
    """Per symbol-day, a time-ordered series with book features and forward returns."""
    rows = []
    for p in days:
        recs = load_day(p)
        by = defaultdict(list)
        for d in recs:
            by[d["sym"]].append(d)
        day = p.name.split(".")[0]
        for sym, series in by.items():
            series.sort(key=lambda d: d["ts"])
            n = len(series)
            if n < 120:
                continue
            ltp = np.array([float(d["ltp"]) for d in series])
            for i in range(5, n - max(HORIZONS) - 1):
                d = series[i]
                px = ltp[i]
                if px <= 0:
                    continue
                tb = float(d.get("total_buy_qty") or 0)
                ts_ = float(d.get("total_sell_qty") or 0)
                bq = float(d.get("bid_qty") or 0)
                aq = float(d.get("ask_qty") or 0)
                # depth-weighted imbalance across the visible ladder
                bids = d.get("bids") or []
                asks = d.get("asks") or []
                bw = sum(q for _, q, _ in bids[:5])
                aw = sum(q for _, q, _ in asks[:5])
                feats = (
                    float(d.get("imbalance") or 0),                      # top of book
                    (tb - ts_) / (tb + ts_) if (tb + ts_) else 0.0,      # full book
                    (bw - aw) / (bw + aw) if (bw + aw) else 0.0,         # 5-level
                    float(d.get("spread_bps") or 0),
                    (ltp[i] / ltp[i - 5] - 1) * 100,                     # recent drift
                )
                fwd = [(ltp[i + h] / px - 1) * 100 for h in HORIZONS]
                rows.append((day, sym, d["ts"][11:16], *feats, *fwd))
    return rows


def main():
    files = sorted(BOOK.glob("2026-*.ndjson*"))
    if not files:
        print("  no order-book files found")
        return 1
    print(f"  {len(files)} sessions: {files[0].name.split('.')[0]} -> "
          f"{files[-1].name.split('.')[0]}")
    print("  loading (this is ~2M snapshots)...", flush=True)
    rows = build(files)
    print(f"  {len(rows):,} decision points\n")

    day = np.array([r[0] for r in rows])
    A = np.array([r[3:] for r in rows], dtype=float)
    days = sorted(set(day))
    cut = days[int(len(days) * 0.67)]
    tr, ho = day < cut, day >= cut
    print(f"  TRAIN < {cut} <= HOLDOUT   ({tr.sum():,} / {ho.sum():,} rows)\n")

    FN = ["imbalance_top", "imbalance_book", "imbalance_5lvl", "spread_bps", "drift"]
    FC = {n: i for i, n in enumerate(FN)}
    HC = {h: 5 + i for i, h in enumerate(HORIZONS)}

    # market-neutral: strip the cross-sectional mean at each (day, time)
    key = np.char.add(np.char.add(day, "|"), np.array([r[2] for r in rows]))
    neu = A.copy()
    idx = defaultdict(list)
    for i, k in enumerate(key):
        idx[k].append(i)
    for k, ii in idx.items():
        ii = np.array(ii)
        for h in HORIZONS:
            c = HC[h]
            neu[ii, c] = A[ii, c] - np.nanmean(A[ii, c])

    def ic(x, y):
        ok = np.isfinite(x) & np.isfinite(y)
        return float(np.corrcoef(x[ok], y[ok])[0, 1]) if ok.sum() > 500 else 0.0

    print("  INFORMATION COEFFICIENT (market-neutral forward returns)")
    print(f"  {'feature':<18}" + "".join(f"{h//2:>8}min" for h in HORIZONS))
    for n in FN:
        print(f"  {n:<18}" + "".join(
            f"{ic(A[:, FC[n]], neu[:, HC[h]]):>+11.4f}" for h in HORIZONS))

    print("\n  DECILE SPREAD ON HOLDOUT — gross, and per trade after the toll")
    print(f"  {'feature':<18}{'horizon':>9}{'top':>10}{'bottom':>10}"
          f"{'per-trade':>11}{'net':>10}{'t':>8}")
    best = []
    for n in FN[:3]:
        x = A[:, FC[n]]
        for h in HORIZONS:
            y = neu[:, HC[h]]
            ok = np.isfinite(x) & np.isfinite(y) & ho
            if ok.sum() < 5000:
                continue
            xs, ys = x[ok], y[ok]
            lo, hi = np.quantile(xs, 0.1), np.quantile(xs, 0.9)
            top, bot = ys[xs >= hi], ys[xs <= lo]
            per = (top.mean() - bot.mean()) / 2
            sd = math.sqrt(top.var() / len(top) + bot.var() / len(bot)) / 2 or 1e-9
            best.append((per - TOLL, n, h, top.mean(), bot.mean(), per, per / sd))
    best.sort(reverse=True)
    for netedge, n, h, t, b, per, tstat in best[:10]:
        print(f"  {n:<18}{h//2:>8}m{t:>9.4f}%{b:>9.4f}%{per:>10.4f}%"
              f"{per-TOLL:>+9.4f}%{tstat:>8.2f}")
    print()
    win = [x for x in best if x[0] > 0]
    if win:
        print(f"  {len(win)} configuration(s) beat the toll. Best: {win[0][1]} at "
              f"{win[0][2]//2}min, net {win[0][0]:+.4f}%/trade")
    else:
        print("  NOTHING beats the 0.106% toll.")
        gross = max(b[5] for b in best)
        print(f"  best gross edge {gross:.4f}% vs toll 0.106% "
              f"— short by {0.106-gross:.4f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
