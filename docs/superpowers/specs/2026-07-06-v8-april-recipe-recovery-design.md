# v8 Twin-Shadow — April-Recipe Recovery (Design Spec)

*Date: 2026-07-06 · Author: Soumya Swain / Claude · Status: Approved design, pre-implementation*

## 1. Problem

`DEGRADATION_ANALYSIS_Apr-Jul_2026.md` documents a monotonic decay of the v5 engine:
live v5 went from **+1.35%/day at 77% win rate (April)** to **−0.24%/day at 46% (July)**.
The report's verdict: this is not a broken concept but a **complexity cascade** that diluted a
proven engine. The proof it can work is our own April data. The prescribed fix is to **revert to
the April recipe**, not reinvent — and to add complexity back **one variable at a time, measured**.

The April engine that printed money was: **NIFTY-50, top-5, long-only, +1.5/−0.75 fixed bracket,
early (~09:20) entry, flat by EOD.** The live engine has drifted to: NIFTY-200, up to 20 positions,
long+short, 3.0% target with 0.7% trailing stop, late entry via a rescore loop, plus a (now
weight-0) overfit ML factor.

## 2. Goal

Build a **twin-shadow** paper experiment that (a) reproduces the April recipe cleanly and (b) tests
whether a *minimal* 5-tree ML tie-breaker adds value — with the two isolated so the ML's marginal
contribution is directly measurable.

**Non-goals:** touching any running engine's behavior; reinventing the strategy; adding shorts, ML
complexity beyond 5 trees, or new dashboards; changing the NIFTY-200 dashboard universe used elsewhere.

## 3. Chosen approach — Twin shadow (option C)

Two new engines that differ by exactly one env var:

| Engine | Role | Difference |
|---|---|---|
| **`v8`** | Control — pure April replica | `ML_SCORE_WEIGHT=0` |
| **`v8_ml`** | Treatment — April + 5-tree tilt | `ML_SCORE_WEIGHT≈0.10` (5-tree model) |

Because everything else is identical, `v8_ml − v8` P&L/WR **is** the 5-tree's marginal effect. This
directly answers "does minimal ML help selection?" as a controlled single-variable test, matching
the report's "add back one thing at a time, measured" discipline.

## 4. Architecture & isolation

Engines in this repo are ~15-line wrappers that set env vars and then `runpy.run_path` the shared
`scripts/v5-paper-trade.py`. Pattern reference: `scripts/v5_long-paper-trade.py`,
`scripts/v5_cut-paper-trade.py`.

- `scripts/v8-paper-trade.py` — wrapper, sets April-recipe env + `ML_SCORE_WEIGHT=0`.
- `scripts/v8_ml-paper-trade.py` — same env + `ML_SCORE_WEIGHT=0.10` + points at the 5-tree model.
- Registered as two new entries in the `ENGINES` array in `scripts/launch-market.sh`.
- State dirs: `docs/paper-trades/v8/`, `docs/paper-trades/v8_ml/` (created on first run, like peers).
- Telegram silent (`TELEGRAM_DISABLE=1`).

**Isolation guarantee:** no running engine (v5, v5_classic, v5_cut, v5_long, v5_flip, v7_regime)
changes behavior. This is enforced by the no-op-default rule in §5.

## 5. New defensive base knobs

The April recipe needs three params that are currently **hardcoded module constants**, not env-exposed.
Each becomes an env override that **defaults to today's exact value** — so when the var is unset (every
existing engine), behavior is byte-for-byte identical.

| Param | Today (hardcoded) | v8 value | File | Env var |
|---|---|---|---|---|
| Position cap | `MAX_POSITIONS_TOTAL = 20` | `5` | `prototype/v5/risk_manager.py` | `MAX_POSITIONS_TOTAL` |
| Bracket target | `TARGET_PCT = 3.0` | `1.5` | `prototype/v5/alpha_hunter.py` | `TARGET_PCT` |
| Stop | `TRAILING_STOP_PCT = 0.7` (trailing) | `0.75` **fixed** | `prototype/v5/alpha_hunter.py` | `STOP_PCT` + `STOP_MODE` |

The stop change is not just a number — April used a **fixed** stop, current code **trails**. So a
`STOP_MODE` flag (`fixed` \| `trailing`, default `trailing`) gates the behavior; `STOP_PCT` supplies
the level. When both unset → current trailing-0.7 behavior unchanged.

Params already env-exposed (reused as-is): `SHORT_REQ_MAX_SCORE` / `SHORT_REQ_CHG_PCT` (long-only),
`RESCORE_INTERVAL_MIN` (early-entry-and-hold), `FLAT_EXIT_WINDOW_*` (flat by EOD), `UNIVERSE_FILE`,
`ML_SCORE_WEIGHT`, `ENGINE_NAME`, `TELEGRAM_DISABLE`.

