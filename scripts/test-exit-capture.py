#!/usr/bin/env python3
"""
test-exit-capture — could a different EXIT rule have kept the profit our winners
gave back, without paying more in whipsaw stops than it recovers?

THE QUESTION (from the 2026-08-17 autopsy)
Rs23,629 of that day's Rs38,178 in-trade ceiling sat inside STOPPED-OUT trades that
were profitable at their peak. Mechanism: the trailing stop arms only at +1.0%;
whipsaw days tag +0.6-0.9%, never arm the trail, then reverse through the full stop.
The band between "in profit" and "trail armed" is where winners round-trip.

THE DISCIPLINE
  - Entries are EXACTLY the trades the engines took (symbol, date, time, side,
    entry price, stop, target from the trade record). Only the exit rule varies.
    One variable at a time — same isolation as test-timeframe.py.
  - Every policy replays on the same trades -> PAIRED per-trade differences vs the
    baseline replay, which is far more powerful than unpaired comparison.
  - The baseline is REPLAYED too (not the booked P&L), so simulator bias cancels
    in the pairing. Booked-vs-replayed agreement is reported as a sanity check.
  - Bars: the 60-day 5m parquet cache from the falsification run (on disk, no API).
  - When a bar spans both stop and target, the STOP fills first. Pessimistic by
    construction — optimistic ordering is how backtests manufacture edge.

THE KILL GATE, fixed in advance
A candidate policy must beat the baseline replay by t > 2 on paired per-trade
deltas over >= 300 trades, net of costs at BOTH fee rates (0.1060% small /
0.0787% at size). Otherwise the current exit stands.

MFE CAPTURE is reported per policy: realized / max-favorable-excursion, the direct
measure of "how much of the Rs38k-class ceiling this rule keeps".

Run:
    python3 scripts/test-exit-capture.py                    # v5, full cache window
    python3 scripts/test-exit-capture.py --engine v5_wide
    python3 scripts/test-exit-capture.py --limit-days 20
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import statistics as st
import sys
import warnings
from datetime import time as dtime
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CACHE = ROOT / "prototype" / "data" / "waterfall"
OUT = ROOT / "1cr-roadmap" / "research"

FORCE_EXIT = dtime(15, 15)
COST_SMALL, COST_SIZE = 0.1060, 0.0787
MIN_PAIRS = 300

# ── policies ────────────────────────────────────────────────────────────────
# Each: (name, arm_pct, step_pct, breakeven_at) — arm/step in %, breakeven_at
# moves the stop to entry once that % is reached (None = never).
# "atr" policies scale arm/step to the symbol-day's 5m ATR14 instead of fixed %.
POLICIES = [
    ("baseline arm1.0/step0.5", 1.00, 0.50, None),      # today's live rule
    ("arm0.5/step0.25",         0.50, 0.25, None),
    ("arm0.5/step0.5",          0.50, 0.50, None),
    ("arm0.3/step0.25",         0.30, 0.25, None),
    ("arm0.75/step0.25",        0.75, 0.25, None),
    ("be@0.4 + arm1.0",         1.00, 0.50, 0.40),      # breakeven early, trail late
    ("be@0.6 + arm1.0",         1.00, 0.50, 0.60),
    ("atr: arm1.5A/step0.75A",  "atr1.5", "atr0.75", None),
    ("no-trail (target/stop)",  None, None, None),
]


def load_trades(engine: str, day_min: str, day_max: str):
    """Every closed trade with a usable entry record inside the bar-cache window."""
    out = []
    for f in sorted(glob.glob(str(ROOT / "docs" / "paper-trades" / engine / "20??-??-??.json"))):
        day = Path(f).stem
        if not (day_min <= day <= day_max):
            continue
        try:
            j = json.loads(Path(f).read_text())
        except Exception:
            continue
        if j.get("VOID"):
            continue
        for pl in (j.get("pools") or {}).values():
            for c in (pl.get("closed") or []):
                ep = c.get("entry_price"); q = c.get("qty")
                et = (c.get("entry_time") or "")[:5]
                if not ep or not q or not et or c.get("entry_date") != day:
                    continue   # same-day intraday entries only — multi-day carries
                               # have overnight gaps this replay cannot price
                side = "SHORT" if (c.get("position_type") or "LONG").upper() == "SHORT" else "LONG"
                out.append(dict(
                    sym=c["symbol"], day=day, et=et, side=side,
                    ep=float(ep), q=int(q),
                    sl=float(c.get("sl_price") or 0) or None,
                    tp=float(c.get("target_price") or 0) or None,
                    booked=float(c.get("pnl_pct") or 0)))
    return out


_bars_cache = {}


def day_bars(sym: str, day: str):
    key = (sym, day)
    if key in _bars_cache:
        return _bars_cache[key]
    f = CACHE / f"{sym}.NS_5m.parquet"
    val = None
    if f.exists():
        try:
            df = pd.read_parquet(f)
            d = df[df.index.strftime("%Y-%m-%d") == day].between_time("09:15", "15:30")
            if len(d) >= 10:
                val = list(zip(d.index.strftime("%H:%M"),
                               d["Open"].astype(float), d["High"].astype(float),
                               d["Low"].astype(float), d["Close"].astype(float)))
        except Exception:
            val = None
    _bars_cache[key] = val
    return val


def atr14(bars, upto_idx):
    """5m ATR14 as a % of price, from bars up to (not incl.) the entry bar."""
    lo = max(1, upto_idx - 14)
    trs = []
    for i in range(lo, upto_idx):
        _, o, h, l, c = bars[i]
        pc = bars[i - 1][4]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return None
    return st.mean(trs) / bars[upto_idx - 1][4] * 100


def replay(bars, i0, t, arm, step, be_at):
    """Replay one trade under one policy. Returns (pnl_pct, mfe_pct, reason)."""
    sgn = 1 if t["side"] == "LONG" else -1
    ep = t["ep"]
    # stops/targets from the record where present, else engine defaults
    stop = t["sl"] if t["sl"] else ep * (1 - sgn * 0.015)
    tgt = t["tp"] if t["tp"] else ep * (1 + sgn * 0.02)
    # ATR-scaled policies resolve their %s per trade
    if isinstance(arm, str):
        a = atr14(bars, i0)
        if a is None:
            return None
        arm_pct = float(arm[3:]) * a
        step_pct = float(step[3:]) * a
    else:
        arm_pct, step_pct = arm, step

    best = ep
    mfe = 0.0
    trail = None
    for i in range(i0, len(bars)):
        tm, o, h, l, c = bars[i]
        fav = (h - ep) / ep * 100 * sgn if sgn > 0 else (ep - l) / ep * 100
        mfe = max(mfe, fav)
        # pessimistic ordering: adverse levels first
        hit_stop = (l <= stop) if sgn > 0 else (h >= stop)
        hit_trail = trail is not None and ((l <= trail) if sgn > 0 else (h >= trail))
        if hit_stop or hit_trail:
            px = stop if hit_stop and (trail is None or (stop > trail if sgn > 0 else stop < trail) is False) else (trail if hit_trail else stop)
            # fill at the worse of the two levels touched
            if hit_stop and hit_trail:
                px = min(stop, trail) if sgn > 0 else max(stop, trail)
            elif hit_trail:
                px = trail
            else:
                px = stop
            return (sgn * (px - ep) / ep * 100, mfe, "STOP/TRAIL")
        hit_tgt = (h >= tgt) if sgn > 0 else (l <= tgt)
        if hit_tgt and arm is not None:
            return (sgn * (tgt - ep) / ep * 100, mfe, "TARGET")
        if hit_tgt and arm is None:
            return (sgn * (tgt - ep) / ep * 100, mfe, "TARGET")
        # update best + trail on the bar close (no intrabar lookahead)
        if sgn > 0:
            best = max(best, c)
        else:
            best = min(best, c)
        run = sgn * (best - ep) / ep * 100
        if be_at is not None and run >= be_at:
            if sgn > 0:
                stop = max(stop, ep)
            else:
                stop = min(stop, ep)
        if arm_pct is not None and arm is not None and run >= arm_pct:
            lvl = best * (1 - sgn * step_pct / 100)
            trail = lvl if trail is None else (max(trail, lvl) if sgn > 0 else min(trail, lvl))
        if tm >= FORCE_EXIT.strftime("%H:%M"):
            return (sgn * (c - ep) / ep * 100, mfe, "FORCE")
    _, o, h, l, c = bars[-1]
    return (sgn * (c - ep) / ep * 100, mfe, "EOD")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="v5")
    ap.add_argument("--limit-days", type=int, default=0)
    a = ap.parse_args()

    # cache window = what the parquet files actually hold
    probe = sorted(CACHE.glob("RELIANCE.NS_5m.parquet"))
    if not probe:
        print("  no bar cache — run falsify-predicates.py first"); return 1
    df = pd.read_parquet(probe[0])
    days = sorted(set(df.index.strftime("%Y-%m-%d")))
    day_min, day_max = days[0], days[-1]
    if a.limit_days:
        day_min = days[-a.limit_days]
    trades = load_trades(a.engine, day_min, day_max)
    print(f"  {a.engine}: {len(trades)} same-day trades in cache window {day_min}..{day_max}")

    # replay every policy on every trade
    rows = {name: [] for name, *_ in POLICIES}
    mfes = []
    booked_vs_base = []
    usable = 0
    for t in trades:
        bars = day_bars(t["sym"], t["day"])
        if not bars:
            continue
        i0 = next((i for i, b in enumerate(bars) if b[0] >= t["et"]), None)
        if i0 is None or i0 >= len(bars) - 2:
            continue
        res = {}
        ok = True
        for name, arm, step, be in POLICIES:
            r = replay(bars, i0, t, arm, step, be)
            if r is None:
                ok = False
                break
            res[name] = r
        if not ok:
            continue
        usable += 1
        mfes.append(res[POLICIES[0][0]][1])
        booked_vs_base.append((t["booked"], res[POLICIES[0][0]][0]))
        for name in res:
            rows[name].append(res[name])

    print(f"  usable replays: {usable} (bars found + full policy set)")
    if usable < 50:
        print("  too few — aborting"); return 1

    # sanity: does the baseline replay track what was actually booked?
    bk = [b for b, _ in booked_vs_base]; rp = [r for _, r in booked_vs_base]
    corr = np.corrcoef(bk, rp)[0, 1]
    print(f"\n  SANITY — baseline replay vs booked P&L: mean {st.mean(bk):+.3f}% vs "
          f"{st.mean(rp):+.3f}%, corr {corr:.2f}")
    print("  (imperfect by design — booked fills happen between bars; the pairing "
          "cancels simulator bias)")

    base_name = POLICIES[0][0]
    base = [r[0] for r in rows[base_name]]
    avg_mfe = st.mean(mfes)
    print(f"\n  average MFE per trade: {avg_mfe:.3f}% — the ceiling every policy chases")
    print(f"\n  {'policy':<26}{'gross%':>8}{'capt%':>7}{'net@.106':>9}{'net@.079':>9}"
          f"{'Δ/trade':>9}{'t(pair)':>8}")
    print("  " + "-" * 78)
    results = {}
    for name, *_ in POLICIES:
        vals = [r[0] for r in rows[name]]
        g = st.mean(vals)
        capt = g / avg_mfe * 100 if avg_mfe else 0
        deltas = [v - b for v, b in zip(vals, base)]
        md = st.mean(deltas)
        sd = st.pstdev(deltas)
        tp = md / (sd / math.sqrt(len(deltas))) if sd > 0 else 0.0
        results[name] = dict(n=len(vals), gross=round(g, 4),
                             capture_pct=round(capt, 1),
                             net_small=round(g - COST_SMALL, 4),
                             net_size=round(g - COST_SIZE, 4),
                             delta=round(md, 4), t_paired=round(tp, 2))
        mark = ""
        if name != base_name and md > 0 and tp > 2 and len(deltas) >= MIN_PAIRS:
            mark = "  << BEATS BASELINE"
        print(f"  {name:<26}{g:>8.4f}{capt:>6.1f}%{g-COST_SMALL:>9.4f}"
              f"{g-COST_SIZE:>9.4f}{md:>+9.4f}{tp:>8.2f}{mark}")

    print(f"\n  KILL GATE: beat baseline on paired deltas, t>2, n>={MIN_PAIRS}, both fee rates.")
    winners = [k for k, v in results.items()
               if k != base_name and v["delta"] > 0 and v["t_paired"] > 2 and v["n"] >= MIN_PAIRS]
    if winners:
        print(f"  SURVIVORS: {', '.join(winners)}")
        print("  A backtest cannot confirm — a survivor earns a SHADOW ENGINE, not a live change.")
    else:
        print("  NOTHING SURVIVES — the current exit stands; the Rs38k ceiling is not")
        print("  recoverable by trail tuning on this evidence.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"exit-capture-{a.engine}.json").write_text(json.dumps(
        {"engine": a.engine, "window": [day_min, day_max], "usable": usable,
         "avg_mfe_pct": round(avg_mfe, 4),
         "replay_vs_booked_corr": round(float(corr), 3),
         "results": results}, indent=2))
    print(f"  wrote {OUT}/exit-capture-{a.engine}.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
