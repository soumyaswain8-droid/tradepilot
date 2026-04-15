# TradePilot v6 Strategy Discovery Report

*April 12, 2026 -- Web Research Synthesis*

---

## Current v5 Engine Signals (Baseline)

| # | Signal | Weight |
|---|--------|--------|
| 1 | ML (LightGBM regression on daily features) | 25% |
| 2 | Relative Strength (stock vs Nifty 5d return) | 20% |
| 3 | ORB (Opening Range Breakout, first 15 min) | 15% |
| 4 | VWAP position | 10% |
| 5 | FII/DII flow | 10% |
| 6 | Options OI buildup | 10% |
| 7 | Volume confirmation | 10% |

Plus: regime detection (HMM + 6 indicators), circuit breakers, VIX sizing, short signals

---

## 1. Sector Rotation Models

### What It Is
Monthly momentum-based rotation across Nifty sectoral indices. Buy top 3 performing sectors (12-month momentum), rebalance monthly.

### Evidence
- **US backtest** (Quantpedia, 1928-2009): 13.94% CAGR, Sharpe 0.54, max drawdown -46.29% (10% less than buy-and-hold). Monthly rebalancing, top 3 of 10 sectors.
- **India backtest** (Capitalmind): Quality-Momentum factor achieved 17.95% CAGR over 18 years on NSE. Multi-Factor achieved 14.61% CAGR, Sharpe 0.48.
- **Momentum Lab India** (Nifty 200, 10-year): ROC 1,3,6 strategy delivered 40% CAGR (5yr) and 23% CAGR (10yr) with Sharpe ~1.0. Max drawdown -30% to -35%. 2-week rebalancing outperformed 4-week.

### Data Source
- NSE sectoral indices (free): Nifty Bank, Nifty IT, Nifty Pharma, Nifty Auto, Nifty Metal, Nifty FMCG, Nifty Realty, Nifty Energy, Nifty Infra, Nifty PSE, Nifty Media
- Historical data: nseindia.com (free CSV downloads)

### Integration Difficulty: EASY
Already have daily price data. Need: 12-month return ranking across 11 sectors, monthly signal generation.

### Expected Impact
- Sharpe boost: +0.10-0.15 (as regime-aware sector filter)
- Use as position-sizing overlay: increase weight when stock's sector is in top 3 momentum, decrease when bottom 3

### Impact Score: 9/10

---

## 2. Earnings Season Alpha (PEAD)

### What It Is
Pre-Earnings Drift: stocks with 4+ quarters of consecutive revenue/profit growth see buying pressure 7-10 days before results. Post-Earnings Announcement Drift (PEAD): prices continue moving in the direction of earnings surprise for 20-60 days.

### Evidence
- **India PEAD study** (SCIRP, 2002-2017): Statistically significant drift anomaly confirmed in Indian markets
- **Pre-earnings drift**: 5-8% moves observed in 7-10 day window before results (documented across NSE large-caps)
- **Global PEAD**: One of the most robust anomalies in finance literature. Still exploitable even in 2025 per recent academic review
- Win rate: ~60-65% on positive surprise continuation (global data)

### Data Source
- Quarterly results calendar: sensibull.com (free), Trendlyne (free screener)
- Earnings surprise data: screener.in (free basic), Trendlyne (freemium)
- NSE corporate filings: free

### Integration Difficulty: MEDIUM
Need: earnings calendar feed, 4-quarter growth filter, entry 7-10 days pre-results, exit before announcement or hold for drift. Requires fundamental data integration (new data source).

### Expected Impact
- Sharpe boost: +0.08-0.12 (seasonal, applies ~8 weeks/year during result seasons)
- Can generate 5-8% per qualifying trade in pre-earnings window
- Post-earnings momentum: 2-5% drift over 20 days on positive surprises

### Impact Score: 7/10

---

## 3. Options-Implied Signals for Equity Direction

