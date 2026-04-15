# TradePilot v6 -- The Machine

*Master Plan: From Paper Trading to Market Domination*

**Author:** Soumya Swain | soumya@devpilot.co.in
**Date:** April 12, 2026
**Version:** v1.0
**Status:** Planning

---

## 1. Where We Are (Evolution Summary)

| Version | What It Does | Lines | Status |
|---------|-------------|------:|--------|
| v3 | ML classification, regime-aware | ~1,500 | Retired |
| v4 | 7-signal composite scorer, long-only | ~2,100 | Live (paper) |
| v5 | Multi-pool + shorts + regime + risk | ~4,800 | Live (paper) |
| v5.2 | F&O options experiment | ~1,300 | Live (paper) |
| **v6** | **The Machine** | **~15,000 est** | **Planning** |

### 2-Day Paper Trading Results

- **v4:** Rs -19,279 (Day 1 bear: -30K, Day 2 bull: +11K)
- **v5:** Rs +38,986 (Day 1: -1.5K, Day 2: +40K)

v5 proved the thesis: **regime detection + shorts + risk management = profitable**.

---

## 2. v6 Vision: "The Machine"

v6 is NOT a bigger v5. It is a fundamentally different architecture.

> **v5 = Rule-based system with ML assistance**
> **v6 = Multi-agent AI system with rule-based safety rails**

### Architecture Overview

```
ORCHESTRATOR (Master Agent)
  Coordinates all agents, manages state, kills bad trades, enforces risk limits

SIGNAL AGENTS (4 parallel):
  - Technical Agent (ML+TA)
  - Sentiment Agent (LLM+NLP)
  - Institutional Flow Agent (FII/DII/Insider)
  - Cross-Asset Agent (Bonds, USD/INR, Crude, Gold)

RISK AGENT
  - Regime detection (HMM + 8 indicators)
  - VIX-based sizing
  - Cross-strategy correlation guard
  - Portfolio VaR/CVaR limits
  - Kill switch

EXECUTION AGENT
  - Zerodha Kite API (live orders)
  - Smart order routing (limit vs market)
  - Slippage minimization
  - Order deduplication + audit trail

PORTFOLIO AGENT
  - Multi-strategy allocation (equity + F&O + hedge)
  - Kelly-optimal position sizing
  - Dynamic rebalancing
  - Tax-aware profit booking (STCG vs LTCG)

MARKETS:
  NSE 500 Equity + Index F&O + Stock F&O +
  Commodities (Gold, Crude) + Currency (USD/INR)

DATA LAYER:
  Real-time ticks (WebSocket) + News (LLM sentiment) +
  FII/DII + Insider trades + Delivery % +
  Options chain + Cross-asset prices +
  Google Trends + Alternative data
```

---

## 3. The Reality Check

The OpenAI "$9K to $90K" story is cherry-picked backtests, not a real product.

### What ACTUALLY works at top quant funds

- **Renaissance:** Signal processing + HMM + statistical arbitrage (Sharpe ~2.0)
- **Two Sigma:** Gradient boosting on alternative data (15-20% annual)
- **Citadel:** ML for execution optimization

No LLM makes trading decisions. The AI is infrastructure, not the decision-maker.

### Our Realistic Targets

| Metric | Target | World-class? |
|--------|--------|:------------:|
| Sharpe ratio | 1.5-2.0 | Yes (top 1% of hedge funds) |
| Annual return | 25-40% | Yes (beats 99% of mutual funds) |
| Max drawdown | <15% | Yes (institutional grade) |
| Win rate | 60%+ | Yes (with proper R:R) |
| Profit ratio | 80% days profitable | Ambitious but achievable |

---

## 4. Six Strategy Layers

v6 deploys ALL six simultaneously.

### Layer 1: Technical Momentum/Reversion (v4/v5 evolved)

- LightGBM + TFT + LSTM ensemble on 500 stocks
- Dynamic blend: momentum in BULL, mean-reversion in BEAR
- Intraday (ORB, VWAP) + Swing (3-7d) + Positional (2-4wk)
- **Expected Sharpe: 1.0-1.5**

