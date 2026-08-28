# Precursors: what did tomorrow's biggest winners look like today?

**VERDICT: Winners are forecastable. Winning on them is not.**

The top-50 daily gainers are strongly predictable — 4.87x lift out-of-sample, AUC 0.695,
date-clustered t=32.5. That part is real and survives every honest correction. But the
same signal predicts the top-50 *losers* at **6.28x**, which is higher. The features
identify tomorrow's lottery tickets, not tomorrow's direction. The predicted basket goes
**down** more often than up (P(up)=0.443, median return −0.50%/day), and its entire
positive mean return comes from the bottom decile of turnover — names you cannot trade.

**THE NUMBER:** predicted-top-50 basket, 343 holdout days, net of 0.107% intraday cost:
**−0.0224%/day, t=−0.26, max drawdown −34.3%.** Net of 0.24% delivery: **−0.1554%/day,
t=−1.81, maxDD −55.5%.** Market-neutral makes it worse, not better.

---

## Data

Built from `quant/data/sf_ret.parquet` + `sf_turn.parquet` (survivorship-free, 1232
sessions x 3046 symbols). The shared `winners_panel.parquet` had not landed, so this is an
independent build — `quant/_precursors_build.py`, output at
`docs/research/overnight/winners_panel_own.parquet`.

- **1,935,973 stock-days, 980 sessions** (2022-06 to 2026-06; first 252 sessions consumed
  by the 52-week warmup), 2,967 symbols.
- `win = 1` if the stock was a top-50 gainer that day among names that traded, had real
  turnover, traded the prior day, and had all 9 features defined. Base rate **2.53%**
  (2.24% in the holdout).
- All features measured at the **previous close** and shifted one day. No same-day
  information enters any feature.
- Mean return of an actual winner: **+8.95%**. Mean return of an actual top-50 loser: −5.79%.

## 1+2. Winners vs non-winners — naive vs date-clustered

Naive pooled t-stats are inflated by roughly **1.4x** because stock-days within a date are
correlated. The clustered column is the honest one: the daily cross-sectional difference in
z-scored feature (winners minus non-winners), t-tested across 980 days.

| feature | winner mean | non-winner mean | diff / sd | t naive | **t clustered** | days positive |
|---|---:|---:|---:|---:|---:|---:|
| vol20 | 0.0311 | 0.0232 | **+0.605** | 114.6 | **83.1** | 99.3% |
| turn_ratio | 1.815 | 1.122 | +0.430 | 57.1 | **48.7** | 95.6% |
| ret1 | +1.17% | +0.06% | +0.394 | 47.2 | **32.7** | 88.0% |
| ret5 | +2.57% | +0.35% | +0.349 | 47.7 | **31.0** | 85.6% |
| vs_sma20 | +2.45% | +0.24% | +0.322 | 46.5 | **28.5** | 84.1% |
| ret21 | +4.80% | +1.22% | +0.292 | 46.1 | **27.7** | 83.2% |
| ret63 | +7.29% | +2.70% | +0.224 | 38.5 | **21.6** | 79.3% |
| turn20 (log10) | 2.444 | 2.618 | −0.160 | −35.7 | **−22.3** | 23.2% (i.e. 76.8% negative) |
| pos52 | 0.585 | 0.541 | +0.137 | 29.0 | **16.2** | 70.0% |

Every feature clears Bonferroni at |t|>=4 by a wide margin even after clustering. The
portrait of tomorrow's winner is unambiguous and stable across 99.3% of days for `vol20`:

> **small, volatile, already moving up, with turnover spiking above its own 20-day norm.**

`vol20` is the single dominant discriminator (0.605 sd) and `turn20` is *negative* — winners
are systematically **less** liquid than the universe.

## 3. Predictive model — train/holdout split by date

Logistic regression on cross-sectionally z-scored features. Train 2022-06-22 → 2025-01-20
(637 days), holdout 2025-01-20 → 2026-06-12 (343 days). No tuning on the holdout.

Fitted coefficients: `vol20 +0.452`, `turn20 −0.239`, `turn_ratio +0.176`, `ret1 +0.105`,
`vs_sma20 +0.082`, `ret63 +0.056`, `pos52 +0.031`, `ret5 +0.008`, `ret21 −0.014`.

| | base rate | top-50 hit rate | **lift** | t clustered |
|---|---:|---:|---:|---:|
| Train | 2.72% | 12.05% | 4.43x | 47.96 |
| **Holdout** | 2.24% | **10.92%** | **4.87x** | **32.52** |

Holdout AUC **0.6952**. The lift is *higher* out of sample than in sample — this is not
overfitting. Rank stocks by this score, take the top 50, and about 1 in 9 will be an actual
top-50 gainer versus 1 in 45 at random. **The hindsight ceiling is not unreachable in the
classification sense.**

## The reason it does not pay: the signal is symmetric

| holdout, predicted top-50 | winner hit | lift | **loser hit** | **lift** | gross %/day | t | median ret |
|---|---:|---:|---:|---:|---:|---:|---:|
| full 9-feature model | 10.92% | 4.87x | **14.07%** | **6.28x** | +0.0846 | 0.98 | −0.500% |
| vol20 only | 7.18% | 3.20x | 9.69% | 4.32x | −0.0542 | −0.59 | −0.416% |
| momentum only (ret1/5/21/63) | 11.60% | 5.17x | 13.28% | 5.92x | +0.2601 | 2.92 | −0.212% |
| no vol20 | 11.04% | 4.92x | 13.16% | 5.87x | +0.2034 | 2.46 | −0.249% |

