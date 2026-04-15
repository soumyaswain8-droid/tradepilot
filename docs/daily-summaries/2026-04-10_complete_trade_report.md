# TradePilot Complete Trade Report -- April 10, 2026

*V4 + V5 Engine Performance | Paper Trading Day*

**Author:** Soumya Swain | soumya@devpilot.co.in
**Date:** Thursday, April 10, 2026

---

## Executive Summary

A dominant day for TradePilot. Both engines delivered profits with near-perfect execution. The V4 engine achieved a flawless 100% win rate across 22 trades on Rs 10,00,000 capital, netting Rs +11,537 (+1.15%). The V5 multi-pool engine, operating on Rs 50,00,000 capital with both longs and shorts, generated Rs +40,480 (+0.81%) across 26 trades with a 96% win rate. V5's intraday short pool was the standout, with COALINDIA shorted 6 times for a combined Rs +23,198. Combined P&L across both engines: **Rs +52,017**.

---

## 1. Market Context

| Indicator | Value |
|:----------|:------|
| Market Regime | SIDEWAYS |
| Gap Direction | UP |
| V4 Strategy | Long-Only |
| V5 Strategy | Multi-Pool (Longs + Shorts) |

---

## 2. V4 Engine Performance

### Capital & Summary

| Metric | Value |
|:-------|------:|
| Capital | Rs 10,00,000 |
| Net P&L | Rs +11,537 |
| Return | +1.15% |
| Total Trades | 22 |
| Winners | 22 |
| Losers | 0 |
| Win Rate | 100% |
| Scans | 32 |
| Rescores | 11 |

### V4 Closed Trades (22 -- All Winners)

| # | Stock | Entry | Exit | Qty | P&L | P&L% | Entry Time | Exit Time | Reason | Score |
|--:|:------|------:|-----:|----:|----:|-----:|:-----------|:----------|:-------|------:|
| 1 | ASIANPAINT | 2,311.80 | 2,360.00 | 21 | +1,012 | +2.08% | 09:31 | 10:11 | TARGET | 62 |
| 2 | EICHERMOT | 7,255.00 | 7,304.00 | 6 | +294 | +0.68% | 09:31 | 10:57 | STOPLOSS | 58 |
| 3 | ASIANPAINT | 2,311.80 | 2,352.70 | 22 | +900 | +1.77% | 10:11 | 10:57 | STOPLOSS | 71 |
| 4 | ICICIBANK | 1,302.90 | 1,315.70 | 40 | +512 | +0.98% | 09:31 | 12:50 | STOPLOSS | 66 |
| 5 | HEROMOTOCO | 5,373.50 | 5,461.50 | 9 | +792 | +1.64% | 09:31 | 12:50 | TARGET | 66 |
| 6 | SBILIFE | 1,928.20 | 1,932.70 | 18 | +81 | +0.23% | 10:47 | 12:50 | STOPLOSS | 62 |
| 7 | EICHERMOT | 7,255.00 | 7,412.00 | 5 | +785 | +2.16% | 11:18 | 12:50 | TARGET | 63 |
| 8 | M&M | 3,208.70 | 3,260.60 | 15 | +778 | +1.62% | 09:41 | 13:41 | TARGET | 62 |
| 9 | M&M | 3,208.70 | 3,245.20 | 14 | +511 | +1.14% | 14:02 | 14:32 | STOPLOSS | 66 |
| 10 | SBIN | 1,057.50 | 1,062.80 | 48 | +254 | +0.50% | 09:31 | 14:43 | STOPLOSS | 63 |
| 11 | BAJAJ-AUTO | 9,673.00 | 9,760.50 | 5 | +438 | +0.90% | 09:31 | 14:43 | STOPLOSS | 65 |
| 12 | ADANIENT | 2,062.00 | 2,077.40 | 21 | +323 | +0.75% | 13:31 | 14:43 | STOPLOSS | 62 |
| 13 | AXISBANK | 1,345.80 | 1,351.20 | 39 | +211 | +0.40% | 09:31 | 15:15 | TIME_EXIT | 62 |
| 14 | INDUSINDBK | 827.40 | 830.85 | 61 | +210 | +0.42% | 09:31 | 15:15 | TIME_EXIT | 64 |
| 15 | SHRIRAMFIN | 1,026.80 | 1,028.45 | 48 | +79 | +0.16% | 09:31 | 15:15 | TIME_EXIT | 63 |
| 16 | BAJAJFINSV | 1,794.40 | 1,810.30 | 26 | +413 | +0.89% | 09:31 | 15:15 | TIME_EXIT | 64 |
| 17 | BAJFINANCE | 914.95 | 925.80 | 55 | +597 | +1.19% | 10:11 | 15:15 | TIME_EXIT | 65 |
| 18 | HDFCBANK | 807.50 | 810.35 | 63 | +180 | +0.35% | 10:11 | 15:15 | TIME_EXIT | 57 |
| 19 | HEROMOTOCO | 5,373.50 | 5,469.00 | 10 | +955 | +1.78% | 13:01 | 15:15 | TIME_EXIT | 72 |
| 20 | ICICIBANK | 1,302.90 | 1,322.60 | 42 | +827 | +1.51% | 13:01 | 15:15 | TIME_EXIT | 69 |
| 21 | BAJAJ-AUTO | 9,673.00 | 9,815.50 | 6 | +855 | +1.47% | 15:04 | 15:15 | TIME_EXIT | 67 |
| 22 | SBIN | 1,057.50 | 1,066.95 | 56 | +529 | +0.89% | 15:04 | 15:15 | TIME_EXIT | 65 |

