# Daily Regime-Switching Research — Topic Rotation

The daily watchdog picks one of these topics per day (deterministic by date hash so the rotation is reproducible). After ~30 days we cycle.

| # | Topic | Why it matters |
|---|---|---|
| 1 | Recent arxiv papers (last 30 days) on regime-switching trading | Track frontier |
| 2 | hmmlearn vs pomegranate vs hmmkit Python libraries | Phase 2.1 implementation choice |
| 3 | Bayesian Online Change-Point Detection (BOCPD) — implementations + tuning | Alternative to HMM |
| 4 | Indian VIX (`India VIX`) regime behaviour — recent studies | Detector feature engineering |
| 5 | Bull/bear regime persistence in NSE — empirical studies 2020-2026 | Sample-size for BEAR engine |
| 6 | FII/DII as regime leading indicator — recent papers | Detector feature engineering |
| 7 | Walk-forward Combinatorial Purged CV (CPCV) — open-source implementations | Phase 2.2 validation |
| 8 | Look-ahead bias detection tools in time-series ML | Audit `_load_csv` bug |
| 9 | Kaufman Efficiency Ratio — intraday regime confirm | Phase 2.1 sub-regime |
| 10 | Bank-Nifty/Nifty ratio as regime tell — Indian-specific | Detector enhancement |
| 11 | Sector rotation as regime signal — Indian sectors | Feature engineering |
| 12 | Options skew / PCR as regime indicator | Phase 2.4 prerequisite |
| 13 | Multi-resolution regime detection (daily + intraday) | Architecture pattern |
| 14 | Renaissance Medallion 2025-2026 disclosures | Industry intelligence |
| 15 | Two Sigma machine learning regime modeling updates | Industry intelligence |
| 16 | AQR factor timing — newest publications | Industry intelligence |
| 17 | Indian quant fund disclosures (True Beacon, Dolat, Quant MF) | Local industry |
| 18 | F&O expiry day regime effects — recent research | Sub-regime feature |
| 19 | Budget day Indian market behaviour — historical | Event flag feature |
| 20 | RBI policy day market reaction patterns | Event flag feature |
| 21 | Indian election cycle regime data | Event flag feature |
| 22 | Order flow imbalance as regime indicator | Microstructure feature |
| 23 | Volume profile regime classification | Microstructure feature |
| 24 | Statistical jump models (Nystrup et al 2024 follow-ups) | Alternative to HMM |
| 25 | Probability of Backtest Overfitting (PBO) — implementations | Phase 2.2 validation |
| 26 | Deflated Sharpe Ratio — references + libraries | Phase 2.2 validation |
| 27 | LightGBM regime-aware tutorials + GitHub repos | Phase 2.2 reference code |
| 28 | Hidden Markov Model online refit strategies | Detector design |
| 29 | Soft-mixture vs hard-switch routing — empirical comparisons | Phase 4 trigger condition |
| 30 | Position handoff patterns in multi-strategy funds | Phase 4 architecture |

---

## How a topic gets picked

The script `scripts/regime-switching-daily-research.py` uses:

```python
topic_index = (date.today().toordinal()) % NUM_TOPICS
```

This means the rotation is purely date-driven — you can predict tomorrow's topic. The 30-topic cycle takes ~30 days. After cycling, the same topic is revisited fresh, and we compare with the prior coverage to track how the field has evolved.

## How comparison happens

Every daily file has the same structure (`# Topic`, `## Key findings`, `## Sources`, `## Comparison notes`). When the same topic comes up in a future cycle, the agent reads the prior file and notes what's NEW.

Files live in `docs/research/regime-switching-daily/YYYY-MM-DD.md` so a `ls -la` gives the chronological sequence at a glance.

## How to add a new topic

Edit this file. Insert the topic in the table. Update `NUM_TOPICS` in the script. The next cycle will include it.

## How to skip a day

If the watchdog runs but the day's topic is irrelevant or already covered well, the agent should write a 3-line file noting "skipped — already well-covered, see {prior_file}". Empty days are still useful as a record.
