#!/usr/bin/env python3
"""
simulate-strategy-search — the full simulation: entries AND exits AND direction,
searched together over ~3.5 months, then verified on untouched data.

WHY THIS IS NOT "SEARCH UNTIL PROFIT APPEARS"
Searching until something works GUARANTEES finding something that worked — on the
data you searched. That is curve-fitting, and it is how strategies die on contact
with Monday. The protection, fixed before the first run:

  TRAIN    sessions before 2026-07-15  — search all 36 combos freely
  HOLDOUT  2026-07-15 onward           — the top 3 by train-t run ONCE, untouched
  GATE     a combo is "real" only if HOLDOUT net > 0 at 0.0787% fees with t > 2

36 combos are tested, so in-sample winners are expected BY CHANCE. Only the holdout
verdict counts. If nothing survives, the answer is "no profitable configuration in
this search space" — which is a result, not a failure.

THE SEARCH SPACE (bounded, pre-registered — 6 entries x 3 exits x 2 directions)
  Entries: conf5/conf6/conf7 (>=k of the 10 falsification predicates agreeing on a
           direction — confluence was the one monotonic positive from that run);
           pair (smt_divergence + short_term_reversal agreeing — best pair found);
           orb30 (30-min opening-range break); rev_open (fade the 5-day move at 09:30)
  Exits:   fixed tgt1.2/stop0.6 (the dumb control);
           trail arm0.3/step0.25 (yesterday's paired-test survivor);
           trail arm0.5/step0.25
  Dir:     both / long-only (the short book has bled historically — measured, so
           long-only earns a slot in the space)

Costs at 0.0787% (the at-size fee the fleet actually pays now). Stop-fills-first.
Bars: prototype/data/simcache (Kite, 2026-05-01 onward, fetched licensed).

Run:  python3 scripts/simulate-strategy-search.py            # full
      python3 scripts/simulate-strategy-search.py --limit 30 # smoke (symbols)
"""
from __future__ import annotations

import argparse, json, math, statistics as st, sys, warnings
from datetime import time as dtime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.waterfall import predicates as P   # noqa: E402

CACHE = ROOT / "prototype" / "data" / "simcache"
OUT = ROOT / "1cr-roadmap" / "research"
SPLIT = "2026-07-15"
FEE = 0.0787
FORCE = "15:15"
FIRST, LAST = "09:30", "14:00"
GATE_T, GATE_MIN_N = 2.0, 200

ENTRIES = ["conf5", "conf6", "conf7", "pair", "orb30", "rev_open"]
EXITS = ["fixed", "trail03", "trail05"]
DIRS = ["both", "long"]


def resample15(day5):
    return day5.resample("15min", label="right", closed="right").agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last",
         "Volume": "sum"}).dropna()


