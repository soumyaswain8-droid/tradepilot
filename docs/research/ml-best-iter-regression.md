# LightGBM `best_iter=2` Regression — Diagnosis Report

*Investigation only. No code changes made. — 2026-04-27*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Module** | `prototype/v4/ml_engine.py` |
| **Status** | Bug fixed on 2026-04-21. Today (2026-04-27) reproduces the healthy state. |
| **Created** | 2026-04-27 |
| **Updated** | 2026-04-27 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Kishore Rajendra |
| **Email** | kishorer747@gmail.com |
| **LinkedIn** | [linkedin.com/in/kishorer747](https://www.linkedin.com/in/kishorer747) |

:::

---

## 1. Problem Statement

LightGBM exposes `model.best_iteration_` as the boosting round at which the validation metric stopped improving for `early_stopping_rounds` consecutive rounds. With `n_estimators=2000` and `learning_rate=0.05`, a healthy intraday-return model needs hundreds-to-thousands of rounds to capture the signal across 50K+ rows and 22 features.

**`best_iteration_ = 2` means the model committed exactly two boosting rounds before early stopping concluded the validation metric would not improve.** With only 2 trees, predictions collapse onto two leaves of two stumps — the output distribution is near-degenerate and the model is functionally untrained. Live inference still runs (no exception), it just produces near-constant scores around the global mean. That silently kills the alpha and downstream rankers degrade to near-random.

The known-good baseline (visible in `scripts/launch-market.sh:206`, `scripts/render-tuesday-eod-pdf.py:590`, and the `2026-04-21` archive) is `best_iter ≈ 1726`. Today's `2026-04-27 10:54` retrain landed at `best_iter = 1558` — back inside the healthy range.

---

## 2. Code Investigation Findings

### 2.1 Hyperparameters & early-stopping (current state)

`prototype/v4/ml_engine.py:80-96`

```python
LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "num_leaves": 15,
    "max_depth": 4,
    "min_child_samples": 50,
    "reg_alpha": 0.3,        # Was 0.5 — partial loosen for Nifty-200 dataset
    "reg_lambda": 1.0,       # Was 2.0 — partial loosen for Nifty-200 dataset
    "subsample": 0.6,
    "colsample_bytree": 0.6,
    "learning_rate": 0.05,
    "n_estimators": 2000,
    "verbose": -1,
}
EARLY_STOPPING_ROUNDS = 100   # Increased from 50
```

### 2.2 Where `best_iter` is decided (final model only)

`ml_engine.py:601-612` — final model fit:

```python
from sklearn.model_selection import train_test_split
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.1, random_state=42, shuffle=True   # RANDOM split
)
model = lgb.LGBMRegressor(**LGBM_PARAMS)
model.fit(
    X_train, y_train,
    eval_set=[(X_val, y_val)],
    callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False),
               lgb.log_evaluation(0)],
)
```

`meta["best_iteration"] = model.best_iteration_` is recorded only for the final, full-data model — not for the walk-forward folds (which each have their own internal early-stopping but those `best_iter` values are not persisted).

The comment block at `ml_engine.py:595-600` explicitly documents the previous failure:

> "Random 10% validation for early stopping. Previously used last-10% sequential, which landed on a recent regime and early-stopped at iteration 2. Random split gives a representative validation signal across the full training period."

This is the smoking gun — the bug is already fixed in code, with a comment naming the exact symptom.

### 2.3 Walk-forward validation (per-fold, not persisted)

`ml_engine.py:442-569`. 15 folds, train=6 mo / test=1 mo / 5-day embargo, each fold trains its own model with the same `EARLY_STOPPING_ROUNDS=100` and reports IC / hit-rate / L-S spread. Best-IC fold model is held in memory as `best_model` but discarded at the end (line 568) — it is never saved. Only the `train_and_save` final model (random-split early-stopped) is persisted to `lgbm_intraday.txt`.

### 2.4 Feature pipeline

`ml_engine.py:285-387`. Critical safety: every feature is shifted by 1 day at lines 380-382 to prevent look-ahead bias. Target is winsorised to 1st/99th percentile. Intraday features are filled with `0.0` for days without 5-min data. No NaN explosion observed in the current dataset (50,563 rows after `dropna`).

---

## 3. Per-Hypothesis Assessment

::: {.metrics-table}

| Hypothesis | Likelihood | Evidence |
|------------|:----------:|----------|
| (a) Early-stopping threshold too tight (`EARLY_STOPPING_ROUNDS` lowered to 1-2) | **LOW** | Currently 100 (line 96). Was raised from 50 → 100 in the fix. No path lowers it. |
| (b) Training data quality regressed (NaN, scaling, target shift) | **LOW** | Target stats stable (mean -0.0008, std 0.0154). Row count grew 21K (Apr 10) → 50K (Apr 18+) cleanly. Feature-importance entropy is healthy in today's run. |
| (c) Hyperparameter tuning rolled back (regularisation too tight) | **MEDIUM-HISTORICAL** | This **was** part of the prior bug. `reg_alpha=0.5, reg_lambda=2.0` over-regularised the Nifty-200 (199 stock) dataset and combined with the bad val split froze training at 2 rounds. Already loosened to `0.3 / 1.0`. Risk re-emerges only if someone hand-edits these back. |
| **(d) Walk-forward fold split degeneracy** | **LOW for final model** | Folds use different windows; per-fold IC ranges -0.31 to +0.24 today, no obviously degenerate split. The persisted `best_iteration` does not come from walk-forward folds — they are independent. |
| (e) Random seed change causing one bad fold | **LOW** | `random_state=42` is hardcoded at line 603. Same seed every retrain. |
| **(f) Sequential val split landing on regime-shift period** | **HIGH-HISTORICAL — root cause** | Pre-fix code used last-10% sequential val split. With 50K rows sorted by Date, the last 10% = ~3 weeks of recent market regime (different vol, different leadership, different IV). The model's first 2 trees on the global average already minimised MAE on that narrow recent slice; further trees that improved global fit *worsened* MAE on the shifted-regime val set, so early-stopping fired at iteration 2. The 2026-04-21 fix swapped this to `train_test_split(..., shuffle=True, random_state=42)` so the val set is now an i.i.d. sample of the full period — early stopping now reflects true generalisation. |

:::

---

## 4. Most Likely Root Cause (Historical)

**Sequential last-10% validation split + over-regularisation, hitting a regime-shift in the most recent 3 weeks of data.** The bug was a sequential time split for the *final* model's early-stopping holdout, not a walk-forward fold issue and not data corruption.

Evidence chain (from archive metadata):

::: {.metrics-table}

| Date | Rows | best_iter | reg_alpha / lambda | Val split | Outcome |
|------|-----:|----------:|--------------------|-----------|---------|
| 2026-04-10 | 21,805 | 5 | 0.5 / 2.0 | sequential | Already under-fitting on smaller dataset |
| 2026-04-18 | 50,661 | 2 | 0.5 / 2.0 | sequential | Bug surfaces clearly when dataset grew |
| 2026-04-20 | 50,612 | 2 | 0.5 / 2.0 | sequential | Reproduced (pre-fix archive) |
| 2026-04-21 | 50,612 | **1,726** | **0.3 / 1.0** | **random** | **Fix applied** — model healthy again |
| 2026-04-27 | 50,563 | **1,558** | 0.3 / 1.0 | random | Today — healthy, fix holds |

:::

The fix that worked combined three changes:
1. `train_test_split(..., shuffle=True, random_state=42)` — primary cause cured
2. `reg_alpha 0.5 → 0.3`, `reg_lambda 2.0 → 1.0` — gives the model room to grow trees
3. `EARLY_STOPPING_ROUNDS 50 → 100` — patience cushion against noisy MAE

The forensic report at `scripts/render-forensic-report.py:484` documents the same conclusion.

---

## 5. Is the Bug Still Present?

**No. The bug is fixed in the current code.** Evidence:

- `ml_engine.py:601-604` uses random shuffled split (the fix).
- `ml_engine.py:86-87, 96` carry the loosened regularisation and longer early-stopping patience.
- Today's metadata (`lgbm_meta.json`, `2026-04-27T10:54:15`) records `best_iteration: 1558` with `india_vix` as the #1 feature (importance 3192) — exactly the post-fix profile.
- The explanatory comment at lines 595-600 makes the prior failure mode and rationale explicit, reducing the chance of accidental rollback.

**Residual risk:** there is no automated guard. Anyone who edits `LGBM_PARAMS` (raising regularisation), changes the val split back to sequential, or lowers `EARLY_STOPPING_ROUNDS` will re-introduce the regression silently. There is no detection, no alert, no quarantine.

---

## 6. Recommendations — Detection & Prevention

These are read-only suggestions; implementation is left for a follow-up sprint.

### 6.1 Mandatory model-quality gate in `train_and_save`

Right after `model.fit(...)` at `ml_engine.py:612`, insert a guard:

```python
MIN_ACCEPTABLE_BEST_ITER = 100   # below this is over-regularised / under-fit
if model.best_iteration_ < MIN_ACCEPTABLE_BEST_ITER:
    raise RuntimeError(
        f"REJECTED MODEL: best_iter={model.best_iteration_} < {MIN_ACCEPTABLE_BEST_ITER}. "
        f"Likely over-regularised or val-split regime shift. "
        f"Model NOT saved. Investigate before re-running."
    )
```

Place this **before** `model.booster_.save_model(...)` at line 619 so a bad model never overwrites a good one.

### 6.2 Promote-on-quality (atomic write pattern)

Save first to `lgbm_intraday.txt.candidate`, validate, then `os.rename` over `lgbm_intraday.txt`. This way the live engine always reads the last known-good model. Pair with: archive previous good model into `models/archive/<DATE>/` before promotion (already done manually — automate it).

### 6.3 Walk-forward sanity floor

After the walk-forward loop, reject if `mean_ic < 0` or `ic_positive_pct < 30`. The known-good baseline is mean IC ~0.02-0.05 with 50-75% positive folds. Today's `mean_ic=0.0242, ic_positive=53.3%` is on the low end of healthy.

### 6.4 Telegram alert hook in `scripts/retrain-ml.sh`

After step 2 (training), parse `prototype/v4/models/lgbm_meta.json`:

```bash
BEST_ITER=$(python3 -c "import json; print(json.load(open('prototype/v4/models/lgbm_meta.json'))['best_iteration'])")
if [ "$BEST_ITER" -lt 100 ]; then
    # send Telegram critical alert
    ./scripts/notify-telegram.sh "CRITICAL: Retrain produced best_iter=$BEST_ITER (<100). Model rejected."
    exit 1
fi
./scripts/notify-telegram.sh "Retrain OK. best_iter=$BEST_ITER, mean_ic=$MEAN_IC"
```

### 6.5 Two-split corroboration (optional, cheap)

For early-stopping, fit twice — once on a random split, once on a TimeSeriesSplit-style penultimate slice — and accept the model only if both `best_iter` values agree within an order of magnitude. This catches both regime-shift over-fitting and val-leakage simultaneously.

### 6.6 Versioned hyperparameter pinning

Capture the `LGBM_PARAMS` dict + `EARLY_STOPPING_ROUNDS` + val-split strategy as a SHA-256 hash and write it into `lgbm_meta.json`. On every retrain, log the hash. A human-visible diff catches accidental rollbacks during code review.

---

## 7. Runbook — "If `best_iter < 100` happens again"

1. **STOP.** Do not let the engine run on the new model. The bad model has likely already overwritten `lgbm_intraday.txt` (until 6.1/6.2 are implemented).
2. **Restore last known good** from `prototype/v4/models/archive/`. The latest dated subdirectory with `best_iteration ≥ 100` is the safe rollback target. Copy `lgbm_intraday.txt` and `lgbm_meta.json` back to `prototype/v4/models/`.
3. **Diff the LGBM_PARAMS** in `prototype/v4/ml_engine.py` against the last good metadata's `lgbm_params`. Look for any of: `reg_alpha`, `reg_lambda`, `learning_rate`, `min_child_samples`, `num_leaves`, `n_estimators`, `EARLY_STOPPING_ROUNDS`. Revert any change.
4. **Diff the val-split logic** at `ml_engine.py:601-604`. Confirm it is still `train_test_split(..., shuffle=True, random_state=42)`. If anyone changed it to sequential / `train_test_split(..., shuffle=False)` / TimeSeriesSplit, revert.
5. **Inspect the dataset target stats**. Run:
   ```bash
   python3 -c "
   from prototype.v4.ml_engine import build_training_dataset
   d = build_training_dataset()
   print('rows:', len(d), 'stocks:', d.symbol.nunique())
   print('target mean:', d.target.mean(), 'std:', d.target.std())
   print('target NaN:', d.target.isna().sum())
   print('date range:', d.Date.min(), 'to', d.Date.max())
   "
   ```
   Healthy baseline: 50K+ rows, 199 stocks, target mean ≈ -0.001, std ≈ 0.015, zero NaN. Wild deviations point to upstream data corruption (yfinance backfill issue, CSV header mismatch).
6. **Inspect feature importances** in the bad model's metadata. If everything is `0` except 3-4 features at single-digit importance → confirms the under-fit signature. If a single feature dominates >90% → look-ahead leakage.
7. **Re-run retrain manually** with `python3 -m prototype.v4.ml_engine --train` and watch the live log. The walk-forward fold output appears first; per-fold IC values and hit rates should look normal (mix of positive and negative, hit rates 45-58%) before the final model section prints `Best iteration: <N>`.
8. **If `best_iter` is still low after revert**: the data itself has changed (regime shift in the last training period). Trim the dataset to the prior known-good `date_range` from the archive metadata and retrain — if `best_iter` recovers, the new tail data is the issue. Investigate the new period's `india_vix`, `nifty_change_pct` stats.
9. **Once green**, archive the recovered model to `prototype/v4/models/archive/<DATE>-recovered/` and post a Telegram update.
10. **File a learning** in the DevPilot DB:
    ```bash
    dp learn "TRADEPILOT: best_iter=<N> recurrence on <date>. Root cause: <X>. Fix: <Y>." --tags tradepilot,ml,best-iter,regression
    ```

---

## 8. Appendix — File & Line Citations

::: {.spec-table}

| File | Line(s) | Reference |
|------|--------:|-----------|
| `prototype/v4/ml_engine.py` | 80-96 | `LGBM_PARAMS` dict + `EARLY_STOPPING_ROUNDS` |
| `prototype/v4/ml_engine.py` | 442-569 | `walk_forward_validation` (per-fold, not persisted) |
| `prototype/v4/ml_engine.py` | 575-648 | `train_and_save` — final model + metadata write |
| `prototype/v4/ml_engine.py` | 595-600 | Comment block documenting the prior 2-iter failure |
| `prototype/v4/ml_engine.py` | 601-612 | Random shuffle split (the fix) |
| `prototype/v4/ml_engine.py` | 619 | `model.booster_.save_model(...)` — no quality gate |
| `prototype/v4/ml_engine.py` | 630 | `meta["best_iteration"]` write |
| `scripts/retrain-ml.sh` | 53-55 | Retrain step — no post-train validation |
| `scripts/launch-market.sh` | 206 | Documents healthy baseline `best_iter=1726` |
| `scripts/render-forensic-report.py` | 61-66, 463, 482-484 | Forensic narrative of the 2026-04-18 → 2026-04-21 incident |
| `prototype/v4/models/lgbm_meta.json` | full | Today (2026-04-27): `best_iteration=1558` — healthy |
| `prototype/v4/models/archive/2026-04-20-pre-fix/lgbm_meta.json` | full | Pre-fix: `best_iteration=2`, `reg_alpha=0.5`, `reg_lambda=2.0` |
| `prototype/v4/models/archive/2026-04-21/lgbm_meta.json` | full | Post-fix: `best_iteration=1726`, `reg_alpha=0.3`, `reg_lambda=1.0` |

:::
