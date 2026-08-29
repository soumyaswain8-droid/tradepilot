# Five Years, Every NSE Winner — Overnight Scan

**Run:** 2026-08-28, 00:58 → 08:30 IST
**Universe:** survivorship-free panel — 1,232 sessions × 3,046 symbols, including the 417 that stopped trading
**Question asked:** scan every stock that went up over five years, at least the top 50 of each day. Find when we should have entered and exited. Find what the winners had in common.

---

## The answer in one line

**The precursors predict magnitude, not direction.** Six independent lanes, six different horizons, one structure: you can forecast *which stocks will move* with real and repeatable accuracy. You cannot forecast *which way*.

That is not six failures. It is one property of this market, measured six ways.

---

## What "when should we have entered" actually returns

The question has a trivial answer — at the low, out at the high — and it is worth nothing, because neither is knowable at the time. It was computed anyway, as a ceiling, and then paired with the number that is actually reachable.

| | Return |
|:--|--:|
| Perfect hindsight, low → high | **+4.99%** |
| Enter once the stock is already +2% on the day | **−0.118%** (before costs) |
| Same entry, but only on stocks that *finished* top-decile | **+1.55%** |

The middle row is what a live system can reach. It is negative. The bottom row is what a winner-filtered backtest reports — and the **1.67 percentage point gap between them is pure hindsight**. That gap is the exact mechanism that made April look profitable.

**Winners front-load.** 31% of a winner's entire daily gain lands in the first 15 minutes, 41% by 10:00, 95% by 15:00. The long flat afternoon looks participable and is not.

---

## What the winners had in common

Measured on prior-close data only, no look-ahead. Tomorrow's top-50 winner looks like this today:

- **small** — turnover is *negatively* loaded; winners are systematically less liquid
- **volatile** — `vol20` dominates every other feature (+0.605 sd, correct sign on 99.3% of days)
- **already moving up**
- **turnover spiking above its own 20-day norm**

Every feature clears Bonferroni on 1.94M stock-days. The folklore is correct.

**A model built on these picks tomorrow's top-50 at 4.87× the base rate** (10.92% vs 2.24%), AUC 0.695, and the lift is *higher* out-of-sample than in. This is a genuinely strong, genuinely real forecast.

### And it pays nothing

The same model predicts the top-50 **losers at 6.28×** — better than it predicts winners. The predicted basket's median return is **−0.50%/day**, P(up) = 0.443.

It is a volatility detector. It correctly finds names with a wide conditional distribution tomorrow, and **both tails widen together**. You cannot extract a first moment from a second-moment signal.

Net of the 0.107% intraday toll: **−0.0224%/day, t = −0.26**. Shorting the same basket also loses (−0.1916%/day, t = −2.23) — the fat right tail bleeds the short.

---

## Lane by lane

### 1. Precursors — are winners forecastable?
**Yes, and it is worthless.** Details above. Gross +0.0846%/day at t = 0.98 — not significant even before costs.

Small-caps are *more* forecastable (low-turnover tercile 5.41× lift vs 4.31× high) and the low tercile is the only positive net number (+0.1511%/day). It dies three ways: it decays within the holdout (t 2.08 → 1.38), it fails Bonferroni at ~20 variants, and it is entirely the untradeable bottom decile — **a turnover floor of just 10 units flips gross to −0.0244%**.

### 2. Intraday timing — when does the move happen?
**Too early to catch.** Entering at +2% returns −0.118% to the close market-neutral (n = 5,802, t = −4.78); after the toll, −0.225%, t = −19.8. Negative at every threshold (+1/+2/+3/+5%) and every holding period. Fading it instead nets +1.3 bps, t = 1.14 — inside slippage.

All 2,775 fixed-clock X→Y rules tested: best in-sample t = 0.90 against a ~4.0 Bonferroni bar — *worse than the ~3.5 you would expect from the best of 2,775 pure-noise draws*. All top 5 flip negative out of sample.

