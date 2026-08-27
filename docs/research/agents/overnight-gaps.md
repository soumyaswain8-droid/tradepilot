# Overnight vs Intraday Decomposition — NSE 2022-2025

**VERDICT: not viable as a strategy — but the decomposition is a major structural finding.**

**THE NUMBER:** In the liquid NSE universe, **100% of the equity return is earned overnight.**
Overnight (prev close -> open) = **+68.7%/yr, t=14.1, Sharpe 7.1, maxDD -9.7%**.
Intraday (open -> close) = **-48.2%/yr, t=-5.6, Sharpe -2.8, maxDD -86.0%**.
Total = +19.3%/yr. n=987 sessions, ~850 names/day (prior-day turnover >= Rs5cr, price >= Rs20).

## 1. The decomposition (equal-weight, last-traded prices)

| Component | bps/day | ann % | vol bps | Sharpe | t | maxDD |
|---|---:|---:|---:|---:|---:|---:|
| OVERNIGHT (prevC->open) | +27.25 | +68.7 | 60.8 | 7.11 | 14.07 | -9.7% |
| INTRADAY (open->close) | -19.12 | -48.2 | 107.3 | -2.83 | -5.60 | -86.0% |
| TOTAL | +7.65 | +19.3 | 117.3 | 1.04 | 2.05 | -24.9% |

Stable every single year: overnight ann +65.7 / +80.7 / +82.6 / +45.8 for 2022/23/24/25; intraday
ann -61.5 / -35.4 / -52.5 / -43.3. Never flips sign. Intraday carries ~1.8x the volatility of
overnight for negative return.

**Artifact checks passed.** (a) NSE CLOSE_PRICE is a 30-min VWAP, not a trade — only 7.0% of
rows have CLOSE==LAST. Redoing everything off LAST_PRICE (corporate-action adjusted via NSE's
own PREV_CLOSE/prior-close factor) moves overnight from 69.1% to 68.7%. The VWAP wedge is
0.33 bps/day. Not the explanation. (b) Bid-ask: effect is monotone in liquidity but survives at
the very top — Top-25-by-turnover names give overnight **+60.3%/yr, t=11.2**. A 24 bps/day
effect cannot be a spread artifact in the 25 most-traded stocks on the exchange.

| Liquidity tercile | ON ann | ID ann | TOT ann |
|---|---:|---:|---:|
| T1 low | +76.5 | -57.3 | +17.6 |
| T2 mid | +71.0 | -50.6 | +19.1 |
| T3 high | +58.6 | -36.7 | +21.2 |
| Top 100 by turnover | +58.5 | -35.5 | — |
| Top 25 by turnover | +60.3 | -34.5 | — |

## 2. Buy-at-close / sell-at-open — FAILS on the flat DP fee and STT

Gross +27.25 bps/day looks enormous. It is almost exactly eaten by delivery costs, because a
one-day hold pays the **full** delivery bill every single day.

| Position | Delivery cost | Net/day | Net/yr |
|---|---:|---:|---:|
| Rs 3,000 | 84.9 bps | -57.6 | **-145.3%** |
| Rs 25,000 | 29.7 bps | -2.5 | -6.3% |
| Rs 100,000 | 24.1 bps | +3.2 | +7.9% |
| Rs 1,000,000 | 22.4 bps | +4.8 | +12.2% |

Top-100-liquid version: net **-2.2%/yr at Rs1L (t=-0.45)**, **+2.0%/yr at Rs10L (t=0.41)**.
The arithmetic: 0.2% STT + 0.015% stamp + fees = **22.4 bps floor even at infinite size**, and
252 round trips/yr = **56.5% of capital per year in cost** against a 58.5% gross. There is no
position size that fixes this — the STT is proportional, so the cliff logic that saves intraday
does not apply. You would need >2x the observed overnight drift to clear it. Dead, t < 0.5.

The return is real; it is just not *repeatedly* harvestable. Buy-and-hold captures it at one
cost, which is exactly what an index fund already does (that is the 19.3% total).

