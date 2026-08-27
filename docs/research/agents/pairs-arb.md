# Pairs trading / statistical arbitrage — NOT VIABLE

**VERDICT: not viable.** Cointegration selected on the training window does not survive out of
sample, and even at zero cost the out-of-sample spread edge is insignificant.

**THE NUMBER:** k=2.0, 58 pairs, n=518 OOS trades (296/yr), win rate 60.8%,
**net −25.9 bps per trade after both legs' costs, t = −0.68**. Gross (zero-cost) is +20.8 bps,
t = +0.54 — not significant even before the toll. Worst drawdown −5.7 units of one-leg notional
(≈ −5.7 × Rs1L = −Rs5.7L on a book carrying ~Rs20–30L of gross exposure, roughly −20%).

| k | trades | /yr | win rate | gross bps | **net bps** | t (net) | max DD (leg-units) |
|---|---|---|---|---|---|---|---|
| 1.5 | 744 | 425 | 61.6% | −12.3 | **−59.1** | −1.97 | −8.8 |
| 2.0 | 518 | 296 | 60.8% | +20.8 | **−25.9** | −0.68 | −5.7 |
| 2.5 | 309 | 177 | 51.5% | −1.9 | **−48.6** | −0.91 | −4.3 |

**WHAT I TESTED.** sf_ret.parquet split by date: train = 2021-06-17→2024-09-10 (800 sessions),
holdout = 2024-09-11→2026-06-12 (432). Liquidity filter on the train window only (median turnover
≥ Rs20 cr/day, ≥97% coverage in both windows) → 269 names → 36k candidate pairs. Screened on TRAIN
ONLY: return correlation ≥ 0.50, OLS hedge ratio on log prices, Dickey-Fuller t on the residual
< −3.0, half-life 3–60 days → **58 cointegrated pairs** (PSU banks, metals, IT, PSU power — all
economically sensible). Traded on the HOLDOUT with the train-fixed beta and a causal 60-day rolling
z-score: enter |z|>k, exit |z|<0.25, 30-day time stop, 4σ stop. Costs charged on both legs:
delivery 0.2% STT + 0.015% stamp + Rs18.80 DP per leg per sell = **46.8 bps round trip for the pair**
at Rs1L/leg (21.4 bps if run intraday MIS — still loses).

**WHY IT FAILED — the specific arithmetic.**
1. *Cointegration evaporates.* Of the 58 train-selected pairs, only **1** is still cointegrated in
   the holdout at t<−3.0 (6 at t<−2.5). Mean DF t decays −3.61 (train) → −1.32 (holdout).
2. *In-sample looks superb and is a mirage:* same pairs, same rules, train window: +195 bps net,
   **t = 7.34**, 67.8% win rate. Holdout: −26 bps, t = −0.68. Textbook selection bias.
3. *The toll.* OOS gross +20.8 bps vs 46.8 bps two-leg cost — the spread moves less than half the
   toll. Two legs means two STT hits and two DP fees.
4. *High win rate, negative mean.* 61% of trades win. The losers are the pairs that de-cointegrate
   and never come back (4σ stop / 30-day timeout), and they are 2–3× the size of the winners.

**Capital note.** Rs18.80 DP is paid twice (Rs37.60/round trip): 3.8 bps at Rs1L/leg, 15 bps at
Rs25k/leg, 75 bps at Rs5k/leg. Small pair positions are punished doubly. Also: cash-market short
*delivery* is not permitted in India — the short leg needs futures or SLB, so the real universe is
F&O names only and the real cost is higher than modelled here. Both facts make the gap worse, not
better.

**Do not retry** the same-window select-and-trade version; it produces t=7.3 and is false.
