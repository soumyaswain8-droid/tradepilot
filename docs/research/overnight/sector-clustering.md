# Sector / Theme Clustering — Do Winners Clump, and Does the Theme Persist?

**VERDICT: Clumping is real and huge. Persistence is not there.**
Big daily winners arrive in tight sector clumps — the leading cluster holds **27.5%** of the top-50 winners against a **8.3%** random baseline (HHI 0.1845 vs null 0.1480, t=40.0, p=2e-208, n=982 days). But **today's leading cluster does not lead tomorrow**: 0 of 16 pre-registered variants clear Bonferroni |t| >= 2.96 on train, and after costs every variant is flat-to-negative in both train and holdout.
**Not tradeable. Do not build on this.** Clumping without persistence is a description of how the market moves, not an edge — you can see the theme only after it has already paid.

---

## 1. What was tested

The lane's premise: every other precursor lane died because precursors predict **volatility, not sign**. Sector flow is a genuinely different mechanism — directional and slow-moving. If institutional money rotates into a theme over days, then (a) winners should cluster by theme, and (b) the theme that led today should still lead tomorrow.

Both halves were tested separately, because only the pair is tradeable.

| | Setting |
|:--|:--|
| Data | `quant/data/sf_ret.parquet`, `sf_turn.parquet` — 3046 names, 1232 sessions, 2021-06-17 to 2026-06-12 |
| Sector map | None labelled exists in the repo. Data-driven: rolling KMeans (K=12) on top-20 PCA components of a trailing 250-session return-correlation matrix |
| Refit | Every 125 sessions; labels applied **forward only** (fit on `[s-250, s)`, applied to `[s, s+125)`) |
| Split | Train 2021-06 to 2024-06 (750 sessions) / Holdout 2024-07 to 2026-06 (482 sessions) |
| Variants | 16 pre-registered: signal lookback {1d, 5d} x hold {1, 3, 5, 10d} x {all names, top-turnover-decile} |
| Threshold | Bonferroni for 16 tests -> **\|t\| >= 2.96** |
| Neutralisation | Every leg reported as excess over the same-day universe mean return |
| Costs | 0.107% round trip intraday (hold=1), 0.24% round trip delivery (hold>1), plus flat Rs 18.80 DP fee per sell per scrip |

### Universe guard (the trap that nearly ate this run)

The previous run screened `turnover >= 1e7` assuming rupees. **`sf_turn.parquet` is denominated in Rs lakh** (p10 = 8.8, median = 327, p90 = 9298). Every symbol failed the screen, the universe collapsed to zero, and every statistic returned NaN.

The failure was loud only because it was total. A threshold slightly too high — say 5000 lakh instead of 1e7 — would have left a few dozen mega-caps and produced entirely plausible-looking numbers off a distorted universe. So the universe size is now asserted and **printed before any statistic is computed**:

```
UNIVERSE: median=1123  p5=810 p25=982 p75=1165 p95=1224  min=722 max=1283
UNIVERSE: days with <300 names = 0 / 982
universe guard PASSED
```

Threshold used: `TURN_MIN = 100.0` lakh = **Rs 1 crore/day** median trailing-20-session turnover, lagged one day. Assertion: median universe >= 200 names, and fewer than 5% of days below 200.

Second fix from the same run: forward returns were accumulated with `np.nansum`, which silently scores a missing session as a zero return — quietly filling holes with "the stock didn't move." Forward windows now require **every** session in the hold window to be present; incomplete names are dropped, not zero-filled.

---

## 2. Result A — Clumping: strongly confirmed

For each session, take the 50 largest returns in the universe, and measure the Herfindahl concentration of their cluster labels. The null is 200 Monte Carlo draws of 50 names from that same day's universe, so the null automatically absorbs unequal cluster sizes and same-day universe composition.

| Metric | Actual | Random null | Diff |
|:--|--:|--:|--:|
| HHI of top-50 winners' clusters | **0.1845** | 0.1480 | +0.0365 |
| Largest cluster's share of top 50 | **27.5%** (median 26.0%) | 8.3% | +19.2pp |
| Days where actual > null | **93.3%** | 50% | — |

t = 40.0, p = 2.07e-208, n = 982 days.

This is one of the strongest effects measured in any lane. On a typical day roughly **13 or 14 of the 50 biggest winners belong to a single cluster.** Winners are emphatically not scattered.

It is also stable — and if anything strengthening:

| Regime | HHI diff | t | Top-cluster share | n |
|:--|--:|--:|--:|--:|
| 2021-2023 | +0.0311 | 23.5 | 26.4% | 378 |
| 2024-2026 | +0.0399 | 33.0 | 28.1% | 604 |

No regime dependence to report here. The clumping is a permanent structural feature.

---

## 3. Result B — Persistence: absent

Rank clusters by mean return over the signal lookback, go long the leading cluster and short the lagging cluster, hold forward, report excess over the universe mean.

**Gross, train (2021-06 to 2024-06):**

| sig | hold | liq | gross %/obs | t |
|--:|--:|:--|--:|--:|
| 1 | 1 | all | 0.1794 | 2.24 |
| 1 | 3 | all | 0.2937 | 2.16 |
| 1 | 5 | all | 0.4858 | 2.44 |
| 1 | 10 | all | 0.6097 | **2.86** |
| 1 | 10 | liquid | 0.6999 | 2.52 |
| 5 | 1 | all | 0.0734 | 0.94 |
| 5 | 3 | all | -0.0444 | -0.24 |
| 5 | 5 | all | -0.0960 | -0.34 |
| 5 | 10 | all | -0.0510 | -0.11 |

