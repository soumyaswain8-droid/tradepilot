# TradePilot v5 — The Machine

## Data Layer (6 sources)
### yfinance
- NSE/BSE OHLCV
- 5-min intraday candles
- 60 days history
### nsepython
- FII/DII daily flows
- Options chain + PCR
### Google News RSS
- Live market news
- Sentiment detection
### NSE CSV Files
- 2,400+ stock files
- 2 years daily OHLCV
### Cross-Asset Data
- DXY (US Dollar)
- Brent Crude Oil
- Gold Futures
- Bitcoin
- S&P 500
- US 10Y Yield
### Shoonya (planned)
- 1 year 1-min candles
- 50 Nifty stocks

## Signal Layer (12 sources)
### Original 7 Signals
#### ML Engine (25%)
- LightGBM regression
- 22 features
- Walk-forward IC: 0.03
- 803 lines
#### Relative Strength (20%)
- Stock vs Nifty 5d/20d
#### ORB Breakout (15%)
- First 15-min high/low
- 60-89% directional accuracy
#### VWAP Position (10%)
- Institutional reference price
#### FII/DII Flow (10%)
- nsepython live data
- 3d/5d rolling signal
#### Options OI (10%)
- Long/short buildup
- PCR signal
#### Volume (10%)
- Today vs 20-day average

### NEW 5 Signals (built Day 3-4)
#### Alpha Hunter
- Sector rotation scanner
- 10 sectors monitored
- Deploys into counter-trend winners
- Activates at 10:00 AM on BEAR days
- 672 lines
#### Cross-Asset
- DXY, Crude, Gold, BTC
- S&P 500, US 10Y yield
- FII flow predictor
- Risk-off score
- 358 lines
#### Market Breadth
- % above 20/50/200-DMA
- Advance/Decline ratio
- New 52-week highs/lows
- Contrarian signals
- 460 lines
#### Options PCR + IV Skew
- Put-Call ratio extremes
- IV skew (fear premium)
- PCR > 1.3 = contrarian BUY
- PCR < 0.5 = contrarian SELL
- 438 lines
#### Calendar + Enhanced Tech
- Monday effect
- Expiry week (Tuesday)
- Williams %R, CMF, CCI
- ATR percentile
- 52-week distance
- 289 lines

## Decision Layer
### Regime Detector (417L, 8 dependents)
- HMM + 6 indicators
- BULL / BEAR / SIDEWAYS
- Score -6 to +6
- Drives allocation %
- Drives short signals
- Drives Alpha Hunter
### Pre-Market Intel (374L)
- GIFT Nifty gap prediction
- FII flow signal
- Global sentiment (S&P, Asia)
- Runs at 8:30 AM
### Signal Engine (259L)
- BUY signals (top 20%)
- SELL signals (bottom 20%)
- HOLD (middle 60%)
- Regime-aware filtering
### Composite Scorer (580L, 5 dependents)
- 7-signal weighted scoring
- Ranks all 201 stocks
- Relative ranking (not absolute)
- Always produces 10+ BUY signals

## Risk Layer
### Risk Manager (595L)
- Tier 1: 5 losses → pause pool
- Tier 2: 3 same stock → ban
- Tier 3: Daily > 1% → all 50%
- Tier 4: Weekly > 3% → pause
- Tier 5: Monthly > 7% → ALL STOP
### Pool Manager (337L)
- INTRADAY 30%
- SWING 25%
- POSITIONAL 25%
- INVESTMENT 15%
- RESERVE 5%
- Regime-based allocation shifts
- Profit waterfall monthly
### Position Sizer (288L)
- Half-Kelly criterion
- VIX-based: min(15/VIX, 1.0)
- Max 25% per stock
- Score-weighted allocation

## Execution Layer (4 Engines)
### v4 Engine (727L)
- Rs 10L, carry-forward
- Long-only
- Composite scorer
- 3-day: Rs -19,279
### v5 Engine (692L) ★ WINNER
- Rs 10L, carry-forward
- Long + Short
- Multi-pool
- Alpha Hunter at 10 AM
- Telegram alerts
- 3-day: Rs +54,783
### v5.2 F&O (548L)
- Rs 10L, carry-forward
- 4 Options strategies
- Protective puts
- Straddle selling
- 3-day: Rs -56,180
### v5.3 Staged Entry (1163L)
- Rs 10L, carry-forward
- 3-tier conviction
- Live price confirmation
- ORB + VWAP + Volume gates
- 3-day: Rs 0

## Output Layer
### Telegram Bot (424L)
- /status command
- /regime command
- Trade entry alerts
- Trade exit alerts
- Circuit breaker alerts
- Daily summary at 3:30 PM
### Web Dashboard (1851L)
- Stocks tab
- Gainers (index filters)
- F&O (Groww-style)
- Intraday (redesigned)
- AI Picks + Chat
- Trade Lab (v4 vs v5)
- Intel (live news)
- Paper Trade
### PDF Reports
- Daily summary
- Trade analysis + charts
- Candlestick with markers
- Performance papers
- Upgrade roadmaps
### DevPilot DB
- 79 learnings
- 7 sprints
- 99 tasks
- All findings persisted

## Stats
### Code
- 15,937 total lines
- 34 files
- 17 modules
### Data
- 201 stocks (Nifty 200)
- 2,400+ CSV files
- 201 intraday files
### Trading
- 12 signal sources
- 4 parallel engines
- Rs 10L each
- 20-session validation (Day 3/20)
### Intelligence
- 79 learnings in DB
- 2 watchdog agents
- Daily improvement loop
