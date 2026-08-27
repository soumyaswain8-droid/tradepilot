# Goal arithmetic — what Rs 1 crore/yr actually requires

**VERDICT: NOT VIABLE at current capital. Not "hard" — arithmetically closed.**
Rs 1 crore/yr of investment profit needs Rs 4–12.5 crore of capital. We have Rs 3,000–25,000.
That is a factor of ~10,000. No return assumption bridges it. The gap is capital, not skill.

---

## 1. Honest return benchmarks (measured, `quant/data/sf_ret.parquet`, survivorship-free)

Equal-weight daily rebalance of the top-N by 60d median turnover, returns clipped ±25%,
1,172 sessions, 2021-09 → 2026-06 (4.74 yrs).

| Universe | CAGR | Max DD | Worst rolling 12m | Median 12m | % of 12m windows negative | Worst rolling 3y (annualised) |
|:--|--:|--:|--:|--:|--:|--:|
| Top 100 | 10.79% | −24.6% | **−13.08%** | 9.34% | 35.2% | 9.21% |
| Top 200 | 11.45% | −25.1% | −11.80% | 10.71% | 33.7% | 9.18% |
| Top 500 | 13.69% | −25.0% | −10.89% | 9.06% | 31.1% | 12.43% |
| Top 1000 | 14.58% | −26.0% | −11.66% | 8.81% | 27.2% | 12.54% |
| Top 1500 | 16.38% | −26.7% | −13.22% | 11.41% | 24.6% | 13.10% |

Calendar years (top-500): 2021 +2.6%, 2022 −1.0%, **2023 +46.6%**, 2024 +21.6%, 2025 −1.9%, 2026 YTD +3.5%.

**The headline 18.3% is not a forecast.** Three facts kill it as a planning number:

1. **One year is the whole result.** 2023 alone (+46.6%) carries the entire CAGR. Strip it and
   the remaining 3.7 years compound at roughly 5–6%/yr. A 4.7-year sample containing one 47% year
   is a bull-market sample, not a cycle.
2. **The worst 12-month window was −10.9% to −13.2%**, and roughly **one 12-month window in three
   was negative**. The drawdown was −25%.
3. **There is only ONE independent 3-year window** in 4.74 years. The "worst 3y = +12.4%/yr" number
   is not evidence of a floor — it is an artefact of the sample starting and ending inside the same
   expansion. Do not use it.

**Defensible long-run expectation: 10–12%/yr gross, before costs and before tax.**
Median rolling 12m across all universes is 8.8–11.4%; the higher CAGRs come from the *less liquid*
tail, which is exactly where our cost floor bites hardest (§6). Plan on **~10%**, treat 15% as a
good outcome, and treat anything above that as unproven.

---

## 2. Capital ladder — capital required for a target annual profit

| Target annual profit | @ 8% | @ 15% | @ 25% | @ 40% |
|:--|--:|--:|--:|--:|
| Rs 1 lakh | Rs 12.5 L | Rs 6.7 L | Rs 4.0 L | Rs 2.5 L |
| Rs 10 lakh | Rs 1.25 cr | Rs 66.7 L | Rs 40.0 L | Rs 25.0 L |
| **Rs 1 crore** | **Rs 12.50 cr** | **Rs 6.67 cr** | **Rs 4.00 cr** | **Rs 2.50 cr** |

Read the bottom row again. The cheapest cell — 40%/yr sustained, which does not exist (§3) —
still demands **Rs 2.5 crore**. At the defensible 10–12%, it is **Rs 8–10 crore**.

---

## 3. Which cells are plausible

| Cell | Verdict |
|:--|:--|
| 8%/yr | **Real.** Below our own measured median. An index fund clears this with no effort. |
| 15%/yr | **Plausible but not guaranteed.** Sits at the top of our measured median band. Requires the next 5 years to look like the last 5 — i.e. requires another 2023. |
| 25%/yr **sustained** | **Not established.** Our best live lead (mom_12_1, ~26% gross) has t = 0.91–1.82 — below any significance bar — and −55% max DD at N=3. That is a coin-flip dressed as a strategy. |
| 40%/yr **sustained** | **Fantasy. Say it plainly.** |

