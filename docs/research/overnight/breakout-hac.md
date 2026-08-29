# BREAKOUT — Verdict: Dead. Not an Edge.

*The t-statistic was overlap inflation. Corrected, the best number in the study is **t = 1.48** against a Bonferroni bar of 3.0–3.3 — it misses by more than half. And the effect does not exist in the first half of the holdout (t = 0.08 at h=5), only the second. It is a nine-month regime, not an edge.*

**Nothing in the winner-anatomy lane survives. Closed.**

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — quant research |
| **Version** | `v1.0.0` |
| **Status** | Complete — negative result, lane closed |
| **Created** | 2026-08-28 |
| **Updated** | 2026-08-28 |
| **Parent** | `winner-anatomy.md` §6, §7 items 1–3 |
| **Script** | `quant/_winner_anatomy2.py` |
| **Verdict** | **BREAKOUT is not tradeable. Max corrected \|t\| = 1.48.** |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## 1. Provenance — what had to be rebuilt

Two things the brief assumed exist did **not** survive the disk failure:

| Asset | Status | Action |
|:--|:--|:--|
| `quant/_winner_anatomy2.py` | **Absent.** Never written — the disk died first. | Written from scratch this run. |
| `docs/research/overnight/winners_panel_own.parquet` | **Absent.** Deleted with the volume. | Rebuilt in memory from `sf_ret` + `sf_turn` using the verbatim logic of `_precursors_build.py`. |

Because the panel was rebuilt rather than reloaded, **§2 is a reproduction check before any new number is reported.** It matches `winner-anatomy.md` to the last printed digit:

::: {.metrics-table}

| Cell | Reported in `winner-anatomy.md` | Reproduced here |
|:--|--:|--:|
| BREAKOUT holdout, n | 36,760 | 36,760 |
| BREAKOUT holdout h=5 | +0.325% (t = 2.66) | +0.325% (t = 2.66) |
| BREAKOUT holdout h=10 | +0.584% (t = 3.39) | +0.584% (t = 3.39) |
| BREAKOUT holdout h=21 | +0.867% (t = 3.39) | +0.867% (t = 3.39) |
| BREAKOUT train h=5 / h=21 | +0.015% (0.35) / −0.023% (−0.31) | +0.015% (0.35) / −0.023% (−0.31) |
| REVERSAL holdout h=1 | −0.152% (t = −3.10) | −0.152% (t = −3.10) |

:::

The rebuild is exact. Everything below rests on the same panel that produced the parent report.

---

## 2. Test 1 — Newey-West correction

**Bandwidth choice.** The daily series being tested is the cross-sectional mean market-neutral return of BREAKOUT names on each session. For an h-day holding period these observations overlap by h−1 days, which induces an **MA(h−1)** structure by construction. The correct Bartlett bandwidth is therefore **L = h** (or h−1); this is a *known* dependence length, not an unknown one to be estimated.

The Newey-West (1994) automatic rule-of-thumb, `L = floor(4·(n/100)^(2/9))`, returns **L = 5** for n ≈ 340 regardless of horizon. **That is the wrong tool here** — it is designed for unknown persistence and is blind to the fact that the h=21 series is mechanically autocorrelated out to lag 20. It is reported below only to show it *understates* the correction at long horizons. **The headline is L = h.**

::: {.changes-table}

| Horizon | Mean (MN) | Naive t | **NW t (L = h)** | NW t (L = h−1) | NW t (auto, L=5) | Inflation |
|:--|--:|--:|--:|--:|--:|--:|
| **h = 1** *(control)* | +0.080% | +1.44 | **+1.48** | +1.44 | +1.64 | **0.97×** |
| h = 5 | +0.325% | +2.66 | **+1.47** | +1.51 | +1.47 | 1.81× |
| h = 10 | +0.584% | +3.39 | **+1.40** | +1.42 | +1.62 | 2.41× |
| h = 21 | +0.867% | +3.39 | **+0.99** | +0.99 | +1.53 | **3.44×** |

:::

**The h=1 control passes.** h=1 windows do not overlap, so its t should barely move — it goes 1.44 → 1.48 (0.97×, i.e. the correction is essentially nil and marginally *raises* it, which is ordinary sampling noise in the lag-1 autocovariance). At L = 0 it returns exactly 1.44, the naive value, as it must. The implementation is behaving.

The prior agent's paragraph-argument estimated the corrected range at **1.2–1.7**. The computed answer is **0.99–1.48**. The argument was right and slightly generous.

### 2b. Kernel-free cross-check

To confirm this is not an artefact of the Bartlett kernel or bandwidth, the same series was split into **disjoint** subsamples — every h-th session, so no two windows overlap at all — and a plain iid t computed on each.

::: {.metrics-table}

