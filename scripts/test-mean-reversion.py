#!/usr/bin/env python3
"""
test-mean-reversion — does fading beat following, after costs?

THE FOUR QUESTIONS, set before any result was seen
  1. INVERT L3       does trading AGAINST daily bias beat trading WITH it?
  2. REVERSAL DEPTH  short_term_reversal fires at +/-3% over 5 days. Is there a
                     threshold where the edge clears the toll?
  3. REVERSAL + SIZE the two findings interact. At Rs108k a round trip costs
                     0.0787%; below Rs66,667 it costs 0.1060%. A signal can clear
                     at size and fail below the cliff.
  4. REGIME          does reversion work in RISK_ON and fail in RISK_OFF? If it is
                     regime-specific, L1 stays a hard veto and L3 flips beneath it.

KILL CRITERIA, fixed in advance so the test cannot be argued with afterwards
  If inverted-bias does not beat a random entry at t > 2 over >= 300 setups after
  costs, mean reversion is DEAD as a thesis and the spec's L3 is deleted rather
  than inverted. Same gate that killed the SMC thesis in a day.

WHY THIS IS A BACKTEST AND NOT A LIVE SHADOW
A backtest can kill a thesis definitively and can never confirm one. We are trying
to kill this cheaply before building anything, exactly as with SMC.

THE EVIDENCE THAT PROMPTED IT (2026-08-10, 145,500 simulated trades)
  trading WITH daily bias     -0.0389% gross
  trading AGAINST daily bias  +0.0033% gross
  short_term_reversal         best of 10 predicates
  mtf_alignment (trend)       9th of 10
Three independent readings, all saying this market mean-reverts intraday.

Run:
    python3 scripts/test-mean-reversion.py
    python3 scripts/test-mean-reversion.py --limit 40
"""
from __future__ import annotations

import argparse
import json
import logging
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
from prototype.waterfall import predicates as P   # noqa: E402

CACHE = ROOT / "prototype" / "data" / "waterfall"
OUT = ROOT / "1cr-roadmap" / "research"

COST_SMALL = 0.1060      # <= Rs66,667 per position — where every engine has lived
COST_SIZE  = 0.0787      # ~Rs108,000 per position — v5_size's measured rate
TARGET_PCT, STOP_PCT = 1.2, 0.6
TIME_STOP, FIRST, LAST = dtime(14, 45), dtime(9, 30), dtime(14, 0)
SEEDS = 5
MIN_SETUPS = 300         # kill-criterion floor

logger = logging.getLogger("meanrev")


def simulate(day5, i, side):
    """Identical to the falsification harness: fixed dumb exit, stop assumed to fill
    first when a bar spans both. One variable at a time."""
    if i >= len(day5) - 1:
        return None
    entry = float(day5["Close"].iloc[i])
    if not np.isfinite(entry) or entry <= 0:
        return None
    sgn = 1 if side == "long" else -1
    tgt, stp = entry * (1 + sgn * TARGET_PCT / 100), entry * (1 - sgn * STOP_PCT / 100)
    for j in range(i + 1, len(day5)):
        b, ts = day5.iloc[j], day5.index[j]
        hi, lo = float(b["High"]), float(b["Low"])
        ht = (hi >= tgt) if sgn > 0 else (lo <= tgt)
        hs = (lo <= stp) if sgn > 0 else (hi >= stp)
        if ht and hs:
            return -STOP_PCT
        if hs:
            return -STOP_PCT
        if ht:
            return TARGET_PCT
        if ts.time() >= TIME_STOP:
            return sgn * (float(b["Close"]) - entry) / entry * 100
    return sgn * (float(day5["Close"].iloc[-1]) - entry) / entry * 100


def tstat(vals, cost):
    if len(vals) < 3:
        return 0.0, 0.0
    net = [v - cost for v in vals]
    sd = st.pstdev(net)
    return st.mean(net), (st.mean(net) / (sd / math.sqrt(len(net))) if sd else 0.0)


