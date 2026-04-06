#!/usr/bin/env python3
"""
TradePilot Intraday Validation Capture
Captures AI predictions every 2 hours during market hours.
Compares each snapshot with the previous one to track real-time accuracy.

Market Hours: 9:15 AM - 3:30 PM IST
Captures at: 09:30, 11:30, 13:30, 15:30

Usage:
    python3 scripts/intraday-capture.py                # Single capture now
    python3 scripts/intraday-capture.py --daemon        # Run all day (captures every 2h)
    python3 scripts/intraday-capture.py --compare       # Compare latest with previous
    python3 scripts/intraday-capture.py --day-summary   # End-of-day summary
    python3 scripts/intraday-capture.py --report        # Weekly report with intraday data
"""

import json
import csv
import os
import sys
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# --- Config ---
PROJECT_ROOT = Path(__file__).parent.parent
WEEK_DIR = PROJECT_ROOT / "docs" / "validation" / "week-2026-04-07"
API_URL = "http://localhost:5050/api/scores"
SCREENSHOT_URL = "http://localhost:5050"

# Market hours IST
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MIN = 30

# Capture schedule (hour, minute) IST
CAPTURE_TIMES = [
    (9, 30),    # Just after open
    (11, 30),   # Mid-morning
    (13, 30),   # Post-lunch
    (15, 30),   # Market close
]


def get_day_dir(date=None):
    """Get or create today's intraday directory."""
    if date is None:
        date = datetime.now()
    date_str = date.strftime("%Y-%m-%d")
    day_dir = WEEK_DIR / "daily" / date_str
    day_dir.mkdir(parents=True, exist_ok=True)
    return day_dir, date_str


def fetch_scores():
    """Fetch current AI scores from TradePilot API."""
    import urllib.request
    try:
        req = urllib.request.Request(API_URL)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        return sorted(data, key=lambda s: s.get("score", 0), reverse=True)
    except Exception as e:
        print(f"ERROR: Could not fetch from {API_URL}: {e}")
        return None


def capture_snapshot():
    """Capture a single intraday snapshot."""
    now = datetime.now()
    day_dir, date_str = get_day_dir(now)
    time_str = now.strftime("%H%M")
    time_label = now.strftime("%H:%M")

    stocks = fetch_scores()
    if not stocks:
        return None

    buy = [s for s in stocks if s.get("direction") == "BUY"]
    hold = [s for s in stocks if s.get("direction") == "HOLD"]
    avoid = [s for s in stocks if s.get("direction") == "AVOID"]

    snapshot = {
        "date": date_str,
        "time": time_label,
        "captured_at": now.isoformat(),
        "snapshot_id": f"{date_str}_{time_str}",
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

    # Save JSON
    json_path = day_dir / f"{time_str}_scores.json"
    with open(json_path, "w") as f:
        json.dump(snapshot, f, indent=2)

    # Save CSV
    csv_path = day_dir / f"{time_str}_scores.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "price", "score", "direction", "change_pct",
                         "rsi", "trend", "macd", "volatility"])
        for s in stocks:
            writer.writerow([
                s.get("symbol"), s.get("price"), s.get("score"),
                s.get("direction"), s.get("change"), s.get("rsi"),
                s.get("trend"), s.get("macd"), s.get("volatility"),
            ])

    print(f"[{time_label}] Captured {len(stocks)} stocks -> {day_dir.name}/{time_str}_scores.json")
    print(f"  BUY: {len(buy)}  HOLD: {len(hold)}  AVOID: {len(avoid)}")

    return snapshot


def find_previous_snapshot(day_dir, current_time_str):
    """Find the most recent snapshot before current time."""
    snapshots = sorted(day_dir.glob("????_scores.json"))
    prev = None
    for s in snapshots:
        t = s.stem.replace("_scores", "")
        if t < current_time_str:
            prev = s
    return prev


def compare_snapshots(current, previous_path):
    """Compare two intraday snapshots."""
    with open(previous_path) as f:
        prev = json.load(f)

    prev_stocks = {s["symbol"]: s for s in prev["stocks"]}
    curr_stocks = {s["symbol"]: s for s in current["stocks"]}

    results = []
    signal_changes = []
    correct = 0
    total = 0

    for symbol in prev_stocks:
        if symbol not in curr_stocks:
            continue
        p = prev_stocks[symbol]
        c = curr_stocks[symbol]

        prev_price = p["price"]
        curr_price = c["price"]
        if prev_price == 0:
            continue

        change_pct = round(((curr_price - prev_price) / prev_price) * 100, 3)
        prev_dir = p.get("direction", "?")
        curr_dir = c.get("direction", "?")

        # Did signal change?
        if prev_dir != curr_dir:
            signal_changes.append({
                "symbol": symbol,
                "from": prev_dir,
                "to": curr_dir,
                "price_change": change_pct,
            })

        # Score the previous prediction
        if prev_dir == "BUY":
            is_correct = change_pct > 0
        elif prev_dir == "HOLD":
            is_correct = -1.5 <= change_pct <= 2
        elif prev_dir == "AVOID":
            is_correct = change_pct < 0.5
        else:
            is_correct = None

        if is_correct is not None:
            total += 1
            if is_correct:
                correct += 1

        results.append({
            "symbol": symbol,
            "prev_dir": prev_dir,
            "curr_dir": curr_dir,
            "prev_score": p["score"],
            "curr_score": c["score"],
            "prev_price": prev_price,
            "curr_price": curr_price,
            "change_pct": change_pct,
            "correct": is_correct,
            "signal_changed": prev_dir != curr_dir,
        })

    results.sort(key=lambda r: r["prev_score"], reverse=True)
    accuracy = round((correct / total) * 100, 1) if total > 0 else 0

    return {
        "from_time": prev["time"],
        "to_time": current["time"],
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "signal_changes": signal_changes,
        "results": results,
    }