| Horizon | Disjoint subsamples | Mean t across them | Range | Fraction with \|t\| > 3 |
|:--|--:|--:|--:|--:|
| h = 5 | 5 (n≈68 each) | +1.21 | [+0.86, +1.70] | **0 / 5** |
| h = 10 | 10 (n≈34 each) | +1.14 | [+0.55, +1.97] | **0 / 10** |
| h = 21 | 21 (n≈16 each) | +0.80 | [+0.01, +1.87] | **0 / 21** |

:::

Two independent methods agree: **1.2 / 1.1 / 0.8 (non-overlapping) versus 1.47 / 1.40 / 0.99 (Newey-West).** Not one of the 36 disjoint subsamples reaches |t| = 3. The naive t was overlap inflation, full stop.

The intuition, stated plainly: 323 overlapping 21-day windows contain roughly **323 / 21 ≈ 15 independent observations**, not 323. The naive t divided by √323 when it was entitled to √15. √(323/15) ≈ 4.6 — the same order as the 3.44× inflation actually measured.

### 2c. The correction applied to the rest of the lane

::: {.metrics-table}

| Cell | Naive t | NW t (L = h) | Note |
|:--|--:|--:|:--|
| BREAKOUT train h=5 | +0.35 | +0.21 | zero stays zero |
| BREAKOUT train h=21 | −0.31 | −0.11 | zero stays zero |
| BREAKOUT holdout **raw** h=21 | +5.79 | +1.76 | 3.28× — the raw number was the most inflated in the study |
| REVERSAL holdout h=1 | −3.10 | **−3.12** | no overlap, unmoved — survives the bar |
| REVERSAL holdout h=5 | −3.50 | −2.15 | |
| REVERSAL holdout h=21 | −1.92 | −0.78 | |

:::

Worth recording: **REVERSAL at h=1 is the only cell in the entire winner-anatomy lane that clears the multiplicity bar after correction** (|t| = 3.12 vs bar 3.0–3.3) — and it is a *negative* mean. The parent report's reading of REVERSAL as a paid-for lottery premium is the one finding the correction leaves standing, and it remains untradeable for the short-side reasons in `pre-open.md` §7.

---

## 3. Test 1 verdict against the multiplicity bar

The lane pre-declared ~30–40 tests, giving a Bonferroni threshold of **|t| ≥ 3.0–3.3**.

::: {.metrics-table}

| | Value |
|:--|--:|
| Best BREAKOUT t, naive | +3.39 (h=10, h=21) |
| Best BREAKOUT t, **overlap-corrected** | **+1.48** (h=1 — the horizon with no overlap and no economic claim) |
| Best BREAKOUT t at h ≥ 5, corrected | **+1.47** (h=5) |
| Bonferroni bar | 3.0 – 3.3 |
| Even the *uncorrected single-test* bar (1.96) | not cleared at h ≥ 5 |

:::

**BREAKOUT fails by a factor of more than two.** Pre-correction it sat *on* the multiplicity line; post-correction it does not clear the bar a single isolated test would demand. There is no reading of the multiplicity accounting under which this number is evidence of anything.

---

## 4. Test 2 — the decisive question: split-half and momentum

The correction alone leaves open whether a real, weak effect exists that the correction merely made insignificant. The persistence test answers that, and the answer is worse than insignificance.

### 4a. Holdout split in half by date

Holdout spans 2025-01-20 → 2026-06-12 (343 sessions). Midpoint **2025-09-29**.

::: {.changes-table}

| Horizon | H1 mean (Jan–Sep 2025) | H1 naive t | H1 NW t | H2 mean (Oct 2025–Jun 2026) | H2 naive t | H2 NW t |
|:--|--:|--:|--:|--:|--:|--:|
| h = 1 | +0.027% | +0.37 | +0.35 | +0.132% | +1.57 | +1.76 |
| h = 5 | **+0.014%** | **+0.08** | +0.05 | +0.642% | +3.71 | +1.96 |
| h = 10 | +0.180% | +0.88 | +0.35 | +1.007% | +3.63 | +1.60 |
| h = 21 | **+0.132%** | **+0.40** | +0.12 | +1.693% | +4.44 | +1.33 |

:::

**The first half of the holdout is indistinguishable from the training period.** At h=5 it is +0.014% (t = 0.08) — against +0.015% (t = 0.35) in training. At h=21, +0.132% (t = 0.40).

So the honest picture is not "absent in train, present in holdout." It is:

> **Absent across 637 training sessions. Absent across the first 171 holdout sessions. Present only in the last 172 sessions.**

That is 808 sessions of nothing followed by nine months of something. A real effect shows in both halves. This concentrates entirely in one — the textbook signature of a regime.

### 4b. Year by year (full sample, BREAKOUT market-neutral)

::: {.changes-table}

