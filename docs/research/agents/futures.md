# Lane: index & stock FUTURES as a cheaper wrapper

**VERDICT: not viable.** Two independent kills — the cost saving is ~7x smaller than
it looks, and the capital floor locks out our entire account range.

## THE NUMBER
mom_12_1, N=20, F&O-proxy universe, market-neutralised, monthly rebalance:

| book | cost | ALL (n=48) | OOS 2024-07+ (n=23) |
|---|---|---|---|
| long-only exc-mkt | cash delivery | +7.10%/y, t=1.08 | **-1.04%/y, t=-0.15** |
| long-only exc-mkt | futures | +9.41%/y, t=1.43 | **+1.27%/y, t=0.18** |
| long-only exc-mkt | futures+25bp roll | +6.41%/y, t=0.98 | **-1.73%/y, t=-0.25** |
| long-short | futures | +3.50%/y, t=0.83 | **-2.91%/y, t=-0.60** |

Best OOS case is t=0.18. Bar is |t|>=4. Nothing survives. maxDD -9% to -25%.

## Cost arithmetic (round trip, % of notional)
| instrument | round trip |
|---|---|
| NIFTY fut (75 x 25,000 = Rs18.75L) | **0.0288%** |
| stock fut @ Rs5-7L notional | **0.033-0.036%** |
| cash intraday | 0.107% |
| cash delivery @ Rs1L | 0.244% |

Futures are genuinely **6.8x cheaper than delivery**. STT 0.02% sell-side only
(note: raised from 0.0125% on 01-Oct-2024), stamp 0.002% buy-only, no DP fee,
Rs20 brokerage cap is trivial at Rs18L notional.

**But mom_12_1's real one-way monthly turnover is 29.5%, not 100%** — only 3.5x
book traded per year. So the annual drag is 0.80%/y in cash vs 0.12%/y in futures.
**The entire prize is 0.68%/y.** The OOS gross deficit is -2.2% to -7.5%/y. You
cannot close a 3-7 point hole with a 0.7 point saving. Cost was never the binding
constraint on this signal.

## Capital floor (the hard stop)
| | notional | margin (SPAN+ELM) |
|---|---|---|
| NIFTY 1 lot | Rs18,75,000 | ~Rs2,62,500 |
| stock fut 1 lot | Rs5-10L | ~Rs1,10,000-2,20,000 |

- **Rs25,000: cannot trade one lot of anything.** 0.23 lots.
- **Rs1,00,000: still cannot trade one lot.** 0.91 lots.
- **Rs3,00,000: 2 stock-future lots = 3.3x gross leverage on a 2-name book.**
  mom_12_1 already prints -55% DD at N=3 unlevered. At 3.3x that is ruin.

A diversified N=20 futures momentum book needs ~Rs22L margin (Rs1L x 20 lots x 1.1).
That is 7x our top-end capital.

## Secondary findings
- **F&O universe is only ~220 names.** Restricting to top-200-by-turnover did NOT
  hurt gross (+9.81%/y vs +7.88%/y on the full 3046) — the liquid-universe version
  is actually cleaner and has half the drawdown (-11% vs -25%). Worth keeping as a
  universe filter for the cash book regardless.
- **Basis/carry is a wash only if fully cash-backed.** Long futures forgo ~6.5%/y
  financing embedded in the premium; you recover it only by earning the same rate on
  the ~78% unpledged cash. Levered, you pay it outright. Long-short cancels it.
- Roll cost sensitivity: 10bp/roll costs 1.2%/y, 25bp costs 3.4%/y at 100% roll.
  This alone exceeds the transaction-cost saving.

## Method
sf_ret.parquet (survivorship-free, 1232 x 3046, returns clipped +/-50%). Universe =
top-200 trailing-6m-median turnover as an F&O-eligibility proxy (eligibility is
liquidity-driven). mom_12_1 = cumret t-252..t-21. Long-only reported as excess over
equal-weight universe return (beta stripped). Split 2024-07-01, never tuned on OOS.
Script: `scratchpad/fut.py`.

## WHY IT FAILED
The thesis was "every failure has been a cost failure." In this lane it is false.
At 29.5% monthly turnover the cash-vs-futures cost gap is 0.68%/y, while mom_12_1's
out-of-sample gross alpha is negative. Futures make a losing signal lose slightly
less. And the Rs1.1L-per-lot margin floor means Rs25,000-Rs1,00,000 cannot hold a
single position, while Rs3,00,000 can only hold a 2-name book at 3.3x leverage.
