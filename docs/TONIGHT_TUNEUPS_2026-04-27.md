# Tonight's Tune-Ups — 2026-04-27 (post-market)

> ## ⚠️ SUPERSEDED BY IMPLEMENTATION_BRIEF
>
> **As of 2026-04-27 evening**, the authoritative plan for this week is
> `docs/IMPLEMENTATION_BRIEF_2026-04-27.md`. That brief is statistically
> grounded (Lopez de Prado deflated Sharpe + 95% CI gating) and ships 4
> tactical fixes + retirement + weekly tracker tonight, then enforces a
> 4-week observation freeze through 2026-05-25.
>
> **What shipped tonight (per the brief, not per the items below):**
> - Tasks 1.1-1.4 in `scripts/v5-paper-trade.py` (working tree)
> - Engine retirement in `scripts/launch-market.sh` (working tree)
> - ML guardrail in `prototype/v4/ml_engine.py` (working tree)
> - Weekly tracker `scripts/weekly-stats-tracker.py` + Monday 8 AM LaunchAgent
> - `docs/RETIRED_ENGINES.md`, `docs/observation_journal.md`,
>   `docs/baseline_pre_track_a_2026-04-27.txt`, `docs/TOMORROW_MORNING_CHECKLIST.md`
> - 16/16 unit tests in `tests/test_track_a.py` pass
>
> **What the items below became:**
> - Item #6 (SHORT entry quality gate via Nifty intraday %) → SUPERSEDED by brief's Task 1.1 (premarket-based, more decisive signal). My spec at `docs/research/short-entry-quality-gate-spec.md` kept for reference.
> - Item #3 (Late-start preflight + intraday regime override) → DEFERRED to post-2026-05-25 gate (no engine code changes during observation window).
> - Item #1 (ML retrain self-healing) → spec ready, ship after next missed Saturday retrain triggers it.
> - Item #2 (best_iter regression guardrail) → SHIPPED in working tree tonight.
> - Item #4 (Scorer divergence) → CLOSED — analysis showed dashboard scorer frozen since 04-02 (broken pipeline), not a real comparison anymore.
> - Item #8 (v5 proper ML training plan) → DEFERRED to post-2026-05-25 gate per brief §3.
>
> The original items are preserved below for completeness but treat the brief as the source of truth.

---


Scheduled for: after market close (15:35 IST), once EOD comparison report is reviewed.
Owner: Soumya.
Status: queued · local-only · do not commit engine code until weekend review.
Trigger context: 10:44 IST launch — v5/v5_6/v5_7 refused to start due to stale ML model (6 days old, max=3). Saturday 04-25 retrain was missed. Manually retrained 10:52 to unblock today.

## Item #1 — ML retrain self-healing on engine startup

**Trigger:** Today's launch sequence failed for the 3 main engines (v5, v5_6, v5_7) because `check_model_freshness(max_age_days=3)` in `prototype/utils/signal_guards.py:203` raised SystemExit. Saturday's scheduled retrain didn't run, so by Monday morning the model was 6 days old. Engines refused to trade — correctly, but disruptively.

**Hypothesis:** The freshness guard is the right behavior, but the recovery should be automatic. If model is stale at engine startup AND market is about to open, the engine should trigger a retrain instead of dying.

**Tonight's deliverable:**
- `docs/research/ml-retrain-selfheal-spec.md` covering:
  - Add `check_and_refresh_model()` helper in `signal_guards.py` that:
    1. Checks model age
    2. If stale and within market open window (08:30-09:15 IST), calls `scripts/retrain-ml.sh`
    3. Re-checks freshness after retrain; only abort if STILL stale
  - Propose env var `ML_AUTO_RETRAIN_ON_STARTUP=true` (default true for v5/v5_6/v5_7)
  - Add launch script step [3.5/9]: pre-flight retrain check before any engine starts
  - Telegram alert: "Auto-retrained stale model at 09:10 — engines starting"
- No engine code changes tonight. Spec + helper file only.

**Estimated time:** 45 min.

## Item #2 — Investigate `best_iter=2` regression in retrain

