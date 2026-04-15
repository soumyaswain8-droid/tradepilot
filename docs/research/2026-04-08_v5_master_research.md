# TradePilot v5 -- Master Research Document

*Definitive reference for building TradePilot v5: multi-horizon, ML-powered, India-first*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Version** | `v5.0.0` |
| **Status** | Research Complete -- Ready for Implementation |
| **Created** | 2026-04-08 |
| **Updated** | 2026-04-08 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@devpilot.co.in |
| **LinkedIn** | [linkedin.com/in/soumya-swain](https://www.linkedin.com/in/soumya-swain-116208107/) |

:::

---

## 1. Executive Summary

TradePilot v5 is a complete architecture rebuild: from single-horizon classification to **multi-horizon ensemble ML** with regime-aware risk management. The core thesis remains unchanged -- build the platform that makes Indian traders profitable -- but the engine underneath gets radically smarter.

**Key numbers driving v5:**

| Metric | Value | Source |
|:-------|------:|:-------|
| Indian demat accounts | 212.8M | CDSL/NSDL 2025 |
| F&O traders losing money | 93% | SEBI 2024 |
| Aggregate retail F&O losses | Rs 1.8 trillion (3yr) | SEBI 2024 |
| Monthly SIP flows (structural floor) | Rs 29,361 cr | AMFI Sep 2025 |
| Backtest Sharpe degradation in live | 30-50% | Academic consensus |
| LightGBM vs deep learning on tabular | LightGBM wins | Kaggle + papers |
| Insider buying cluster outperformance | 11.2% over 6 months | SEBI data analysis |
| Target portfolio Sharpe (live) | >1.0 | v5 design goal |

**What v5 delivers:** 4 trading pools (intraday/swing/positional/investment), LightGBM+TFT+LSTM ensemble, regime detection via HMM, alternative data (FII flows, insider trades, delivery %), automated circuit breakers, and tax-aware profit waterfall -- all running on an M1 Mac.

---

<div class="page-break"></div>

## 2. V4 to V5 Evolution

### What Failed in V4

| V4 Problem | Impact | V5 Fix |
|:-----------|:-------|:-------|
| Classification target (up/down/avoid) | Destroyed magnitude info; 96% AVOID class | Regression target: predict intraday return magnitude |
| Single horizon (intraday only) | Missed swing/positional alpha | 4 independent pools with separate models |
| No regime detection | Same strategy in bull and bear | HMM 3-state model shifts allocation dynamically |
| k-fold cross-validation | Data leakage from future | Walk-forward with 5-day embargo |
| No alternative data | Only price/volume features | FII/DII flows, delivery %, insider buys, VIX |
| No risk framework | Position sizing by gut feel | VaR/CVaR + Kelly + ATR stops per horizon |
| No compounding rules | Profits sat idle | Profit waterfall across pools monthly |

### What Stays from V4

- LightGBM as primary model (validated as best for tabular financial data)
- Core feature set: RSI, VWAP deviation, ATR, volume ratio, gap %
- Zerodha/Dhan broker integration
- pandas-ta for feature engineering
- vectorbt for backtesting research

---

## 3. Multi-Horizon Architecture

### 3.1 Four Pool Structure (Rs 50L base capital)

| Pool | Allocation | Capital | Holding Period | Turnover | Model |
|:-----|----------:|-------:|:---------------|:---------|:------|
| Intraday | 30% | 15L | Close by 3:15 PM | Daily | LightGBM (30-min return) |
| Swing | 25% | 12.5L | 3-7 days | Weekly | LightGBM + TFT ensemble |
| Positional | 25% | 12.5L | 2-4 weeks | Bi-weekly | Sector rotation + momentum |
| Investment | 15% | 7.5L | 1-6 months | Monthly | Fundamental + insider signals |
| Reserve | 5% | 2.5L | Drawdown buffer | On-demand | Cash only |

### 3.2 Regime-Based Allocation Shifts

Composite regime score from 6 indicators (Nifty vs 50/200-DMA, VIX, A/D ratio, FII 5d flow, sector breadth). Bull >= +3, Bear <= -3, else Sideways.

| Pool | Bull | Sideways | Bear |
|:-----|-----:|---------:|-----:|
| Intraday | 30% | 35% | 25% |
| Swing | 30% | 20% | 15% |
| Positional | 25% | 20% | 10% |
| Investment | 15% | 15% | 20% |
| Reserve | 0% | 10% | 30% |

### 3.3 Profit Waterfall (Monthly Cycle)

```
Intraday profits -> 50% stays, 30% -> swing, 20% -> positional
Swing profits    -> 60% stays, 40% -> investment
Positional profits -> 70% stays, 30% -> investment
Investment       -> 100% reinvested (true compounding)
```

### 3.4 Rebalancing Rules

- Weekly drift check: rebalance if any pool > 5% off target
- After drawdown: reduce pool to 75% for 2 weeks, excess to reserve
- Restore full size only after 5 consecutive profitable days

---

<div class="page-break"></div>

## 4. Data Sources Master Table

Ranked by predictive power for Indian markets. All free unless noted.

### 4.1 Tier 1 -- Highest Alpha (Always Include)

| Source | Data Type | Alpha Signal | Frequency | Python Library |
|:-------|:----------|:-------------|:----------|:---------------|
| NSE FII/DII flows | Cash + F&O activity | FII selling >2000cr = bearish 1-3 days | Daily EOD | `nsefin` |
| Participant-wise OI | FII/DII/Pro/Client positions | FII long/short ratio predicts direction | Daily 5-6 PM | `nsepython` |
| NSE delivery bhavcopy | Delivery % per stock | >60% + price up = institutional buying | Daily EOD | `NseIndiaApi` |
| India VIX | Fear gauge | <11 complacency, >25 panic buy signal | Real-time | `jugaad-data` |
| GIFT Nifty | Overnight price discovery | Gap prediction ~75% accuracy | Continuous | TradingView API |
| Insider trades (SEBI) | Promoter buys/sells | 3+ insiders in 30d = 11.2% outperformance | Weekly | SEBI SAST filings |

### 4.2 Tier 2 -- Strong Signal (Include After Validation)

| Source | Data Type | Alpha Signal | Frequency | Access |
|:-------|:----------|:-------------|:----------|:-------|
| NSE option chain | OI + Greeks by strike | Max pain convergence on expiry day | Real-time | `nsepython` |
| Promoter pledge data | Pledged shares % | Rising pledges = risk of forced selling | Quarterly | BSE/NSE filings |
| Bulk/block deals | Large transactions | Institutional entry/exit signals | Daily | NSE website |
| AMFI MF flows | Category-wise inflows | SIP decline 3mo = market top signal | Monthly | AMFI website |
| Nifty sectoral indices | Sector performance | Relative strength for rotation model | Daily | NSE website |
| Google Trends (pytrends) | Search interest | Retail sentiment proxy | Weekly | `pytrends` |

### 4.3 Tier 3 -- Alternative / Supplementary

| Source | Data Type | Alpha Signal | Frequency | Access |
|:-------|:----------|:-------------|:----------|:-------|
| UPI transaction volumes | NPCI monthly data | Consumer spending proxy | Monthly | NPCI website |
| Monthly auto sales | SIAM/FADA data | Sector health indicator | Monthly | Industry reports |
| Naukri JobSpeak Index | Hiring activity | Economic momentum proxy | Monthly | Naukri website |
| FinBERT sentiment | News sentiment scoring | Contrarian at extremes | Real-time | HuggingFace (free) |
| MSCI rebalancing | Index additions/deletions | Forced FII flows $200-500M | Quarterly | MSCI website |

### 4.4 Paid (Worth It)

| Source | Cost | What You Get |
|:-------|-----:|:-------------|
| Zerodha Kite Connect full | Rs 500/mo | 10yr intraday data + WebSocket 3000 instruments |
| Chartink alerts | Rs 780/mo | Webhook-triggered scans, 100+ indicators |
| Trendlyne Pro | Rs 119/mo | 1400+ parameters, DVM scoring |

---

<div class="page-break"></div>

## 5. ML Engine Design

### 5.1 Ensemble Architecture

```
Input Features (20)
    |
    +---> LightGBM Regressor -----> predicted_return_lgb (weight: 0.50)
    |     (tabular, fast, interpretable)
    |
    +---> Temporal Fusion Transformer -> predicted_return_tft (weight: 0.30)
    |     (attention over time, handles regime shifts)
    |
    +---> LSTM -----------------------> predicted_return_lstm (weight: 0.20)
          (sequential patterns, momentum)
    |
    v
  Weighted Average -> final_predicted_return
    |
    v
  RL Position Sizer (FinRL PPO) -> position_size (% of pool)
    |
    v
  Risk Filter (VaR, regime, circuit breaker) -> TRADE or SKIP
```

**Expected live performance:** Sharpe 1.0-1.8, IC 0.05-0.10 (30-50% below backtest).

### 5.2 Target Variable

```python
# Regression, NOT classification (v4's mistake)
target = (close_1500 - open_0930) / open_0930
target = np.clip(target, target.quantile(0.01), target.quantile(0.99))  # winsorize
```

### 5.3 Top 20 Features (SHAP-ranked)

**Tier 1 (always include):** RSI(14), VWAP deviation, ORB 15-min range, previous day return, ATR(14)/close, volume ratio (today/20d avg), gap %.

**Tier 2 (include after validation):** MACD histogram, Bollinger %B, ADX(14), FII/DII net flow, options OI PCR, sector relative strength, 5-day return, intraday volatility (H-L)/C.

**Tier 3 (calendar/alternative):** Day of week, days to F&O expiry, Nifty 50 morning return, India VIX, delivery %.

### 5.4 LightGBM Configuration

```python
LGBM_PARAMS = {
    'objective': 'regression', 'metric': 'mae',
    'num_leaves': 31, 'max_depth': 6,
    'min_child_samples': 100,  # HIGH -- prevents noise fitting
    'reg_alpha': 0.1, 'reg_lambda': 1.0,
    'subsample': 0.7, 'colsample_bytree': 0.7,
    'learning_rate': 0.01, 'n_estimators': 5000,  # early stopping cuts
}
```

### 5.5 Validation: Walk-Forward with Embargo

```
Fold 1: [=====train 1yr=====]--5d embargo--[test 1mo]
Fold 2:    [=====train 1yr=====]--5d embargo--[test 1mo]
Fold 3:       [=====train 1yr=====]--5d embargo--[test 1mo]
```

**Success criteria:** IC > 0.05 in >60% of folds. Long-short spread > 0 in >70% of months after costs.

### 5.6 Training Pipeline

| Step | Tool | Frequency |
|:-----|:-----|:----------|
| Feature computation | pandas-ta + custom | Daily batch |
| Feature store | DuckDB (Parquet files) | Append daily |
| Model training | LightGBM + neuralforecast (TFT/LSTM) | Monthly retrain |
| Hyperparameter search | Optuna | Quarterly |
| Feature importance | SHAP + alphalens-reloaded | Monthly |
| Backtest validation | vectorbt | After every retrain |
| Signal generation | Ensemble inference | Real-time |
| Position sizing | FinRL PPO | Trained quarterly |

### 5.7 Foundation Models (Supplementary Only)

TimesFM (Google) and Chronos (Amazon) are mediocre alone but add 2-5% ensemble improvement. Use as a 4th ensemble member with weight 0.10 if compute allows. All run on M1 Mac.

---

<div class="page-break"></div>

## 6. Indian Market Edges -- Top 10 Ranked

Ranked by (alpha potential x accessibility). All free data.

| Rank | Edge | Alpha | Effort | Horizon | Priority |
|-----:|:-----|:------|:-------|:--------|:---------|
| 1 | **India VIX regime detection** | High | Low | All | P0 |
| 2 | **FII/DII flow tracking** | High | Medium | Swing + Positional | P0 |
| 3 | **GIFT Nifty gap prediction** | Medium | Low | Intraday | P0 |
| 4 | **Delivery % signals** | Medium | Medium | Swing | P1 |
| 5 | **Insider buying clusters** | High | Medium | Positional + Investment | P1 |
| 6 | **F&O expiry patterns** | Medium | Medium | Intraday + Swing | P1 |
| 7 | **Sector rotation model** | High | High | Positional + Investment | P1 |
| 8 | **Promoter pledge stress** | Medium | Low | Investment | P2 |
| 9 | **MF flow analysis** | Low-Med | Low | Investment | P2 |
| 10 | **Small/mid-cap momentum ratio** | High (risky) | Medium | Positional | P2 |

### Key Signals Summary

- **VIX < 11:** Buy puts for protection. **VIX > 25:** Aggressive equity buying.
- **FII net sell > 2000cr/day:** Bearish 1-3 sessions. **FII buy reversal after 10+ sell days:** Strong rally.
- **GIFT Nifty premium > 0.3%:** Gap-up 75% probability. Trade at open.
- **Delivery > 60% + price up 3%:** Institutional accumulation. Buy for swing.
- **3+ insiders buying in 30 days:** 11.2% outperformance over 6 months.
- **Weekly expiry now Tuesday (NSE, since Sep 2025).** All expiry models must recalibrate.

---

## 7. Alternative Data Integration

### What V5 Adds Beyond Price/Volume

| Data Category | Specific Source | Integration Method | Model Input |
|:--------------|:---------------|:-------------------|:------------|
| Institutional flows | FII/DII daily CSV from NSE | `nsefin` Python lib, daily batch | Feature: fii_net_5d, dii_net_5d |
| Options market | Participant-wise OI, option chain | `nsepython`, daily batch | Feature: fii_long_short_ratio, pcr |
| Delivery conviction | NSE delivery bhavcopy | `NseIndiaApi`, daily batch | Feature: delivery_pct, delivery_vs_20d_avg |
| Insider activity | SEBI SAST filings, bulk/block deals | Web scrape weekly | Feature: insider_buy_cluster_30d |
| Sentiment | FinBERT on news headlines | HuggingFace inference, hourly | Feature: news_sentiment_score |
| Search interest | Google Trends for stock/sector names | `pytrends`, weekly | Feature: search_momentum_7d |
| Macro proxy | UPI volumes (NPCI), auto sales | Monthly manual + DB | Feature: consumer_momentum_index |
| Volatility regime | India VIX + GARCH(1,1) | `arch` library, daily | Feature: vix_regime, garch_vol |

### India-Specific Notes

- No credit card transaction data, dark pools, or satellite imagery alpha in India
- **Uniquely Indian edges:** Promoter pledging (no Western equivalent), bulk/block deal transparency, daily FII/DII disclosure (most markets don't publish daily)

---

<div class="page-break"></div>

## 8. Risk Management Framework

### 8.1 Drawdown Limits

| Horizon | Max Daily DD | Max Weekly DD | Max Monthly DD | Kill Switch |
|:--------|------------:|-------------:|--------------:|:------------|
| Intraday | 2% of pool | 5% of pool | 10% of pool | Pause 1 day |
| Swing | -- | 3% of pool | 8% of pool | Reduce size 50% |
| Positional | -- | -- | 10% of pool | Exit weakest 50% |
| Investment | -- | -- | 15% of pool | Review, no panic |
| **Portfolio** | **1% of total** | **3% of total** | **7% of total** | **All-stop** |

### 8.2 Circuit Breaker Rules

| Trigger | Action | Duration |
|:--------|:-------|:---------|
| Pool daily DD > 2% | Pause pool rest of day | 1 day |
| Pool weekly DD > 5% | Reduce pool to 50% size | 1 week |
| Portfolio weekly DD > 3% | Pause all intraday/swing | 2 days |
| Portfolio monthly DD > 7% | All-stop, reserve only | Until manual review |
| 5 consecutive losing days | Reduce all pools to 50% | 3 days |
| Single trade > 1% total capital loss | Review sizing model | Immediate |

### 8.3 Recovery + Regime Detection

**Recovery ladder:** After circuit breaker: Day 1-3 at 25%, Day 4-7 at 50%, Day 8-14 at 75%, Day 15+ full.

**Regime detection:** 3-state HMM on (returns, volatility) via `hmmlearn`. Current state drives allocation (Section 3.2) + VIX sizing: `size_multiplier = min(15/current_vix, 1.0)`.

### 8.5 Stop-Loss by Horizon

| Horizon | Method | Typical % | Trailing |
|:--------|:-------|----------:|:---------|
| Intraday | ATR(14) x 1.5 | 1.5-2% | 1 ATR after 1:1 R:R |
| Swing | ATR(14) x 2.5 + support | 3-5% | Close below 8-EMA |
| Positional | Weekly ATR x 2 + 200-DMA | 5-8% | Close below 21-EMA |
| Investment | 85% of fair value estimate | 10-15% | None; quarterly review |

### 8.6 Correlation Guard

Never hold >3 stocks from same sector across all pools. If correlation > 0.7 between two holdings, treat as 1.5 effective positions for Kelly sizing.

---

## 9. Technology Stack

### 9.1 Core Stack

| Layer | Tool | Why |
|:------|:-----|:----|
| **Data ingestion** | Dhan API (free, dev) + Zerodha Kite (prod) | Zero cost dev, best liquidity prod |
| **Historical data** | jugaad-data + OpenChart (1-min) | Free, 10+ years daily, 5yr intraday |
| **Tick storage** | QuestDB | ASOF JOIN (critical for financial data), fastest ingestion |
| **Feature store** | DuckDB + Parquet | Zero infra cost, fast analytics, AES-256 |
| **Backtesting** | vectorbt (research sweeps) + Backtrader (event-driven) | Speed + live trading path |
| **Feature engineering** | pandas-ta (primary) + TA-Lib (optional C accelerator) | 150+ indicators, pure Python |
| **ML training** | LightGBM + neuralforecast (TFT, LSTM) | Best tabular + best temporal |
| **RL sizing** | FinRL (PPO agent) | Position sizing > signal generation for RL |
| **Hyperparameters** | Optuna | Bayesian optimization, pruning |
| **Feature analysis** | SHAP + alphalens-reloaded | Importance + factor tearsheets |
| **Research platform** | Microsoft Qlib (15K stars) | End-to-end quant research |
| **Portfolio optimization** | PyPortfolioOpt (quick) + Riskfolio-Lib (advanced) | MV, HRP, CVaR, risk parity |
| **Execution abstraction** | OpenAlgo | 30+ Indian brokers, one unified API |
| **Screening** | Chartink webhooks + custom scanner | Free, webhook to OpenAlgo |
| **Dashboards** | Grafana + QuestDB | Real-time P&L, portfolio heat maps |
| **Alerts** | Telegram Bot API | What Indian traders actually use |
| **Sentiment** | FinBERT / FinGPT (HuggingFace) | Free, runs on M1 Mac |
| **Performance reporting** | quantstats | Full tearsheets, benchmark comparison |

### 9.2 Broker API Ranking (India)

| Rank | Broker | Latency | Cost | Best For |
|-----:|:-------|:--------|:-----|:---------|
| 1 | Dhan | ~50ms | Free | Development, intraday algo |
| 2 | Zerodha Kite | Low | Rs 500/mo | Production, largest ecosystem |
| 3 | Fyers | Low | Free | Free API with bracket orders |
| 4 | Angel One SmartAPI | Moderate | Free | Easiest onboarding |
| 5 | Flattrade | Moderate | Free + 0 brokerage | Cost minimization |

### 9.3 Key Dependencies

All run on M1 Mac, no GPU required. Core: `lightgbm neuralforecast vectorbt pandas-ta pyportfolioopt riskfolio-lib hmmlearn shap alphalens-reloaded optuna quantstats nsefin jugaad-data nsepython finrl questdb duckdb python-telegram-bot`.

---

<div class="page-break"></div>

## 10. Implementation Roadmap

**Phase 1 -- Foundation (Weeks 1-3):** QuestDB + DuckDB setup. Ingest 5yr daily (jugaad-data) + 1yr 1-min (OpenChart). Build 20-feature pipeline (pandas-ta + custom). Integrate FII/DII daily feed via `nsefin`. Set up walk-forward validation with 5-day embargo.

**Phase 2 -- ML Engine (Weeks 4-6):** Train LightGBM regressor (IC > 0.05 target). Train TFT + LSTM via neuralforecast. Build ensemble combiner (weighted average + confidence). SHAP analysis to trim to 12-15 features. Full backtest via vectorbt.

**Phase 3 -- Risk + Execution (Weeks 7-9):** HMM regime detector (3-state). 4-pool capital manager with rebalancing. Circuit breakers + ATR stop engine. OpenAlgo integration for paper trading. Dhan API as dev broker.

**Phase 4 -- Alt Data + Production (Weeks 10-12):** Insider trade scraper (SEBI filings). Delivery % + FinBERT sentiment features. Retrain ensemble with alt data. Grafana dashboards + Telegram alerts. Tax-aware P&L tracker. Zerodha production broker switch.

**Total: 12 weeks to live trading.**

---

## 11. Success Criteria

### 11.1 ML Model Metrics

| Metric | Target | Measurement |
|:-------|:-------|:------------|
| Information Coefficient (IC) | >0.05 mean | Walk-forward folds |
| IC stability | Positive in >60% of folds | Walk-forward folds |
| Long-short spread | >0 in >70% of months | After costs (0.1%/trade) |
| Hit rate (intraday) | >53% | Live trades |
| Hit rate (swing) | >50% | Live trades |

### 11.2 Portfolio Metrics

| Metric | Target | Horizon |
|:-------|:-------|:--------|
| Live Sharpe ratio | >1.0 | Annual |
| Sortino ratio | >2.0 | Annual |
| Calmar ratio | >2.0 | Annual |
| Max drawdown per pool | <10% | Any period |
| Max portfolio drawdown | <7% | Any period |
| Profit factor | >1.5 | Per pool |
| Win rate (overall) | >55% | All trades |
| Annual return target | 25-40% | After costs + taxes |

### 11.3 Operational Metrics

| Metric | Target |
|:-------|:-------|
| Model retrain frequency | Monthly |
| Feature store lag | <1 hour from market close |
| Signal generation latency | <5 seconds |
| Order execution (Dhan/Zerodha) | <100ms |
| Dashboard refresh | Real-time (WebSocket) |
| Uptime during market hours | 99.9% |

---

## 12. Key Research References

### Open-Source Repositories

| Repository | Stars | Use In v5 |
|:-----------|------:|:----------|
| machine-learning-for-trading (Stefan Jansen) | 17,009 | ML cookbook, LightGBM patterns |
| QuantConnect Lean | 18,288 | Strategy reference |
| FinRL | 14,698 | PPO position sizing agent |
| Microsoft Qlib | 15,000+ | End-to-end quant research platform |
| vectorbt | 7,107 | Fast backtesting |
| OpenAlgo | 1,608 | 30+ Indian broker abstraction |
| jugaad-data | 504 | Free NSE historical data |

### Proven Strategies (Backtested)

| Strategy | Sharpe | Max DD | Best Horizon |
|:---------|-------:|-------:|:-------------|
| VWAP mean reversion | 3.57 | 16% | Intraday |
| Opening Range Breakout (ORB) | 2.40 | -- | Intraday |
| Momentum factor (top decile) | -- | -- | Positional |
| Pairs trading (Nifty 50 cointegrated) | -- | 2.57% | Market-neutral |
| LightGBM 30-min direction | 1.0-1.8 (live) | -- | Intraday + Swing |

### Academic / Industry Sources

- SEBI: "Analysis of Profit and Loss of Individual Traders in Equity F&O Segment" (Sep 2024)
- Lopez de Prado: "Advances in Financial Machine Learning" (mlfinlab implementation)
- Stefan Jansen: "Machine Learning for Algorithmic Trading" (2nd edition)
- QuestDB benchmarks: 12-36x faster than InfluxDB for ASOF JOIN
- Kaggle competitions: LightGBM consistently outperforms deep learning on tabular data

---

*Research compiled: April 8, 2026. All tools verified, all data sources confirmed free/accessible. This document is the single source of truth for TradePilot v5 implementation.*
