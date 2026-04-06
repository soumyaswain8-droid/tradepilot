# TradePilot Weekly Validation Study
**Week: Apr 7-11, 2026**

## Purpose
Track AI predictions every 2 hours during market hours.
Compare each snapshot with previous to measure real-time accuracy.
Generate a weekly PDF report at the end.

## Option A: Automated Daemon (recommended)

```bash
# Start TradePilot + daemon in one go
cd ~/Documents/tinker/projects/tradepilot
python3 prototype/app.py &
python3 scripts/intraday-capture.py --daemon
```

Daemon auto-captures at: **09:30, 11:30, 13:30, 15:30**
Auto-compares with previous snapshot. Generates day summary at 15:30.

## Option B: Manual Captures

```bash
# Single capture anytime
python3 scripts/intraday-capture.py

# Capture + compare with previous snapshot
python3 scripts/intraday-capture.py --compare

# End-of-day summary
python3 scripts/intraday-capture.py --day-summary
```

## End of Week

```bash
python3 scripts/daily-capture.py --report
# Generates: reports/weekly_validation_report.md -> PDF
```

## Folder Structure
```
week-2026-04-07/
  daily/
    2026-04-06_baseline.json        # Sunday baseline (Friday close)
    2026-04-06_scores.csv           # Daily flat CSV
    2026-04-06_dashboard_*.png      # Screenshots
    2026-04-07/                     # Monday intraday folder
      0930_scores.json              # 09:30 snapshot
      0930_scores.csv
      1130_scores.json              # 11:30 snapshot
      1130_scores.csv
      1130_vs_0930.json             # 11:30 vs 09:30 comparison
      1130_comparison.csv
      1330_scores.json              # 13:30 snapshot
      1330_vs_1130.json             # interval comparison
      1530_scores.json              # 15:30 (market close)
      1530_vs_1330.json
      day_summary.md                # Auto-generated at close
    2026-04-08/                     # Tuesday intraday folder
      ...
  screenshots/
  reports/
    weekly_validation_report.md
    weekly_validation_report.pdf
```

## What Each Snapshot Captures
- All 49 NIFTY 50 stocks: price, AI score, signal (BUY/HOLD/AVOID)
- Technical indicators: RSI, trend, MACD, volatility
- Targets and stop-loss levels

## What Each Comparison Shows
- Accuracy: % of correct signals since last snapshot
- Signal changes: which stocks flipped BUY->HOLD, HOLD->AVOID, etc.
- Biggest movers: stocks that moved the most
- Wrong calls: where the AI got it wrong

## Validation Scoring (per 2-hour interval)
- **BUY = Correct** if stock went up (> 0%)
- **HOLD = Correct** if stock stayed flat (-1.5% to +2%)
- **AVOID = Correct** if stock didn't rise (< +0.5%)

## What We're Measuring
1. **Intraday accuracy** -- does the AI hold up hour-by-hour?
2. **Signal consistency** -- does it flip-flop during the day?
3. **Open vs Close accuracy** -- full-day prediction quality
4. **Score stability** -- do scores drift or stay firm?
5. **Weekly trend** -- is accuracy improving or degrading?