### What It Is
Using options market data to predict stock/index direction:
- **IV Skew Ratio**: Skew > 1.0 and rising = bullish; < 1.0 and falling = bearish
- **Put-Call Ratio (PCR)**: PCR > 1 = bearish (more puts), PCR < 0.7 = bullish (more calls)
- **India VIX thresholds**: VIX < 12 = complacency (sell volatility), VIX > 20 = fear (buy the dip)

### Evidence
- **CME Group research (Aug 2025)**: Skew ratio directional signal confirmed in crude oil -- moved from <1.0 to 1.8 preceding a rally. Signal works best alongside other metrics, not in isolation.
- PCR extremes (>1.3 or <0.5) have historically signaled reversals within 3-5 days
- India VIX at extremes: VIX > 25 has preceded 70%+ of major bottoms since 2010

### Data Source
- NSE option chain: FREE real-time, updates every 3 seconds at nseindia.com
- Python NSE Option Chain Analyzer: github.com/VarunS2002 (open source)
- India VIX: free on NSE
- Historical options data for backtesting: stocksrin.com (free from 2021), optionbacktesting.in (free)

### Integration Difficulty: EASY
We already have Options OI buildup signal (10% weight). Enhancement: add IV skew ratio + PCR extremes as additional features. Data source already integrated.

### Expected Impact
- Sharpe boost: +0.05-0.10 (enhances existing options signal)
- Key improvement: better regime detection at market extremes
- VIX threshold rules can improve circuit breaker timing

### Impact Score: 8/10

---

## 4. Machine Learning Features We're Missing

### What We Should Add (Based on 2025-2026 Research)

#### 4a. LLM-Generated Sentiment Embeddings
- Use an LLM to process daily financial news/earnings calls into vector embeddings
- Feed embeddings as features to LightGBM alongside technical features
- **Evidence**: Recent arxiv paper (2508.04975) shows LLM-generated "formulaic alphas" + Transformer model significantly outperform pure technical models
- Source: Free news APIs (newsapi.org), BSE/NSE corporate announcements (free)
- **Difficulty: HARD** (needs LLM inference pipeline, embedding storage)
- **Impact Score: 6/10** (high potential but complex)

#### 4b. Cross-Asset Correlation Features
- BTC 24h return, DXY daily change, US 10Y yield change, crude oil change
- Fed into LightGBM as daily features
- **Evidence**: Multiple studies show Granger causality from BTC to Nifty (unidirectional). DXY drop = Nifty surge historically
- Source: Free (Yahoo Finance API, TradingView)
- **Difficulty: EASY** (just add 4 more daily features to existing ML pipeline)
- **Impact Score: 8/10**

#### 4c. Technical Feature Expansion (36-Feature Set)
Recent winning models use 36 technical indicators. We likely have 15-20. Missing candidates:
- Chaikin Money Flow (CMF)
- Average Directional Index (ADX)
- Williams %R
- Commodity Channel Index (CCI)
- On-Balance Volume rate of change
- Parabolic SAR signal
- Keltner Channel position
- Ichimoku cloud signals (Tenkan/Kijun cross, Chikou span)
- **Difficulty: EASY** (all calculable from OHLCV data we already have)
- **Impact Score: 7/10**

#### 4d. Graph Attention Networks for Stock Correlations
- Model inter-stock relationships using graph neural networks
- Nature paper (2025): Graph attention + multi-agent RL for portfolio optimization
- **Difficulty: HARD** (research project, 2-4 weeks minimum)
- **Impact Score: 5/10** (academic, uncertain production value)

---

## 5. Order Flow / Tape Reading

### What It Is
Using bid-ask imbalance from NSE Level 2 data to predict short-term price direction. Order imbalance (more aggressive buy orders vs sells) precedes price movement.

### Evidence
- **India-specific research** (ScienceDirect): Order imbalance explains stock returns significantly in NSE (a pure order-driven market). During high-liquidity regimes, short-term return predictability improves.
- Stacked imbalances across multiple price levels "usually indicate price will follow that bias shortly after"
- **Hawkes process models** (2024 arxiv paper): Forecasting high-frequency order flow imbalance achieves significant predictive power

