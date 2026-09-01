# Does the Overnight Mover Drift Survive Transactable Prices?

**VERDICT — FAIL, 0 of 4 pre-registered criteria. At fills you can actually get, the
+0.639%/night drift becomes +0.435%/night gross, and a Rs8,000 position pays 0.475% to
harvest it. Net: −0.040%/night, median −0.048%, t = −0.32.**

**The drift is not an illusion of untradeable prices — realistic fills cost only 8bp, far less
than `gap-risk.md` feared. It dies on two other things: the flat Rs18.80 DP charge (breakeven
needs a Rs9,623 position), and the fact that the mean lives in 12 events out of 299 that were
locked at upper circuit when you would have had to buy them.**

**Do not build the lane. The one honest caveat: at Rs24,000 concentration the mean is
+0.117%/night, but t = 0.94 and `gap-risk.md` §6 already rejected that configuration on tail
risk. There is no cell that passes both.**

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — positional lane feasibility |
| **Version** | `v1.0.0` |
| **Status** | Complete — negative result |
| **Created** | 2026-09-01 |
| **Parent** | `docs/research/positional/gap-risk.md` §5, §9 item 2 |
| **Data** | `quant/data/bhavcopy_daily.parquet` (events) + Kite 5-minute historical (fills) |
| **Sample** | 336 drawn / 300 priced / 286 tradeable, 251 distinct dates, 2021-07 to 2026-08 |
| **Pre-registration** | Written and frozen before any intraday bar was fetched — §2 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## 1. What was measured, and every choice that decides the answer

`gap-risk.md` §5 measured +0.639%/night on prior-day +5% movers using `close[t] → open[t+1]`.
Neither price is transactable: the NSE daily close is a 30-minute VWAP of the closing session,
and the open is the pre-open call auction. This document replaces both with prices from
5-minute bars.

### 1.1 Event definition (daily bhavcopy)

::: {.inventory-table}

| Rule | Threshold | Why |
|:-----|:----------|:----|
| Mover day | `close[t]/close[t−1] − 1` in **[+5%, +20%]** | The +20% cap is the circuit band — a close-to-close move above it is arithmetically impossible and is therefore a corporate action |
| Liquidity | 20-day median `turnover_lakh` **>= 100** | Rs 1 crore. `turnover_lakh` is in Rs **LAKH**. Computed through day *t* inclusive — known at the close, no lookahead |
| Split filter | \|`open[t+1]/close[t]` − 1\| **<= 20%** | The **circuit band**, not a `prev_close` reconciliation. `gap-risk.md` §0 establishes why: this store's `prev_close` is unadjusted, so a split passes the reconciliation cleanly |
| Contiguity | day *t−1*, *t*, *t+1* must be consecutive sessions | |

**Population: 57,384 mover-nights, 2,245 symbols, 2021-07-14 to 2026-08-25.**
Paper drift +0.6365% mean, +0.5155% median — reproducing `gap-risk.md` §5 to within 3bp.

### 1.2 Sampling — stratified, so no regime can carry the result

Twenty-one calendar quarters (2021Q3 … 2026Q3), **16 events drawn per quarter**, at most 2 per
symbol, `numpy` seed 20260901. **336 events, 299 distinct symbols.**

The sample reproduces the population: paper drift **+0.632% mean / +0.478% median** against
+0.637% / +0.516%. It is not a lucky draw.

### 1.3 Entry — the price you can actually hit

**Volume-weighted average of the 15:15 and 15:20 five-minute bars (15:15–15:25 IST),**
typical price `(H+L+C)/3` weighted by bar volume.

Chosen because it is an order a person can work: ten minutes of participation, finishing five
minutes before the close, entirely outside the 15:00–15:30 window the official close is
averaged over. A single market order at 15:29 would be a worse and less honest assumption —
it concentrates the whole position into one print in the thinnest, most reflexive minute of
the day.

### 1.4 Exit — deliberately not the open print

**Close of the 09:15 five-minute bar — the traded price at 09:20, five minutes after the
open.** Secondary exit reported throughout: VWAP of 09:15–09:25.

The pre-open auction print is excluded by construction. It is the price `gap-risk.md` §8
item 1 flagged as an optimistic floor.

### 1.5 Costs