def signals_for_day(sym_bars, daily, day, ref_day_bars):
    """First directional fire per entry family for one stock-day.
    Returns {family: (bar_index, side)}. Mirrors the falsification harness."""
    day5 = sym_bars[sym_bars.index.strftime("%Y-%m-%d") == day].between_time("09:15", "15:30")
    if len(day5) < 30:
        return {}, day5
    as_of_day = pd.Timestamp(day)
    out = {}
    idxs = [i for i, ts in enumerate(day5.index) if FIRST <= ts.strftime("%H:%M") <= LAST]
    if not idxs:
        return {}, day5
    # rev_open: known before the session — fires at the first eligible bar
    r = P.short_term_reversal(daily, as_of_day)
    if r.get("signal"):
        out["rev_open"] = (idxs[0], r["signal"])
    orh = orl = None
    for i in idxs:
        ts = day5.index[i]
        hist5 = day5.iloc[:i]
        if len(hist5) < 6:
            continue
        # opening range (first 30 min)
        if orh is None and ts.strftime("%H:%M") >= "09:45":
            op = day5.between_time("09:15", "09:45")
            if len(op):
                orh, orl = float(op["High"].max()), float(op["Low"].min())
        if "orb30" not in out and orh is not None:
            c = float(hist5["Close"].iloc[-1])
            if c > orh:
                out["orb30"] = (i, "long")
            elif c < orl:
                out["orb30"] = (i, "short")
        need_conf = any(k not in out for k in ("conf5", "conf6", "conf7", "pair"))
        if not need_conf:
            continue
        prior = sym_bars[sym_bars.index < ts].tail(600)
        h15 = resample15(prior)
        votes = {"long": 0, "short": 0}
        fired = {}
        def cast(name, d):
            side = {"bullish": "long", "bearish": "short", "long": "long",
                    "short": "short"}.get(d)
            if side:
                votes[side] += 1
                fired[name] = side
        pools = P.liquidity_pools(h15) if len(h15) > 6 else []
        for pl in pools:
            s = P.liquidity_sweep(h15, pl["level"])
            if s.get("swept"):
                cast("sweep", s["dir"]); break
        for g in P.find_fvg(h15):
            if g["distance_pct"] < 0.3:
                cast("fvg", g["dir"]); break
        last = float(hist5["Close"].iloc[-1])
        for ob in P.find_order_blocks(h15):
            if ob["lo"] <= last <= ob["hi"]:
                cast("ob", ob["dir"]); break
        ph = P.amd_phase(h15, pools)
        if ph.get("phase") == "manipulation_complete":
            cast("amd", ph["dir"])
        if ref_day_bars is not None and len(ref_day_bars) > 20:
            ref_hist = ref_day_bars[ref_day_bars.index < ts]
            if len(ref_hist) > 20:
                sm = P.smt_divergence(hist5, ref_hist)
                if sm.get("smt"):
                    cast("smt", sm["dir"])
        if r.get("signal"):
            cast("rev", r["signal"])
        g2 = P.overnight_gap(daily, day5, as_of_day)
        if g2.get("signal"):
            cast("gap", g2["signal"])
        orb2 = P.opening_range(day5, ts)
        if orb2.get("signal"):
            cast("or", orb2["signal"])
        maj = "long" if votes["long"] >= votes["short"] else "short"
        n = votes[maj]
        for k, kk in (("conf5", 5), ("conf6", 6), ("conf7", 7)):
            if k not in out and n >= kk:
                out[k] = (i, maj)
        if "pair" not in out and fired.get("smt") and fired.get("rev") \
           and fired["smt"] == fired["rev"]:
            out["pair"] = (i, fired["smt"])
    return out, day5


