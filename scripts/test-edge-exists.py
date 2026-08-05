#!/usr/bin/env python3
"""
test-edge-exists — does the signal predict anything, out-of-sample, since June?

THE QUESTION THAT DECIDES WHAT WE DO NEXT
v5's win rate went 77% (April) -> 53% -> 47% -> 47% -> 42%. Since 2026-06-01 it has
lost Rs 15,269 over 2,226 trades, t = -2.00. Everything shipped in the last week —
score floor, deployment, time gate, multi-day holds, wider universe — tunes a
strategy whose core signal has produced a 47% win rate for three months. Tuning a
coin flip produces a tuned coin flip.

So: is there a signal, or is there not?

THREE INDEPENDENT TESTS, because any one of them can be fooled

  1. INFORMATION COEFFICIENT — correlation between the score at entry and the return
     that followed. This is the direct question: does a higher score mean a better
     outcome? A real equity signal runs IC 0.03-0.05. Anything near zero means the
     score carries no information about what happens next.

  2. MARKET-ADJUSTED RETURN — our return minus NIFTY's over the SAME window. A long
     book in a rising market makes money without any skill at all. April was +4.8%
     on NIFTY; some of that 77% was simply beta. Subtracting the index is what
     separates picking from participating.

  3. RANDOM BASELINE — the same number of trades, in the same stocks, on the same
     days, entered at random times. If our timed entries do not beat coin-flip
     entries in the same names, the signal adds nothing and the whole apparatus is
     an expensive way to hold a random basket.

WHAT WOULD FALSIFY THE STRATEGY
IC near zero AND market-adjusted return near zero AND no advantage over random. Any
one of those alone is survivable; all three together means there is nothing to tune
and the honest move is to stop trading it while we find a real signal.

Run:
    python3 scripts/test-edge-exists.py                 # June onwards
    python3 scripts/test-edge-exists.py --from 2026-04-01
    python3 scripts/test-edge-exists.py --engine v5_cut
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import random
import statistics as st
import sys
import warnings
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
random.seed(42)          # reproducible baseline


def load_trades(engine: str, since: str):
    out = []
    for f in sorted(glob.glob(str(ROOT / "docs" / "paper-trades" / engine / "*.json"))):
        b = os.path.basename(f)[:-5]
        if len(b) != 10 or b < since:
            continue
        try:
            d = json.loads(Path(f).read_text())
        except Exception:
            continue
        if d.get("VOID"):
            continue
        for pl in (d.get("pools") or {}).values():
            for c in (pl.get("closed") or []):
                if c.get("pnl") is None or not c.get("symbol"):
                    continue
                out.append({
                    "symbol": c["symbol"], "session": b,
                    "score": float(c.get("score") or 0),
                    "pnl_pct": float(c.get("pnl_pct") or 0),
                    "side": "SHORT" if str(c.get("position_type") or "").upper() == "SHORT" else "LONG",
                    "entry_time": str(c.get("entry_time") or "")[:5],
                    "exit_time": str(c.get("exit_time") or "")[:5],
                    "entry_price": float(c.get("entry_price") or 0),
                })
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = sum((a - mx) ** 2 for a in xs) ** 0.5
    dy = sum((b - my) ** 2 for b in ys) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def nifty_by_day(since: str):
    """NIFTY open->close % for each session, so a trade's return can be judged
    against what simply being long that day would have paid."""
    from prototype.v4 import kite_data as kd
    tok = None
    for r in kd._call(lambda: kd.client().instruments("NSE"), "i"):
        if r.get("tradingsymbol") == "NIFTY 50" and r.get("segment") == "INDICES":
            tok = r["instrument_token"]
            break
    if not tok:
        return {}
    start = datetime.strptime(since, "%Y-%m-%d") - timedelta(days=5)
    bars = kd.client().historical_data(tok, start, datetime.now(), "day")
    return {str(b["date"])[:10]: (b["close"] - b["open"]) / b["open"] * 100
            for b in bars if b["open"]}


def intraday_bars(symbol: str, day: str, cache: dict):
    key = (symbol, day)
    if key in cache:
        return cache[key]
    from prototype.v4 import kite_data as kd
    out = []
    try:
        tok = kd.token_for(symbol)
        if tok:
            d0 = datetime.strptime(day, "%Y-%m-%d")
            out = [b for b in kd.client().historical_data(tok, d0, d0 + timedelta(days=1), "15minute")
                   if str(b["date"])[:10] == day]
    except Exception:
        out = []
    cache[key] = out
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="v5")
    ap.add_argument("--from", dest="since", default="2026-06-01")
    ap.add_argument("--sample", type=int, default=400,
                    help="trades to use for the random-baseline test (needs bar data)")
    a = ap.parse_args()

    from prototype.v4 import kite_data as kd
    ok, detail = kd.token_alive()
    if not ok:
        print(f"  Kite token dead: {detail}", file=sys.stderr)
        return 2

    tr = load_trades(a.engine, a.since)
    if not tr:
        print(f"  no trades for {a.engine} since {a.since}", file=sys.stderr)
        return 1
    days = sorted({t["session"] for t in tr})
    print(f"\n  DOES THE SIGNAL PREDICT ANYTHING?  {a.engine}, {a.since} onwards")
    print(f"  {len(tr):,} closed trades over {len(days)} sessions\n")

    # ── TEST 1: information coefficient ────────────────────────────────────
    scored = [t for t in tr if t["score"] > 0]
    ic = pearson([t["score"] for t in scored], [t["pnl_pct"] for t in scored])
    n = len(scored)
    se = (1 / (n - 2)) ** 0.5 if n > 3 else 0
    print(f"  TEST 1 — INFORMATION COEFFICIENT (score vs return)")
    print(f"    n = {n:,}   IC = {ic:+.4f}   t = {ic/se if se else 0:+.2f}")
    print(f"    a real equity signal runs IC 0.03-0.05")
    print(f"    -> {'signal carries information' if abs(ic) > 0.03 and abs(ic/se if se else 0) > 2 else 'NO usable information in the score'}")

    # ── TEST 2: market-adjusted ────────────────────────────────────────────
    nif = nifty_by_day(a.since)
    adj = []
    for t in tr:
        m = nif.get(t["session"])
        if m is None:
            continue
        # a SHORT profits when the market falls, so its benchmark is inverted
        bench = m if t["side"] == "LONG" else -m
        adj.append(t["pnl_pct"] - bench)
    print(f"\n  TEST 2 — MARKET-ADJUSTED RETURN (ours minus NIFTY, same day)")
    if adj:
        m_adj = st.mean(adj)
        se_adj = st.pstdev(adj) / (len(adj) ** 0.5)
        raw = st.mean([t["pnl_pct"] for t in tr])
        print(f"    raw return       {raw:+.4f}% / trade")
        print(f"    market-adjusted  {m_adj:+.4f}% / trade   t = {m_adj/se_adj if se_adj else 0:+.2f}")
        print(f"    -> {'beats the index' if m_adj > 0 and abs(m_adj/se_adj) > 2 else ('LOSES to simply holding the index' if m_adj < 0 and abs(m_adj/se_adj) > 2 else 'no distinguishable difference from the index')}")

    # ── TEST 3: random-entry baseline ──────────────────────────────────────
    print(f"\n  TEST 3 — vs RANDOM ENTRY in the same stocks, same days")
    sample = random.sample(tr, min(a.sample, len(tr)))
    cache = {}
    ours, rnd = [], []
    for i, t in enumerate(sample, 1):
        bars = intraday_bars(t["symbol"], t["session"], cache)
        if len(bars) < 6:
            continue
        # our actual result
        ours.append(t["pnl_pct"])
        # a random entry and exit in the same session, same direction, same stock
        i0 = random.randint(0, len(bars) - 2)
        i1 = random.randint(i0 + 1, len(bars) - 1)
        e, x = float(bars[i0]["close"]), float(bars[i1]["close"])
        r = (x - e) / e * 100
        rnd.append(r if t["side"] == "LONG" else -r)
        if i % 100 == 0:
            print(f"      ...{i}/{len(sample)}", file=sys.stderr)
    if ours and rnd:
        mo, mr = st.mean(ours), st.mean(rnd)
        se_d = (st.pstdev(ours) ** 2 / len(ours) + st.pstdev(rnd) ** 2 / len(rnd)) ** 0.5
        print(f"    n = {len(ours)} matched pairs")
        print(f"    our timed entries   {mo:+.4f}% / trade")
        print(f"    random entries      {mr:+.4f}% / trade")
        print(f"    difference          {mo-mr:+.4f}%   t = {(mo-mr)/se_d if se_d else 0:+.2f}")
        print(f"    -> {'our timing beats random' if (mo-mr) > 0 and abs((mo-mr)/se_d) > 2 else 'our timing is NOT better than random entry'}")

    print(f"\n  {'='*66}")
    verdicts = []
    verdicts.append(abs(ic) > 0.03)
    verdicts.append(bool(adj) and st.mean(adj) > 0)
    verdicts.append(bool(ours and rnd) and st.mean(ours) > st.mean(rnd))
    passed = sum(verdicts)
    print(f"  {passed}/3 tests show a positive edge.")
    if passed == 0:
        print(f"  VERDICT: no measurable edge since {a.since}. Tuning cannot fix this —")
        print(f"  the signal itself needs replacing, and trading it costs money meanwhile.")
    elif passed == 3:
        print(f"  VERDICT: the edge is real. The problem is execution, and the shadows")
        print(f"  running now are the right work.")
    else:
        print(f"  VERDICT: mixed. Some signal exists but it is not surviving costs and")
        print(f"  execution as configured.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
