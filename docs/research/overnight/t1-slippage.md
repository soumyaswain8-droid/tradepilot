# Is T1 monthly reversal alive? Replacing the modelled impact charge with a measurement

**VERDICT: the cost question is UNDETERMINED. The strategy is DEAD anyway.**
We cannot measure T1 — our 1.79M order-book snapshots cover exactly 200 symbols, all above the
81.7th turnover percentile, 2.7 decades away from T1. Extrapolating the measured cost curve gives
**0.50%/month** (linear) or **2.44%/month** (quadratic on the same 200 points) against a decision
threshold of 0.525% — the two defensible fits land on opposite sides. But it does not matter:
**at every cost assumption in that whole range the second-half t-stat stays under 1.3.** The
slippage question was never the binding constraint. Out-of-sample decay is.

---

## 1. Inventory — what the order-book collection actually covers

`docs/research/orderbook/` — 15 sessions, 2026-08-07 .. 2026-08-28, 266 MB gzipped,
**200 symbols, identical every day**. This is the project's standing top-200 liquid universe.
Ladders are 5 levels a side; snapshots ~30s apart; 347,477 usable snapshots after 1-in-6
sampling and tick filtering.

Where those 200 sit in the tradeable universe (turnover from bhavcopy, EQ series,
130 sessions Dec-2025..Jun-2026, 2,598 names, **TURNOVER_LACS in Rs lakh**):

| | Rs lakh/day | universe percentile |
|---|---:|---:|
| Least liquid of the 200 | 2,559 | **81.7th** |
| 200-universe median | 19,531 | 95.6th |
| Most liquid of the 200 | 305,425 | 100th |
| **T1 median (universe quintile 1)** | **4.98** | 10th |
| T1 upper edge | 15.66 | 20th |

**The collection cannot measure T1 and no amount of care makes it.** The nearest observed point
is 514x more liquid than T1's median name. Everything below is extrapolation and is labelled as such.

(Note: T1 median turnover here is Rs4.98 L/day vs Rs10.2 L/day in `cap-segments.md` — different
window, 2026 smallcap turnover is down. Both figures are carried through below.)

## 2. What IS measurable — the empirical cost curve, 200 names

Round-trip cost = buy walking up the visible ask ladder for the full notional, sell walking down
the bids, expressed against mid. This is quoted half-spread **plus** depth walk, no model.

| turnover decile within the 200 | median turnover (Rs L) | half-spread bps | **Rs25k RT bps** | **Rs1L RT bps** |
|---|---:|---:|---:|---:|
| 1 (least liquid of the 200) | 6,626 | 1.94 | **4.48** | 5.58 |
| 2 | 9,138 | 1.73 | 4.34 | 5.62 |
| 3 | 11,487 | 1.55 | 3.67 | 4.61 |
| 4 | 14,191 | 1.43 | 3.45 | 4.23 |
| 5 | 17,813 | 1.48 | 3.46 | 4.05 |
| 6 | 20,978 | 1.15 | 2.87 | 3.70 |
| 7 | 26,276 | 1.10 | 2.65 | 3.15 |
| 8 | 33,986 | 1.12 | 2.46 | 3.27 |
| 9 | 43,564 | 0.93 | 2.16 | 2.83 |
| 10 (most liquid) | 89,611 | 0.68 | 1.74 | 2.11 |

Median across all 200: half-spread 1.33 bps, Rs25k round trip **3.08 bps (0.031%)**,
Rs1L round trip **3.80 bps (0.038%)**. Rs25k fills inside the visible 5 levels 100% of the time;
Rs1L fills 98.5%. Size barely matters up here — the whole Rs25k→Rs1L step costs 0.7 bp.

For calibration: this is the band the project trades, and the measured 0.031% round trip is
comfortably below the 0.106% toll already assumed. **Nothing in the liquid band is mis-costed.**

## 3. The extrapolation, and how far past the data it reaches

log(cost) on log(turnover), fitted on the 200:

| fit | slope | R² | T1 @ Rs4.98L | T1 @ Rs10.2L |
|---|---:|---:|---:|---:|
| linear (log-log power law) | −0.337 | 0.62 | **49.6 bps** [95% PI 29.7 – 82.9] | **39.0 bps** |
| quadratic (same 200 points) | — | 0.63 | **243.7 bps** | **147.9 bps** |

**The lever arm: the prediction point is 10.4 standard deviations below the mean of the support
and 2.71 decades below the smallest observed turnover.** A 95% prediction interval computed at
that distance is arithmetic, not evidence — it assumes the fitted form is exactly right where no
data constrains it. It is not a confidence statement and should not be read as one.

