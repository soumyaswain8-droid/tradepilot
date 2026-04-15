# TradePilot — System Mind Map

*15,937 lines | 34 files | 12 signals | 4 engines | 201 stocks | 79 learnings*

---

## System Overview

```
                        ┌─────────────────────────────┐
                        │     TRADEPILOT PLATFORM      │
                        │   "The Machine" — v5 Engine  │
                        │   7,795 lines core engine    │
                        └──────────────┬──────────────┘
                                       │
          ┌────────────────────────────┼────────────────────────────┐
          │                            │                            │
    ┌─────▼─────┐              ┌──────▼──────┐              ┌─────▼─────┐
    │   DATA    │              │  INTELLIGENCE│              │  OUTPUT   │
    │  LAYER    │              │    LAYER     │              │  LAYER    │
    └─────┬─────┘              └──────┬──────┘              └─────┬─────┘
          │                           │                           │
     6 Sources                   5 Layers                    5 Channels
```

---

## Layer 1: DATA SOURCES (6)

```
┌──────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                             │
├───────────┬───────────┬──────────┬──────────┬────────┬──────────┤
│ yfinance  │nsepython  │Google RSS│ NSE CSV  │Cross-  │ Shoonya  │
│           │           │          │          │Asset   │ (future) │
│ NSE/BSE   │ FII/DII   │ Live     │ 2,400+   │DXY/BTC │ 1-min    │
│ OHLCV     │ Options   │ News     │ files    │Crude/  │ candles  │
│ Intraday  │ Chain     │ Feed     │ Daily    │Gold/S&P│ 1 year   │
│ 5-min     │ PCR       │          │ History  │US 10Y  │          │
└─────┬─────┴─────┬─────┴────┬─────┴────┬─────┴───┬────┴────┬─────┘
      │           │          │          │         │         │
      ▼           ▼          ▼          ▼         ▼         ▼
  data_nse.py  fii_feed.py  app.py   ml_engine  cross_    shoonya_
  (669 lines)  (371 lines)  (news)   (803 lines) asset.py download.py
                                                 (358 L)  (269 lines)
```

---

## Layer 2: SIGNALS (12 sources)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      SIGNAL SOURCES (12)                            │
├─────────────────────────────┬───────────────────────────────────────┤
│   ORIGINAL 7 (from v4)     │   NEW 5 (built Day 3-4)              │
├─────────────────────────────┼───────────────────────────────────────┤
│                             │                                       │
│  ┌─────────────────────┐   │  ┌────────────────────────────────┐   │
│  │ 1. ML Engine    25% │   │  │ 8. Alpha Hunter                │   │
│  │    LightGBM         │   │  │    Sector rotation scanner     │   │
│  │    22 features      │   │  │    Deploys into counter-trend  │   │
│  │    Walk-forward     │   │  │    winners on bear days        │   │
│  │    IC: 0.03         │   │  │    672 lines                   │   │
│  └─────────────────────┘   │  └────────────────────────────────┘   │
│  ┌─────────────────────┐   │  ┌────────────────────────────────┐   │
│  │ 2. Relative Str 20% │   │  │ 9. Cross-Asset                 │   │
│  │    5d/20d vs Nifty  │   │  │    DXY, Crude, Gold, BTC       │   │
│  └─────────────────────┘   │  │    S&P 500, US 10Y yield       │   │
│  ┌─────────────────────┐   │  │    358 lines                   │   │
│  │ 3. ORB         15% │   │  └────────────────────────────────┘   │
│  │    15-min breakout  │   │  ┌────────────────────────────────┐   │
│  └─────────────────────┘   │  │ 10. Market Breadth              │   │
│  ┌─────────────────────┐   │  │     % above 20/50/200-DMA      │   │
│  │ 4. VWAP        10% │   │  │     A/D ratio, new highs/lows  │   │
│  │    Institutional    │   │  │     Contrarian signals          │   │
│  └─────────────────────┘   │  │     460 lines                  │   │
│  ┌─────────────────────┐   │  └────────────────────────────────┘   │
│  │ 5. FII/DII     10% │   │  ┌────────────────────────────────┐   │
│  │    nsepython live   │   │  │ 11. Options PCR + IV Skew       │   │
│  └─────────────────────┘   │  │     Put-Call ratio extremes     │   │
│  ┌─────────────────────┐   │  │     Fear premium detection      │   │
│  │ 6. Options OI  10% │   │  │     438 lines                  │   │
│  │    OI buildup       │   │  └────────────────────────────────┘   │
│  └─────────────────────┘   │  ┌────────────────────────────────┐   │
│  ┌─────────────────────┐   │  │ 12. Calendar + Enhanced Tech    │   │
│  │ 7. Volume      10% │   │  │     Monday effect, expiry week  │   │
│  │    Confirmation     │   │  │     Williams %R, CMF, CCI       │   │
│  └─────────────────────┘   │  │     289 lines                  │   │
│                             │  └────────────────────────────────┘   │
└─────────────────────────────┴───────────────────────────────────────┘
```

---

## Layer 3: DECISION ENGINE

```
┌─────────────────────────────────────────────────────────────────┐
│                      DECISION ENGINE                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Regime Detector (417 lines)                              │   │
│  │ HMM + 6 indicators → BULL / BEAR / SIDEWAYS              │   │
│  │ Drives: allocation %, short signals, alpha hunter         │   │
│  │ Hub node: 8 modules depend on this                        │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │ Pre-Market Intel (374 lines)                             │   │
│  │ GIFT Nifty gap + FII flow + Global sentiment             │   │
│  │ Runs at 8:30 AM before market open                        │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │ Signal Engine (259 lines)                                │   │
│  │ BUY (long) + SELL (short) + HOLD signals                 │   │
│  │ Regime-aware: BEAR = more shorts, BULL = more longs      │   │
│  └──────────────────────┬───────────────────────────────────┘   │
│                         │                                       │
│  ┌──────────────────────▼───────────────────────────────────┐   │
│  │ Composite Scorer (580 lines)                             │   │
│  │ 7-signal weighted scoring → rank all 201 stocks          │   │
│  │ Top 20% = BUY, Bottom 20% = SELL, Middle = HOLD         │   │
│  │ Hub node: 5 modules depend on this                        │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 4: RISK MANAGEMENT