Every variant predicts losers **better than it predicts winners**. Return distribution of
the predicted basket: mean +0.0846%, **median −0.5002%**, P(up)=0.443, P(>+5%)=0.120,
P(<−5%)=0.108, skew +0.58. Rest of universe: median −0.0906%, P(up)=0.469.

So the model is a **volatility/lottery detector**. It correctly identifies the names with a
wide conditional distribution tomorrow. Both tails widen together. The positive mean is a
thin right-skew residue sitting on top of a basket that loses money on 55.7% of its
positions — and that residue is smaller than the toll.

## 4. Net returns of the predicted top-50 basket (holdout, 343 days, equal weight)

| cost model | net %/day | t | annualised | max DD | market-neutral net | t |
|---|---:|---:|---:|---:|---:|---:|
| intraday MIS 0.107% | **−0.0224** | −0.26 | −5.5% | −34.3% | −0.0253% | −0.52 |
| delivery CNC 0.24% | **−0.1554** | −1.81 | −32.4% | −55.5% | −0.1583% | −3.27 |

Universe mean return over the same days: +0.0029%/day, so market-neutralising changes
almost nothing — this was never a beta story. It is simply a −0.02% to −0.16% per day
strategy. Gross is +0.0846%/day at **t=0.98 — not significant even before costs.**

## 5. Liquidity segmentation — the forecastability inverts, then dies

Winners concentrate in illiquid names: winner share is **2.96%** in the low-turnover
tercile, 2.55% mid, **2.08%** high.

| turnover tercile | base | top hit | lift | t | gross %/day | t | net MIS %/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| low (median ~25) | 2.57% | 13.93% | **5.41x** | 22.16 | +0.2581 | 2.47 | +0.1511 |
| mid (median ~444) | 2.21% | 9.36% | 4.24x | 18.36 | +0.0093 | 0.10 | −0.0977 |
| high (median ~5505) | 1.94% | 8.37% | 4.31x | 14.25 | −0.0649 | −0.76 | −0.1879 |

**Small-caps are more forecastable than large-caps**, and they are the only place with a
positive net number. That lead does not survive contact:

- It **decays within the holdout**: first half +0.3207% (t=2.08), second half +0.1957%
  (t=1.38).
- It is one of ~20 variants tested. Bonferroni needs |t|>=3.2 here; it gives 2.47.
- Fatally, it is **entirely an artifact of the untradeable bottom decile.** Applying any
  turnover floor at all destroys it:

| min turnover | eligible names/day | gross %/day | t | net MIS %/day | t (net, mkt-neutral) |
|---:|---:|---:|---:|---:|---:|
| 0 (no floor) | 2230 | +0.0846 | 0.98 | −0.0224 | −0.52 |
| **10** | 2031 | **−0.0244** | −0.28 | −0.1314 | **−2.75** |
| 50 | 1702 | −0.0623 | −0.72 | −0.1693 | −3.50 |
| 100 | 1531 | −0.0596 | −0.69 | −0.1666 | −3.46 |
| 300 | 1236 | −0.0384 | −0.42 | −0.1454 | −2.88 |
| 1000 | 856 | −0.0275 | −0.30 | −0.1345 | −2.50 |
| 3000 | 524 | −0.0719 | −0.83 | −0.1789 | −3.64 |

The entire positive gross return of the strategy lives in the ~200 names/day below the
lowest floor tested — the bottom decile, median turnover 6 units. Remove them and the
strategy is negative at every single liquidity threshold, and significantly negative net of
costs at all of them.

**Shorting the basket does not work either:** −0.1916%/day net MIS, t=−2.23. The median
position falls 0.50% but the right tail (12% of positions gain >5%) is fat enough to bleed
a short book. Both sides pay the toll and neither side owns the distribution.

---

## What this closes

1. **The classification problem is solved and it does not matter.** 4.87x lift, AUC 0.695,
   t=32.5 clustered, out-of-sample, survivorship-free. Anyone proposing "predict the daily
   gainers" as a research direction can stop — it has been done, it works, and it pays
   −0.02%/day.
2. **The hindsight ceiling is unreachable** because the features that identify winners are
   variance features, not mean features. `vol20` at +0.605 sd is by far the strongest
   discriminator, and volatility is direction-agnostic by construction. You cannot get a
   first moment out of a second-moment signal.
3. **Anything future work finds in the low-turnover tercile should be assumed dead until
   proven fillable.** The one positive net number in this entire study (+0.1511%/day) came
   from names with ~25 units of daily turnover and evaporated at the first floor.
4. Consistent with the already-ruled-out ridge/GBM result and the cross-sectional ranking
   failure. Adds the specific reason: the price-feature panel carries information about
   *dispersion*, and every attempt to monetise it is a bet on the mean.

**Do not redo:** daily-gainer classification from prior-close price/volume features, in any
model class. The ceiling is 4.87x lift and it is worth less than zero after costs.

---

Scripts: `quant/_precursors_build.py`, `quant/_precursors_analyse.py`,
`quant/_precursors_diag.py`, `quant/_precursors_final.py`.
Stats table: `docs/research/overnight/_precursor_stats.csv`.
Panel: `docs/research/overnight/winners_panel_own.parquet` (1.94M rows).
