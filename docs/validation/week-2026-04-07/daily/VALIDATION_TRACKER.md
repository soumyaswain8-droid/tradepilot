# TradePilot AI Validation - Apr 6, 2026

**Baseline Date:** Sunday Apr 6 (prices from Friday Apr 4 close)
**Compare Date:** Monday Apr 7 (market close)
**Model:** XGBoost + LightGBM Ensemble v2
**Overall Signal:** Very Bearish (0 BUY / 3 HOLD / 46 AVOID)

---

## HOLD Signals (AI says: price should stay flat or go up slightly)

| # | Stock | Friday Price | Score | RSI | Trend | MACD | Mon Price | Change | Correct? |
|---|-------|-------------|-------|-----|-------|------|-----------|--------|----------|
| 1 | COALINDIA | 449.35 | 43.8 | 51.4 | Sideways | Bearish | ___ | ___% | ___ |
| 2 | TECHM | 1,441.50 | 41.2 | 66.3 | Uptrend | Bullish | ___ | ___% | ___ |
| 3 | RELIANCE | 1,350.50 | 40.7 | 40.9 | Downtrend | Bearish | ___ | ___% | ___ |

**HOLD Accuracy: ___/3**

---

## AVOID Signals - Top 10 (AI says: price should go down or stay weak)

| # | Stock | Friday Price | Score | RSI | Trend | MACD | Mon Price | Change | Correct? |
|---|-------|-------------|-------|-----|-------|------|-----------|--------|----------|
| 1 | ONGC | 287.20 | 39.9 | 67.8 | Strong Uptrend | Bullish | ___ | ___% | ___ |
| 2 | TITAN | 4,097.20 | 39.6 | 47.8 | Uptrend | Bearish | ___ | ___% | ___ |
| 3 | HCLTECH | 1,402.20 | 38.3 | 58.6 | Uptrend | Bullish | ___ | ___% | ___ |
| 4 | HINDALCO | 916.25 | 36.7 | 42.2 | Uptrend | Bearish | ___ | ___% | ___ |
| 5 | DIVISLAB | 5,856.50 | 34.6 | 22.9 | Downtrend | Bearish | ___ | ___% | ___ |
| 6 | HINDUNILVR | 2,065.30 | 33.2 | 37.0 | Downtrend | Bearish | ___ | ___% | ___ |
| 7 | HEROMOTOCO | 5,011.50 | 31.1 | 34.1 | Downtrend | Bearish | ___ | ___% | ___ |
| 8 | NTPC | 359.65 | 30.0 | 35.4 | Downtrend | Bearish | ___ | ___% | ___ |
| 9 | BRITANNIA | 5,442.00 | 28.7 | 28.0 | Downtrend | Bearish | ___ | ___% | ___ |
| 10 | APOLLOHOSP | 7,317.50 | 28.3 | 37.8 | Downtrend | Bearish | ___ | ___% | ___ |

**Top 10 AVOID Accuracy: ___/10**

---

## AVOID Signals - Big Names (banks, IT, heavyweights)

| # | Stock | Friday Price | Score | RSI | Trend | Mon Price | Change | Correct? |
|---|-------|-------------|-------|-----|-------|-----------|--------|----------|
| 1 | BHARTIARTL | 1,789.70 | 28.1 | 47.2 | Downtrend | ___ | ___% | ___ |
| 2 | ITC | 292.85 | 26.1 | 35.2 | Downtrend | ___ | ___% | ___ |
| 3 | INFY | 1,300.80 | 25.0 | 54.6 | Uptrend | ___ | ___% | ___ |
| 4 | ICICIBANK | 1,215.80 | 21.1 | 33.7 | Downtrend | ___ | ___% | ___ |
| 5 | SBIN | 1,018.40 | 10.9 | 36.9 | Downtrend | ___ | ___% | ___ |
| 6 | HDFCBANK | 750.90 | 7.6 | 33.7 | Downtrend | ___ | ___% | ___ |
| 7 | TCS | 2,450.70 | 9.7 | 48.3 | Sideways | ___ | ___% | ___ |
| 8 | BAJFINANCE | 826.85 | 4.0 | 39.8 | Downtrend | ___ | ___% | ___ |

**Big Names AVOID Accuracy: ___/8**

---

## Scoring Rules for Validation

- **HOLD = Correct** if stock moves between -1% to +3% (flat to slightly up)
- **AVOID = Correct** if stock moves < 0% (goes down) or stays flat (-0.5% to +0.5%)
- **AVOID = Wrong** if stock goes up > 1% (AI missed an opportunity)

## Overall Accuracy

| Category | Correct | Wrong | Total | Accuracy |
|----------|---------|-------|-------|----------|
| HOLD | ___ | ___ | 3 | ___% |
| AVOID (Top 10) | ___ | ___ | 10 | ___% |
| AVOID (Big Names) | ___ | ___ | 8 | ___% |
| **TOTAL** | ___ | ___ | **21** | **___%** |

---

## Screenshots

- `dashboard_full.png` - Full page screenshot
- `dashboard_top.png` - Top stocks (HOLD signals)
- `dashboard_mid.png` - Mid section (AVOID 20-35 score)
- `dashboard_bottom.png` - Bottom section (AVOID 10-20 score)
- `dashboard_bottom2.png` - Lowest scores (AVOID < 10)
- `baseline.json` - Raw data with all 49 stocks

## Notes
_Fill in after Monday market close_
