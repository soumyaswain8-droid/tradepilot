# Overnight Gap Risk for a Stop-Only Positional Book

**VERDICT — the gap is not what kills this lane.** On the names our screen would actually pick,
the expected loss beyond a 2% stop is **0.059% per night held**, against **0.107% per night** of
intraday toll avoided by not round-tripping. The gap eats 55% of the saving and leaves 45%.

**What kills it is the Rs18.80 DP charge.** On a Rs24,000 book split 4 ways, the delivery round
trip costs 0.553% of position value, and the lane does not break even against the intraday
alternative until a **20-session hold**. At 3 positions it needs 10 sessions. At 1-2 positions it
works from 10 sessions. The gap risk and the DP charge together consume the entire toll saving.

**Sizing is not the binding constraint.** A fully-deployed Rs24,000 book in 4 mover positions loses
**Rs578 on a p99 night** and **Rs1,085 on a p99.9 night** — survivable. But cost wants 1-2 big
positions and the tail wants 4-6 small ones, and on Rs24,000 you cannot have both.

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — positional lane feasibility |
| **Version** | `v1.0.0` |
| **Status** | Complete |
| **Created** | 2026-09-01 |
| **Data** | `quant/data/bhavcopy_daily.parquet`, offline, no Kite |
| **Sample** | 1,590,117 tradeable stock-nights, 2,520 symbols, 2021-07-08 to 2026-08-26 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## 0. Universe construction and the filters that matter

Started from 2,586,854 rows / 3,269 symbols. Applied, in order:

::: {.inventory-table}

| Filter | Rule | Rows dropped |
|:-------|:-----|-------------:|
| Liquidity | 20-day median `turnover_lakh` >= **100** (= Rs 1 crore), known as of close[t] | — (1,667,190 survive) |
| prev_close reconciliation | \|`prev_close`/close[t] − 1\| <= 2% — catches relisting and corrupt prev_close | 26,921 |
| Circuit band | \|gap\| <= 20% — see below | 407 |
| Session contiguity | previous row must be the immediately prior session | 49,745 |
| **Final** | | **1,590,117 nights** |

:::

**The units trap was real and I hit the corporate-action trap too.** `turnover_lakh` is in Rs LAKH,
so the Rs 1 crore threshold is `>= 100`, not `>= 1e7`. Separately: the brief suggested a prev_close
reconciliation within 2% as the corporate-action filter. **That filter does not work on this store.**
This bhavcopy's `prev_close` is *unadjusted* — on a 1:10 split day it equals the raw previous close,
so the reconciliation passes cleanly while the gap reads −90%. My first pass kept LICMFGOLD at
−98.97%, GROWWSLVR at −90.1%, SAKSOFT at −90.4% — all splits. The reconciliation still earns its
keep (it removes 26,921 relisting/suspension artefacts) but it is **not** the split filter.

The split filter that works is the **circuit band**: NSE's widest price band is 20%, so an opening
print more than 20% from the previous close is arithmetically impossible in a normal session and is
therefore a corporate action. 407 rows, every one inspected being a split or bonus.

**A sensitivity I attempted and then discarded, because it was wrong.** I tried culling gaps whose
open/close ratio matched a common bonus ratio (1:1, 1:4, 1:10 …) to within 0.4%. It removed 10,603
rows and cut p0.1 from −8.19% to −3.60% — implausibly good. The reason: **4/5 = 0.80 is both a 1:4
bonus and the −20% lower circuit; 9/10 is both a 1:9 bonus and the −10% circuit; 19/20 is the −5%
circuit.** The filter was culling real crashes. ADANIENSOL on 2024-11-21 — the bribery-indictment
gap, a genuine −20.0% — was flagged as a corporate action. So was GPIL, GVKPIL, SOLARA, WHIRLPOOL.
**With daily data alone, an in-band bonus and a circuit-locked crash are not separable.** I have kept
the raw distribution and flagged the residual contamination in §8 rather than launder the tail.

---

## 1. The gap distribution