**Trigger:** Latest `logs/ml-retrain.log` shows "Best iteration: 2" — model converged in 2 rounds. Memory note from earlier sprint says working state was `best_iter=1726`. A 2-iteration model is essentially untrained — predictions will be near-random.

**Hypothesis:** Either (a) early-stopping threshold changed, (b) training data quality regressed (NaN explosion, feature scaling broken), (c) hyperparameter tuning was rolled back accidentally, or (d) walk-forward validation now produces a degenerate split.

**Tonight's deliverable:**
- `docs/research/ml-best-iter-regression.md` covering:
  - Diff git log of `prototype/v4/ml_engine.py` between when `best_iter=1726` was last produced (find the metadata file or commit) and today
  - Inspect today's training dataset: row count, NaN ratio per feature, target distribution
  - Re-run training with verbose=2 to see early-stopping decision
  - Compare top-feature importance: today's top-5 vs the india_vix-#1 baseline mentioned in launch script telegram
  - If regression confirmed, identify the offending change and either revert or pin hyperparameters
- This is investigation only — no model changes until root cause is clear.

**Estimated time:** 60 min.

## Item #3 — Late-start preflight + intraday regime override

**Trigger:** Today's 10:55 launch (1h 40min after market open) caused immediate deploys at intraday highs without any session-context awareness. Result: bleeding through midday despite Nifty +0.63%. JIOFIN already +4% from open when entered LONG; 5 SHORTs deployed in a rising tape because regime classifier still labeled SIDEWAYS.

**Soumya's articulation (2026-04-27 ~12:50 IST):**
> "We shouldn't directly jump into the trade. We should see today's data, how the market has been from the beginning. Let it open at 9:15. If we are entering at 1 o'clock, we should see the stocks performance from 9:15 to now to see how it is performing, then decide LONG/SHORT/sidewise — we do not jump into direct buying which will bleed like now."

**Hypothesis:** Engine deploy logic is session-time blind. It treats every scan identically whether engine started at 09:06 or 13:00. A late-start preflight that analyzes morning OHLCV before deploying would prevent buying-at-the-top.

**Tonight's deliverable:** `docs/research/late-start-preflight-spec.md` covering:

1. **Detect late start**: `engine_boot_time > 09:30` → `LATE_ENTRY_MODE = True`
2. **Pull morning OHLCV**: For each stock in universe, fetch 5-min bars from 09:15 → current
3. **Per-stock context**:
   - Open price, % move from open, intraday high/low
   - Volume vs 10-day avg
   - Last 30-min trend (UP/FLAT/DOWN)
4. **Market context**:
   - Nifty open vs current
   - % stocks green (breadth)
   - Sector heat (which sectors strong/weak)
5. **Live regime override**: If Nifty +0.5% AND breadth >55% green → force BULL regime (18/2) regardless of historical SIDEWAYS classification. Same for BEAR (Nifty −0.5% AND breadth <45% green → force BEAR 8/12).
6. **Entry filters for late mode**:
   - LONG only if `% from open < +1.5%` AND `last 30-min trend != DOWN`
   - SHORT only if `% from open > -1.5%` AND `last 30-min trend != UP`
   - Skip stocks already extended (>2.5% either direction)
7. **Size reduction on first late-scan**: 50-60% of normal Kelly size to acknowledge stale-information disadvantage
8. **Defer if too late**: If start time > 14:00, skip first deploy entirely — only manage existing positions

**Backtest plan:**
- Replay last 5 trading days assuming engine started at 10:55 each day
- Compare: actual P&L vs simulated P&L with late-start preflight
- Quantify saved ₹ per engine

**Estimated time:** 90 min (spec + helper file + backtest replay).

## Item #4 — Scorer divergence: dashboard `ai_scorer` vs engine `composite_scorer`

**Trigger:** Today's consensus check showed only 27% overlap between dashboard BUY list and engine LONG deploys (3/11 stocks). Random would be 38%. Engines are actively diverging from the dashboard scorer. Plus: 2 conflicts where engines SHORTed dashboard BUY-rated stocks (COCHINSHIP, LICHSGFIN).