### 3. Sustained runners — the multi-week moves
**462 sixty-day doublings in five years** across 384 symbols (~92/yr) in a genuinely tradeable universe; 929 at 120 days; **zero 20-day triples**. Regime-bound — 2023 produced 3× more than 2025 — and concentrated ~2× in the smallest liquidity tercile.

Precursors are real (vol60 +0.56σ, ret252 +0.47σ, extended above the 200-day MA, near 52-week highs). They do not survive the split:

| | Net excess (60d) | t |
|:--|--:|--:|
| Train best rule *(grid-searched)* | +0.20% | +2.67 |
| **Holdout, same rule** | **−2.82%** | **−16.09** |

**The decisive number:** the screen leaves the doubling rate untouched — 0.21% vs a 0.24% base rate, *no lift* — while tripling the halving rate to 2.29%. Doublers-per-halving falls from **0.31 unconditionally to 0.09 screened**: one doubler for every eleven halvings.

Chasing a visible run is worse: buying after +100% in 60 days returns −7.58% market-neutral, t = −6.10, at 10:1 halving-to-doubling odds.

**Cost is irrelevant here** — 0.59% on a 60-day hold. Zero the toll entirely and it still loses 2.2–4.5%. This is absence of information, not a fee problem.

Monte Carlo, 5 names, 200k paths: **53.4% chance of ending down**, median −0.89%, P(>+50%) = 0.02%. Five *random* stocks do better (51.9% down).

### 4. Cap segments — were we fishing in the wrong pond?
**Yes — and the right pond cannot be fished.** Cross-sectional IC of prior-day vs next-day return: **−0.056** in the least-liquid quintile vs **−0.013** in the most-liquid. Same sign, **4.3× the magnitude**. The project's long-quoted −0.017 lands exactly on T5 — we had been measuring the weakest corner of the universe. The gradient holds in all three sub-periods, so it is structural, not the microcap bull.

Best gross daily edge anywhere: **+17.8 bps/day**. Delivery STT round trip: **20 bps**. It loses before spread, DP fee, brokerage or impact.

The near-miss: T1 monthly reversal, market-neutral, delisted marked to −100%, +3.13%/month gross at t = 3.68 on fees alone. Then impact at ₹25,000/position → t = 2.18; second half → t = 0.46; at ₹1,00,000 → t = 0.90; filtered to names absorbing ₹5 lakh/day → gross 3.13% → 2.20%. **The edge lives in the untradeable tail of the untradeable band.**

Circuit-locks are *not* the binding constraint (<0.02% of days). **Impact is** — ₹25,000 is 2.45% of a median T1 name's entire daily turnover.

> **Touches other work:** `mom_12_1` *inverts* down-cap — −33.6%/yr (t = −3.27) in T1, ~0 in T5. The 26% gross long-only momentum figure on our books is consistent with **being beta**.

### 5. Pre-open selection — the thread that looked live
**The gap is not the obstacle.** This corrects an assumption carried into the lane. Across 599,661 symbol-days:

| Cohort | Gap (unreachable) | 09:15 open → close (reachable) | Gap share |
|:--|--:|--:|--:|
| Top decile | +0.664% | **+3.758%** | 15.0% |
| Top 1% | +1.323% | **+8.679%** | 13.1% |
| All names | +0.212% | −0.153% | — |

**85% of a winner's day is reachable from the open.** The "31% in the first fifteen minutes" was already measured *from the open*, so it sits inside the reachable portion. The barrier is purely forecasting.

**And the forecast fails.** 96 variants, entry at the actual 09:15 open, market-neutral, net of 0.107%: **not one is net-positive.** Best is −0.032%/day, t = −1.15. Best gross of any variant: **+0.075% against the 0.107% toll — short by 30%.** The holdout was never touched, because nothing qualified to be taken there.

The signals are real and split-stable — low-volatility, low-prior-gap, prior-day-loser, high-delivery names outperform intraday, and delivery-% is the only signal that *strengthens* out of sample (IC +0.033 → +0.059). They are simply about **half the size** they need to be.

### 6. Winner anatomy — does any setup break the symmetry?
**No.** Every structural type sits at the unconditional up/down ratio:

| Type | n | P(win) lift | P(>+5%) | P(<−5%) | ratio | mean MN | t |
|:--|--:|--:|--:|--:|--:|--:|--:|
| BREAKOUT | 36,760 | 1.46× | 3.76% | 2.36% | 1.59 | +0.080% | 1.44 |
| REVERSAL | 22,109 | 1.37× | 7.89% | 5.24% | 1.51 | −0.152% | −3.10 |
| CONTINUATION | 19,851 | 1.97× | 6.14% | 4.27% | 1.44 | −0.052% | −0.79 |
| FROM-NOWHERE | 89,552 | 0.43× | 1.22% | 0.62% | 1.97 | −0.025% | −0.86 |
| **ALL** | 488,828 | 1.00× | 3.61% | 2.24% | **1.61** | 0 | — |

**No setup bends the 1.61.** The types sort winner-probability well (CONTINUATION 1.97×) and sort loser-probability by the same amount. The fat right tail is a property of Indian equity returns generally — right-skewed tails around a *negative* median — not of any identifiable structure.

REVERSAL is the instructive case: the only type with genuine positive skew, 1.5× more big-up than big-down days, and the only result significant in **both** periods with the same sign — **negative** (h=1: train −0.208% t=−4.18, holdout −0.152% t=−3.10). A real fat right tail that reliably loses money: a lottery-preference premium, paid by the buyer.

BREAKOUT is the only positive and fails persistence — t = 3.39 in the holdout, t = 0.35 in training. Zero signal until 2025. A regime, not an edge, and plainly the `mom_12_1` factor already on our books.

### 7. Sector clustering — do winners arrive in themed clumps?
**They do, enormously — and it forecasts nothing.** This was the one mechanism left that was *directional* rather than price-derived, so it mattered.

**Clumping is real and large.** Top-50 daily winners have a Herfindahl of 0.1845 against a Monte-Carlo null of 0.1480 — **t = 40.0, p = 2e-208**, n = 982 days. The leading cluster holds **27.5% of the top 50** against an 8.3% random baseline: roughly 13–14 of the 50 biggest winners on any given day share one theme. Actual beats null on 93.3% of days, and it is slightly *stronger* in 2024–2026.

**Persistence is absent.** **0 of 16 pre-registered variants clear the Bonferroni bar of |t| ≥ 2.96 even gross** (best 2.86, on the most-overlapping variant, where the Newey-West correction is least trustworthy). The best-on-train pick replicates at holdout **t = 0.14**.

The arithmetic that ends it: at hold = 1, gross is 0.18% (train) / 0.21% (holdout) against a **0.214% cost floor**. The effect and the cost line are the same number.

> **The trap this lane sets:** a t-statistic of 40 on the clumping test could easily be written up as "sector rotation confirmed" and read as a green light. It is not one. **Theme membership is contemporaneous, not predictive** — the clump is visible only once the day has happened.

**And no regime saved it.** There is no era where this worked; the weak gross drift is marginally *larger* in 2024–2026, it simply never cleared costs in either half. That is a cleaner negative than a decayed edge — there is nothing to wait for.

### 8. The thirty biggest single-day winners — the ceiling is legislated
Full tables in `biggest-winners.md`, computed from bhavcopy with the prev-close reconciliation above.

**The 20% circuit is the whole story.** Twenty of the top thirty sit at *exactly* +20.0%. In five years only **10 stock-days in the entire market cleared +20%**, and every one is an F&O name with no price band. The largest clean single-day move in the panel is **+46.9%** (MASKINVEST).

**There is no +100% single-day tail in tradeable Indian equity. The exchange truncates it.** Every strategy that hopes to catch one is hoping for something that happens ten times per 2.6 million stock-days, in names we cannot access.

**And big up-days give back.** Median forward return for the top 30: **−1.0% at 5 days, −2.2% at 20**. For the tradeable subset it is worse — **−3.5% / −5.2%**, with only 7 of 15 positive at 5 days.

**They are not breakouts.** Median prior-day `pos52` is 0.45 (0.35 for tradeable names); only 3 of 15 were anywhere near a 52-week high.

