# TradePilot: McKinsey-Level Competitive Analysis

*Deep Feature Matrix, Pricing Breakdown, and Strategic Gap Analysis -- Indian Trading Platforms*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Version** | `v1.0.0` |
| **Status** | Research Phase |
| **Created** | 2026-04-02 |
| **Updated** | 2026-04-02 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | support@devpilot.co.in |
| **LinkedIn** | [linkedin.com/in/kishorer747](https://www.linkedin.com/in/kishorer747) |

:::

---

## Executive Summary

This document provides a granular, feature-by-feature competitive analysis of 11 Indian trading platforms plus TradePilot. The analysis covers exact feature sets, pricing tiers, user base metrics, technology capabilities, recent innovations, known weaknesses, and revenue model breakdowns. The goal: identify every gap TradePilot must fill and every advantage it can exploit.

**Key findings:**

1. No Indian platform combines AI scoring + backtesting + risk guardrails in a single product
2. The options analytics market (Sensibull, Opstra) is ripe for disruption through integration
3. Algo trading (Streak, Tradetron) is fragmented -- SEBI's Apr 2026 rules will force consolidation
4. Zerodha's ecosystem moat is wide but shallow -- users hate the fragmentation across 8+ apps
5. TradePilot's "profit probability" approach has zero direct competitors in India

---

<div class="page-break"></div>

## 1. Competitor Deep Dives

### 1.1 Zerodha Kite

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2010 |
| Headquarters | Bangalore |
| Active clients | 2.3 Cr+ (23M+) |
| NSE market share | ~16-17% of active clients |
| Revenue (FY25) | Rs 8,320 Cr (~$1B) |
| Profit (FY25) | Rs 4,700 Cr (~$560M) |
| Valuation | Bootstrapped, profitable since inception |
| Employees | ~1,500 |
| Play Store rating | 3.8/5 (1M+ downloads) |
| App Store rating | 3.6/5 |
| Trustpilot | 1.7/5 (2,800+ reviews) |

**Exact Feature List**

| Category | Features |
|:---------|:---------|
| **Order Types** | Market, Limit, SL, SL-M, AMO, GTT (Good Till Triggered), Bracket Orders (suspended), Cover Orders |
| **Charting** | Basic built-in charts, 100+ indicators, 5 chart types, drawing tools. NO multi-chart layouts, NO replay |
| **Options** | Basic options chain, no Greeks display natively, no payoff diagrams, no strategy builder. Relies on Sensibull integration |
| **Algo/Automation** | None native. Relies on Streak integration (separate subscription). Kite Connect API for custom algos |
| **Education** | Varsity (free, 500+ chapters, 13 modules). Best-in-class free trading education |
| **Portfolio** | Console (back-office): P&L, tax P&L, tradebook, holdings. Basic visualizations |
| **Screeners** | None native. Relies on Smallcase/Screener.in |
| **Mutual Funds** | Coin (direct MF platform, free) |
| **IPO** | IPO application via UPI |
| **Commodities** | MCX trading supported |
| **Currency** | Currency derivatives supported |
| **API** | Kite Connect v3 (REST + WebSocket). Rs 2,000/month. Rate limit: 10 req/sec |
| **Paper Trading** | None |
| **Backtesting** | None native. Streak offers limited backtesting |
| **Risk Tools** | GTT for automated exit. No portfolio-level risk metrics |
| **Social** | None |
| **Tax** | Console provides basic tax P&L report. No ITR auto-fill |

**Pricing**

| Item | Cost |
|:-----|-----:|
| Account opening | Rs 0 (free) |
| Equity delivery | Rs 0 (free) |
| Equity intraday | Rs 20/order or 0.03% (whichever lower) |
| F&O | Rs 20/order |
| Currency | Rs 20/order |
| Commodity | Rs 20/order |
| AMC (demat) | Rs 300/year |
| Kite Connect API | Rs 2,000/month |
| Pledge margin | Free |

**Hidden/additional charges:** DP charges Rs 15.93/scrip on sell, STT, GST, stamp duty, SEBI charges. Total effective cost per F&O trade: ~Rs 30-45 including all charges.

**Revenue Model Breakdown (estimated)**

| Stream | % of Revenue | Notes |
|:-------|------------:|:------|
| Brokerage (F&O) | ~55% | Rs 20/order on massive F&O volumes |
| Brokerage (equity intraday) | ~15% | |
| Interest on client funds | ~12% | Float income on idle margin |
| Kite Connect API | ~5% | Developer subscriptions |
| Sensibull/Streak rev share | ~3% | Ecosystem partnerships |
| Coin (MF) | ~2% | Commission from AMCs |
| Other (charges, penalties) | ~8% | DP charges, delayed payments |

**Recent Innovations (2025-2026)**

- GTT (Good Till Triggered) orders expanded
- Varsity content expanded to 500+ chapters
- Simplified margin reporting (post SEBI peak margin rules)
- Kite 4.0 UI refresh (minor)
- Console tax reporting improvements

**Known Weaknesses**

1. **Platform outages during volatility** -- multiple documented incidents where Kite was down during market open/budget day. FreePressJournal reported 88% of users unable to trade during one incident
2. **Charting is basic** -- no multi-chart, no Pine Script equivalent, no replay
3. **No native options analytics** -- forces users to Sensibull (separate subscription)
4. **No backtesting or paper trading** -- critical gap for strategy development
5. **Customer support is terrible** -- 1.7/5 on Trustpilot, automated replies, long resolution times
6. **Bracket orders suspended** since 2020 and never restored
7. **No AI/ML features** -- pure execution terminal
8. **API is expensive** -- Rs 2,000/month prices out hobbyist algo traders
9. **Ecosystem fragmentation** -- Kite + Console + Coin + Varsity + Streak + Sensibull + Smallcase = 7+ separate apps for one workflow

**What Zerodha Has That TradePilot Does NOT (Yet)**

1. SEBI-registered broker license (TradePilot needs RA or AP path)
2. 2.3 Cr+ user base and brand trust
3. Kite Connect API ecosystem with 500+ third-party apps
4. Varsity (best free trading education in India)
5. Coin (direct mutual fund platform)
6. MCX/currency trading
7. IPO application flow
8. Margin pledge facility
9. 3-in-1 account (trading + demat + bank) via partner banks
10. Regulatory compliance infrastructure (KYC, fund segregation, audit)

---

<div class="page-break"></div>

### 1.2 Groww

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2016 |
| Headquarters | Bangalore |
| Active clients | 1.25 Cr+ (12.5M+) |
| Total registered users | 12 Cr+ (120M+ including MF-only) |
| Valuation | $3B (2024 round) |
| Funding | $393M total raised |
| Revenue (FY25 est.) | Rs 3,500-4,000 Cr |
| Play Store rating | 4.3/5 (10M+ downloads) |
| App Store rating | 4.5/5 |
| Trustpilot | 2.1/5 but 100% response rate |

**Exact Feature List**

| Category | Features |
|:---------|:---------|
| **Order Types** | Market, Limit, SL, SL-M, AMO. NO GTT, NO bracket orders, NO cover orders |
| **Charting** | Very basic charts, ~30 indicators, line/candle only. Minimal drawing tools |
| **Options** | Basic options chain. Option chain view with OI data. No strategy builder, no payoff diagrams |
| **Algo/Automation** | None |
| **Education** | Groww Learn (articles + short videos). Good for absolute beginners, not deep |
| **Portfolio** | Holdings + P&L view. Clean but basic analytics |
| **Screeners** | Basic stock screener with fundamental filters |
| **Mutual Funds** | Groww's core strength. 5,000+ MF schemes, SIP calculator, one-tap invest |
| **IPO** | Full IPO application support |
| **Commodities** | Not supported |
| **Currency** | Not supported |
| **API** | No public API for trading |
| **Paper Trading** | None |
| **Backtesting** | None |
| **Risk Tools** | None beyond basic SL orders |
| **Social** | None |
| **Tax** | Basic P&L reports |
| **Unique** | Stocks + MF + FD + Digital Gold + US Stocks (via Vested) in one app |

**Pricing**

| Item | Cost |
|:-----|-----:|
| Account opening | Rs 0 |
| Equity delivery | Rs 0 |
| Equity intraday | Rs 20/order or 0.05% |
| F&O | Rs 20/order |
| AMC | Rs 0 |
| MF investment | Rs 0 (direct plans) |

**What Groww Offers Beginners That TradePilot Should Match**

1. **One-tap investing** -- the simplest UX in Indian fintech. Stock/MF purchase in <3 taps
2. **Multi-asset in one app** -- Stocks + MF + FD + Gold + US Stocks
3. **Beginner-friendly language** -- no jargon, explanations inline
4. **SIP for everything** -- SIP for stocks, MF, gold
5. **Discovery feed** -- curated stock lists ("Top Gainers", "Most Bought")
6. **Rs 0 barrier** -- no AMC, no hidden charges, no minimum balance
7. **MF comparison tools** -- compare 2-3 funds side by side
8. **Clean mobile-first UX** -- designed for Tier-II/III users on budget phones

**Known Weaknesses**

1. No commodities or currency trading
2. Charting is extremely basic
3. No algo trading or automation
4. No bracket/cover orders
5. No GTT orders
6. No API access
7. Not suitable for active traders
8. Options tools are minimal
9. US stocks via Vested (separate entity, regulatory complexity)

---

<div class="page-break"></div>

### 1.3 Upstox

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2012 |
| Headquarters | Mumbai |
| Active clients | 40L+ (4M+) |
| Registered users | 1.5 Cr+ (15M+) |
| Backers | Ratan Tata, Tiger Global, GVK Davix |
| Revenue (FY25 est.) | Rs 1,200-1,500 Cr |
| Play Store rating | 3.5/5 |
| App Store rating | 3.2/5 |
| Trustpilot | 1.6/5 |

**Exact Feature List**

| Category | Features |
|:---------|:---------|
| **Order Types** | Market, Limit, SL, SL-M, AMO, GTT, Bracket Orders, Cover Orders |
| **Charting** | TradingView integration (embedded), 100+ indicators, 13 chart types |
| **Options** | Options chain with Greeks, strategy builder (basic), payoff chart |
| **Algo/Automation** | None native. API available |
| **Education** | Upstox Learning Center, video courses |
| **Portfolio** | Holdings, P&L, portfolio analytics |
| **3-in-1 Account** | Yes (with Axis Bank) |
| **NRI Trading** | Supported |
| **Mutual Funds** | Available |
| **IPO** | Available |
| **Commodities** | MCX supported |
| **Currency** | Supported |
| **API** | Free developer API (REST + WebSocket) |
| **Paper Trading** | None |
| **Backtesting** | None |

**Pricing**

| Item | Cost |
|:-----|-----:|
| Account opening | Rs 0 |
| Equity delivery | Rs 0 |
| Intraday/F&O | Rs 20/order or 0.05% |
| AMC | Rs 0 |
| API | Free |

**Known Weaknesses**

1. 1.6/5 Trustpilot -- among the worst in industry
2. "Dead slow" app performance reported repeatedly
3. Hidden charges controversy (DP charges, call & trade fees)
4. Order execution failures during volatile sessions
5. Customer support is poor
6. App crashes frequently during market hours
7. Fund withdrawal delays reported

---

<div class="page-break"></div>

### 1.4 Angel One (formerly Angel Broking)

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 1996 |
| Headquarters | Mumbai |
| Active clients | 2.5 Cr+ (25M+) -- largest by registered users |
| Revenue (FY25) | Rs 4,300 Cr |
| Profit (FY25) | Rs 1,400 Cr |
| Listed | NSE/BSE (ANGELONE) |
| Play Store rating | 4.0/5 |
| App Store rating | 4.1/5 |

**Exact Feature List**

| Category | Features |
|:---------|:---------|
| **Order Types** | Market, Limit, SL, SL-M, AMO, GTT, Bracket, Cover |
| **Charting** | Built-in with 100+ indicators, TradingView embedded |
| **Options** | Options chain, basic strategy view |
| **Algo/Automation** | SmartAPI (free, Python/Java/Node SDKs). Best free API in India |
| **Education** | Angel One Academy (video + articles) |
| **Portfolio** | Smart Portfolio (AI-based recommendations) |
| **Screeners** | Built-in stock screener with technical + fundamental filters |
| **Mutual Funds** | Available (commission-free) |
| **IPO** | Available |
| **Commodities** | MCX supported |
| **Currency** | Supported |
| **NRI Trading** | Supported |
| **API** | SmartAPI -- FREE, well-documented, WebSocket support |
| **Research** | AI-powered stock recommendations, research reports |
| **Advisory** | ARQ Prime -- AI advisory engine |

**Pricing**

| Item | Cost |
|:-----|-----:|
| Account opening | Rs 0 |
| Equity delivery | Rs 0 |
| Intraday/F&O | Rs 20/order |
| AMC | Rs 240/year (waived first year) |
| SmartAPI | Free |

**Known Weaknesses**

1. Learning curve steeper than Groww
2. AMC of Rs 240/year (others are free)
3. UI can feel cluttered
4. App performance issues on lower-end devices
5. Aggressive marketing (spam calls/messages reported)
6. Research quality inconsistent

---

<div class="page-break"></div>

### 1.5 Dhan

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2021 |
| Headquarters | Mumbai |
| Active clients | 15L+ (1.5M+) |
| Founded by | Ex-CTO of Edelweiss |
| Play Store rating | 4.2/5 |
| App Store rating | 4.5/5 |
| Trustpilot | 3.5/5 (best among Indian brokers) |

**Exact Feature List**

| Category | Features |
|:---------|:---------|
| **Order Types** | Market, Limit, SL, SL-M, AMO, GTT, Bracket, Cover, OCO (One-Cancels-Other) |
| **Charting** | TradingView embedded, multi-chart layouts, 100+ indicators |
| **Options** | **DEXT (Dhan Express Trade)** -- fastest options execution in India. Options chain with Greeks, strategy builder, payoff diagrams |
| **Algo/Automation** | DhanHQ API (free), Python SDK, algo trading support |
| **Education** | Limited |
| **Portfolio** | Real-time P&L, portfolio analytics |
| **Unique Features** | **TV Dashboard** -- designed for multi-monitor trading setups. Lightning fast execution (<50ms claim). Options Scalper mode |
| **Mutual Funds** | Not available |
| **IPO** | Available |
| **Commodities** | MCX supported |
| **Currency** | Supported |
| **API** | DhanHQ API (free, REST + WebSocket) |
| **Paper Trading** | None |
| **Backtesting** | None native |

**Pricing**

| Item | Cost |
|:-----|-----:|
| Account opening | Rs 0 |
| Equity delivery | Rs 0 |
| Intraday | Rs 20/order |
| F&O | Rs 20/order |
| AMC | Rs 0 |
| DhanHQ API | Free |

**Known Weaknesses**

1. Small user base (1.5M vs Zerodha's 23M)
2. Brand recognition still low
3. No mutual fund integration
4. Education content is thin
5. Limited research/advisory

---

<div class="page-break"></div>

### 1.6 5Paisa

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2016 (part of IIFL Group) |
| Active clients | 15L+ (1.5M+) |
| Listed | NSE/BSE |
| Play Store rating | 3.5/5 |

**Exact Feature List**

| Category | Features |
|:---------|:---------|
| **Order Types** | Market, Limit, SL, AMO, Bracket, Cover |
| **Charting** | Basic built-in charts |
| **Options** | Basic options chain |
| **Algo** | None |
| **Education** | 5Paisa School (articles) |
| **Mutual Funds** | Available |
| **IPO** | Available |
| **Commodities** | MCX supported |
| **API** | Available (paid) |
| **Unique** | Flat Rs 20/trade across all segments. "Ultra Trader" pack for active traders |

**Pricing**

| Item | Cost |
|:-----|-----:|
| Account opening | Rs 0 |
| All trades | Rs 20 flat |
| Power Investor Pack | Rs 999/month (free delivery + research) |
| AMC | Rs 400/year (waived with pack) |

**Known Weaknesses**

1. UI/UX is dated
2. Limited charting
3. Customer support issues
4. Smaller ecosystem than competitors

---

### 1.7 Fyers

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2015 |
| Headquarters | Bangalore |
| Active clients | 5L+ (500K+) |
| Play Store rating | 4.0/5 |
| Niche | Active traders, technical analysis focused |

**Exact Feature List**

| Category | Features |
|:---------|:---------|
| **Order Types** | Market, Limit, SL, SL-M, AMO, GTT, Bracket, Cover |
| **Charting** | **Best native charting in India.** TradingView-powered, multi-chart layouts, 100+ indicators, 50+ drawing tools, chart linking |
| **Options** | Options chain with Greeks, basic strategy builder |
| **Algo** | Fyers API v3 (free). Python SDK. Strong algo community |
| **Education** | Fyers School of Stocks (detailed courses) |
| **Screeners** | Stock/F&O screener with custom filters |
| **Unique** | Lifetime free demat AMC. Fyers One (desktop terminal). Opinion Trading integration |

**Pricing**

| Item | Cost |
|:-----|-----:|
| Account opening | Rs 0 |
| Equity delivery | Rs 0 |
| Intraday/F&O | Rs 20/order |
| AMC | Rs 0 (lifetime free) |
| API | Free |

**Known Weaknesses**

1. Mid-tier user base (500K)
2. Brand visibility low outside trader communities
3. API documentation could be better
4. Limited research content
5. No mutual fund platform

---

<div class="page-break"></div>

### 1.8 Sensibull (Options Analytics)

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2018 |
| Headquarters | Bangalore |
| Acquired by | Zerodha (2021) |
| Users | 5L+ paid subscribers (estimated) |
| Niche | Options analytics, strategy building |

**Exact Feature List (What TradePilot Must Benchmark)**

| Category | Features | Details |
|:---------|:---------|:--------|
| **Options Chain** | Enhanced chain | OI, volume, Greeks (Delta, Gamma, Theta, Vega), IV, IV percentile |
| **Strategy Builder** | Multi-leg strategies | Build any combination: straddles, strangles, iron condors, butterflies, custom spreads |
| **Payoff Diagram** | Interactive P&L chart | Real-time payoff curve with breakeven points, max profit, max loss |
| **Greeks Dashboard** | Portfolio Greeks | Aggregate Delta, Gamma, Theta for entire portfolio |
| **IV Analysis** | IV charts | Historical IV, IV percentile, IV skew across strikes |
| **OI Analysis** | Open Interest tools | OI heatmap, OI change, max pain calculation, PCR (Put-Call Ratio) |
| **Trader's Diary** | Trade journal | Auto-import trades, tag strategies, track performance |
| **Earnings Analysis** | Event impact | Historical earnings impact, expected move calculator |
| **Option Scanner** | Strategy scanner | Scan for strategies meeting criteria (e.g., "high probability iron condors") |
| **What-If Analysis** | Scenario simulator | Simulate price/time/IV changes on open positions |

**Pricing**

| Tier | Cost | Features |
|:-----|-----:|:---------|
| Free | Rs 0 | Basic options chain, limited payoff |
| Lite | Rs 800/month | Strategy builder, payoff, Greeks |
| Pro | Rs 1,600/month | Full suite: IV analysis, OI tools, scanner, journal |
| Yearly Pro | Rs 12,000/year | ~Rs 1,000/month effective |

**What Sensibull Has That TradePilot Needs**

1. **Multi-leg strategy builder** with real-time margin calculation
2. **IV percentile and IV rank** for every strike
3. **Max Pain calculation** with OI visualization
4. **Portfolio-level Greeks aggregation**
5. **What-If scenario simulator** (change price, time, IV independently)
6. **Option strategy scanner** ("find me all iron condors with >70% probability")
7. **Earnings expected move calculator**
8. **Auto trade journal** with strategy tagging
9. **OI heatmap** showing concentration across strikes
10. **PCR (Put-Call Ratio)** historical charts

---

### 1.9 Smallcase

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2015 |
| Headquarters | Bangalore |
| Users | 60L+ (6M+) |
| Partner brokers | 15+ (Zerodha, Groww, Angel One, etc.) |
| AUM | Rs 50,000+ Cr (estimated) |

**Exact Feature List (Portfolio Approach)**

| Category | Features |
|:---------|:---------|
| **Smallcases** | Curated stock/ETF portfolios by theme (e.g., "All Weather", "Electric Mobility", "Brand Value") |
| **Rebalancing** | Periodic rebalancing with one-click execution. Manager-triggered updates |
| **SIP** | Smallcase SIP -- monthly auto-investment into curated portfolios |
| **Research** | Each smallcase has research rationale, historical performance, risk metrics |
| **Managers** | SEBI-registered managers (Windmill Capital, Wright Research, etc.) |
| **Custom** | Create your own smallcase (portfolio) |
| **Tracking** | Portfolio-level P&L, XIRR, benchmark comparison |
| **Integration** | Works through partner broker apps (not standalone execution) |

**Pricing**

| Type | Cost |
|:-----|-----:|
| Free smallcases | Rs 0 (basic themes) |
| Paid smallcases | Rs 100-1,500/quarter (per smallcase, set by manager) |
| Smallcase Manager subscription | Rs 500-3,000/quarter (varies by manager) |
| Execution | Standard brokerage through partner broker |

**Smallcase's Portfolio Approach TradePilot Should Consider**

1. **Theme-based investing** simplifies stock selection for beginners
2. **One-click rebalancing** reduces friction for portfolio maintenance
3. **SEBI-registered managers** provide regulatory credibility
4. **Portfolio as a product** -- not individual stocks, but curated baskets
5. **Integration model** -- works across multiple brokers, not locked to one
6. **SIP for portfolios** -- recurring investment in diversified baskets

---

<div class="page-break"></div>

### 1.10 Streak (Algo Trading)

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2016 |
| Acquired by | Zerodha |
| Users | 10L+ (1M+ registered) |
| Niche | No-code algo trading for retail |

**Exact Feature List (Algo Features TradePilot Should Benchmark)**

| Category | Features | Details |
|:---------|:---------|:--------|
| **Strategy Builder** | No-code visual builder | Drag-and-drop conditions: IF RSI < 30 AND MACD crossover THEN BUY |
| **Indicators** | 50+ technical indicators | RSI, MACD, Bollinger, SuperTrend, VWAP, EMA, SMA, Ichimoku, etc. |
| **Conditions** | Complex logic | AND/OR combinations, nested conditions, multi-timeframe |
| **Backtesting** | Historical backtesting | Test strategy on 5+ years of data. Shows P&L, win rate, drawdown, Sharpe ratio |
| **Paper Trading** | Live paper trading | Run strategy on live data without real money |
| **Alerts** | Strategy alerts | Get notified when conditions are met (without auto-execution) |
| **Live Deployment** | Auto-trade | Deploy strategy for live execution through Zerodha |
| **Marketplace** | Strategy marketplace | Browse/copy strategies from other users (with performance data) |
| **Scanner** | Market scanner | Scan entire market for stocks meeting custom criteria |
| **Multi-Timeframe** | Cross-timeframe logic | Combine daily + hourly conditions in one strategy |

**Pricing**

| Tier | Cost | Features |
|:-----|-----:|:---------|
| Free | Rs 0 | 5 backtests/day, no live deployment |
| Ultimate | Rs 499/month | Unlimited backtests, live deploy, paper trading, marketplace |
| Yearly | Rs 4,999/year | ~Rs 417/month |

**What Streak Algo Offers That TradePilot Needs**

1. **No-code strategy builder** -- visual, not programming
2. **Historical backtesting with realistic slippage/brokerage** deduction
3. **Paper trading on live data** before risking real capital
4. **Strategy marketplace** -- social proof + strategy sharing
5. **Multi-timeframe strategy logic**
6. **Market-wide scanner** -- find stocks matching ANY custom criteria
7. **Performance metrics** -- Sharpe ratio, max drawdown, win rate, P&L curve
8. **One-click deployment** from backtest to live

---

### 1.11 TradingView (Charting)

**Company Profile**

| Metric | Value |
|:-------|:------|
| Founded | 2011 |
| Headquarters | New York |
| Monthly active users | 90M+ globally |
| India users | 15M+ (estimated, one of top 3 markets) |
| Valuation | $3B+ |

**Exact Feature List (Charting Benchmark)**

| Category | Features |
|:---------|:---------|
| **Charts** | 15+ chart types (candle, Heikin-Ashi, Renko, Kagi, P&F, line, area, etc.) |
| **Indicators** | 400+ built-in indicators |
| **Community Indicators** | 100,000+ community-created indicators via Pine Script |
| **Pine Script** | Proprietary scripting language for custom indicators, strategies, alerts |
| **Multi-Chart** | Up to 8 charts on one screen (Premium) |
| **Replay** | Bar replay -- replay historical price action tick by tick |
| **Drawing Tools** | 110+ drawing tools (Fibonacci, Gann, pitchfork, etc.) |
| **Alerts** | Complex conditional alerts on any indicator/price level |
| **Screener** | Stock screener with 100+ filters (fundamental + technical) |
| **Watchlists** | Unlimited watchlists with color coding |
| **Paper Trading** | Built-in paper trading with virtual portfolio |
| **Social** | Ideas, scripts, community chat, follow traders |
| **Data** | Global data coverage (NSE/BSE included) |
| **Real-Time** | Real-time data (with exchange fees or delay) |

**Pricing (India)**

| Tier | Cost | Key Features |
|:-----|-----:|:---------|
| Free | Rs 0 | 1 chart, 3 indicators, delayed data |
| Essential | Rs 1,050/month | 2 charts, 5 indicators, no ads |
| Plus | Rs 1,750/month | 4 charts, 10 indicators, custom timeframes |
| Premium | Rs 3,500/month | 8 charts, 25 indicators, Pine Script priority |
| Yearly discount | ~40% off | |

**What TradingView Has That TradePilot Should Target**

1. **Pine Script** -- custom indicator language (massive community moat)
2. **Bar replay** -- practice reading charts on historical data
3. **Multi-chart layouts** -- essential for multi-stock monitoring
4. **Community indicators** -- 100K+ free indicators
5. **Social layer** -- ideas, comments, followers
6. **Real-time alerts** on any condition
7. **110+ drawing tools** -- professional technical analysis
8. **Cross-market data** -- global stocks, crypto, forex, commodities

---

<div class="page-break"></div>

## 2. Master Feature Matrix

### 2.1 Core Trading Features

::: {.gap-table}

| Feature | Zerodha | Groww | Upstox | Angel One | Dhan | Fyers | TradePilot (Planned) |
|:--------|:-------:|:-----:|:------:|:---------:|:----:|:-----:|:-------------------:|
| Equity delivery | Yes | Yes | Yes | Yes | Yes | Yes | Yes (via broker) |
| Equity intraday | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| F&O trading | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Commodities (MCX) | Yes | No | Yes | Yes | Yes | Yes | Phase 2 |
| Currency derivatives | Yes | No | Yes | Yes | Yes | Yes | Phase 2 |
| Mutual Funds | Yes | Yes | Yes | Yes | No | No | Phase 2 |
| US Stocks | No | Yes* | No | No | No | No | Phase 3 |
| IPO application | Yes | Yes | Yes | Yes | Yes | Yes | Phase 2 |
| GTT orders | Yes | No | Yes | Yes | Yes | Yes | Yes |
| Bracket orders | Suspended | No | Yes | Yes | Yes | Yes | Yes |
| Cover orders | Yes | No | Yes | Yes | Yes | Yes | Yes |
| OCO orders | No | No | No | No | Yes | No | Yes |
| AMO orders | Yes | Yes | Yes | Yes | Yes | Yes | Yes |

:::

### 2.2 Charting & Analysis

::: {.gap-table}

| Feature | Zerodha | Groww | Upstox | Angel One | Dhan | Fyers | TradingView | TradePilot |
|:--------|:-------:|:-----:|:------:|:---------:|:----:|:-----:|:-----------:|:----------:|
| Chart types | 5 | 2 | 13 | 8 | 10 | 12 | 15+ | 15+ |
| Technical indicators | 100+ | 30 | 100+ | 100+ | 100+ | 100+ | 400+ | 200+ |
| Drawing tools | 30 | 5 | 50 | 40 | 50 | 50+ | 110+ | 60+ |
| Multi-chart layout | No | No | Yes | No | Yes | Yes | Yes (8) | Yes (6) |
| Custom indicator scripting | No | No | No | No | No | No | Pine Script | Phase 2 |
| Bar replay | No | No | No | No | No | No | Yes | Yes |
| Heatmaps | No | No | No | No | No | No | Yes | Yes (liquidity) |
| Chart linking | No | No | No | No | No | Yes | Yes | Yes |

:::

### 2.3 Options Analytics

::: {.gap-table}

| Feature | Zerodha | Groww | Dhan | Sensibull | TradePilot |
|:--------|:-------:|:-----:|:----:|:---------:|:----------:|
| Options chain | Basic | Basic | Good | Advanced | Advanced |
| Greeks display | No | No | Yes | Full suite | Full suite |
| Strategy builder | No | No | Basic | Advanced | Advanced |
| Payoff diagrams | No | No | Yes | Interactive | Interactive |
| IV analysis | No | No | No | IV rank/percentile | IV rank + AI |
| Max Pain | No | No | No | Yes | Yes |
| OI heatmap | No | No | No | Yes | Yes + AI overlay |
| What-If simulator | No | No | No | Yes | Yes |
| Portfolio Greeks | No | No | No | Yes | Yes |
| Strategy scanner | No | No | No | Yes | Yes + AI scoring |
| Expected move | No | No | No | Yes | Yes |

:::

### 2.4 Algo Trading & Automation

::: {.gap-table}

| Feature | Zerodha | Angel One | Dhan | Streak | TradePilot |
|:--------|:-------:|:---------:|:----:|:------:|:----------:|
| Trading API | Rs 2K/mo | Free | Free | N/A | Free |
| No-code strategy builder | No | No | No | Yes | Yes |
| Backtesting | No | No | No | Yes (5yr) | Yes (10yr+) |
| Paper trading | No | No | No | Yes | Yes |
| Live auto-execution | Via API | Via API | Via API | Yes | Yes |
| Strategy marketplace | No | No | No | Yes | Yes |
| Multi-timeframe logic | No | No | No | Yes | Yes |
| Performance metrics | No | No | No | Basic | Advanced (Sharpe, Sortino, Calmar) |
| Optimization/walk-forward | No | No | No | No | Yes |
| Slippage modeling | No | No | No | Basic | Advanced |

:::

### 2.5 AI & Intelligence

::: {.gap-table}

| Feature | Zerodha | Groww | Angel One | Dhan | Sensibull | TradePilot |
|:--------|:-------:|:-----:|:---------:|:----:|:---------:|:----------:|
| AI trade scoring | No | No | No | No | No | **Yes (core)** |
| Profit probability | No | No | No | No | No | **Yes (core)** |
| Risk guardrails | No | No | No | No | No | **Yes (core)** |
| Sentiment analysis | No | No | Basic | No | No | **Yes (NLP)** |
| Pattern recognition | No | No | No | No | No | **Yes (CNN)** |
| Position sizing AI | No | No | No | No | No | **Yes (Kelly)** |
| Smart alerts | No | No | Basic | No | No | **Yes** |
| AI research reports | No | No | Yes* | No | No | **Yes** |
| FII/DII flow analysis | No | No | No | No | No | **Yes** |

:::

### 2.6 Education & Community

::: {.gap-table}

| Feature | Zerodha | Groww | Angel One | Streak | TradingView | TradePilot |
|:--------|:-------:|:-----:|:---------:|:------:|:-----------:|:----------:|
| Education content | Best (Varsity) | Good (beginner) | Medium | Basic | Medium | Comprehensive |
| Video courses | No | Yes | Yes | No | No | Yes |
| Paper trading | No | No | No | Yes | Yes | Yes |
| Community forum | No | No | No | No | Ideas/Chat | Verified traders |
| Social trading | No | No | No | Marketplace | Ideas | Verified signals |
| Trade journal | No | No | No | No | No | Auto-journal |
| Performance leaderboards | No | No | No | No | No | Verified P&L |

:::

---

<div class="page-break"></div>

## 3. Pricing Comparison Matrix

::: {.gap-table}

| Cost Item | Zerodha | Groww | Upstox | Angel One | Dhan | Fyers | 5Paisa | TradePilot |
|:----------|--------:|------:|-------:|----------:|-----:|------:|-------:|----------:|
| Account opening | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Equity delivery | 0 | 0 | 0 | 0 | 0 | 0 | 20 | 0 |
| Intraday brokerage | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 0-20* |
| F&O brokerage | 20 | 20 | 20 | 20 | 20 | 20 | 20 | 0-20* |
| Annual AMC | 300 | 0 | 0 | 240 | 0 | 0 | 400 | 0 |
| API access | 2,000/mo | N/A | 0 | 0 | 0 | 0 | Paid | 0 |
| Options tools | 800-1,600/mo** | N/A | N/A | N/A | Included | N/A | N/A | Included |
| Algo/backtest | 499/mo*** | N/A | N/A | N/A | N/A | N/A | N/A | Included |
| Charting (pro) | 1,050-3,500/mo**** | N/A | N/A | N/A | N/A | N/A | N/A | Included |

:::

*Notes:*
- \* TradePilot: Rs 0 on Pro plan, Rs 20 on Free tier
- \*\* Via Sensibull subscription
- \*\*\* Via Streak subscription
- \*\*\*\* Via TradingView subscription

**True Cost of Active Trading Today (Monthly)**

::: {.metrics-table}

| Component | Current Stack Cost | TradePilot Pro |
|:----------|-------------------:|---------------:|
| Broker (Zerodha) | Rs 25/mo AMC equiv | Rs 0 |
| Options analytics (Sensibull Pro) | Rs 1,600/mo | Included |
| Algo trading (Streak) | Rs 499/mo | Included |
| Charting (TradingView Plus) | Rs 1,750/mo | Included |
| **Total** | **Rs 3,874/mo** | **Rs 499/mo** |
| **Annual** | **Rs 46,488/year** | **Rs 5,988/year** |
| **Savings** | -- | **Rs 40,500/year (87%)** |

:::

---

<div class="page-break"></div>

## 4. User Base & Market Share

::: {.task-table}

| Platform | Active Clients (2025-26) | Registered Users | NSE Market Share | Growth Trend |
|:---------|-------------------------:|:-----------------|:-----------------|:-------------|
| Zerodha | 23M+ | 23M+ | ~16-17% | Stable, slight decline |
| Angel One | 25M+ | 27M+ | ~17-18% | Growing fast |
| Groww | 12.5M active | 120M+ registered | ~10-11% | Rapid growth |
| Upstox | 4M active | 15M+ registered | ~4-5% | Declining active |
| ICICI Direct | 10M+ | 12M+ | ~8% | Stable |
| HDFC Securities | 5M+ | 8M+ | ~5% | Stable |
| Dhan | 1.5M+ | 3M+ | ~1.5% | Fast growing |
| Fyers | 500K+ | 1.5M+ | <1% | Niche growth |
| 5Paisa | 1.5M+ | 4M+ | ~1.5% | Slow |
| Motilal Oswal | 3M+ | 5M+ | ~3% | Stable |

:::

**Key market dynamics:**
- Angel One overtook Zerodha in registered users in 2025
- Groww has the most registered users (120M+) but many are MF-only
- Active F&O traders are concentrated: Zerodha (~35%), Angel One (~25%), Groww (~15%)
- "Investor exodus" reported mid-2025: 6 lakh+ accounts closed across top platforms
- Dhan growing fastest among new-age brokers in the active trader segment

---

<div class="page-break"></div>

## 5. Technology Capability Comparison

::: {.gap-table}

| Capability | Zerodha | Groww | Upstox | Angel One | Dhan | Fyers | TradePilot |
|:-----------|:-------:|:-----:|:------:|:---------:|:----:|:-----:|:----------:|
| **API availability** | Paid | No | Free | Free | Free | Free | Free |
| **API quality/docs** | Good | N/A | Medium | Best | Good | Medium | Planned: Best |
| **WebSocket streaming** | Yes | No | Yes | Yes | Yes | Yes | Yes |
| **Execution latency** | 100-200ms | 200ms+ | 150-300ms | 100-200ms | <50ms | 100-150ms | Target: <30ms |
| **Uptime (reported)** | 99.5% | 99.7% | 99.2% | 99.5% | 99.8% | 99.7% | Target: 99.95% |
| **Mobile performance** | Medium | Fast | Slow | Medium | Fast | Medium | Fast |
| **Multi-broker support** | No | No | No | No | No | No | Yes |
| **SDK languages** | Python | N/A | Python | Python/Java/Node | Python | Python | Python/JS/Go |
| **Webhook support** | No | No | No | No | No | No | Yes |
| **Rate limits** | 10 req/s | N/A | 25 req/s | 10 req/s | 10 req/s | 10 req/s | 50 req/s |

:::

---

## 6. Revenue Model Comparison

::: {.gap-table}

| Revenue Stream | Zerodha | Groww | Angel One | Dhan | TradePilot |
|:---------------|:-------:|:-----:|:---------:|:----:|:----------:|
| F&O brokerage | Primary (55%) | Growing | Primary (50%) | Primary | Secondary |
| Equity brokerage | 15% | Primary | 15% | 10% | Low |
| Interest on float | 12% | 10% | 15% | 10% | N/A |
| API subscriptions | 5% | 0% | 0% | 0% | 0% |
| Partner rev share | 3% | 2% | 5% | 0% | N/A |
| MF commissions | 2% | 8% | 3% | 0% | Phase 2 |
| **Subscription (SaaS)** | **0%** | **0%** | **0%** | **0%** | **Primary (60%+)** |
| Data/education | 0% | 0% | 2% | 0% | 15% |
| Advisory/signals | 0% | 0% | 5% | 0% | 10% |

:::

**TradePilot's SaaS-first model is unique.** Every other Indian platform relies on per-order brokerage. TradePilot's subscription model aligns with the user (you pay for value, not volume), enabling honest AI recommendations that don't benefit from more trades.

---

<div class="page-break"></div>

## 7. Strategic Gap Analysis: Where TradePilot Wins

### 7.1 Competitive Gaps TradePilot Fills

::: {.task-table}

| Gap | Who Has It Today | What TradePilot Does | Priority |
|:----|:-----------------|:----|:---------|
| AI trade scoring | Nobody | Per-trade profit probability before execution | P0 |
| Risk guardrails | Nobody | Daily loss limits, position sizing, drawdown alerts | P0 |
| Unified platform | Nobody (fragmented) | Charts + Options + Algo + Analytics in ONE app | P0 |
| Backtesting + paper trading | Streak only (limited) | 10-year backtest with slippage, walk-forward optimization | P0 |
| Options analytics integrated | Sensibull (separate) | Sensibull-grade tools built into trading workflow | P1 |
| No-code strategy builder | Streak (limited) | Visual builder with AI optimization hints | P1 |
| Tax automation | Nobody | Auto-categorize gains, ITR-ready export | P1 |
| Verified community | Nobody | Verified P&L, audited signals, accountability | P1 |
| Multi-broker execution | Nobody | Trade across Zerodha + Dhan + Angel from one screen | P2 |
| Fractional investing | Groww (US stocks only) | Buy Rs 100 of any stock | P2 |

:::

### 7.2 Where Competitors Still Beat TradePilot

::: {.task-table}

| Area | Competitor Advantage | TradePilot Gap | Mitigation |
|:-----|:----|:----|:---------|
| User base | Zerodha: 23M users | Zero users | Partner with brokers (AP model) |
| Brand trust | Zerodha: 14 years in market | New entrant | SEBI RA registration, verified performance |
| Education | Zerodha Varsity: 500+ chapters | No content yet | Partner with Varsity, create AI-specific content |
| Execution infrastructure | Dhan: <50ms latency | No execution engine | Co-locate in NSE colo, use broker APIs initially |
| Regulatory license | All competitors: licensed brokers | No license | Start as RA, then AP, then broker |
| Mutual Funds | Groww: 5,000+ MF schemes | No MF platform | Phase 2 via partner broker |
| Multi-asset | Zerodha: equity+FO+MCX+currency | Equity + F&O only initially | Phased asset class addition |
| Mobile app | All competitors: mature apps | No app yet | Mobile-first development from day 1 |
| Customer support | Groww: 100% Trustpilot response | No support infra | AI-first support + human escalation |

:::

### 7.3 TradePilot's Unfair Advantages

1. **AI-native architecture** -- competitors would need to rebuild from scratch to add AI scoring
2. **SaaS revenue alignment** -- we profit when traders profit, not when they trade more
3. **No legacy baggage** -- can build modern stack (Go/Rust + WebSocket + ML pipeline) without maintaining 10-year-old code
4. **Multi-broker model** -- not locked to one broker, can offer best execution across platforms
5. **Post-SEBI algo rules** -- designed for the new regulatory framework, competitors retrofitting
6. **Indian market ML models** -- trained on FII/DII flows, budget impact, sector rotation unique to India

---

<div class="page-break"></div>

## 8. Competitive Positioning Map

### 8.1 Positioning Grid

```
                        Active Trader Focused
                               ^
                               |
              Fyers            |           Dhan
                        Upstox|    Angel One
                               |
    Simple/Basic -------- Zerodha -------- Advanced/Pro
                               |
                     Groww     |     5Paisa
                               |
                               |
                        Beginner Focused


    TradePilot target position: Top-right quadrant
    (Active Trader Focused + Advanced/Pro)
    BUT with a beginner on-ramp (Groww-like simplicity for Level 1)
```

### 8.2 Strategic Playbook

**Phase 1 (Month 0-3): Land**
- Launch as AI trading analytics platform (RA license)
- Free tier: AI scores for top 200 stocks
- Pro tier: Full scoring + backtesting + paper trading
- Integrate with Zerodha/Dhan APIs for execution

**Phase 2 (Month 3-6): Expand**
- Add options analytics (Sensibull alternative)
- No-code strategy builder
- Multi-broker support
- Mobile app launch

**Phase 3 (Month 6-12): Dominate**
- Community with verified signals
- Tax automation
- AP licenses for direct execution
- Institutional-grade data feeds

**Phase 4 (Year 2): Own**
- Full broker license
- MCX/currency trading
- Fractional investing
- Voice trading

---

## 9. Key Takeaways

1. **The Indian trading market is a $2.2B opportunity** growing at 33% YoY in accounts but only 2.84% in revenue -- proving the market is commoditized and ripe for value-based disruption

2. **No Indian platform has AI at its core.** Angel One has basic AI recommendations; that is it. TradePilot's profit probability engine is genuinely differentiated

3. **The fragmented tool stack is the #1 pain point.** Active traders use 5-6 separate tools costing Rs 3,800+/month. TradePilot at Rs 499/month replaces all of them

4. **93% of F&O traders lose money.** This is both the problem and the opportunity. A platform that demonstrably reduces losses will see viral adoption

5. **SEBI's new algo rules (Apr 2026) create a window.** Old platforms must retrofit. TradePilot builds native compliance

6. **Dhan is the real competitor to watch,** not Zerodha. Dhan has the fastest execution, best options UX, and the most trader-focused DNA. TradePilot must outperform Dhan on analytics + AI while matching their speed

7. **Groww owns beginners. TradePilot should not compete for beginners initially.** Focus on active F&O traders (10M+) who are losing money and will pay for tools that help them stop

8. **The SaaS model is TradePilot's strategic moat.** Every competitor depends on brokerage revenue, creating a conflict of interest (more trades = more revenue, even if trades are bad). TradePilot's subscription model is aligned with trader profitability

---

## Sources

- SEBI: Individual Trader Equity F&O Loss Study (Sep 2024)
- IMARC Group: India Security Brokerage Market Report 2034
- Trustpilot: Zerodha (1.7/5, 2800+ reviews), Upstox (1.6/5), Groww (2.1/5)
- Storyboard18: Investor Exodus Report (Aug 2025)
- NSE: Monthly Active Client Data (2025-26)
- Angel One: FY25 Annual Report
- Zerodha: FY25 Financial Disclosures
- Sensibull: Feature documentation and pricing pages
- Streak: Feature documentation and pricing pages
- TradingView: India pricing and feature documentation
- Smallcase: Platform documentation and manager directory
- Dhan: Product pages, DhanHQ API documentation
- Fyers: Product pages, API v3 documentation
- 5Paisa: Pricing and feature documentation
- FreePressJournal: Zerodha outage report
- Reddit: r/IndianStreetBets, r/IndianStockMarket community discussions
- SEBI: Algo Trading Circular (effective Apr 1, 2026)
- SEBI: F&O Lot Size and Expiry Regulations (Nov 2024)
