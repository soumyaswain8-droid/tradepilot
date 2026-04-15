#!/usr/bin/env python3
"""
TradePilot v2 vs v3 Daily Comparison
Loads today's v2 intraday scores, runs v3 scoring on the same stocks,
fetches live prices from yfinance, and compares both against actual movement.

Usage:
    python3 scripts/v3-daily-compare.py                # Compare using latest v2 snapshot
    python3 scripts/v3-daily-compare.py --snapshot 1158 # Compare using specific v2 snapshot
    python3 scripts/v3-daily-compare.py --date 2026-04-06 # Compare for a different date
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PROTO_DIR = PROJECT_ROOT / "prototype"
WEEK_DIR = PROJECT_ROOT / "docs" / "validation" / "week-2026-04-07"

# Add prototype dir to path so we can import v3 engine
sys.path.insert(0, str(PROTO_DIR))


def load_v2_snapshot(date_str=None, snapshot_time=None):
    """Load the latest (or specified) v2 snapshot for the given date."""
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    day_dir = WEEK_DIR / "daily" / date_str

    if not day_dir.exists():
        print(f"ERROR: No data directory for {date_str} at {day_dir}")
        return None, None

    if snapshot_time:
        target = day_dir / f"{snapshot_time}_scores.json"
        if not target.exists():
            print(f"ERROR: Snapshot {target} not found")
            return None, None
        snapshots = [target]
    else:
        snapshots = sorted(day_dir.glob("????_scores.json"))

    if not snapshots:
        print(f"ERROR: No v2 snapshots found in {day_dir}")
        return None, None

    latest = snapshots[-1]
    with open(latest) as f:
        data = json.load(f)

    print(f"Loaded v2 snapshot: {latest.name} ({len(data['stocks'])} stocks)")
    return data, latest


def run_v3_scoring(symbols):
    """Run v3 scoring engine on the given symbols."""
    try:
        from trading_engine_v3 import score_stocks_v3
        ns_symbols = [s if s.endswith(".NS") else f"{s}.NS" for s in symbols]
        results = score_stocks_v3(ns_symbols)
        print(f"v3 scored {len(results)} stocks (regime-aware engine)")
        return results
    except Exception as e:
        print(f"ERROR running v3 scoring: {e}")
        import traceback
        traceback.print_exc()
        return None


def fetch_live_prices(symbols):
    """Fetch latest prices from yfinance for actual movement comparison."""
    try:
        import yfinance as yf
        ns_symbols = [s if s.endswith(".NS") else f"{s}.NS" for s in symbols]
        data = yf.download(ns_symbols, period="5d", interval="1d",
                           progress=False, threads=True)
        prices = {}
        if "Close" in data.columns:
            close = data["Close"]
            if len(close.shape) == 1:
                # Single stock
                sym = ns_symbols[0].replace(".NS", "")
                if len(close.dropna()) >= 2:
                    prices[sym] = {
                        "prev_close": float(close.dropna().iloc[-2]),
                        "latest_close": float(close.dropna().iloc[-1]),
                    }
            else:
                for col in close.columns:
                    vals = close[col].dropna()
                    sym = col.replace(".NS", "") if isinstance(col, str) else str(col)
                    if len(vals) >= 2:
                        prices[sym] = {
                            "prev_close": float(vals.iloc[-2]),
                            "latest_close": float(vals.iloc[-1]),
                        }
        print(f"Fetched live prices for {len(prices)} stocks")
        return prices
    except Exception as e:
        print(f"ERROR fetching prices: {e}")
        return {}


def evaluate_signal(direction, actual_change_pct):
    """Evaluate whether a signal was correct based on actual price movement."""
    if direction == "BUY":
        return actual_change_pct > 0
    elif direction == "AVOID":
        return actual_change_pct < 0.5
    elif direction == "HOLD":
        return -1.5 <= actual_change_pct <= 2.0
    return None


def compare_v2_v3(v2_snapshot, v3_scores, live_prices):
    """Build comparison of v2 vs v3 predictions against actual movement."""
    v2_map = {s["symbol"].replace(".NS", ""): s for s in v2_snapshot["stocks"]}
    v3_map = {s["symbol"].replace(".NS", ""): s for s in (v3_scores or [])}

    comparisons = []
    v2_correct = 0
    v3_correct = 0
    v2_total = 0
    v3_total = 0
    both_total = 0
    agreement_count = 0

    for symbol in sorted(v2_map.keys()):
        v2 = v2_map[symbol]
        v3 = v3_map.get(symbol)
        live = live_prices.get(symbol)

        actual_change = None
        if live:
            prev = live["prev_close"]
            curr = live["latest_close"]
            if prev > 0:
                actual_change = round(((curr - prev) / prev) * 100, 3)

        entry = {
            "symbol": symbol,
            "v2_score": v2.get("score", 0),
            "v2_direction": v2.get("direction", "?"),
            "v2_price": v2.get("price", 0),
            "v3_score": v3.get("score", 0) if v3 else None,
            "v3_direction": v3.get("direction", "?") if v3 else None,
            "v3_confidence": v3.get("confidence", 0) if v3 else None,
            "v3_market_regime": v3.get("market_regime", "?") if v3 else None,
            "v3_rs_5d": v3.get("relative_strength_5d", 0) if v3 else None,
            "v3_rs_20d": v3.get("relative_strength_20d", 0) if v3 else None,
            "actual_change_pct": actual_change,
            "live_price": live["latest_close"] if live else None,
            "agreement": (v2.get("direction") == v3.get("direction")) if v3 else None,
        }

        # Evaluate accuracy
        if actual_change is not None:
            v2_ok = evaluate_signal(v2.get("direction", "?"), actual_change)
            v3_ok = evaluate_signal(v3.get("direction", "?"), actual_change) if v3 else None

            entry["v2_correct"] = v2_ok
            entry["v3_correct"] = v3_ok

            if v2_ok is not None:
                v2_total += 1
                if v2_ok:
                    v2_correct += 1
            if v3_ok is not None:
                v3_total += 1
                if v3_ok:
                    v3_correct += 1
            if v2_ok is not None and v3_ok is not None:
                both_total += 1
                if entry["agreement"]:
                    agreement_count += 1
        else:
            entry["v2_correct"] = None
            entry["v3_correct"] = None

        comparisons.append(entry)

    # Sort by v2 score descending
    comparisons.sort(key=lambda x: x["v2_score"], reverse=True)

    v2_accuracy = round((v2_correct / v2_total) * 100, 1) if v2_total > 0 else 0
    v3_accuracy = round((v3_correct / v3_total) * 100, 1) if v3_total > 0 else 0
    agreement_rate = round((agreement_count / both_total) * 100, 1) if both_total > 0 else 0

    # Signal distribution
    v2_buys = [c for c in comparisons if c["v2_direction"] == "BUY"]
    v2_holds = [c for c in comparisons if c["v2_direction"] == "HOLD"]
    v2_avoids = [c for c in comparisons if c["v2_direction"] == "AVOID"]
    v3_buys = [c for c in comparisons if c["v3_direction"] == "BUY"]
    v3_holds = [c for c in comparisons if c["v3_direction"] == "HOLD"]
    v3_avoids = [c for c in comparisons if c["v3_direction"] == "AVOID"]

    # Precision by signal type
    def precision(entries, field):
        correct = sum(1 for e in entries if e.get(field) is True)
        total = sum(1 for e in entries if e.get(field) is not None)
        return round((correct / total) * 100, 1) if total > 0 else 0

    regime = comparisons[0]["v3_market_regime"] if comparisons and comparisons[0].get("v3_market_regime") else "UNKNOWN"

    summary = {
        "date": v2_snapshot["date"],
        "v2_snapshot_time": v2_snapshot["time"],
        "market_regime": regime,
        "total_stocks": len(comparisons),
        "v2": {
            "accuracy": v2_accuracy,
            "correct": v2_correct,
            "total_evaluated": v2_total,
            "buy_count": len(v2_buys),
            "hold_count": len(v2_holds),
            "avoid_count": len(v2_avoids),
            "buy_precision": precision(v2_buys, "v2_correct"),
            "hold_precision": precision(v2_holds, "v2_correct"),
            "avoid_precision": precision(v2_avoids, "v2_correct"),
        },
        "v3": {
            "accuracy": v3_accuracy,
            "correct": v3_correct,
            "total_evaluated": v3_total,
            "buy_count": len(v3_buys),
            "hold_count": len(v3_holds),
            "avoid_count": len(v3_avoids),
            "buy_precision": precision(v3_buys, "v3_correct"),
            "hold_precision": precision(v3_holds, "v3_correct"),
            "avoid_precision": precision(v3_avoids, "v3_correct"),
        },
        "agreement": {
            "rate": agreement_rate,
            "agreed": agreement_count,
            "total": both_total,
        },
        "comparisons": comparisons,
    }

    return summary


def print_comparison_table(summary):
    """Print a formatted comparison table to stdout."""
    print(f"\n{'='*75}")
    print(f"  TradePilot v2 vs v3 Comparison -- {summary['date']} ({summary['v2_snapshot_time']})")
    print(f"  Market Regime: {summary['market_regime']}")
    print(f"{'='*75}")

    v2 = summary["v2"]
    v3 = summary["v3"]

    print(f"\n  OVERALL ACCURACY")
    print(f"  {'v2':>8}: {v2['accuracy']:>5.1f}% ({v2['correct']}/{v2['total_evaluated']})")
    print(f"  {'v3':>8}: {v3['accuracy']:>5.1f}% ({v3['correct']}/{v3['total_evaluated']})")
    delta = v3["accuracy"] - v2["accuracy"]
    tag = "v3 BETTER" if delta > 0 else "v2 BETTER" if delta < 0 else "TIED"
    print(f"  {'Delta':>8}: {delta:+.1f}pp [{tag}]")

    print(f"\n  SIGNAL DISTRIBUTION")
    print(f"  {'':>8}  {'BUY':>5}  {'HOLD':>5}  {'AVOID':>5}")
    print(f"  {'v2':>8}  {v2['buy_count']:>5}  {v2['hold_count']:>5}  {v2['avoid_count']:>5}")
    print(f"  {'v3':>8}  {v3['buy_count']:>5}  {v3['hold_count']:>5}  {v3['avoid_count']:>5}")

    print(f"\n  PRECISION BY SIGNAL")
    print(f"  {'':>8}  {'BUY':>7}  {'HOLD':>7}  {'AVOID':>7}")
    print(f"  {'v2':>8}  {v2['buy_precision']:>6.1f}%  {v2['hold_precision']:>6.1f}%  {v2['avoid_precision']:>6.1f}%")
    print(f"  {'v3':>8}  {v3['buy_precision']:>6.1f}%  {v3['hold_precision']:>6.1f}%  {v3['avoid_precision']:>6.1f}%")

    agr = summary["agreement"]
    print(f"\n  AGREEMENT: {agr['rate']}% ({agr['agreed']}/{agr['total']})")

    # Show disagreements (most interesting)
    disagree = [c for c in summary["comparisons"]
                if c["v3_direction"] and c["v2_direction"] != c["v3_direction"]]
    if disagree:
        print(f"\n  DISAGREEMENTS ({len(disagree)}):")
        print(f"  {'Symbol':<10} {'v2':>6} {'v3':>6} {'Actual':>8} {'v2 OK':>6} {'v3 OK':>6}")
        print(f"  {'-'*48}")
        for d in sorted(disagree, key=lambda x: abs(x.get("actual_change_pct", 0) or 0), reverse=True):
            act = f"{d['actual_change_pct']:+.2f}%" if d["actual_change_pct"] is not None else "N/A"
            v2ok = "YES" if d.get("v2_correct") else "NO" if d.get("v2_correct") is False else "-"
            v3ok = "YES" if d.get("v3_correct") else "NO" if d.get("v3_correct") is False else "-"
            print(f"  {d['symbol']:<10} {d['v2_direction']:>6} {d['v3_direction']:>6} {act:>8} {v2ok:>6} {v3ok:>6}")

    # Top v3 BUY picks with RS info
    v3_buys = [c for c in summary["comparisons"] if c["v3_direction"] == "BUY"]
    if v3_buys:
        print(f"\n  v3 TOP BUY PICKS:")
        print(f"  {'Symbol':<10} {'Score':>6} {'RS 5d':>7} {'RS 20d':>7} {'Actual':>8} {'OK':>4}")
        print(f"  {'-'*48}")
        for b in sorted(v3_buys, key=lambda x: x["v3_score"] or 0, reverse=True)[:10]:
            act = f"{b['actual_change_pct']:+.2f}%" if b["actual_change_pct"] is not None else "N/A"
            ok = "YES" if b.get("v3_correct") else "NO" if b.get("v3_correct") is False else "-"
            rs5 = f"{b['v3_rs_5d']:+.1f}%" if b["v3_rs_5d"] is not None else "N/A"
            rs20 = f"{b['v3_rs_20d']:+.1f}%" if b["v3_rs_20d"] is not None else "N/A"
            print(f"  {b['symbol']:<10} {b['v3_score']:>6.1f} {rs5:>7} {rs20:>7} {act:>8} {ok:>4}")

    print(f"\n{'='*75}\n")


def save_comparison(summary, date_str=None):
    """Save comparison results to validation directory."""
    if date_str is None:
        date_str = summary["date"]
    day_dir = WEEK_DIR / "daily" / date_str
    day_dir.mkdir(parents=True, exist_ok=True)

    out_path = day_dir / "v2_vs_v3_comparison.json"
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {out_path}")
    return out_path


def main():
    date_str = None
    snapshot_time = None

    # Parse args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--date" and i + 1 < len(args):
            date_str = args[i + 1]
            i += 2
        elif args[i] == "--snapshot" and i + 1 < len(args):
            snapshot_time = args[i + 1]
            i += 2
        else:
            i += 1

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    print(f"TradePilot v2 vs v3 Comparison -- {date_str}")
    print(f"{'='*50}")

    # Step 1: Load v2 snapshot
    v2_data, v2_path = load_v2_snapshot(date_str, snapshot_time)
    if not v2_data:
        sys.exit(1)

    # Step 2: Extract stock symbols from v2
    symbols = [s["symbol"] for s in v2_data["stocks"]]
    print(f"Stocks to compare: {len(symbols)}")

    # Step 3: Run v3 scoring
    print("\nRunning v3 scoring engine...")
    v3_scores = run_v3_scoring(symbols)

    # Step 4: Fetch live prices
    print("\nFetching live prices from yfinance...")
    live_prices = fetch_live_prices(symbols)

    # Step 5: Compare
    print("\nComparing v2 vs v3...")
    summary = compare_v2_v3(v2_data, v3_scores, live_prices)

    # Step 6: Save and display
    save_comparison(summary, date_str)
    print_comparison_table(summary)


if __name__ == "__main__":
    main()