`gap = open[t+1] / close[t] − 1`, all 1,590,117 tradeable stock-nights.

::: {.metrics-table}

| Percentile | Gap | |
|:-----------|-------:|:--|
| p0.1 | **−8.19%** | 1 night in 1,000 |
| p1 | **−3.13%** | |
| p5 | −1.26% | |
| p10 | −0.71% | |
| p25 | −0.05% | |
| **median** | **+0.24%** | |
| p75 | +0.71% | |
| p90 | +1.33% | |
| p95 | +1.94% | |
| p99 | +4.02% | |
| p99.9 | +8.47% | |

:::

Mean **+0.294%**, std 1.214%, **skew −0.084**, min −20.0%, max +20.0%.
Deeper into the tail: p0.5 = −4.44%, p0.01 = **−16.44%**.

Three things to notice.

**The median gap is positive (+0.24%) and so is the mean (+0.294%).** More than half of all
stock-nights gap up. This is the overnight-drift anomaly and it is large here — §5 deals with it and
with why it is less capturable than it looks.

**The skew is very slightly negative (−0.084) but the tail asymmetry is real.** p1 is −3.13% while
p99 is +4.02%, which looks symmetric-to-right-skewed. But p0.1 is −8.19% against p99.9 of +8.47%,
and p0.01 is −16.44%. The distribution is roughly symmetric out to p1 and then the left side
degenerates faster in the region that matters for a stop.

**The tail is truncated by construction.** 0.0028% of nights open at or below −19%; the −20% circuit
is a hard wall. A stock that "wanted" to open at −35% opens at −20% and then trades down through the
day. **Every left-tail number in this document is therefore an understatement**, and the
understatement is worst exactly where it hurts most. See §8.

---

## 2. Stop survivability

Entry assumed at close[t]; stop placed at `entry × (1 − s)`. "Through" = the open is below the stop,
so the stop cannot be honoured and the fill is the open.

::: {.suite-table}

| Stop | P(gap through) | Mean fill | Median fill | p5 of fills | Worst |
|:-----|---------------:|----------:|------------:|------------:|------:|
| 2% | **2.370%** | **−3.62%** | −2.90% | −7.55% | −20.0% |
| 3% | 1.096% | −5.01% | −4.24% | −10.00% | −20.0% |
| 5% | 0.316% | −7.83% | −6.60% | −15.15% | −20.0% |

:::

Read the 2% row carefully, because it answers the question the brief asks. A 2% stop is jumped on
**2.37% of nights** — roughly one night in 42 — and when it is jumped, **the average fill is −3.62%,
not −2%**. The median failure is −2.90%: mild. But the p5-of-failures is −7.55%, and 5% of 2.37% is
about one night in 840 where a 2% stop turns into a loss of 7.5% or worse. On a Rs6,000 position
that is Rs450 against an intended Rs120.

The wider the stop, the rarer the breach but the uglier it is when it happens: a 5% stop only fails
once in 316 nights, but the mean failure is −7.83% and the p5 is −15.15%. **Widening the stop does
not buy safety, it buys concentration** — the same expected damage delivered in fewer, larger hits.

---

## 3. Expected cost of the gap, per night, against the toll saved

Define the marginal charge for one night of exposure as the expected loss *beyond* the stop:
`E[max(0, −gap − s)]`. The stop loss itself is not a gap cost — you would take it intraday too.
Only the overshoot is attributable to holding.

::: {.metrics-table}

| Slice | E[excess] / night, 2% stop | E[excess] / night, 3% | E[excess] / night, 5% |
|:------|--------------------------:|----------------------:|----------------------:|
| Whole tradeable universe | **0.0384%** | 0.0221% | 0.0090% |
| Quiet names (prior move < 1%) | 0.0232% | 0.0123% | 0.0048% |
| **Screen proxy** (prior +5% AND top-vol tercile) | **0.0590%** | 0.0295% | 0.0103% |
| Prior day >= +8% | 0.0667% | 0.0303% | 0.0092% |
| Prior day >= +12% | 0.1036% | — | — |
| Prior day <= −5% (buying the crash) | **0.2254%** | — | — |