```
┌─────────────────────────────────────────────────────────────────┐
│                      RISK MANAGEMENT                            │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Risk Manager (595 lines) — 5-Tier Circuit Breakers       │   │
│  │                                                          │   │
│  │  Tier 1: 5 consecutive losses → pause pool               │   │
│  │  Tier 2: 3 losses same stock → ban stock for day         │   │
│  │  Tier 3: Daily loss > 1% → reduce ALL pools 50%          │   │
│  │  Tier 4: Weekly loss > 3% → pause intraday + swing       │   │
│  │  Tier 5: Monthly loss > 7% → ALL-STOP                    │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌──────────────────────┐  ┌────────────────────────────────┐   │
│  │ Pool Manager (337L)  │  │ Position Sizer (288L)          │   │
│  │                      │  │                                │   │
│  │ INTRADAY  30%        │  │ Kelly Criterion (half-Kelly)   │   │
│  │ SWING     25%        │  │ VIX-based: min(15/VIX, 1.0)   │   │
│  │ POSITIONAL 25%       │  │ Max 25% per stock              │   │
│  │ INVESTMENT 15%       │  │ Score-weighted allocation      │   │
│  │ RESERVE    5%        │  │                                │   │
│  └──────────────────────┘  └────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Layer 5: EXECUTION (4 Engines in Parallel)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   EXECUTION ENGINES (Rs 10L each, carry-forward)        │
│                                                                         │
│  ┌──────────────┐ ┌───────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │   v4 ENGINE   │ │  v5 ENGINE    │ │ v5.2 F&O     │ │ v5.3 STAGED  │  │
│  │   727 lines   │ │  692 lines    │ │ 548 lines    │ │ 1163 lines   │  │
│  ├──────────────┤ ├───────────────┤ ├──────────────┤ ├──────────────┤  │
│  │ Long-only    │ │ Long + Short  │ │ 4 Options    │ │ 3-tier       │  │
│  │ Composite    │ │ Multi-pool    │ │ strategies   │ │ conviction   │  │
│  │ scorer       │ │ Regime-aware  │ │ Regime-driven│ │ Live price   │  │
│  │ No regime    │ │ Alpha Hunter  │ │ Put/Call buy │ │ confirm      │  │
│  │ awareness    │ │ at 10:00 AM   │ │ Straddle sell│ │ ORB + VWAP   │  │
│  ├──────────────┤ ├───────────────┤ ├──────────────┤ ├──────────────┤  │
│  │ 3-day result │ │ 3-day result  │ │ 3-day result │ │ 3-day result │  │
│  │ Rs -19,279   │ │ Rs +54,783 ★  │ │ Rs -56,180   │ │ Rs 0         │  │
│  └──────────────┘ └───────────────┘ └──────────────┘ └──────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Layer 6: OUTPUT

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          OUTPUT CHANNELS                                │
│                                                                         │
│  ┌──────────────┐ ┌───────────────┐ ┌──────────────┐ ┌──────────────┐  │
│  │  TELEGRAM     │ │  DASHBOARD    │ │  AI PICKS    │ │  PDF REPORTS │  │
│  │  424 lines    │ │  1,851 lines  │ │  (in app.py) │ │  (Pyppeteer) │  │
│  ├──────────────┤ ├───────────────┤ ├──────────────┤ ├──────────────┤  │
│  │ /status      │ │ Stocks tab    │ │ Top 5/10/20  │ │ Daily summary│  │
│  │ /regime      │ │ Gainers tab   │ │ stocks       │ │ Trade analysis│ │
│  │ Trade alerts │ │ F&O (Groww)   │ │ ETFs + MFs   │ │ Candlestick  │  │
│  │ Daily summary│ │ Intraday      │ │ AI Chat Q&A  │ │ charts       │  │
│  │ Regime change│ │ Trade Lab     │ │ 80+ stock    │ │ Performance  │  │
│  │              │ │ AI Picks      │ │ names matched│ │ papers       │  │
│  │              │ │ Intel (news)  │ │              │ │              │  │
│  └──────────────┘ └───────────────┘ └──────────────┘ └──────────────┘  │
│                                                                         │
│  ┌──────────────┐ ┌───────────────┐                                     │
│  │  TRADE LAB   │ │  DEVPILOT DB  │                                     │
│  │  (in app.py) │ │  79 learnings │                                     │
│  ├──────────────┤ ├───────────────┤                                     │
│  │ v4 vs v5     │ │ 7 sprints     │                                     │
│  │ daily P&L    │ │ 99 tasks      │                                     │
│  │ Bar charts   │ │ All findings  │                                     │
│  │ Trade detail │ │ persisted     │                                     │
│  └──────────────┘ └───────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Daily Flow

```
08:30 ─── PRE-MARKET ────────────────────────────────────────────────
          │
          ├── premarket_intel.py → Gap: UP/DOWN, FII signal, Global
          ├── regime_detector.py → BULL / BEAR / SIDEWAYS (score -6 to +6)
          ├── cross_asset.py → DXY, Crude, BTC, S&P overnight
          └── market_breadth.py → % above DMA, contrarian signal

