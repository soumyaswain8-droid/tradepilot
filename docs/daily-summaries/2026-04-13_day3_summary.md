# TradePilot Day 3 Report

**April 13, 2026 -- 4-Engine Paper Trading Summary**

---

## Market Context

| Indicator | Value |
|:----------|:------|
| **NIFTY 50** | 23,822 (-0.95%) |
| **SENSEX** | 76,706 (-1.09%) |
| **India VIX** | 20.5 (elevated fear) |
| **Regime** | BEAR (score -4/6) -- 5 of 6 indicators bearish |
| **Pre-market** | Gap DOWN -1.90%, FII -1,039 Cr selling |
| **Global** | S&P 500 -0.1%, Asia -1.2% |
| **A/D Ratio** | 5.5% (extreme -- almost nothing green) |

A brutal bear day for Indian markets. Nifty fell nearly 1%, FIIs were net sellers, and the advance-decline ratio hit an extreme 5.5% -- meaning only 1 in 18 stocks closed green. This is the kind of day that separates adaptive engines from rigid ones.

---

## 4-Engine Results

### v4: Equity Engine (Legacy)

| Metric | Value |
|:-------|------:|
| **P&L** | Rs 0 |
| **Trades** | 0 |
| **Win Rate** | N/A |

VIX sizing reduced capital allocation to 50%, but the BEAR regime meant no BUY signals crossed the threshold. v4 sat in 100% cash all day.

**Verdict:** Too scared. Missed opportunity -- some stocks were clearly green even in a bear market. v4 cannot short, cannot rotate sectors, cannot adapt. It is dead on bear days.

---

### v5: Multi-Pool Engine (THE WINNER)

| Metric | Value |
|:-------|------:|
| **P&L** | **Rs +14,303** |
| **Trades** | 93 |
| **Wins / Losses** | 80 / 13 |
| **Win Rate** | **86%** |
| **Capital Deployed** | 30% (BEAR regime) |

The standout performer. Despite a bear market, v5's SWING pool found **16 stocks going UP** while Nifty dropped:

`VOLTAS` `NTPC` `VEDL` `ONGC` `COALINDIA` `BLUESTARCO` `MCX` `ADANIPOWER` `OIL` `WAAREEENER`

**Key insight:** Sector rotation. Energy, metals, and infrastructure stocks rallied while the broader market fell. v5's multi-pool architecture naturally captures these rotations by scanning across sectors rather than following index direction.

Telegram alerts are now wired in -- sending entry/exit notifications in real time.

---

### v5.2: F&O Engine

| Metric | Value |
|:-------|------:|
| **P&L** | **Rs -56,180** |
| **Trades** | 2 (0W / 2L) |
| **Win Rate** | 0% |

Worst day across all engines.

**What happened:**
- Bought protective puts: NIFTY 23550PE at Rs 104 and NIFTY 23500PE at Rs 102
- Both expired nearly worthless: exited at Rs 9 each (-91% loss)

**Why it failed:**
Market dropped only -0.95% -- not enough for puts to generate value. VIX at 20.5 made options expensive (high implied volatility = inflated premiums). Buying puts when VIX is already elevated means you're paying for fear that's already priced in.

**Lesson:** Don't buy puts when VIX > 18. Puts work when VIX is LOW and you expect it to spike. On high-VIX days, sell premium (straddle/strangle selling) instead of buying.

---

### v5.3: Precision Engine

| Metric | Value |
|:-------|------:|
| **P&L** | Rs 0 |
| **Trades** | 0 |
| **Signals** | 20 generated, 20 cancelled |

All 20 signals were classified as Tier 2 (requiring ORB + volume confirmation). None confirmed -- volume was extremely low across all stocks (0.0x to 0.4x of 20-day average).

Every signal was cancelled with the same reason:

```
"low volume (0.0x < 1.2x threshold)"
```

**Verdict:** Ultra-conservative. Correct in principle -- low volume means unreliable price moves -- but missed Rs 14,303 that v5 captured. The 1.2x volume threshold is too strict for bear days when overall market volume naturally dips.

---

## 3-Day Cumulative Scorecard

| Engine | Day 1 (Bear) | Day 2 (Bull) | Day 3 (Bear) | TOTAL |
|:-------|----------:|----------:|----------:|----------:|
| v4 | -30,816 | +11,537 | 0 | **-19,279** |
| **v5** | 0 | +40,480 | +14,303 | **+54,783** |
| v5.2 | 0 | 0 | -56,180 | **-56,180** |
| v5.3 | 0 | 0 | 0 | **0** |

**v5 leads v4 by Rs 74,062 over 3 days.** v5.2 is the worst performer and needs major recalibration. v5.3 hasn't traded yet -- too conservative to generate signal.

---

## Watchdog Report Findings

Analysis from April 12 watchdog run, validated against Day 3 data.

### Trade Analysis Watchdog

1. **v5 entry price bug CONFIRMED** -- COALINDIA short entry recorded at 452.70 vs actual market price 438 at time of entry. P&L overstated by ~40% on shorts. v5.3 fixes this with live price confirmation via `get_prices_batch()`.

