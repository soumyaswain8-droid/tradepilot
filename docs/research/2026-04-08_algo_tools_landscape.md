# Algorithmic Trading Tools Landscape (India + Global) -- April 2026

## 1. Backtesting Frameworks

| Framework | Language | Speed | Live Trading | India Support | Free | Key Limitation |
|-----------|----------|-------|:------------:|:-------------:|:----:|----------------|
| **vectorbt** | Python | Fastest (NumPy+Numba vectorized) | No | Generic (works with any OHLCV) | Yes | Python 3.5-3.6 era; install issues on newer Python. PRO version is paid |
| **backtesting.py** | Python | Fast | No | Generic | Yes | No live trading, no broker integration. Research-only |
| **Backtrader** | Python | Moderate (event-driven) | Yes (IB, Oanda) | Via custom broker adapters | Yes | Maintainer inactive since 2021. Community forks exist |
| **Zipline-reloaded** | Python | Moderate | No | Needs custom data bundles | Yes | Heavy Quantopian legacy. Complex data pipeline setup |
| **NautilusTrader** | Rust+Python | Very fast (Rust core) | Yes (IB, Binance, Betfair) | Via custom adapters | Yes | Steep learning curve. Overkill for simple strategies |
| **QuantConnect Lean** | C#/Python | Fast (cloud or local) | Yes (IB, TD, Coinbase) | NSE data available on QC cloud | Free tier | C# primary. Python support is secondary. Cloud lock-in risk |
| **bt** | Python | Fast (vectorized) | No | Generic | Yes | Less popular, smaller community |

**Recommendation for TradePilot**: vectorbt for fast research/parameter sweeps, Backtrader or NautilusTrader for live execution path.

**Repos**:
- vectorbt: github.com/polakowo/vectorbt (7.1K stars)
- backtesting.py: github.com/kernc/backtesting.py (8.2K stars)
- Backtrader: github.com/mementum/backtrader (14K stars)
- NautilusTrader: github.com/nautechsystems/nautilus_trader (4.5K stars)
- Zipline-reloaded: github.com/stefan-jansen/zipline-reloaded
- QuantConnect Lean: github.com/QuantConnect/Lean (18.3K stars)

---

## 2. Live Data Feeds for India (NSE/BSE)

| Broker API | Free Tier | WebSocket | Historical Data | Rate Limits | Key Strength |
|------------|:---------:|:---------:|-----------------|-------------|-------------|
| **Zerodha Kite Connect** | Free (personal, no market data) | Yes (3000 instruments) | 10yr intraday (paid plan) | 60 quotes/min, 120 hist/min, 5000 orders/day | Largest ecosystem, best docs |
| **Dhan API** | Free (all users) | Yes | Yes (included free) | Moderate | Zero API cost, fast execution, great for intraday |
| **Angel One SmartAPI** | Free | Yes | Yes (included) | Moderate | Easiest onboarding, free everything |
| **Upstox API v2** | Free | Yes | Yes | Moderate | Clean REST API, good Python SDK |
| **Flattrade API** | Free + zero brokerage | Yes | Yes | Moderate | Cheapest overall (zero brokerage + free API) |
| **Breeze (ICICI)** | Free with demat | Yes | Limited | Conservative | Bank-backed, good for delivery |
| **Fyers API** | Free | Yes | Yes | Moderate | Good charting, free API |

**Paid plan**: Zerodha Kite Connect full suite = Rs 500/month (includes historical data + WebSocket).

**Recommendation for TradePilot**: Dhan (free, fast, good WebSocket) or Angel One SmartAPI (free, easy) for development. Zerodha for production (largest liquidity, best docs).

---

## 3. Portfolio Optimization

| Library | What It Does | Free | Key Feature | Limitation |
|---------|-------------|:----:|-------------|------------|
| **PyPortfolioOpt** | Mean-variance, Black-Litterman, HRP, shrinkage | Yes | Scikit-learn style API, excellent docs | No regime-aware optimization |
| **Riskfolio-Lib** | 20+ risk measures, factor models, worst-case optimization | Yes | Most comprehensive. CVaR, CDaR, Kelly, nested clustering | Steep learning curve for advanced features |
| **skfolio** | Portfolio optimization on scikit-learn pipeline | Yes | ML-native, cross-validation for portfolios | Newer, smaller community |
| **cvxpy** | Raw convex optimization solver | Yes | Full control over custom constraints | Not finance-specific, you build everything |

**Repos**:
- PyPortfolioOpt: github.com/PyPortfolio/PyPortfolioOpt (4.5K stars)
- Riskfolio-Lib: github.com/dcajasn/Riskfolio-Lib (3K stars)
- skfolio: github.com/skfolio/skfolio (1.2K stars)

**Recommendation**: PyPortfolioOpt for quick prototyping. Riskfolio-Lib when you need HRP, nested clustering, or CVaR constraints.

---

