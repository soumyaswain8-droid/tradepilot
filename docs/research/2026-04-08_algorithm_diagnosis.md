# TradePilot Algorithm Diagnosis & Research — 2026-04-08

## Problem Statement
Out of Nifty 50 stocks, model generates only 2 BUY signals. 15 stocks were up >1% today.
Model missed 13 profitable trades (24.1% combined upside left on the table).

## Root Causes

### 1. Wrong Prediction Target
- Model predicts: 5-day forward return > 0.5% (binary classification)
- Need: intraday/next-day momentum ranking
- File: `trading_engine_v3.py:213-226` — `forward_days = 5`, `label = fwd_ret > 0.005`

### 2. Score Distribution Broken
- Range: 0.5 to 69 (mean: 17, median: 12.6)
- BUY threshold: v2 >= 55, v3 >= 50-60 (regime dependent)
- Result: 96% AVOID, 2 BUY signals
- File: `app.py:148` (v2 thresholds), `trading_engine_v3.py:656` (v3 thresholds)

### 3. Features are Mean-Reversion, Not Momentum
- Top features: ATR 13.25%, MACD 7.56%, pct_from_low 6.21%
- Missing: VWAP, ORB, volume surge, FII/DII flow, options OI
- File: `trading_engine_v3.py:111-128` (V3_FEATURE_COLS)

### 4. Boost Thresholds Too Stringent
- rs_5d > 3% for +8 boost (almost nothing qualifies)
- ret_1d > 3% with vol_ratio > 1.5 for +6 boost
- File: `trading_engine_v3.py:611-643`

### 5. Training Precision Poor
- 44.79% precision, 56.46% recall on training set
- Model assigns near-zero probability to most stocks

## Today's Evidence (April 8, 2026)

| Stock | Actual Change | Model Signal | Score | Verdict |
|-------|--------------|-------------|-------|---------|
| TITAN | +3.97% | BUY | 67.3 | Correct |
| SHRIRAMFIN | +3.20% | AVOID | 6.5 | MISSED |
| EICHERMOT | +2.75% | AVOID | 17.6 | MISSED |
| INDUSINDBK | +2.21% | AVOID | 8.7 | MISSED |
| MARUTI | +2.14% | AVOID | 19.4 | MISSED |
| ADANIENT | +2.06% | AVOID | 26.0 | MISSED |
| M&M | +1.87% | AVOID | 22.2 | MISSED |
| SBILIFE | +1.79% | HOLD | 42.7 | MISSED |
| BAJFINANCE | +1.67% | AVOID | 10.9 | MISSED |
| ONGC | +1.44% | BUY | 58.7 | Correct |

## Recommended v4 Architecture

### Layer 1: Morning Data (9:00 AM)
- Pre-market session data (nsefin library)
- FII/DII net flow (last 3 days, nsepython)
- Options OI for Nifty 50 F&O stocks

### Layer 2: ORB Scan (9:30 AM)
- Opening Range Breakout (first 15-min high/low breach)
- Gap classification (magnitude + volume)
- VWAP position (above/below, distance)
- Relative strength rank (all 50 stocks sorted)

### Layer 3: Composite Scoring
```
score = 0.25 * ml_probability
      + 0.20 * vwap_position_score
      + 0.15 * orb_breakout_score
      + 0.15 * relative_strength_rank
      + 0.10 * oi_buildup_signal
      + 0.10 * fii_flow_direction
      + 0.05 * gap_momentum_score
```

### Layer 4: Output
- Rank all 50 by composite score
- Top 5-10 = STRONG BUY (Kelly-sized positions)
- Next 10 = BUY (smaller positions)
- Middle 20 = HOLD
- Bottom 10 = AVOID

## Action Items (Priority Order)

1. Relative strength ranking (2 hrs) — always flags top 10
2. ORB breakout detection (4 hrs) — 60-89% NSE win rate
3. Switch to regression (3 hrs) — predict magnitude not class
4. Add VWAP (3 hrs) — #1 institutional indicator
5. FII/DII flow (2 hrs) — leading indicator
6. Options OI buildup (4 hrs) — Sensibull's edge
7. Composite scoring (3 hrs) — multi-signal robustness
8. Kelly position sizing (2 hrs) — confidence-based allocation

## Key Libraries Needed
- nsepython — options chain, FII/DII data, pre-open data
- nsefin — pre-market info, option chain with Greeks
- nsetools — real-time quotes with VWAP field
- yfinance — intraday candles for VWAP/ORB computation

## References
- Zerodha Streak: rule-based, 80+ technical indicators, NO ML
- Sensibull: options flow data (OI analysis, IV, PCR, max pain)
- Smallcase: factor-based ranking (momentum, value, quality)
- None of these use ML prediction as primary method