:::

**The toll saved.** Per night of exposure, an intraday book must pay a fresh round trip: **0.107%**
of position value. A positional book pays one delivery round trip amortised over the whole hold:
`(0.240% + Rs18.80/P) / H`. So the marginal saving from holding one more night is
`0.107% − (0.240% + Rs18.80/P)/H`, with a **ceiling of 0.107%/night** as H grows.

**Direct comparison, at the ceiling:**

::: {.metrics-table}

| | Per night | Share of the 0.107% ceiling |
|:--|----------:|----------------------------:|
| Toll saved (ceiling, H → large) | +0.107% | 100% |
| Gap cost, universe | −0.038% | **36%** |
| Gap cost, our screen slice | −0.059% | **55%** |
| Gap cost, prior day >= +8% | −0.067% | **62%** |
| Gap cost, buying a −5% crash | −0.225% | **211% — negative** |

:::

**Answer to the central question: the toll saved is larger than the gap risk, by roughly 1.8x on
the names we would actually trade.** 0.107% saved against 0.059% paid, net +0.048%/night. That
margin is not comfortable but it is the right sign — *provided the hold is long enough for the
delivery round trip to amortise*, which is where the lane actually breaks.

---

## 3b. Where it actually breaks: the DP charge

The 0.107% ceiling is only reached at infinite hold. The real per-night economics on a Rs24,000
book, net of the gap cost (screen slice, 0.059%/night):

::: {.suite-table}

| Position size | Positions | Hold 2d | Hold 5d | Hold 10d | Hold 20d |
|:--------------|----------:|--------:|--------:|---------:|---------:|
| Rs24,000 | 1 | −0.111% | −0.016% | **+0.016%** | **+0.032%** |
| Rs12,000 | 2 | −0.150% | −0.031% | **+0.008%** | **+0.028%** |
| Rs8,000 | 3 | −0.190% | −0.047% | +0.000% | **+0.024%** |
| Rs6,000 | 4 | −0.229% | −0.063% | −0.007% | **+0.020%** |
| Rs4,000 | 6 | −0.307% | −0.094% | −0.023% | **+0.013%** |
| Rs3,000 | 8 | −0.385% | −0.125% | −0.039% | +0.005% |

:::

*(net %/night = 0.107 − (0.240 + 1880/P)/H − 0.059)*

The Rs18.80 DP charge is **0.078%** of a Rs24,000 position but **0.627%** of a Rs3,000 one. On a
small book it is the single largest line item — larger than STT, larger than the gap. At 8 positions
the delivery round trip costs 0.867% of position value, eight times the intraday round trip it was
supposed to replace.

At the best cell in that table (1 position, 20-day hold) the edge is +0.032%/night = **Rs7.70 a
night on a Rs24,000 book**. That is the entire prize from the toll arbitrage. It is noise. **The
toll saving is real and it does beat the gap risk, but on Rs24,000 the absolute rupees are too
small to build a lane around on cost grounds alone.** The lane has to earn its keep from directional
edge, not from cost arbitrage — see §5.

---

## 4. Conditioning: do our names have fatter left tails?

**Yes. Measuring the average stock would have flattered us by about 60%.**

::: {.suite-table}