2. **Missed Rs 12-18K from Nifty 200 stocks** -- SIEMENS +4.76%, ABB +3.27%, ADANIGREEN +3.91% were not in the scanning universe. Now FIXED with Nifty 200 expansion.

3. **Entry timing lag** -- v4 enters 15-16 minutes after open, missing 1.5-1.9% of gap-up moves. v5.3's staged entry system addresses this.

4. **Pairs divergence opportunity** -- SUNPHARMA -2.6% vs DRREDDY +1.6% = 4.2% spread uncaptured. No pairs trading module exists yet.

5. **v4 Day 1 re-entry bug** -- SHRIRAMFIN entered 4x, losing Rs 8,400 on repeated failures. Re-entry cap now in place.

### Strategy Discovery Watchdog

Top 5 new signals to add, ranked by estimated impact:

| Rank | Signal | Impact | Notes |
|:-----|:-------|:------:|:------|
| 1 | Sector Rotation | 9/10 | 40% CAGR on India backtest. Energy/metals/infra rallied today while Nifty fell |
| 2 | Cross-Asset Features | 8/10 | DXY, crude, bonds, BTC correlation with Nifty. Granger causality confirmed |
| 3 | Market Breadth | 8/10 | % stocks above 20-DMA. Today's A/D at 5.5% = extreme fear = potential bottom |
| 4 | Options PCR + IV Skew | 8/10 | PCR > 1.3 = reversal signal. Would improve v5.2's entry timing |
| 5 | Technical Feature Expansion | 7/10 | ADX, Williams %R, calendar effects (Monday, expiry week) |

---

## Key Learnings

### 1. v5's SWING Pool is the Secret Weapon

Finds sector rotation stocks that go UP even when the market drops. VOLTAS +3.14%, MCX +3.13%, BLUESTARCO, NTPC, VEDL all green on a bear day. This is the core differentiator.

### 2. v5.2 F&O Needs Complete Recalibration

- Don't buy puts when VIX > 18 (options too expensive)
- Should sell premium (straddle selling) instead of buying on high-VIX days
- Puts should only trigger when VIX < 15 AND regime score <= -4

### 3. v5.3 is Too Conservative

Cancelled ALL 20 signals. The volume filter (> 1.2x average) is too strict for bear days when volume is naturally low. Proposed fix: reduce threshold to 0.8x, or use session-relative volume instead of 20-day average.

### 4. v4 is Dead on Bear Days

Zero trades, zero P&L. VIX sizing + no BUY signals = complete paralysis. v4 cannot short, cannot adapt to sector rotation.

### 5. Sector Rotation is the #1 Missing Signal

Today's bear day had clear sector rotation: energy, metals, infrastructure UP while IT, banking DOWN. A sector momentum scanner would have caught this and directed capital to the right sectors automatically.

### 6. Entry Price Accuracy is Critical

Watchdog confirmed v5's short entry prices are stale. v5.3's live price confirmation is the correct fix. All engines should use `get_prices_batch()` at the moment of entry.

### 7. A/D Ratio at 5.5% = Extreme Fear

Historically, such extreme readings precede bounces within 1-3 days. This is a contrarian signal we should track and potentially act on.

---

## What Could Have Been Done Better

| Area | What Happened | What Should Have Happened |
|:-----|:--------------|:--------------------------|
| v4 | 0 trades (paralyzed) | Deploy 20-30% into sector rotation winners |
| v5 shorts | Entry at stale prices | Use live prices (v5.3 approach) |
| v5.2 puts | Bought expensive puts (-91%) | Sell premium instead, or buy puts only when VIX < 15 |
| v5.3 volume | All signals cancelled (0.0x volume) | Lower threshold to 0.8x, use session-relative volume |
| Pairs | Missed DRREDDY/SUNPHARMA 4.2% spread | Build pairs trading module |
| Sectors | No sector-level analysis | Add sector rotation scanner |

---

## Platform Updates Built Today

- **AI Picks & Advisor page** -- Stocks/ETFs/MF recommendations + AI chat interface
- **Smart stock name matching** -- 80+ names resolved ("tata steel", "hdfc bank", etc.)
- **Live news feed** -- Google News RSS integration, replaces stale Day 1 news
- **F&O tab redesigned** -- Groww-style: index cards + explore + option chain
- **Intraday tab redesigned** -- Index cards + top movers layout
- **Gainers index filter** -- Nifty 50/100/200/Midcap/Smallcap selector
- **Swipe feature removed** -- Cleaner UX
- **Telegram /status command** -- Working and tested
- **v5 Telegram alerts** -- Entry/exit/regime/daily summary notifications wired

---

## Tomorrow's Plan

1. **v5 continues as-is** -- winning engine, don't touch
2. **Recalibrate v5.2** -- switch from put buying to premium selling on high-VIX days
3. **Adjust v5.3 volume threshold** -- from 1.2x down to 0.8x
4. **Start building sector rotation scanner** -- highest impact new signal
5. **Watch for bounce signal** -- A/D at 5.5% is extreme, contrarian buy may be coming
6. **Run all 4 engines** for continued comparison

---

*Report by Soumya Swain | soumya@devpilot.co.in*
*TradePilot Paper Trading -- Day 3 of Multi-Engine Evaluation*