### V4 Exit Reason Breakdown

| Exit Reason | Trades | Total P&L | Avg P&L/Trade |
|:------------|-------:|----------:|--------------:|
| TARGET | 4 | +3,368 | +842 |
| STOPLOSS | 8 | +3,313 | +414 |
| TIME_EXIT | 10 | +4,857 | +486 |
| **Total** | **22** | **+11,537** | **+524** |

All stop-loss exits were profitable -- trailing stops had moved above entry price before triggering. This confirms the V4 trailing stop mechanism is working correctly.

---

## 3. V5 Engine Performance

### Capital & Summary

| Metric | Value |
|:-------|------:|
| Capital | Rs 50,00,000 |
| Net P&L | Rs +40,480 |
| Return | +0.81% |
| Total Trades | 26 |
| Winners | 25 |
| Losers | 1 |
| Win Rate | 96.2% |
| Regime | SIDEWAYS |
| Gap | UP |

---

### 3a. V5 Intraday Pool -- Shorts

**Pool P&L: Rs +26,487 | 13 trades | 12W / 1L**

| # | Stock | Type | Entry | Exit | Qty | P&L | P&L% | Entry | Exit | Reason |
|--:|:------|:-----|------:|-----:|----:|----:|-----:|:------|:-----|:-------|
| 1 | COALINDIA | SHORT | 452.70 | 439.50 | 244 | +3,221 | +2.92% | 13:03 | 13:13 | TARGET |
| 2 | COALINDIA | SHORT | 452.70 | 431.60 | 244 | +5,148 | +4.66% | 13:13 | 13:23 | TARGET |
| 3 | TCS | SHORT | 2,539.80 | 2,529.60 | 48 | +490 | +0.40% | 13:03 | 13:43 | STOPLOSS |
| 4 | COALINDIA | SHORT | 452.70 | 433.50 | 218 | +4,186 | +4.24% | 13:44 | 13:54 | TARGET |
| 5 | COALINDIA | SHORT | 452.70 | 436.80 | 195 | +3,100 | +3.51% | 14:14 | 14:24 | TARGET |
| 6 | COALINDIA | SHORT | 452.70 | 432.80 | 194 | +3,861 | +4.40% | 14:45 | 14:55 | TARGET |
| 7 | TCS | SHORT | 2,539.80 | 2,526.00 | 48 | +662 | +0.54% | 13:44 | 15:15 | STOPLOSS |
| 8 | SUNPHARMA | SHORT | 1,665.40 | 1,655.70 | 91 | +883 | +0.58% | 13:03 | 15:15 | TIME_EXIT |
| 9 | INFY | SHORT | 1,299.40 | 1,293.00 | 105 | +672 | +0.49% | 13:03 | 15:15 | TIME_EXIT |
| 10 | NTPC | SHORT | 380.60 | 380.45 | 288 | +43 | +0.04% | 13:44 | 15:15 | TIME_EXIT |
| 11 | ONGC | SHORT | 289.45 | 286.90 | 339 | +864 | +0.88% | 14:14 | 15:15 | TIME_EXIT |
| 12 | APOLLOHOSP | SHORT | 7,481.00 | 7,506.00 | 13 | -325 | -0.33% | 15:15 | 15:15 | TIME_EXIT |
| 13 | COALINDIA | SHORT | 452.70 | 434.20 | 199 | +3,682 | +4.09% | 15:15 | 15:15 | TIME_EXIT |

**Star Performer: COALINDIA** -- Shorted 6 times, all profitable, combined P&L: **Rs +23,198**

---

### 3b. V5 Swing Pool -- Longs

**Pool P&L: Rs +13,993 | 13 closed trades | 9 positions still open**

