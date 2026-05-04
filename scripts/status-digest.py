#!/usr/bin/env python3
"""Build a compact battle-status digest string. Prints to stdout for Telegram send."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TODAY = datetime.now().strftime("%Y-%m-%d")

# Active engines (7) — v4 RE-INSTATED 2026-04-28 after 82% WR contradiction.
# v6 NEW 2026-04-28 EOD: "v4 raw signals + Track A bolt-on" experiment.
# v5_8 NEW 2026-04-29 EOD: v5 with regime-aware slot partition DISABLED.
# v5_2 and v5_3 still retired.
ENGINES = [
    ("v4", "v4"),
    ("v5", "v5"),
    ("v5_classic", "v5-classic"),
    ("v5_6", "v5.6"),
    ("v5_7", "v5.7"),
    ("v6", "v6"),
    ("v5_8", "v5.8"),
]


def engine_stats(key: str) -> dict:
    fp = ROOT / "docs" / "paper-trades" / key / f"{TODAY}.json"
    if not fp.exists():
        return {"pnl": 0, "trades": 0, "wins": 0, "losses": 0, "open": 0, "win_rate": 0}
    try:
        d = json.loads(fp.read_text())
    except Exception:
        return {"pnl": 0, "trades": 0, "wins": 0, "losses": 0, "open": 0, "win_rate": 0}

    # v4 has flat keys
    if key == "v4":
        closed = d.get("closed_trades") or [p for p in d.get("positions", []) if p.get("status") == "closed"]
        pnl = d.get("realized_pnl", 0)
        wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
        losses = sum(1 for t in closed if t.get("pnl", 0) < 0)
        open_ct = sum(1 for p in d.get("positions", []) if p.get("status") != "closed")
        trades = len(closed)
    else:
        # v5 family uses summary
        s = d.get("summary", {})
        pnl = s.get("total_pnl", 0)
        wins = s.get("wins", 0)
        losses = s.get("losses", 0)
        trades = s.get("trades", 0)
        open_ct = sum(len(p.get("positions", [])) for p in d.get("pools", {}).values())
    wr = (wins / trades * 100) if trades else 0
    return {"pnl": pnl, "trades": trades, "wins": wins, "losses": losses, "open": open_ct, "win_rate": wr}


rows = []
for key, label in ENGINES:
    s = engine_stats(key)
    rows.append((label, s))
rows.sort(key=lambda r: -r[1]["pnl"])

now = datetime.now().strftime("%H:%M IST")
close = 15 * 60 + 15
nowmin = datetime.now().hour * 60 + datetime.now().minute
mins_left = max(0, close - nowmin)

lines = [f"📊 TradePilot — {now} (T-{mins_left}min to close)"]
lines.append("")
total_pnl = sum(r[1]["pnl"] for r in rows)
total_trades = sum(r[1]["trades"] for r in rows)
lines.append(f"Combined: Rs {total_pnl:+,.0f} across {total_trades} trades")
lines.append("")
medals = ["🥇", "🥈", "🥉", " 4", " 5", " 6", " 7"]
for i, (label, s) in enumerate(rows):
    medal = medals[i]
    lines.append(
        f"{medal} {label:11s} Rs {s['pnl']:+8,.0f}  "
        f"{s['wins']:2d}W/{s['losses']:2d}L "
        f"({s['win_rate']:3.0f}%)  open:{s['open']:2d}"
    )

# Highlight the v5 vs v5_classic experiment
v5_pnl = next((s["pnl"] for l, s in rows if l == "v5"), 0)
v5c_pnl = next((s["pnl"] for l, s in rows if l == "v5-classic"), 0)
delta = v5c_pnl - v5_pnl
sign = "+" if delta > 0 else ""
lines.append("")
lines.append(f"🧪 v5-classic vs v5: {sign}Rs {delta:+,.0f} (pre-Rust advantage)")

print("\n".join(lines))
