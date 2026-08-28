# Sustained Runners: Can You Screen For the Next Double?

*Overnight research lane — survivorship-free 5-year census of 50%/100%/200% multi-week runs, and an out-of-sample test of whether their precursors are tradeable.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Lane** | Sustained runners (multi-week, not one-day spikes) |
| **Version** | `v1.0.0` |
| **Status** | Complete — negative result |
| **Data** | `quant/data/sf_ret.parquet` + `sf_turn.parquet`, 1232 sessions x 3046 symbols, 2021-06 to 2026-06, survivorship-free (includes 417 delisted names) |
| **Created** | 2026-08-28 |
| **Updated** | 2026-08-28 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## VERDICT: NOT VIABLE

The precursors of a sustained run are **real but useless**. They separate future runners
from non-runners by 0.3–0.6 standard deviations in-sample, yet a screen built on them
fails completely out-of-sample: it does **not** raise the probability of catching a double
(0.21% vs a 0.24% base rate — no lift at all), while it **triples** the probability of a
50%+ loss (2.29% vs 0.76%).

**THE NUMBER:** market-neutral net excess return of the screen, 60-day hold, holdout period:
**−5.14%** per trade, n = 5,767, t = **−10.95** (date-clustered). The simpler interpretable
rule: **−2.82%**, n = 67,401, t = **−16.09**. Both are negative with overwhelming significance
in the wrong direction.

Cost is indeed irrelevant here — 0.59% on a 60-day hold. The screen loses by 5–10x the toll.
**The precursors have no predictive power. They have anti-predictive power.**

---

## 1. The Run Census — How Many Doublers Are There?

Universe restricted to genuinely tradeable names: traded ≥90% of the last 60 sessions
**and** median daily turnover ≥ Rs 25 lakh. That is a median of **1,404 names per day** out
of 3,046. Runs are counted non-overlapping (a new run cannot start inside a prior one).

::: {.metrics-table}

| Window / Threshold | Runs (5 yrs) | Distinct symbols |
|:-------------------|-------------:|-----------------:|
| 20d ≥ +50% | 1,363 | 851 |
| 20d ≥ +100% | 89 | 82 |
| 20d ≥ +200% | **0** | 0 |
| 60d ≥ +50% | 2,965 | 1,414 |
| 60d ≥ +100% | 462 | 384 |
| 60d ≥ +200% | 18 | 16 |
| 120d ≥ +50% | 3,348 | 1,557 |
| 120d ≥ +100% | 929 | 695 |
| 120d ≥ +200% | 125 | 117 |

:::

**Read this carefully.** A 60-day double is a genuinely rare event: 462 occurrences across
five years and ~1,400 tradeable names — roughly **92 per year**, or a base rate of
**0.33% of all stock-days**. A 20-day triple among tradeable stocks happened **zero times
in five years**.

### By calendar year (60-day window)

::: {.metrics-table}

| Year | ≥ +50% | ≥ +100% | ≥ +200% |
|:-----|-------:|--------:|--------:|
| 2021 (partial, from Jun) | 234 | 54 | 4 |
| 2022 | 471 | 60 | 5 |
| 2023 | **956** | **160** | 3 |
| 2024 | 646 | 96 | 4 |
| 2025 | 442 | 56 | 1 |
| 2026 (partial, to Jun) | 216 | 36 | 1 |

:::

Runs are a **regime phenomenon**, not a constant. 2023 produced 3x more doublers than 2025.
Any strategy calibrated on 2021–2023 is calibrated on a small-cap bull market.

### By liquidity tercile (proxy for size)

Terciles computed cross-sectionally on the run's start date, within the tradeable universe.

::: {.metrics-table}

| Window / Threshold | Bottom (small) | Middle | Top (large) |
|:-------------------|---------------:|-------:|------------:|
| 20d ≥ +50% | 640 (47%) | 456 (33%) | 267 (20%) |
| 60d ≥ +50% | 1,191 (40%) | 1,006 (34%) | 768 (26%) |
| 60d ≥ +100% | 210 (45%) | 152 (33%) | 100 (22%) |
| 120d ≥ +100% | 416 (45%) | 294 (32%) | 219 (24%) |