| Slice | n | p1 | p5 | P(through 2%) | Mean fill | E[excess]/night |
|:------|--:|---:|---:|--------------:|----------:|----------------:|
| **Universe** | 1,590,117 | −3.13% | −1.26% | **2.37%** | −3.62% | 0.0384% |
| Liquidity T1 (low, Rs1.0-4.5cr) | 530,041 | −3.30% | −1.37% | 2.57% | −3.58% | 0.0406% |
| Liquidity T2 (Rs4.5-21cr) | 530,038 | −3.11% | −1.23% | 2.33% | −3.66% | 0.0386% |
| Liquidity T3 (high, >Rs21cr) | 530,038 | −3.02% | −1.16% | 2.21% | −3.63% | 0.0361% |
| Vol T1 (low, <28.5% ann.) | 529,447 | −2.37% | −0.92% | 1.34% | −3.33% | 0.0179% |
| Vol T2 (28.5-42.6% ann.) | 529,445 | −2.82% | −1.21% | 1.99% | −3.54% | 0.0305% |
| **Vol T3 (high, >42.6% ann.)** | 531,225 | −4.26% | −1.65% | **3.77%** | −3.77% | **0.0668%** |
| Quiet (prior move <1%) | 714,213 | −2.52% | −1.04% | 1.67% | −3.39% | 0.0232% |
| Prior day >= +3% | 151,241 | −3.17% | −1.40% | 2.71% | −3.37% | 0.0370% |
| **Prior day >= +5%** | 57,856 | −3.49% | −1.68% | **3.75%** | −3.30% | 0.0488% |
| Prior day >= +8% | 19,189 | −3.91% | −2.10% | **5.54%** | −3.20% | 0.0667% |
| Prior day >= +12% | 5,681 | −4.43% | −2.59% | **8.24%** | −3.26% | 0.1036% |
| **Prior day <= −5%** | 34,077 | **−8.35%** | −3.11% | **8.37%** | **−4.69%** | **0.2254%** |
| **Screen proxy** (+5% & top-vol) | 42,301 | −3.77% | −1.87% | **4.41%** | −3.34% | 0.0590% |
| Screen & bottom-liq | 20,856 | −3.79% | −1.70% | 3.84% | −3.48% | 0.0567% |
| Screen & top-vol & bottom-liq | 15,511 | −4.16% | −1.87% | 4.40% | −3.52% | 0.0670% |

:::

**Volatility is the dominant conditioner, not liquidity.** The liquidity terciles barely separate —
2.21% vs 2.57% breach rate top to bottom. Within a Rs 1 crore turnover floor, more liquidity buys
you almost nothing in gap protection. Realised volatility separates hard: 1.34% vs 3.77%, a factor
of 2.8, and E[excess] goes 0.018% → 0.067%, a factor of 3.7.

**Being a mover is a genuine, monotone risk premium.** Breach rate at a 2% stop: 1.67% (quiet) →
2.71% (+3%) → 3.75% (+5%) → 5.54% (+8%) → 8.24% (+12%). Our entries are movers by construction, so
the honest number for this lane is 3.75-4.4%, not the universe's 2.37%. **The universe average
understates our gap-through rate by ~60% and our E[excess] by ~54%.**

One consolation: conditional on breaching, movers-up fill slightly *better* than the universe
(−3.30% vs −3.62%). They breach more often but less violently. The extra risk is frequency, not
severity.

**The one slice that is unambiguously fatal is buying after a crash.** Prior day <= −5%: p1 of
−8.35%, an 8.37% breach rate, a −4.69% mean fill, and E[excess] of 0.225%/night — **twice the entire
toll saving**. If any part of the screen has a mean-reversion / falling-knife component, that part
cannot be held overnight at all.

---

## 5. Does holding pay? The overnight drift

::: {.suite-table}

| Slice | n | Overnight mean | Overnight median | Intraday mean | Close-to-close mean | c2c median |
|:------|--:|---------------:|-----------------:|--------------:|--------------------:|-----------:|
| Universe | 1,590,117 | **+0.294%** | +0.240% | −0.216% | +0.073% | −0.068% |
| Prior day >= +3% | 151,241 | +0.640% | +0.497% | −0.291% | +0.342% | −0.017% |
| **Prior day >= +5%** | 57,856 | **+0.639%** | +0.518% | −0.261% | +0.371% | −0.065% |
| Prior day >= +8% | 19,189 | +0.898% | +0.652% | −0.290% | +0.596% | −0.034% |
| Prior day <= −5% | 34,077 | +0.213% | +0.284% | +0.337% | +0.534% | +0.509% |
| Screen proxy | 42,301 | +0.688% | +0.542% | −0.243% | +0.436% | −0.037% |