## 3. Why our intraday work keeps failing — the structural answer

**An intraday long book is fighting a -19.1 bps/day drift before it pays a single rupee of
costs.** Net-long intraday you start each day -19 bps in the hole, then pay the 107 bps toll.
That is a -48%/yr structural headwind that no price feature will overcome. This is the cleanest
explanation yet for the 1,104-rule null result and the ridge/GBM inversions: the intraday
session is where the *negative* half of the return lives.

The mirror is not a fix either. Intraday **short** bias earns +19.1 bps/day gross vs the 107 bps
round-trip toll — still **5.6x too small**, before borrow and before the -86% drawdown profile
of being short a market that rises overnight.

Cross-sectional intraday dispersion is 234 bps (1-sigma) vs 97 bps overnight, so the intraday
*pool* is not empty — a perfect-foresight decile spread would earn ~832 bps/day. The 107 bps
toll is only 4.6% of a 1-sigma intraday move. The pool exists; we simply have no skill in it.
The problem is signal, not room.

## 4. Gap continuation vs reversion — real signal, killed by the toll

Cross-sectionally demeaned (market-neutral), sorted into gap deciles, split by date at 2024-01-01.
**Gaps REVERT, strongly and monotonically, and it holds out of sample.**

| Gap decile | IS gap bps | IS next-intraday | OOS gap bps | OOS next-intraday |
|---|---:|---:|---:|---:|
| D1 (biggest gap down) | -142.7 | **+55.3** | -148.5 | **+60.2** |
| D5 | -10.3 | +5.6 | -12.1 | +5.2 |
| D6 | +16.6 | -10.0 | +16.6 | -10.1 |
| D10 (biggest gap up) | +166.0 | **-63.4** | +173.9 | **-66.4** |

D1-D10 reversion spread: IS **+118.3 bps/day, t=33.3**; OOS **+126.3 bps/day, t=29.4**,
Sharpe 21, maxDD -0.75%. This is by far the largest and most significant intraday effect
anywhere in this project — and it still loses money:

**Two legs x 107 bps = 214 bps toll. Net = 126.3 - 214 = -87.7 bps/day.** Long-short is dead.

Large single-name gaps, single leg, demeaned, holdout 2024-25:
- gap **up** >+3% (n=8,027): subsequent intraday **-99.1 bps, t=-21.6** -> short it: 99.1 - 107 = **-7.9 bps**
- gap **down** <-3% (n=5,058): subsequent intraday **+106.6 bps, t=+18.6** -> buy it: 106.6 - 107 = **-0.4 bps**

Exact breakeven. n is large, t is ~20, the effect is stable across the date split — and it lands
within 1 bps of the toll. This is the project's recurring pattern in its purest form: the edge is
genuine, persistent, statistically overwhelming, and approximately equal to the cost of taking it.

## What to take away

1. **Where the return lives is now known.** All of it is overnight. Any strategy that is flat
   overnight has structurally forfeited the equity premium and is trading a -48%/yr session.
2. **Do not run net-long intraday books.** The -19 bps/day drift is a headwind, not noise.
3. **Gap reversion is the best intraday signal we have found (OOS t=29).** It is ~0.5-1.0x the
   toll. If execution cost ever drops below ~100 bps round trip — larger clip sizes do not help
   (cost is flat below Rs66,667), but STT/brokerage regime change or a broker with better
   fills would — this is the first thing to re-test. Nothing else is this close.
4. The 0.2% delivery STT makes *any* daily-turnover overnight strategy impossible at 56.5%/yr
   cost drag, independent of capital.

---
Data: `quant/data/bhavcopy/` 1,304 files (10 skipped = market holidays), EQ series only,
2022-01-01..2025-12-31, 839k stock-days. Filters: price >= Rs20, prior-day turnover >= Rs5cr,
|component| < 25%, gap <= 5 calendar days, corporate-action factor in [0.5, 2.0].
Scripts: scratchpad `load_bhav.py`, `decomp2.py`.