## 4. Execution & Broker APIs (India Rankings)

| Rank | Broker | Latency | Bracket/Cover Orders | API Cost | Best For |
|:----:|--------|---------|:--------------------:|----------|---------|
| 1 | **Dhan** | Low (~50ms) | Yes | Free | Intraday algo traders, API-first design |
| 2 | **Zerodha** | Low | Yes (GTT, BO deprecated) | Rs 500/mo | Production systems, largest ecosystem |
| 3 | **Fyers** | Low | Yes | Free | Free API with good data |
| 4 | **Angel One** | Moderate | Limited | Free | Beginners, free SmartAPI |
| 5 | **Upstox** | Moderate | Yes | Free | Clean API, good SDK |
| 6 | **Flattrade** | Moderate | Yes | Free + 0 brokerage | Cost-minimization |

**Note**: Zerodha deprecated Bracket Orders in 2020. Use GTT (Good Till Triggered) + manual stop management instead. Dhan and Fyers still support bracket orders natively.

---

## 5. Real-Time Screening Tools

| Tool | Type | Free Tier | India NSE/BSE | API/Webhook | Key Strength |
|------|------|:---------:|:-------------:|:-----------:|-------------|
| **Chartink** | Technical screener | Yes (scans free, alerts Rs 780/mo) | NSE only | Webhook alerts (linkable to OpenAlgo) | Best free technical screener for India. 100+ indicators |
| **Trendlyne** | Fundamental + technical | Limited free | NSE + BSE | Limited | DVM scoring, 1400+ parameters, SEBI registered |
| **Screener.in** | Fundamental | Yes (generous) | NSE + BSE | No API | Best free fundamental screener. Custom queries |
| **TradingView** | Charting + screening | Free (limited) | Global + NSE | Pine Script alerts + webhooks | Best charting. Webhook to OpenAlgo/broker |
| **PKScreener** | AI-powered scanner | Yes (open source) | NSE | CLI tool | GitHub: pkjmesra/PKScreener. AI predictions |

**Recommendation**: Chartink webhooks + OpenAlgo for automated signal-to-order pipeline. Screener.in for stock universe filtering.

---

## 6. Data Warehousing for Tick Data

| Database | Type | Ingestion Speed | Query Speed | Free | Best For | Limitation |
|----------|------|:--------------:|:-----------:|:----:|---------|------------|
| **QuestDB** | Purpose-built TSDB | Fastest (12-36x InfluxDB) | Fastest (ASOF JOIN native) | Yes (OSS) | Tick data, market data, HFT analytics | Smaller ecosystem than Postgres |
| **TimescaleDB** | Postgres extension | Good (hypertable) | Good (Hypercore columnar) | Yes (community) | Teams already on Postgres. Familiar SQL | No ASOF JOIN. Row-based hot storage slower |
| **InfluxDB 3.0** | Column-native TSDB | Good | Good for simple queries | Core: free | IoT/observability crossover | Complex analytics slower than QuestDB |
| **DuckDB** | In-process OLAP | N/A (file-based) | Very fast analytics | Yes | Local analysis, Parquet/CSV crunching, backtesting | Not a server DB. No concurrent writes |

**2026 Update**: QuestDB added matured SQL support. DuckDB v1.4 added AES-256 encryption. TimescaleDB has Hypercore (hybrid row-columnar). InfluxDB 3.0 Core went GA.

**Recommendation for TradePilot**: QuestDB for tick storage (ASOF JOIN is critical for financial data). DuckDB for local backtesting analytics on Parquet files.

---

## 7. Feature Engineering Libraries

| Library | Indicators | Speed | Install Ease | Key Feature | Limitation |
|---------|:----------:|-------|:------------:|-------------|------------|
| **TA-Lib** | 150+ | Fastest (C core) | Hard (C dependency) | Industry standard, candlestick patterns | Windows install nightmare. No pip-only |
| **pandas-ta** | 150+ (+ 60 candlestick w/ TA-Lib) | Fast (Numba) | Easy (pip) | Pure Python, Pandas native, most comprehensive | Some indicators differ slightly from TA-Lib |
| **finta** | 80+ | Moderate | Easy (pip) | Lightweight, simple API | Fewer indicators, less maintained |
| **ta** (Python) | 40+ | Moderate | Easy (pip) | Simple, well-documented | Limited indicator set |
| **tsfresh** | 800+ time-series features | Slow (exhaustive) | Easy (pip) | Automatic feature extraction for ML | Not finance-specific. Overkill for simple TA |

**Repos**:
- TA-Lib: github.com/TA-Lib/ta-lib-python
- pandas-ta: github.com/twopirllc/pandas-ta (5K stars)
- finta: github.com/peerchemist/finta (2.1K stars)
- tsfresh: github.com/blue-yonder/tsfresh (8.5K stars)

**Recommendation**: pandas-ta as primary (pure Python, easy install, comprehensive). TA-Lib as optional accelerator if C dependency is manageable.

