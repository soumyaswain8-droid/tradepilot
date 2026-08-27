# Seasonality & Calendar Effects — agent findings

**VERDICT: not viable.** One large, genuinely persistent effect found (Monday cross-sectional
momentum). It fails on cost arithmetic and on execution law, not on statistics.

## THE NUMBER

Monday winner-minus-loser decile spread, market-neutral, liquid-500, `sf_ret` 2021-06..2026-06:

| | gross | t | n | net after cost |
|:--|--:|--:|--:|--:|
| Full sample | +0.396%/Mon | 5.39 | 243 | **-0.084%** |
| Train (to 2023-12) | +0.497% | 4.91 | 122 | +0.017% |
| Holdout (2023-12+) | +0.294% | 2.77 | 121 | -0.186% |

Positive every one of 6 calendar years. Gross equity 2.57x, max DD -10.1%.
Net of 0.48% (two delivery legs): equity **0.802x**, max DD **-31.7%**.

Cost: signal is Friday's close-to-close, payoff is Monday's close-to-close → you must hold
Friday close to Monday close. That is CNC delivery on both legs = 2 x 0.24% = 0.48%, plus
Rs18.80 per scrip per sell (~100 scrips = another ~0.19% on a Rs1L book). Gross 0.396% < 0.48%.

**And the short leg does not exist.** Overnight short delivery is not permitted for retail in
India. Even the arithmetic-passing version is unexecutable.

### Where the Monday effect actually lives (bhavcopy, lagged-20d-turnover top-500, n=246)

| segment | gross | t | holdout | cost | net |
|:--|--:|--:|--:|--:|--:|
| Fri close → Mon close (delivery) | +0.620% | 6.79 | +0.434 (t=3.58) | 0.480% | +0.140% |
| Fri close → Mon **open** (gap) | +0.430% | 10.22 | +0.401 (t=5.40) | 0.480% | -0.050% |
| Mon **open** → Mon close (MIS) | +0.190% | 2.29 | **+0.032 (t=0.32)** | 0.214% | -0.024% |

70% of the effect is an overnight gap — the one segment that cannot be shorted. The intraday
segment, which *is* MIS-shortable at 0.107%/leg, collapses to t=0.32 out of sample and is
below cost anyway. Net drawdown -27% to -32% in every variant.

(An earlier same-day-turnover ranking gave +1.208%/t=10.25. That was lookahead — high turnover
today selects big movers today. Discard it; the lagged numbers above are the honest ones.)

## WHAT ELSE I TESTED

- **Day of week (levels + vs-rest, EW liquid-500).** Wed +0.248% t=3.44 full — but train t=0.56,
  holdout t=3.28, and the yearly means climb monotonically 2021→2026 (+0.13% → +0.76%). That is a
  trend, not a weekday. Mon -0.193% t=-1.99, Fri -0.156% t=-1.85. None clear Bonferroni.
- **Turn of month.** Looks like the headline: TOM(last1+first1) +0.395% excess, t=4.08.
  It is an in-sample ghost — train t=5.77, **holdout t=1.21**. Same decay at every window
  (last2+first2: train 5.47 → holdout 0.19; last3+first3: 4.06 → 1.18). As a tradable long-only
  timing rule TOM3 nets ~15%/yr vs 15.0%/yr for simply buying and holding the same universe with
  zero trades. No edge, more risk of ruin.
- **Expiry.** Monthly expiry day -0.229% t=-1.56; expiry week t=0.01; weekly expiry day
  (Thursday pre-Sep-2025, Tuesday after) t=1.10; day-after-expiry t=-0.09. Nothing.
- **Month of year.** Best is April +0.345% t=2.57, worst Feb -0.311% t=-2.07. Twelve slices,
  both well under the correction threshold. No "Sell in May" here.
- **Holiday gaps.** Day before a >=4-day break t=1.54 (n=28); day after t=1.86 (n=28, and it is
  train t=0.07 / holdout t=2.38 — noise). Samples are far too small to act on.
- **Intraday time of day** (`panel_5min` 200 syms x 42 sess; `prototype/intraday` 201 syms x 79
  sess). Largest 5-min bucket mean is +0.035% (14:50). Cost is 0.107%. Every bucket is 3-10x
  too small. The apparent t-stats (up to 22) are fake — n counts symbol-bars that are almost
  perfectly cross-correlated within a bar; effective n is the session count (~79), which divides
  those t's by ~10. First 30 min are twice as volatile as midday (0.243% vs 0.111% mean |move|,
  last 30 min 0.144%) — that is dispersion to pay for, not to earn.
- **Overnight vs intraday split** (per symbol-day): overnight +0.0133% (t=1.05),
  intraday -0.0466% (t=-2.66). The known "all the drift is overnight" pattern is present in sign
  but 8x below the 0.107% intraday toll and unshortable overnight.
- **Cross-section by slice.** 1-day reversal is flat overall (t=-1.78) and by TOM. It is *entirely*
  a Monday phenomenon — see above; Tue-Fri all |t| < 1. Cross-sectional dispersion is essentially
  identical across weekdays (2.14%-2.30%), so no day offers cheaper alpha per unit risk.

## MULTIPLE TESTING

**~210 hypotheses** (40 daily calendar slices, 7 cross-sectional slices, ~150 intraday 5-min
buckets across two datasets, 12 Monday decompositions, 5 TOM tradability variants).
Bonferroni threshold at alpha=0.05, m=210: **|t| >= 3.9**.

Only two things exceed it: TOM in-sample (which then dies in holdout, exactly the failure mode
the correction exists to catch) and the Monday spread (t=5.39, which survives holdout at t=2.77
and is real — it just loses to the cost line).

## WHY IT FAILED — the arithmetic

Monday cross-sectional momentum is the single strongest, most persistent pattern in this lane:
t=5.39, holdout t=2.77, positive in all 6 years, -10% gross drawdown. It fails because the
payoff window straddles a weekend. That forces CNC delivery — 0.48% round trip for two legs
against 0.396% of gross — and Indian retail cannot hold a short leg overnight at all. Shifting
to the MIS-tradable Monday open-to-close window drops the cost to 0.214% but drops the signal to
+0.032% out of sample (t=0.32), because 70% of the move has already happened in the opening gap
before you can trade it.

The date being known in advance removes forecasting risk. It does not remove the toll.