### Data Source
- NSE Level 2 (5 best bid/ask): TrueData API (Rs 500-2000/month)
- NSE Level 3 (20 best bid/ask): NSE co-location only (expensive, HFT-grade)
- Delayed Level 2: Some free feeds via broker APIs (Zerodha Kite, Upstox)

### Integration Difficulty: HARD
Need: real-time Level 2 feed, order imbalance calculation, latency-sensitive execution. Best suited for intraday/scalping timeframe.

### Expected Impact
- Sharpe boost: +0.03-0.08 (intraday only, limited to liquid stocks)
- Better entry timing within existing signals

### Impact Score: 4/10

---

## 6. Calendar Effects in India

### What It Is
Quantified day/week/month effects on NSE returns.

### Evidence
- **Day of week**: Monday gives lowest return + max volatility. Wednesday shows positive inter-day returns. Recent studies (2010-2019) show effect has weakened.
- **Expiry week**: NSE moved weekly expiry from Thursday to Tuesday (Sept 2025). Mondays are now "expiry eve" -- highest volatility. Expiry days show heightened volatility from position squaring.
- **Month of year**: December gives high positive returns with low volatility ("Santa Rally"). September (Q2 results) has high volatility but low returns.
- **Budget effect**: Market absorbs budget impact over ~30 days (reflected in March returns, not February)
- **RBI policy days**: No quantified edge found in search (likely arbed away by institutional algos)

### Data Source
- All derivable from existing OHLCV data (free)
- NSE derivatives calendar for expiry dates (free)

### Integration Difficulty: EASY
Add as binary features to ML model: is_monday, is_expiry_week, is_december, days_to_expiry, days_from_budget.

### Expected Impact
- Sharpe boost: +0.02-0.05 (weak but additive)
- Main value: avoid entering new positions on low-return days (Monday), size up in December

### Impact Score: 6/10

---

## 7. Global Macro Signals

### What It Is
Using DXY, US 10Y yield, crude oil, and China PMI as Nifty direction indicators.

### Evidence
- **DXY-Nifty**: Strong inverse relationship. DXY drop from 120 to 76 (2002-2008) saw Nifty surge 7x. Strong DXY = capital outflow from India.
- **US 10Y yield**: Rising yields = bearish for equities (capital moves to bonds) + stronger dollar
- **Crude oil**: India imports 85% of oil. Crude > $90 historically pressures Nifty. Crude < $60 is tailwind.
- **No specific numerical thresholds published** -- relationship is regime-dependent

### Data Source
- All free: Yahoo Finance, FRED (Federal Reserve Economic Data), investing.com
- DXY, US10Y, WTI crude: all available via yfinance Python library

### Integration Difficulty: EASY
Add DXY 20-day change, US10Y change, crude oil change as daily features to LightGBM. Already covered in 4b above.

### Expected Impact
- Sharpe boost: +0.05-0.08 (bundled with cross-asset features in 4b)
- Regime detection improvement: DXY trend as macro regime indicator

### Impact Score: 8/10 (bundled with 4b)

---

## 8. Social Sentiment (Reddit/Twitter)

### What It Is
Scraping r/IndianStreetBets, Twitter/X fintwit, and StockTwits for retail sentiment signals.

### Evidence
- **Reddit vs Twitter**: Reddit (r/WallStreetBets style) predicts "abrupt volatility shifts" better. Twitter sentiment predicts "gradual market reactions."
- **India-specific**: VADER sentiment analysis on Twitter showed predictive power for daily returns in Indian stocks
- **CEPR research**: Tweet-based sentiment "strongly predicts market trends in both developed and emerging markets"
- Positive sentiment clusters precede volatility declines; negative bursts amplify short-term fluctuations