09:35 ─── STAGE 1 DEPLOYMENT ────────────────────────────────────────
          │
          ├── composite_scorer.py → Score all 201 stocks
          ├── signal_engine.py → BUY (top 20%) + SELL (bottom 20%)
          ├── risk_manager.py → Can we trade? Position size?
          └── pool_manager.py → Which pool? INTRADAY / SWING / etc.

10:00 ─── ALPHA HUNTER ──────────────────────────────────────────────
          │
          ├── alpha_hunter.py → Scan 10 sectors for rotation
          ├── Find counter-trend winners (stocks UP while market DOWN)
          └── Deploy 21% more capital into confirmed winners

10:15+ ── MONITORING (every 10 min) ─────────────────────────────────
          │
          ├── Price check all positions (SL / target / trailing)
          ├── Circuit breaker check (5-tier)
          ├── Telegram alert on every exit
          └── Rescore every 30 min (signal flip detection)

15:15 ─── FORCE CLOSE ───────────────────────────────────────────────
          │
          ├── Close ALL intraday positions
          ├── Keep SWING / POSITIONAL / INVESTMENT
          └── Save carry-forward balance

15:30 ─── END OF DAY ────────────────────────────────────────────────
          │
          ├── Daily summary → Telegram
          ├── v4 vs v5 comparison
          ├── Carry forward balance
          ├── Learnings → DevPilot DB
          └── PDF report generation
```

---

*Architecture document — TradePilot v5, April 13, 2026*
*Author: Soumya Swain, soumya@devpilot.co.in*
