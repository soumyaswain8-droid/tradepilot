# Do the segments behave differently? Nifty-50 vs mid vs small vs penny

**VERDICT: not viable — but the premise was right.**
The small/illiquid end IS more forecastable (4x the cross-sectional IC). It is also
where market impact scales fastest. The two cancel almost exactly. Nothing clears the bar.

**THE NUMBER:** least-liquid quintile, 1-month reversal, market-neutral within band,
delisted names marked to −100%: **+3.13%/month gross, n=45 months, t=3.68 on fees alone —
but t=2.18 once impact is charged at Rs25,000/position and t=0.90 at Rs1,00,000.**
Second half t=0.46. Fails the Bonferroni bar and fails out-of-sample.

Data: `quant/data/sf_ret.parquet` + `sf_turn.parquet` (survivorship-free, 3046 syms,
1232 sessions, 2021-06..2026-06) + monthly close prices rebuilt from
`quant/data/bhavcopy/` (59 month-end snapshots, EQ series only).

---

## 1. Segmentation

Monthly re-formation. Turnover bands = quintiles of trailing-21-day median turnover.
Price bands = month-end close from bhavcopy.

| Turnover band | avg names | median turnover |   | Price band | avg names |
|---|---:|---:|---|---|---:|
| T1 least liquid | 382 | Rs 10.2 L/day |   | < Rs10 | 61 |
| T2 | 381 | Rs 75.0 L/day |   | Rs10–50 | 267 |
| T3 | 381 | Rs 311 L/day |   | Rs50–200 | 513 |
| T4 | 381 | Rs 1,082 L/day |   | Rs200–1000 | 698 |
| T5 most liquid | 381 | Rs 8,207 L/day |   | > Rs1000 | 337 |

The top-200-by-turnover band the project has always fished in is roughly the top half
of T5. **We have been sampling ~7% of the tradeable universe.** The premise of the
question is correct.

## 2. Segment behaviour

| Band | mean bp/day | daily vol | +10% days | −10% days | lag-1 autocorr (t) | x-sec IC (t) |
|---|---:|---:|---:|---:|---:|---:|
| T1 least liquid | 11.6 | 3.02% | 1.008% | 0.159% | **+0.058** (38.1) | **−0.0559** (−15.2) |
| T2 | 7.5 | 2.97% | 0.931% | 0.155% | +0.042 (28.1) | −0.0387 (−11.5) |
| T3 | 6.0 | 2.86% | 0.746% | 0.160% | +0.036 (24.0) | −0.0299 (−9.2) |
| T4 | 5.9 | 2.79% | 0.564% | 0.166% | +0.024 (15.9) | −0.0285 (−8.5) |
| T5 most liquid | 5.5 | 2.56% | 0.343% | 0.193% | **+0.017** (11.8) | **−0.0129** (−3.5) |

| Price band | mean bp/day | vol | +10% | −10% | autocorr | x-sec IC (t) |
|---|---:|---:|---:|---:|---:|---:|
| < Rs10 | 16.5 | 3.63% | 1.454% | 0.303% | +0.142 | **+0.023** (+3.6) |
| Rs10–50 | 9.9 | 3.12% | 1.049% | 0.197% | +0.070 | −0.0232 (−5.5) |
| Rs50–200 | 9.3 | 2.93% | 0.850% | 0.169% | +0.024 | **−0.0530** (−15.2) |
| Rs200–1000 | 5.8 | 2.75% | 0.605% | 0.155% | +0.019 | −0.0382 (−13.2) |
| > Rs1000 | 3.5 | 2.50% | 0.351% | 0.142% | +0.027 | −0.0121 (−3.9) |

Note the striking asymmetry: illiquid names have **6x more +10% days than liquid names
but the SAME rate of −10% days**. The small end goes up in jumps and down in a grind —
consistent with promoter-driven pops, not with a tradeable return distribution.

## 3. THE KEY COMPARISON — yes, predictability differs, by 4x