**0 of 16 variants clear |t| >= 2.96, even gross.** The best is sig=1 / hold=10 at t = 2.86 — under the bar, and it is the single most-overlapping variant in the set, where the Newey-West correction is doing the most work and is least trustworthy.

Three things kill it beyond the raw threshold:

1. **The sign flips between lookbacks.** A 1-day signal is weakly positive; a 5-day signal is weakly *negative* on train. If sector flow were a real slow-moving mechanism, a longer lookback should measure it better, not invert it.
2. **The sign flips between train and holdout.** In the long-only book, sig=5 variants are negative across the board on train (t down to -3.63) and positive across the board on holdout (t up to +1.59). A mechanism does not change sign at an arbitrary 2024-07-01 boundary. Noise does.
3. **Nothing replicates.** The best-train pick (sig=1, hold=10, liquid decile) delivers holdout net 0.064%/obs at **t = 0.14**.

**Net of costs** — every variant, both periods:

| Period | Best net variant | net %/obs | t |
|:--|:--|--:|--:|
| Train | sig1 hold10 liquid | +0.1447 | 0.52 |
| Holdout | sig5 hold10 liquid | +0.7365 | 1.06 |

One variant does clear Bonferroni on net t in train — sig=5, hold=3, all names, at **t = -3.27**. That is a significant *loss*, not a signal: gross was already -0.04% and costs took it to -0.60%. Reported for completeness so it is not misread as a hit.

Cost accounting: each daily observation is a full independent round trip on both legs, because the strategy opens a fresh hold-h-day position every session (h overlapping books, each rebalanced every h days). That is 0.214% per observation at hold=1 and 0.555% at hold>1, including the Rs 18.80 DP fee assumed against Rs 50,000 per name (3.76 bps/leg). Costs are not being double-counted.

The arithmetic is the whole story at hold=1: gross is **0.18% (train) / 0.21% (holdout)** against a **0.214%** cost floor. The effect and the cost line are the same number. There is nothing left over.

### Regime check

| Regime | Variant | gross | t | net | t |
|:--|:--|--:|--:|--:|--:|
| 2021-2023 | sig1 hold1 all | 0.1774 | 2.11 | -0.0366 | -0.44 |
| 2024-2026 | sig1 hold1 all | 0.2080 | 2.43 | -0.0060 | -0.07 |
| 2021-2023 | sig5 hold5 all | -0.2068 | -0.66 | -0.7620 | -2.44 |
| 2024-2026 | sig5 hold5 all | 0.3192 | 1.01 | -0.2360 | -0.75 |

There is no era in which this worked. This is **not** a memory that died in 2024 — the weak gross drift is, if anything, marginally larger in 2024-2026. It simply never cleared costs in either regime. That is a cleaner negative than a decayed edge: nothing to wait for, nothing to revive.

---

## 4. Interpretation

The two results have to be read together, and they say something specific.

Clumping is enormous and persistence is nil. That combination means theme membership is **contemporaneous information, not predictive information**. On the day a theme moves, its names move together — which is why the HHI test screams. But the identity of tomorrow's theme is not contained in today's ranking. The rotation is either faster than a day, or genuinely unpredictable at the cluster level, or already priced by the close of the day it becomes visible.

This is worth stating plainly because the premise was reasonable and the first result looks spectacular. A t of 40 on the clumping test could easily be reported as "sector rotation confirmed" and taken as a green light. It is not one. **The 27.5% concentration figure is only a measurement of same-day co-movement.** Acting on it requires knowing the cluster in advance, and the persistence test is exactly the test of whether you can — the answer is no.

So sector flow joins the other lanes, but for a different reason. The precursor lanes died because they predicted volatility rather than sign. This one was genuinely directional, as hoped — and it died on **timing**: the direction is real but only observable after it has been paid out.

### What this does not rule out

- **Intraday persistence.** Everything here is close-to-close daily. If a theme leads in the first hour and continues through the session, that is a different test with different data (`panel_5min.pkl`) and is untouched by this result.
- **Labelled sectors.** KMeans on return correlation recovers statistical co-movement blocks, which is arguably the right object here, but it is not the same as GICS/NSE sector labels. A labelled map could carve differently. Given gross returns sit at the cost line rather than above it, a better partition would have to roughly triple the effect to matter — this is not a near-miss worth re-cutting.
- **Longer horizons.** The hold=10 variants were the least-bad and the trend across hold length is mildly upward on gross. A monthly-horizon test is a separate lane, not an extension of this one, and it would need its own pre-registration.

---

## 5. Reproduction

Script: `scratchpad/sector.py` (transient). Runtime ~15s warm, ~90s cold including clustering. Only intermediate artifact is a 7.5 MB `labels.npy` cluster-label cache, deleted after the run. No large files written.

Fixes applied to the blocked run:
1. `TURN_MIN = 1e7` -> `100.0` (turnover is Rs lakh, not rupees)
2. Forward returns require the complete hold window; no `nansum` zero-fill
3. Universe size asserted and printed before any statistic

---

*Author: Soumya Swain <soumya@suryaai.co.in> · 2026-08-28 · lane status: CLOSED, negative*
