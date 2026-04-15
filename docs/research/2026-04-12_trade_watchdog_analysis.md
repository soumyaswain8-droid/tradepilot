# TradePilot Watchdog Analysis: Apr 9-10, 2026

**Engines Analyzed:** v4 (Day 1 + Day 2), v5 (Day 2 only)
**Market Data Source:** yfinance (NSE actual prices, 15-min intervals)
**Analysis Date:** 2026-04-12

---

## Executive Summary

| Metric | v4 Day 1 (Apr 9) | v4 Day 2 (Apr 10) | v5 Day 2 (Apr 10) |
|--------|:-:|:-:|:-:|
| Total PnL | -Rs 30,816 (-3.08%) | +Rs 11,537 (+1.15%) | +Rs 40,480 (+0.81%) |
| Win Rate | 5/37 (13.5%) | 22/22 (100%) | 25/26 (96.2%) |
| Best Trade | JSWSTEEL +1.27% | ASIANPAINT +2.08% | COALINDIA short +4.66% |
| Worst Trade | SHRIRAMFIN -2.87% | None negative | APOLLOHOSP -0.33% |

**Key finding:** v5 earned Rs 40,480 but left an estimated Rs 25,000-40,000 on the table from missed opportunities and suboptimal timing. v4 Day 1 was a catastrophic -3.08% loss caused by going all-long in a bear session.

---

## 1. MISSED OPPORTUNITIES

### 1A. Stocks That Moved >3% on Apr 10 That We Did NOT Trade

| Stock | Day Change | Intraday Range | Why We Missed | Signal That Would Have Caught It |
|-------|:----------:|:--------------:|---------------|----------------------------------|
| SIEMENS | +4.76% | +5.27% | Not in Nifty 50 scan universe | **Expand scan to Nifty 200**. Siemens broke out at 11:45 (+3.67%) with a massive 15-min candle from 3277 to 3353. A momentum breakout scanner would have caught this. |
| ADANIGREEN | +3.91% | +4.52% | Not in Nifty 50 scan universe | Same. Clean uptrend from 11:15 onward, +2.06% to +3.91%. |
| CUMMINSIND | +3.58% | +4.96% | Not in Nifty 50 scan universe | Steady grind from 12:15 (+0.79%) to close (+3.64%). Volume breakout pattern. |
| ABB | +3.27% | +4.41% | Not in Nifty 50 scan universe | Co-moved with SIEMENS (industrials sector rotation). 11:45 candle explosion from 6776 to 6875. |
| DIVISLAB | +3.13% | +3.36% | Not in Nifty 50 scan universe | Steady pharma outperformer while SUNPHARMA crashed -2.61%. Sector pair divergence signal. |

**Estimated missed profit (SIEMENS alone):** Entry at 3280 (11:45 breakout), exit at 3390 (15:00) = +3.35% on Rs 1L position = Rs 3,350.

**Estimated missed profit (all 5 stocks):** Rs 12,000-18,000 combined on conservative position sizing.

### 1B. Stocks Within Nifty 50 That Had Better Setups Than What We Traded

| Stock | Day Change | What We Traded Instead | Opportunity Cost |
|-------|:----------:|------------------------|-----------------|
| BAJAJ-AUTO | +4.40% | v4 entered at 9673, exited 9760 (+0.90% STOPLOSS) and 9815 (+1.47% TIME) | Actual close was 9813. The stock ran from 9400 open to 9844 high. v4 entered AFTER the gap-up and missed the real move from 9400-9675. |
| TITAN | +1.69% | v4 Day 1 shorted TITAN for -0.90% loss | TITAN recovered on Day 2. Should have waited for confirmation rather than counter-trend trading. |
| DRREDDY | +1.60% | Not traded on either day | While we shorted SUNPHARMA (-2.61%), DRREDDY went +1.60%. A long DRREDDY / short SUNPHARMA pair would have captured +4.21% spread. |

### 1C. Apr 9 Missed Short Opportunities

v4 went 100% long on a day Nifty fell -0.56%. The biggest movers DOWN that v4 should have shorted:

| Stock | Day Change | v4 Action | Should Have Done |
|-------|:----------:|-----------|------------------|
| BRITANNIA | -2.58% | Not traded | Short signal was clear: opened at 5620, broke below 5500 by 10:00 |
| LT | -2.30% | Went LONG at 4006, stopped out -1.92% | Should have SHORTED. LT fell from 3988 open to 3886 close. v4's LONG cost Rs 1,922. |
| HDFCBANK | -2.12% | Went LONG at 816, exited at 806 (-1.23%) + 799 (-2.12%) | Should have SHORTED after the initial gap-up reversal at 09:30. |
| INDUSINDBK | -2.08% | Went LONG at 836, exited at 820 (-1.96%) | Clear downtrend all day from 834 to 812. |

**Estimated avoided loss + captured profit:** v4 lost Rs 6,800 going long on these 4 stocks. Shorting them could have earned Rs 8,000-12,000 instead. Net delta: Rs 15,000-19,000.

---

## 2. TIMING ANALYSIS

### 2A. v4 Day 2 (Apr 10) Entry Timing

| Stock | v4 Entry Time | v4 Entry Price | Optimal Entry | Optimal Price | Improvement |
|-------|:----------:|:-:|:----------:|:-:|:-:|
| ASIANPAINT | 09:31 | 2311.8 | 09:15 (open) | 2275.6 | 1.6% better entry = Rs 760 more profit |
| BAJAJ-AUTO | 09:31 | 9673.0 | 09:15 (open) | 9488.5 | 1.9% better = Rs 925 more on 5 shares |
| HEROMOTOCO | 09:31 | 5373.5 | 09:15 (open) | 5304.0 | 1.3% better = Rs 625 more on 9 shares |
| EICHERMOT | 09:31 | 7255.0 | 09:15 (open) | 7213.5 | 0.6% better = Rs 249 more on 6 shares |
| M&M | 09:41 | 3208.7 | 09:15 (open) | 3182.0 | 0.8% better = Rs 400 more on 15 shares |

**Pattern:** v4 consistently enters 15-16 minutes after market open, AFTER the initial gap-up move has already occurred. The ORB (Opening Range Breakout) strategy waits for the first 15-min candle to close, but on strong gap-up days, the best prices are at the open.

**Recommendation:** Add a "gap-up momentum" entry mode that enters at 09:15-09:20 when pre-market signals are strongly bullish AND gap > 1%. The ORB confirmation can be used as a HOLD signal rather than ENTRY signal.

### 2B. v5 Day 2 Entry Timing (Shorts)

v5 started at 13:03 (half-day engine). Key timing observations:

| Stock | v5 Entry Price | Actual Market Price at 13:03 | Actual Intraday Low | v5 Entry vs Low |
|-------|:-:|:-:|:-:|:-:|
| COALINDIA | 452.7 (short) | ~438 (market was already at -3.66%) | 427.5 (at 13:15) | v5 shorted at 452.7 but market was already at 438. Entry price seems stale -- used a much higher reference price. |
| TCS | 2539.8 (short) | ~2513 (market was at -1.95%) | 2501.1 | Same pattern -- entry price is 09:15 level, not actual 13:03 level |
| SUNPHARMA | 1665.4 (short) | ~1651 (market was at -1.50%) | 1630.4 | Entry was 1665, market was already 1651 |
| INFY | 1299.4 (short) | ~1292 (market was at -1.88%) | 1283.4 | Entry was 1299, market was 1292 |

**CRITICAL FINDING:** v5's entry prices appear to be from the OPENING range (09:15-09:30), not the actual price at 13:03 when it started trading. This means:
- COALINDIA short at 452.7 when actual price was ~438: this explains the apparent +4.66% profit on a 10-min trade. The actual fill price would have been ~438, yielding +2.5% on the first exit at 431.6 (still good).
- If the PnL calculations use correct fill prices, the actual profits are accurate. But if entry prices are stale, **the PnL is overstated by approximately 40-60%**.