Sign is the same (mean-reverting) but **magnitude is 4.3x larger in the illiquid band**:
IC −0.056 (T1) vs −0.013 (T5). The project's measured −0.017 in the liquid band is
confirmed and sits exactly where T5 lands.

Sub-period stability (IC of prior-day rank vs next-day rank):

| Band | 2021-06..2022-12 | 2023-01..2024-06 | 2024-07..2026-06 |
|---|---:|---:|---:|
| T1 | −0.012 (t=−1.7) | −0.066 (t=−10.4) | −0.082 (t=−15.2) |
| T5 | −0.005 (t=−0.8) | −0.019 (t=−3.0) | −0.014 (t=−2.4) |

T1 > T5 in every sub-period. This is a structural property, not a regime artifact.

**One sign flip worth flagging:** sub-Rs10 stocks are the only segment with a
**positive** IC (+0.023, t=3.6) — they trend rather than revert. But that band is
61 names with a 37% delisting rate; do not act on it.

**And a direct hit on the live lead:** 12-1 momentum, market-neutral within band, is
strongly **negative** in the illiquid end (T1: −33.6%/yr net, t=−3.27) and merely flat
in the liquid end (T5: −5.3%/yr, t=−0.70). The mom_12_1 lead does not generalise
down-cap — it inverts. What is left of it in T5 after neutralising the market is
approximately zero, which is consistent with the 26% gross long-only figure being beta.

## 4. THE HONEST COUNTERWEIGHT

| Band | delisted/stopped | circuit-lock proxy | Rs25k as % of ADV | modelled impact (1-way) |
|---|---:|---:|---:|---:|
| T1 | **20.2%** (182/901) | 0.017% of days | **2.45%** | 0.47% |
| T2 | 14.5% | 0.012% | 0.33% | 0.17% |
| T3 | 12.3% | 0.009% | 0.080% | 0.081% |
| T4 | 9.1% | 0.009% | 0.023% | 0.042% |
| T5 | 6.0% | 0.008% | 0.0030% | 0.014% |
| < Rs10 | **37.1%** (59/159) | 0.101% | 1.41% | 0.43% |
| > Rs1000 | 7.9% | 0.005% | 0.013% | 0.029% |

Circuit-lock is NOT the binding constraint (proxy: |ret|≥9.9% on below-25th-percentile
own-turnover; <0.02% of days everywhere). **Impact is.** Rs25,000 is 2.45% of a median
T1 name's entire daily turnover — one retail-sized order is a material fraction of the
day's tape.

## 5. Does the daily reversal pay? No — the STT arithmetic kills it before spread

Long the bottom decile by prior-day return, market-neutralised within band, daily
rebalance, decile ≈ 35 names:

| Band | gross bp/day | STT floor (delivery) | net |
|---|---:|---:|---:|
| T1 | **+17.8** | 20.0 bp | **−2.2 before any other cost** |
| Rs50–200 | +15.8 | 20.0 | −4.2 |
| T5 | −2.1 | 20.0 | −22.1 |

At the full Rs25,000 delivery cost (0.215% + Rs18.80 DP = 0.29%) T1 nets −11.2 bp/day
(t=−4.8, n=1221). Holding 5 days to amortise the fee destroys the signal faster than it
saves cost: gross falls to 1.7 bp/day, i.e. 8.7 bp per 5-day round trip against 29 bp.

**The clean kill: the best gross daily edge anywhere in the universe (17.8 bp) is smaller
than the 20 bp STT on a delivery round trip. Zero brokerage, zero DP fee, zero spread,
zero impact — it still loses.** Overnight holds cannot use the 0.107% intraday rate.

## 6. Monthly horizon — the one thing that nearly worked

T1, buy the worst-decile-by-1-month-return, market-neutral within band, monthly rebalance,
delisted names marked to −100% (conservative: the reversal picks precisely the names that
die, and it survives that marking):

