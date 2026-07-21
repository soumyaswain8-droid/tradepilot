# SELL-Tier Scorer Gap — Design

> **STATUS: DRAFT — pending user review, not approved for implementation.**
> Author: Soumya Swain <soumya@suryaai.co.in>. Research + design only; no
> code changed as part of this document.

---

## 1. Problem + evidence

On 2026-07-20 (regime: SIDEWAYS) `prototype/ai_scorer.score_stocks()` — the
scorer behind `docs/dashboard-scores/*.json` and the dashboard's stock-detail
panel in `prototype/app.py` — scored 393 stocks: **62 BUY / 94 HOLD / 237
AVOID / 0 SELL** per the captured JSON (`docs/dashboard-scores/2026-07-20.json`,
`Counter({'AVOID': 237, 'HOLD': 94, 'BUY': 62})`). `docs/audit/2026-07-20_audit-report.md`
cites the same-shaped numbers as "147 BUY / 121 HOLD / 237 AVOID / 0 SELL"
(§ line 51) — the AVOID=237 and SELL=0 figures match exactly; the BUY/HOLD
split differs because the audit's citation appears to be from a different
intraday scan capture than the EOD dashboard-scores snapshot. Either way,
**SELL is structurally zero** — not a bad day, a bad day for the label to
even exist.

The audit's counterfactual (line 10, line 52): shorting the dashboard's
worst-scored (AVOID) names that actually fell, at Rs 30,000/name, would
have made **Rs 4,197** that day. Instead, the two engines that do trade
shorts posted losses on their short book: 27 `SHORTED_RISER` trades (shorting
a name that then rose against the short) left **Rs 3,038 on the table**
(line 25: `| SHORTED_RISER | 27 | Rs -1,518 | Rs 3,038 |`).

### Recurrence — this is not a one-off

Every `docs/dashboard-scores/*.json` snapshot from 2026-04-23 through
2026-07-20 (55 captured days) shows `sell_count: 0`. The scorer has never
once emitted SELL in the archived record:

| Date range | Days sampled | SELL count | Note |
|---|---|---|---|
| 2026-04-23 → 2026-07-20 | 55 | 0 every day | `ai_scorer.score_stocks` has no SELL branch (§2) |

`SHORTED_RISER` cost, last two audited weeks (from the engines' own SELL/SHORT
path, § 2 — not the scorer):

| Date | SHORTED_RISER count | Realized loss | Est. cost if avoided |
|---|---:|---:|---:|
| 2026-07-06 | 30 | Rs -2,541 | Rs 5,081 |
| 2026-07-07 | 19 | Rs -816 | Rs 1,632 |
| 2026-07-09 | 32 | Rs -2,074 | Rs 4,147 |
| 2026-07-14 | 23 | Rs -1,087 | Rs 2,174 |
| 2026-07-15 | 15 | Rs -2,119 | Rs 4,236 |
| 2026-07-16 | 35 | Rs -2,859 | Rs 5,719 |
| 2026-07-17 | 39 | Rs -1,524 | Rs 3,047 |
| 2026-07-20 | 27 | Rs -1,518 | Rs 3,038 |

(`2026-07-08`, `2026-07-10`, `2026-07-13` audits have no `SHORTED_RISER` line
— either no shorts that day or a green day where the short-block suppressed
entries.) Every audited day since 2026-06-08 repeats the same prescription
almost verbatim: *"never short a stock that's green on the day — short only
below VWAP"* (27 of 30 audit reports in `docs/audit/` contain this exact
phrase). A standing prescription repeated in 27 consecutive reports without
being implemented is itself a signal that this needs to move from "note in
the audit" to "gate in code."

### Root cause — `ai_scorer.score_stocks` has no SELL label at all

`prototype/ai_scorer.py:242`:

```python
direction = "BUY" if score >= 50 else "HOLD" if score >= 35 else "AVOID"
```