> **This overturns the folk model, and it is the surprise of the night.** The biggest single-day winners are **large caps on news** — ZEEL/Sony, IDEA's relief package, the Adani–Hindenburg names — not illiquid shells. Fourteen of the top thirty clear ₹1 crore turnover. The shells that *appeared* in early passes were mostly **data errors, not real moves**. Meanwhile the only positive forward drift sits in the illiquid half (+1.6% / +2.8%) — precisely where capital cannot go.

---

## The chart pack — verify it yourself

`CHART-EVIDENCE.md` and 12 annotated candlestick charts in `charts/`, drawn from real Kite daily bars: real candles, volume panel, 20/50-day MAs, optimal entry and exit marked with the % gain.

**What they establish:** all 12 optimal entries were **below both moving averages, in a 22–60% drawdown**. Near-tautological — the run low *is* the point of maximum weakness — but it kills the framing that our entries need tuning. No trend system can aim at that bar, because at that bar every trend indicator says sell.

The reachable version: **first close back above the 50-day MA printed 35.9% above the low, 8.3 sessions late, with +106.5% still ahead** of a +169.7% perfect move — about 63% of the run, on a signal visible in real time.

Only 2 of 12 lows carried a real volume signal. **Five of twelve came on below-average volume** — the capitulation flush we screen for mostly is not there.

> **The pack's own caveat, stated in it:** these twelve were selected by searching for the biggest gains. They carry **zero information about hit rate**. The one unbiased fact inside the sample is that holding 60 sessions past the peak gave back 21% on average, 11 of 12 lower.

---

## Two things that need fixing regardless of strategy

**1. `sf_ret` is winsorized at ±50%** — 47 stock-days sit at exactly +0.500 and 316 at exactly −0.500. Any "largest winners" ranking taken off it is a 47-way tie at the clip. Rankings must be computed from bhavcopy `CLOSE/PREV_CLOSE` instead. *(Impact on the lanes is small — the 20% circuit means the clip almost never binds on a real daily return — but it is silent when it does.)*

**1b. NSE `PREV_CLOSE` is corrupt on relisting days.** A first pass returned NIRLON at **+38,456%** (prev close 1.40 against a 540.00 open), plus a dozen post-suspension call auctions near +1,000%. The fix — require the official prev close to reconcile with the prior traded close within 2% *and* the stock to have traded the prior session — also removes unadjusted splits and bonuses in the same rule. Cost: 14,900 of 2,624,099 stock-days (0.57%).

> **RETRACTED:** an earlier lane reported that `sf_ret` disagreed with Kite in the illiquid tail (ASHIMASYN +101.6% vs +56.7%; CCHHL +123.2% vs +73.2%) and inferred a corporate-action artifact. **This does not reproduce.** `sf_ret`'s maximum for ASHIMASYN is +19.46% and for CCHHL is +20.00% — neither ever exceeds the price band, and bhavcopy agrees to the decimal. Neither the claimed panel figures nor the claimed Kite "actuals" are consistent with 20%-banded stocks. The artifact claim is unsupported on this evidence and nothing should be built on it without re-deriving it.

**2. A liquidity screen needs a trade-density floor, not just a turnover floor.** With a loose filter the runner screen appeared to *double* its holdout hit rate (0.24% → 0.46%). All of it was stale prints in untradeable shells, and it vanished under a real tradability test.

**3. Overlapping-window t-statistics are inflated 2–3.5× and this is not confined to one lane.**
Raw BREAKOUT at h=21 was **t = 5.79**; corrected it is **1.76**. Any multi-week t-statistic in
this codebase computed on overlapping windows without a HAC correction should be assumed
inflated by that factor until checked.