| Year | n | h=5 | h=10 | h=21 |
|:--|--:|--:|--:|--:|
| 2022 | 12,720 | −0.026% (NW −0.16) | +0.170% (NW +0.82) | −0.019% (NW −0.07) |
| 2023 | 49,945 | +0.037% (NW +0.40) | +0.039% (NW +0.22) | +0.012% (NW +0.03) |
| 2024 | 59,280 | +0.078% (NW +0.64) | +0.055% (NW +0.28) | +0.057% (NW +0.16) |
| 2025 | 23,947 | +0.154% (NW +0.70) | +0.386% (NW +0.94) | +0.960% (NW +0.98) |
| 2026 | 13,719 | +0.544% (NW +1.06) | +0.690% (NW +0.71) | +0.146% (NW +0.11) |

:::

Three flat years, then two warm ones — and **not one of the fifteen cells reaches NW |t| = 1.1.** The 2025 h=21 cell that reads +0.960% at naive t = 3.32 corrects to **0.98**.

### 4c. Regressing out `mom_12_1`

Daily cross-sectional Fama-MacBeth over the full holdout cross-section (488,828 rows), BREAKOUT as a dummy. `corr(BREAKOUT, mom_12_1) = +0.234`.

::: {.changes-table}

| Horizon | Specification | Coefficient | Naive t | **NW t (L = h)** |
|:--|:--|--:|--:|--:|
| h = 5 | BO dummy alone | +0.370% | +2.87 | +1.58 |
| h = 5 | BO \| `mom_12_1` | +0.309% | +2.58 | **+1.46** |
| h = 5 | BO \| mom, vol20, turn20 | +0.319% | +3.14 | +1.76 |
| h = 10 | BO dummy alone | +0.669% | +3.67 | +1.51 |
| h = 10 | BO \| `mom_12_1` | +0.530% | +3.20 | **+1.37** |
| h = 10 | BO \| mom, vol20, turn20 | +0.531% | +3.72 | +1.63 |
| h = 21 | BO dummy alone | +1.013% | +3.76 | +1.09 |
| h = 21 | BO \| `mom_12_1` | +0.693% | +2.83 | **+0.87** |
| h = 21 | BO \| mom, vol20, turn20 | +0.709% | +3.41 | +1.05 |

:::

Momentum absorbs **17% of the h=5 coefficient, 21% at h=10, 32% at h=21** — a real but partial overlap. So the parent report's claim that BREAKOUT *is* `mom_12_1` is too strong: they are correlated (+0.23), not identical, and a residual remains.

**But the residual is not significant** — NW t of 1.46 / 1.37 / 0.87, worse at every horizon than the uncontrolled figure and nowhere near 3.0. That is the finding, and it stands.

> **STRUCK 2026-08-29 (see `hac-audit.md`).** This paragraph originally continued: "the momentum
> factor itself behaves identically in the same window: `mom_12_1` slope at h=21 reads naive
> t = +5.72 correcting to NW +1.49, i.e. it is *also* a holdout-only regime number, consistent
> with the factor's known on-book range of t = 0.91–1.82. Both are being lifted by the same nine
> months."
>
> Two errors. It compared a **daily Fama-MacBeth regression slope** to a **net-of-cost portfolio
> t-statistic** as though they were the same quantity — they are not, and the "consistent with"
> is meaningless. And the 1.49 is an artifact of the 323-session holdout window: extended to the
> full sample the same slope reads **naive 10.97 → NW 2.92**, with 21 of 21 disjoint subsamples
> clearing 1.96. The momentum slope survives HAC comfortably.
>
> BREAKOUT's verdict is unaffected — the residual after controlling for momentum is still
> NW t ≤ 1.46.

**Answer to the decisive question: nothing survives.** What is left after removing momentum is a statistically absent quantity that exists only in the final third of the sample.

---

## 5. Test 3 — stop-loss truncated payoff

Does truncating the left tail monetise the right one? Exit at the close of the first day the cumulative position is ≤ −s; otherwise hold to h. Holdout, raw gross returns.

::: {.changes-table}

| Type | h=21 no stop | stop −5% | stop −10% | stop −15% |
|:--|--:|--:|--:|--:|
| BREAKOUT | +0.895% | +0.766% (−0.130) | +0.730% (−0.165) | +0.803% (−0.092) |
| REVERSAL | +4.055% | **+0.968% (−3.087)** | +2.290% (−1.765) | +3.230% (−0.825) |
| CONTINUATION | −0.267% | −1.041% (−0.774) | −0.848% (−0.581) | −0.445% (−0.178) |
| ALL | +0.465% | −0.059% (−0.523) | +0.123% (−0.342) | +0.305% (−0.159) |

:::

**Answer: no — the opposite, uniformly.** Every stop level, at every horizon (h=10 shown in the script output), for every type, **lowers** the mean. There is not one favourable cell in the entire grid.