External reference points for the 25–40% column (context, not our measurement):
Berkshire compounded ~20%/yr across 60 years and is the single most celebrated record in the
business. Renaissance Medallion is the only widely-cited fund in the 40%+ net band, it has been
closed to outside money for decades, and it is hard-capped at a few billion dollars precisely
because the edge does not scale. Broad hedge-fund indices land in the high single digits.
The best Indian equity funds over 10+ years sit around 15–18%.

**If 40%/yr were sustainable, it would be the dominant fact of global finance rather than
a line in a spreadsheet.** Any plan whose success depends on a 25%+ cell is not a plan.

---

## 4. Compounding path — Rs 25,000 start → Rs 1 crore

Years required, monthly contribution `C` added at month end:

| Monthly contribution | @ 8% | @ 15% | @ 25% | @ 40% |
|:--|--:|--:|--:|--:|
| Rs 0 | 77.9 y | 42.9 y | 26.9 y | 17.8 y |
| Rs 5,000 | 33.8 y | 22.5 y | 16.0 y | 11.7 y |
| Rs 10,000 | 25.9 y | 18.0 y | 13.2 y | 9.9 y |
| Rs 25,000 | 16.5 y | 12.4 y | 9.6 y | 7.4 y |
| Rs 50,000 | 10.8 y | 8.7 y | 7.0 y | 5.7 y |
| Rs 1,00,000 | 6.5 y | 5.6 y | 4.8 y | 4.0 y |

Note the row that matters: **with zero contributions, Rs 25,000 takes 43 years at 15% and still
27 years at an impossible 25%.** The starting capital is irrelevant to the outcome. What moves the
timeline is the contribution rate — going from Rs 5,000/mo to Rs 50,000/mo cuts 22.5 years to
8.7 years *at the same return*, a bigger effect than moving from 8% to 40% at fixed contribution.

And Rs 1 crore of *capital* is not the goal — Rs 1 crore of *annual profit* is. That target is
another 4–12× beyond every number in this table.

---

## 5. Where the outcome actually comes from

Annual return vs. what could simply be deposited:

| Capital | Return @ 15% | per month | Return @ 25% | per month |
|:--|--:|--:|--:|--:|
| Rs 3,000 | Rs 450 | **Rs 38** | Rs 750 | **Rs 62** |
| Rs 25,000 | Rs 3,750 | **Rs 312** | Rs 6,250 | **Rs 521** |
| Rs 1 lakh | Rs 15,000 | Rs 1,250 | Rs 25,000 | Rs 2,083 |
| Rs 5 lakh | Rs 75,000 | Rs 6,250 | Rs 1.25 L | Rs 10,417 |
| Rs 10 lakh | Rs 1.5 L | Rs 12,500 | Rs 2.5 L | Rs 20,833 |
| Rs 40 lakh | Rs 6.0 L | Rs 50,000 | Rs 10.0 L | Rs 83,333 |
| Rs 4 crore | Rs 60 L | Rs 5.0 L | **Rs 1.00 cr** | Rs 8.3 L |

At Rs 25,000, a *spectacular* 25% year earns **Rs 6,250 — about Rs 520 a month.**
The difference between a world-class 25% and a passive 10% is Rs 3,750 for the entire year.
That is the total prize for every hour spent on strategy research at this account size.

**Crossover — capital at which annual return exceeds annual savings:**

