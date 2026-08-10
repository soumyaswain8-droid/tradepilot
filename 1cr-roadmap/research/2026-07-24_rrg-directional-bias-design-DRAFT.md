# RRG Directional Bias — Design Draft

**STATUS: DRAFT — pending user review. Not implemented. No code changed.**

**Author:** Soumya Swain <soumya@suryaai.co.in>
**Date:** 2026-07-24

---

## 1. Problem

`prototype/v5/rrg_regime.py` computes a daily rotation-count signal —
`pos_def - pos_cyc`, the fraction of defensive-sector tickers beating ^NSEI
minus the fraction of cyclical-sector tickers beating ^NSEI, N=1 day
lookback. Sign convention (verified from source, `rrg_regime.py` line
100-102): **negative signal = cyclicals outperforming defensives =
risk-on / cyclical leadership; positive signal = defensives outperforming
= risk-off / defensive leadership.**

This signal passed Gate-1 on 2026-07-20 (`1cr-roadmap/research/2026-07-20_gate1-
rrg-sensor-backtest.md`, data-repair re-run: form=count, set=extended, N=1,
threshold=-0.2143 → profit-capture 85%, loss-capture 73%, PASS vs 70/70
gate) and is live in the `v5_rrg` shadow variant. But **only its binarized
form is used**: `rrg_score()` collapses the signal to CHOP(0)/TREND(100),
which `trend_mode.py`'s hysteresis turns into a single throttle — CHOP
suppresses entries, non-CHOP is vanilla sizing. The signal's *sign* (which
side is leading) is computed every day and then thrown away.

Meanwhile two audit-identified leak classes are directional in exactly the
way RRG's discarded sign could address:
- **LONG_IN_BEAR** — longs opened while the regime/tape is bearish.
- **SHORTED_RISER** — bottom-percentile shorts fired into stocks that are
  actually rallying.

## 2. Live evidence (verified against source files)

Both live days below were re-checked against the actual JSON artifacts and
audit reports rather than taken on faith from the prompt — two figures in
the prompt turned out to be imprecise (noted inline).

### 2026-07-22 — defensive-leadership day (risk-off) vs BULLISH premarket

- `docs/paper-trades/v5_rrg/2026-07-22.json`: `rrg_signal.signal = 0.1429`
  → defensive leadership → risk-off → `trend_mode = CHOP`.
- Same file's own premarket block: `overall.bias = BULLISH` (score +1,
  driver: "Global bullish (S&P +0.9%)"), `regime = SIDEWAYS`.
- This is a **disagreement**: RRG read risk-off while premarket read
  risk-on.
- Net P&L that day (`docs/paper-trades/*/2026-07-22_report.md`, "Net P&L"
  row, ground truth — see caveat below): v5 -1,984, v5_classic +452,
  **v5_cut +5,112 (fleet best)**, v5_flip +446, v5_long -1,205, v8 -178,
  v5_rrg -221. **v5_rrg was not the fleet's best net on 07-22** — v5_cut
  was, for reasons unrelated to RRG. v5_rrg did materially outperform the
  vanilla v5 engine that day (-221 vs -1,984), consistent with the CHOP
  throttle already doing its job, but it was not a fleet-wide win.

### 2026-07-23 — cyclical-leadership day (risk-on) vs BEARISH premarket/regime

- `docs/paper-trades/v5_rrg/2026-07-23.json`: `rrg_signal.signal =
  -0.3571` → cyclical leadership → risk-on → `trend_mode = TREND`.
- `docs/paper-trades/v5/2026-07-23.json` (the vanilla engine's premarket,
  which v5_rrg's own premarket block that day did *not* independently
  match — see below): `gap_prediction = {direction: DOWN, magnitude_pct:
  -0.32, confidence: 0.75}`, `overall.bias = BEARISH` (score -1), regime =
  `BEAR`. This matches the prompt's cited numbers exactly.
- v5_rrg's *own* premarket block that day (`v5_rrg/2026-07-23.json`) is
  actually `overall.bias = NEUTRAL` (gap read FLAT -0.26% @ 0.6 conf, a
  slightly different premarket snapshot than v5's), but `regime = BEAR` is
  shared across variants. Either way, RRG's directional read
  (risk-on/cyclical) disagreed with the fleet's regime call (BEAR) and
  with the vanilla engine's premarket bias (BEARISH).
- Net P&L that day (`*/2026-07-23_report.md`, "Net P&L" row): v5 +709,
  v5_classic +943, v5_cut -743, v5_flip -27, v5_long -296, v8 -352,
  **v5_rrg +1,036 (fleet best)**. Confirmed: v5_rrg *was* the best net
  performer on 07-23. **The magnitude is Rs 1,036, not the Rs 532 cited in
  the prompt** — corrected here.
- Leak classes that day, from `docs/audit/2026-07-23_audit-report.md`:
  `LONG_IN_BEAR`: 20 trades, **Rs -2,190 realized / Rs 4,378 "on the
  table"** (the report's 2x-of-loss recoverable-opportunity column — the
  prompt's "Rs 4.4k" matches this "on the table" figure, not the realized
  loss). `SHORTED_RISER`: 35 trades, **Rs -1,590 realized / Rs 3,177 on
  the table**. Across the last ~3 weeks of audits, SHORTED_RISER's daily
  "on the table" figure ranges roughly Rs 1.3k–5.8k, so "~Rs 3k/day" is a
  reasonable order-of-magnitude, not a precise daily constant.
