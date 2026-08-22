#!/usr/bin/env python3
"""
test-classic-swing — the canonical "awesome-list" strategies on 5 years of dailies.

WHY (2026-08-22, Soumya): an Instagram reel (gittrend.io) promoting the curated
algo-trading lists — "40+ strategies" — prompted the question: do the textbook
systems those lists catalogue make money on OUR market with HONEST costs? Every
thesis we killed was intraday; these are daily-bar swing systems, genuinely untested
here. The new swing lane makes the answer directly actionable.

THE COST MODEL — and a correction it forced
Multi-day holds are CNC DELIVERY, not intraday MIS. Zerodha delivery: brokerage 0,
but STT is 0.1% on EACH side (vs 0.025% sell-only intraday), stamp 0.015% buy,
DP charge ~Rs15.93+GST per sell, exchange txn 0.00297%x2, SEBI, GST. On a Rs115k
position that is ~0.24% round trip — THREE TIMES the 0.0787% we have been modelling
for v5_swing. (Flagged: the swing lane's live accounting needs the same fix.)

THE STRATEGIES (long-only, as the lists canonically state them)
  sma_cross    close crosses above SMA20 with SMA20>SMA50; exit cross back under
  rsi2         Connors RSI(2)<10 with close>SMA200; exit RSI(2)>70 or 5 sessions
  boll_rev     close < lower Bollinger(20,2) with close>SMA200; exit at mid-band
  mom_rotate   monthly: top-10 by 6-month return, hold a month, rotate
  hi52_break   close makes a 250-day high; 10% trailing stop on closes

THE GATE, fixed in advance
  Train 2021-06..2024-12 (context only — these systems have no parameters to fit;
  the split guards against my own selective reading). Holdout 2025-01..2026-06.
  Real = holdout net > 0 after 0.24% with t > 2.

Data: quant/data/eod/*.parquet (201 symbols, 2021-06..2026-06).
Run:  python3 scripts/test-classic-swing.py
"""
from __future__ import annotations

import glob, json, math, statistics as st, sys, warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
EOD = ROOT / "quant" / "data" / "eod"
OUT = ROOT / "1cr-roadmap" / "research"

CNC_COST = 0.24          # % round trip, delivery (see docstring)
SPLIT = "2025-01-01"
GATE_T, GATE_N = 2.0, 100


def load():
    out = {}
    for f in sorted(EOD.glob("*.parquet")):
        s = f.stem
        try:
            d = pd.read_parquet(f)
            if len(d) > 300 and {"Open", "High", "Low", "Close"} <= set(d.columns):
                d = d.sort_index()
                out[s] = d
        except Exception:
            pass
    return out