0.240% delivery round trip **plus the flat Rs18.80 DP charge on the sell**. Reported at three
position sizes because that flat fee is 0.078% of Rs24,000 and 0.627% of Rs3,000. Headline is
**Rs8,000** — the size `gap-risk.md` §9 recommends (3 positions on a Rs24,000 book).

---

## 2. The pre-registered bar

Frozen in `PREREG.txt` **after** drawing the sample and seeing its paper drift, but **before
fetching a single intraday bar** — therefore before any realistic-fill or netted number existed.

::: {.metrics-table}

| | Criterion | Threshold |
|:--|:----------|:----------|
| **B1** | per-trade net **mean** | >= **+0.15%**/night |
| **B2** | date-clustered **t-statistic** | >= **3.0** |
| **B3** | per-trade net **median** | > **0** |
| **B4** | top 5% of events' share of net P&L | <= **50%** |

:::

All four at the Rs8,000 headline size. **4/4 = build. 3/4 = redesign and retest. <=2/4 = dead.**

B3 is the load-bearing one and was made deliberately hard: `gap-risk.md` §5 already showed the
mover close-to-close **median** is −0.065%/day. If the net median is negative the lane is a
right-tail lottery, and a Rs24,000 book will not survive the losing string long enough to reach
the tail.

**Also frozen in advance:** if Kite coverage fell below 60% of sampled events, the answer would
be *undetermined*, not *fail*.

---

## 3. Data acquisition and two traps in it

**Coverage: 300 of 336 events priced (89.3%)** — comfortably above the 60% floor. 265 of 299
symbols resolved to an NSE instrument token; the 34 that did not are delisted or renamed
(AGSTRA, APTECHT, JPASSOCIAT, ONMOBILE, …). 265 Kite calls, throttled to 0.34s, 154 seconds
total, zero errors — a live trading session was sharing the token.

**Trap 1 — Kite is corporate-action adjusted, bhavcopy is not.** 55 of 300 events came back
with Kite prices at a different level from bhavcopy, one of them at 0.5x. Compared naively,
this reads as −49% of "slippage". It is a later split, back-adjusted into Kite's history.

The fix: recover the adjustment factor per day from `high` and `low`, which are exact matching
quantities between the two stores, then normalise bhavcopy into Kite's space before comparing.
The two anchors agreed to 5 decimal places on every event. **The ratio returns were never
affected** — entry and exit both come from Kite, so a constant factor cancels. Only the
paper-vs-real comparison needed the fix. One event whose factor *changed* across the night (a
corporate action on the night itself) was dropped: **299 clean nights**.

**Trap 2 — coverage is mildly biased, and it runs in the lane's favour.** The 36 unresolved
events had a *higher* paper drift (+0.859% vs +0.605%) and lower liquidity (median 20-day
turnover Rs359 lakh vs Rs745 lakh). Correcting for it would add roughly **+0.03pp** to every
mean below. That is stated here so it cannot be read as a hidden thumb on the scale; it does
not change any verdict, and those names are the least tradeable in the sample.

---

## 4. What realistic fills actually cost — and the finding that contradicts the prior

::: {.suite-table}

| Comparison | n | Mean | Median | p10 | p90 |
|:-----------|--:|-----:|-------:|----:|----:|
| Kite 09:15 bar open vs printed open *[sanity]* | 299 | −0.009% | **+0.000%** | −0.019% | +0.003% |
| **ENTRY** 15:15–25 VWAP vs printed close | 299 | **+0.012%** | **+0.012%** | −0.363% | +0.384% |
|   … on the biggest movers (day >= +8%) | 93 | +0.045% | +0.000% | −0.472% | +0.432% |
| **EXIT** @09:20 vs printed open — all | 299 | **−0.072%** | −0.130% | −1.799% | +1.748% |
|   … **UP-gap** mornings | 209 | **−0.105%** | −0.201% | −1.889% | +1.709% |
|   … **DOWN-gap** mornings | 90 | **+0.006%** | −0.127% | −1.564% | +1.783% |
| EXIT VWAP 09:15–25 vs printed open — all | 299 | −0.047% | −0.069% | −1.661% | +1.609% |
|   … UP-gap | 209 | −0.070% | −0.083% | −1.873% | +1.583% |
|   … DOWN-gap | 90 | +0.008% | +0.042% | −1.336% | +1.772% |