:::

**The overnight drift is strongly positive and it is strongest exactly on the names we would hold.**
+0.639%/night mean and +0.518% median for prior-day +5% movers, against a gap cost of 0.049%/night
and a toll saving of 0.107%/night. **The drift is an order of magnitude larger than either.** If it
is real, the entire cost debate in §3 is a rounding error.

It is also where every one of my doubts lives. Four caveats, in descending order of how much they
worry me:

1. **You cannot buy at the printed close.** NSE's official close is a volume-weighted average of the
   last 30 minutes, not a tradeable price. A market order at 15:29 fills near the last trade. In a
   period where the last half-hour drifts, the difference is systematically against you and it is
   plausibly of the same order as the +0.24% median gap itself. This alone could account for most of
   the universe-level drift.
2. **You cannot sell at the printed open either.** The 09:15 print is the pre-open auction
   equilibrium. It is thin, and it is thinnest on exactly the gap-down mornings where you most need
   it. Every "fill at the open" in §2 is an optimistic floor.
3. **The period is a bull market.** 2021-07 to 2026-08 is a sustained Indian small-cap advance.
   +0.294%/night equal-weighted annualises to ~73%, which is not a stationary parameter — it is a
   description of this sample.
4. **The mean is a right tail, the median is not.** For +5% movers the close-to-close mean is
   +0.371%/day but the **median is −0.065%/day**. More than half of mover entries lose money day
   over day; the mean is carried by a minority of large winners. That is a normal momentum profile,
   but it means a small book will experience a long string of small losses, and any position sizing
   that cannot survive that string will never reach the winners.

**Conclusion for §5: the drift does not kill the idea — it is the strongest thing in this document
in the lane's favour. But it is measured at prices you cannot transact, and validating it against
realistic close/open fills is a strictly higher priority than anything about gaps.**

---

## 6. Position sizing

A single-name gap is not the risk that sizes a book — a market-wide gap is, because on a bad night
every position gaps together. Measured directly: the cross-sectional mean gap by date, 1,267 days.

::: {.metrics-table}

| Market-wide mean gap | Value |
|:---------------------|------:|
| p0.1 | −3.52% |
| p1 | −1.63% |
| p5 | −0.58% |
| median | +0.34% |
| mean | +0.30% |
| **worst observed** | **−8.06%** (2025-04-07) |

:::

The eight worst nights in five years: 2025-04-07 (−8.06%, the tariff shock), 2026-03-02 (−3.52%),
2022-02-24 (−3.52%, the invasion), 2022-02-22 (−2.80%), 2024-08-05 (−2.48%, the yen-carry unwind),
2022-08-29, 2025-05-09, 2022-02-14. **The correlated event is the sizing constraint, and it arrives
about once a year.**

Portfolio-level, drawing k names at random *from the same date* (so correlation is preserved), from
the mover slice — i.e. exactly the book we would run:

::: {.suite-table}

| Positions | Size on Rs24,000 | p99 night | p99.9 night | Worst observed |
|:----------|-----------------:|----------:|------------:|---------------:|
| 1 | Rs24,000 | −3.54% = **Rs850** | −7.99% = **Rs1,918** | −20.0% = Rs4,800 |
| 2 | Rs12,000 | −2.86% = Rs686 | −5.63% = Rs1,351 | −11.9% = Rs2,861 |
| 3 | Rs8,000 | −2.56% = Rs614 | −4.95% = Rs1,188 | −10.7% = Rs2,558 |
| **4** | **Rs6,000** | **−2.41% = Rs578** | **−4.52% = Rs1,085** | −8.10% = Rs1,944 |
| 6 | Rs4,000 | −2.27% = Rs545 | −4.28% = Rs1,027 | −6.83% = Rs1,639 |

:::

Diversification helps in the tail but saturates fast, because the residual is market beta and cannot
be diversified away: going 1 → 4 positions halves the p99.9 loss (Rs1,918 → Rs1,085); going 4 → 6
buys only another Rs58.