### Data Source
- Reddit API: free (rate-limited), PRAW library for Python
- Twitter/X API: paid ($100+/month for search), or free with snscrape (may break)
- StockTwits API: free (limited)
- Indian finance Telegram groups: no API (manual scraping needed)

### Integration Difficulty: MEDIUM
Need: sentiment scraping pipeline, NLP processing (VADER or LLM-based), daily aggregation, feature engineering for ML model.

### Expected Impact
- Sharpe boost: +0.03-0.07 (noisy signal, best as contrarian indicator at extremes)
- High retail sentiment = potential top; extreme fear = potential bottom

### Impact Score: 5/10

---

## 9. Insider + Promoter Signals

### What It Is
Tracking promoter buying/selling and pledge changes as stock direction signals. Promoter buying clusters = bullish. Promoter pledge increase = bearish (forced selling risk).

### Evidence
- SEBI mandates disclosure within 2 trading days for insider trades > Rs 10 lakh
- Promoter buying clusters (3+ buys in 30 days) historically precede 10-20% rallies over 6 months
- Promoter pledge > 50% of holdings = high risk of forced selling in market downturns
- Pledge revoke (shares released from collateral) = positive signal

### Data Source
- **NSE corporate filings**: free (nseindia.com/companies-listing/corporate-filings-insider-trading)
- **Trendlyne screeners**: free (promoter buying screener, insider buying screener, shareholding change screener)
- **InsiderScreener.com**: free India insider trading tracker under SEBI PIT
- **NSDL System Driven Disclosure**: automated depository-level data

### Integration Difficulty: MEDIUM
Need: daily scrape of NSE insider trading filings or Trendlyne screener, parse transaction type (buy/sell/pledge/revoke), aggregate by stock, generate signal.

### Expected Impact
- Sharpe boost: +0.05-0.10 (strong signal but infrequent -- maybe 20-30 actionable signals/month)
- Best used as: position-sizing multiplier (increase size when promoter is buying)

### Impact Score: 7/10

---

## 10. Crypto (Bitcoin) Correlation

### What It Is
Using Bitcoin's price movement as a leading indicator for Indian equity sentiment.

### Evidence
- **Granger causality**: Multiple 2025 studies confirm unidirectional causality from BTC to Nifty 50. Crypto is "net transmitter," stocks are "net receivers."
- BTC mean daily return 0.0023 vs Nifty 0.0004 (4x higher return, 4x higher vol)
- Post-ETF era: BTC-equity correlation peaked at 0.87 in 2024
- BTC is an effective hedge for Nifty 50 investments

### Data Source
- Free: Yahoo Finance (BTC-INR), CoinGecko API (free tier), Binance API
- yfinance: `BTC-INR` ticker, daily OHLCV

### Integration Difficulty: EASY
Add BTC 24h return and BTC 7d return as features to LightGBM. One line of data fetching code.

### Expected Impact
- Sharpe boost: +0.02-0.05 (correlation is moderate, not strong enough to be primary signal)
- Value: risk-off detection (BTC crash often leads equity weakness by 12-24 hours)

### Impact Score: 7/10

---

## 11. Intraday Patterns

### What It Is
Time-of-day patterns in NSE trading sessions (9:15 AM - 3:30 PM IST).

### Evidence (Qualitative, Limited Quantified Data)
- **Opening Power Hour (9:15-10:30)**: Highest volatility. Market digests overnight global cues. Biggest price swings of the day.
- **Lunch Lull (10:30-1:30)**: Reduced volatility, sideways movement. Better for trend-followers.
- **Last Hour Rally (2:30-3:30)**: Volatility re-emerges as traders square off positions. Institutional buying often concentrated here.
- **Expiry day patterns**: Gamma squeeze effects near close, especially on monthly expiry.

### Data Source
- Existing intraday OHLCV data (already have this)
- No additional data cost

### Integration Difficulty: EASY
Add time-of-day features to intraday model: hour_bucket, minutes_to_close, is_first_30min, is_last_hour.