This is a hard 3-way partition of the model's `predict_proba` output — there
is no branch, threshold, or code path that can ever produce `"SELL"`. It is
not a mis-calibrated threshold; the label is **absent from the function**.
`prototype/app.py:699` duplicates the same 3-way pattern for a different
score cut (`BUY >= 55 / HOLD >= 40 / AVOID`), and the dashboard's per-stock
detail copy (`prototype/app.py:2820-2822`) confirms the UI never recommends
a short even for AVOID names — it says *"consider shorting"* as throwaway
prose, not an actionable field. So both the batch scorer and the live
dashboard display share the same gap: bearishness saturates at "AVOID",
there is no lower tier.

## 2. Current short path (what actually drives shorts today)

The engines that *do* place shorts (v5, v5_classic — 18 and 30 shorts
respectively on 07-20 per the audit) do **not** consume `ai_scorer.py` at
all. Their SELL signal comes from a completely separate module,
`prototype/v5/signal_engine.py`, which:

1. Scores the universe via `prototype.v4.composite_scorer.score_all_stocks`
   (not `ai_scorer`), sorted by score descending.
2. Applies **regime-aware percentile cuts** (`signal_engine.py:41-44,
   174-181`): top 20% (10% in BEAR) = BUY, bottom 20% (10% in SIDEWAYS, 0% in
   BULL) = SELL candidate pool.
3. Gates each bottom-percentile candidate through a "Fix #1" weakness check
   added 2026-04-28 after an RCA (`signal_engine.py:46-53, 190-208`):

   ```python
   SHORT_REQUIRE_NEGATIVE_CHANGE_PCT = float(os.environ.get("SHORT_REQ_CHG_PCT", "-0.5"))
   SHORT_REQUIRE_MAX_SCORE = float(os.environ.get("SHORT_REQ_MAX_SCORE", "35"))
   ...
   actually_weak = (stock_change < SHORT_REQUIRE_NEGATIVE_CHANGE_PCT and
                    stock_score < SHORT_REQUIRE_MAX_SCORE)
   if actually_weak:
       direction, pos = "SELL", "SHORT"
   else:
       direction, pos = "HOLD", "NONE"   # bottom-ranked but not force-shorted
   ```

So today's shorts are **rank + intraday-change-at-scan-time gated**, not
VWAP-confirmed and not persistently re-checked. `score_for_short()`
(`signal_engine.py:56-87`) does compute a `below_vwap` boolean and folds it
into a `short_score` weighting, but that value is descriptive metadata on
the signal (feeds `short_metrics` for logging/sizing), not a hard gate —
a candidate can be shorted while still above VWAP as long as it clears the
`change_pct < -0.5%` bar at the scan instant. That instant reading is the
likely SHORTED_RISER mechanism: a name dips below the -0.5% bar early in a
scan window, gets shorted, then rallies back through the rest of the session
— the entry condition was never re-verified against VWAP or against the
day's running direction.

Separately, `_short_block_active()` (`v5-paper-trade.py:95-105`) suppresses
*all* SELL entries for the first `SHORT_BLOCK_WINDOW_MIN` (default 60) min
when premarket is bullish and gap-up exceeds `SHORT_BLOCK_GAP_PCT` (0.5%) —
a pre-existing partial mitigation for the same wrong-direction-short failure
mode, but it only covers the open window, not the VWAP-confirmation gap
described above.

**Net**: "the dashboard's top SELLs" language in the audit is informal — the
dashboard has no SELL field to point to (§1); the audit's counterfactual is
constructed post-hoc from the AVOID list sorted by realized fall. The
engines' actual shorts come from a second, disconnected scorer
(`v4.composite_scorer` via `signal_engine.py`) whose weakness gate is
directional-magnitude-based, not VWAP-persistence-based, which is
consistent with why VWAP is the audit's repeated prescription rather than
something already enforced.

## 3. Candidate approaches

### (a) Minimal engine-side SELL filter — no scorer change

