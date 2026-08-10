#!/usr/bin/env python3
"""
falsify-predicates — Deliverable 1 of the agentic waterfall: the week-1 kill gate.

THE QUESTION, AND ONLY THIS QUESTION
    Do any of these predicates carry edge over history, after costs, against a random
    entry in the same stock on the same day?

WHY A BACKTEST AND NOT A WEEK OF FORWARD PAPER
50 stocks x 5 sessions = 250 stock-days; at a 10-20% setup rate that is 25-50 trades.
Detecting a 0.15% net edge against a ~1.3% per-trade spread at t=2 needs roughly
(2*1.3/0.15)^2 ~ 300 trades. A week forward is 6-12x short of the power required — which
is precisely how the previous two months produced no conclusion. 60 days x 200 stocks
gives ~12,000 stock-days and enough setups to actually decide.

THE ASYMMETRY THAT MAKES THIS VALID
A backtest can KILL a thesis definitively but can never confirm one. No edge in-sample
guarantees no edge out-of-sample; edge in-sample may be overfitting. This is a
falsification gate, not a validation gate. Read the output accordingly.

ONE VARIABLE AT A TIME
Every predicate uses the SAME dumb exit — 1.2% target, 0.6% stop, 14:45 time stop. The
test measures predicate quality, not exit tuning. This mirrors test-timeframe.py, which
held entries constant to isolate holding period.

THE CONTROL IS THE POINT
Each predicate is compared against a random entry on the same stock-day with identical
exits, over 5 seeds. A predicate that cannot beat random is not a signal, whatever its
win rate looks like. This is the test that exposed the current v5 engine.

NOT MEASURED HERE, AND WHY
Order-book imbalance. Depth collection began 2026-08-07, so there is no history. It is
excluded rather than approximated with a volume proxy.

Run:
    python3 scripts/falsify-predicates.py --limit 20      # smoke, ~20 symbols
    python3 scripts/falsify-predicates.py                 # full NIFTY-200
    python3 scripts/falsify-predicates.py --refresh       # re-download bars
"""
from __future__ import annotations

import argparse
import json
import logging
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

COST_PCT = 0.12          # 12 bps round trip — the engines' own booked rate
TARGET_PCT = 1.2
STOP_PCT = 0.6
TIME_STOP = dtime(14, 45)
FIRST_ENTRY = dtime(9, 30)
LAST_ENTRY = dtime(14, 0)
SEEDS = 5

IST = "Asia/Kolkata"
logger = logging.getLogger("falsify")

# Every predicate that ever fires, counted — so "never fired" (a bug) can never be
# mistaken for "fired and lost" (a result). This is the funnel-ledger principle
# applied to the backtest itself.
FIRE_COUNTS: dict = {}


def as_side(d):
    """Family A speaks bullish/bearish; the simulator speaks long/short. Without this
    every SMC signal was silently dropped at the seam and the run reported 'no edge'
    for predicates that had never been given a chance to trade."""
    return {"bullish": "long", "bearish": "short",
            "long": "long", "short": "short"}.get(d)
ALL_PREDICATES = ["liquidity_sweep", "fvg", "order_block", "amd_phase",
                  "smt_divergence", "mtf_alignment", "short_term_reversal",
                  "overnight_gap", "index_lead", "opening_range"]


# ───────────────────────────── data ─────────────────────────────

def fetch(symbols, refresh=False):
    """5m bars (60d) + daily (2y), cached to parquet. yfinance caps intraday at 60
    days, which is the binding constraint on sample size."""
    import yfinance as yf
    CACHE.mkdir(parents=True, exist_ok=True)
    out = {}
    todo = []
    for s in symbols:
        f5, fd = CACHE / f"{s}_5m.parquet", CACHE / f"{s}_1d.parquet"
        if not refresh and f5.exists() and fd.exists():
            try:
                out[s] = {"5m": pd.read_parquet(f5), "1d": pd.read_parquet(fd)}
                continue
            except Exception:
                pass
        todo.append(s)
    if todo:
        logger.info(f"downloading {len(todo)} symbols (cached: {len(out)})")
    for i, s in enumerate(todo, 1):
        try:
            b5 = yf.download(s, period="60d", interval="5m", progress=False,
                             auto_adjust=False, threads=False)
            bd = yf.download(s, period="2y", interval="1d", progress=False,
                             auto_adjust=False, threads=False)
            if isinstance(b5.columns, pd.MultiIndex):
                b5.columns = b5.columns.get_level_values(0)
            if isinstance(bd.columns, pd.MultiIndex):
                bd.columns = bd.columns.get_level_values(0)
            if b5.empty or bd.empty:
                continue
            b5.index = pd.to_datetime(b5.index, utc=True).tz_convert(IST)
            bd.index = pd.to_datetime(bd.index).tz_localize(None)
            b5.to_parquet(CACHE / f"{s}_5m.parquet")
            bd.to_parquet(CACHE / f"{s}_1d.parquet")
            out[s] = {"5m": b5, "1d": bd}
        except Exception as e:
            logger.warning(f"{s}: {type(e).__name__}")
        if i % 25 == 0:
            logger.info(f"  {i}/{len(todo)}")
    return out


