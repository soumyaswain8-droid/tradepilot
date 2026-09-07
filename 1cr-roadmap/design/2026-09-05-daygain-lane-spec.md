# DAYGAIN — top-gainer concentration lane. Pre-registered spec.

**Status:** DRAFT — gates registered before Phase 0 runs.
**Drop into:** `1cr-roadmap/design/`. **Date:** 2026-09-05.

## Why this lane exists

Ledger-reconstructed counterfactual across 31 sessions (2026-07-21 →
2026-09-03, prices recovered from the fleet's own verdict + trade records):
top-10 day gainers at 09:35, ₹1.125L each, hold to last observation, 0.12%
costs → **+₹172,099, 20/31 win days, +0.049%/day** vs the live fleet's
−0.031%/day on the same capital. Known upward bias: 56% of basket slots had
truncated observation paths (scanner stopped watching fading names), and
truncated paths average +0.29% vs +0.76% for full-day paths — the true
number is lower and only real bar data can say how much.

Second purpose regardless of P&L: **baseline**. If v5's scored, gated,
re-scanned machinery cannot beat this one-decision rule net of costs, the
scoring layer is not paying for itself.

Prior art this does NOT duplicate: classics `mom_rotate` (monthly, 6-month
lookback — failed holdout) tests a different horizon; `v5_size` and
`v5_hold` test concentration and holding on v5's signal, not on the naked
gainer rank.

## The rule (frozen — no parameter changes after registration)

- **Universe:** NSE equities, price ≥ ₹50, ADV ≥ ₹5 cr (liquidity floor).
- **Signal time:** one decision at 09:35. Rank by %change from prior close.
- **Filters:** skip chg > +15% (circuit-lock risk); skip if already
  upper-circuit; skip ASM/GSM stage ≥ 2.
- **Positions:** LONG only, top 10 after filters, equal ₹1.125L slots
  (above the ₹67k cost cliff by construction). Fill modeled at 09:36 price
  + 0.10% slippage (momentum names fill badly — modeled, not wished away).
- **Stop:** −3.0% hard from fill. Wide by intraday standards on purpose —
  the thesis is "gainers persist through the day", not "gainers never dip".
- **Exit:** 15:15 square-off. No trailing, no targets, no re-entry. One
  decision per day is the whole point.
- **Costs:** real intraday schedule — min(0.03%, ₹20)/order + STT + txn +
  GST + stamp, per the real_cost model. At this size ≈ ₹45–60/position
  round trip.
- **Index kill:** if Nifty is below −1.0% at 09:35, no entries that day
  (gainer persistence is a risk-on effect; don't fight a falling tape).

## Phase 0 — real-data backtest (on the Mac; needs yfinance/Kite bars)

Reuse the classics harness (`test-classic-swing.py` structure) with minute
or 5-minute bars, 2021 → 2026-06 train, **2026-07+ holdout untouched**, on
the survivorship-free panel — delisted symbols included, same as the hi52
verdict run.

**Pre-registered Phase 0 gates (all three, on holdout):**
1. Net edge per basket-day > 0 after full costs and slippage.
2. t-stat ≥ 2.0 on daily net returns.
3. Max drawdown of the daily equity curve ≤ 15% of deployed capital.

Fail any → lane dies here, verdict doc written, no parameter search to
resurrect it. (Sweeping N, the 09:35 time, or the stop until it passes is
the overfitting front door — the arm-band spec's rule applies here too.)

## Phase 1 — paper lane (only if Phase 0 passes)

- New engine `v5_daygain`, ₹11.25L paper capital, standard daily artifacts
  so weekly reports pick it up automatically.
- **20 sessions.** Pre-registered promotion gates:
  1. Cumulative net > 0.
  2. Beats the fleet's best intraday engine's net over the same 20 sessions.
  3. Realized slippage vs 09:36 model within 2× of Phase 0 assumption
     (else the fill model was fantasy — verdict doc, back to Phase 0).
- Kill switch: cumulative net below −₹40k at any point → stop early,
  write the verdict.

## Phase 2 — the baseline report (runs regardless of Phase 1 outcome)

One table in the weekly report, every week: DAYGAIN net vs each v5 engine
net, same capital. If the scored engines lose to the baseline for 4
consecutive weeks, that is a finding about the scoring layer, and it goes
in the research log as one.

## Falsification sentence

If Phase 0 holdout fails, day-gainer persistence at this horizon is not a
net edge after honest costs on clean data, the +₹172k ledger number was
truncation bias plus one hot regime, and the lane is dead — the reusable
residue is the baseline harness and the cost math, same as every other
killed lane.