The functional-form risk swamps the statistical risk. Two fits to the *same 200 points*, both
defensible, differ by **4.9x** at T1. The quadratic is not a strawman — the curvature is real and
signed: slope is **−0.358** on the illiquid half of the 200 and **−0.280** on the liquid half.
Cost accelerates as turnover falls, within the data. Straight-lining that in logs is the
optimistic choice, not the neutral one.

Three further mechanisms all push the true number **above** the linear extrapolation:

- **Tick floor.** T1's median price is Rs42.54 (p25: Rs15.52). One NSE tick of Rs0.05 is
  **11.8 bps** at the median price and 32.2 bps at p25. The 200-name universe (median price
  Rs1,169) quotes a median spread of ~6 ticks, where a tick is 0.43 bps and therefore invisible.
  At T1 the tick is a first-order cost. A 2-tick spread alone is 24 bps; 3 ticks is 35 bps.
- **The ladder runs out.** Median visible 5-level depth in the 200 is Rs691,434 — Rs25k is 3.6%
  of it. Depth scales with turnover at elasticity 0.75, so at T1 the visible book is a few
  thousand rupees. **A Rs25,000 order at T1 is larger than the entire displayed ladder**, which
  means our measurement *technique* — walking a visible book — does not even transfer. Any T1
  number requires assumptions about replenishment and hidden liquidity that the liquid band
  never forced us to make.
- **Order vs print size.** T1's median print is Rs3,112 (138 trades/day). Rs25,000 is **8 prints**
  and **5.0% of the name's entire daily turnover**. In the 200, Rs25k is ~0.6 of a single print.

**Honest range for T1 Rs25k round-trip cost: 0.25% to 2.4%, centred somewhere near 0.5–1.0%.**
Anyone quoting a point estimate here is quoting a functional form.

## 4. The deciding comparison

The `cap-segments.md` t-stats are exactly linear in the impact charge (verified: its own three
rows reproduce to ±0.02 under `t = 3.68 × (3.13 − fee − impact) / 2.84`). So the threshold is
solvable rather than guessable:

> **t = 3.00 requires T1 round-trip impact ≤ 0.525%/month.** (The doc's "~0.6%" was right.)

| cost estimate | impact %/mo | full-sample t | **second-half t** |
|---|---:|---:|---:|
| linear extrapolation @ Rs10.2L | 0.39 | 3.18 | 1.14 |
| linear extrapolation @ Rs4.98L | **0.50** | **3.04** | **1.05** |
| linear 95% PI, optimistic end | 0.30 | 3.30 | 1.23 |
| linear 95% PI, pessimistic end | 0.83 | 2.61 | 0.74 |
| `cap-segments.md` modelled charge | 1.14 | 2.18 | 0.46 |
| quadratic extrapolation @ Rs4.98L | 2.44 | 0.52 | −0.72 |

**On the cost question alone: undetermined.** The point estimate (0.50%) sits 0.025 percentage
points on the *good* side of a 0.525% threshold, inside a band that spans it five times over.
There is no honest way to call that.

**But the answer does not depend on resolving it.** The right-hand column is the one that decides.
`cap-segments.md` split the sample in half in advance; H1 t was 2.55 and H2 t was 0.46 with impact
charged. Re-run that split across the entire plausible cost range — from the most optimistic
extrapolation this data supports to the most pessimistic — and **H2 t never exceeds 1.23**. The
edge decayed out of sample, and cheaper execution does not un-decay it. Halving the impact charge
buys ~0.5 t-units in the second half, from "nothing" to "nothing".

The modelled `sigma*sqrt(participation)` charge was probably ~2x too harsh at Rs25k. That was a
real soft spot and it is worth knowing it was soft. It was not, however, load-bearing.

## 5. The independent proxy — and why it fails as a cross-check

Corwin-Schultz (2012) high-low spread estimator, computed from bhavcopy OHLC for all 2,598 names,
plus Amihud and per-print size. Two independent estimates agreeing would have been worth a lot.
They do not agree, and the proxy is the one at fault.

| band | turnover Rs L | CS spread % | Amihud | median print Rs | daily range % |
|---|---:|---:|---:|---:|---:|
| T1 | 4.98 | 1.57 | 23.95 | 3,112 | 4.84 |
| T2 | 41.49 | 1.08 | 3.11 | 5,469 | — |
| T3 | 233.47 | 0.80 | 0.53 | 9,470 | — |
| T4 | 916.40 | 0.68 | 0.14 | 12,074 | — |
| T5 | 7,191.74 | 0.46 | 0.02 | 25,944 | — |

**Where we can check it, CS is wrong by 13x.** In the 200-name band CS says 0.403% round trip;
the book says 0.031%. And its cross-sectional correlation with measured cost inside the 200 is
only 0.34 (R² = 0.12) — it barely ranks names correctly even where it is calibrated.

The bias is the known one: CS reads intraday volatility as spread. The tell is in the data —
CS/range is 0.16 in the liquid 200 and 0.325 at T1, and T1's daily range (4.84%) is nearly double
the liquid band's (2.56%). **The bias is larger exactly where we need the estimate**, so:

- Taking CS at face value (1.57%) is an **upper bound**, not an estimate.
- Applying the measured 13x correction gives 12 bps, which is **below the one-tick floor of
  11.8 bps at T1's median price** — i.e. arithmetically impossible. The correction is not constant.
- Regressing measured cost on CS and extrapolating gives 3.7 bps — also below the tick floor,
  also impossible.

So the proxy does not corroborate anything. Its one genuine contribution is the *directly observed*
T1 quantities that need no model at all: **median print Rs3,112, 138 trades/day, Rs25k = 8 prints
= 5.0% of daily turnover, median price Rs42.54.** Those numbers are measured, they are not
flattering, and they are the most reliable thing in this document about T1.

The `avg_trade_rs` route was tried as a shorter lever (Rs25k is 8 prints at T1 vs 1 print in the
200 — only 0.9 decades of extrapolation instead of 2.7). It predicts 8.4 bps, which is again below
the tick floor, on R² = 0.21. A short lever arm on a weak relationship is not an improvement.

## 6. What would actually settle it

Only direct collection. Specification:

| | |
|---|---|
| **Symbols** | 40 names sampled across T1 (turnover Rs2–16 L/day), stratified by price so the Rs15/Rs42/Rs123 price quartiles are each represented — the tick floor makes price a first-order cost driver at T1 and a turnover-only sample will hide it |
| **Sessions** | 20 (four calendar weeks). The 200-name medians were stable by ~10 sessions; T1 quotes are sparser, so double it |
| **Cadence** | 30s, as now. T1 trades ~1 print per 2.7 min, so 30s does not undersample |
| **Fields** | current schema **plus tick prints** — the 5-level ladder is smaller than a Rs25k order at T1, so ladder-walking alone cannot produce an answer. The measurement that does not depend on depth is effective spread, `2·\|P_trade − mid\|`, which needs only LTP against the prevailing quote |
| **Volume** | ~600k snapshots ≈ **90 MB gzipped** at the observed 150 bytes/snapshot |
| **Then** | re-run this analysis with T1 inside the support instead of 2.7 decades outside it |

**Recommendation: do not collect it.** It answers a question whose answer changes nothing —
section 4's right-hand column is insensitive to the entire plausible cost range. Collect it only
if the T1 reversal is independently revived on the decay axis (two more years of data, per
`cap-segments.md`'s own second caveat). The cost measurement is the second question, not the first.

## 7. Caveats

- Order-book window is 15 sessions in Aug-2026 — one market regime, no event days isolated.
  Costs here are medians; the tail matters for a strategy that rebalances into losers.
- Cost is measured against contemporaneous mid, i.e. it is a *quoted* cost. It excludes delay,
  adverse selection and the impact of one's own order on subsequent quotes — all of which are
  larger at T1 than in the 200, again biasing the extrapolation optimistic.
- Turnover for the 200 is Dec-2025..Jun-2026; the book snapshots are Aug-2026. Liquidity ranks
  are persistent, but the two are not contemporaneous.
- 2 of 130 bhavcopy files skipped (NSE changed the column schema on 15/16-Jun-2026).
- CS is the unadjusted 2-day estimator; the overnight-return-adjusted variant was not used.
  It would reduce but not close a 13x gap.
- The t-stat mapping in section 4 assumes cost affects the mean and not the variance of monthly
  returns. That is how `cap-segments.md` computed its own three rows, so the comparison is
  internally consistent, but at high impact levels it is optimistic.

---

*Data: `docs/research/orderbook/` (15 sessions × 200 syms, 347,477 sampled snapshots),
`quant/data/bhavcopy/` (130 sessions, 2,598 EQ names). Scratch artifacts deleted.
Author: Soumya Swain. 2026-08-28.*