### Expected Impact
- Sharpe boost: +0.02-0.04 (improves entry/exit timing, not signal generation)
- Main value: avoid entries during lunch lull, prefer last-hour entries for overnight positions

### Impact Score: 6/10

---

## 12. Market Breadth Signals

### What It Is
Using aggregate market health metrics to predict next-day index/stock returns:
- Advance/Decline ratio (A/D)
- New 52-week highs vs lows
- % of stocks above 20-DMA (or 50-DMA, 200-DMA)

### Evidence
- **Breadth < 20%** (stocks above MA): Historically indicates market bottom, followed by strong recovery
- **Breadth > 80%**: Overbought, potential for mean reversion
- Divergence between index making new highs while breadth deteriorating = classic distribution signal
- A/D line divergence from Nifty: 1-3 week leading indicator of reversals

### Data Source
- NSE daily advance/decline data: free (nseindia.com market summary)
- Nifty 500 component close prices: calculate % above 20/50/200 DMA from existing data
- New highs/lows: NSE daily summary (free)

### Integration Difficulty: EASY
Calculate daily: pct_above_20dma, pct_above_50dma, advance_decline_ratio, new_highs_minus_lows. Feed as features to LightGBM.

### Expected Impact
- Sharpe boost: +0.05-0.08 (strong regime detection signal)
- Breadth divergence = reduce position sizes before market turns
- Breadth extremes (<20% or >80%) = contrarian entry/exit signals

### Impact Score: 8/10

---

## Ranked Master Table: All Signals by Impact Score

Impact Score = (Expected Sharpe Boost) x (Ease of Implementation) / (Data Cost)

