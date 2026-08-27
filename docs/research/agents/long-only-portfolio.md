# Long-only portfolio construction — "just own good stocks"

**Lane:** simple long-only. **Data:** `quant/data/sf_ret.parquet` + `sf_turn.parquet` (survivorship-free,
1232 sessions x 3046 symbols, 2021-06 → 2026-06). First 252 sessions burned for signal formation;
live window 2022-06 → 2026-06 (973 trading days, 4.0 yrs).

**VERDICT: viable, but only as risk reduction — not as return edge, and not at Rs25,000.**

---

## THE NUMBER

Best defensible construction = **quality screen (low vol + positive 12-1 momentum + stable turnover),
equal-weight 50 names, ANNUAL rebalance.**

| | Benchmark EW-500 (annual) | Quality-50 (annual) |
|:--|--:|--:|
| Gross CAGR | 20.0% | 14.6% |
| **Net CAGR @ Rs1,00,000** | **13.3%** | **13.5%** |
| Net CAGR @ Rs25,000 | −6.4% | 10.9% |
| Volatility | 18.1% | 12.4% |
| **Sharpe (net, 100k)** | **0.73** | **1.09** |
| Max drawdown | −25.5% | −16.9% |
| Worst calendar month | −10.7% | −9.3% |
| **Worst rolling 12m** | **−16.9%** (to 2025-09-26) | **−8.4%** (to 2025-09-04) |
| Cost drag/yr (100k) | 4.34% DP + 0.06% pct | 0.61% DP + 0.10% pct |
| Names sold over 4y | 1,155 | 163 |

Same net return, **two-thirds of the risk, one-seventh the cost**.

**But the return difference is not statistically real.** Daily excess vs benchmark:
mean −0.78%/yr, **t = −0.14**, n = 973. Beta-adjusted: beta 0.54, alpha 5.75%/yr, **t = 1.50** —
nowhere near the |t| ≥ 4 Bonferroni bar (36 configurations tested). The vol and drawdown reduction is
real and mechanical (low realised vol persists); the return advantage is not established.

## WHAT I TESTED

36 configurations: equal-weight top-N by 60d median turnover (N = 25/50/100/200/500), inverse-volatility
(N = 50/100), equal-risk-contribution on a shrunk covariance (N = 25/50), and the quality screen
(N = 15/25/50) — each at monthly / quarterly / annual rebalance, at Rs25,000 and Rs1,00,000.
Costs charged on every rebalance: 0.2% STT on value sold, 0.015% stamp on value bought,
**Rs18.80 flat DP fee per name sold**. Delisted names (493 in the file) exit at last traded price;
their median last-20-session return is +5.2%, so these are mergers/renames, not wipeouts — no
material optimism from that assumption.

## THE HONEST PART: 2021-2026 WAS A BULL MARKET

Split at 2024-06-30 (100k, net):

| | 2022-06 → 2024-06 | **2024-07 → 2026-06** |
|:--|--:|--:|
| Benchmark EW-500 annual | +36.5% CAGR, MDD −13.3% | **−6.4% CAGR, MDD −25.4%, worst-12m −16.9%** |
| Quality-50 annual | +25.0% CAGR, MDD −11.8% | **+2.7% CAGR, MDD −16.9%, worst-12m −8.4%** |
| Inverse-vol 50 annual | +29.2% CAGR, MDD −12.1% | −5.2% CAGR, MDD −20.9% |

**The whole 18-20% headline is the 2022-2024 leg.** The last two years the benchmark lost money.
The benchmark's rolling 12-month return was **negative 37% of the time**; the quality screen's, 15%.
Anyone shown the 5-year average and not this table is being misled.

## EXECUTABILITY AT Rs25,000 — the binding constraint

NSE EQ close prices (31-Oct-2025, n=2283): p10 Rs23, **median Rs253**, p75 Rs735, p90 Rs1,677, p95 Rs3,056.
Liquid large-caps — exactly what these screens pick — sit in the upper half.

- **N=50 at Rs25,000 → Rs500/name.** Buys zero shares of ~40% of the eligible universe. Not executable.
- **N=500 at Rs25,000 → Rs50/name.** The benchmark is a fiction at this capital: the DP fee alone is
  17.4%/yr, which is why it prints −6.4% net.
- **Practical ceiling at Rs25,000 is 10-15 names** (Rs1,700-2,500 each), and even then share
  indivisibility injects ±10-15% weight error, which swamps the difference between EW / inverse-vol / ERC.

Executable recommendation at Rs25,000: **quality screen, 15 names, annual rebalance** —
net 9.9% CAGR, vol 12.4%, Sharpe 0.80, MDD −19.7%, worst-12m −10.1%, DP fee 0.84%/yr.

## WHAT DIDN'T WORK

- **Monthly rebalancing is fatal at small capital.** Quality-50 monthly: gross 15.4%, net at Rs25,000
  **−12.8%**. The DP fee is 21.4%/yr. Arithmetic: ~30 names sold/month × Rs18.80 × 12 = Rs6,768 on
  Rs25,000. Rebalance frequency, not stock selection, is the dominant lever below Rs1,00,000.
- **ERC lost outright.** Gross 4.6-7.6% CAGR — the shrunk-covariance optimiser piles into the lowest-vol
  mega-caps and gives up too much return for the vol it saves. Sharpe 0.30-0.37. Dropped.
- **Inverse-vol is a weak version of the quality screen** (Sharpe 0.75 vs 1.09, worst-12m −12.9% vs −8.4%).
  The positive-12m-return filter, not the weighting, does the work.
- **Concentration hurts, monotonically.** EW gross CAGR: N=500 20.0% → N=200 17.2% → N=100 14.0% →
  N=50 12.9% → N=25 6.4%. Breadth is the free lunch; there is no evidence the liquidity ranking
  identifies better stocks at the top.

## ANSWER TO THE QUESTION

For capital that should grow with least attention: **50 equal-weighted names passing a low-vol +
positive-12-1-momentum + stable-turnover screen, rebalanced once a year, at Rs1,00,000 or more.**
It matched the naive 500-stock benchmark's net return with 12.4% vol vs 18.1%, a −16.9% max drawdown
vs −25.5%, and lost only 8.4% in its worst year vs the benchmark's 16.9% — while touching the account
once every twelve months. Defend it as *lower risk for the same money*, never as *more money* — the
return difference carries t = −0.14 and the alpha t = 1.50.

Below Rs1,00,000 the flat Rs18.80 DP fee dominates everything; below Rs25,000 no diversified
long-only book is executable at all, and the honest advice is a low-cost index fund or ETF where
the fee is a percentage, not a flat rupee amount.

*Scripts: `scratchpad/lo.py`, `lo2.py`; results `res2.csv`.*
