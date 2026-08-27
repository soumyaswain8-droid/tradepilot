#!/usr/bin/env python3
"""
shadow-settle — settle the floor's shadow trades against real minute bars, and check
them against a gate that was written down BEFORE the data arrived.

Shadow trades cost nothing: the floor records what it would have opened and never
opens it. This resolves each one honestly -- walking the bars forward from entry and
taking whichever of stop or target was touched FIRST, then the close if neither --
and charges the full 0.106% round trip so the number is what we would have kept.

WHY A PRE-REGISTERED GATE. Six ideas in this project were killed by a bar stated in
advance, and each of those killings was correct. Three times in one week a result
looked real on a small or selected sample and evaporated on a wider one. A gate
declared before the evidence exists is the only defence against fitting the rule to
the data after the fact -- so the thresholds live in floor.py, not here, and this
script only reports pass or fail against them.

    python3 scripts/shadow-settle.py            # settle today, report cumulative
    python3 scripts/shadow-settle.py --all      # re-settle every day on record
"""
from __future__ import annotations
import json, math, statistics as st, sys, time, warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prototype.agents.floor import SHADOW_FILE, SHADOW_GATE, ENTRY_TRIGGER
TOLL_PCT = 0.106
SETTLED = SHADOW_FILE / "settled.jsonl"


def bars(sym, day, k, cache):
    key = (sym, day)
    if key in cache:
        return cache[key]
    from prototype.v4 import kite_data as kd
    tok = kd.token_for(sym)
    D = datetime.strptime(day, "%Y-%m-%d")
    try:
        raw = k.historical_data(tok, D, D + timedelta(days=1), "minute") if tok else []
    except Exception:
        raw = []
    time.sleep(0.34)
    cache[key] = raw
    return raw


def settle(rec, day, k, cache):
    """Walk forward from entry; whichever of stop/target is touched FIRST wins.

    Order matters and is the whole point. Checking 'did it reach the target at any
    time' without asking whether the stop came first is the look-ahead that makes a
    losing rule look profitable.
    """
    b = bars(rec["symbol"], day, k, cache)
    if len(b) < 5:
        return None
    t0 = rec["at"][:5]
    fwd = [x for x in b if str(x["date"])[11:16] >= t0]
    if not fwd:
        return None
    entry, stop, tgt = rec["entry"], rec["stop"], rec["target"]
    for x in fwd:
        lo, hi = float(x["low"]), float(x["high"])
        hit_stop, hit_tgt = lo <= stop, hi >= tgt
        if hit_stop and hit_tgt:
            # both inside one minute — cannot tell the order, assume the worse
            return {"exit": stop, "reason": "STOP_SAME_BAR",
                    "at": str(x["date"])[11:16]}
        if hit_stop:
            return {"exit": stop, "reason": "STOP", "at": str(x["date"])[11:16]}
        if hit_tgt:
            return {"exit": tgt, "reason": "TARGET", "at": str(x["date"])[11:16]}
    last = float(fwd[-1]["close"])
    return {"exit": last, "reason": "SESSION_END", "at": str(fwd[-1]["date"])[11:16]}


def main():
    days = sorted(p.stem for p in SHADOW_FILE.glob("2026-*.jsonl")) \
        if SHADOW_FILE.exists() else []
    if "--all" not in sys.argv:
        today = datetime.now().strftime("%Y-%m-%d")
        days = [d for d in days if d == today] or days[-1:]
    if not days:
        print("  no shadow trades recorded yet")
        print(f"  the floor writes them to {SHADOW_FILE} whenever ENTRY_MODE=shadow")
        return 0

    from prototype.v4 import kite_data as kd
    k = kd.client()
    cache, out = {}, []
    for day in days:
        rows = [json.loads(l) for l in (SHADOW_FILE / f"{day}.jsonl").read_text().splitlines() if l.strip()]
        for r in rows:
            res = settle(r, day, k, cache)
            if not res:
                continue
            gross = (res["exit"] / r["entry"] - 1) * 100
            out.append({**r, **res, "day": day,
                        "gross_pct": round(gross, 4),
                        "net_pct": round(gross - TOLL_PCT, 4)})
    if not out:
        print("  shadow trades exist but none could be settled — check the Kite session")
        return 1

    SETTLED.parent.mkdir(parents=True, exist_ok=True)
    SETTLED.write_text("\n".join(json.dumps(o) for o in out) + "\n")

    nets = [o["net_pct"] for o in out]
    mu = st.mean(nets)
    sd = st.pstdev(nets) or 1e-9
    t = mu / (sd / math.sqrt(len(nets)))
    wins = sum(1 for x in nets if x > 0)
    ndays = len({o["day"] for o in out})

    print(f"\n  ═══ SHADOW SETTLEMENT — rule: {ENTRY_TRIGGER} ═══")
    print(f"  {len(out)} trades across {ndays} session(s), settled on real minute bars")
    print(f"  fees charged at {TOLL_PCT}% round trip, so these are net figures")
    print()
    from collections import Counter
    for r, c in Counter(o["reason"] for o in out).most_common():
        sub = [o["net_pct"] for o in out if o["reason"] == r]
        print(f"    {r:<16}{c:>5}   mean {st.mean(sub):+.3f}%")
    print()
    print(f"    win rate     {wins}/{len(out)}  ({wins/len(out)*100:.0f}%)")
    print(f"    net/trade    {mu:+.4f}%")
    print(f"    t-statistic  {t:+.2f}")
    print()

    G = SHADOW_GATE
    checks = [
        ("trades", len(out), G["min_trades"], len(out) >= G["min_trades"]),
        ("sessions", ndays, G["min_days"], ndays >= G["min_days"]),
        ("net/trade %", round(mu, 4), G["min_net_pct"], mu >= G["min_net_pct"]),
        ("t-statistic", round(t, 2), G["min_t"], t >= G["min_t"]),
    ]
    print("  GATE (declared in floor.py before any of this data existed)")
    for name, got, need, ok in checks:
        print(f"    {'PASS' if ok else 'FAIL'}  {name:<14}{got:>10}   needs >= {need}")
    if all(c[3] for c in checks):
        print("\n  ALL CONDITIONS MET — this rule has earned ENTRY_MODE='live'.")
    else:
        miss = [c[0] for c in checks if not c[3]]
        print(f"\n  NOT YET: {', '.join(miss)}. Stays in shadow — which costs nothing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