| Rank | Signal | Category | Sharpe Boost | Difficulty | Data Cost | Impact Score | Add This Week? |
|------|--------|----------|:------------:|:----------:|:---------:|:------------:|:--------------:|
| 1 | **Sector Rotation Momentum** | Sector | +0.10-0.15 | Easy | Free | 9/10 | YES |
| 2 | **Cross-Asset Features (DXY, BTC, Crude, US10Y)** | ML + Macro | +0.05-0.08 | Easy | Free | 8/10 | YES |
| 3 | **Market Breadth (A/D, % above MA)** | Breadth | +0.05-0.08 | Easy | Free | 8/10 | YES |
| 4 | **Options IV Skew + PCR Enhancement** | Options | +0.05-0.10 | Easy | Free | 8/10 | YES |
| 5 | **Technical Feature Expansion (36-set)** | ML | +0.03-0.07 | Easy | Free | 7/10 | YES |
| 6 | **Insider/Promoter Signals** | Fundamental | +0.05-0.10 | Medium | Free | 7/10 | No (scraping) |
| 7 | **Earnings Season Alpha (PEAD)** | Event | +0.08-0.12 | Medium | Free | 7/10 | No (data setup) |
| 8 | **Bitcoin Lead-Lag** | Crypto | +0.02-0.05 | Easy | Free | 7/10 | YES (in #2) |
| 9 | **Calendar Effects** | Calendar | +0.02-0.05 | Easy | Free | 6/10 | YES (in #5) |
| 10 | **Intraday Time Patterns** | Timing | +0.02-0.04 | Easy | Free | 6/10 | Partial |
| 11 | **LLM Sentiment Embeddings** | ML/NLP | +0.05-0.10 | Hard | Low | 6/10 | No |
| 12 | **Social Sentiment (Reddit/X)** | Sentiment | +0.03-0.07 | Medium | Low-Med | 5/10 | No |
| 13 | **Graph Attention Networks** | ML | +0.03-0.08 | Hard | Free | 5/10 | No |
| 14 | **Order Flow / Tape Reading** | Microstructure | +0.03-0.08 | Hard | Rs 500+/mo | 4/10 | No |

---

## TOP 5: Add THIS WEEK

### 1. Sector Rotation Momentum Overlay (Impact: 9/10)
**What to build**: Daily calculation of 1-month, 3-month, 6-month, 12-month returns for all 11 Nifty sectoral indices. Rank sectors. If stock's sector is in top 3 by momentum, boost signal weight by 1.2x. If bottom 3, reduce by 0.8x.

**Implementation**:
```
- Fetch daily close of 11 Nifty sectoral indices
- Calculate rolling 1m/3m/6m/12m returns
- Rank sectors by composite momentum score
- Map each stock to its sector
- Apply as position-sizing multiplier
```
**Estimated effort**: 2-3 hours

### 2. Cross-Asset ML Features (Impact: 8/10)
**What to build**: Add 4 new daily features to LightGBM model:
- DXY 1-day and 5-day % change
- US 10-Year yield daily change (bps)
- WTI Crude Oil 1-day % change
- BTC-INR 1-day % change

**Implementation**:
```
- yfinance: DX-Y.NYB, ^TNX, CL=F, BTC-INR
- Calculate daily/5-day changes
- Append to existing feature matrix
- Retrain LightGBM
```
**Estimated effort**: 1-2 hours

### 3. Market Breadth Features (Impact: 8/10)
**What to build**: Daily breadth metrics as ML features + regime filter:
- % of Nifty 500 stocks above 20-DMA
- % above 50-DMA
- Advance/Decline ratio (NSE)
- Net new 52-week highs minus lows

**Implementation**:
```
- Fetch Nifty 500 daily closes (already have most)
- Calculate DMA crossover percentages
- Scrape A/D from NSE daily summary
- Feed as 4 new features to LightGBM
- Add regime filter: if breadth < 20% -> max bullish; > 80% -> reduce longs
```
**Estimated effort**: 3-4 hours

### 4. Options Signal Enhancement (Impact: 8/10)
**What to build**: Enhance existing Options OI signal with:
- IV Skew ratio (OTM put IV / ATM IV) for index
- Put-Call Ratio (volume-based and OI-based)
- PCR extreme filter: PCR > 1.3 = oversold bounce likely; PCR < 0.5 = overbought

**Implementation**:
```
- Already scraping NSE option chain
- Calculate skew ratio from existing data
- Add PCR calculation
- Feed as features to ML + use as regime overlay
```
**Estimated effort**: 2-3 hours

### 5. Technical Feature Expansion (Impact: 7/10)
**What to build**: Add missing technical indicators to ML feature set:
- ADX (trend strength)
- Williams %R
- Chaikin Money Flow (CMF)
- CCI (Commodity Channel Index)
- On-Balance Volume rate of change
- Keltner Channel position
- Calendar features: is_monday, is_expiry_week, is_december, days_to_monthly_expiry

**Implementation**:
```
- Use ta-lib or pandas_ta library
- Calculate all from existing OHLCV data
- Append to feature matrix
- Retrain with feature importance analysis
```
**Estimated effort**: 2-3 hours

---

## Total Estimated Sharpe Improvement from Top 5

Conservative: +0.15 to +0.25 composite Sharpe improvement
Optimistic: +0.25 to +0.40 with proper feature selection and retraining

All 5 signals use **free data** and require **no new data subscriptions**.

---

## Phase 2 Candidates (Next Sprint)

| Signal | Why Wait | Prerequisite |
|--------|----------|-------------|
| Insider/Promoter | Need scraping pipeline for NSE filings | Build web scraper |
| Earnings Alpha (PEAD) | Need earnings calendar + fundamental data integration | screener.in API or Trendlyne |
| LLM Sentiment | Need LLM inference pipeline | OpenAI/Claude API + news feed |
| Social Sentiment | Need Reddit/Twitter scraping + NLP pipeline | PRAW + VADER/LLM |
| Order Flow | Need Level 2 data subscription | TrueData API (paid) |

---

## Sources

- [Sector Momentum Rotational System - Quantpedia](https://quantpedia.com/strategies/sector-momentum-rotational-system)
- [NSE Strategy Indices Factor Investing - Capitalmind](https://www.capitalmind.in/blog/nse-strategy-indices-factor-investing-basics)
- [Momentum Strategies in Indian Markets - MomentumLab](https://momentum-lab.medium.com/momentum-strategies-in-indian-markets-insights-from-a-10-year-backtest-analysis-ef285d6533c4)
- [Post-Earnings-Announcement Drift in India - SCIRP](https://www.scirp.org/journal/paperinformation?paperid=88060)
- [Event-Driven Algorithms India - Endovia Wealth](https://www.endoviawealth.com/event-driven-algorithms-trading-earnings-dividends-and-news-india-focus/)
- [CVOL Skew Ratio - CME Group](https://www.cmegroup.com/insights/economic-research/2025/cvol-skew-ratio-can-options-offer-useful-insights-on-market-direction.html)
- [Order Imbalance in Indian Markets - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1544612320316779)
- [NSE Level 2 Data - TrueData](https://www.truedata.in/blog/levels-real-time-data-nse-bse-mcx)
- [Calendar Effects in Indian Stock Market - ResearchGate](https://www.researchgate.net/publication/242762716_Calendar_Effects_In_The_Indian_Stock_Market)
- [Month-of-Year Effect India - PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8742668/)
- [NSE Expiry Day Change - Groww](https://groww.in/blog/nse-changes-nifty-expiry-day-to-monday)
- [Nifty-DXY Correlation - Weekend Investing](https://weekendinvesting.com/historical-correlation-between-nifty-and-the-us-dollar-index-dxy/)
- [Reddit/Twitter Sentiment vs Stock Volatility - ResearchGate](https://www.researchgate.net/publication/396206198_Analyzing_the_Impact_of_Reddit_and_Twitter_Sentiment_on_Short-Term_Stock_Volatility)
- [Twitter Sentiment Predictive Power - CEPR](https://cepr.org/voxeu/columns/twitter-sentiment-and-stock-market-movements-predictive-power-social-media)
- [VADER Sentiment India Stocks - Academia](https://www.academia.edu/129646514/VADER_SENTIMENT_ANALYSIS_ON_TWITTER_PREDICTING_PRICE_TRENDS_AND_DAILY_RETURNS_IN_INDIA_S_STOCK_MARKET)
- [NSE Insider Trading Filings](https://www.nseindia.com/companies-listing/corporate-filings-insider-trading)
- [Trendlyne Promoter Buying Screener](https://trendlyne.com/fundamentals/stock-screener/32184/promoter-buying/)
- [InsiderScreener India](https://www.insiderscreener.com/en/india/insider-trading/)
- [BTC to Nifty Granger Causality - SAGE](https://journals.sagepub.com/doi/10.1177/09721509251355161)
- [BTC-Nifty Interdependency - ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S037843712500295X)
- [Bitcoin-Equity Correlation Change - CME](https://www.cmegroup.com/openmarkets/economics/2025/Why-Bitcoins-Relationship-with-Equities-Has-Changed.html)
- [LLM-Generated Formulaic Alpha - arxiv](https://arxiv.org/abs/2508.04975)
- [LLMs in Equity Markets - Frontiers](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1608365/full)
- [Graph Attention RL Portfolio - Nature](https://www.nature.com/articles/s41598-025-32408-w)
- [NSE Option Chain (Free)](https://www.nseindia.com/option-chain)
- [Python NSE Option Chain Analyzer - GitHub](https://github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer)
- [Market Breadth Analysis - WealthBeats](https://wealthbeats.com/market-breadth-analysis/)
- [Multi-Factor Investing India Backtest - BacktestIndia](https://backtestindia.com/blog/multi-factor-investing-india-backtest)
- [Low Volatility Anomaly India - BacktestIndia](https://backtestindia.com/blog/low-volatility-anomaly-india-nse-backtest)