**The recommendation, and the assumption it protects.**

> **Assumption protected: a p99.9 overnight event — one bad night every four years of daily holding —
> must not cost more than 5% of the book (Rs1,200), and a p99 night (2-3 times a year) must not cost
> more than 2.5% (Rs600).**

**Four positions of Rs6,000 each, fully deployed.** p99 = Rs578 (2.4%), p99.9 = Rs1,085 (4.5%),
worst-in-five-years = Rs1,944 (8.1%). Both budgets are met with a little room. Three positions of
Rs8,000 also passes (Rs614 / Rs1,188) and costs meaningfully less in DP charges — **Rs8,000 × 3 is
the better cell if you can accept a p99 of 2.6%**, and it is the configuration I would actually run,
because §3b shows the cost curve is steeper than the risk curve between k=3 and k=4.

**Do not run 1 or 2 concentrated positions.** The cost table wants it, but a single position carries
a −20% worst case (Rs4,800, one fifth of the book) and a p99.9 of Rs1,918. The Rs130/round-trip DP
saving is not worth that.

**And note what this section really says: the gap is affordable.** Rs578 on a p99 night is not a
book-ending event. **A stop-only overnight book on Rs24,000 CAN be sized safely.** The reason to be
cautious about this lane is cost (§3b) and execution realism (§5), not tail risk.

---

## 7. The multi-day version

Gaps compound. Measured path-wise on actual consecutive sessions (not iid-assumed), from **mover
entries** (prior day >= +5%):

::: {.suite-table}

| Hold | P(>=1 gap through 2%) | iid prediction | Mean worst gap | p1 worst | p0.1 worst | Total E[excess] | Cum. overnight |
|:-----|----------------------:|---------------:|---------------:|---------:|-----------:|----------------:|---------------:|
| 1 night | **3.75%** | 3.75% | +0.64% | −3.49% | −7.92% | 0.049% | +0.64% |
| 2 nights | **6.94%** | 7.35% | −0.21% | −4.80% | −11.47% | 0.109% | +0.98% |
| 5 nights | **14.96%** | 17.4% | −0.97% | −7.10% | −15.71% | 0.280% | +2.07% |
| 10 nights | **24.88%** | 34.0% | −1.56% | −9.69% | −17.34% | 0.542% | +3.75% |

:::

For the universe (for contrast): 2.37% / 4.49% / 10.18% / 18.23% at 1/2/5/10 nights.

**A 10-day mover hold breaches a 2% stop on a gap one time in four.** That is the number to
internalise before building the lane — a quarter of ten-day holds will have at least one morning
where the stop was meaningless.

**Realised breaches are consistently *below* the iid prediction** (24.9% vs 34.0% at 10 nights).
Gaps cluster: bad nights concentrate in the same names and the same weeks, so the *number of names
affected* is smaller than independence would suggest, but the *damage to those names* is worse. This
cuts both ways for a small book — fewer positions hit, but when the market-wide night arrives (§6)
all of them are hit at once.

**The multi-day economics are the ones that work.** Over a 10-night mover hold: cumulative overnight
drift **+3.75%**, total expected gap excess **−0.542%**. That is a **6.9:1 ratio in favour of
holding**. And the DP charge amortises: at Rs8,000 × 3 positions, 10 sessions, the delivery round
trip is 0.0475%/night against 0.107% of intraday toll avoided. **Long holds are what make this lane
work; short holds make it strictly worse than intraday.** A 2-day hold is negative in every cell of
the §3b table.

---

## 8. What makes this measurement optimistic

Listed in order of how much I think each one matters.

**1. You cannot exit at the open — this is the big one.** Every §2 fill assumes you transact at the
pre-open auction price. On a gap-down morning that auction is thin and one-sided, and a market
order behind it fills worse. The mean fill of −3.62% at a 2% stop is a **floor**, not an estimate.
I cannot size this error without intraday data; I would guess 20-50 bps of additional slippage on
breach mornings, which would push the screen-slice E[excess] from 0.059% toward 0.07-0.08%/night —
i.e. from 55% of the toll saving to 65-75% of it.