---

## 8. Monitoring & Alerting

| Tool | Purpose | Free | Integration | Key Feature |
|------|---------|:----:|-------------|-------------|
| **Grafana** | P&L dashboards, portfolio visualization | Yes (OSS) | Postgres, QuestDB, InfluxDB, TimescaleDB | Best open-source dashboarding. Real-time refresh |
| **Telegram Bot API** | Trade alerts, signal notifications | Yes | Python (python-telegram-bot) | Instant mobile alerts, group channels |
| **Discord Webhooks** | Team alerts, strategy monitoring | Yes | Simple HTTP POST | Rich embeds, thread-based discussion |
| **Ntfy** | Self-hosted push notifications | Yes (OSS) | HTTP POST / curl | No app needed, works on any device |

**Recommendation**: Grafana + QuestDB for P&L dashboards. Telegram bot for trade alerts (most Indian traders use Telegram).

---

## 9. India-Specific Platforms

### OpenAlgo (Open Source -- Most Important for TradePilot)

| Attribute | Detail |
|-----------|--------|
| **What** | Self-hosted algo trading platform, unified API across 30+ Indian brokers |
| **GitHub** | github.com/marketcalls/openalgo (1.6K stars) |
| **Stack** | Python Flask + React frontend |
| **Brokers** | Zerodha, Dhan, Angel One, Upstox, Fyers, Flattrade, ICICI, Kotak, 5paisa, Shoonya, Aliceblue, and 15+ more |
| **Key Feature** | 40 unified REST APIs. Connect TradingView/Chartink/Amibroker signals to any broker |
| **2026 Roadmap** | Rust desktop app, Flutter mobile app, AI/LLM integration |
| **License** | AGPL-3.0 |
| **Limitation** | Self-hosted only. No cloud offering. Requires Python/Flask knowledge |

### AlgoTest

| Attribute | Detail |
|-----------|--------|
| **What** | Backtesting-first platform, specializing in options strategies |
| **URL** | algotest.in |
| **Free Tier** | Free backtesting for options. Paid for live execution |
| **Key Feature** | India's best options backtesting. Pre-built strategy templates |
| **Limitation** | Primarily options-focused. Limited equity strategy support |

### Tradetron

| Attribute | Detail |
|-----------|--------|
| **What** | No-code visual strategy builder + marketplace |
| **URL** | tradetron.tech |
| **Pricing** | Rs 1,000-3,000+/month |
| **Key Feature** | Strategy marketplace (deploy others' strategies). Multi-broker |
| **Limitation** | Monthly cost adds up. Limited customization vs code-based |

### StockMock

| Attribute | Detail |
|-----------|--------|
| **What** | India's first intraday options backtesting platform (Nifty/BankNifty) |
| **URL** | stockmock.in |
| **Free Tier** | Limited free backtests |
| **Key Feature** | Time-based backtesting for index options. Very granular |
| **Limitation** | Backtesting only, no live execution. Index options only |

---

## 10. Free NSE Data Sources

| Source | Data Type | Depth | API | GitHub |
|--------|-----------|-------|:---:|--------|
| **jugaad-data** | NSE daily OHLCV, derivatives, indices | 20+ years | Python lib | github.com/jugaad-py/jugaad-data |
| **OpenChart** | 1-min candle data NSE/NFO | Recent | REST | github.com/marketcalls/openchart |
| **nse-stock-data** | Nifty/BankNifty 1-min intraday | 5+ years pre-downloaded | CSV files | github.com/aeron7/nifty-banknifty-intraday-data |
| **yfinance** | Global + NSE (.NS suffix) | 20+ years daily, 7d intraday | Python lib | github.com/ranaroussi/yfinance |
| **NSEpy** | NSE historical + derivatives | 10+ years | Python lib | github.com/swapniljariwala/nsepy |

---

## Recommended Stack for TradePilot

| Layer | Tool | Why |
|-------|------|-----|
| **Data ingestion** | Dhan API (free) + jugaad-data (historical) | Zero cost, good WebSocket |
| **Tick storage** | QuestDB | ASOF JOIN, fastest ingestion |
| **Backtesting** | vectorbt (research) + Backtrader (event-driven) | Speed + live-trading path |
| **Feature engineering** | pandas-ta + TA-Lib (optional) | Comprehensive, easy install |
| **Portfolio optimization** | PyPortfolioOpt | Simple, well-documented |
| **Execution** | OpenAlgo (broker abstraction) | 30+ brokers, one API |
| **Screening** | Chartink webhooks + custom scanner | Free, webhook to OpenAlgo |
| **Analytics** | DuckDB (local) + Grafana (dashboards) | Zero infra cost |
| **Alerts** | Telegram bot | What Indian traders use |
| **Live broker** | Zerodha (production) / Dhan (dev) | Best liquidity / free dev |

---

*Research date: April 8, 2026. Sources verified via web search.*
