"""Backtest runner for staged learnings.

Replays historical trades from engine reports (docs/paper-trades/{engine}/YYYY-MM-DD_report.md)
with proposed rule changes applied, then compares counterfactual P&L.

Currently supports:
    #001: Pre-market gap filter (disable shorts on gap-up, longs on gap-down)
    #003: Same-stock same-direction re-entry block after stoploss

Usage:
    python3 -m prototype.backtest.runner --learning 001 --thresholds 0.15 0.2 0.3
    python3 -m prototype.backtest.runner --learning 003 --policy strict
    python3 -m prototype.backtest.runner --all
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import date as date_type
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PAPER_TRADE_DIR = ROOT / "docs" / "paper-trades"
RESULTS_DIR = ROOT / "learnings" / "backtest_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

ENGINES = ["v4", "v5", "v5_6", "v5_7"]


@dataclass
class Trade:
    engine: str
    date: str                # YYYY-MM-DD
    direction: str           # LONG or SHORT
    pool: str                # INTRADAY, SWING, etc
    symbol: str
    entry: float
    exit: float
    pnl: float
    reason: str              # TARGET, STOPLOSS, SIGNAL_FLIP, SIGNAL_EXIT, TIME_EXIT
    order: int = 0           # intra-day ordering (by row number in report)


def parse_report(engine: str, date_str: str) -> list[Trade]:
    """Parse a markdown trade report into structured Trade objects."""
    fp = PAPER_TRADE_DIR / engine / f"{date_str}_report.md"
    if not fp.exists():
        return []
    trades: list[Trade] = []
    in_table = False
    order = 0
    # Report format: | # | Type | Pool | Stock | Entry | Exit | P&L | Reason |
    pnl_re = re.compile(r"Rs\s+([+-]?[\d,]+)")
    for line in fp.read_text().splitlines():
        line = line.strip()
        if line.startswith("| # |") or line.startswith("|---"):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.startswith("|") or line.startswith("| #"):
            continue
        parts = [c.strip() for c in line.strip("|").split("|")]
        if len(parts) < 8:
            if line and not line.startswith("|"):
                in_table = False  # exited the table
            continue
        try:
            _, dtype, pool, sym, entry_s, exit_s, pnl_s, reason = parts[:8]
            if dtype not in ("LONG", "SHORT"):
                continue
            m = pnl_re.search(pnl_s)
            pnl = float(m.group(1).replace(",", "")) if m else 0.0
            trades.append(Trade(
                engine=engine, date=date_str, direction=dtype, pool=pool,
                symbol=sym, entry=float(entry_s), exit=float(exit_s),
                pnl=pnl, reason=reason, order=order,
            ))
            order += 1
        except (ValueError, IndexError):
            continue
    return trades


def load_all_trades() -> list[Trade]:
    """Load every trade from every engine's historical reports."""
    out: list[Trade] = []
    for engine_dir in sorted(PAPER_TRADE_DIR.iterdir()):
        if not engine_dir.is_dir():
            continue
        engine = engine_dir.name
        if engine not in ENGINES:
            continue
        for report in sorted(engine_dir.glob("*_report.md")):
            date_str = report.stem.replace("_report", "")
            out.extend(parse_report(engine, date_str))
    return out