- Fleet trade book that day: 111 trades, 26 long / 85 short
  (`2026-07-23_audit-report.md` bottom line). v5_classic individually ran
  18 long / 40 short. **The prompt's "18-short book" does not check out
  literally** — v5_classic's 18-count was its *long* leg, not short; its
  short leg was 40. The fleet-wide short skew (85 of 111 trades) into a
  morning rally is real and is the substrate SHORTED_RISER measures, but
  the specific "18" figure should not be repeated as "18 shorts."

### Net verdict on "2-for-2"

Directionally, yes: RRG's sign disagreed with the premarket/regime stack
on both 07-22 (risk-off vs BULLISH premarket) and 07-23 (risk-on vs
BEARISH premarket/BEAR regime) — two different disagreement directions on
two consecutive live days. But only 07-23 shows RRG's side "winning" on
P&L; 07-22 shows the CHOP throttle merely limiting damage relative to
vanilla, not leading the fleet. **This is a 2-session anecdote, not a
pattern — treat it as the trigger for a backtest, not as evidence the
directional read is validated (see §3).**

## 3. The evidence gap — what Gate-1 did and did not validate

`1cr-roadmap/research/2026-07-20_gate1-rrg-sensor-backtest.md` validated a
**binary CHOP/TREND classifier against loss-capture**: does flagging a day
CHOP correlate with days v5's *existing* long/short mix actually lost
money on (the "CHOP vs non-CHOP P&L split" table, e.g. CHOP-flagged days
summed to -10,710, TREND days to -2,738, in the original spread/base run).
Profit-capture/loss-capture are classification-quality metrics for **"is
today risky enough to throttle,"** computed against the fleet's *existing*
trade mix — not against which side (long vs short) was correct. Gate-1
never scored the sign of the signal against realized market direction, and
never split P&L by long-book vs short-book performance conditioned on the
sign. **Using RRG's sign as a directional bias input is an unvalidated
extrapolation from a passed gate that tested something else.** This gap is
the reason §5 proposes a distinct backtest before any live directional use.

## 4. Design options

### (a) RRG as one more premarket vote

`prototype/v5/premarket_intel.py::get_premarket_intel()` sums three ±1
votes (gap_prediction, fii_signal, global_sentiment) into `score ∈
[-3,+3]`, then maps score→bias/multiplier via fixed thresholds (score≥2→
BULLISH 1.0x … score≤-2→BEARISH 0.3x). RRG becomes a 4th ±1 vote: negative
signal (cyclical/risk-on) = +1, positive (defensive/risk-off) = -1, using
the already-Gate-1'd THRESHOLD=-0.2143 as the zero-crossing, or a
new dead-zone. Cheapest to build (one function, one line in the sum);
cheapest to reason about, since it reuses the existing vote-sum machinery
verbatim.
- *Con:* it dilutes into a 4-way average — the same mechanism that
  currently produces the wrong day-calls (BULLISH bias on 07-22, BEARISH
  on 07-23) would still be wrong on those two days even with RRG voting,
  because RRG is 1 of 4 votes and the other 3 didn't move. A single new
  vote is unlikely to flip score across a threshold boundary on the days
  that matter most.

### (b) RRG veto rules only — asymmetric, targeted at the named leaks

No change to the premarket score math. Two one-directional gates layered
on top of `signal_engine.py`'s allocation and `v5-paper-trade.py`'s
BEARISH-bias size-down path:
- **Cyclical-leadership day** (signal below threshold) → block any
  BEARISH-bias-driven size/entry downgrade, AND block bottom-percentile
  SHORT allocation (the `sell_count`/`rank > n - sell_count` branch in
  `signal_engine.py` lines ~190-208) — maps directly to SHORTED_RISER.
- **Defensive-leadership day** (signal above threshold, i.e. today's
  existing CHOP flag) → block fresh LONG adds — maps directly to
  LONG_IN_BEAR.
- Smallest surface area: touches two existing decision points rather than
  the shared bias score used identically by all v5 variants. Easy to
  isolate in a shadow without disturbing v5_rrg's already-passed
  CHOP-throttle behavior.
- *Con:* two new threshold-gated branches is still a calibration surface,
  just a smaller one than (c).

### (c) Full directional tier replacing the premarket bias source

Promote RRG's 3-way read (risk-on / risk-off / neutral, via a
signal-magnitude dead-zone around the Gate-1 threshold) to the *primary*
bias input, demoting gap/fii/global to secondary or tie-break signals.
Most expressive, most disruptive — replaces a component used identically
across v5, v5_classic, v5_cut, v5_flip, v5_long, v8. A single sensor with
only 2 anecdotal live days and no directional backtest becomes the
fleet's primary bias source.
- *Con:* highest blast radius for the least amount of validation. Not
  recommended as a first move.

