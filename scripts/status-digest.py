#!/usr/bin/env python3
"""Build a compact editorial-style digest for Telegram. Prints HTML to stdout.

Output is wrapped in <pre>...</pre> for monospace rendering; sender must use
parse_mode=HTML when forwarding to Telegram (telegram-digest.sh does this).

Aesthetic refresh 2026-05-07: stripped emoji noise (the 🥇🥈🥉 medals, the
chart bar, the lab-flask), replaced with editorial dividers, en-dashes, and
column-aligned mono. Matches the new TradePilot landing/dashboard voice.
"""
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
    ("v5_classic", "v5_classic"),
    ("v5_6", "v5_6"),
    ("v5_7", "v5_7"),
    ("v6", "v6"),
    ("v5_8", "v5_8"),
]


def engine_stats(key: str) -> dict:
    fp = ROOT / "docs" / "paper-trades" / key / f"{TODAY}.json"
    if not fp.exists():
        return {"pnl": 0, "trades": 0, "wins": 0, "losses": 0, "open": 0, "win_rate": 0}
    try:
        d = json.loads(fp.read_text())
    except Exception:
        return {"pnl": 0, "trades": 0, "wins": 0, "losses": 0, "open": 0, "win_rate": 0}

    if key == "v4":
        closed = d.get("closed_trades") or [p for p in d.get("positions", []) if p.get("status") == "closed"]
        pnl = d.get("realized_pnl", 0)
        wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
        losses = sum(1 for t in closed if t.get("pnl", 0) < 0)
        open_ct = sum(1 for p in d.get("positions", []) if p.get("status") != "closed")
        trades = len(closed)
    else:
        s = d.get("summary", {})
        pnl = s.get("total_pnl", 0)
        wins = s.get("wins", 0)
        losses = s.get("losses", 0)
        trades = s.get("trades", 0)
        open_ct = sum(len(p.get("positions", [])) for p in d.get("pools", {}).values())
    wr = (wins / trades * 100) if trades else 0
    return {"pnl": pnl, "trades": trades, "wins": wins, "losses": losses, "open": open_ct, "win_rate": wr}


def fmt_pnl(n: float) -> str:
    """Indian-grouping rupee with sign. e.g. +1,96,789 / -5,000."""
    sign = "+" if n >= 0 else "-"
    a = abs(int(round(n)))
    # Indian grouping: last 3 digits, then comma every 2 digits
    s = str(a)
    if len(s) <= 3:
        return f"{sign}{s}"
    last3 = s[-3:]
    rest = s[:-3]
    chunks = []
    while len(rest) > 2:
        chunks.append(rest[-2:])
        rest = rest[:-2]
    if rest:
        chunks.append(rest)
    chunks.reverse()
    return f"{sign}{','.join(chunks)},{last3}"


def main():
    rows = []
    for key, label in ENGINES:
        s = engine_stats(key)
        rows.append((label, s))
    rows.sort(key=lambda r: -r[1]["pnl"])

    now = datetime.now().strftime("%H:%M IST")
    close_min = 15 * 60 + 15
    nowmin = datetime.now().hour * 60 + datetime.now().minute
    mins_left = max(0, close_min - nowmin)

    total_pnl = sum(r[1]["pnl"] for r in rows)
    total_trades = sum(r[1]["trades"] for r in rows)
    total_open = sum(r[1]["open"] for r in rows)

    # Width-43 monospace block. Telegram <pre> renders in JetBrains-Mono-like font.
    width = 43
    line = "─" * width

    body = []
    # Header bar
    if mins_left > 0:
        title = f"TRADEPILOT  ·  {now}  ·  T−{mins_left}min"
    else:
        title = f"TRADEPILOT  ·  {now}  ·  EOD"
    body.append(title.upper())
    body.append(line)
    # Combined headline number — given the "by the numbers" treatment
    body.append(f"  COMBINED  Rs {fmt_pnl(total_pnl):>10}   {total_trades} trades")
    body.append(f"  OPEN      {total_open:>10}   v4 vs v5 family below")
    body.append(line)
    # Column header
    body.append(f"  #  ENGINE        PNL        WR    OPEN")
    body.append(line)
    # Per-engine rows. Mark v4 with a bullet if it leads, otherwise plain.
    for i, (label, s) in enumerate(rows):
        rank = f"{i + 1}"
        leader = "★" if i == 0 else "·"
        pnl_str = fmt_pnl(s['pnl'])
        body.append(
            f"  {rank}{leader} {label:<11s} Rs {pnl_str:>9} {s['win_rate']:>3.0f}%   {s['open']:>2}"
        )
    body.append(line)

    # v5 vs v5_classic experiment row — labeled, no emoji
    v5_pnl = next((s["pnl"] for l, s in rows if l == "v5"), 0)
    v5c_pnl = next((s["pnl"] for l, s in rows if l == "v5_classic"), 0)
    delta = v5c_pnl - v5_pnl
    body.append(f"  EXPERIMENT  v5_classic − v5: Rs {fmt_pnl(delta):>8}")

    # v4 vs v5_family split — the headline Mode A finding
    v4_pnl = next((s["pnl"] for l, s in rows if l == "v4"), 0)
    v5_family_pnl = total_pnl - v4_pnl
    if total_pnl != 0:
        v4_pct = round(v4_pnl / total_pnl * 100)
        body.append(f"  SPLIT       v4 {v4_pct:>3}%   v5 family {100 - v4_pct:>3}%")
    body.append(line)

    # Print HTML for Telegram (parse_mode=HTML in telegram-digest.sh)
    print("<pre>" + "\n".join(body) + "</pre>")


if __name__ == "__main__":
    main()