def line(label, vals, cost, base=None):
    if not vals:
        print(f"  {label:<34}{'—':>8}")
        return None
    m, t = tstat(vals, cost)
    vs = f"{m - base:+.4f}" if base is not None else ""
    flag = "SURVIVES" if (m > 0 and t > 2 and len(vals) >= MIN_SETUPS) else ""
    print(f"  {label:<34}{len(vals):>7,}{st.mean(vals):>10.4f}{m:>10.4f}{t:>8.2f}{vs:>10}  {flag}")
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="  %(message)s")

    files = sorted(CACHE.glob("*_5m.parquet"))
    syms = [f.name[:-11] for f in files if not f.name.startswith("^")]
    if a.limit:
        syms = syms[:a.limit]
    logger.info(f"{len(syms)} symbols from cache | cost {COST_SMALL}% small / "
                f"{COST_SIZE}% at size | exit {TARGET_PCT}/{STOP_PCT}")

    # NIFTY daily as the regime reference: above its 20d mean = RISK_ON.
    nif = pd.read_parquet(CACHE / "^NSEI_1d.parquet") if (CACHE / "^NSEI_1d.parquet").exists() else None
    regime = {}
    if nif is not None:
        for i in range(25, len(nif)):
            d = str(nif.index[i].date())
            regime[d] = "RISK_ON" if float(nif["Close"].iloc[i]) > float(nif["Close"].iloc[i-20:i].mean()) else "RISK_OFF"

    rng = np.random.default_rng(a.seed)
    withb, againstb, rand = [], [], []
    depth = {k: [] for k in (1, 2, 3, 4, 5, 6)}
    by_regime = {"RISK_ON": [], "RISK_OFF": []}

    for n, s in enumerate(syms, 1):
        try:
            b5 = pd.read_parquet(CACHE / f"{s}_5m.parquet")
            bd = pd.read_parquet(CACHE / f"{s}_1d.parquet")
        except Exception:
            continue
        for day, day5 in b5.groupby(b5.index.date):
            day5 = day5.between_time("09:15", "15:30")
            if len(day5) < 20:
                continue
            as_of = pd.Timestamp(day)
            bias = P.daily_bias(bd, as_of)
            b = bias["bias"]
            if b not in ("long", "short"):
                continue
            inv = "short" if b == "long" else "long"
            # one decision per stock-day, at a fixed time, so entry timing is not a variable
            idx = [i for i, ts in enumerate(day5.index)
                   if FIRST <= ts.time() <= LAST]
            if len(idx) < 4:
                continue
            i0 = idx[len(idx) // 3]
            rw, ra = simulate(day5, i0, b), simulate(day5, i0, inv)
            if rw is not None:
                withb.append(rw)
            if ra is not None:
                againstb.append(ra)
                reg = regime.get(str(day))
                if reg:
                    by_regime[reg].append(ra)
            for sd in range(SEEDS):
                rr = simulate(day5, idx[rng.integers(len(idx))],
                              "long" if rng.integers(2) else "short")
                if rr is not None:
                    rand.append(rr)
            # reversal depth: fade the 5-day move, threshold swept
            d = P.before(bd, as_of)
            if d is not None and len(d) > 6:
                r5 = (float(d["Close"].iloc[-1]) / float(d["Close"].iloc[-6]) - 1) * 100
                for th in depth:
                    if abs(r5) >= th:
                        side = "long" if r5 < 0 else "short"   # fade the move
                        rv = simulate(day5, i0, side)
                        if rv is not None:
                            depth[th].append(rv)
        if n % 40 == 0:
            logger.info(f"  {n}/{len(syms)} symbols")

    print(f"\n  {'':34}{'n':>7}{'gross%':>10}{'net%':>10}{'t':>8}{'vs rnd':>10}")
    print("  " + "-" * 81)
    rbase, _ = tstat(rand, COST_SMALL)
    print(f"  {'RANDOM BASELINE':<34}{len(rand):>7,}{st.mean(rand):>10.4f}{rbase:>10.4f}")
    print()
    print("  Q1 — INVERT L3 (cost 0.1060%, small positions)")
    line("with daily bias", withb, COST_SMALL, rbase)
    inv_small = line("AGAINST daily bias", againstb, COST_SMALL, rbase)

    print("\n  Q3 — SAME SIGNAL AT SIZE (cost 0.0787%)")
    line("with daily bias @ size", withb, COST_SIZE, rbase)
    inv_size = line("AGAINST daily bias @ size", againstb, COST_SIZE, rbase)

    print("\n  Q2 — REVERSAL DEPTH (fade an N% 5-day move, cost at size)")
    for th in sorted(depth):
        line(f"fade >= {th}% move", depth[th], COST_SIZE, rbase)

    print("\n  Q4 — REGIME CONDITIONING (against-bias, cost at size)")
    for reg in ("RISK_ON", "RISK_OFF"):
        line(reg, by_regime[reg], COST_SIZE, rbase)

    # ---- the kill gate, applied exactly as written in advance
    m, t = tstat(againstb, COST_SIZE)
    ok = (len(againstb) >= MIN_SETUPS and t > 2 and m > rbase)
    print("\n  " + "=" * 81)
    print(f"  KILL GATE: inverted bias needs n>={MIN_SETUPS}, t>2, and beat random")
    print(f"    n={len(againstb):,}  t={t:+.2f}  net={m:+.4f}%  random={rbase:+.4f}%")
    if ok:
        print("    -> SURVIVES. Mean reversion stays alive; L3 gets INVERTED, not deleted.")
        print("       A backtest cannot confirm — re-run on a held-out period next.")
    else:
        print("    -> DEAD. Delete L3 from the spec rather than inverting it.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mean-reversion-result.json").write_text(json.dumps({
        "cost_small": COST_SMALL, "cost_size": COST_SIZE,
        "random_net": round(rbase, 4),
        "with_bias_n": len(withb), "against_bias_n": len(againstb),
        "against_net_small": round(inv_small, 4) if inv_small is not None else None,
        "against_net_size": round(inv_size, 4) if inv_size is not None else None,
        "t": round(t, 2), "survives": bool(ok),
        "depth": {str(k): {"n": len(v), "net_at_size": round(st.mean(v) - COST_SIZE, 4)}
                  for k, v in depth.items() if v},
        "regime": {k: {"n": len(v), "net_at_size": round(st.mean(v) - COST_SIZE, 4)}
                   for k, v in by_regime.items() if v},
    }, indent=2))
    print(f"  wrote {OUT}/mean-reversion-result.json\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