### Layer 2: Sentiment Alpha (NEW in v6)

- Claude/Llama sentiment scoring of news headlines + earnings calls
- 74% directional accuracy per research (Sharpe 3.05 in papers)
- Sources: MoneyControl, Economic Times, BSE announcements
- Contrarian at extremes (panic sell = buy signal)
- **Expected Sharpe: 1.5-3.0 (supplementary)**

### Layer 3: Institutional Flow (v5 enhanced)

- FII/DII daily net flow -- 1-3 day lead indicator
- Delivery percentage spikes -- institutional accumulation signal
- Insider buying clusters -- 11.2% annual alpha
- Bulk/block deal following
- **Expected Sharpe: 0.8-1.3**

### Layer 4: Cross-Asset Signals (NEW in v6)

- India 10Y bond yield changes -- equity sector rotation
- USD/INR trend -- FII flow prediction
- Crude oil spikes -- negative for Indian equities
- Gold rally + equity fall -- risk-off regime
- US market overnight -- gap prediction
- **Expected Sharpe: 0.8-1.2 (overlay)**

### Layer 5: Options Premium Harvesting (v5.2 evolved)

- Weekly expiry straddle/strangle selling on Nifty/BankNifty
- IV consistently exceeds realized vol by 20-30% in India
- Protective puts during BEAR regime
- Covered calls on profitable SWING holdings
- **Expected Sharpe: 1.0-2.0**

### Layer 6: Pairs/Statistical Arbitrage (NEW in v6)

- Cointegrated pairs within sectors (e.g., TCS-INFY, HDFCBANK-ICICIBANK)
- Market-neutral: profit regardless of market direction
- 4.97% annual on Nifty 50 pairs (from research)
- **Expected Sharpe: 1.5-2.5 (market-neutral)**

---

## 5. Technology Stack

| Component | Tool | Why |
|-----------|------|-----|
| Live execution | Zerodha Kite Connect (Rs 2K/month) | Best reliability, Python SDK |
| Tick data | Kite WebSocket (3000 instruments) | Real-time, ~1sec latency |
| Historical data | QuestDB (tick storage) + DuckDB (analytics) | ASOF JOIN, fastest ingestion |
| ML training | LightGBM + neuralforecast (TFT/LSTM) | Proven, M1 Mac compatible |
| Sentiment | Claude API + local Llama 3.1 (Ollama) | Best accuracy + fallback |
| Feature store | DuckDB + Parquet files | Zero infra cost, AES-256 |
| Backtesting | vectorbt (research) + custom event-driven | Speed + accuracy |
| Monitoring | Grafana + Telegram bot | Real-time dashboards + alerts |
| Server | AWS Mumbai (ap-south-1) | Low latency to NSE, SEBI compliant |
| CI/CD | GitHub Actions | Auto-deploy on push |

---

## 6. Go-Live Checklist

