#!/usr/bin/env python3
"""eod-veto-shadow — score the swept-level-reclaim veto against today's engine trades
WITHOUT changing anything. Reads the candle replay the EOD driver already makes.

    python3 scripts/eod-veto-shadow.py <date> [replay.json] [engines]

Writes docs/research/shadows/veto/<date>.json + .md and appends to veto-ledger.csv.
Buckets per engine: reclaim (entered against a swept-and-reclaimed level), clean,
untagged (no candles or fewer than 4 bars before entry).
"""
import sys, json, csv
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v5.reclaim import tag_from_bars  # noqa: E402

OUT = ROOT / "docs" / "research" / "shadows" / "veto"
TAGS = ("reclaim", "clean", "untagged")


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
        out["engines"][eng] = {"trades": rows, "buckets": _bucket(rows)}
        all_trades += rows
    out["fleet"] = _bucket(all_trades)
    return out


def write_ledger(path, scored):
    path = Path(path)
    rows = []
    if path.exists():
        with open(path) as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != scored["date"]]
    for eng, e in scored["engines"].items():
        for tag in TAGS:
            b = e["buckets"][tag]
            rows.append({"date": scored["date"], "engine": eng, "tag": tag, "n": b["n"], "pnl": b["pnl"], "win_pct": b["win"]})
    rows.sort(key=lambda r: (r["date"], r["engine"], r["tag"]))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "engine", "tag", "n", "pnl", "win_pct"])
        w.writeheader(); w.writerows(rows)


def write_md(path, scored):
    lines = [f"# Veto shadow — {scored['date']}", "",
             "Engine SHORTs entered within 3 bars of a swept-and-reclaimed session low (LONGs: rejected session high).",
             "Nothing was blocked; this is the score the veto WOULD have had.", "",
             "| Engine | Tag | n | P&L | Win |", "|---|---|---:|---:|---:|"]
    for eng, e in scored["engines"].items():
        for tag in TAGS:
            b = e["buckets"][tag]
            lines.append(f"| {eng} | {tag} | {b['n']} | {b['pnl']:,.0f} | {b['win']}% |")
    f = scored["fleet"]
    lines += ["", f"Fleet: reclaim {f['reclaim']['n']} trades ₹{f['reclaim']['pnl']:,.0f} · clean {f['clean']['n']} trades ₹{f['clean']['pnl']:,.0f} · untagged {f['untagged']['n']}"]
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
    f = scored["fleet"]
    print(f"veto shadow {date}: reclaim n={f['reclaim']['n']} pnl={f['reclaim']['pnl']:,.0f} | clean n={f['clean']['n']} pnl={f['clean']['pnl']:,.0f} | untagged {f['untagged']['n']} -> {OUT / (date + '.md')}")


if __name__ == "__main__":
    main()