def compare_latest():
    """Compare the latest snapshot with the previous one."""
    day_dir, date_str = get_day_dir()
    snapshots = sorted(day_dir.glob("????_scores.json"))

    if len(snapshots) < 2:
        print("Need at least 2 snapshots to compare. Run capture first.")
        return

    with open(snapshots[-1]) as f:
        current = json.load(f)

    comparison = compare_snapshots(current, snapshots[-2])
    save_comparison(day_dir, current, comparison)
    print_comparison(comparison)


def save_comparison(day_dir, current, comparison):
    """Save comparison results."""
    time_str = current["time"].replace(":", "")
    comp_path = day_dir / f"{time_str}_vs_{comparison['from_time'].replace(':', '')}.json"
    with open(comp_path, "w") as f:
        json.dump(comparison, f, indent=2)

    # CSV for easy reading
    csv_path = day_dir / f"{time_str}_comparison.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "prev_signal", "curr_signal", "prev_score", "curr_score",
                         "prev_price", "curr_price", "change_pct", "correct", "signal_changed"])
        for r in comparison["results"]:
            writer.writerow([
                r["symbol"], r["prev_dir"], r["curr_dir"], r["prev_score"], r["curr_score"],
                r["prev_price"], r["curr_price"], r["change_pct"],
                "YES" if r["correct"] else "NO" if r["correct"] is not None else "N/A",
                "CHANGED" if r["signal_changed"] else "",
            ])


def print_comparison(comp):
    """Print comparison summary."""
    print(f"\n{'='*55}")
    print(f"  {comp['from_time']} -> {comp['to_time']}  |  Accuracy: {comp['accuracy']}% ({comp['correct']}/{comp['total']})")
    print(f"{'='*55}")

    if comp["signal_changes"]:
        print(f"\n  Signal Changes ({len(comp['signal_changes'])}):")
        for sc in comp["signal_changes"]:
            arrow = "UP" if sc["price_change"] > 0 else "DOWN"
            print(f"    {sc['symbol']}: {sc['from']} -> {sc['to']}  ({sc['price_change']:+.2f}% {arrow})")

    wrong = [r for r in comp["results"] if r["correct"] is False]
    if wrong:
        print(f"\n  Wrong Calls ({len(wrong)}):")
        for r in sorted(wrong, key=lambda x: abs(x["change_pct"]), reverse=True)[:5]:
            print(f"    {r['symbol']}: said {r['prev_dir']}, moved {r['change_pct']:+.3f}%")

    movers = sorted(comp["results"], key=lambda x: abs(x["change_pct"]), reverse=True)[:5]
    print(f"\n  Biggest Movers:")
    for m in movers:
        tag = "OK" if m["correct"] else "MISS"
        print(f"    {m['symbol']}: {m['change_pct']:+.3f}% (signal: {m['prev_dir']}) [{tag}]")