> **CORRECTED 2026-08-29 — the original wording here was wrong twice.** It said "the immediate
> casualty is a number already on our books: `mom_12_1` corrects from a naive 5.72 to NW 1.49."
> The audit in `hac-audit.md` establishes that **`mom_12_1` is two different measurements** and
> they were conflated:
>
> - **What is on our books** is `validate_mom121.py`: a monthly rebalance, month *t* to month
>   *t+1*, each month used once. It is **genuinely non-overlapping and needs no correction** —
>   applying NW at L=1/3/6 moves it 0.28 → 0.31 → 0.34, nothing past the third decimal. It was
>   already dead, of having no excess over buy-and-hold-everything, not of overlap.
> - **The 5.72 was never ours.** It is a daily Fama-MacBeth regression slope created on 08-28
>   as a control variable inside the breakout lane.
>
> And the 1.49 is itself misleading: it is holdout-only, 323 sessions. Extended to the full
> sample the same slope reads **naive 10.97 → NW 2.92**, with 21 of 21 disjoint subsamples
> clearing 1.96. **The momentum slope survives HAC comfortably** — 1.49 is what a short window
> can resolve, not a verdict.
>
> None of this rescues BREAKOUT: its residual after controlling for momentum is still NW
> t ≤ 1.46.

**4. Options STT is 0.15%, not 0.1%.** Budget 2026 raised it from 0.10% effective 1 April 2026,
alongside the futures hike to 0.05%. Verified live against zerodha.com/charges, not recalled.
This is the third time a stated STT rate in this project has been wrong and the second time it
was wrong in the direction that flattered a premium-selling strategy — **any options costing
should be re-derived from the broker's published sheet rather than from memory.**

**5. Units.** `sf_turn.parquet` is denominated in **₹ lakh**, not rupees. One agent lost an entire run to this, and — worse — a threshold slightly too low would have produced plausible numbers off a distorted universe instead of an obvious empty one. Any script touching it should assert a minimum universe size before computing a statistic.

---

## Run integrity

The root volume hit **0 bytes at ~01:20** — caused by this run's own artifacts, a 183 MB panel plus a subagent's intermediate pickle. Because every write path needs a temp file, *nothing on the machine could write* for the next six hours, including the cleanup command. Six hours of scheduled jobs failed silently.

Three lanes lost their write step and reported findings in-message instead; those are transcribed here and marked. Sector clustering produced no numbers at all and was **re-run cleanly at 08:19** — its result above is from the completed run, not the failed one.

---

## What this means for the plan

The five-year scan did not find a way to trade the winners. What it did find is why every previous lane died the same way, and that is worth more than another rule:

- **Direction is the missing ingredient, not accuracy.** We have been improving a magnitude forecast and expecting a direction payoff. The precursor model is excellent at its actual job and that job does not pay.
- **The last non-price mechanism is now tested.** Sector rotation was the remaining hope — directional, slow-moving, flow-driven. The themes are real and enormous; they are simply not *predictive*, and the effect and the cost line are the same number.
- **Everything price-derived is now tested at scale** and can stop consuming effort. Five years, 3,046 symbols, ~2.35M observations, seven lanes, all pre-registered and date-split.

**Every open thread was closed on 2026-08-28.** All three are resolved below, and all three
resolved negative. There is no remaining untested idea from the original search — which is
itself the result, and a cleaner place to stand than a list of maybes:

1. ~~Delta-hedged short straddle.~~ **RESOLVED 2026-08-28 — fail, thread closed.**
   See `delta-hedged-straddle.md`. 530 sessions.

   **The mechanism worked exactly as theorised and it still was not enough.** Years-to-t=2 fell
   from the condor's **637 to 6.4** — a ~100× variance collapse from precisely the predicted
   source. It then missed all six pre-registered bars: Sharpe 0.79 (bar 1.0), t=1.13 (bar 2.0),
   6.4 years (bar 4.0), max drawdown **−42.5%** (bar 15%), worst week **−18.7%** (bar 10%).

   Three things worth keeping:
   - **At one lot, hedging is worse than not hedging** (Sharpe 0.54 vs 0.61). The 75-unit NIFTY
     futures lot makes the hedge bang-bang between 0 and 75; rounding noise swamps the benefit.
     It only begins working near 5 lots — about **₹10 lakh of margin**, which disqualifies it for
     this account whatever the Sharpe says.
   - **The tail is a ruin path.** Underwater 85 of 107 weeks; the worst 5 weeks sum to −77% of
     capital. A daily-close hedge gives *zero* gap protection: a 5% overnight gap costs −34.6%
     in one morning and erases 54 weeks of edge in a single print.
   - **The hedge turns over ₹1.4M/week to collect ₹22.6k of premium** — 64×. That ratio is why
     intraday hedging is unlikely to rescue it.

   Intraday hedging was **not testable and was not faked**: bhavcopy is EOD-only and Kite drops
   expired instruments, so settled weeklies have no instrument token. It would need
   forward-collected minute bars or a paid feed — not worth buying on this evidence.
