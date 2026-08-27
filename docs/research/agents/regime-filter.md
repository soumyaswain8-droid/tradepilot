# Regime detection — when should we NOT trade?

**VERDICT: not viable.** Cross-sectional dispersion is the only regime variable that
separates anything, and it fails out-of-sample in both tests. Trend, volatility and
breadth separate nothing.

## THE NUMBER
Paper trades, high-dispersion abstention, **day-level**: −7.3 bp/trade on sat-out days
vs +1.0 bp on traded days, **Welch t = −1.40, p = 0.17, n = 16 vs 41 days.** Not significant.
mom_12_1 low-dispersion months, deployable long-only net of delivery costs and
market-demeaned: **train +0.73%/mo t=1.27, test +1.55%/mo t=2.47** — but the high-dispersion
bucket was *better* in train (+0.85% t=2.32) and negative in test (−0.79% t=−0.97). The split
reverses. n = 47 months.

## WHAT I TESTED
Regimes built causally (all features shifted one day, expanding percentile ranks, never a
full-sample quantile): index vs 50-day MA, 20d realised vol, 5d-smoothed cross-sectional
dispersion, % of names above own 20d MA. Bucketed 20,789 real closed trades (58 sessions,
15 engines, Jun 1 – Aug 27 2026) and, independently, 47 monthly mom_12_1 decile spreads on
survivorship-free sf_ret.

## WHY IT FAILED — the specific arithmetic

**1. The trade-level t-stat is fake.** Pooled, high-dispersion trades show −22.1 bp,
t = −9.64 out of sample, and 15/15 engines improve when you drop them. That looks
overwhelming. It is not: 20,789 trades come from **58 days × 15 engines trading overlapping
names**. Effective n is 58, not 20,789. Collapse to daily P&L and t goes from −9.64 to −1.40.
Every regime number in this lane must be quoted at day level.

**2. The August win is three days.** Test-period abstention turns −Rs48,796 into +Rs4,393 —
but Rs53,190 of that swing is 2026-08-12/13/14. Meanwhile the filter *misses* 08-04 (−19,904),
08-05, 08-17, 08-18, all of which were normal-dispersion. It catches one cluster and calls it
a regime.

**3. Trend and vol have zero variance in the live window.** The index sat above its 50-day MA
on **all 58 sessions**, and 20d vol never reached the top expanding tercile. There is no
trend-down or high-vol sample to test. Any "trade only in uptrends" rule is untested, not validated.

**4. Abstention is not free here.** Applying the train-only threshold sits out 16 of 58 days
(28%) — a quarter of the calendar surrendered for a filter whose day-level p is 0.17.

## USEFUL BY-PRODUCT (not my lane, for the mom agent)
mom_12_1 top-decile long-only, monthly, **market-demeaned and net of real delivery costs**
(0.215% + Rs18.80/scrip, 31% measured turnover → 0.164%/mo at Rs10L, 0.077%/mo at Rs1cr):
**+0.76%/mo t=2.46 (Rs10L), +0.85%/mo t=2.74 (Rs1cr)**, ~+9–10% annual excess, n=47 months.
That survives costs and market-neutralisation whole-sample — it does not survive a
dispersion regime filter, and t=2.7 does not clear the Bonferroni bar.

## Recommendation
Do not ship a dispersion gate. The one thing worth keeping is the measurement discipline:
**stop quoting per-trade t-stats on the paper-trade record** — with 15 engines on shared
names the honest denominator is trading days, and that divides t by roughly 7.