**Hypothesis:** Two parallel scorers (dashboard's `ai_scorer.score_stocks` vs engines' `composite_scorer.py`) are diverging. One may be better than the other. We don't know which.

**Tonight's deliverable:** `docs/research/scorer-divergence-analysis.md` covering:
- Diff the feature inputs of both scorers
- 5-day backtest: dashboard top-20 picks (held flat 1 day) vs engine deploys (real outcomes)
- P&L per scorer head-to-head
- Recommendation: align, replace, or run both with consensus filter ("only deploy if both agree")

**Estimated time:** 60 min.

## Item #6 — SHORT entry quality gate (NEW — surfaced by deep-dive RCA)

**Trigger:** Deep-dive RCA on today (`docs/reports/2026-04-27/DEEP_DIVE_ROOT_CAUSE.md`) showed SHORTs were the dominant bleed source: combined LONG P&L +Rs 4,657 vs combined SHORT P&L -Rs 2,596 in a Nifty +0.63% day. Removing SHORTs entirely today would have doubled net P&L. The slot-partition fix (Item #1 from 04-24) is working as designed but it FORCES SHORTs into the queue every day regardless of conditions. We need a per-trade quality gate that vetoes SHORT entries when they will likely bleed.

**Hypothesis:** A 3-condition AND filter on every SHORT signal would have rejected ~80% of today's losing SHORTs. The filter does not change the slot allocation (Item #1 stays as-is) — it just adds an entry-quality check before the SHORT is deployed.

**Tonight's deliverable:** `docs/research/short-entry-quality-gate-spec.md` covering the gate logic and a backtest on the past 5 days of SHORT entries.

**Gate logic — all 3 conditions must be TRUE for a SHORT to deploy:**

1. **Market direction veto**: Nifty intraday change <= +0.30%
   - If Nifty is up >0.30%, suppress all new SHORTs (doesn't matter what the stock looks like — the tape is rising)
   - Today this single check would have blocked ~80% of SHORT deploys (Nifty was +0.63% all day)

2. **Stock momentum veto**: Stock % from open < 0 AND last 30-min trend != UP
   - The stock itself must already be showing weakness — not just the engine's signal saying weakness
   - Prevents shorting stocks that are merely "overbought by score" but trending up

3. **Sector breadth veto**: Stock's sector must be net red (>= 50% of sector stocks declining)
   - Don't short a stock whose sector peers are rallying
   - Catches sector-rotation traps where the ranked-weak stock is actually the laggard in a hot sector

**Wiring**: One new function `check_short_quality(symbol, signal, market_state)` in `prototype/v5/risk_manager.py`, called from the SHORT branch of `check_can_trade()`. Returns `(allowed: bool, reason: str)`. Ten lines of code + 4 lines of context fetch in the deploy loop.

**Backtest plan (mandatory before live):**
- Replay every SHORT entry from 2026-04-22 to 2026-04-27
- Per-day: how many SHORTs would the gate have rejected, and what was the actual P&L on those rejected vs accepted
- Acceptance bar: gate must keep WR above 65% on accepted SHORTs while not killing >40% of profitable SHORTs

**Estimated time:** 75 min (spec + helper + backtest).

## Item #7 — (existing weekend backlog, unchanged)

- v4 + v5_3 fix-or-retire batch (decide whether to keep underperformers)
- Pool-cap backtest (position sizing limits)

These remain on the weekend list, unaffected by today's stale-model issue.

---

## Tonight's Execution Order (re-prioritized after RCA)

| Priority | Item | Why this priority | Time | Touches engine code? |
|:---:|---|---|:---:|:---:|
| **P0** | **#6 SHORT entry quality gate** | Addresses today's dominant bleed source. Highest P&L impact for tomorrow. | 75 min | Spec only tonight; code on weekend |
| **P0** | **#3 Late-start preflight + intraday regime override** | Compounder of #6 — if engine starts late OR regime classifier wrong, this is the safety net | 90 min | Spec only tonight; code on weekend |
| P1 | **#1 ML auto-retrain self-healing** | Prevents today's startup trigger from recurring next time Saturday retrain misses | 45 min | Spec + helper file (no engine logic change) |
| P2 | **#2 best_iter=2 investigation** | Quality concern — needs root cause before next retrain. Investigation only. | 60 min | None (read/diff only) |
| P3 | **#4 Scorer divergence analysis** | Strategic — informs whether to align dashboard + engine scorers | 60 min | None (research) |
| Weekend | **#7 Weekend backlog** | v4/v5_3 fix-or-retire + pool-cap backtest. Untouched by today's RCA. | — | Weekend only |

**Total tonight:** ~5h 30min if all P0/P1/P2 done. P3 and weekend backlog can slip to Saturday.

**Engine-code freeze rule still applies tonight** — all P0 and P3 items are SPEC ONLY tonight. Code commits happen on weekend review (Thu 04-30 decision day per v5 observation window).

**Single highest-leverage hour tonight:** Item #6 spec + backtest. If the gate rejects 80% of bleeding SHORTs as hypothesized, tomorrow could swing from today's +Rs 1K to potentially +Rs 5-8K per engine even with the same regime mislabel.

## Today's status

- Manual retrain triggered: 10:52 IST (PID 25760)
- Watchdog stopped temporarily to prevent respawn-loop on the 3 dead engines
- After retrain completes: relaunch v5/v5_6/v5_7, restart watchdog
- Observation window Day 1 partially compromised — engines start mid-morning instead of 09:06

## Decisions Made Tonight (2026-04-27, post-market)

### D1 — Engine retirement: v4, v5_2, v5_3
**Action**: Removed from `scripts/launch-market.sh` ENGINES array. Scripts and models preserved (commented out, can re-enable). Active set is now 4 engines: v5, v5_classic, v5_6, v5_7.
**Reason**: Concentrate ML training and observation on the v5 lineage. v4 was the original; v5_2 was an F&O experiment; v5_3 was over-filtered (-Rs 52,864 cumulative).
**v4 preserved as ML substrate**: composite_scorer.py, ml_engine.py, tiered models, all data — all still actively used by v5/v5_6/v5_7 underneath. Only the standalone v4 paper-trade engine retires from the daily launch.

### D2 — ML training guardrail (Item #2 implemented in working tree)
**Action**: Added `MIN_BEST_ITERATION = 100` constant + atomic candidate→live promote pattern in `prototype/v4/ml_engine.py`. Verified: today's model (best_iter=1558) passes; 4 of 5 archived models would have been rejected.
**Reason**: Prevent silent regression. If a future retrain produces a degenerate model, the live model is preserved and a clear error fires.

### D3 — v5 proper ML training plan (Item #8 spec)
**Action**: Wrote `docs/research/v5-proper-ml-training-plan.md`. Two-phase plan: Phase A (strengthen shared v4/v5 ML stack — universe + history + features + purged CV + Optuna) for May 2-3 weekend, Phase B (v5-specific outcome model) for May 9-10 after Phase A validates.
**Reason**: The user asked for "proper ML training for v5". Phase A is the highest-leverage 14-hr spend and lifts every active engine.

## All Tonight's Specs Index

| Item | File | Status |
|---|---|---|
| #1 ML retrain self-healing | `docs/research/ml-retrain-selfheal-spec.md` | Spec ready |
| #2 Model training guardrail | (implemented in `prototype/v4/ml_engine.py`) | DONE — working tree |
| #3 Late-start preflight + regime override | `docs/research/late-start-preflight-spec.md` | Spec ready (with backtest) |
| #4 Scorer divergence | `docs/research/scorer-divergence-analysis.md` | Analysis ready |
| #6 SHORT entry quality gate | `docs/research/short-entry-quality-gate-spec.md` | Spec ready (with backtest) |
| #8 v5 proper ML training plan | `docs/research/v5-proper-ml-training-plan.md` | Plan ready |
| Engine retirement | `scripts/launch-market.sh` | DONE — working tree |
