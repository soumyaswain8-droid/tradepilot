# TradePilot v2 vs v3 Validation Plan

**Week:** 2026-04-07 to 2026-04-11
**Objective:** Determine whether v3 (regime-aware) engine outperforms v2 in live market conditions

---

## What We Are Comparing

| Dimension | v2 (Current Production) | v3 (Candidate) |
|-----------|------------------------|----------------|
| Model | XGBoost + LightGBM ensemble | Same ensemble + regime-aware thresholds |
| Scoring | Fixed thresholds (BUY/HOLD/AVOID) | Dynamic thresholds by market regime (BULL/BEAR/SIDEWAYS) |
| Features | Technical indicators only | Technical + relative strength vs NIFTY + sector momentum |
| Key addition | -- | Relative strength (RS) 5-day and 20-day vs market |
| Target | High accuracy overall | 80% profitable trade ratio, precision-optimized |

## Data Collection

### Intraday Capture (v2) -- Already Running
- Daemon: `scripts/intraday-capture.py --daemon`
- Schedule: 09:30, 11:30, 13:30, 15:30 IST
- Output: `docs/validation/week-2026-04-07/daily/{date}/{time}_scores.json`
- Do NOT restart or modify the daemon during validation week

### Daily v2 vs v3 Comparison
- Script: `scripts/v3-daily-compare.py`
- Run once daily after 15:30 IST (market close): `python3 scripts/v3-daily-compare.py`
- For specific snapshot: `python3 scripts/v3-daily-compare.py --snapshot 1530`
- For past date: `python3 scripts/v3-daily-compare.py --date 2026-04-08`
- Output: `docs/validation/week-2026-04-07/daily/{date}/v2_vs_v3_comparison.json`

### Daily Checklist
1. Verify daemon captured all 4 snapshots (check daily dir for 0930/1130/1330/1530 files)
2. Run `python3 scripts/v3-daily-compare.py` after market close
3. Note market regime detected by v3 (BULL/BEAR/SIDEWAYS)
4. Log any anomalies (API down, missing stocks, stale data)

## Metrics to Track

### Primary Metrics (Daily)

| Metric | Definition | Target |
|--------|-----------|--------|
| Overall Accuracy | % of correct direction calls vs actual movement | v3 > v2 |
| BUY Precision | % of BUY calls that were actually profitable | > 80% (v3 target) |
| HOLD Precision | % of HOLD calls where stock stayed within -1.5% to +2% | > 70% |
| AVOID Precision | % of AVOID calls where stock moved < +0.5% | > 75% |
| Agreement Rate | % of stocks where v2 and v3 give same signal | Track (not a target) |

### Secondary Metrics (Weekly Aggregate)

| Metric | Definition | Why It Matters |
|--------|-----------|----------------|
| RS Correlation | Correlation between v3 relative strength and actual 1-day/5-day returns | Validates RS feature adds value |
| Regime Accuracy | Did regime detection match actual NIFTY movement? | Foundation of v3's advantage |
| Signal Stability | How often does v3 flip a signal within the same day (intraday)? | Fewer flips = more tradeable |
| Missed Winners | Stocks that moved >3% up but were AVOID | Opportunity cost |
| False BUYs | Stocks rated BUY that dropped >2% | Risk metric |
| Sharpe Proxy | Mean return of BUY picks / std dev of BUY pick returns | Risk-adjusted quality |

### Disagreement Analysis (Daily)

When v2 and v3 disagree, track:
- Which engine was correct more often on disagreements
- Are disagreements clustered by sector or regime?
- Does v3's RS data explain the disagreement outcome?

## End-of-Week Analysis Plan

### Data Required
- 5 daily comparison JSONs (Mon-Fri)
- 20 intraday snapshots (4 per day)
- NIFTY 50 daily data for regime validation

### Analysis Steps

1. **Aggregate accuracy** -- Pool all 5 days, compute overall v2 vs v3 accuracy
2. **Regime breakdown** -- Split results by detected regime (BULL/BEAR/SIDEWAYS)
3. **BUY precision deep-dive** -- Of all v3 BUY calls across the week:
   - Win rate (% that were profitable next day)
   - Average return of BUY picks vs average return of AVOID picks
   - Best and worst BUY calls
4. **RS feature validation** -- Scatter plot: RS_5d vs actual_1d_return
   - If correlation > 0.3, RS adds predictive value
   - If no correlation, v3's RS boost may be noise
5. **Disagreement P&L** -- Simulate: if you followed v3 on disagreements vs v2, what was the P&L?
6. **Intraday stability** -- Count signal flips per stock across 4 daily snapshots (v2 only since v3 runs once daily)
7. **Decision** -- Based on above, recommend: ship v3 / keep v2 / needs more data

### Output
- `docs/validation/week-2026-04-07/WEEKLY_REPORT.md` -- Full analysis
- `docs/validation/week-2026-04-07/WEEKLY_REPORT.pdf` -- Rendered via dp content render

## File Structure

```
docs/validation/week-2026-04-07/
  VALIDATION_PLAN.md              <-- this file
  VALIDATION_TRACKER.md           <-- daily log
  WEEKLY_REPORT.md                <-- end-of-week analysis (Friday)
  daily/
    2026-04-06/                   <-- Sunday baseline
      1634_scores.json
    2026-04-07/                   <-- Monday
      1158_scores.json            <-- v2 intraday capture
      v2_vs_v3_comparison.json    <-- daily comparison output
    2026-04-08/                   <-- Tuesday (upcoming)
    ...
    2026-04-11/                   <-- Friday
```

## Quick Reference

```bash
# Check daemon is running
ps aux | grep intraday-capture

# Run daily comparison (after market close)
python3 scripts/v3-daily-compare.py

# Compare specific snapshot
python3 scripts/v3-daily-compare.py --snapshot 1530

# Compare past date
python3 scripts/v3-daily-compare.py --date 2026-04-08

# Check today's captures
ls docs/validation/week-2026-04-07/daily/$(date +%Y-%m-%d)/
```