def rsi(series, n):
    delta = series.diff()
    up = delta.clip(lower=0).rolling(n).mean()
    dn = (-delta.clip(upper=0)).rolling(n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def trades_sma_cross(d):
    c = d["Close"]; s20 = c.rolling(20).mean(); s50 = c.rolling(50).mean()
    sig = (c > s20) & (s20 > s50)
    out, ent = [], None
    for i in range(51, len(d)):
        if ent is None and sig.iloc[i] and not sig.iloc[i - 1]:
            ent = (d.index[i], float(c.iloc[i]))
        elif ent is not None and not sig.iloc[i]:
            out.append((ent[0], d.index[i], (float(c.iloc[i]) / ent[1] - 1) * 100))
            ent = None
    return out


def trades_rsi2(d):
    c = d["Close"]; r2 = rsi(c, 2); s200 = c.rolling(200).mean()
    out, ent, held = [], None, 0
    for i in range(201, len(d)):
        if ent is None and r2.iloc[i] < 10 and c.iloc[i] > s200.iloc[i]:
            ent = (d.index[i], float(c.iloc[i])); held = 0
        elif ent is not None:
            held += 1
            if r2.iloc[i] > 70 or held >= 5:
                out.append((ent[0], d.index[i], (float(c.iloc[i]) / ent[1] - 1) * 100))
                ent = None
    return out


def trades_boll(d):
    c = d["Close"]; ma = c.rolling(20).mean(); sd = c.rolling(20).std()
    lower, mid = ma - 2 * sd, ma
    s200 = c.rolling(200).mean()
    out, ent = [], None
    for i in range(201, len(d)):
        if ent is None and c.iloc[i] < lower.iloc[i] and c.iloc[i] > s200.iloc[i]:
            ent = (d.index[i], float(c.iloc[i]))
        elif ent is not None and c.iloc[i] >= mid.iloc[i]:
            out.append((ent[0], d.index[i], (float(c.iloc[i]) / ent[1] - 1) * 100))
            ent = None
    return out


def trades_hi52(d):
    c = d["Close"]; hi = c.rolling(250).max()
    out, ent, peak = [], None, 0.0
    for i in range(251, len(d)):
        px = float(c.iloc[i])
        if ent is None and px >= float(hi.iloc[i]) and px > float(hi.iloc[i - 1]):
            ent = (d.index[i], px); peak = px
        elif ent is not None:
            peak = max(peak, px)
            if px <= peak * 0.90:
                out.append((ent[0], d.index[i], (px / ent[1] - 1) * 100))
                ent = None
    if ent is not None:
        out.append((ent[0], d.index[-1], (float(c.iloc[-1]) / ent[1] - 1) * 100))
    return out


def momentum_rotation(frames):
    """Cross-sectional: month-end, rank by 6-month return, hold top 10 a month."""
    closes = pd.DataFrame({s: d["Close"] for s, d in frames.items()}).sort_index()
    monthly = closes.resample("ME").last()
    rets = []
    for i in range(7, len(monthly) - 1):
        r6 = monthly.iloc[i] / monthly.iloc[i - 6] - 1
        top = r6.dropna().nlargest(10).index
        fwd = (monthly.iloc[i + 1][top] / monthly.iloc[i][top] - 1) * 100
        for s, r in fwd.dropna().items():
            rets.append((monthly.index[i], r))
    return rets


def report(name, rows):
    """rows: list of (entry_date, ret_pct) after split into train/hold by entry."""
    res = {}
    for bucket, sel in (("train", lambda dt: str(dt) < SPLIT),
                        ("hold", lambda dt: str(dt) >= SPLIT)):
        v = [r - CNC_COST for dt, r in rows if sel(dt)]
        if len(v) < 3:
            res[bucket] = dict(n=len(v), net=0.0, t=0.0)
            continue
        m = st.mean(v); sd = st.pstdev(v)
        res[bucket] = dict(n=len(v), net=round(m, 3),
                           t=round(m / (sd / math.sqrt(len(v))), 2) if sd else 0,
                           win=round(sum(1 for x in v if x > 0) / len(v) * 100))
    h = res["hold"]
    ok = h["net"] > 0 and h["t"] > GATE_T and h["n"] >= GATE_N
    print(f"  {name:<12} train n={res['train']['n']:>5} net {res['train']['net']:>+7.3f}% "
          f"| HOLDOUT n={h['n']:>5} net {h['net']:>+7.3f}% t={h['t']:>+6.2f} "
          f"win {h.get('win','-')}%  {'<< SURVIVES' if ok else ''}")
    return name, res, ok


def main():
    frames = load()
    print(f"  {len(frames)} symbols, daily 2021-06..2026-06 | CNC cost {CNC_COST}% | "
          f"holdout from {SPLIT}\n")
    results, survivors = {}, []
    strategies = [("sma_cross", trades_sma_cross), ("rsi2", trades_rsi2),
                  ("boll_rev", trades_boll), ("hi52_break", trades_hi52)]
    for name, fn in strategies:
        rows = []
        for s, d in frames.items():
            for e, x, r in fn(d):
                rows.append((e.date() if hasattr(e, "date") else e, r))
        n, res, ok = report(name, rows)
        results[n] = res
        if ok:
            survivors.append(n)
    rows = momentum_rotation(frames)
    n, res, ok = report("mom_rotate", [(dt.date(), r) for dt, r in rows])
    results[n] = res
    if ok:
        survivors.append(n)

    print(f"\n  GATE: holdout (2025+) net>0 after {CNC_COST}%, t>{GATE_T}, n>={GATE_N}")
    print(f"  VERDICT: {'SURVIVORS: ' + ', '.join(survivors) if survivors else 'none survive'}")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "classic-swing-result.json").write_text(json.dumps(
        {"cost": CNC_COST, "split": SPLIT, "results": results,
         "survivors": survivors}, indent=2))
    print(f"  wrote {OUT}/classic-swing-result.json")


if __name__ == "__main__":
    main()
