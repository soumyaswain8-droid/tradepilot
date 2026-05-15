# Drift Watcher — Live IC & Regime Monitor

**Tier 3 (Background). Veto: NO — pages Sarathi.**

## Mission
Continuous live IC monitoring. Detect regime shifts before they damage P&L. Page Sarathi on significance.

## Cadence
- **Continuous during market hours** (09:15–15:30 IST)
- **Sleeps weekends + non-market hours**

## Inputs
- Live position outcomes as trades close
- Last 5-day rolling IC computed from closed trades
- Feature distribution snapshots vs training-time distribution

## Outputs
- Live status file `docs/team/status/drift-watcher.json` updated every 5 min:
  ```json
  {
    "ts":"...",
    "rolling_5d_ic": 0.018,
    "ic_trend":"flat|rising|falling",
    "feature_drift_pct": 0.05,
    "adwin_state":"OK|WARNING|CHANGE",
    "page_sent": null
  }
  ```
- On significance, write to `docs/team/activity/YYYY-MM-DD.jsonl` and call Sarathi.

## Algorithms
- **ADWIN (Adaptive Windowing)** — River library. Detects distribution change in residual stream.
- **Page-Hinkley test** — detects abrupt shift in mean residual.
- **Feature drift** — Kolmogorov-Smirnov test on current 24h feature distribution vs training distribution; flag if KS p-value < 0.01 on 3+ features.

## Paging Triggers
- Rolling 5-day IC drops below 0.02 → WARN
- Rolling 5-day IC drops below 0.01 OR turns negative → PAGE Sarathi
- ADWIN signals CHANGE → PAGE Sarathi
- Feature drift on > 5 features simultaneously → PAGE Sarathi

## KPI
- Drift events detected within 1 hour of statistical significance
- 0 missed regime shifts (validated by post-hoc analysis)
- < 1 false alarm per month

## Implementation
**Script-based**, no LLM. Background process started at market open by `launch-market.sh`. Uses River library for ADWIN + Page-Hinkley. Polls every 60s. Process tree clean per CDE-005.