| variant | univ | positions | gross/mo | impact/mo | fee/mo | net ann | t | MDD | H1 t | H2 t |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fees only, Rs25k | 391 | 39 | 3.13% | — | 0.29% | 34.1% | **3.68** | −10.2% | 3.76 | 1.50 |
| + impact, Rs25k | 391 | 39 | 3.13% | 1.14% | 0.30% | 20.3% | 2.18 | −16.6% | 2.55 | 0.46 |
| + impact, Rs1L | 391 | 39 | 3.13% | 2.19% | 0.24% | 8.5% | 0.90 | −24.0% | 1.57 | −0.48 |
| min Rs5L/day, Rs25k | 270 | 27 | 2.20% | 0.81% | 0.30% | 13.1% | 1.33 | −27.8% | 1.48 | 0.35 |
| min Rs5L/day, Rs1L | 270 | 27 | 2.20% | 1.62% | 0.24% | 4.1% | 0.41 | −34.1% | 0.81 | −0.30 |

Every step toward executability costs more than it is worth. Filtering to names that can
actually absorb Rs5 lakh/day of turnover cuts the gross edge from 3.13% to 2.20% — **the
edge lives in the untradeable tail of the untradeable band.**

## 7. Regime check — it is NOT the microcap bull

Equal-weight band return, annualised, delisting marked to −100%:

| period | T1 | T2 | T3 | T4 | T5 |
|---|---:|---:|---:|---:|---:|
| 2021-06..2022-12 | −3.5% | −0.9% | +2.6% | +5.7% | −0.4% |
| 2023-01..2024-06 | −9.9% | +4.4% | +26.5% | +34.6% | **+37.1%** |
| 2024-07..2026-06 | −31.6% | −35.1% | −24.0% | −14.2% | −6.8% |

The 2023-24 Indian small-cap bull shows up in T3/T4/T5, **not in T1**. Once you mark
delistings to −100%, the least-liquid quintile lost money in all three sub-periods. So the
T1 reversal edge is not a bull-market artifact — but it also is not a bull-market ride,
and its strength decayed (H1 t=2.55 → H2 t=0.46 with impact charged).

## 8. Conclusion — which side each segment falls on

| Segment | Predictability | Executable at Rs25k–1L | Verdict |
|---|---|---|---|
| T1 / < Rs10 | Best (IC −0.056) | No — 2.5% of ADV, 20–37% delist | Edge real, uncapturable |
| T2 / Rs10–50 | Good (IC −0.039) | Marginal — 0.33% of ADV | Gross 0.99%/mo, t=1.09 net. Nothing. |
| T3–T4 / Rs50–1000 | Moderate (IC −0.030) | **Yes** — 0.02–0.08% of ADV | Reversal is NEGATIVE here (−14%/yr) |
| T5 / > Rs1000 | Worst (IC −0.013) | Yes, trivially | Where we have been. Correctly so. |

**There is no segment where predictability and executability coexist.** They are the same
variable with opposite signs. The IC gradient (−0.013 → −0.056 as you go down-liquidity)
and the impact gradient (0.014% → 0.47% one-way) rise together, and the impact gradient
rises faster. T3/T4 is the only band that is both liquid enough and non-trivial in size —
and it is the band where the reversal sign is against you.

**Recommendation:** stop treating "we only looked at the top 200" as an unexplored
opportunity. It has now been looked at. The unexplored direction is not smaller names, it
is longer holding periods or a different instrument where the 20 bp STT floor does not
apply per round trip.

### What would change this verdict
- Real quoted spreads for T1 names (I used a modelled `sigma*sqrt(participation)` impact,
  not measured). If actual round-trip slippage in T1 is under ~0.6%/month the monthly
  reversal returns to t>3. We have no depth data below the top 200 to check this.
- n=45 months is thin. Two more years would settle the H2 decay question.

### Caveats
- Bhavcopy month-end price panel is 59 of 60 months; symbols not in EQ series are excluded
  from price bands (turnover bands are unaffected).
- Circuit-lock is a proxy (low-turnover + near-limit move), not verified against actual
  NSE band files.
- ~20 strategy variants tested here; t=3.68 clears a 20-test Bonferroni (~3.0) on fees
  alone but not the project-wide 1000-test bar, and not with impact charged.
