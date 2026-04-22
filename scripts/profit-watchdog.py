#!/usr/bin/env python3
"""
Profit Watchdog — snapshots all engines every 30 min through the trading day.

Reads each engine's today-JSON, extracts summary + position state, appends a
row to docs/watchdog/YYYY-MM-DD_snapshots.jsonl. Stops at 15:35 automatically.

Launched by scripts/launch-profit-watchdog.sh (runs in background).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "docs" / "paper-trades"
OUT_DIR = ROOT / "docs" / "watchdog"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ENGINES = ["v4", "v5", "v5_classic", "v5_2", "v5_3", "v5_6", "v5_7"]
SNAPSHOT_INTERVAL_SEC = 30 * 60     # every 30 min
STOP_AT = dtime(15, 35)              # market auto-stop


def read_engine_state(engine: str, date_str: str) -> dict:
    """Return a small summary dict for one engine, or {} if file missing."""
    path = PAPER / engine / f"{date_str}.json"
    if not path.exists():
        return {"engine": engine, "status": "no_file"}
    try:
        d = json.loads(path.read_text())
    except Exception as e:
        return {"engine": engine, "status": f"parse_error: {e}"}

    summary = d.get("summary", {}) or {}
    total_pnl = float(summary.get("total_pnl", 0) or 0)
    trades = int(summary.get("trades", 0) or 0)
    wins = int(summary.get("wins", 0) or 0)
    losses = int(summary.get("losses", 0) or 0)
    win_rate = round(100.0 * wins / trades, 1) if trades > 0 else 0.0

    pools = d.get("pools", {}) or {}
    open_pos = 0
    deployed = 0.0
    pool_breakdown = {}
    for pname, pool in pools.items():
        positions = pool.get("positions", []) or []
        open_pos += len(positions)
        pool_deployed = sum(
            float(p.get("cost") or (p.get("qty", 0) * p.get("entry_price", 0)))
            for p in positions
        )
        deployed += pool_deployed
        pool_breakdown[pname] = {
            "open": len(positions),
            "closed": len(pool.get("closed_trades", []) or []),
            "realized": float(pool.get("realized_pnl", 0) or 0),
        }

    return {
        "engine": engine,
        "status": "ok",
        "total_pnl": round(total_pnl, 2),
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "open_positions": open_pos,
        "deployed_rs": round(deployed, 2),
        "regime": d.get("regime", "?"),
        "scan_count": int(summary.get("scan_count", 0) or 0),
        "pools": pool_breakdown,
    }


def snapshot_once(date_str: str) -> dict:
    """Take one snapshot of all engines. Returns the snapshot dict."""
    now = datetime.now()
    snap = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time_hhmm": now.strftime("%H:%M"),
        "engines": [read_engine_state(e, date_str) for e in ENGINES],
    }

    out_path = OUT_DIR / f"{date_str}_snapshots.jsonl"
    with out_path.open("a") as f:
        f.write(json.dumps(snap) + "\n")

    # Also print a one-line scoreboard for tail-following
    ranked = sorted(
        [e for e in snap["engines"] if e.get("status") == "ok"],
        key=lambda e: e.get("total_pnl", 0),
        reverse=True,
    )
    line_parts = [f"[{snap['time_hhmm']}]"]
    for e in ranked[:3]:  # show top 3
        line_parts.append(
            f"{e['engine']}:{e['total_pnl']:+.0f}({e['trades']}t/{e['win_rate']}%)"
        )
    print(" ".join(line_parts), flush=True)
    return snap


def should_stop() -> bool:
    now_t = datetime.now().time()
    return now_t >= STOP_AT


def main() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[profit-watchdog] starting for {today}", flush=True)
    print(f"[profit-watchdog] snapshots every {SNAPSHOT_INTERVAL_SEC // 60} min "
          f"-> {OUT_DIR}/{today}_snapshots.jsonl", flush=True)
    print(f"[profit-watchdog] auto-stop at {STOP_AT.strftime('%H:%M')}", flush=True)

    # Take an immediate snapshot on boot, then loop
    snapshot_once(today)

    while not should_stop():
        # Sleep in 60-second chunks so we can stop promptly at 15:35
        slept = 0
        while slept < SNAPSHOT_INTERVAL_SEC and not should_stop():
            time.sleep(60)
            slept += 60
        if should_stop():
            break
        try:
            snapshot_once(today)
        except Exception as e:
            print(f"[profit-watchdog] snapshot error: {e}", flush=True)

    # Final snapshot right before stop
    try:
        snapshot_once(today)
    except Exception:
        pass
    print(f"[profit-watchdog] reached stop time, exiting", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