def resample(b5: pd.DataFrame, rule: str) -> pd.DataFrame:
    return b5.resample(rule, label="right", closed="right").agg(
        {"Open": "first", "High": "max", "Low": "min",
         "Close": "last", "Volume": "sum"}).dropna()


# ───────────────────────────── simulation ─────────────────────────────

def simulate(day5: pd.DataFrame, entry_idx: int, direction: str) -> dict | None:
    """Fixed exit from the entry bar's close. Walks forward 5m bars.

    When a bar's range spans BOTH target and stop we assume the STOP filled first.
    Without tick data the ordering is unknowable, and the optimistic assumption is how
    backtests manufacture edge that does not exist live.
    """
    if entry_idx >= len(day5) - 1:
        return None
    entry = float(day5["Close"].iloc[entry_idx])
    if not np.isfinite(entry) or entry <= 0:
        return None
    sign = 1 if direction == "long" else -1
    tgt = entry * (1 + sign * TARGET_PCT / 100)
    stp = entry * (1 - sign * STOP_PCT / 100)

    for j in range(entry_idx + 1, len(day5)):
        bar = day5.iloc[j]
        ts = day5.index[j]
        hi, lo = float(bar["High"]), float(bar["Low"])
        hit_t = (hi >= tgt) if sign > 0 else (lo <= tgt)
        hit_s = (lo <= stp) if sign > 0 else (hi >= stp)
        if hit_t and hit_s:
            return {"pct": -STOP_PCT, "reason": "stop_ambiguous_bar"}
        if hit_s:
            return {"pct": -STOP_PCT, "reason": "stop"}
        if hit_t:
            return {"pct": TARGET_PCT, "reason": "target"}
        if ts.time() >= TIME_STOP:
            ex = float(bar["Close"])
            return {"pct": sign * (ex - entry) / entry * 100, "reason": "time_stop"}
    ex = float(day5["Close"].iloc[-1])
    return {"pct": sign * (ex - entry) / entry * 100, "reason": "eod"}


# ───────────────────────────── the run ─────────────────────────────