**2. The 20% circuit truncates the tail I am trying to measure.** 0.0028% of nights open at or below
−19%, and 407 rows were removed as exceeding the band (all corporate actions). But a name that
"wants" to open at −40% opens at −20% *locked*, with no liquidity to sell into, and trades down from
there. **My worst-case is capped at −20% by exchange rule, not by reality.** Illiquid names with
2%/5%/10% bands are truncated even harder. The genuine left tail of a stop-only book is worse than
anything in this document, and I have no way to see it in daily bhavcopy.

**3. You cannot enter at the printed close.** NSE's close is a 30-minute VWAP. Buying at 15:29 in a
rising tape means paying more than the number I used as the entry price. This inflates every
overnight-return figure in §5 and, because the entry price is also the stop reference, slightly
understates the §2 breach rates.

**4. Residual corporate actions inside the ±20% band.** Small bonuses (1:10 = −9.09%, 1:20 = −4.76%)
and large special dividends survive both filters and masquerade as gap-downs. As shown in §0 they
are **not separable from circuit-locked crashes** with daily data — 4/5, 9/10 and 19/20 are
simultaneously bonus ratios and circuit levels. This bias runs the *other* way (it makes the left
tail look worse than it is), so it partly offsets items 1-3, but I cannot net them. A CA calendar
would settle it and should be sourced before this lane goes live.

**5. Sample period.** 2021-07 to 2026-08 contains exactly one broad crash night (2025-04-07,
−8.06% market-wide). March 2020 is not in the store — the data begins 2021-06-17. **The worst night
in this sample is not the worst night that can happen.**

**6. Contiguity filter removes 49,745 nights.** These are suspension/halt resumptions, which a real
book *would* have been holding through. Removing them is convenient and makes the measurement
optimistic. They are 3% of the sample.

**7. Survivorship — the mildest concern.** 573 of 3,269 symbols stop trading before the sample end
and remain in the store, so dead names are represented. The liquidity and volatility filters are
computed as-of and shifted, with no lookahead. The store's start date (2021-06-17) is the only
survivorship cut: anything delisted before then is simply absent.

---

## 9. What I would do

1. **Do not build the lane for the cost saving.** §3b: at any position count a Rs24,000 book can
   support, the net edge from the toll arbitrage is between −0.06% and +0.03% per night — under
   Rs8/night at best. The Rs18.80 DP charge is 0.31% of a Rs6,000 position and eats what the gap
   leaves.
2. **Validate the overnight drift against transactable prices before anything else.** +0.64%/night
   on movers is 10x the gap cost and 6x the toll saving. It is the only number here big enough to
   fund a lane, and it is measured at two prices you cannot trade. This is the single highest-value
   follow-up.
3. **If the lane is built: 3 positions of Rs8,000, minimum 10-session hold, 3% stop.** Three
   positions passes the p99.9 budget (Rs1,188) while keeping the DP charge to 0.235% of position.
   A 3% stop cuts E[excess] from 0.059% to 0.030%/night for a breach rate of 1.85% — and a stop-only
   book should prefer the rarer, wider stop precisely because the stop is not enforceable overnight
   anyway.
4. **Exclude prior-day decliners from the overnight book entirely.** Prior day <= −5% carries
   E[excess] of 0.225%/night, twice the entire toll saving, with a p1 of −8.35%. If the screen has
   any mean-reversion component, that component must be flat by the close.
5. **Filter on realised volatility, not on liquidity.** Within a Rs 1 crore floor, extra liquidity
   buys almost nothing (2.57% vs 2.21% breach rate). The top volatility tercile breaches 2.8x more
   than the bottom. A vol cap is the cheapest gap-risk control available.
6. **Source a corporate-action calendar.** It is the one measurement error I could not resolve, and
   it is contaminating the exact region of the distribution the sizing depends on.
