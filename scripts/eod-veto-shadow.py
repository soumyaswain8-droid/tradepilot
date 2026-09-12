#!/usr/bin/env python3
"""eod-veto-shadow — score the swept-level-reclaim veto against today's engine trades
WITHOUT changing anything. Reads the candle replay the EOD driver already makes.

    python3 scripts/eod-veto-shadow.py <date> [replay.json] [engines]

Writes docs/research/shadows/veto/<date>.json + .md and appends to veto-ledger.csv.
Buckets per engine AND per side: reclaim (entered against a swept-and-reclaimed level),
clean, untagged (no candles or fewer than 4 bars before entry).

Side matters: the ₹-2,226/66-trade evidence is SHORTs into a bought session low. The
LONG rule is the untested mirror of it, so a combined bucket would let unevidenced LONG
P&L move a number the veto decision is supposed to be read off. Keep them apart.
"""
import sys, json, csv
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v5.reclaim import tag_from_bars  # noqa: E402

OUT = ROOT / "docs" / "research" / "shadows" / "veto"
TAGS = ("reclaim", "clean", "untagged")
SIDES = ("SHORT", "LONG")
LEDGER_FIELDS = ["date", "engine", "side", "tag", "n", "pnl", "win_pct"]


def _side(row):
    return "SHORT" if str(row.get("side", "")).upper() == "SHORT" else "LONG"


def _bucket_by_side(trades):
    return {s: _bucket([t for t in trades if _side(t) == s]) for s in SIDES}


def _bucket(trades):
    b = {}
    for tag in TAGS:
        xs = [t for t in trades if t["tag"] == tag]
        b[tag] = {"n": len(xs), "pnl": round(sum(float(t["pnl"] or 0) for t in xs), 2),
                  "win": (round(100 * sum(1 for t in xs if float(t["pnl"] or 0) > 0) / len(xs)) if xs else 0)}
    return b


def score_replay(replay, engines):
    cand = replay.get("candles") or {}
    out = {"date": replay.get("date"), "engines": {}}
    all_trades = []
    for eng in engines:
        e = (replay.get("engines") or {}).get(eng) or {}
        rows = []
        for t in e.get("trades") or []:
            side = str(t.get("dir") or t.get("position_type") or "LONG").upper()
            bars = cand.get(t.get("symbol"))
            tag = tag_from_bars(bars, t.get("entry_time"), side) if bars else None
            rows.append({"symbol": t.get("symbol"), "side": side, "entry_time": t.get("entry_time"),
                         "pnl": t.get("pnl"), "reason": t.get("reason"), "tag": tag or "untagged"})
        out["engines"][eng] = {"trades": rows, "buckets": _bucket(rows),
                               "buckets_by_side": _bucket_by_side(rows)}
        all_trades += rows
    out["fleet"] = _bucket(all_trades)
    out["fleet_by_side"] = _bucket_by_side(all_trades)
    return out


def write_ledger(path, scored):
    path = Path(path)
    rows = []
    if path.exists():
        with open(path) as f:
            r = csv.DictReader(f)
            # a pre-2026-09-12 ledger has no `side` column; those rows cannot be split
            # after the fact, so drop them and let the backfill rewrite the file.
            if r.fieldnames == LEDGER_FIELDS:
                rows = [x for x in r if x["date"] != scored["date"]]
    for eng, e in scored["engines"].items():
        for side in SIDES:
            for tag in TAGS:
                b = e["buckets_by_side"][side][tag]
                rows.append({"date": scored["date"], "engine": eng, "side": side, "tag": tag,
                             "n": b["n"], "pnl": b["pnl"], "win_pct": b["win"]})
    rows.sort(key=lambda r: (r["date"], r["engine"], r["side"], r["tag"]))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=LEDGER_FIELDS)
        w.writeheader(); w.writerows(rows)


def write_md(path, scored):
    lines = [f"# Veto shadow — {scored['date']}", "",
             "Engine SHORTs entered within 3 bars of a swept-and-reclaimed session low (LONGs: rejected session high).",
             "Nothing was blocked; this is the score the veto WOULD have had.", "",
             "SHORT is the evidenced side; LONG is the untested mirror — read them apart.", "",
             "| Engine | Side | Tag | n | P&L | Win |", "|---|---|---|---:|---:|---:|"]
    for eng, e in scored["engines"].items():
        for side in SIDES:
            for tag in TAGS:
                b = e["buckets_by_side"][side][tag]
                lines.append(f"| {eng} | {side} | {tag} | {b['n']} | {b['pnl']:,.0f} | {b['win']}% |")
    fs = scored["fleet_by_side"]
    for side in SIDES:
        b = fs[side]
        lines += ["", f"Fleet {side}: reclaim {b['reclaim']['n']} trades ₹{b['reclaim']['pnl']:,.0f} · "
                      f"clean {b['clean']['n']} trades ₹{b['clean']['pnl']:,.0f} · untagged {b['untagged']['n']}"]
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    date = sys.argv[1]
    replay_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "watchdog" / "reports" / f"{date}_eod" / "left-on-table.json"
    engines = (sys.argv[3] if len(sys.argv) > 3 else "v5,v5_wide").split(",")
    if not replay_path.exists():
        print(f"no replay at {replay_path}"); sys.exit(1)
    replay = json.load(open(replay_path))
    scored = score_replay(replay, engines)
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(scored, open(OUT / f"{date}.json", "w"), indent=1)
    write_md(OUT / f"{date}.md", scored)
    write_ledger(OUT / "veto-ledger.csv", scored)
    for side in SIDES:
        b = scored["fleet_by_side"][side]
        print(f"veto shadow {date} {side}: reclaim n={b['reclaim']['n']} pnl={b['reclaim']['pnl']:,.0f} | "
              f"clean n={b['clean']['n']} pnl={b['clean']['pnl']:,.0f} | untagged {b['untagged']['n']}")
    print(f"  -> {OUT / (date + '.md')}")


if __name__ == "__main__":
    main()