:::

**Three things here are worth more than the verdict.**

**1. The entry worry was wrong.** `gap-risk.md` §8 item 3 predicted that buying at 15:29 in a
rising tape would cost materially against the printed 30-minute-VWAP close. Measured, a
15:15–15:25 participation costs **+1.2bp**, mean and median alike. The reason is mechanical:
the closing VWAP window is 15:00–15:30, and 15:15–15:25 sits inside it, so the entry is drawn
from the same distribution as the benchmark. The concern was real in principle and is
approximately zero in size for this order shape.

**2. The exit asymmetry runs the opposite way to the prediction.** The brief expected down-gap
mornings to be the painful ones — thin book, one-sided, you sell into it. Measured, **down-gap
mornings cost nothing (+0.006%) and up-gap mornings cost 10bp.** The pre-open auction
*overshoots*, and the first five minutes fade it back: a gap up gives some back, a gap down
bounces. Waiting five minutes is a small loss on the mornings you are happy and a small gain on
the mornings you are not. That is the reverse of the feared asymmetry, and it is the mild
consolation in this document.

**3. The 09:15 auction print is reachable at 09:15 but not at 09:20.** The sanity row shows
Kite's first continuous-session bar opens at exactly the bhavcopy open (median 0.000%). So the
auction price is real; the cost is the five minutes of waiting, not the auction itself.

**Total realistic-fill cost: 8.4bp/night** (+0.615% paper → +0.531% real, all 299 nights).
**The drift is not an artefact of untransactable prices.** That specific hypothesis is refuted.

---

## 5. Netting it out

Gross, on the **286 tradeable** nights (§6 defines the exclusion):

::: {.metrics-table}

| Leg pair | Gross mean | Gross median |
|:---------|-----------:|-------------:|
| Paper: printed close → printed open | +0.534% | +0.436% |
| Real entry → printed open *(isolates the exit)* | +0.519% | +0.385% |
| **Real entry → real exit @09:20** | **+0.435%** | **+0.427%** |
| Real entry → real exit VWAP 09:15–25 | +0.467% | +0.345% |

:::

Net of 0.240% + Rs18.80/P:

::: {.suite-table}

| Set | Size | Net mean | Net median | Win % | t naive | **t date-clustered** | t NW |
|:----|-----:|---------:|-----------:|------:|--------:|---------------------:|-----:|
| All 299 nights | Rs24,000 | +0.212% | +0.125% | 51.8 | 1.60 | 1.57 | 1.85 |
| All 299 nights | **Rs8,000** | +0.056% | −0.032% | 49.5 | 0.42 | 0.41 | 0.77 |
| All 299 nights | Rs3,000 | −0.336% | −0.423% | 40.5 | −2.54 | −2.49 | −1.94 |
| **Tradeable 286** | Rs24,000 | +0.117% | +0.109% | 51.4 | 0.97 | **0.94** | 1.23 |
| **Tradeable 286** | **Rs8,000** | **−0.040%** | **−0.048%** | 49.0 | −0.33 | **−0.32** | 0.02 |
| **Tradeable 286** | Rs3,000 | −0.431% | −0.440% | 39.9 | −3.59 | **−3.47** | −3.01 |

:::

Date-clustered bootstrap 95% CI on the headline mean (4,000 resamples, dates resampled whole):
**[−0.284%, +0.201%]**. It straddles zero.

**On the t-statistics.** These are one-night, non-overlapping holds, so there is no mechanical
window overlap of the kind `docs/research/overnight/hac-audit.md` corrects — the inflation
mechanism it documents does not apply here, and saying so is more honest than applying a
correction for show. What *does* apply is cross-sectional correlation among events sharing a
date (286 events, 251 distinct dates) and regime clustering across nearby dates. Both are
handled: standard errors are clustered by date, and a Newey-West statistic on the date-mean
series (T=251, L=4 by the 4(T/100)^(2/9) rule) is reported alongside. Clustering barely moves
the number here because dates are nearly unique — which is itself worth knowing.

**The breakeven position size.** Gross real is 0.435%; the variable cost is 0.240%; that leaves
0.195% of headroom for the flat fee. Rs18.80 / 0.195% = **Rs9,623**. Below a Rs9,623 position
the lane cannot pay its own DP charge at any t-statistic. A Rs24,000 book cannot hold three
positions above that line — only two, and `gap-risk.md` §6 rules out two.