| Savings rate | @ 8% | @ 15% | @ 25% |
|:--|--:|--:|--:|
| Rs 5,000/mo | Rs 7.5 L | Rs 4.0 L | Rs 2.4 L |
| Rs 10,000/mo | Rs 15.0 L | Rs 8.0 L | Rs 4.8 L |
| Rs 25,000/mo | Rs 37.5 L | Rs 20.0 L | Rs 12.0 L |
| Rs 50,000/mo | Rs 75.0 L | Rs 40.0 L | Rs 24.0 L |

**Below roughly Rs 5–10 lakh, the portfolio is a rounding error against income.** Return only
becomes the dominant lever somewhere north of Rs 10–20 lakh. Concretely: starting at Rs 25,000 and
adding Rs 25,000/mo, after 5 years you have Rs 15.25 L at 0% return, Rs 22.09 L at 15%, Rs 28.09 L
at 25%. Even at an unattainable 25%, **54% of the balance is money you deposited.**

---

## 6. The cost floor makes small capital actively worse

Delivery (CNC): 0.2% STT on sell + 0.015% stamp on buy = **0.215% round trip, size-independent**,
plus **Rs 18.80 flat DP fee per scrip per sell**.

| Position size | DP fee as % | Total round-trip drag |
|:--|--:|--:|
| Rs 3,000 | 0.627% | **0.842%** |
| Rs 10,000 | 0.188% | 0.403% |
| Rs 25,000 | 0.075% | 0.290% |
| Rs 1,00,000 | 0.019% | 0.234% |
| Rs 5,00,000 | 0.004% | 0.219% |

The flat fee is regressive by construction. Annualised drag on a **Rs 25,000 account**:

| Positions | Position size | Monthly rebal | Quarterly | Semi-annual |
|:--|--:|--:|--:|--:|
| N=3 | Rs 8,333 | 5.29%/yr | 1.76%/yr | 0.88%/yr |
| N=5 | Rs 5,000 | 7.09%/yr | 2.36%/yr | 1.18%/yr |
| N=10 | Rs 2,500 | **11.60%/yr** | 3.87%/yr | 1.93%/yr |
| N=20 | Rs 1,250 | **20.63%/yr** | 6.88%/yr | 3.44%/yr |

This is decisive. A diversified, monthly-rebalanced book at Rs 25,000 **loses 7–21%/yr to fees
alone** — it consumes the entire honest expected return before a single decision is evaluated.
Small capital is forced into a corner: few positions (concentration risk, the −55% DD problem)
and infrequent rebalancing. mom_12_1's ~26% gross with monthly rebalance at N=3 gives up 5.3%/yr
to costs at this size — and its t-stat says the 26% may not be real to begin with.

Note the trap: the higher measured CAGRs (16.4% at top-1500) come from smaller, less liquid names
where spread and impact are worst. The extra return is not reachable through the cost floor.

---

## What the arithmetic permits

1. **Rs 1 crore/yr is not reachable from Rs 25,000 by returns.** It is a Rs 4–12 crore capital
   problem. Ranked by leverage on the outcome: **capital contribution ≫ time ≫ return**.
2. **Below ~Rs 5 lakh, strategy work has near-zero expected value in rupees.** A perfect 25% year
   on Rs 25,000 pays Rs 6,250 and 5–21 points of it goes to DP fees. An extra Rs 10,000/mo of
   income beats any achievable alpha by an order of magnitude, with certainty and no drawdown.
3. **Plan on 10–12%/yr, not 18.3%.** Our own 4.7-year sample is one bull run; a third of its
   12-month windows are negative and it drew down 25%.
4. **Any target that requires >20%/yr sustained is not a target, it is a wish.**
5. **The only defensible small-capital configuration** is concentrated (N≤5), rebalanced no more
   than quarterly, keeping cost drag under ~2.5%/yr. That is a constraint imposed by the Rs 18.80
   flat fee, not a strategy choice.

If Rs 1 crore/yr is genuinely the objective, the honest route runs through income, business
revenue, or outside capital. The market is where capital is *preserved and compounded* once it
exists — it is not where it is manufactured from Rs 25,000.