def evaluate_symbol(sym, data, ref5, rng):
    """Walk every session. At each decision bar, ask each predicate whether it fires.
    First fire per predicate per day wins — one trade per predicate per stock-day."""
    b5, bd = data["5m"], data["1d"]
    rows = []
    for day, day5 in b5.groupby(b5.index.date):
        day5 = day5.between_time("09:15", "15:30")
        if len(day5) < 20:
            continue
        as_of_day = pd.Timestamp(day)
        bias = P.daily_bias(bd, as_of_day)
        b = bias["bias"]

        fired = {}
        rand_pool = []
        for i, ts in enumerate(day5.index):
            t = ts.time()
            if t < FIRST_ENTRY or t > LAST_ENTRY:
                continue
            rand_pool.append(i)
            hist5 = day5.iloc[:i]                       # today, strictly closed
            if len(hist5) < 6:
                continue
            # Structure (order blocks, AMD, swings) needs MULTI-DAY history. Built
            # from today's bars alone the 15m frame has 2-3 rows early in a session,
            # so find_order_blocks (needs 12) and amd_phase (needs 20) could never
            # fire — they silently returned nothing and looked like "no edge".
            all_prior = b5[b5.index < ts].tail(600)     # ~8 sessions of 5m
            h15 = resample(all_prior, "15min")
            ref_hist = P.before(ref5, ts) if ref5 is not None else None
            ref_day = (ref_hist[ref_hist.index.date == day]
                       if ref_hist is not None and not ref_hist.empty else None)

            sigs = {}
            # ---- Family A
            pools = P.liquidity_pools(h15) if len(h15) > 6 else []
            if bias.get("protected_low"):
                pools.append({"kind": "pdl", "level": bias["pdl"], "n": 1})
                pools.append({"kind": "pdh", "level": bias["pdh"], "n": 1})
            for pl in pools:
                s = P.liquidity_sweep(h15, pl["level"])
                if s["swept"]:
                    sigs["liquidity_sweep"] = s["dir"]
                    break
            for g in P.find_fvg(h15):
                if g["distance_pct"] < 0.3:
                    sigs["fvg"] = g["dir"]; break
            last = float(hist5["Close"].iloc[-1])
            for ob in P.find_order_blocks(h15):
                if ob["lo"] <= last <= ob["hi"]:
                    sigs["order_block"] = ob["dir"]; break
            ph = P.amd_phase(h15, pools)
            if ph.get("phase") == "manipulation_complete":
                sigs["amd_phase"] = ph["dir"]
            if ref_day is not None and len(ref_day) > 20:
                sm = P.smt_divergence(hist5, ref_day)
                if sm["smt"]:
                    sigs["smt_divergence"] = sm["dir"]
            mt = P.mtf_alignment({"5m": hist5, "15m": h15}, b)
            if mt["of"] and mt["aligned"] == mt["of"] and b in ("long", "short"):
                sigs["mtf_alignment"] = b
            # ---- Family B
            r = P.short_term_reversal(bd, as_of_day)
            if r["signal"]:
                sigs["short_term_reversal"] = r["signal"]
            g = P.overnight_gap(bd, day5, as_of_day)
            if g.get("signal"):
                sigs["overnight_gap"] = g["signal"]
            if ref_day is not None:
                il = P.index_lead(ref_day, ts)
                if il["signal"]:
                    sigs["index_lead"] = il["signal"]
            orb = P.opening_range(day5, ts)
            if orb["signal"]:
                sigs["opening_range"] = orb["signal"]

            for name, d in sigs.items():
                FIRE_COUNTS[name] = FIRE_COUNTS.get(name, 0) + 1
                d = as_side(d)
                if name in fired or d is None:
                    continue
                res = simulate(day5, i, d)
                if res:
                    fired[name] = True
                    rows.append({"symbol": sym, "day": str(day), "predicate": name,
                                 "dir": d, "bias": b, "pct": res["pct"],
                                 "reason": res["reason"],
                                 "with_bias": (d == b)})
        # ---- random control on the same stock-day, identical exits
        if rand_pool:
            for sd in range(SEEDS):
                i = rand_pool[rng.integers(len(rand_pool))]
                d = "long" if rng.integers(2) else "short"
                res = simulate(day5, i, d)
                if res:
                    rows.append({"symbol": sym, "day": str(day),
                                 "predicate": f"__random_{sd}", "dir": d, "bias": b,
                                 "pct": res["pct"], "reason": res["reason"],
                                 "with_bias": (d == b)})
    return rows


