# Swing horizon (3–10 days) — the gap between intraday and monthly

Author: Soumya Swain · 2026-08-28 · data: `quant/data/sf_ret.parquet` (survivorship-free, 3046 syms, 2021-06→2026-06)

**VERDICT: not viable.** The cost-amortisation curve is real and behaves exactly as theory says — but it
crosses zero at ~14 days, not 3–10, and by then the sign is not reliable out-of-sample.

## THE NUMBER

Gross market-neutral decile spread accrues at **0.032% per calendar day of holding** (linear fit vs h,
r = 0.88, intercept ≈ 0). Delivery round trip is **flat 0.468%** (0.215% × 2 legs at Rs1,00,000).

| Book | Cost | Break-even holding period |
|---|---:|---:|
| Long/short spread, Rs1,00,000 | 0.468% | **14.5 days** |
| Long/short spread, Rs25,000 | 0.580% | **18.0 days** |
| Long-only vs market, Rs1,00,000 | 0.234% | 7.2 days |
| Long-only vs market, Rs25,000 | 0.290% | 9.0 days |

The Rs18.80 DP fee alone moves break-even by 3.5 days at Rs25,000 and 1.2 days at Rs1,00,000.

Best train variant: `acc` (5d return minus 21d drift), h=10, gross spread **+0.909%**/cohort, t=2.96, n=61.
Fails Bonferroni for 44 variants (needs |t| ≥ 3.19). **Holdout: −0.031%, t = −0.078, n=36.** Dead.
Second and third train picks (`acc` h=3, `ret_21` h=5) also die: holdout t = 1.57 and 0.02, both net-negative.

## FULL CURVE — net edge vs holding period 1→21

`mean|gross|` = mean absolute decile spread across 10 features, full sample (an *upper bound*: sign fitted in-sample).
`hold` columns = out-of-sample only (2024-12-11→2026-06), best train feature, direction locked from train.

| h | mean\|gross\| | net vs 100k cost | hold gross | hold t | hold net 100k | hold net 25k | n(hold) |
|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | 0.036% | −0.432% | +0.032% | 0.64 | −0.435% | −0.548% | 368 |
| 2 | 0.060% | −0.407% | +0.065% | 0.70 | −0.403% | −0.515% | 184 |
| 3 | 0.072% | −0.395% | +0.200% | 1.57 | −0.267% | −0.380% | 122 |
| 4 | 0.124% | −0.344% | +0.068% | 0.40 | −0.400% | −0.512% | 92 |
| 5 | 0.162% | −0.306% | +0.131% | 0.59 | −0.337% | −0.450% | 73 |
| 6 | 0.205% | −0.263% | +0.053% | 0.23 | −0.415% | −0.527% | 61 |
| 7 | 0.208% | −0.259% | +0.450% | 1.55 | −0.018% | −0.131% | 52 |
| 8 | 0.250% | −0.218% | +0.508% | 1.43 | **+0.040%** | −0.073% | 46 |
| 9 | 0.321% | −0.147% | +0.139% | 0.38 | −0.329% | −0.442% | 40 |
| 10 | 0.324% | −0.144% | −0.031% | −0.08 | −0.499% | −0.611% | 36 |
| 11 | 0.417% | −0.051% | −0.195% | −0.49 | −0.663% | −0.776% | 33 |
| 12 | 0.427% | −0.040% | +1.142% | 2.31 | **+0.674%** | **+0.561%** | 30 |
| 13 | 0.431% | −0.037% | +0.738% | 1.36 | **+0.270%** | +0.157% | 28 |
| 14 | 0.357% | −0.110% | +0.685% | 1.58 | **+0.217%** | +0.104% | 26 |
| 15 | 0.727% | +0.259% | −1.128% | −1.84 | −1.595% | −1.708% | 24 |
| 16 | 0.337% | −0.131% | +0.699% | 1.01 | **+0.231%** | +0.119% | 23 |
| 17 | 0.487% | +0.020% | −0.640% | −0.82 | −1.108% | −1.220% | 21 |
| 18 | 0.600% | +0.132% | −0.194% | −0.35 | −0.661% | −0.774% | 20 |
| 19 | 0.643% | +0.175% | −0.511% | −0.88 | −0.978% | −1.091% | 19 |
| 20 | 0.383% | −0.085% | +0.100% | 0.10 | −0.368% | −0.481% | 18 |
| 21 | 0.887% | +0.419% | +0.327% | 0.49 | −0.141% | −0.254% | 17 |

Holdout signed mean across all 21 horizons: **+0.126% per cohort, sd 0.496%, positive in 15/21.**
Pooled that is t ≈ 1.16 on 21 overlapping-feature estimates — indistinguishable from zero, and the sign
flips violently (h=12 is +1.14%, h=15 is −1.13%, three days apart). That is noise, not a horizon effect.

## WHAT I TESTED

11 close-observable features (1/5/21-day returns, distance from 20/50-day averages, 52-week range
position, 21-day realised vol, 5/60-day turnover ratio, up-day fraction, 5d-vs-21d acceleration, and an
explicit long-reversal) × holding periods 3/5/7/10 = **44 train variants**. Universe: top-500 by 21-day
median turnover with ≥200 sessions of history (avg 383 names/day). Decile sort each cohort, D10−D1,
equal weight. **Every forward return is cross-sectionally demeaned over the identical window**, so the
rising-market beta trap is closed. Entry lagged one full session (close t signal → hold t+1→t+1+h), so
no next-open lookahead. Cohorts sampled every h days — **non-overlapping**, so the t-stats are honest.
Train 2021-06→2024-12 (862 sessions), holdout 2024-12→2026-06 (370 sessions), split fixed before search.

## WHY IT FAILED — the arithmetic

The premise was right: cost does amortise. At h=1 the toll is 13× the gross edge; at h=10 it is only
1.4×. That is a 9× improvement and it is exactly the mechanism the brief predicted.

It is not enough. Edge accumulates at 0.032%/day; the delivery toll is 0.468% flat. You need **14.5 days**
of holding before the accumulation catches the toll — and 14.5 days is past this lane, in the monthly
bucket where `mom_12_1` already lives. Inside 3–10 days the best case is h=10 at −0.144% net, and that
"best case" is a sign-fitted upper bound; the honest out-of-sample number at h=10 is **−0.499%**.

Worse, buying holding period costs statistical power quadratically: h=10 leaves 25 independent cohorts
a year, so even a genuine 0.5% edge needs ~6 years to reach t=2. The two things you need — enough days
to amortise the toll, and enough independent cohorts to prove the sign — pull against each other in this
window. There is no h in 3–21 where both hold.

## USABLE CORNER (not a recommendation)

Long-only-vs-market at Rs1,00,000 breaks even at 7.2 days — the single-leg toll is half. But an
India cash book cannot short (RBI margin ban), so "market-neutral long-only" means the demeaning is a
benchmark, not a hedge; the realised book carries full beta. That is precisely the trap the brief warns
about, so I am not counting it. If it is pursued, it must be with an index-future hedge costed in.

## What would change the answer
- Larger positions do NOT help materially: the DP fee is only 0.038% of the 0.468% toll at Rs1,00,000.
  The binding cost is 0.215% statutory (STT + stamp), which is size-invariant. **No capital level fixes this.**
- Only a gross edge above ~0.15%/day (5× what any of these 11 features produce) makes 3–10 days work.
- Or a structurally cheaper wrapper — futures/options where STT is 0.02% not 0.2%. That is a different lane.
