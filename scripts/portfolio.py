#!/usr/bin/env python3
"""
portfolio — one honest view of everything TradePilot has traded.

WHAT THIS IS FOR
Soumya asked for a profile in his name holding the whole book: settled trades, swing
positions, carried holds — the entire portfolio in one place rather than 26 engine
directories.

THREE CORRECTIONS APPLIED, because the raw files would mislead:

1. COSTS. Some engines book costs into pnl_net and some never have. v5_classic has
   NEVER booked a cost in its entire history, so its raw P&L flatters it against v5
   by roughly Rs 14.30 a trade. Where an engine reports no cost, the measured
   Rs 14.30/trade is subtracted here so the comparison is like-for-like.

2. ACTIVE vs RETIRED. 26 engine directories exist; far fewer are in the current
   launch roster. A retired engine's frozen P&L is history, not holdings, and adding
   it to a live total would overstate the portfolio. Both are shown, separately.

3. VOIDED SESSIONS. Sessions annotated VOID (e.g. the US book seeded by out-of-hours
   Sunday fills on 2026-08-03) are excluded from totals and listed apart. A number
   that silently includes fills that could not have happened is not a portfolio.

PAPER, NOT REAL. Every position here is simulated against live prices. The linked
Zerodha account holds zero positions and zero orders — its NSE segment is not even
enabled. Nothing in this file represents money that exists.

Usage:
    python3 scripts/portfolio.py                # summary to stdout
    python3 scripts/portfolio.py --json out.json
    python3 scripts/portfolio.py --engine v5    # one engine's detail
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRADE_DIR = ROOT / "docs" / "paper-trades"
COST_PER_TRADE = 14.30           # v5's measured round-trip cost
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

OWNER = {"name": "Soumya Swain", "email": "soumya@suryaai.co.in"}


def active_engines() -> set:
    """Engines in the current launch roster — parsed from the launcher itself so this
    cannot drift out of date the way a hardcoded list would."""
    f = ROOT / "scripts" / "launch-market.sh"
    if not f.exists():
        return set()
    out = set()
    for line in f.read_text().splitlines():
        s = line.strip()
        if s.startswith('"') and "|scripts/" in s and not s.startswith("#"):
            out.add(s.split("|")[0].strip('"'))
    return out


def _session_files(engine: str):
    for f in sorted(glob.glob(str(TRADE_DIR / engine / "*.json"))):
        b = os.path.basename(f)[:-5]
        if DATE_RE.match(b):
            yield b, f


def load_engine(engine: str) -> dict:
    live = active_engines()
    sessions, closed, positions, voided = [], [], [], []
    realised = costs = 0.0
    capital = 0.0

    for day, path in _session_files(engine):
        try:
            d = json.loads(Path(path).read_text())
        except Exception:
            continue
        if d.get("VOID"):
            voided.append({"date": day, "reason": str(d.get("void_reason", ""))[:160]})
            continue
        cap = float(d.get("total_capital") or d.get("capital") or 0)
        if cap:
            capital = cap
        sm = d.get("summary") or {}
        n = int(sm.get("trades") or 0)

        # cost honesty: engines that never booked a cost get charged the measured rate
        booked = float(sm.get("total_cost") or 0)
        gross = float(sm.get("total_pnl") or 0)
        net = sm.get("total_pnl_net")
        if booked > 0 and net is not None:
            day_net, day_cost = float(net), booked
        else:
            day_cost = n * COST_PER_TRADE
            day_net = gross - day_cost
        realised += day_net
        costs += day_cost
        sessions.append({"date": day, "trades": n, "gross": round(gross, 2),
                         "cost": round(day_cost, 2), "net": round(day_net, 2)})

        pools = d.get("pools") or {}
        for pname, pl in pools.items():
            for c in (pl.get("closed") or []):
                closed.append({**{k: c.get(k) for k in
                                  ("symbol", "direction", "position_type", "qty",
                                   "entry_price", "exit_price", "pnl", "pnl_pct",
                                   "reason", "entry_date", "entry_time", "exit_time",
                                   "score")},
                               "pool": pname, "engine": engine, "session": day})
    # open positions come from the LATEST session only — earlier files hold that
    # day's snapshot, and summing them would count the same position many times
    if sessions:
        last = sessions[-1]["date"]
        try:
            d = json.loads((TRADE_DIR / engine / f"{last}.json").read_text())
            for pname, pl in (d.get("pools") or {}).items():
                for p in (pl.get("positions") or []):
                    positions.append({**p, "pool": pname, "engine": engine})
        except Exception:
            pass

    return {
        "engine": engine,
        "status": "active" if engine in live else "retired",
        "capital": round(capital, 2),
        "sessions": len(sessions),
        "first_session": sessions[0]["date"] if sessions else None,
        "last_session": sessions[-1]["date"] if sessions else None,
        "trades": sum(s["trades"] for s in sessions),
        "realised_net": round(realised, 2),
        "costs": round(costs, 2),
        "open_positions": positions,
        "closed_trades": closed,
        "session_rows": sessions,
        "voided": voided,
    }


def build() -> dict:
    engines = sorted(d.name for d in TRADE_DIR.iterdir()
                     if d.is_dir() and not d.name.startswith("."))
    per = [load_engine(e) for e in engines]
    per = [p for p in per if p["sessions"]]

    act = [p for p in per if p["status"] == "active"]
    ret = [p for p in per if p["status"] == "retired"]

    def agg(rows):
        return {
            "engines": len(rows),
            "trades": sum(r["trades"] for r in rows),
            "realised_net": round(sum(r["realised_net"] for r in rows), 2),
            "costs": round(sum(r["costs"] for r in rows), 2),
            "open_positions": sum(len(r["open_positions"]) for r in rows),
        }

    by_pool = defaultdict(lambda: {"positions": 0, "value": 0.0})
    for p in act:
        for pos in p["open_positions"]:
            b = by_pool[pos.get("pool", "?")]
            b["positions"] += 1
            b["value"] += abs(float(pos.get("qty", 0)) * float(pos.get("entry_price", 0)))
    for v in by_pool.values():
        v["value"] = round(v["value"], 2)

    all_sessions = sorted({s["date"] for p in per for s in p["session_rows"]})
    return {
        "owner": OWNER,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "disclaimer": ("PAPER TRADING. Simulated fills against live NSE prices. "
                       "The linked Zerodha account holds zero positions and zero "
                       "orders; its NSE segment is not enabled."),
        "period": {"first": all_sessions[0] if all_sessions else None,
                   "last": all_sessions[-1] if all_sessions else None,
                   "sessions": len(all_sessions)},
        "active": agg(act),
        "retired": agg(ret),
        "by_pool": dict(by_pool),
        "engines": [{k: v for k, v in p.items()
                     if k not in ("closed_trades", "session_rows")} for p in per],
        "voided_sessions": [{**v, "engine": p["engine"]} for p in per for v in p["voided"]],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--engine", default="")
    a = ap.parse_args()

    if a.engine:
        e = load_engine(a.engine)
        print(f"\n  {e['engine']} ({e['status']}) — {e['sessions']} sessions, "
              f"{e['trades']} trades, net Rs {e['realised_net']:+,.0f}")
        for p in e["open_positions"]:
            v = float(p.get("qty", 0)) * float(p.get("entry_price", 0))
            print(f"    OPEN  {p.get('symbol',''):<12} {p.get('pool',''):<10} "
                  f"{p.get('qty')} @ {p.get('entry_price')}  = Rs {v:,.0f}")
        return 0

    p = build()
    o = p["owner"]
    print(f"\n  PORTFOLIO — {o['name']} <{o['email']}>")
    print(f"  {p['period']['sessions']} sessions, {p['period']['first']} .. {p['period']['last']}")
    print(f"  {p['disclaimer']}\n")
    for label, key in (("ACTIVE", "active"), ("RETIRED", "retired")):
        s = p[key]
        print(f"  {label:<9} {s['engines']:>3} engines  {s['trades']:>6,} trades  "
              f"net Rs {s['realised_net']:>+12,.0f}  costs Rs {s['costs']:>10,.0f}  "
              f"{s['open_positions']:>3} open")
    print("\n  OPEN POSITIONS BY POOL (active engines)")
    for pool, v in sorted(p["by_pool"].items(), key=lambda kv: -kv[1]["value"]):
        print(f"    {pool:<12} {v['positions']:>3} positions   Rs {v['value']:>12,.0f}")
    print("\n  PER ENGINE (active)")
    print(f"    {'engine':<13}{'sessions':>9}{'trades':>8}{'net Rs':>13}{'open':>6}")
    for e in sorted([x for x in p["engines"] if x["status"] == "active"],
                    key=lambda x: -x["realised_net"]):
        print(f"    {e['engine']:<13}{e['sessions']:>9}{e['trades']:>8}"
              f"{e['realised_net']:>13,.0f}{len(e['open_positions']):>6}")
    if p["voided_sessions"]:
        print(f"\n  EXCLUDED — {len(p['voided_sessions'])} voided session(s):")
        for v in p["voided_sessions"]:
            print(f"    {v['engine']} {v['date']}: {v['reason'][:90]}")
    if a.json:
        Path(a.json).write_text(json.dumps(p, indent=2, default=str))
        print(f"\n  wrote {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
