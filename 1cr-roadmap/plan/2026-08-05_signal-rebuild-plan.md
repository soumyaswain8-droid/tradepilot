# Signal Rebuild Plan

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Version** | `v1.0.0` |
| **Status** | Proposed — awaiting go-ahead |
| **Created** | 2026-08-05 |
| **Updated** | 2026-08-05 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

## Why this plan exists

v5 has lost money since 1 June: **−₹15,269 over 2,226 trades, t = −2.00**. Three
independent tests found the cause, and it is not costs, sizing, universe or exits.

Holding stock, day and stop-loss constant and changing **only when we enter**:

| | Return per trade |
|:--|--:|
| Our timed entries | +0.0549% |
| **Random entry times** | **+0.2012%** |

Random won across 5 independent seeds, t between 2.76 and 4.24. Giving random entries
our own 1.5% stop did not close the gap (t = +2.37 in random's favour), so the stops
are not the problem either.

## The root cause, measured

Every feature in the composite score describes what has **already happened**:

| Feature | Weight | Type | Why |
|:--|--:|:--|:--|
| `rs_score` | 26.7% | Lagging | High relative strength means it already outperformed |
| `orb_score` | 20.0% | Lagging | Fires only after price breaks the opening range |
| `vwap_score` | 13.3% | Lagging | Describes where price got to |
| `fii_score` | 13.3% | **Stale** | FII/DII flows publish end-of-day — today's read is yesterday's flow |
| `oi_score` | 13.3% | Lagging | Open interest accumulates after positioning |
| `vol_score` | 13.3% | Lagging | Volume spikes after the move starts |
| **Leading** | **0.0%** | | |

The 126-minute median entry lag is not an implementation bug. It is the arithmetic
consequence of a feature set in which nothing is forward-looking. Cadence adds a
structural floor on top: `ORB_MINUTES=15` means nothing can fire before 09:30,
`SCAN_INTERVAL_MIN=10` adds up to 10 minutes, and `RESCORE_INTERVAL_MIN=30` means
scores refresh twice an hour.

## The constraint that shapes everything

Kite's historical API returns **OHLCV only** — no bid/ask, no order-book depth, at any
interval. Verified directly.

So the one genuinely leading data source we can access, the live order book, **cannot
be backtested**. It must be collected forward before it can be tested at all. Any plan
that promises a validated leading signal in under a month is lying about this.

## Phase 0 — Stop paying for tuning (today, ~1 hour)

Six shadows are testing refinements to a signal that trails a coin flip. They cost
attention and muddy the record.

| Engine | Action | Why |
|:--|:--|:--|
| `v5_pick` | Pause | Score floor — tunes a score with no measured information |
| `v5_deploy` | Pause | 96% deployment — amplifies a negative edge |
| `v5_time` | Pause | Opening-hour gate — execution tweak |
| `v5_hold` | **Keep** | Tests exit structure, which is a separate open question |
| `v5_wide` | **Keep** | Universe breadth is data collection, costs nothing extra |
| `v5_kite` | **Keep** | Feed migration canary — infrastructure, not strategy |
| `v5`, `v5_classic` | **Keep** | Controls. Without them nothing new can be compared |

Paused engines keep their history; nothing is deleted.

## Phase 1 — Collect what cannot be backtested (start tomorrow)

Build `scripts/collect-orderbook.py`:

- Snapshot 5-level depth for the NIFTY-200 every 30 seconds during market hours
- Store to `docs/research/orderbook/YYYY-MM-DD.parquet`
- **Trades nothing.** Pure collection.
- Cost: one Kite quote call per 30s per 200-symbol batch — well inside rate limits

Record per snapshot: `bid_qty`, `ask_qty` (5 levels each), `spread`, `last_price`,
`volume`. From these, `imbalance = (bid−ask)/(bid+ask)` is the candidate leading
feature: **depth builds before price moves**.

**This is the long pole.** Two to three weeks of collection before there is enough to
test. Starting it tomorrow is the single most time-sensitive item in this plan.

## Phase 2 — Test what is testable now (this week)

Three hypotheses that only need OHLCV, so they can be tested against existing history
today. Each is a genuine leading candidate:

| # | Hypothesis | Status |
|:--|:--|:--|
| 1 | **Peer lead-lag** — when a sector moves and one name lags, it catches up | ❌ **Tested, dead.** 1,551 setups, +0.004%, t = 0.32, 49.3% win rate |
| 2 | **Index-futures lead** — NIFTY futures move before cash constituents | Untested |
| 3 | **Overnight gap follow-through** — does a gap predict the day's direction? | Untested |

Hypothesis 1 is already eliminated. That is the point of testing before building: it
cost 20 minutes instead of a sprint.

## Phase 3 — Question the timeframe (parallel, cheap)

The current strategy is intraday, and intraday is where costs bite hardest: at
0.055% per trade on a ₹45,000 position, gross edge is about ₹25 against ₹14.30 of
cost. That margin cannot survive a 47% win rate.

Test whether the **same signal on a longer holding period** clears costs — a signal
too weak for intraday can be perfectly good at 5–10 days, because the cost is paid
once against a larger move. `v5_hold` already gestures at this; a clean multi-day test
is cheap and uses data we have.

## What this plan does not promise

There may be no accessible leading signal. Order-book imbalance is the best candidate
because it is genuinely forward-looking and available to us, but it is a hypothesis
with no local evidence yet, and retail-latency depth snapshots at 30-second intervals
are a weak version of what professional order-flow desks use.

**Decision point after Phase 2 collection completes (~3 weeks):** if imbalance shows
no predictive power either, the honest conclusion is that this system cannot find an
intraday edge with retail-accessible data, and the choice is to move to a longer
timeframe or stop.

## Immediate recommendation

Halt the ₹12,000 live-money plan. The live A/B was meant to pick the winning engine,
but every engine has lost money since June. There is nothing to promote yet.

Paper trading continues throughout — the data is free and the out-of-sample record is
the only thing that will tell us whether any rebuild worked.
