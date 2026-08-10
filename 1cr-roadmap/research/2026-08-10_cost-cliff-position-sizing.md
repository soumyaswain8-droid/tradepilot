# The Cost Cliff — why three months of engines could not clear costs

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Status** | Root cause confirmed, fix deployed as `v5_size` |
| **Found** | 2026-08-10 |
| **Evidence** | 3,526 live paper trades, 18 engines, Aug 3–7 2026 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

## The finding

Zerodha intraday brokerage is **"0.03% or ₹20 per executed order, whichever is
LOWER"**. Below ₹66,667 per position the percentage binds; above it the flat ₹20 binds
and **cost falls as position size rises**.

| Position | Round-trip cost |
|--:|--:|
| ₹12,000 | 0.1060% |
| ₹45,000 | 0.1060% |
| ₹66,667 | 0.1060% ← the cliff |
| ₹100,000 | 0.0824% |
| ₹200,000 | 0.0588% |
| ₹500,000 | 0.0447% |

Measured across all 3,526 live paper trades: **median position ₹7,252, largest ever
₹44,992.** Not one trade in three months crossed the cliff. Every engine ran
permanently inside the most expensive fee bracket.

## Why it was structural, not bad luck

Three things compound, all in code:

1. `pool_manager.get_pool_budget()` returns **remaining** cash, not the pool's size
2. `scripts/v5-paper-trade.py:806` — `base = budget * 0.15`
3. `risk_manager.MAX_POSITIONS_TOTAL = 20`

Position size therefore decays geometrically as the pool fills:

| Position # | Budget remaining | base = 15% |
|--:|--:|--:|
| 1 | ₹300,000 | ₹45,000 |
| 3 | ₹216,750 | ₹32,512 |
| 6 | ₹133,112 | ₹19,967 |
| 12 | ₹50,203 | ₹7,530 |

Median across 20 slots lands near ₹7,000 — exactly the ₹7,252 observed.

**Capital was never the constraint.** Every engine had ₹10 lakh. `v5_deploy` already ran
a ₹6 lakh INTRADAY pool (base ₹90,000, max observed ₹88,633 — it did cross the cliff)
and still had a **₹12,891 median**, because dilution across slots, not pool size, sets
the median. The earlier hypothesis that a risk *multiplier* was cutting size by ~85% was
wrong: `get_effective_multiplier()` is VIX × recovery × regime and maxes at 0.85–1.0.

## Why this outranks every signal result

Gross edge measured across three independent families:

| Family | Gross edge/trade | Clears cost above |
|:--|--:|--:|
| v5 technical scorer | +0.069% | ~₹140,000 |
| SMC / ICT | +0.051% | ~₹292,000 |
| Evidenced baseline | +0.057% | ~₹200,000 |
| Best confluence pair | +0.091% | **~₹85,000** |

Every one of them clears at ₹100,000–₹200,000 per position. **None clears at ₹7,252.**
We were not failing to find signal — we were finding it repeatedly and spending it all
on brokerage.

## How the error survived scrutiny

The cost model was verified, and the verification was correct: *"percentage-based,
exactly 0.12% at every position size from ₹5,000 to ₹50,000."* That measurement is
true. Its range stopped ₹16,667 short of the point where the answer changes. It
confirmed a flat cost and concealed a variable one.

The general lesson: **a verification is only as good as the range it sampled.** When a
quantity is asserted to be constant, the test must include the region where it would
stop being constant — otherwise it proves the assumption rather than testing it.

## The fix — `scripts/v5_size-paper-trade.py`

Two env overrides, no code change to the shared path:

```
POOL_ALLOC          = {"INTRADAY": 1.0}    pool ₹10L instead of ₹3L
MAX_POSITIONS_TOTAL = 5                    instead of 20
```

Projected ladder, verified before launch:

| Position | Size | Cost |
|--:|--:|--:|
| 1 | ₹150,000 | 0.0667% |
| 3 | ₹108,375 | 0.0788% |
| 5 | ₹78,301 | 0.0955% |

Median ₹108,375 at **0.0788%** — a saving of **0.0272%/trade** against today's 0.1060%,
larger than the entire net deficit.

v5 and the other 17 engines are untouched, so the comparison isolates position size.

## What could still kill it

- **Slippage.** The entire gain is ~3 bps. A ₹1.5L order that moves a NIFTY-200 book
  more than ~2 bps erases it. NIFTY-200 medians run tens of crores daily, so ₹1.5L is
  ~0.0075% of volume — but this must be measured against the order-book depth data
  collected since 2026-08-07, not assumed.
- **Concentration.** Five positions instead of twenty means lumpier P&L and a worse
  drawdown at the same net edge. That is a real cost, not a rounding error.
- **The liquidity screen was built for ₹45,000 positions** (`≤0.5% of daily turnover`).
  At ₹1.5L it needs re-running before any wider universe uses this sizing.

## Verification for today's session

At 09:45, `v5_size`'s median position must exceed ₹66,667. If it does not, the
experiment did not happen and the result means nothing.