The mechanism is visible in the skew column: stopping *does* what it advertises — BREAKOUT h=10 skew goes −0.07 → +0.56 at a −5% stop, REVERSAL +0.64 → +2.01 at h=21. **The payoff shape becomes markedly more lottery-like and the expectation falls.** You are buying cosmetic positive skew with real money.

The severity scales with how much the name moves: REVERSAL, the highest-volatility type, loses **3.09 percentage points of mean return** to a −5% stop over 21 days, because 60.8% of positions get stopped out of a distribution whose recovery is exactly what pays. This is the daily-close approximation of the classic result that stops on mean-reverting, high-volatility names convert drawdown into realised loss.

*Caveat: exits are evaluated at daily closes (the panel is EOD), so a true intraday stop would trigger more often and, on this evidence, cost more.*

---

## 6. Test 4 — BREAKOUT by turnover bucket

`turn20` terciles within holdout BREAKOUT rows (≈12,250 each). Boundaries: **Rs 0.9 → 16 → 83 → 3,741 crore/day** average.

::: {.changes-table}

| Bucket | h=5 mean | h=5 naive t | h=5 NW t | h=5 NW \| mom | h=21 NW t | h=21 NW \| mom |
|:--|--:|--:|--:|--:|--:|--:|
| LOW (0.9–16 cr) | +0.379% | +2.70 | +1.47 | +1.33 | +1.16 | +0.93 |
| MID (16–83 cr) | +0.437% | +3.40 | **+1.94** | +1.82 | +0.80 | +0.51 |
| HIGH (83–3,741 cr) | +0.104% | +0.77 | +0.43 | +0.16 | +0.77 | +0.49 |

:::

The effect is **monotonically absent in liquid names.** HIGH turnover — the only bucket where a real book could be run without impact — is +0.104% at NW t = 0.43, and +0.032% (t = 0.16) once momentum is controlled. Whatever is happening lives in the illiquid two-thirds, where the 0.24% delivery toll plus impact would consume the +0.4% gross several times over.

This is the standard shape of a non-edge: it hides where you cannot trade it and vanishes where you can. Best cell in the whole table, MID at h=5 with momentum controlled, is **NW t = 1.82** — still under the single-test bar, let alone Bonferroni.

*Note on the `turn20` feature: it is `log10` of the 20-day mean turnover with non-trading days filled as zero (verbatim from `_precursors_build.py`), whereas the tradeable filter uses the 20-day **median** ≥ Rs 1 crore. That is why the LOW bucket floor reads below Rs 1 crore. The bucketing is monotone in liquidity regardless; the conclusion does not turn on the boundary.*

---

## 7. Verdict

::: {.metrics-table}

| Objection | Status |
|:--|:--|
| Overlap inflation | **Computed.** 1.8× / 2.4× / 3.4× at h=5/10/21. Best corrected t = 1.48. Confirmed kernel-free by 36 disjoint subsamples, none above \|t\| = 2. |
| Multiplicity | **Fails.** 1.47 against a 3.0–3.3 bar. Does not clear even 1.96. |
| Persistence | **Fails worse than reported.** Absent in train *and* in the first half of the holdout (h=5 t = 0.08). Confined to the last 172 sessions. |
| Already-owned factor | **Partly.** `mom_12_1` absorbs 17–32%; the residual is not significant (NW t ≤ 1.46) and `mom_12_1` itself corrects to NW 1.49 in the same window. |
| Tradeable where liquid | **No.** HIGH-turnover tercile: NW t = 0.16 with momentum controlled. |

:::

**BREAKOUT is not an edge and never was one.** The parent report reached the right verdict from persistence alone; this run replaces the one argued paragraph with a number and finds the argument was, if anything, too kind. The last object in the winner-anatomy lane that could have been mistaken for a live trading edge has been shot with a computation.

**Lane status: closed.** All three outstanding follow-ups are complete. No item here justifies a shadow lane, a paper-trade variant, or further investment.

**One thing worth carrying forward** (not to trading, to method): the h=21 **raw** BREAKOUT number was naive t = **+5.79**, correcting to **+1.76**. Any overlapping-window t-statistic produced anywhere in this codebase without a HAC correction should be assumed inflated by 2–3.5× at multi-week horizons until shown otherwise.

---

## 8. Reproduction

```bash
/Users/soumyaswain/anaconda3/bin/python3 quant/_winner_anatomy2.py
```

Rebuilds the panel in memory from `quant/data/sf_ret.parquet` + `sf_turn.parquet`, writes no intermediate files, prints all five tests including the T0 reproduction check. Runtime ≈ 3 minutes. `sf_turn` is in **Rs lakh**; `sf_ret` is **winsorised at ±50%** and is not used for extreme-value work here.
