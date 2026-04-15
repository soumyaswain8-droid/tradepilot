# TradePilot — Module Dependency Map

*34 files | 15,937 lines | Hub nodes: config (11), regime_detector (8), composite_scorer (5)*

---

## Hub Nodes (most connected)

```
                    ┌─────────────────────┐
                    │     config.py       │
                    │   225 lines         │
                    │   11 modules depend │
                    │   on this file      │
                    └─────────┬───────────┘
                              │
        ┌──────────┬──────────┼──────────┬──────────┬──────────┐
        │          │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼          ▼
   ml_engine  data_nse  composite  signal    market   options
                        _scorer    _engine   _breadth _signals
                              │
                    ┌─────────┴───────────┐
                    │  regime_detector.py  │
                    │   417 lines          │
                    │   8 modules depend   │
                    │   on this file       │
                    └─────────┬───────────┘
                              │
        ┌──────────┬──────────┼──────────┬──────────┐
        │          │          │          │          │
        ▼          ▼          ▼          ▼          ▼
   signal     alpha      v5-paper   v5.2-paper  v5.3-paper
   _engine    _hunter    trade.py   trade.py    trade.py
   comparator
```

---

## Full Dependency Graph

```
LEGEND:
  ──▶  "depends on" (arrow points to dependency)
  [N]  number of lines
  {D}  number of dependents (modules that import this)

═══════════════════════════════════════════════════════════════════

V4 CORE ENGINE (3,242 lines)
─────────────────────────────

  config.py [225] {11} ◄───────────────── THE CENTRAL HUB
       │                                  Every module reads config
       ├──▶ (no dependencies — pure config)
       │
  data_nse.py [669] {4}
       │
       ├──▶ config.py (NIFTY symbols, cache dir)
       │
  ml_engine.py [803] {4}
       │
       ├──▶ config.py (feature list, LGBM params)
       │
  features_intraday.py [405] {2}
       │
       ├──▶ (standalone — pure functions)
       │
  features_institutional.py [191] {2}
       │
       ├──▶ (standalone — pure functions)
       │
  composite_scorer.py [580] {5} ◄─────── THE SCORING HUB
       │
       ├──▶ config.py (weights, thresholds, universe)
       ├──▶ data_nse.py (FII, options, quotes)
       ├──▶ ml_engine.py (predict_ml_score)
       ├──▶ features_intraday.py (ORB, VWAP, gap)
       └──▶ features_institutional.py (FII score, OI)
       │
  position_sizer.py [288] {1}
       │
       ├──▶ config.py (Kelly params)


═══════════════════════════════════════════════════════════════════

V5 CORE MODULES (5,271 lines)
──────────────────────────────

  regime_detector.py [417] {8} ◄──────── THE BRAIN
       │
       ├──▶ fii_feed.py (real FII data)
       ├──▶ data_nse.py (Nifty quotes)
       │
  premarket_intel.py [374] {3}
       │
       ├──▶ (yfinance for GIFT Nifty, S&P, Asia)
       │
  signal_engine.py [259] {2}
       │
       ├──▶ composite_scorer.py (base scores)
       ├──▶ regime_detector.py (filter by regime)
       ├──▶ config.py (universe)
       │
  pool_manager.py [337] {2}
       │
       ├──▶ (standalone — manages pool state)
       │
  risk_manager.py [595] {1}
       │
       ├──▶ pool_manager.py (reads pool state)
       │
  fii_feed.py [371] {1}
       │
       ├──▶ (nsepython + cache — standalone)
       │
  comparator.py [189] {2}
       │
       ├──▶ regime_detector.py
       ├──▶ premarket_intel.py
       │
  telegram_bot.py [424] {1}
       │
       ├──▶ (standalone — HTTP to Telegram API)


═══════════════════════════════════════════════════════════════════

V5 NEW SIGNALS — Built Day 3-4 (2,217 lines)
──────────────────────────────────────────────

  alpha_hunter.py [672] {1} ◄──────────── SECTOR ROTATION
       │
       ├──▶ regime_detector.py (only activates in BEAR/SIDEWAYS)
       ├──▶ (yfinance for sector index data)
       │
  cross_asset.py [358] {0}
       │
       ├──▶ (yfinance for DXY, crude, gold, BTC, S&P, US 10Y)
       ├──▶ (standalone — no internal deps)
       │
  market_breadth.py [460] {1}
       │
       ├──▶ config.py (ACTIVE_SYMBOLS for universe)
       ├──▶ (reads CSV files from prototype/data/)
       │
  options_signals.py [438] {1}
       │
       ├──▶ (nsepython for option chain)
       ├──▶ config.py (fallback VIX estimation)
       │
  enhanced_features.py [289] {1}
       │
       ├──▶ (standalone — pure computation)


═══════════════════════════════════════════════════════════════════

EXPERIMENTS (1,248 lines)
─────────────────────────

  v5_2/options_engine.py [710] {1}
       │
       ├──▶ regime_detector.py (strategy selection)
       │
  v5_3/staged_entry.py [519] {0}
       │
       ├──▶ signal_engine.py (base signals)
       ├──▶ regime_detector.py (conviction tiers)
       ├──▶ composite_scorer.py (rescore at midday)


═══════════════════════════════════════════════════════════════════

TRADING SCRIPTS (4,325 lines)
──────────────────────────────

  v4-paper-trade.py [727]
       │
       ├──▶ composite_scorer.py (score_all_stocks)
       ├──▶ config.py (universe, params)
       │
  v5-paper-trade.py [692]
       │
       ├──▶ signal_engine.py (BUY + SELL signals)
       ├──▶ regime_detector.py (regime for sizing)
       ├──▶ alpha_hunter.py (10 AM sector rotation)
       ├──▶ telegram_bot.py (alerts)
       │
  v5_2-paper-trade.py [548]
       │
       ├──▶ options_engine.py (F&O strategies)
       ├──▶ regime_detector.py (strategy selection)
       │
  v5_3-paper-trade.py [1163]
       │
       ├──▶ staged_entry.py (conviction tiers)
       ├──▶ regime_detector.py (tier classification)


═══════════════════════════════════════════════════════════════════

WEB SERVER (1,851 lines)
─────────────────────────

  app.py [1851]
       │
       ├──▶ composite_scorer.py (score_stocks_v4 for AI Picks)
       ├──▶ config.py (ACTIVE_SYMBOLS, NIFTY_200)
       ├──▶ regime_detector.py (for /api/ask market regime Q&A)
       │
       │    SERVES:
       ├──── / (dashboard HTML)
       ├──── /api/scores (stock scores)
       ├──── /api/picks (AI recommendations)
       ├──── /api/ask (AI chat Q&A)
       ├──── /api/tradelab/days (v4 vs v5 tracking)
       ├──── /api/tradelab/trades/<date> (trade details)
       ├──── /api/bots/geopolitical (live Google News)
       ├──── /api/gainers-losers?index= (filtered gainers)
       ├──── /api/fno/chain/<index> (option chain)
       └──── /api/paper/* (paper trading)
```

