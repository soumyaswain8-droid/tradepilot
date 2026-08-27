# Lane: forced flows — index rebalances, month/quarter-end

**VERDICT: not viable (index rebalance: needs data we do not have; calendar flows: dead out-of-sample)**

## THE NUMBER
- Turn-of-month (the only thing that looked real): +0.748%/event gross, n=58, t=4.18 full sample.
  Net of delivery costs at Rs100k: +0.514%/event, t=2.88, MDD -11.6%.
  **Holdout (2024-06 → 2026-06, n=24): -0.136% gross, t=-0.52; net -0.370%/event ≈ -4.4%/yr. Sign inverts.**
- Index add/delete, market-neutral: ADD n=8, +0.78% over +1..+10d, t=0.25. DEL n=6, +5.99%, t=2.98 —
  but the generalised version (below) is t=0.72. The n=6 result is event-selection noise.
- Quarter-end "deletion-like" rebound, generalised: +0.33%, n=285, t=0.72. Non-quarter-end days: -0.17%, t=-2.88.

## WHAT I TESTED
(1) **Can we even find rebalance dates?** Built an abnormal-turnover detector on sf_turn.parquet
(turnover / trailing-60d median, then divided by the cross-sectional median to strip market-wide
activity). The top cluster dates are **not** rebalance days — they are the June-2024 post-election
smallcap frenzy and May-2026. Checked the detector against 14 hand-coded Nifty-50 changes
(ADANIENT/SHREECEM 2022-09-30 … JIOFIN/ZOMATO/BPCL/BRITANNIA 2025-03-28): median relative
turnover spike was **1.2x for adds, 1.7x for deletes**, versus a 15x detection threshold. Rebalance
flow is invisible in daily totals — for Nifty-50 names, Indian index-fund AUM is small relative to
normal daily turnover, and the flow executes in the closing auction, which daily bars average away.
(2) Event study ±10d around those 14 events, market-neutralised against an equal-weight liquid-300 book.
(3) Generalised the "deleted stock reverts" pattern: worst-15 liquid 10-day losers bought on
quarter-end close, held 10 days, excess vs liquid-300 — 19 quarter-ends, n=285 stock-events.
(4) Turn-of-month: equal-weight liquid-300 return at every lag k = -3…+5 around the last trading day
of all 59 months, split train (pre-2024-06) / holdout.

## WHY IT FAILED — the arithmetic
- **Rebalance lane: no data.** We hold no index-membership history. The 14 events I could hand-code
  are (a) too few for any t-stat, (b) recalled from memory, so they carry my own selection bias, and
  (c) the flow is not detectable from daily turnover, so we cannot bootstrap a larger event set from
  the panel. Ruling this in or out needs **NSE index-maintenance circulars (announcement date,
  effective date, symbol, index, add/delete) for all Nifty 50/Next 50/Midcap 150/Smallcap 250 reviews,
  2021-2026** — roughly 400-600 events — plus closing-auction volume. Neither is on disk.
- **Turn-of-month is in-sample beta.** In-sample it earned 6.2%/yr net while the same liquid-300 book
  held continuously earned 0.0597%/day ≈ **14.8%/yr**. So the "edge" underperformed doing nothing
  even before it broke. Out-of-sample it is negative. Costs are not what killed it — the effect is.
- **Quarter-end reversal is just reversal, and a weak one.** +0.33% gross vs 0.234% delivery cost
  (0.2% STT + 0.015% stamp + Rs18.80 DP on a Rs100k position) leaves +0.10% at t=0.72. At a Rs25k
  position the DP fee alone is 0.075% and the residual is +0.02%. Only ~4 quarter-ends/yr × 15 names
  = 60 opportunities/yr; at Rs100k each that is Rs1.5m of capital deployed for a coin flip.

## Survivorship note
All of the above used sf_ret/sf_turn (3046 symbols incl. 417 that stopped trading). This matters
specifically here: index deletions are the exact names a survivor-biased panel drops. The
deletion-side results are therefore honest — they are just not significant.