---

## 6. Mean versus median, and whether the outliers were tradeable

This is where the lane actually dies.

**The distribution is symmetric-looking and centred on nothing.** Net percentiles, tradeable
set, Rs8,000: p1 −3.98%, p5 −2.91%, p10 −2.39%, p25 −1.24%, **p50 −0.05%**, p75 +0.95%,
p90 +2.16%, p95 +3.02%, p99 +6.08%.

**Tail concentration.** Across 286 tradeable nights the net returns sum to **−11.3
percentage points**. The top 5% (14 events) contribute **+71.9**; the bottom 5% contribute
**−56.6**. Mean excluding the top 5%: **−0.306%**. Excluding both tails: −0.103%.

The top 5% therefore account for *more than* the total P&L — the denominator is negative.
**B4 fails in the strongest possible sense: without the top 5% the lane is not merely weaker,
it is decisively loss-making, and even with them it is still loss-making.**

**And the biggest events were not buyable.** Twelve of the 299 clean nights were frozen through the
entire 15:15–15:25 entry window — every bar with `high == low`, at a price sitting on a
standard 5% / 10% / 20% circuit band. That is an upper-circuit lock: buyers queued, no sellers.
You cannot accumulate a position there.

::: {.metrics-table}

| | n | Real gross mean |
|:--|--:|----------------:|
| Upper-circuit locked in the entry window | **12** | **+3.327%** |
| Everything else | 286 | +0.435% |

:::

**Those 12 unbuyable events are 4% of the sample and they are the difference between a positive
and a negative answer.** Including them, the Rs8,000 net mean is **+0.056%**; excluding them it
is **−0.040%**. The edge that survives to the mean is concentrated in names that were locked
limit-up at the moment the strategy requires you to buy.

Only one event was frozen through 09:15–09:30 the next morning (unexitable). The exit side is
not the problem; the entry side is.

---

## 7. The structural point: this drift cannot be compounded

Worth stating plainly, because it constrains any redesign.

The overnight drift is a **once-per-position** effect. Hold a mover for ten sessions and you
collect ten overnight legs *and* ten intraday legs, which sum to close-to-close — and
`gap-risk.md` §5 measured the mover intraday leg at **−0.261%/day**, cancelling most of it. To
harvest the overnight leg *alone* you must sell every morning and re-buy every afternoon, which
costs a **full delivery round trip every night**: 0.475% at Rs8,000 against 0.435% of realistic
gross. The trade is under water before the first t-statistic is computed.

This is why `gap-risk.md` §7's "long holds are what make this lane work" and this document's
result are not in conflict. Long holds amortise the DP charge — but they amortise it against
close-to-close momentum, which is a different claim requiring a different test. **The overnight
drift specifically cannot fund a lane, because the only way to collect it repeatedly is to pay
for it repeatedly.**

---

## 8. Regime: the paper drift itself has decayed

::: {.suite-table}

| Year | n | Paper mean | Real gross mean | Net mean, Rs8,000 | Net median |
|:-----|--:|-----------:|----------------:|------------------:|-----------:|
| 2021 | 26 | +0.842% | +0.874% | +0.399% | +0.237% |
| 2022 | 50 | +0.745% | +0.548% | +0.073% | −0.173% |
| 2023 | 55 | +0.601% | +0.446% | −0.029% | −0.157% |
| 2024 | 54 | +0.635% | +0.762% | +0.287% | +0.023% |
| 2025 | 57 | +0.433% | +0.655% | +0.180% | +0.313% |
| **2026** | 44 | **+0.034%** | **−0.651%** | **−1.126%** | **−0.929%** |

:::

Quarterly, 11 of 21 quarters are net-positive at Rs8,000 — a coin flip. But the last four
quarters (2025Q4 through 2026Q3) are **all negative on the paper measure as well as the real
one**. Whatever the drift was, it is not present in the most recent year even before costs and
even at untransactable prices. `gap-risk.md` §5 caveat 3 — "the period is a bull market,
+0.294%/night is a description of this sample, not a stationary parameter" — is confirmed
directly.

---

## 9. Scoring against the pre-registered bar

::: {.metrics-table}