def generate_day_summary():
    """Generate end-of-day summary from all intraday snapshots."""
    day_dir, date_str = get_day_dir()
    snapshots = sorted(day_dir.glob("????_scores.json"))

    if not snapshots:
        print("No snapshots found for today.")
        return

    # Load all snapshots
    all_data = []
    for sp in snapshots:
        with open(sp) as f:
            all_data.append(json.load(f))

    # Compare first vs last (open vs close)
    first = all_data[0]
    last = all_data[-1]

    first_stocks = {s["symbol"]: s for s in first["stocks"]}
    last_stocks = {s["symbol"]: s for s in last["stocks"]}

    lines = []
    lines.append(f"# Intraday Summary: {date_str}\n")
    lines.append(f"**Snapshots:** {len(all_data)} (captured at {', '.join(d['time'] for d in all_data)})")
    lines.append(f"**Model:** XGBoost + LightGBM Ensemble v2\n")

    # Signal distribution over the day
    lines.append("## Signal Distribution Through the Day\n")
    lines.append("| Time | BUY | HOLD | AVOID | Highest Score |")
    lines.append("|------|-----|------|-------|---------------|")
    for d in all_data:
        s = d["summary"]
        lines.append(f"| {d['time']} | {s['buy']} | {s['hold']} | {s['avoid']} | {s['highest_score']} |")
    lines.append("")

    # Open vs Close comparison
    lines.append("## Open vs Close (Full Day Accuracy)\n")
    full_day = compare_snapshots(last, snapshots[0])
    lines.append(f"**Accuracy:** {full_day['accuracy']}% ({full_day['correct']}/{full_day['total']})\n")

    if full_day["signal_changes"]:
        lines.append(f"**Signal Changes:** {len(full_day['signal_changes'])}\n")
        lines.append("| Stock | Open Signal | Close Signal | Day Change |")
        lines.append("|-------|------------|-------------|------------|")
        for sc in full_day["signal_changes"]:
            lines.append(f"| {sc['symbol']} | {sc['from']} | {sc['to']} | {sc['price_change']:+.2f}% |")
        lines.append("")

    # Per-interval comparisons
    lines.append("## Interval Accuracy\n")
    lines.append("| Interval | Accuracy | Correct | Total | Signal Changes |")
    lines.append("|----------|----------|---------|-------|----------------|")

    for i in range(1, len(all_data)):
        comp = compare_snapshots(all_data[i], snapshots[i - 1])
        lines.append(f"| {comp['from_time']} -> {comp['to_time']} | "
                     f"{comp['accuracy']}% | {comp['correct']} | {comp['total']} | "
                     f"{len(comp['signal_changes'])} |")
    lines.append("")

    # Stock-level tracking (price journey through the day)
    lines.append("## Stock Price Journey\n")
    times = [d["time"] for d in all_data]
    header = "| Stock | Signal | " + " | ".join(times) + " | Day Change |"
    sep = "|-------|--------|" + "|".join(["-------"] * len(times)) + "|------------|"
    lines.append(header)
    lines.append(sep)

    for symbol in sorted(first_stocks.keys()):
        if symbol not in last_stocks:
            continue
        prices = []
        for d in all_data:
            stock = next((s for s in d["stocks"] if s["symbol"] == symbol), None)
            prices.append(f"{stock['price']:.2f}" if stock else "-")

        open_p = first_stocks[symbol]["price"]
        close_p = last_stocks[symbol]["price"]
        day_change = ((close_p - open_p) / open_p * 100) if open_p else 0
        signal = first_stocks[symbol].get("direction", "?")

        lines.append(f"| {symbol} | {signal} | {' | '.join(prices)} | {day_change:+.2f}% |")
    lines.append("")

    summary_path = day_dir / "day_summary.md"
    with open(summary_path, "w") as f:
        f.write("\n".join(lines))

    print(f"\nDay summary saved: {summary_path}")
    print(f"  Snapshots: {len(all_data)}")
    print(f"  Full-day accuracy: {full_day['accuracy']}%")
    print(f"  Signal changes: {len(full_day['signal_changes'])}")

    return summary_path


def daemon_mode():
    """Run captures throughout the day at scheduled times."""
    print("TradePilot Intraday Daemon")
    print(f"Schedule: {', '.join(f'{h:02d}:{m:02d}' for h, m in CAPTURE_TIMES)}")
    print("Waiting for next capture window...\n")

    captured_today = set()

    while True:
        now = datetime.now()
        current_minutes = now.hour * 60 + now.minute

        # Check if market day (Mon-Fri)
        if now.weekday() >= 5:
            print(f"[{now.strftime('%H:%M')}] Weekend. Sleeping 1h...")
            time.sleep(3600)
            continue

        # Check each capture time
        for h, m in CAPTURE_TIMES:
            target_minutes = h * 60 + m
            key = f"{now.strftime('%Y-%m-%d')}_{h:02d}{m:02d}"

            # Capture if within 5-min window and not already captured
            if 0 <= (current_minutes - target_minutes) <= 5 and key not in captured_today:
                print(f"\n[{now.strftime('%H:%M')}] Capture window: {h:02d}:{m:02d}")

                # Ensure TradePilot is running
                snapshot = capture_snapshot()
                if snapshot:
                    captured_today.add(key)

                    # Auto-compare with previous if we have one
                    day_dir, _ = get_day_dir()
                    snapshots = sorted(day_dir.glob("????_scores.json"))
                    if len(snapshots) >= 2:
                        comp = compare_snapshots(snapshot, snapshots[-2])
                        save_comparison(day_dir, snapshot, comp)
                        print_comparison(comp)

                    # Generate day summary at market close
                    if h == 15:
                        print("\nMarket close — generating day summary...")
                        generate_day_summary()

        # Reset captures at midnight
        if now.hour == 0 and now.minute < 2:
            captured_today.clear()

        # Sleep 60 seconds before next check
        time.sleep(60)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--capture"

    if mode == "--daemon":
        daemon_mode()
    elif mode == "--compare":
        compare_latest()
    elif mode == "--day-summary":
        generate_day_summary()
    elif mode == "--report":
        # Reuse weekly report from daily-capture.py
        print("Use: python3 scripts/daily-capture.py --report")
    else:
        capture_snapshot()


if __name__ == "__main__":
    main()
