#!/usr/bin/env python3
"""
TradePilot Daily Validation Capture
Run this daily after market close (3:30 PM IST) to capture AI predictions.

Usage:
    python3 scripts/daily-capture.py              # Capture today's data
    python3 scripts/daily-capture.py --compare     # Capture + compare with yesterday
    python3 scripts/daily-capture.py --report       # Generate weekly PDF report
"""

import json
import csv
import os
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# --- Config ---
PROJECT_ROOT = Path(__file__).parent.parent
WEEK_DIR = PROJECT_ROOT / "docs" / "validation" / "week-2026-04-07"
DAILY_DIR = WEEK_DIR / "daily"
SCREENSHOTS_DIR = WEEK_DIR / "screenshots"
REPORTS_DIR = WEEK_DIR / "reports"
TRADEPILOT_URL = "http://localhost:5050"
API_URL = f"{TRADEPILOT_URL}/api/scores"

# Ensure dirs exist
for d in [DAILY_DIR, SCREENSHOTS_DIR, REPORTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def fetch_scores():
    """Fetch current AI scores from TradePilot API."""
    import urllib.request
    try:
        req = urllib.request.Request(API_URL)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return sorted(data, key=lambda s: s.get("score", 0), reverse=True)
    except Exception as e:
        print(f"ERROR: Could not fetch scores from {API_URL}")
        print(f"  Make sure TradePilot is running: python3 prototype/app.py")
        print(f"  Error: {e}")
        sys.exit(1)


def save_daily_data(today, stocks):
    """Save today's stock data as JSON + CSV."""
    date_str = today.strftime("%Y-%m-%d")

    buy = [s for s in stocks if s.get("direction") == "BUY"]
    hold = [s for s in stocks if s.get("direction") == "HOLD"]
    avoid = [s for s in stocks if s.get("direction") == "AVOID"]

    # JSON
    payload = {
        "date": date_str,
        "captured_at": datetime.now().isoformat(),
        "model": "XGBoost + LightGBM Ensemble v2",
        "summary": {
            "total": len(stocks),
            "buy": len(buy),
            "hold": len(hold),
            "avoid": len(avoid),
            "highest_score": stocks[0]["score"] if stocks else 0,
            "lowest_score": stocks[-1]["score"] if stocks else 0,
        },
        "stocks": stocks,
    }
    json_path = DAILY_DIR / f"{date_str}_scores.json"
    with open(json_path, "w") as f:
        json.dump(payload, f, indent=2)

    # CSV (flat, easy to diff)
    csv_path = DAILY_DIR / f"{date_str}_scores.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "price", "score", "direction", "change_pct",
                         "rsi", "trend", "macd", "volatility", "target", "stopLoss"])
        for s in stocks:
            writer.writerow([
                s.get("symbol"), s.get("price"), s.get("score"), s.get("direction"),
                s.get("change"), s.get("rsi"), s.get("trend"), s.get("macd"),
                s.get("volatility"), s.get("target"), s.get("stopLoss"),
            ])

    print(f"Saved: {json_path.name}, {csv_path.name}")
    print(f"  BUY: {len(buy)}  HOLD: {len(hold)}  AVOID: {len(avoid)}  Total: {len(stocks)}")
    return payload


