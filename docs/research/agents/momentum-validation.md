# mom_12_1 — validation

Script: `quant/validate_mom121.py` (reproduces every number below).
Data: `quant/data/sf_ret.parquet` (survivorship-free), monthly rebalance, 12-1 momentum
(cum return months t-11..t-1, skip month t), equal-weight top-N, hold month t+1.
Universe: median daily turnover >= Rs1cr, >=5 trading days, valid next-month return
(median 1,153 names). Costs: 0.20% STT + 0.015% stamp + **Rs18.80 flat DP fee per name sold**.

## VERDICT: NOT VIABLE — kill it

## THE NUMBER
Excess over equal-weight-same-universe, net, Rs1L, N=10: **+3.1 pp/yr, t = +0.28, n = 46 months.**
Best excess across all N=1..50 (i.e. already cherry-picked): +3.9 pp/yr, t = 0.58.
Market regression: **beta 1.14, alpha +0.61 pp/yr, t(alpha) = +0.05.** It is beta.

## WHAT WE TESTED
The prior "~26% gross" replicates (N=10 gross 26.1%, net 23.3%). But the equal-weight
benchmark on the *same eligible universe* returned **19.6%/yr gross with MDD -26%**, while
momentum's MDD was -46% at N=10 and -94% at N=1. Momentum earned ~3pp for 1.8x the drawdown.

**N-instability is noise, confirmed.** Split-half Spearman correlation of the excess-vs-N
curve is **rho = -0.46** — the shape *anti*-replicates. Best N = 8 in the first half, 35 in
the second. The 1-sigma sampling band on any single N is **±11.3 pp/yr** against a total
N-curve spread of 31 pp. The entire zig-zag is inside the noise band.

**Walk-forward** (24m rolling train picks N∈1..30, applied to the next month, n=22 OOS):
momentum -12.5%/yr vs benchmark -1.7%/yr, **excess -11.5 pp/yr, t = -0.92**, beating the
benchmark in only 7/22 months. Fixed N=5/10/20 OOS excess: -8.6 / -15.8 / -0.9 pp/yr.

**Regime**: excess +0.57%/mo in up-months, -0.17%/mo in down-months. Works only when the
market rises — beta in disguise, exactly the failure mode we were warned about.
**By year**: +17.0, +16.8, +6.0, -6.8, -26.4 pp (2022→2026). Monotonically decaying.

## WHY IT FAILED
Two separate arithmetic kills.

1. **No edge to begin with.** The alpha over the equal-weight universe is +0.6 pp/yr with
   t=0.05. The 26% was the market (19.6%) plus 1.14x leverage on it.
2. **The flat DP fee eats the small-capital case anyway.** Cost drag at N=10:
   6.58%/yr at Rs25,000 vs 2.79% at Rs1L vs 1.75% at Rs5L. At N=20/Rs25k it is 9.43%/yr.
   At Rs25,000 the net excess at N=10 is **-0.0 pp/yr** — the fee alone erases it.

**Power note (important):** the panel yields only 46 usable rebalances. With the observed
monthly dispersion, reaching t=2 would require an excess of **~+23 pp/yr**. We observe
+0.6 to +3.9. This dataset can never establish monthly-rebalance momentum, and the
observed magnitude is an order of magnitude short. More data would not rescue it.

The last live lead is dead. Do not resurrect without a different signal, not a different N.