def compute_daily_gaps() -> dict[str, float]:
    """Return {date: gap_pct} from Nifty index data. Positive = gap up."""
    df = pd.read_csv(ROOT / "prototype" / "data" / "^NSEI.csv", parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df["prev_close"] = df["Close"].shift(1)
    df["gap_pct"] = (df["Open"] - df["prev_close"]) / df["prev_close"] * 100
    return {row["Date"].strftime("%Y-%m-%d"): float(row["gap_pct"])
            for _, row in df.iterrows() if pd.notna(row["gap_pct"])}


# ═══════════════════════════ LEARNING #001: Gap filter ═══════════════════════════

def backtest_gap_filter(trades: list[Trade], gaps: dict[str, float],
                        threshold: float) -> dict:
    """Filter out shorts on days with gap > +threshold and longs on gap < -threshold."""
    kept: list[Trade] = []
    blocked: list[Trade] = []
    for t in trades:
        gap = gaps.get(t.date)
        if gap is None:
            kept.append(t)
            continue
        if t.direction == "SHORT" and gap > threshold:
            blocked.append(t)
        elif t.direction == "LONG" and gap < -threshold:
            blocked.append(t)
        else:
            kept.append(t)
    return summarize(trades, kept, blocked, f"gap_filter_{threshold:+.2f}%")


# ═══════════════════════════ LEARNING #003: Re-entry block ═══════════════════════════

def backtest_reentry_block(trades: list[Trade], max_sl_before_block: int) -> dict:
    """Block further entries in (symbol, direction) after N stoplosses on the same day."""
    # Group by engine for separate simulation (each engine has its own risk manager)
    kept: list[Trade] = []
    blocked: list[Trade] = []
    # Process in chronological order per engine
    trades_sorted = sorted(trades, key=lambda t: (t.engine, t.date, t.order))
    sl_count: dict[tuple, int] = {}
    for t in trades_sorted:
        key = (t.engine, t.date, t.symbol, t.direction)
        if sl_count.get(key, 0) >= max_sl_before_block:
            blocked.append(t)
            continue
        kept.append(t)
        if t.reason == "STOPLOSS":
            sl_count[key] = sl_count.get(key, 0) + 1
    return summarize(trades, kept, blocked, f"reentry_block_after_{max_sl_before_block}_SL")


# ═══════════════════════════ Summary ═══════════════════════════

def summarize(all_trades: list[Trade], kept: list[Trade], blocked: list[Trade],
              variant_name: str) -> dict:
    """Compute baseline vs filtered P&L, with per-engine breakdown."""
    baseline_pnl = sum(t.pnl for t in all_trades)
    kept_pnl = sum(t.pnl for t in kept)
    blocked_losses_avoided = -sum(t.pnl for t in blocked if t.pnl < 0)
    blocked_gains_missed = sum(t.pnl for t in blocked if t.pnl > 0)
    net_benefit = blocked_losses_avoided - blocked_gains_missed

    per_engine = {}
    for engine in ENGINES:
        eng_all = [t for t in all_trades if t.engine == engine]
        eng_kept = [t for t in kept if t.engine == engine]
        eng_blocked = [t for t in blocked if t.engine == engine]
        if not eng_all:
            continue
        per_engine[engine] = {
            "baseline_pnl": sum(t.pnl for t in eng_all),
            "filtered_pnl": sum(t.pnl for t in eng_kept),
            "trades_blocked": len(eng_blocked),
            "total_trades": len(eng_all),
            "losses_avoided": -sum(t.pnl for t in eng_blocked if t.pnl < 0),
            "gains_missed": sum(t.pnl for t in eng_blocked if t.pnl > 0),
        }

    return {
        "variant": variant_name,
        "total_trades": len(all_trades),
        "kept": len(kept),
        "blocked": len(blocked),
        "baseline_pnl": round(baseline_pnl, 2),
        "filtered_pnl": round(kept_pnl, 2),
        "delta_pnl": round(kept_pnl - baseline_pnl, 2),
        "losses_avoided": round(blocked_losses_avoided, 2),
        "gains_missed": round(blocked_gains_missed, 2),
        "net_benefit": round(net_benefit, 2),
        "per_engine": per_engine,
    }


# ═══════════════════════════ CLI ═══════════════════════════

def fmt_inr(x):
    return f"Rs {x:+,.0f}" if x else "Rs 0"


def print_result(r: dict):
    print(f"\n════ {r['variant']} ════")
    print(f"Total trades: {r['total_trades']}  |  Kept: {r['kept']}  |  Blocked: {r['blocked']}")
    print(f"Baseline P&L:  {fmt_inr(r['baseline_pnl'])}")
    print(f"Filtered P&L:  {fmt_inr(r['filtered_pnl'])}")
    print(f"Δ P&L:         {fmt_inr(r['delta_pnl'])}   (losses avoided {fmt_inr(r['losses_avoided'])}, gains missed {fmt_inr(r['gains_missed'])})")
    print(f"Net benefit:   {fmt_inr(r['net_benefit'])}")
    if r["per_engine"]:
        print("Per-engine:")
        for eng, m in r["per_engine"].items():
            blocked_pct = m["trades_blocked"]/m["total_trades"]*100 if m["total_trades"] else 0
            print(f"  {eng:5s}  base={fmt_inr(m['baseline_pnl']):>12s}  "
                  f"filt={fmt_inr(m['filtered_pnl']):>12s}  "
                  f"blocked={m['trades_blocked']:3d}/{m['total_trades']:3d} ({blocked_pct:.0f}%)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--learning", choices=["001", "003", "all"], default="all")
    ap.add_argument("--thresholds", type=float, nargs="+", default=[0.15, 0.2, 0.3],
                    help="Gap thresholds in % for learning 001")
    ap.add_argument("--policies", type=int, nargs="+", default=[1, 2],
                    help="Max SL before block for learning 003 (1=strict, 2=lenient)")
    args = ap.parse_args()

    trades = load_all_trades()
    gaps = compute_daily_gaps()

    print(f"Loaded {len(trades)} trades across {len({t.engine for t in trades})} engines, "
          f"{len({t.date for t in trades})} dates")
    print(f"Daily gaps available for {len(gaps)} dates")

    all_results = []
    if args.learning in ("001", "all"):
        print("\n╔════════════════════════════════════════════════════╗")
        print("║  LEARNING #001: Pre-market gap filter              ║")
        print("╚════════════════════════════════════════════════════╝")
        for th in args.thresholds:
            r = backtest_gap_filter(trades, gaps, th)
            print_result(r)
            all_results.append(r)

    if args.learning in ("003", "all"):
        print("\n╔════════════════════════════════════════════════════╗")
        print("║  LEARNING #003: Same-stock re-entry block          ║")
        print("╚════════════════════════════════════════════════════╝")
        for p in args.policies:
            r = backtest_reentry_block(trades, max_sl_before_block=p)
            print_result(r)
            all_results.append(r)

    # Save results
    out_path = RESULTS_DIR / f"backtest_results_{date_type.today().isoformat()}.json"
    out_path.write_text(json.dumps({
        "generated_at": pd.Timestamp.now().isoformat(),
        "trades_analyzed": len(trades),
        "date_range": [min(t.date for t in trades), max(t.date for t in trades)] if trades else None,
        "results": all_results,
    }, indent=2, default=str))
    print(f"\n📁 Results saved: {out_path}")


if __name__ == "__main__":
    main()