Leave `ai_scorer.py` alone. In `signal_engine.py`'s existing weakness gate
(§2, `signal_engine.py:190-208`), add a hard VWAP-confirmation term
alongside `SHORT_REQUIRE_NEGATIVE_CHANGE_PCT`/`SHORT_REQUIRE_MAX_SCORE`:
short candidates must show `change_pct < 0` (red on the day, not just below
a -0.5% bar) **AND** `not above_vwap` at the moment of entry — i.e. promote
`score_for_short()`'s existing `below_vwap` field (currently descriptive
only, §2) to a hard AND condition, matching the audit's literal
prescription. Zero new model surface; reuses fields already computed.

- **Pro**: smallest change, directly implements the standing (27x-repeated)
  prescription, testable against the existing SHORTED_RISER trade log with
  no new data pipeline.
- **Con**: does not touch `ai_scorer.py` / dashboard-scores at all — the
  0-SELL dashboard gap (§1's root cause) persists; only the *engines'*
  wrong-way shorts improve. If the dashboard/missed-opportunities report is
  itself a product surface someone reads, this leaves it broken.

### (b) True scorer SELL tier — symmetric bearish scoring

Add a real SELL branch to `ai_scorer.score_stocks()` (and/or the app.py
duplicate), e.g. `direction = "SELL" if score <= 15 else "AVOID" if score <
35 else ...` — but naively lowering the AVOID floor just relabels the
bottom of the existing distribution and inherits the exact bug `signal_engine.py`
already had to patch (RCA 2026-04-28): bottom-percentile/bottom-score ≠
bearish that day. A real symmetric tier needs its own bearish feature set
(the model here is a single `predict_proba` binary-classifier score, not an
independently-trained short model) — i.e., either a second model trained on
"stock closes down N% from here" as the positive class, or a hand-built
`short_score` analogous to `signal_engine.score_for_short()` bolted onto
`ai_scorer.py`.

- **Pro**: fixes the actual root cause — dashboard-scores and the
  missed-opportunities report get a real SELL tier, closing §1.
- **Con**: new calibration surface. `ai_scorer.py`'s model has no bearish
  training target today; retrofitting one risks repeating the TrendScore
  lesson (`docs/research/2026-07-17_gate1-trend-sensor-backtest.md`,
  commit `ba25d80`) — three calibration passes on a hand-tuned multi-term
  score still failed Gate-1 (70% capture / only 54% on the side that
  mattered). A hand-built bearish score with multiple free weights
  (`weakness*0.40 + rel_weakness + vol_confirm + below_vwap + orb_breakdown
  + rs_weak`, mirroring `signal_engine.py:72-77`) has the same
  many-free-parameters risk profile that sensor had.

### (c) Hybrid — bottom-percentile SELL + engine-side confirmation gate

Scorer emits a candidate SELL from the bottom percentile of `ai_scorer`'s
existing score (no new model, reuses what's already computed — cheap,
symmetric with how BUY already works off the same score). The *engine* then
applies the (a)-style hard confirmation gate (red-on-day AND below-VWAP)
before a candidate SELL becomes an actual SHORT `TradePlan`. This mirrors
exactly the two-stage structure `signal_engine.py` already has (percentile
rank → weakness gate) — just relocates stage 1 into `ai_scorer.py` so the
dashboard also gets a populated SELL field, and hardens stage 2 to match the
audit's literal VWAP prescription instead of the looser
`change_pct < -0.5%` bar in place today.

- **Pro**: closes both gaps (§1 dashboard + §2 engine execution) with the
  fewest new free parameters — no new model, reuses the percentile-cut
  pattern already validated (in the sense that it's live and understood) in
  `signal_engine.py`. Confirmation gate is a boolean AND, not a weighted
  score — smallest calibration surface of the three options.
- **Con**: two systems (`ai_scorer.py` for dashboard, `signal_engine.py` for
  live engines) still exist in parallel and could drift; this doesn't
  unify them, it duplicates the pattern into the second one.

**Recommendation: (c), phased so (a)'s engine-side gate ships first.** The
engine-side VWAP gate (a) is the highest-confidence, lowest-risk fix — it
directly encodes 27 audit reports' worth of the same prescription, needs no
new calibration, and is backtestable immediately against the existing
`SHORTED_RISER` trade log. Ship it standalone first (it has value even if
the dashboard SELL tier never lands). Then add the bottom-percentile SELL
label to `ai_scorer.py` (closing the dashboard gap) reusing the same
percentile-cut mechanics already proven in `signal_engine.py`, rather than
(b)'s from-scratch bearish model. Explicitly defer any hand-tuned
multi-term `short_score` (the (b)/(c)-adjacent weighted formula) until the
simpler percentile+boolean-gate version's Gate-1 result says it's needed —
same "fewer free parameters first" order the TrendScore postmortem
recommends.

## 4. Gate-1 test plan

**Data**: `docs/dashboard-scores/*.json` (55 archived days, 2026-04-23 →
2026-07-20) for scores/ranks at capture time, joined to same-day outcome
data already used by the audit pipeline (`docs/audit/*_audit-report.md` /
`docs/audit/*_trade-audit.jsonl` — has realized change_pct, VWAP-relative
position, and the existing `SHORTED_RISER` labeling logic to reuse
directly).

**No-lookahead rule**: candidate SELL/SHORT signal must be constructed from
data available at scan time only — `ai_scorer` score + `change_pct` +
`above_vwap` as of that scan's timestamp, exactly as `signal_engine.py`
already does for its live gate (§2). Outcome (did the trade end profitable,
did SHORTED_RISER fire) is read from the *same trading day's* close/EOD
data, never a later day. This mirrors the RRG design doc's explicit
constraint (`docs/superpowers/specs/2026-07-20-rrg-regime-sensor-design.md`:
"the score for day t uses daily closes up to t-1 only") adapted to
intraday: score/gate inputs must all be ≤ the scan timestamp.

**Cost model**: reuse the audit's own per-trade sizing (Rs 30,000/name, per
`docs/audit/2026-07-20_audit-report.md` line 10) and its existing
SHORTED_RISER win/loss bookkeeping (`Realized loss` / `Est. cost if avoided`
columns already computed per trade in the audit JSONL) rather than inventing
a new cost model — no separate commission/slippage model was found in the
engines' short path beyond what the audit already applies; flag this as an
open question (§6) rather than assume one.

**Pass bar (proposed)**: over the backtest window,
1. Hypothetical short book (candidate SELLs that clear the new gate) is net
   positive after the audit's per-trade cost accounting, **and**
2. SHORTED_RISER-style errors (shorted name closes green vs. entry) drop
   below **15%** of gated short candidates, down from the current unfiltered
   rate — 27-39 SHORTED_RISER trades against total short counts of ~18-30
   *positions* per engine per day in the recent sample implies most/all
   short entries are currently mis-flagged some portion of the day; the
   15% bar is a starting proposal, not derived from a prior baseline
   measurement — flag for calibration once the backtest harness runs.

Both conditions must hold; a profitable book that's still mostly wrong-way
(condition 1 passing on a few large winners) should not pass Gate-1, per the
same asymmetric-capture lesson TrendScore's Gate-1 (70/70 on both sides)
enforced.

## 5. Phased rollout

Standard house convention (Phase 0 log-only → shadow → promote), as already
used for `RiskGate` (`docs/research/2026-07-20_risk_gate_three_state_verdict.md`,
wired log-only in `scripts/v5-paper-trade.py:479-576`):

- **Phase 0 — log-only candidate artifact.** Compute the (c)-style
  bottom-percentile SELL + VWAP/red-day confirmation gate inside
  `signal_engine.py` (or a sibling module) but do not change which
  candidates become live `TradePlan`s. Append candidate SELLs + gate
  pass/fail to a daily artifact (`docs/paper-trades/<engine>/YYYY-MM-DD_sell_candidates.json`,
  mirroring the existing `_verdicts_file()` pattern at `v5-paper-trade.py:489-490`).
- **Shadow variant.** Run the confirmation-gated short path as its own
  engine variant (pattern already established: v5_cut, v5_flip, v5_chop,
  v5_rrg all exist as isolated variants under `docs/paper-trades/`) so it
  accumulates its own P&L record without touching v5/v5_classic capital.
- **Promote.** Only after Gate-1 (§4) passes on the shadow variant's own
  live trades (not just the retrospective backtest), swap the gate into
  the primary engines' short path, same promotion bar used elsewhere in
  this codebase (RiskGate's `RISK_GATE_DRIVE=1` staged promotion is the
  most recent precedent).

**Interactions to account for**:
- **RiskGate.** A SELL/SHORT plan is just a `TradePlan` with
  `side="SHORT"` flowing through the same `RiskGate.evaluate(plan,
  position_type="SHORT")` path already live (`risk_gate.py:119,149,153`) —
  no new gate wiring needed, the confirmation filter sits *upstream* of
  `_build_trade_plan`/`_log_risk_gate_verdicts`, same position as
  `signal_engine.py`'s existing weakness gate today.
- **Regime sensors.** Bear-day/CHOP-day shorts are exactly the days
  `v5_rrg`'s sector-rotation sensor and `v5_chop`'s TrendScore sensor are
  meant to flag (defensive-rotation / low-tape-efficiency days per the RRG
  design doc §1-2). The SELL-tier confirmation gate and the regime sensors
  are complementary, not redundant: the sensor says *when* the book should
  lean short-friendly (regime-level), this design says *which names*
  clear a confirmed-weak bar (name-level) — but note `signal_engine.py`
  already varies `sell_count` by regime (BEAR 20%, SIDEWAYS 10%, BULL 0%,
  `signal_engine.py:174-181`), so any new regime sensor output should feed
  that same percentile-count parameter rather than create a second regime
  read that could disagree with it (the same v4-vs-v5-regime-disagreement
  bug already fixed once, per the comment at `signal_engine.py:142-144`).

## 6. Open questions (with leans)

1. **Does a per-trade cost/slippage model exist beyond the audit's flat
   accounting?** Not found in this pass — leaning toward "no, the audit's
   Rs 30k/name convention is the only cost model in use," but worth a
   direct check of `scripts/v5-paper-trade.py`'s position-sizing/exit-cost
   code before Gate-1 locks in a pass bar.
2. **Should the 15% SHORTED_RISER-rate pass bar be measured, not guessed?**
   Lean: yes — before writing the Gate-1 harness, compute the *actual*
   current SHORTED_RISER rate as a fraction of gated short entries (not
   just absolute counts) across the 55-day sample, and set the bar as a
   relative improvement (e.g. "cut current rate by half") rather than an
   absolute 15% picked without a baseline.
3. **Does `ai_scorer.py` even need touching, or is (a) alone sufficient?**
   Lean: ship (a) first regardless (§3 recommendation) and treat closing
   the dashboard's `sell_count: 0` gap as a separate, lower-urgency
   follow-up — the trading P&L impact (SHORTED_RISER cost) is entirely in
   the engine path, not the dashboard display.
4. **Is `SHORT_REQUIRE_NEGATIVE_CHANGE_PCT`/`SHORT_REQUIRE_MAX_SCORE`
   (currently -0.5% / 35, env-tunable) still the right pair once a hard
   VWAP AND is added, or does the VWAP condition make the change_pct bar
   redundant?** Lean: keep both — VWAP-relative and day-change are
   correlated but not identical (a stock can be below VWAP while still
   green vs. yesterday's close on a strong open), so the two conditions
   catch different mis-short cases; re-tune the change_pct threshold only
   after the VWAP AND is live and its own effect is isolated in the
   backtest, not both at once (avoids conflating two changes' effects,
   same instinct as the TrendScore "fewer free parameters first" lesson).
