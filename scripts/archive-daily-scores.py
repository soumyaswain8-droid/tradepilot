#!/usr/bin/env python3
"""
Daily Scores Archiver — captures the dashboard's full ML score list once a day.

Why: the dashboard's score_stocks() output drives the Stocks tab and Market
Pulse picks, but the values aren't persisted. The 2026-04-22 consensus-pick
analysis was limited because we couldn't compare past trades to historical
BUY lists. This archiver fixes that going forward.

Output:
  docs/dashboard-scores/YYYY-MM-DD.json
  {
    "date": "2026-04-23",
    "captured_at": "09:00:15 IST",
    "scorer": "ai_scorer.score_stocks",
    "elapsed_secs": 16.4,
    "total_scored": 381,
    "buy_count": 89,
    "hold_count": 142,
    "sell_count": 150,
    "buy_list": ["ALOKINDS", "TCS", ...],
    "stocks": [{full record per stock}, ...]
  }

Usage:
  python3 scripts/archive-daily-scores.py            # capture today (skips if exists)
  python3 scripts/archive-daily-scores.py --force    # overwrite today's file
  python3 scripts/archive-daily-scores.py --status   # show what's archived
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "dashboard-scores"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def make_serializable(obj):
    """Strip numpy types and other non-JSON-friendly values."""
    if hasattr(obj, "item"):                    # numpy scalar
        try: return obj.item()
        except Exception: pass
    if hasattr(obj, "tolist"):                  # numpy array
        try: return obj.tolist()
        except Exception: pass
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_serializable(v) for v in obj]
    return obj


def show_status() -> int:
    files = sorted(OUT_DIR.glob("2026-*.json"))
    if not files:
        print("No archived scores yet.")
        return 0
    print(f"Archived files in {OUT_DIR.relative_to(ROOT)}/:\n")
    print(f"  {'date':<12} {'buys':>5} {'holds':>5} {'sells':>5} {'total':>6} {'captured at':<12}")
    print("  " + "-" * 50)
    for f in files:
        try:
            d = json.loads(f.read_text())
            print(f"  {d.get('date','?'):<12} {d.get('buy_count',0):>5} "
                  f"{d.get('hold_count',0):>5} {d.get('sell_count',0):>5} "
                  f"{d.get('total_scored',0):>6} {d.get('captured_at','?'):<12}")
        except Exception as e:
            print(f"  {f.stem:<12}  parse error: {e}")
    return 0


def capture(force: bool = False) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    out_path = OUT_DIR / f"{today}.json"
    if out_path.exists() and not force:
        d = json.loads(out_path.read_text())
        print(f"[archive-scores] {today} already captured "
              f"({d.get('buy_count',0)} BUY · {d.get('total_scored',0)} total · "
              f"at {d.get('captured_at','?')}).")
        print(f"[archive-scores] use --force to overwrite.")
        return 0

    print(f"[archive-scores] capturing scores for {today}...")
    sys.path.insert(0, str(ROOT / "prototype"))

    scorer_name = ""
    try:
        from ai_scorer_v2 import score_stocks_v2 as scorer
        scorer_name = "ai_scorer_v2.score_stocks_v2"
    except ImportError:
        try:
            from ai_scorer import score_stocks as scorer
            scorer_name = "ai_scorer.score_stocks"
        except ImportError as e:
            print(f"[archive-scores] FATAL: no scorer available — {e}")
            return 2

    t0 = time.time()
    try:
        raw = scorer()
    except Exception as e:
        print(f"[archive-scores] FATAL: scorer raised — {e}")
        return 3
    elapsed = round(time.time() - t0, 2)

    if not raw:
        print(f"[archive-scores] WARN: scorer returned 0 stocks — not writing file.")
        return 4

    stocks = [make_serializable(s) for s in raw]
    buy = [s for s in stocks if (s.get("direction") or "").upper() == "BUY"]
    hold = [s for s in stocks if (s.get("direction") or "").upper() == "HOLD"]
    sell = [s for s in stocks if (s.get("direction") or "").upper() == "SELL"]

    payload = {
        "date": today,
        "captured_at": datetime.now().strftime("%H:%M:%S IST"),
        "scorer": scorer_name,
        "elapsed_secs": elapsed,
        "total_scored": len(stocks),
        "buy_count": len(buy),
        "hold_count": len(hold),
        "sell_count": len(sell),
        "score_threshold_buy": 65,    # documented for future analysis
        "buy_list": sorted([s.get("name") or s.get("symbol", "?") for s in buy]),
        "stocks": stocks,
    }

    out_path.write_text(json.dumps(payload, indent=2, default=str))
    size_kb = out_path.stat().st_size / 1024
    print(f"[archive-scores] wrote {out_path.relative_to(ROOT)} ({size_kb:.1f} KB)")
    print(f"[archive-scores] {payload['total_scored']} scored · "
          f"{payload['buy_count']} BUY · {payload['hold_count']} HOLD · "
          f"{payload['sell_count']} SELL · took {elapsed}s")
    if buy:
        top10 = sorted(buy, key=lambda s: -float(s.get("score", 0)))[:10]
        print("[archive-scores] top 10 BUY:")
        for s in top10:
            print(f"    {s.get('name', s.get('symbol','?')):<12} "
                  f"score={float(s.get('score',0)):>5.1f}  price=Rs {float(s.get('price',0)):>9.2f}")
    return 0


def main() -> int:
    if "--status" in sys.argv:
        return show_status()
    force = "--force" in sys.argv
    return capture(force=force)


if __name__ == "__main__":
    sys.exit(main())
