# Week-1 Falsification Gate — Result

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Status** | Complete |
| **Run** | 2026-08-10, sessions 2026-05-18 .. 2026-08-07 |
| **Sample** | 201 symbols, 145,500 simulated trades, 58,000 random controls |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

## Verdict

**No predicate survives.** Per the criteria in the design spec §6.1 — clear 0.120% cost,
t > 2, beat a random entry — nothing passes. The thesis as specified is dead.

The result is more informative than that sentence suggests, and the detail below is
where the value is.

## Individual predicates

Fixed exit for all: 1.2% target, 0.6% stop, 14:45 time stop. Random baseline
net **-0.1149%/trade** (n=58,000).

| Predicate | n | win% | gross% | net% | t | vs random |
|:--|--:|--:|--:|--:|--:|--:|
| smt_divergence | 11,508 | 48% | **+0.0514** | -0.0686 | -11.23 | **+0.0463** |
| short_term_reversal | 4,530 | 42% | **+0.0565** | -0.0635 | -5.50 | **+0.0514** |
| order_block | 6,973 | 43% | +0.0022 | -0.1178 | -15.22 | -0.0029 |
| fvg | 10,820 | 41% | -0.0070 | -0.1270 | -19.43 | -0.0121 |
| amd_phase | 11,269 | 39% | -0.0161 | -0.1361 | -19.82 | -0.0212 |
| liquidity_sweep | 11,361 | 39% | -0.0173 | -0.1373 | -20.06 | -0.0225 |
| overnight_gap | 5,035 | 36% | -0.0233 | -0.1433 | -13.42 | -0.0284 |
| opening_range | 10,228 | 39% | -0.0262 | -0.1462 | -21.38 | -0.0313 |
| mtf_alignment | 5,976 | 37% | -0.0485 | -0.1685 | -18.75 | -0.0537 |
| index_lead | 9,800 | 37% | -0.0691 | -0.1891 | -27.30 | -0.0743 |

Two predicates carry a genuine positive gross edge and beat random by ~0.05%/trade on
large samples. Neither clears the toll.

## Finding 1 — confluence is real, and monotonic

Grouping by symbol/day/direction and counting how many predicates agree:

| # agreeing | n | win% | gross% | net% | vs random |
|--:|--:|--:|--:|--:|--:|
| 1 | 2,278 | 32% | -0.1595 | -0.2795 | -0.1646 |
| 2 | 3,518 | 37% | -0.1014 | -0.2214 | -0.1065 |
| 3 | 3,993 | 36% | -0.0677 | -0.1877 | -0.0728 |
| 4 | 4,231 | 38% | -0.0603 | -0.1803 | -0.0654 |
| 5 | 3,979 | 43% | +0.0010 | -0.1190 | -0.0041 |
| 6 | 2,946 | 45% | +0.0626 | -0.0574 | +0.0574 |
| 7 | 1,317 | 48% | **+0.0836** | -0.0364 | **+0.0785** |
| 8 | 279 | 43% | +0.0399 | -0.0801 | +0.0348 |

A clean dose-response across eight buckets with thousands of samples each. **The
confluence mechanism the design was built around works.** It is the single most
encouraging result here. It is also still not enough: even at 7-of-10 agreement the
net is -0.0364%.

Best pair found — `smt_divergence` + `short_term_reversal` on the same stock/day/side:
n=2,259, gross **+0.0909%**, net -0.0291%, +0.0857 vs random. The best configuration in
the entire study, and still under water.

## Finding 2 — the daily-bias veto is backwards

| | n | gross% | net% | vs random |
|:--|--:|--:|--:|--:|
| Trading **with** daily bias | 29,202 | -0.0389 | -0.1589 | -0.0440 |
| Trading **against** daily bias | 58,298 | +0.0033 | -0.1167 | -0.0018 |

Design spec L3 makes daily bias a **hard veto** that would reject any setup opposing it.
Measured, that filter is harmful: with-bias trades are worse than against-bias trades by
0.042%/trade. Had L3 shipped as specified it would have systematically selected the
worse half.

This is coherent with the rest of the data rather than an anomaly: `short_term_reversal`
(buy the 5-day loser) is the best single predicate, and `mtf_alignment` (trend agreement)
is among the worst. **At this horizon the market is mean-reverting, not trending.** The
design's trend-following assumptions are inverted.

The measurement path caught this on its first run, which is precisely what it was for.

## Finding 3 — my priors were wrong, in a useful direction

Recorded before the run: `mtf_alignment` strong, `order_block` and `amd_phase` weak.

Measured: `mtf_alignment` is **9th of 10**. `order_block` is mid-pack. `smt_divergence`
— the only predicate using information from outside the symbol's own price history — is
**the best**.

The two predicates I flagged as hindsight-prone did not top the table, so the
hindsight-fitting red flag did not trigger. But the "strong evidence" prior was simply
wrong for this market and horizon.

## What this means for the ₹1 crore target

This is now the **third independent measurement of the same shape**:

| Family | Gross edge/trade |
|:--|--:|
| v5 technical scorer (measured 2026-08-05) | +0.069% |
| SMC / ICT predicates | +0.051% |
| Evidenced baseline predicates | +0.057% |
| Best confluence combination | +0.091% |
| **Cost** | **0.120%** |

Three unrelated methodologies converge on 0.05-0.09% gross against a 0.120% toll. The
binding constraint is **not signal discovery — it is cost**. We are not failing to find
signal; we are finding it consistently and it is consistently too small to pay the toll.

`smt_divergence` would need the round trip below **0.0514%** to break even. We pay 2.3x
that.

## Options, ranked

1. **Attack cost.** 12 bps is close to the floor for Indian intraday equity (STT 0.025%
   on sell, brokerage 0.03%, exchange charges, GST, stamp duty). Realistic floor is
   perhaps 8-10 bps — which would still not clear +0.09% with margin. Worth costing
   precisely rather than assuming.
2. **Order-book depth.** The only genuinely new information left untested, and the one
   input that is not derived from the same OHLCV every other family already mined.
   Collection began 2026-08-07; needs 2-3 more weeks before it can be tested.
3. **Larger moves per trade.** Already tested and killed — multi-day holds showed zero
   market-adjusted return (2026-08-05).
4. **Reweight the ₹1 crore target toward product revenue.** The revenue arithmetic
   (~835 subscribers at ₹999/month) does not depend on the trading edge existing.

## Limitations, stated plainly

- 60 days of intraday history, the yfinance ceiling. A Kite token would extend it.
- Confluence buckets are not independent tests; higher agreement naturally selects for
  larger moves, and averaging across predicates that entered at different times
  conflates entry timing with signal strength.
- One fixed exit throughout. This measures signal quality, not whether a different exit
  regime could rescue a signal.
- When a 5m bar spans both target and stop, the stop is assumed to fill first. Without
  tick data the ordering is unknowable, and the optimistic assumption is how backtests
  manufacture edge that vanishes live.
- A backtest can kill a thesis but never confirm one. This one killed.