---

## Dependency Count Summary

| Module | Lines | Depends On | Used By | Role |
|--------|------:|:----------:|:-------:|------|
| **config.py** | 225 | 0 | **11** | Central configuration hub |
| **regime_detector.py** | 417 | 2 | **8** | Market regime brain |
| **composite_scorer.py** | 580 | 5 | **5** | Core scoring engine |
| ml_engine.py | 803 | 1 | 4 | ML prediction |
| data_nse.py | 669 | 1 | 4 | NSE data pipeline |
| premarket_intel.py | 374 | 0 | 3 | Pre-market analysis |
| signal_engine.py | 259 | 3 | 2 | BUY/SELL signal generation |
| pool_manager.py | 337 | 0 | 2 | Multi-pool capital management |
| alpha_hunter.py | 672 | 1 | 1 | Sector rotation scanner |
| risk_manager.py | 595 | 1 | 1 | 5-tier circuit breakers |
| app.py | 1,851 | 3 | 0 | Web dashboard (leaf node) |

---

## Data Flow Diagram

```
EXTERNAL DATA                    INTERNAL PROCESSING                  OUTPUT
─────────────                    ────────────────────                  ──────

yfinance ──────┐
               ├──▶ data_nse ──▶ composite_scorer ──┐
nsepython ─────┤                                     │
               ├──▶ fii_feed ──▶ regime_detector ────┤
Google RSS ────┤                                     ├──▶ v5-paper-trade ──▶ Telegram
               ├──▶ cross_asset                      │         │
NSE CSV ───────┤                                     │         ├──▶ Trade Lab
               ├──▶ ml_engine ──▶ signal_engine ─────┤         │
               │                                     │         ├──▶ PDF Reports
               ├──▶ market_breadth                   │         │
               │                                     ├──▶ app.py ──▶ Dashboard
               ├──▶ options_signals                  │              ├── AI Picks
               │                                     │              ├── Gainers
               └──▶ enhanced_features ───────────────┘              ├── F&O
                                                                    ├── Intraday
                    alpha_hunter (10 AM) ─────────────────────┘     └── Intel
```

---

## Version Evolution

```
v3 ──▶ v4 ──▶ v5 ──▶ v5.2 (F&O experiment)
  │      │      │         │
  │      │      │         └──▶ v5.3 (staged entry experiment)
  │      │      │
  │      │      └──▶ v6 (PLANNED: multi-agent + Kite API + live trading)
  │      │
  │      └── Composite scorer, long-only, Nifty 50
  │
  └── ML classification, regime-aware (retired)

Lines of code growth:
  v3:  ~1,500 lines
  v4:  ~3,200 lines (+1,700)
  v5:  ~7,800 lines (+4,600)
  v5+: ~15,900 lines (+8,100) ← includes experiments + web + scripts
```

---

*Dependency map — TradePilot, April 13, 2026*
*Author: Soumya Swain, soumya@devpilot.co.in*