| Step | What | Timeline | Status |
|-----:|------|----------|--------|
| 1 | Complete 20-session paper validation | 2 more weeks | In progress |
| 2 | Open Zerodha API account (Rs 2K/month) | 1 day | TODO |
| 3 | SEBI algo registration | 2-4 weeks | TODO |
| 4 | Build execution agent (Kite API wrapper) | 1 week | TODO |
| 5 | Shadow mode (log orders, don't execute) | 1 week | TODO |
| 6 | Live with 1 lot (tiny size, real money) | 2 weeks | TODO |
| 7 | Scale to full capital | After 1 month live | TODO |

---

## 7. Implementation Phases

### Phase 1: Foundation (Weeks 1-4) -- "Make It Work"

- Complete 20-session v5 paper validation
- Open Shoonya account, download 1 year intraday data
- Retrain ML ensemble (LightGBM + TFT + LSTM) with intraday features
- Build cross-asset signal overlay (bonds, crude, USD/INR)
- Add delivery percentage to signal engine
- **Target: Sharpe > 1.0, 60%+ win rate on paper**

### Phase 2: Intelligence (Weeks 5-8) -- "Make It Smart"

- LLM sentiment layer (Claude API for news scoring)
- Insider buying data from SEBI filings
- Pairs trading module (cointegrated Nifty 200 pairs)
- Enhanced options strategies (volatility selling)
- Multi-agent orchestrator (coordinate all signal agents)
- **Target: Sharpe > 1.5, 65%+ win rate**

### Phase 3: Execution (Weeks 9-12) -- "Make It Real"

- Zerodha Kite API integration
- Smart order routing (limit for liquid, market for urgent)
- Shadow mode testing (2 weeks)
- SEBI algo registration
- Kill switch + audit trail
- AWS Mumbai deployment
- **Target: Live with 1 lot, no catastrophic bugs**

### Phase 4: Scale (Weeks 13-20) -- "Make It Bigger"

- Scale from 1 lot to full capital
- Add Grafana real-time P&L dashboard
- Commodities module (gold, crude)
- Currency hedging (USD/INR)
- Tax optimization engine (STCG/LTCG awareness)
- Public API for future subscribers
- **Target: 25-40% annual return, Sharpe > 1.5**

---

## 8. Risk Management (Non-Negotiable)

| Rule | Limit | Why |
|------|-------|-----|
| Daily max loss | 2% of capital | Survive any single day |
| Weekly max loss | 5% of capital | Survive any bad week |
| Monthly max loss | 10% of capital | Kill switch trigger |
| Single position max | 10% of capital | Diversification |
| Max leverage (F&O) | 3x | Don't blow up |
| Max correlated positions | 3 from same sector | Concentration risk |
| Kill switch | Auto at -2% daily | Hard stop, no override |
| Recovery ladder | 25/50/75/100% over 15 days | Don't revenge trade |

---

## 9. Competitive Analysis

| Feature | Zerodha | Groww | Angel | **TradePilot v6** |
|---------|:-------:|:-----:|:-----:|:-----------------:|
| Stock trading | Yes | Yes | Yes | Yes (via Kite) |
| F&O | Yes | No | Yes | Yes + AI strategies |
| Algo trading | Manual | No | Basic | **Full AI-powered** |
| Regime detection | No | No | No | **HMM + 8 indicators** |
| Short signals | Manual | No | No | **Auto-generated** |
| Risk management | Basic SL | Basic | Basic | **5-tier breakers** |
| Sentiment analysis | No | No | No | **LLM-powered** |
| Multi-strategy | No | No | No | **6 layers** |
| Cross-asset | No | No | No | **Bonds, crude, FX** |
| Paper trading | Streak | No | No | **Built-in** |

---

## 10. Revenue Model (Phase 2: Public Offering)

After proving the system works (6+ months live track record):

| Tier | Price | What They Get |
|------|------:|---------------|
| Free | Rs 0 | Market data, basic signals, paper trading |
| Pro | Rs 999/mo | Full v6 signals, regime alerts, Telegram bot |
| Algo | Rs 4,999/mo | API access, auto-execution, all strategies |
| Enterprise | Custom | White-label, custom strategies, dedicated support |

**Target:** 1,000 paying users at avg Rs 2,000/month = **Rs 20L MRR**

---

## 11. Why We Win

1. **We built the system before raising money** -- 6,600 lines of battle-tested code
2. **We have live paper trading data** -- not backtests, real market decisions
3. **Multi-strategy diversification** -- 6 layers, not dependent on one approach
4. **India-first** -- FII/DII, delivery %, F&O expiry patterns are our unique edge
5. **AI as infrastructure, not hype** -- regime detection + risk management, not "GPT picks stocks"
6. **Bootstrapped, profitable, then scale** -- same DevPilot philosophy

---

*TradePilot v6 -- The Machine. Built by traders, for traders.*

Soumya Swain | soumya@devpilot.co.in