def compare_with_previous(today, today_stocks):
    """Compare today's prices with yesterday's predictions."""
    date_str = today.strftime("%Y-%m-%d")

    # Find most recent previous data file
    prev_file = None
    for i in range(1, 5):  # Look back up to 4 days (weekends)
        prev_date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        candidate = DAILY_DIR / f"{prev_date}_scores.json"
        if candidate.exists():
            prev_file = candidate
            break
        # Also check baseline format
        candidate2 = DAILY_DIR / f"{prev_date}_baseline.json"
        if candidate2.exists():
            prev_file = candidate2
            break

    if not prev_file:
        print("No previous data found to compare with.")
        return None

    with open(prev_file) as f:
        prev_data = json.load(f)

    prev_stocks = {s["symbol"]: s for s in prev_data["stocks"]}
    today_stocks_map = {s["symbol"]: s for s in today_stocks}

    results = []
    correct = 0
    total = 0

    for symbol, prev in prev_stocks.items():
        if symbol not in today_stocks_map:
            continue
        curr = today_stocks_map[symbol]
        prev_price = prev["price"]
        curr_price = curr["price"]
        if prev_price == 0:
            continue

        change_pct = ((curr_price - prev_price) / prev_price) * 100
        direction = prev.get("direction", "UNKNOWN")

        # Scoring rules
        if direction == "BUY":
            is_correct = change_pct > 0
        elif direction == "HOLD":
            is_correct = -1 <= change_pct <= 3
        elif direction == "AVOID":
            is_correct = change_pct < 1
        else:
            is_correct = None

        if is_correct is not None:
            total += 1
            if is_correct:
                correct += 1

        results.append({
            "symbol": symbol,
            "prev_direction": direction,
            "prev_score": prev["score"],
            "prev_price": prev_price,
            "today_price": curr_price,
            "change_pct": round(change_pct, 2),
            "correct": is_correct,
        })

    # Sort by score descending
    results.sort(key=lambda r: r["prev_score"], reverse=True)

    accuracy = round((correct / total) * 100, 1) if total > 0 else 0

    comparison = {
        "baseline_date": prev_data["date"],
        "compare_date": date_str,
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "results": results,
    }

    comp_path = DAILY_DIR / f"{date_str}_comparison.json"
    with open(comp_path, "w") as f:
        json.dump(comparison, f, indent=2)

    # Also save a readable CSV
    csv_path = DAILY_DIR / f"{date_str}_comparison.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "signal", "score", "prev_price", "today_price",
                         "change_pct", "correct"])
        for r in results:
            writer.writerow([
                r["symbol"], r["prev_direction"], r["prev_score"],
                r["prev_price"], r["today_price"], r["change_pct"],
                "YES" if r["correct"] else "NO" if r["correct"] is not None else "N/A"
            ])

    print(f"\nComparison: {prev_data['date']} -> {date_str}")
    print(f"  Accuracy: {accuracy}% ({correct}/{total})")

    # Show biggest wins/misses
    wrong = [r for r in results if r["correct"] is False]
    if wrong:
        print(f"  Wrong calls ({len(wrong)}):")
        for r in sorted(wrong, key=lambda x: abs(x["change_pct"]), reverse=True)[:5]:
            print(f"    {r['symbol']}: {r['prev_direction']} but moved {r['change_pct']:+.2f}%")

    return comparison