| # | Stock | Entry | Exit | Qty | P&L | P&L% | Reason |
|--:|:------|------:|-----:|----:|----:|-----:|:-------|
| 1 | EICHERMOT | 7,255 | 7,402 | 14 | +2,058 | +2.03% | TARGET |
| 2 | EICHERMOT | 7,255 | 7,417 | 8 | +1,300 | +2.24% | TARGET |
| 3 | EICHERMOT | 7,255 | 7,412 | 8 | +1,260 | +2.17% | TARGET |
| 4 | HEROMOTOCO | 5,373 | 5,442 | 21 | +1,449 | +1.28% | STOPLOSS |
| 5 | M&M | 3,208 | 3,243 | 21 | +733 | +1.09% | STOPLOSS |
| 6 | EICHERMOT | 7,255 | 7,402 | 8 | +1,176 | +2.03% | TARGET |
| 7 | BAJAJ-AUTO | 9,673 | 9,763 | 8 | +724 | +0.94% | STOPLOSS |
| 8 | AXISBANK | 1,345 | 1,346 | 55 | +33 | +0.04% | SIGNAL_FLIP |
| 9 | EICHERMOT | 7,255 | 7,404 | 11 | +1,639 | +2.05% | TARGET |
| 10 | ASIANPAINT | 2,311 | 2,360 | 54 | +2,608 | +2.09% | SIGNAL_FLIP |
| 11 | INDUSINDBK | 827 | 831 | 73 | +292 | +0.48% | SIGNAL_FLIP |
| 12 | SBIN | 1,057 | 1,067 | 51 | +484 | +0.90% | SIGNAL_FLIP |
| 13 | HDFCBANK | 807 | 810 | 86 | +236 | +0.34% | SIGNAL_FLIP |

### Open Positions (Carrying Overnight)

| Stock | Status |
|:------|:-------|
| ICICIBANK | Trailing stop active |
| HEROMOTOCO | Trailing stop active |
| BAJAJ-AUTO | Trailing stop active |
| SHRIRAMFIN | Holding |
| AXISBANK | Holding |
| EICHERMOT | Holding |
| WIPRO | Holding |
| M&M | Holding |
| BAJAJFINSV | Holding |

---

## 4. V4 vs V5 Head-to-Head Comparison

| Metric | V4 | V5 | Winner |
|:-------|---:|---:|:-------|
| Capital | Rs 10,00,000 | Rs 50,00,000 | -- |
| Net P&L | +Rs 11,537 | +Rs 40,480 | V5 (3.5x) |
| Return % | +1.15% | +0.81% | V4 |
| Total Trades | 22 | 26 | -- |
| Win Rate | 100% | 96.2% | V4 |
| Long Trades | 22 | 13 | -- |
| Short Trades | 0 | 13 | V5 |
| Intraday Short P&L | -- | +Rs 26,487 | V5 unique |
| Swing Open Positions | 0 | 9 | V5 carries overnight |
| Avg P&L per Trade | +Rs 524 | +Rs 1,557 | V5 |

### Key Takeaways

- **V4** delivered a perfect session -- 100% win rate with disciplined trailing stops converting even stop-loss exits into profitable trades.
- **V5** demonstrated the power of multi-pool architecture -- intraday shorts contributed 65% of total P&L, a capability V4 lacks entirely.
- **COALINDIA** was the day's biggest opportunity -- V5 captured Rs 23,198 from it through repeated short entries. V4 could not participate.
- **V5 swing pool** carries 9 positions overnight, creating potential for next-day gains (or risk). V4 is fully flat by close.
- Combined both engines produced **Rs +52,017** in a single trading day.

---

## 5. Top Performing Stocks

| Stock | V4 P&L | V5 P&L | Combined | Best Play |
|:------|-------:|-------:|---------:|:----------|
| COALINDIA | -- | +23,198 | +23,198 | V5 short x6 |
| EICHERMOT | +1,079 | +7,433 | +8,512 | V5 swing + V4 target |
| ASIANPAINT | +1,912 | +2,608 | +4,520 | Both engines long |
| HEROMOTOCO | +1,747 | +1,449 | +3,196 | Both engines long |
| ICICIBANK | +1,339 | -- | +1,339 | V4 re-entry |
| BAJAJ-AUTO | +1,293 | +724 | +2,017 | V4 time exits |
| M&M | +1,289 | +733 | +2,022 | Both engines long |
| SBIN | +783 | +484 | +1,267 | Both engines long |

---

## 6. Session Statistics

| Metric | V4 | V5 |
|:-------|---:|---:|
| First Trade | 09:31 | 13:01 (swing) / 13:03 (intraday) |
| Last Trade | 15:15 | 15:15 |
| Session Duration | 5h 44m | 2h 14m |
| Unique Stocks Traded | 14 | 14 |
| Avg Hold Time (est.) | 2-3 hrs | 30-60 min (intraday) |
| Max Concurrent Positions | ~15 | ~12 |

---

*Report generated by TradePilot | soumya@devpilot.co.in*