:::

Runs concentrate ~2x in the least liquid tercile. This is the first warning: the doublers
live exactly where the halvings live, and where a Rs 25,000 account has the worst fills.

---

## 2. What Was Observable Before the Run Started

Features measured at the run's start date (no lookahead: features use data up to and
including day *t*; the run return is *t → t+60*). "Run" = the 4,141 stock-days whose forward
60-day return was ≥ +100%. "Control" = the other 1,256,775 tradeable stock-days.

::: {.gap-table}

| Precursor | Runners (mean) | Control (mean) | Separation (σ) |
|:----------|---------------:|---------------:|---------------:|
| 60d realised volatility (ann.) | 0.483 | 0.390 | **+0.56** |
| 20d realised volatility (ann.) | 0.473 | 0.375 | +0.49 |
| Prior 252-day return | +45.0% | +19.0% | **+0.47** |
| Distance above 200-day MA | +11.9% | +4.0% | +0.35 |
| Prior 120-day return | +18.3% | +7.7% | +0.32 |
| Position in 52-week range (0–1) | 0.599 | 0.511 | +0.27 |
| Prior 60-day return | +9.3% | +3.7% | +0.25 |
| Distance above 50-day MA | +3.3% | +1.0% | +0.21 |
| Prior 20-day return | +3.6% | +1.3% | +0.19 |
| Turnover trend (log 20d/60d) | −0.013 | −0.080 | +0.15 |
| Drawdown from 52w high | −19.4% | −21.6% | +0.14 |
| Turnover level (log10) | 2.92 | 3.06 | **−0.18** |

:::

The picture is coherent and matches folklore: **a future runner is a small, volatile stock
that has already been running, sits near its 52-week high, is extended above its 200-day
moving average, and has rising turnover.** Every sign points the way you would expect. The
separations are statistically enormous given n > 1.2M.

**This is exactly why the lane looked promising. It does not survive step 3.**

---

## 3. THE KEY TEST — Screen Built on Train, Run Forward on Holdout

- **Train:** 2021-06-17 → 2023-12-29 (468,030 stock-days, 2,263 run-starts)
- **Holdout:** 2024-01-01 → 2026-06-12 (792,886 stock-days, 1,878 run-starts)
- Split by date **before** any searching. Nothing was tuned on the holdout.
- Two screens: (a) L2 logistic regression on all 12 precursors, class-balanced;
  (b) an interpretable 4-condition rule, best of an 81-cell grid searched **on train only**.
- Every trade charged **0.6%** (Rs 5,000 position: 0.2% STT + 0.015% stamp + Rs 18.80 DP fee).
- Every number is also reported **market-neutral** (excess over the equal-weighted universe
  over the identical 60 days), because the train period was a bull market and the holdout
  was not: baseline 60-day return was **+8.41% in train** and **+0.84% in holdout**.

::: {.suite-table}

| Screen | n | Median | Net excess mean | t (date-clustered) |
|:-------|--:|-------:|----------------:|-------------------:|
| TRAIN baseline (all tradable) | 468,030 | +4.93% | −2.10% | −28.28 |
| TRAIN logit top 1% | 4,681 | +0.89% | −3.28% | −5.99 |
| TRAIN logit top 5% | 23,402 | +3.42% | −1.60% | −8.51 |
| TRAIN logit top 10% | 46,803 | +4.79% | −0.84% | −4.74 |
| TRAIN best rule *(grid-searched here)* | 53,411 | +6.93% | **+0.20%** | **+2.67** |
| HOLDOUT baseline (all tradable) | 792,886 | −1.22% | −1.57% | −39.08 |
| HOLDOUT logit top 1% | 5,767 | 0.00% | **−5.14%** | **−10.95** |
| HOLDOUT logit top 5% | 32,749 | −1.60% | −3.51% | −20.52 |
| HOLDOUT logit top 10% | 67,482 | −1.56% | −2.50% | −17.39 |
| HOLDOUT **same rule** | 67,401 | −1.99% | **−2.82%** | **−16.09** |

:::