def generate_weekly_report():
    """Generate a markdown report summarizing the week's accuracy."""
    # Collect all comparison files
    comparisons = []
    daily_scores = []

    for f in sorted(DAILY_DIR.glob("*_comparison.json")):
        with open(f) as fh:
            comparisons.append(json.load(fh))

    for f in sorted(DAILY_DIR.glob("*_scores.json")):
        with open(f) as fh:
            daily_scores.append(json.load(fh))

    # Also check baseline files
    for f in sorted(DAILY_DIR.glob("*_baseline.json")):
        with open(f) as fh:
            daily_scores.append(json.load(fh))

    daily_scores.sort(key=lambda d: d["date"])

    if not comparisons:
        print("No comparison data yet. Run with --compare for at least 2 days first.")
        return

    # Build report
    lines = []
    lines.append("# TradePilot AI Validation Report")
    lines.append(f"**Week of April 7-11, 2026**\n")
    lines.append(f"**Model:** XGBoost + LightGBM Ensemble v2")
    lines.append(f"**Universe:** NIFTY 50 ({len(daily_scores[0]['stocks']) if daily_scores else 49} stocks)")
    lines.append(f"**Days Tracked:** {len(comparisons)}\n")
    lines.append("---\n")

    # Daily accuracy table
    lines.append("## Daily Accuracy\n")
    lines.append("| Date | Baseline | Accuracy | Correct | Total | BUY | HOLD | AVOID |")
    lines.append("|------|----------|----------|---------|-------|-----|------|-------|")

    total_correct = 0
    total_total = 0
    for comp in comparisons:
        # Find the daily score data for context
        score_data = next((d for d in daily_scores if d["date"] == comp["baseline_date"]), None)
        buy = hold = avoid = "?"
        if score_data:
            s = score_data["summary"]
            buy, hold, avoid = s.get("buy", "?"), s.get("hold", "?"), s.get("avoid", "?")

        lines.append(f"| {comp['compare_date']} | {comp['baseline_date']} | "
                     f"**{comp['accuracy']}%** | {comp['correct']} | {comp['total']} | "
                     f"{buy} | {hold} | {avoid} |")
        total_correct += comp["correct"]
        total_total += comp["total"]

    overall = round((total_correct / total_total) * 100, 1) if total_total > 0 else 0
    lines.append(f"| **OVERALL** | | **{overall}%** | **{total_correct}** | **{total_total}** | | | |\n")

    # Signal consistency tracking
    lines.append("---\n")
    lines.append("## Signal Consistency (Did the AI change its mind?)\n")

    # Track how each stock's signal changed over the week
    all_symbols = set()
    daily_signals = {}
    for ds in daily_scores:
        date = ds["date"]
        daily_signals[date] = {}
        for s in ds["stocks"]:
            sym = s["symbol"]
            all_symbols.add(sym)
            daily_signals[date][sym] = s.get("direction", "?")

    dates = sorted(daily_signals.keys())
    if len(dates) >= 2:
        lines.append(f"| Stock | {' | '.join(dates)} | Consistent? |")
        lines.append(f"|-------|{'|'.join(['-----'] * len(dates))}|------------|")

        for sym in sorted(all_symbols):
            signals = [daily_signals.get(d, {}).get(sym, "-") for d in dates]
            consistent = "YES" if len(set(s for s in signals if s != "-")) <= 1 else "CHANGED"
            lines.append(f"| {sym} | {' | '.join(signals)} | {consistent} |")
        lines.append("")

    # Worst misses
    lines.append("---\n")
    lines.append("## Biggest Misses (Wrong Calls)\n")
    lines.append("| Date | Stock | Signal | Score | Expected | Actual Change |")
    lines.append("|------|-------|--------|-------|----------|---------------|")

    all_wrong = []
    for comp in comparisons:
        for r in comp["results"]:
            if r["correct"] is False:
                all_wrong.append({**r, "date": comp["compare_date"]})

    all_wrong.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    for w in all_wrong[:15]:
        expected = "down" if w["prev_direction"] == "AVOID" else "flat/up"
        lines.append(f"| {w['date']} | {w['symbol']} | {w['prev_direction']} | "
                     f"{w['prev_score']} | {expected} | {w['change_pct']:+.2f}% |")
    lines.append("")

    # Best calls
    lines.append("---\n")
    lines.append("## Best Calls (Most Accurate)\n")
    lines.append("| Date | Stock | Signal | Score | Change |")
    lines.append("|------|-------|--------|-------|--------|")

    all_right = []
    for comp in comparisons:
        for r in comp["results"]:
            if r["correct"] is True:
                all_right.append({**r, "date": comp["compare_date"]})

    # AVOID stocks that dropped the most = best avoid calls
    avoid_right = [r for r in all_right if r["prev_direction"] == "AVOID"]
    avoid_right.sort(key=lambda x: x["change_pct"])
    for r in avoid_right[:10]:
        lines.append(f"| {r['date']} | {r['symbol']} | AVOID | {r['prev_score']} | {r['change_pct']:+.2f}% |")
    lines.append("")

    # Learnings section
    lines.append("---\n")
    lines.append("## Key Learnings\n")
    lines.append("_Auto-filled after week completes_\n")
    lines.append("- Overall accuracy: {}\n".format(f"{overall}%" if overall else "TBD"))
    lines.append("- Model bias: {}\n".format(
        "Overly bearish" if overall < 50 else "Balanced" if overall < 70 else "Strong"))
    lines.append("- Consistency: Check signal changes table above\n")
    lines.append("- Recommendation: _Fill after analysis_\n")

    # Screenshots reference
    lines.append("---\n")
    lines.append("## Daily Screenshots\n")
    for f in sorted(DAILY_DIR.glob("*_dashboard_full.png")):
        date = f.name[:10]
        lines.append(f"- **{date}**: `daily/{f.name}`")
    lines.append("")

    report_path = REPORTS_DIR / "weekly_validation_report.md"
    with open(report_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nReport saved: {report_path}")
    print(f"  Overall accuracy: {overall}% ({total_correct}/{total_total})")
    print(f"  Days tracked: {len(comparisons)}")
    return report_path


def main():
    today = datetime.now()
    mode = sys.argv[1] if len(sys.argv) > 1 else "--capture"

    print(f"TradePilot Daily Capture - {today.strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    if mode == "--report":
        generate_weekly_report()
        return

    # Fetch and save today's scores
    stocks = fetch_scores()
    save_daily_data(today, stocks)

    if mode == "--compare":
        compare_with_previous(today, stocks)

    print(f"\nFiles at: {DAILY_DIR}")
    print("Next: Run with --compare tomorrow after market close")


if __name__ == "__main__":
    main()