2. ~~Measured T1 slippage.~~ **RESOLVED 2026-08-28 — cost undetermined, strategy dead anyway.**
   See `t1-slippage.md`.

   The order book cannot answer it: 15 sessions × exactly the same 200 liquid symbols, whose
   *least* liquid member sits at the 81.7th turnover percentile. **The nearest observed point
   is 514× more liquid than T1's median.** Extrapolating gives 49.6 bps (log-log) or 243.7 bps
   (quadratic) — a **4.9× spread**, 2.71 decades past the data, and the curvature is signed such
   that straight-lining is the *optimistic* choice rather than the neutral one.

   The threshold solves at ≤0.525%/month for t=3.00 and the point estimate is 0.50% → t=3.04.
   It lands 0.025pp on the good side of a line its own uncertainty band crosses five times over.
   Genuinely undetermined.

   **And it does not matter.** Sweeping the entire plausible cost range through the
   pre-registered split, second-half **t never exceeds 1.23** (0.30% → 1.23; 0.50% → 1.05;
   1.14% → 0.46). Cheaper execution buys ~0.5 t-units in a half that needs ~2.5. The modelled
   impact charge was probably ~2× too harsh — a real soft spot, correctly flagged — but it was
   never load-bearing. **Out-of-sample decay killed this, not costs.**

   Two things worth keeping. The Corwin-Schultz spread proxy is wrong by **13×** where it can be
   checked (0.403% vs a measured 0.031%), and its bias is volatility-driven, so it is worst
   exactly where we would want it — both calibrated corrections produce answers below the tick
   floor, which is arithmetically impossible and is how we know to discard it. And model-free:
   T1's median print is **₹3,112**, so a ₹25,000 order is **8 prints, 5.0% of the name's entire
   daily turnover, and larger than the whole visible 5-level ladder**.
3. ~~Newey-West on BREAKOUT.~~ **RESOLVED 2026-08-28 — dead.** See `breakout-hac.md`.
   Corrected t = **1.47 / 1.40 / 0.99** at h=5/10/21 against a 3.0–3.3 bar; it fails even
   the 1.96 an isolated test would demand. Inflation was 1.81× / 2.41× / **3.44×**. The h=1
   control barely moved (1.44 → 1.48) as it must, and 36 disjoint non-overlapping subsamples
   agree (mean t 1.21/1.14/0.80, not one reaching 2).

   And the "absent in train, present in holdout" framing was too kind: splitting the holdout
   at 2025-09-29 puts **H1 at +0.014%, t=0.08** — indistinguishable from training. The entire
   effect lives in the **last 172 sessions**. 808 flat sessions, then nine warm months.

   Where it is tradeable it is absent: high-turnover names give NW t=0.43, falling to 0.16
   with momentum controlled. It survives only in ₹0.9–16 crore/day names where costs would
   eat it several times over.

Everything else on the price-signal side is closed.

> **A note on what the circuit means for the plan.** Lane 8 changes the shape of the target. We have been searching for a way to catch large moves; the exchange caps a tradeable single-day move at 20%, and the ten exceptions in five years are all F&O names. Combined with lane 3 — 462 sixty-day doublings, none forecastable — the realistic ceiling on any daily-horizon equity strategy here is far lower than the hunt has been implicitly assuming. That is a constraint worth designing around rather than testing against again.

`─────────`
*Generated 2026-08-28. Author: Soumya Swain <soumya@suryaai.co.in>. All figures net of the measured 0.107% intraday / 0.24% delivery toll unless stated. Every lane used a date-split fixed before evaluation, and every t-statistic on stock-day data is date-clustered.*
