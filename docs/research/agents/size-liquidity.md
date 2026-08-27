# Lane: SIZE & LIQUIDITY — small-cap and illiquidity premia

**VERDICT: NOT VIABLE.** The premium is real gross and is *exactly* the thing we cannot
harvest. The signal and the trading cost are the same variable.

**THE NUMBER:** smallest-turnover quintile, market(EW)-neutral, monthly rebalance:
**gross +0.844%/mo (t=3.32, n=56 months)** → **net −0.194%/mo at Rs25,000 (−2.3%/yr)**
and **net −0.886%/mo at Rs1,00,000 (−10.6%/yr)**. Out-of-sample half: gross +0.400%/mo,
t=1.11 → net −7.6%/yr. Q1−Q5 spread gross 1.303%/mo, t=2.64, maxDD −14.2%.

## What I tested
sf_ret + sf_turn (survivorship-free, 1232×3046). Size proxy = **60-day median rupee
turnover** (no market cap on disk; turnover = size × velocity, so a hot microcap
misclassifies as mid — this proxy is directionally right, not clean). Illiquidity =
Amihud, 60d mean of |ret| / Rs-crore turnover. Monthly quintile sorts, forward 21/63/252d
returns, cross-sectionally demeaned. Date split at the median month; nothing tuned on the holdout.

**The two sorts are one sort:** Spearman ρ(size proxy, Amihud) = **−0.978**. Illiquidity
quintiles are the size table mirrored (Q5-illiquid +0.950%/mo, t=3.32). One finding, not two.

## Execution reality (this is the whole story)

| Q (size) | median ADV | Rs25k = %ADV | Rs1L = %ADV | median price | avg trade size | σ_daily |
|---|---:|---:|---:|---:|---:|---:|
| Q1 small | Rs10.9 lakh | **2.30%** | **9.21%** | Rs60 | Rs3,589 | 2.47% |
| Q2 | Rs80 lakh | 0.31% | 1.25% | Rs141 | Rs6,250 | 2.53% |
| Q3 | Rs3.3 cr | 0.08% | 0.30% | Rs325 | Rs8,859 | 2.48% |
| Q4 | Rs11.5 cr | 0.02% | 0.09% | Rs428 | Rs11,638 | 2.47% |
| Q5 large | Rs79 cr | 0.003% | 0.01% | Rs576 | Rs22,158 | 2.17% |

At the 10th percentile of Q1 (ADV Rs1.83 lakh) a Rs25k order is **13.7% of a day's volume**.
Our Rs25k ticket is ~7 average trades in Q1. Tick/price in Q1 = 8.4bps, so even a
one-tick spread costs 4.2bps/side before impact.

## Cost build-up, Q1, delivery (CNC)
Amihud-linear impact (0.037% one-way @25k) is too optimistic at 2.3% of ADV. Using the
standard square-root model σ√(Q/ADV):

| | slippage RT | STT+stamp | DP Rs18.80 | total/mo | gross | **net/mo** |
|---|---:|---:|---:|---:|---:|---:|
| Rs25,000 | 0.748% | 0.215% | 0.075% | **1.038%** | 0.844% | **−0.194%** |
| Rs1,00,000 | 1.497% | 0.215% | 0.019% | **1.730%** | 0.844% | **−0.886%** |

**Liquidity-floor sweep — the killer.** Long bottom-20% by size *within* names above an
ADV floor. Raising the floor cuts cost but kills the premium faster:

| ADV floor | gross/mo | t | cost@25k | net@25k | OOS net |
|---:|---:|---:|---:|---:|---:|
| Rs2 lakh | +0.748 | 2.73 | 0.972 | −0.224 | −0.722 |
| Rs10 lakh | +0.553 | 2.13 | 0.780 | −0.227 | −0.754 |
| Rs50 lakh | +0.409 | 2.03 | 0.548 | **−0.139** (best) | −0.443 |
| Rs1 cr | +0.311 | 1.69 | 0.482 | −0.171 | −0.423 |
| Rs5 cr | +0.030 | 0.15 | 0.387 | −0.357 | −0.528 |

**Net is negative at every floor, at both position sizes.** There is no liquidity band
where the premium exceeds its own cost. That is the classic illusion, confirmed.

## Delisting
519 symbols stop trading. Monthly death rate: **Q1 2.62% vs Q5 0.21% (12.5×)**;
by illiquidity Q5 2.98% vs Q1 0.16%. 43.6% of all deaths sit in Q1. The panel treats a
death as a costless exit at the last traded price — pure fiction.

Nuance, honestly: the median dying name was **up +8.6% over its last 6 months** (mean
+21.7%); only 21.6% fell >20%. So most exits here look like mergers/symbol changes, not
wipeouts — a blanket haircut overstates it. But the sensitivity is brutal:

| haircut on dying names | Q1 gross/mo | t |
|---|---:|---:|
| 0% (as-is) | +0.844 | 3.32 |
| −30% | +0.106 | 0.43 |
| −100% | −1.062 | −3.33 |

## Longer horizons (lower cost/period)
Quarterly rebalance is the only variant that goes net positive: gross +2.137%/qtr
(t=2.43, n=18), cost 1.022% → **+4.46%/yr full sample, +0.37%/yr out of sample**.
Breakeven blended delisting haircut is **−14%**; anything worse erases it. Annual has n=4
rebalances — not evidence. Neither clears the |t|≥4 multiple-testing bar; neither clears
|t|≥2 out of sample.

## Why it fails — the arithmetic
Q1 gross edge 0.844%/mo. Q1 median ADV Rs10.9 lakh. A Rs25,000 order is 2.3% of that,
and at σ=2.47% daily the square-root impact alone is 0.75% round trip — **89% of the
edge consumed before a single statutory paisa**. Add 0.215% STT+stamp and Rs18.80 DP and
we are 23% underwater at Rs25,000 and 105% underwater at Rs1,00,000. Scaling down does
not help (DP fee is flat and rises as a % of a smaller ticket); scaling up makes impact
worse as √Q. Moving up the liquidity ladder cuts cost by 44% but cuts the premium by 45%.

**Where we sit on the line:** decisively on the uncapturable side, at both Rs25,000 and
Rs1,00,000. Not marginal — negative at every floor tested.

## Caveats
- Size proxy is turnover-based, not market cap. Correlated but noisy.
- Slippage is modelled (σ√(Q/ADV)), not measured — we have no order book for microcaps
  (the 200-symbol depth files are all liquid names). Amihud-linear gives a far kinder
  number (0.037% vs 0.374% one-way); I used the conservative one because 2.3% of ADV is
  far outside the range where linear impact is credible.
- 2021–2026 was an extreme Indian microcap bull market — EW universe returned +1.7%/mo.
  The gross premium may be regime, not risk premium; the holdout halving supports that.