The best in-sample rule (`ret60 ≥ 10%` AND `52w-range ≥ 0.70` AND `turnover rising` AND
`vol60 ≥ 0.35`) is the only positive line in the table: **+0.20% excess, t = +2.67** on train.
Pushed forward one day into the holdout it becomes **−2.82%, t = −16.09**. That is not decay.
That is a **sign flip with a 19-point swing in t**. It is the textbook signature of a rule
fitted to a bull-market regime.

### Full distribution of the screened holdout trades (rule, n = 67,401)

::: {.metrics-table}

| Percentile | 60-day return | |
|:-----------|--------------:|:--|
| 5th | −33.6% | |
| 25th | −14.5% | |
| **50th (median)** | **−1.99%** | the number that matters for 5 draws |
| 75th | +12.3% | |
| 95th | +42.5% | |
| 99th | +74.8% | |
| Mean | +0.30% | vs market +1.82% |

:::

The payoff is indeed lottery-shaped — a long right tail. **But the lottery is negatively
priced.** The median ticket loses money, and the market did better with no work.

### By holdout year (rule)

::: {.metrics-table}

| Year | n | Median | Net excess mean | t |
|:-----|--:|-------:|----------------:|--:|
| 2024 | 50,116 | −1.44% | −3.18% | −22.98 |
| 2025 | 14,778 | −4.97% | −1.95% | −9.48 |
| 2026 (to Jun) | 2,507 | +1.54% | −0.78% | −1.75 |

:::

Negative in all three holdout years. There is no sub-period where it works.

---

## 4. Cost Is Not the Problem — Stated Honestly

At Rs 5,000 per position (Rs 25,000 / 5 names), a delivery round trip costs **0.591%**:
0.2% STT + 0.015% stamp + Rs 18.80 flat DP fee. Over a 60-day hold that is negligible
against a distribution with a 21% standard deviation.

**So this is a clean test of predictive power, and the answer is no.** The screen loses
2.8–5.1% market-neutral per trade. Making the toll zero would still leave it losing
2.2–4.5%. There is no cost structure, no broker, and no account size that rescues it.
The precursors simply do not predict.

One trap worth recording: with a **loose** liquidity filter (including stale, thinly-traded
shells) the screen appeared to double the holdout hit rate, 0.24% → 0.46%. That entire
apparent lift vanished the moment I required stocks to trade ≥90% of sessions with
≥ Rs 25 lakh median turnover. **The "edge" was untradeable names with stale prints.**

---

## 5. Survivorship and Ruin — Both Tails

The decisive table. Holdout period, 60-day forward outcomes.

::: {.gap-table}

| Population | n | P(+100%) | P(−50%) | Doublers per halving |
|:-----------|--:|---------:|--------:|---------------------:|
| All tradable stocks (baseline) | 792,886 | 0.24% | 0.76% | **0.31** |
| Rule screen | 67,401 | 0.27% | 1.60% | **0.17** |
| Logit top 1% screen | 5,767 | 0.21% | 2.29% | **0.09** |

:::

**The screen finds 1 doubler for every 11 halvings.** Doing nothing finds 1 for every 3.
The precursors — high volatility, extended above the 200-day MA, near 52-week highs, small —
identify *fat-tailed* stocks, not *right-tailed* ones. They correctly find where the big
moves live and are completely unable to tell you which direction the big move goes. The
screen is not merely useless; it is a **3.4x deterioration** of the unconditional tail ratio.

Delisting risk is real but not the driver: 1.1% of 60-day holds hit a stock that stopped
trading inside the window, essentially identical for the screen (1.05%) and the baseline
(1.13%). The losses come from live stocks falling, not from disappearances.

### Supplementary: can you just ride a run once it is visibly underway?

The lane's premise was that a multi-week run "gives you days to enter." Tested directly —
buy after the move is already on the tape, hold 60 days, market-neutral, net of costs:

::: {.suite-table}

