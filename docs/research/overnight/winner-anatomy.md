# Winner Anatomy — Verdict: No Type Has Tradeable Asymmetry

*Every setup's up/down ratio sits at the unconditional baseline. Nothing bends it.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — quant research |
| **Version** | `v1.0.0` |
| **Status** | Complete — negative result |
| **Created** | 2026-08-28 |
| **Updated** | 2026-08-28 |
| **Panel** | 1.94M stock-days, 980 sessions |
| **Verdict** | **NO TRADEABLE ASYMMETRY** in any winner type |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

> **Transcription note.** The analysis behind this report ran to completion overnight on 2026-07-27/28. Only the file write failed, because the disk filled. **These findings are transcribed verbatim from that completed run — nothing here has been re-computed.** Three follow-ups did not finish before the disk died; they are listed in §7 and the script that runs them is preserved.

---

## 1. Verdict

**No winner type has tradeable asymmetry.**

The question was whether stocks that go on to have big up-days can be sorted in advance into types — breakouts, reversals, continuations — with one type showing a payoff skewed enough to trade. The answer is no, and the reason is cleaner than a marginal-significance argument: **every type's ratio of big-up days to big-down days lands on the unconditional baseline of 1.61.** No setup bends the distribution.

---

## 2. Method

::: {.metrics-table}

| Parameter | Setting |
|:--|:--|
| Panel | 1.94M stock-days, 980 sessions |
| Tradeable filter | 20d median turnover >= Rs 1 crore |
| After filter | 772k train / 489k holdout |
| Split | 2025-01-20 (pre-fixed) |
| Type assignment | **prior-close data only** |

:::

Types are assigned from information available before the day begins, so every result below is implementable in principle.

---

## 3. Next-day holdout results (market-neutral)

::: {.changes-table}

| Type | Definition | n | P(win) lift | P(>+5%) | P(<-5%) | Ratio | Skew | Mean MN | t |
|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| BREAKOUT | pos52 >= .95 | 36,760 | 1.46x | 3.76% | 2.36% | 1.59 | -1.29 | +0.080% | 1.44 |
| REVERSAL | pos52 <= .10, ret21 <= -15% | 22,109 | 1.37x | 7.89% | 5.24% | 1.51 | +0.59 | -0.152% | **-3.10** |
| CONTINUATION | ret21 >= +20% | 19,851 | 1.97x | 6.14% | 4.27% | 1.44 | -0.30 | -0.052% | -0.79 |
| FROM-NOWHERE | — | 89,552 | 0.43x | 1.22% | 0.62% | 1.97 | -3.08 | -0.025% | -0.86 |
| **ALL (baseline)** | — | 488,828 | — | — | — | **1.61** | -0.40 | — | — |

:::

---

## 4. The kill

**Every type's up/down ratio sits at the unconditional 1.61.** BREAKOUT 1.59, REVERSAL 1.51, CONTINUATION 1.44, FROM-NOWHERE 1.97 — scattered around the baseline with no type meaningfully above it, and the highest (FROM-NOWHERE) being the one with the most negative skew (-3.08) and no economic story.

The right-tail fatness we set out to harvest is **a property of Indian equity returns generally — right-skewed tails around a negative median — not of any identifiable structure.** You cannot select into it. The tail is there for everyone and belongs to no setup.

---

## 5. REVERSAL — the instructive case

REVERSAL is the only type with **genuine positive skew: +0.59 to +0.82, at every horizon, in both periods.** It has 1.5x more big-up days than big-down days. It is also the **only result significant in both periods with the same sign** — and that sign is *negative*.

::: {.metrics-table}

| Horizon | Train | Holdout |
|:--|--:|--:|
| h = 1 | -0.208% (t = -4.18) | -0.152% (t = -3.10) |
| h = 5 | -0.632% (t = -5.04) | -0.328% (t = -3.50) |
| h = 10 | -0.721% | -0.433% |

:::

**A real fat right tail that reliably loses money.** This is the clearest thing the study produced: REVERSAL is a lottery-preference risk premium, and the buyer pays it. The excitement of the occasional large winner is exactly what makes the average negative. The only tradeable expression of this finding is the short side, which is unavailable in these names for the same reasons set out in `pre-open.md` §7.

---

## 6. BREAKOUT — the only positive, and it fails persistence

BREAKOUT is the sole type with a positive mean, and it looks strong in the holdout:

::: {.metrics-table}

| Horizon | Holdout (2025-26) | Train (637 days) |
|:--|--:|--:|
| h = 5 | +0.325% (t = 2.66) | +0.015% (t = 0.35) |
| h = 10 | +0.584% (t = 3.39) | +0.023% (t = 0.44) |
| h = 21 | +0.867% (t = 3.39) | -0.023% (t = -0.31) |

:::

**Zero signal in training. It appears only in 2025-26.** That is the signature of a regime, not an edge.

Three further objections, any one of which is sufficient:

1. **It is a factor we already own.** BREAKOUT is plainly the `mom_12_1` momentum factor, already on the books at t = 0.91-1.82. It is not a new discovery.
2. **The t-statistic is inflated by overlap.** The t = 3.39 figures come from **21-day overlapping windows**, clustered only cross-sectionally — serial overlap is not corrected. Newey-West at lag 21 would cut it to roughly **1.2-1.7**. *This is argued, not computed — the disk died before it ran.*
3. **Multiplicity.** 5 types x 4 horizons x 2 periods = 40 cells, or ~30-40 counting classification-threshold choices. Bonferroni bar is **\|t\| >= 3.0-3.3.** BREAKOUT sits on the line pre-correction and under it post-correction — and fails persistence either way.

**CONTINUATION flips sign across the split** — h = 10 goes from train +0.373% (t = 3.49) to holdout -0.751% (t = -4.70). Textbook overfit, and a useful reminder of what the split is for.

---

## 7. Costs and what remains

Net of the **0.24% delivery toll**, every type at every horizon in the holdout is negative — except BREAKOUT at h >= 5, which is the non-persistent momentum regime described above.

> **UPDATE 2026-08-28 — all three follow-ups are now COMPLETE. See `breakout-hac.md`.**
> The Newey-West correction cuts BREAKOUT to **t = 1.47 / 1.40 / 0.99** at h = 5/10/21 (inflation 1.8×/2.4×/3.4×), against the 3.0–3.3 Bonferroni bar. The h=1 control is unmoved (1.44 → 1.48), and 36 disjoint non-overlapping subsamples confirm it kernel-free. Worse for the effect: it is absent in the **first half of the holdout too** (h=5, t = 0.08) — 808 flat sessions then nine warm months. Stops lower the mean in every cell; the effect is nil in liquid names (NW t = 0.16). **§6's verdict stands and is strengthened. Lane closed.**

**Not completed (disk filled) — now done, see above.** Script `quant/_winner_anatomy2.py` (rebuilt 2026-08-28; the original was never written) contains all three:

1. **Newey-West overlap correction** — would settle §6 objection 2 with a number instead of an argument.
2. **Stop-loss truncated-payoff test** — whether truncating the left tail changes any type's economics.
3. **BREAKOUT decomposition by turnover bucket with momentum control** — whether anything survives once `mom_12_1` is held constant.

None of the three is likely to reverse the verdict. Item 1 is the one worth running, because the BREAKOUT t-statistic is currently the only number in this study that could be mistaken for a live edge, and it deserves to be shot with a computation rather than a paragraph.

---

## 8. Status

**Closed as a negative result.** The winner-typing direction is not worth further investment beyond the three follow-ups above.