**New universe file:** `quant/universe_nifty50.txt` — the 50 NIFTY-50 tickers (additive, safe).
(A `nifty50_quotes_batch.json` cache exists under `prototype/data/cache/` and can seed the list.)

## 6. Early-entry mechanism (verify during implementation)

The report attributes April's ~09:20 entry vs current ~11:00–11:46 to the **rescore loop**. Setting
`RESCORE_INTERVAL_MIN` to a large value should make the engine commit on the first scan and hold to
the bracket. **Implementation must verify** this actually produces early entry (dry replay of one day,
confirm avg entry time near market open) rather than assume it.

## 7. The 5-tree ML twin

- **Model:** LightGBM at `n_estimators=5` (vs the retired ~1,735/2,000-tree overfit). Existing training
  pipeline `scripts/train-tiered-models.py` already parameterizes `n_estimators`, so this is a
  hyperparameter + output-path change, not new infra.
- **Training data:** the **Apr–Jul labeled paper-trade history** we already have on disk (trade rows
  with entry features and win/loss outcomes), reusing the existing feature computation.
- **Ship-gate (hard):** train, then evaluate on a time-held-out slice. Wire the model into `v8_ml`
  **only if** it improves top-5 selection hit-rate over the no-ML baseline. If it fails the gate,
  `v8_ml` launches at weight 0 (identical to `v8`) and we record "5-tree does not earn its slot" —
  a clean negative result, not a failure.
- **Wiring:** via the existing `ML_SCORE_WEIGHT` env and the `ml_score` composite factor at ~0.10;
  the other factors renormalize (same mechanism `v5_noml` uses to zero it).

## 8. Evaluation & success bar

- Run both twins live-paper for **≥2 weeks** alongside the existing stable.
- **v8 (control) bar:** ≥ **+1%/day** and ≥ **65% win rate** — the report's reachable target,
  proving the recipe recovers the April edge.
- **v8_ml verdict:** judged purely on **marginal lift over v8** — added net P&L / WR **without** added
  drawdown. If flat or worse, the ML slot stays retired.
- Comparison uses the existing `scripts/engine-compare.py`; no new reporting surface.

## 9. Safety & testing

- **No-op regression test:** assert that with all v8 env vars unset, `MAX_POSITIONS_TOTAL`, `TARGET_PCT`,
  and stop mode/level resolve to today's values — i.e. the base touch cannot alter existing engines.
- **Dry replay:** replay one recent trading day through `v8` and confirm: long-only, ≤5 positions,
  +1.5/−0.75 exits, early entry, flat by EOD.
- **Corporate-action awareness:** inherits whatever the base engine already does; not changed here.

## 10. Deliverables

1. `quant/universe_nifty50.txt` (new universe).
2. Env-gated knobs in `prototype/v5/risk_manager.py` (`MAX_POSITIONS_TOTAL`) and
   `prototype/v5/alpha_hunter.py` (`TARGET_PCT`, `STOP_PCT`, `STOP_MODE`) — all default-preserving.
3. `scripts/v8-paper-trade.py` and `scripts/v8_ml-paper-trade.py` wrappers.
4. Two new lines in the `ENGINES` array in `scripts/launch-market.sh`.
5. 5-tree training run + ship-gate evaluation (reuse `train-tiered-models.py`), model artifact under
   `prototype/models/`.
6. No-op regression test + one-day dry-replay verification.

## 11. Relationship to prior work

This spec **supersedes** `docs/superpowers/plans/2026-07-03-april-revert.md` (the `v5_spring` plan),
which was never executed (no script, roster line, state dir, or `POSITION_PCT` base lever ever landed).
Both target the April +1%/77%-WR profile, but differ in method:

| | `v5_spring` (superseded) | **v8** (this spec) |
|---|---|---|
| Method | Multi-lever nudge of the live engine | Clean-room exact April replica |
| Universe | Keep NIFTY-200 | NIFTY-50 (April's universe) |
| Shorts | Kept, tightly gated | Off — pure long-only |
| Concentration | `POSITION_PCT=0.30` sizing | Hard top-5 cap |
| Bracket | Unchanged (3.0 / 0.7 trail) | +1.5 / −0.75 fixed |
| ML | Deferred | 5-tree isolated twin |
| Attribution | Multi-lever (confounded by design) | Single-variable twin |

v8 is both more faithful to April (reverts the universe and bracket v5_spring left unchanged) and
cleaner to interpret (twin isolation). `FAST_FLIP` — the one v5_spring lever that did land, via the
existing `v5_flip` engine — is unaffected and keeps running as its own shadow.

## 12. Open risks

- **Thin "now" baseline:** only 2 July days anchor the degradation report's July column. Directionally
  consistent with June, but the ≥2-week v8 run is what actually validates the recovery.
- **Early-entry assumption (§6):** must be verified, not assumed.
- **5-tree may not clear its gate:** acceptable — that is itself a clean finding.
- **Base-code touch:** the one shared-code change; mitigated by the no-op-default rule + regression test.