| | Criterion | Threshold | Measured (Rs8,000, tradeable) | |
|:--|:----------|:----------|:------------------------------|:--|
| **B1** | net mean | >= +0.15% | **−0.040%** | **FAIL** |
| **B2** | date-clustered t | >= 3.0 | **−0.32** | **FAIL** |
| **B3** | net median | > 0 | **−0.048%** | **FAIL** |
| **B4** | top 5% share of P&L | <= 50% | **>100%** (total is negative) | **FAIL** |

:::

**0 of 4. DEAD by the rule set before the numbers were seen.**

The most generous defensible reading — all 299 nights including the unbuyable ones, at Rs24,000
concentration — gives mean +0.212%, median +0.125%, t = 1.57. That passes B1 and B3 and still
fails B2 and B3's spirit, and it is a configuration `gap-risk.md` §6 explicitly rejected: a
single Rs24,000 position carries a −20% worst case and a p99.9 of Rs1,918. **There is no cell
that passes both this document's bar and the sizing constraint.**

---

## 10. What would change the answer, and what would not

**Would not:** more events. The 95% CI is [−0.284%, +0.201%] and the point estimate is −0.040%.
To establish a +0.15% mean at t=3 against the observed 2.3% dispersion needs roughly n=2,100
events — and the 2026 rows say the parameter is not stable over the five years it would take to
accumulate them. Sample size is not the binding constraint; the effect is.

**Would not:** better fills. Total fill realism costs 8.4bp. Even a perfect fill at both printed
prices leaves the Rs8,000 net mean at +0.056%, still failing B1, B2 and B3.

**Would change it, and is the only thing that would:** a bigger position. The lane is arithmetically
impossible below Rs9,623 per position. At Rs24,000 × 3 positions — a **Rs72,000 book** — the flat
DP charge falls to 0.078% and the net mean becomes +0.117%/night. That is still t=0.94 and still
fails, but it is the only direction in which the numbers move. **The finding is therefore that
this is not a Rs24,000-book strategy, and at the book size where the cost structure stops being
fatal, the edge is not statistically distinguishable from zero anyway.**

**Recommendations**

1. **Do not build the positional lane on the overnight drift.** `gap-risk.md` §9 item 2 called
   this the single highest-value follow-up and made it a gate. The gate is closed.
2. **Retire the +0.639%/night figure from planning documents.** At transactable prices on
   buyable names it is +0.435% gross and −0.040% net, and in the last four quarters it is
   negative on every measure.
3. **The two mechanisms worth keeping.** Entry via a 15:15–15:25 participation costs ~1bp
   against the printed close — reuse it anywhere an "enter at the close" assumption exists in
   the codebase. And exiting five minutes after the open, rather than at the auction, is
   free-to-favourable on down-gap mornings; `gap-risk.md` §2's fills should be read with that
   correction, which makes its stop-survivability numbers slightly *better*, not worse.
4. **If a positional lane is still wanted, test the different claim.** Close-to-close momentum
   over a 10-session mover hold, entered and exited at 15:15–25 VWAPs, at a book size above
   Rs72,000. That is the hypothesis `gap-risk.md` §7 actually supports. It is not this one, and
   this result says nothing about it either way.

---

## 11. What this measurement still cannot see

1. **Market impact is not in it.** Every fill here is a bar VWAP or a bar close — prices that
   *printed*, on volume that other people traded. A Rs8,000 order is small enough that this is
   a fair assumption on names above Rs1 crore turnover, but it is an assumption, not a
   measurement. `docs/research/overnight/t1-slippage.md` shows the project's order-book
   collection covers only the top-200 names and cannot settle it for smaller ones.
2. **The 34 unresolved symbols are survivorship-adjacent.** They are delisted or renamed, they
   had higher paper drift, and they are absent. §3 sizes the bias at ~+0.03pp and it does not
   change the verdict, but it is a real one-directional gap.
3. **Queue position at 09:15 is invisible.** The exit uses the 09:20 traded price. Whether a
   market order at 09:15:01 fills at the auction price or three ticks through it cannot be
   answered from OHLCV bars. This is the residual of `gap-risk.md` §8 item 1 that this document
   narrows but does not close.
4. **One night only.** Nothing here measures a multi-day hold. §7 explains why that is a
   different question rather than an omission.