### Trade-offs vs the calibration-surface lesson

The TrendScore sensor burned three recalibration passes this week trying
to find a chop/trend threshold pair that cleared Gate-1 (commits
`96c1506`, `a55908c`, `8e43b96`, `ba25d80` — final verdict still FAIL).
The lesson: **do not hand-tune a new threshold against 2 live days.**
Whichever option is chosen, any new threshold (a directional dead-zone,
a veto trigger level) must go through the same backtest-gated process
that RRG's CHOP threshold already went through — not be picked to make
07-22/07-23 look good in hindsight. Option (b) is the safest starting
point precisely because it can reuse the *already-validated* -0.2143
threshold rather than opening a second calibration surface immediately.

## 5. Gate-1 backtest plan for DIRECTIONAL skill (proposed, not run)

A new, separate gate — passing the existing CHOP-classification Gate-1
does not carry over (§3).

- **Harness:** reuse `scripts/backtest-rrg-sensor.py`'s session iteration,
  `_day_signal_inputs`/`_signal` computation, and no-lookahead assertion
  machinery (`_sessions()`, `_fetch_daily()`, `_rel()` — same close-price
  loading, same fail-closed set-membership handling).
- **New metric 1 — day-call accuracy:** for each session, label RRG's sign
  (cyclical-lead=risk-on vs defensive-lead=risk-off) and compare against a
  realized-direction ground truth — proposed: next-session ^NSEI
  close-to-close return sign, cross-checked against which book (long vs
  short) was net profitable that day across the fleet's own trade-audit
  data (`docs/audit/*_trade-audit.jsonl`, already itemized by direction).
- **New metric 2 — P&L split by predicted side:** for cyclical-lead days,
  sum realized long-book P&L vs short-book P&L fleet-wide; for
  defensive-lead days, same split. A genuinely useful directional signal
  should show long P&L concentrated on risk-on days and short P&L (or
  avoided-long losses) concentrated on risk-off days.
- **Proposed pass bar:** mirror Gate-1's 70/70 structure but for
  direction — e.g. ≥65% day-call accuracy AND a positive P&L differential
  (predicted-side P&L minus opposite-side P&L) on at least 65% of
  classified sessions, evaluated over the full available archive.
  **Flag explicitly: the archive is currently ~21-30 sessions, the same
  thin-sample caveat Gate-1 itself carried** — a directional bar should
  probably be held to more sessions than the CHOP bar was, precisely
  because directional mistakes (wrong-side leverage) are more expensive
  than a missed throttle.
- **No-lookahead constraint:** identical to the shipped sensor — `t-1`
  closes only, enforced the same way `rrg_regime.py`'s docstring specifies
  ("the CALLER must ensure only closes strictly before the session date
  being scored are passed in") and the way `v5-paper-trade.py`'s
  `REGIME_SENSOR=rrg` path already drops same-day bars before calling
  `rotation_signal()`. No new lookahead risk is introduced by scoring
  direction instead of CHOP — same inputs, same cutoff, different label.

## 6. Rollout

**Shadow first — do not touch `v5_rrg`.** `v5_rrg` is the only variant
carrying a Gate-1-passed, live-validated CHOP throttle; mutating it to
also test directional logic would confound future recalibration
comparisons (can't tell if a P&L change came from the throttle or the new
veto/vote). Recommend a **new shadow clone** (e.g. `v5_rrg_dir`) that
inherits `v5_rrg`'s current CHOP-throttle config unchanged and layers
option (b)'s veto rules on top, so it can be A/B'd against `v5_rrg` itself
as the control. Only after the §5 backtest passes on the new variant's
own live run (not the 2-day anecdote) should promotion to a non-shadow
variant, or backport into `v5_rrg` directly, be considered.

## 7. Open questions (with leans)

1. **Which option to backtest first?** Lean: **(b)**, asymmetric veto —
   smallest surface area, directly targets the two named leak classes,
   reuses the existing bias-score math unchanged for all other variants.
2. **What threshold defines "leadership strong enough to veto"?** Lean:
   start with the already-validated -0.2143 CHOP threshold rather than
   opening a second calibration surface; only introduce a distinct
   directional threshold if the §5 backtest shows -0.2143 is a poor
   directional cutoff specifically.
3. **How many sessions before promoting from shadow?** Lean: don't
   promote on fewer than ~20-30 directionally-labeled sessions — roughly
   Gate-1's own sample size, arguably more given the higher cost of a
   wrong-side veto vs a missed throttle.
4. **Does the veto stack with or replace the current CHOP throttle?**
   Lean: **stack** (additive) — the CHOP throttle already passed its own
   gate; a directional veto should not risk regressing it. Veto logic
   should be inert on days the throttle already suppresses activity.
5. **Ground truth for "day-call accuracy" (§5)?** Lean: use fleet
   long-vs-short realized P&L split as the primary label (it's directly
   what the veto is meant to protect), with next-day ^NSEI return sign as
   a secondary/independent cross-check — don't rely on ^NSEI sign alone,
   since a correct macro call can still coexist with a fleet that's
   stock-picking badly within that direction.