| Entry trigger | Holdout n | Net excess | t | P(+100%) / P(−50%) |
|:--------------|----------:|-----------:|--:|:-------------------|
| Up ≥30% in 20d | 18,374 | −2.59% | −7.86 | 0.52% / 2.06% |
| Up ≥50% in 20d | 3,487 | −5.45% | −6.07 | 0.83% / 3.10% |
| Up ≥50% in 60d | 24,758 | −3.43% | −8.00 | 0.34% / 2.07% |
| **Up ≥100% in 60d** | 2,318 | **−7.58%** | −6.10 | **0.47% / 4.87%** |
| Up ≥100% in 120d | 10,671 | −4.87% | −7.15 | 0.32% / 2.64% |

:::

Every trigger loses, in both train and holdout, and **the stronger the run you chase, the
worse you do**. Buying a stock that has just doubled in 60 days is the single worst trade in
this entire study: it loses 7.6% market-neutral and gives you a **10:1 chance of halving
versus doubling**. Runs mean-revert violently once visible.

Individual precursors on their own fare no better out-of-sample (market-neutral excess,
holdout): `ret252` top decile −0.37% (t = −2.13), `d200` top decile −1.47% (t = −6.62),
`rng52` top decile −0.56% (t = −2.77), `vol60` top decile −3.76% (t = −36.87).

---

## 6. Capital Reality — 5 Names at Rs 25,000

200,000 Monte Carlo portfolios, each drawing *k* trades with replacement from the actual
holdout screened return distribution, equal-weighted, net of the 0.6% toll.

::: {.suite-table}

| Positions (k) | P(portfolio down) | Median | 5th pct | P(< −20%) | P(> +50%) |
|:--------------|------------------:|-------:|--------:|----------:|----------:|
| 1 | 56.6% | −2.53% | −34.3% | 17.0% | 3.19% |
| **5** | **53.4%** | **−0.89%** | −16.7% | 2.31% | 0.02% |
| 10 | 53.6% | −0.65% | −12.2% | 0.29% | 0.00% |
| 20 | 53.4% | −0.45% | −8.8% | 0.00% | 0.00% |
| 5 (random tradable stocks) | 51.9% | −0.42% | −14.0% | 0.92% | 0.02% |

:::

**At 5 names you end the 60 days down 53.4% of the time, with a median of −0.89%.**
Picking 5 stocks *at random* from the tradeable universe does better (51.9% down,
median −0.42%). The screen is measurably worse than a coin flip against a dartboard.

The diversification arithmetic is also brutal in a way worth internalising. With 5 draws
from a lottery-shaped distribution, the probability of the portfolio gaining more than 50%
is **0.02%** — one in 5,000 — because you need several of your five to be extreme winners
simultaneously. But the probability of a >20% portfolio loss is 2.3%, over 100x higher.
Concentrating to 1 name raises P(+50%) to 3.2% but raises P(−20%) to 17%. **Small accounts
cannot buy the right tail of this distribution; they can only buy its variance.**

---

## Multiple-Testing Note

Roughly 100 distinct specifications were evaluated (9 census cells, 3 logit cut-points x 2
periods, an 81-cell rule grid, 5 ride-the-run triggers, 4 single-feature deciles). Bonferroni
at n ≈ 100 requires |t| ≥ ~3.5. **No positive result anywhere in the study reaches even
t = +2.7, and that one lone positive is in-sample.** There is nothing to correct for.

---

## Conclusion

Sustained runs are real, rare (~92 doublers a year across a 1,400-name tradeable universe),
strongly regime-dependent (2023 had 3x more than 2025), and concentrated ~2x in the smallest
liquidity tercile. Their precursors are also real and exactly what folklore predicts:
volatile, already-trending, near 52-week highs, extended above the 200-day MA, small,
with rising turnover.

**None of it is tradeable.** Those precursors identify high-variance stocks, not
high-return stocks. Screening on them leaves the doubling rate unchanged and triples the
halving rate, turning an unconditional 1-in-3 doubler-to-halver ratio into 1-in-11. The
one rule that worked in-sample flipped from t = +2.67 to t = −16.09 the day the holdout
began. Chasing a run after it is visible is worse still: −7.6% market-neutral, with a
10:1 chance of halving instead of doubling.

Cost was never the obstacle in this lane — 0.59% on a 60-day hold. The obstacle is that
the information is not there. **This lane should be closed.**