def report(df: pd.DataFrame) -> dict:
    rnd = df[df.predicate.str.startswith("__random")]
    rnd_net = (rnd["pct"] - COST_PCT).mean() if len(rnd) else float("nan")

    print(f"\n  RANDOM BASELINE  n={len(rnd):,}  "
          f"gross {rnd['pct'].mean():+.4f}%  net {rnd_net:+.4f}%/trade\n")
    print(f"  {'predicate':<22}{'n':>7}{'win%':>7}{'gross%':>9}{'net%':>9}"
          f"{'t':>7}{'vs rnd':>9}  verdict")
    print("  " + "-" * 78)

    results = {}
    for name, g in df[~df.predicate.str.startswith("__random")].groupby("predicate"):
        n = len(g)
        gross = g["pct"].mean()
        net = gross - COST_PCT
        sd = g["pct"].std(ddof=1) if n > 2 else float("nan")
        t = net / (sd / np.sqrt(n)) if n > 2 and sd and np.isfinite(sd) and sd > 0 else 0.0
        edge_vs_rnd = net - rnd_net
        win = (g["pct"] > 0).mean() * 100
        # A predicate must clear cost AND beat random AND be distinguishable from noise
        if n < 30:
            verdict = "too few"
        elif net > 0 and t > 2 and edge_vs_rnd > 0:
            verdict = "SURVIVES"
        else:
            verdict = "killed"
        results[name] = {"n": int(n), "win_pct": round(win, 1),
                         "gross_pct": round(gross, 4), "net_pct": round(net, 4),
                         "t": round(float(t), 2),
                         "vs_random": round(float(edge_vs_rnd), 4),
                         "verdict": verdict}
        print(f"  {name:<22}{n:>7,}{win:>6.0f}%{gross:>9.4f}{net:>9.4f}"
              f"{t:>7.2f}{edge_vs_rnd:>9.4f}  {verdict}")
    return results, rnd_net


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="  %(message)s")

    from prototype.v4.config import ACTIVE_SYMBOLS_YF
    syms = list(ACTIVE_SYMBOLS_YF)
    if a.limit:
        syms = syms[:a.limit]

    logger.info(f"universe: {len(syms)} symbols | cost {COST_PCT}% | "
                f"exit {TARGET_PCT}/{STOP_PCT} | {SEEDS} random seeds")
    data = fetch(syms + ["^NSEI"], refresh=a.refresh)
    ref5 = data.get("^NSEI", {}).get("5m")
    logger.info(f"loaded {len(data)} symbols; index reference "
                f"{'OK' if ref5 is not None else 'MISSING'}")

    rng = np.random.default_rng(a.seed)
    rows = []
    for i, s in enumerate([x for x in syms if x in data], 1):
        try:
            rows += evaluate_symbol(s, data[s], ref5, rng)
        except Exception as e:
            logger.warning(f"{s}: {type(e).__name__}: {e}")
        if i % 20 == 0:
            logger.info(f"  evaluated {i} symbols, {len(rows):,} trades")

    if not rows:
        print("\n  no trades generated — check data\n")
        return 1
    df = pd.DataFrame(rows)
    results, rnd_net = report(df)

    OUT.mkdir(parents=True, exist_ok=True)
    stamp = str(df["day"].max())
    df.to_parquet(OUT / f"falsify-trades-{stamp}.parquet")
    payload = {"generated_for_sessions": [str(df["day"].min()), stamp],
               "symbols": len([x for x in syms if x in data]),
               "cost_pct": COST_PCT, "target_pct": TARGET_PCT, "stop_pct": STOP_PCT,
               "random_net_pct": round(float(rnd_net), 4),
               "excluded": {"order_book_imbalance":
                            "no history — depth collection began 2026-08-07"},
               "results": results}
    (OUT / f"falsify-report-{stamp}.json").write_text(json.dumps(payload, indent=2))

    print("\n  FIRE LEDGER — raw signals before dedupe (a zero here is a BUG):")
    for pr in ALL_PREDICATES:
        print(f"    {pr:<24}{FIRE_COUNTS.get(pr, 0):>9,}")
    never = [p for p in ALL_PREDICATES if FIRE_COUNTS.get(p, 0) == 0]
    if never:
        print(f"\n  NEVER FIRED — these are BUGS, not verdicts: {', '.join(never)}")
    thin = [p for p in ALL_PREDICATES
            if 0 < FIRE_COUNTS.get(p, 0) < 50]
    if thin:
        print(f"  fired but thin (<50 raw signals): "
              + ", ".join(f"{p}={FIRE_COUNTS[p]}" for p in thin))

    survivors = [k for k, v in results.items() if v["verdict"] == "SURVIVES"]
    print(f"\n  {'='*78}\n  WEEK-1 GATE: ", end="")
    if survivors:
        print(f"{len(survivors)} predicate(s) survive — {', '.join(survivors)}")
        print("  Backtests can kill a thesis, never confirm one. Re-run these on a")
        print("  held-out period before believing them.")
    else:
        print("NOTHING SURVIVES.")
        print("  No predicate clears the 0.12% cost with t>2 while beating a random")
        print("  entry. On this evidence the thesis is dead — change it rather than")
        print("  spending another two months confirming a negative.")
    print(f"  wrote {OUT}/falsify-report-{stamp}.json\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