**This needs urgent verification.** If entry prices are based on pre-market or ORB levels rather than actual execution prices, v5's reported Rs 40,480 profit could actually be Rs 16,000-24,000.

### 2C. Exit Timing Analysis

For v4 Day 2 winners that exited via TIME_EXIT at 15:15:

| Stock | Exit Price (15:15) | Actual Close | Better Exit? | Impact |
|-------|:-:|:-:|:-:|:-:|
| AXISBANK | 1351.2 | 1350.8 | No -- timed correctly | Neutral |
| BAJAJFINSV | 1810.3 | 1809.2 | No | Neutral |
| BAJAJ-AUTO (2nd) | 9815.5 | 9835.0 | Could have held 15 more min for +Rs 97 | Minor |
| HEROMOTOCO (2nd) | 5469.0 | 5457.5 | Exited at better price than close | Good exit |

**Verdict:** v4's 15:15 time exit is reasonable. The last 15 minutes showed mixed action -- some stocks rallied, some sold off. No systematic improvement from holding until 15:29.

---

## 3. EXIT ANALYSIS -- Alternative Stop/Target Scenarios

### v4 Day 2 -- What If We Used Different Parameters?

**ASIANPAINT** (v4's best trade: +2.08% TARGET):
- Actual: Entry 2311.8, Target hit at 2360.0 at 10:11 (+2.08%)
- If held to 3:15 PM: Exit ~2360 = same +2.08% (stock plateaued after target)
- If 1% trailing stop: Would have exited at ~2340 when pullback from 2371 high hit -1.3%. Worse.
- **Verdict:** Target exit was optimal.

**HEROMOTOCO** (v4: +1.64% TARGET):
- Actual: Entry 5373.5, Target hit at 5461.5 at 12:50 (+1.64%)
- If held to 3:15 PM: Exit ~5469 = +1.78% (marginal improvement)
- If 1% trailing stop from 5484 high: Exit at 5429 = +1.03%. Worse.
- **Verdict:** Target exit was near-optimal.

**ICICIBANK** (v4: +0.98% STOPLOSS -- trailing):
- Actual: Entry 1302.9, trailing stop hit at 1315.7 at 12:50
- If held to 3:15 PM: Exit ~1322 = +1.51% (Rs 315 more profit)
- If wider 1% trail: Would have ridden to ~1322 before exiting. Better.
- **Verdict:** Trailing stop was too tight. Cost Rs 315.

**BAJAJ-AUTO** (v4 first position: +0.90% STOPLOSS -- trailing):
- Actual: Entry 9673, trailing stop at 9760.5 at 14:43
- Peak was 9814 at 12:30. Stock pulled back to 9743 (14:15) then recovered to 9844.
- If 1.5% trail from 9820: Exit at 9673 (breakeven). If 1% trail: Exit at 9722.
- **Verdict:** The pullback to 9743 was -0.73% from peak. A 1% trail would have survived this dip and captured the 15:00 rally to 9844. Profit improvement: Rs 855 more.

### v5 Day 2 -- COALINDIA Short Performance

v5 made 6 SHORT trades on COALINDIA, all profitable:
- Trade 1: +2.92% (452.7 -> 439.5, 10 min)
- Trade 2: +4.66% (452.7 -> 431.6, 10 min)
- Trade 3: +4.24% (452.7 -> 433.5, 10 min)
- Trade 4: +3.51% (452.7 -> 436.8, 10 min)
- Trade 5: +4.40% (452.7 -> 432.8, 10 min)
- Trade 6: +4.09% (452.7 -> 434.2, time exit)
- Total COALINDIA P&L: Rs 23,197 (57% of all v5 profit)

COALINDIA actual intraday: Opened 455, steady until 12:30 (454), then crashed to 427.8 by 13:15.

**If v5 had held a single larger SHORT from 452 to 427.5 (the low):** 
- 500 shares x Rs 24.5 = Rs 12,250 -- less than the multiple-entry approach
- The re-entry approach actually worked BETTER because each exit locked in profit at intermediate levels

**If v5 had shorted at 09:15 (455) instead of 13:03 (452.7):**
- Additional Rs 2.3 per share x total ~1,100 shares = Rs 2,530 more

---

## 4. SHORT SIGNAL QUALITY -- v5 Day 2

v5 shorted: COALINDIA, TCS, SUNPHARMA, INFY, NTPC, ONGC, APOLLOHOSP

### Were These the Weakest Stocks?

Actual Nifty 50 stocks that fell the most on Apr 10:

| Rank | Stock | Day Change | v5 Shorted? |
|:----:|-------|:----------:|:-----------:|
| 1 | COALINDIA | -4.59% | YES (6 trades, Rs 23,197 profit) |
| 2 | SUNPHARMA | -2.61% | YES (Rs 883 profit) |
| 3 | INFY | -1.93% | YES (Rs 672 profit) |
| 4 | WIPRO | -1.83% | Not shorted (went LONG in SWING pool!) |
| 5 | TCS | -1.62% | YES (Rs 1,152 profit) |

**Verdict:** v5 correctly identified 4 of the top 5 weakest stocks. The miss was WIPRO -- v5 actually went LONG on WIPRO in its SWING pool at 205.6, while the stock fell to close at 204.9 (-1.83%). This is a conflicting signal: shorting weak IT stocks in INTRADAY while going long on WIPRO in SWING.

### What Was Weaker That We Missed?

| Stock | Day Change | In Scan Universe? | Signal |
|-------|:----------:|:-:|--------|
| WIPRO | -1.83% | Yes | v5 went LONG instead of SHORT. IT sector was weak as a whole. |
| BRITANNIA | -1.16% (Apr 10) | Yes | Second consecutive down day (was -2.58% on Apr 9). Trend continuation short. |

**NTPC short returned only Rs 43 (0.04%)** -- effectively a no-signal trade. Better to have allocated that capital to a larger COALINDIA position or shorted WIPRO.

**APOLLOHOSP was a losing short** (-Rs 325). It was entered at 15:15 with only seconds before close -- this is a noise trade, not a real signal.

---

## 5. REGIME ACCURACY

### v5 Called: SIDEWAYS (with BULLISH premarket bias)

**Actual Market Behavior (Apr 10):**
- Nifty opened at 23,881, high 24,074, low 23,856, close 24,051
- Intraday range: +0.24% to +0.74% from open
- Never went negative from open
- Closed at day's highs

**Correct Regime: MILD BULL / BULLISH**

The market was steadily bullish all day. It opened with a gap-up, consolidated, then ground higher in the afternoon. The "SIDEWAYS" call was partially wrong:
- The index moved +0.71% (open to close) which is a decent up day
- But the index never moved more than +0.81% from open, so the magnitude was modest
- Individual stock dispersion was very high: SIEMENS +4.76% vs COALINDIA -4.59%

**Impact of Wrong Regime Call:**
A "SIDEWAYS" regime causes v5 to use smaller position sizes (1.0x multiplier instead of 1.2x for BULLISH). This means:
- v5's SWING longs (correct direction) were undersized
- v5's INTRADAY shorts (correct for individual weak stocks) were appropriately sized

**A perfect regime detector would have:**
1. Called BULLISH for the index -- size up SWING longs
2. Identified a sector rotation pattern (defense/industrials UP, IT/pharma DOWN)
3. Used sector regime overlays to go long on strong sectors and short weak sectors simultaneously

---

## 6. POSITION SIZING ANALYSIS

### v4 Day 1 -- The Martingale Trap

v4's worst behavior on Apr 9 was RE-ENTERING losing stocks:

| Stock | # Entries | Total Loss | Avg Loss Per Trade |
|-------|:-:|:-:|:-:|
| SHRIRAMFIN | 4 | Rs 8,396 | -2.55% |
| BAJFINANCE | 3 | Rs 4,652 | -1.81% |
| ULTRACEMCO | 3 | Rs 3,680 | -1.49% |
| M&M | 3 | Rs 3,230 | -1.64% |
| MARUTI | 2 | Rs 261 | -0.93% |

v4 entered SHRIRAMFIN FOUR TIMES on a day it fell from 1010 to 990 (-2%). Each re-entry was at approximately the same price (1023.2) with the same stop loss. This is martingale-adjacent behavior -- doubling down on losers.

**Recommendation:** Add a "stock cool-down" rule: after 2 consecutive stop-losses on the same stock in the same session, BLOCK re-entry for 60 minutes minimum.

### v4 Day 2 -- Position Sizing Was Reasonable

All 22 positions were profitable. Position sizes were 8.7% to 19.9% of capital per trade. The re-entry approach worked because the market direction was correct (bullish).

### v5 Day 2 -- Over-Concentrated in COALINDIA

COALINDIA accounted for 6 of 13 intraday trades and 57% of all profit. While this worked, it creates single-stock concentration risk:
- If COALINDIA had reversed after 13:15, all 6 trades could have been losers
- COALINDIA's drop was driven by a single event (likely stock-specific news), not broad market weakness

**Recommendation:** Cap at 3 trades per stock per session in INTRADAY pool. Rotate capital to other weak stocks (SUNPHARMA, INFY had more runway to fall).

---

## 7. STRATEGY GAPS -- New Signals to Add

### 7A. Sector Rotation Scanner (HIGHEST PRIORITY)

**What we missed:** Apr 10 had a massive sector rotation -- industrials/capex (SIEMENS +4.76%, ABB +3.27%, CUMMINSIND +3.58%) surged while IT (TCS -1.62%, INFY -1.93%) and pharma (SUNPHARMA -2.61%) tanked.

**Signal design:**
1. At 09:30, compute sector-level returns for the first 15-min candle
2. If any sector shows >1% divergence from Nifty, flag as rotation
3. Go long on strongest sector stocks, short weakest sector stocks
4. Estimated capture: Rs 15,000-25,000 on this day alone

### 7B. Pairs Divergence Trading (HIGH PRIORITY)

Three actionable pairs on Apr 10:

| Pair | Spread | Trade | Est. Profit |
|------|:------:|-------|:-----------:|
| SUNPHARMA (-2.61%) / DRREDDY (+1.60%) | 4.21% | Long DRREDDY, Short SUNPHARMA | Rs 3,500-5,000 |
| HDFCBANK (+0.35%) / ICICIBANK (+2.55%) | 2.20% | Long ICICIBANK, Short HDFCBANK | Rs 2,000-3,000 |
| COALINDIA (-4.59%) / ONGC (flat) | 4.59% | Short COALINDIA (already did), Long ONGC | Rs 2,000-3,000 |

### 7C. Gap-Up Momentum Entry (MEDIUM PRIORITY)

v4 consistently enters 15-16 min after open, missing the gap-up continuation move. On Apr 10:
- ASIANPAINT gapped up 1.5% at open, v4 entered at 2311.8 (09:31). Pre-open price was 2275.6.
- BAJAJ-AUTO gapped up 1.9% at open, v4 entered at 9673 (09:31). Pre-open price was 9488.5.

A dedicated "gap momentum" entry at 09:15-09:20 for stocks gapping >1.5% with strong pre-market signals would capture this initial move.

### 7D. Mean Reversion on Oversold Stocks (MEDIUM PRIORITY)

On Apr 9, LT fell -2.30% and BRITANNIA fell -2.58%. On Apr 10:
- LT was flat (no data in our scan)
- BRITANNIA no significant bounce

But COALINDIA fell -4.59% on Apr 10 -- a mean-reversion LONG at 427.5 (the intraday low at 13:15) would have captured a bounce to 435 by close (+1.75%).

### 7E. Nifty 200 Universe Expansion (HIGH PRIORITY)

The 5 biggest missed movers (SIEMENS, ADANIGREEN, CUMMINSIND, ABB, DIVISLAB) are all outside Nifty 50 but inside Nifty 200. Expanding the scan universe to Nifty 200 would have:
- Caught SIEMENS +4.76% breakout at 11:45
- Caught ADANIGREEN +3.91% steady uptrend
- Caught ABB +3.27% co-movement with SIEMENS

### 7F. Stock Cool-Down After Consecutive Losses (HIGH PRIORITY)

On Apr 9, v4 entered SHRIRAMFIN 4 times, losing each time. A simple rule:
- After 2 consecutive stop-losses on same stock: 60-min block on re-entry
- This alone would have saved Rs 5,100 (the 3rd and 4th SHRIRAMFIN entries)

### 7G. Regime-Sensitive Position Count (MEDIUM PRIORITY)

On Apr 9 (bear day), v4 had 37 trades (all long). On Apr 10 (bull day), v4 had 22 trades (all long).

Better approach:
- BEAR regime: Max 5 long positions, allow 5 short positions
- SIDEWAYS: Max 8 each direction
- BULL: Max 12 long, max 3 short

---

## 8. RECOMMENDATIONS (Ranked by Impact)

| # | Recommendation | Est. Impact Per Day | Difficulty |
|:-:|----------------|:-------------------:|:----------:|
| 1 | **Fix v5 entry price bug** -- verify if entry prices reflect actual execution or stale ORB levels. If stale, PnL is overstated by 40-60%. | Accuracy fix | Low |
| 2 | **Add sector rotation scanner** -- detect sector divergence at 09:30, trade strongest/weakest sectors | +Rs 15,000-25,000 | Medium |
| 3 | **Expand to Nifty 200 universe** -- missed SIEMENS (+4.76%), ADANIGREEN (+3.91%), ABB (+3.27%) | +Rs 12,000-18,000 | Low |
| 4 | **Stock cool-down rule** -- block re-entry after 2 consecutive stop-losses on same stock | Save Rs 5,000-10,000 on bear days | Low |
| 5 | **Add pairs divergence** -- SUNPHARMA/DRREDDY, HDFCBANK/ICICIBANK, energy pairs | +Rs 7,000-11,000 | Medium |
| 6 | **Gap-up momentum entry** -- enter at 09:15-09:20 on strong gap days instead of waiting for ORB | +Rs 2,000-4,000 | Low |
| 7 | **Regime-sensitive position count** -- reduce position count in BEAR regime, allow shorts in v4 | Save Rs 15,000-20,000 on bear days | Medium |
| 8 | **Widen trailing stops** -- use 1.0-1.5% trail instead of 0.5% to survive normal pullbacks | +Rs 500-1,500 | Low |
| 9 | **Cap per-stock trades** -- max 3 intraday trades per stock per session to avoid concentration | Risk reduction | Low |
| 10 | **Mean-reversion overlay** -- detect oversold conditions (RSI < 30 on 15-min) for bounce trades | +Rs 2,000-5,000 | Medium |

---

## Appendix: Key Price Data

### Apr 10 Nifty 50 -- Full Day
- Open: 23,881 | High: 24,074 | Low: 23,856 | Close: 24,051
- Change: +0.71% (mild bull)
- Regime: MILD BULL (not SIDEWAYS as v5 called)

### Apr 9 Nifty 50 -- Full Day
- Open: 23,909 | High: 23,991 | Low: 23,683 | Close: 23,775
- Change: -0.56% (bear)
- Regime: BEAR (v4 had no regime detection, went all-long)

### v5 SWING Positions Carried Forward (End of Apr 10)
- ICICIBANK long at 1302.9 (current ~1322, unrealized +1.5%)
- HEROMOTOCO long at 5373.5 (current ~5466, unrealized +1.7%)
- BAJAJ-AUTO long at 9673.0 (current ~9815, unrealized +1.5%)
- SHRIRAMFIN long at 1026.8 (current ~1028, unrealized +0.2%)
- AXISBANK long at 1345.8 (current ~1351, unrealized +0.4%)
- EICHERMOT long at 7255.0 (current ~7424, unrealized +2.3%)
- WIPRO long at 205.6 (current ~205, unrealized -0.3%) -- CONFLICTING with IT short thesis
- M&M long at 3208.7 (current ~3260, unrealized +1.6%)
- BAJAJFINSV long at 1794.4 (current ~1809, unrealized +0.8%)
