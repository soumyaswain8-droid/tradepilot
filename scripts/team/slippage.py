"""
Execution Analyst — slippage logging and net-of-cost P&L recomputation.

USED TWO WAYS:

1. Live engine hook (per-trade): engine calls record_slippage() at fill time.
   Writes to docs/slippage/YYYY-MM-DD.jsonl

2. EOD batch: aggregate per-trade slippage into a daily report at
   docs/exec/YYYY-MM-DD_slippage.json.

Engine integration (single line in each engine's exit path):

    from scripts.team.slippage import record_slippage
    record_slippage(engine="v5", symbol=sym, direction=dir,
                    expected_price=expected, fill_price=actual,
                    quantity=qty, side="entry|exit", trade_id=tid)

EOD aggregation (run by daily 15:31 IST cron):

    python3 scripts/team/slippage.py --aggregate --date today

Replay mode (Sprint 1 backfill — estimate slippage from existing trade JSONs
using nearest-quote heuristic):

    python3 scripts/team/slippage.py --backfill --engine v5 --from 2026-04-21 --to 2026-05-14
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SLIP_DIR = PROJECT_ROOT / "docs" / "slippage"
EXEC_DIR = PROJECT_ROOT / "docs" / "exec"
SLIP_DIR.mkdir(parents=True, exist_ok=True)
EXEC_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT_ROOT))
from scripts.team.log import log_activity  # noqa: E402

IST = timezone(timedelta(hours=5, minutes=30))


def _date_today() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def _ts() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def record_slippage(engine: str, symbol: str, direction: str,
                    expected_price: float, fill_price: float,
                    quantity: int, side: str,
                    trade_id: str | None = None,
                    extra: dict | None = None) -> dict:
    """
    Append a single slippage record. Both sides (entry + exit) get logged separately.
    Returns the record.
    """
    if expected_price <= 0 or fill_price <= 0:
        return {}  # nonsensical input, skip silently
    slip = (fill_price - expected_price) / expected_price
    # Direction-aware: for BUY entries (or SHORT exits) higher fill = adverse
    if (side == "entry" and direction == "BUY") or (side == "exit" and direction == "SELL"):
        adverse_bps = slip * 10_000
    else:
        adverse_bps = -slip * 10_000
    record = {
        "ts": _ts(),
        "engine": engine,
        "trade_id": trade_id,
        "symbol": symbol,
        "direction": direction,
        "side": side,
        "expected_price": expected_price,
        "fill_price": fill_price,
        "quantity": quantity,
        "slip_pct": slip,
        "adverse_bps": adverse_bps,
        "trade_value": fill_price * quantity,
    }
    if extra:
        record["extra"] = extra
    path = SLIP_DIR / f"{_date_today()}.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n")
    return record


def aggregate_day(date_str: str | None = None) -> dict:
    """Read all slippage records for one date; produce per-engine daily summary."""
    date_str = date_str or _date_today()
    path = SLIP_DIR / f"{date_str}.jsonl"
    if not path.exists():
        return {"date": date_str, "engines": {}, "note": "no slippage data"}

    by_engine: dict[str, list[dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        by_engine.setdefault(r["engine"], []).append(r)

    summary: dict[str, dict] = {}
    for eng, records in by_engine.items():
        n = len(records)
        if n == 0:
            continue
        adverse_total_bps = sum(r["adverse_bps"] for r in records)
        weights = [abs(r["trade_value"]) for r in records]
        if sum(weights) > 0:
            weighted_adverse_bps = sum(r["adverse_bps"] * w for r, w in zip(records, weights)) / sum(weights)
        else:
            weighted_adverse_bps = 0
        total_value = sum(r["trade_value"] for r in records)
        cost_at_actual = sum(abs(r["adverse_bps"])/10_000 * r["trade_value"] for r in records)
        cost_at_10bps = sum(0.001 * r["trade_value"] for r in records)
        cost_at_15bps = sum(0.0015 * r["trade_value"] for r in records)

        summary[eng] = {
            "n_legs": n,
            "trades_value_total": round(total_value, 2),
            "avg_adverse_bps": round(adverse_total_bps / n, 2),
            "weighted_adverse_bps": round(weighted_adverse_bps, 2),
            "implied_cost_actual_rs": round(cost_at_actual, 2),
            "implied_cost_10bps_rs": round(cost_at_10bps, 2),
            "implied_cost_15bps_rs": round(cost_at_15bps, 2),
        }

    out = {"date": date_str, "engines": summary, "generated_at": _ts()}
    out_path = EXEC_DIR / f"{date_str}_slippage.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    log_activity("execution-analyst", "slippage-aggregate",
                 summary=f"Aggregated slippage for {date_str}: {len(summary)} engines, "
                         f"{sum(s['n_legs'] for s in summary.values())} legs",
                 links={"report": str(out_path.relative_to(PROJECT_ROOT))})
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--aggregate", action="store_true")
    p.add_argument("--date", default=None,
                   help="YYYY-MM-DD or 'today' (default)")
    p.add_argument("--smoke", action="store_true",
                   help="Generate a tiny synthetic slippage record for testing")
    args = p.parse_args()

    if args.smoke:
        # Synthetic record for dashboard smoke test
        rec = record_slippage(
            engine="v5", symbol="SMOKE_TEST",
            direction="BUY", expected_price=100.0, fill_price=100.12,
            quantity=100, side="entry", trade_id="smoke-001")
        print("Smoke record written:", rec)
        return

    if args.aggregate:
        date_str = None if (not args.date or args.date == "today") else args.date
        out = aggregate_day(date_str)
        print(json.dumps(out, indent=2))
        return

    p.print_help()


if __name__ == "__main__":
    main()