def replay_exit(day5, i0, side, policy):
    sgn = 1 if side == "long" else -1
    ep = float(day5["Close"].iloc[i0])
    if not np.isfinite(ep) or ep <= 0:
        return None
    stop = ep * (1 - sgn * 0.006)
    tgt = ep * (1 + sgn * 0.012) if policy == "fixed" else None
    arm, step = ((0.3, 0.25) if policy == "trail03" else (0.5, 0.25)) \
        if policy != "fixed" else (None, None)
    best = ep; trail = None
    for j in range(i0 + 1, len(day5)):
        tm = day5.index[j].strftime("%H:%M")
        h, l, c = (float(day5["High"].iloc[j]), float(day5["Low"].iloc[j]),
                   float(day5["Close"].iloc[j]))
        if (l <= stop) if sgn > 0 else (h >= stop):
            return sgn * (stop - ep) / ep * 100
        if trail is not None and ((l <= trail) if sgn > 0 else (h >= trail)):
            return sgn * (trail - ep) / ep * 100
        if tgt is not None and ((h >= tgt) if sgn > 0 else (l <= tgt)):
            return sgn * (tgt - ep) / ep * 100
        best = max(best, c) if sgn > 0 else min(best, c)
        if arm is not None and sgn * (best - ep) / ep * 100 >= arm:
            lvl = best * (1 - sgn * step / 100)
            trail = lvl if trail is None else (max(trail, lvl) if sgn > 0 else min(trail, lvl))
        if tm >= FORCE:
            return sgn * (c - ep) / ep * 100
    return sgn * (float(day5["Close"].iloc[-1]) - ep) / ep * 100


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    files = sorted(CACHE.glob("*_5m.parquet"))
    syms = [f.name[:-11] for f in files if f.name != "NIFTY50_5m.parquet"]
    if a.limit:
        syms = syms[:a.limit]
    ref = pd.read_parquet(CACHE / "NIFTY50_5m.parquet") \
        if (CACHE / "NIFTY50_5m.parquet").exists() else None
    print(f"  {len(syms)} symbols | split at {SPLIT} | fee {FEE}% | "
          f"{len(ENTRIES)}x{len(EXITS)}x{len(DIRS)} = "
          f"{len(ENTRIES)*len(EXITS)*len(DIRS)} combos", flush=True)

    res = {}   # (entry, exit, dir) -> {"train": [], "hold": []}
    for e in ENTRIES:
        for x in EXITS:
            for d in DIRS:
                res[(e, x, d)] = {"train": [], "hold": []}

    for n, s in enumerate(syms, 1):
        try:
            b5 = pd.read_parquet(CACHE / f"{s}_5m.parquet")
        except Exception:
            continue
        daily = b5.resample("1D").agg({"Open": "first", "High": "max", "Low": "min",
                                       "Close": "last", "Volume": "sum"}).dropna()
        daily.index = daily.index.tz_localize(None).normalize()
        for day in sorted(set(b5.index.strftime("%Y-%m-%d"))):
            ref_day = (ref[ref.index.strftime("%Y-%m-%d") == day]
                       if ref is not None else None)
            sigs, day5 = signals_for_day(b5, daily, day, ref_day)
            if not sigs:
                continue
            bucket = "train" if day < SPLIT else "hold"
            for fam, (i0, side) in sigs.items():
                for x in EXITS:
                    r = replay_exit(day5, i0, side, x)
                    if r is None:
                        continue
                    net = r - FEE
                    res[(fam, x, "both")][bucket].append(net)
                    if side == "long":
                        res[(fam, x, "long")][bucket].append(net)
        if n % 20 == 0:
            tot = sum(len(v["train"]) + len(v["hold"]) for v in res.values())
            print(f"  {n}/{len(syms)} symbols, {tot:,} combo-trades", flush=True)

    def stats(vals):
        if len(vals) < 3:
            return dict(n=len(vals), net=0.0, t=0.0)
        m = st.mean(vals); sd = st.pstdev(vals)
        return dict(n=len(vals), net=round(m, 4),
                    t=round(m / (sd / math.sqrt(len(vals))), 2) if sd else 0.0)

    print(f"\n  ══ TRAIN (pre-{SPLIT}) — all 36, ranked ══", flush=True)
    print(f"  {'combo':<28}{'n':>7}{'net%':>9}{'t':>7}")
    ranked = []
    for k, v in res.items():
        tr = stats(v["train"])
        ranked.append((k, tr))
    ranked.sort(key=lambda x: -x[1]["t"])
    for k, tr in ranked[:12]:
        print(f"  {'/'.join(k):<28}{tr['n']:>7,}{tr['net']:>9.4f}{tr['t']:>7.2f}")

    top3 = [k for k, tr in ranked if tr["net"] > 0 and tr["n"] >= GATE_MIN_N][:3]
    print(f"\n  ══ HOLDOUT ({SPLIT} onward) — top 3 run ONCE ══")
    verdicts = {}
    for k in top3:
        hv = stats(res[k]["hold"])
        ok = hv["net"] > 0 and hv["t"] > GATE_T and hv["n"] >= GATE_MIN_N
        verdicts["/".join(k)] = dict(hold=hv, survives=bool(ok),
                                     train=dict(stats(res[k]["train"])))
        print(f"  {'/'.join(k):<28}{hv['n']:>7,}{hv['net']:>9.4f}{hv['t']:>7.2f}"
              f"   {'SURVIVES — REAL on this evidence' if ok else 'fails holdout'}")
    if not top3:
        print("  nothing on train was even net-positive with n>=200")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "strategy-search-result.json").write_text(json.dumps(
        {"split": SPLIT, "fee": FEE, "combos": len(res),
         "train": {"/".join(k): stats(v["train"]) for k, v in res.items()},
         "holdout_verdicts": verdicts}, indent=2))
    print(f"\n  wrote {OUT}/strategy-search-result.json")
    survivors = [k for k, v in verdicts.items() if v["survives"]]
    print(f"  VERDICT: {'SURVIVORS: ' + ', '.join(survivors) if survivors else 'NO configuration in this space is real-profitable at 0.0787% fees.'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
