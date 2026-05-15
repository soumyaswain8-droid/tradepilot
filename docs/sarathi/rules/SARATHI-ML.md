# SARATHI-ML — ML Training Verification

**Triggered on:** every model retrain candidate, before promotion to live.
**Veto power:** YES — BLOCKS promotion of any model that fails any rule unless CEO override is logged.

This is **the May-13 fix**. Each rule corresponds to a specific failure that occurred or would have been caught by these checks.

## Rules

### ML-001 — CPCV report exists
Candidate model has a CPCV (Combinatorial Purged Cross-Validation) report with PBO (Probability of Backtest Overfitting) < 0.5.

- **Check:** `verification_report.json` next to model file has `cpcv.pbo` field; value < 0.5.
- **Fail action:** `BLOCK` — promotion blocked.

### ML-002 — IC ≥ champion
Candidate OOS IC ≥ current champion's OOS IC. If downgrade is intentional (e.g., trading IC for stability), explicit CEO sign-off with reason.

- **Check:** `verification_report.candidate.oos_ic` vs `prototype/v4/models/champion_meta.json:oos_ic`.
- **Fail action:** `BLOCK` — promotion blocked. Logs the gap.
- **Note on May-13:** champion IC=0.0061, candidate IC=0.0054. This rule would have BLOCKED that promotion.

### ML-003 — IC ≥ spec floor
Candidate OOS IC ≥ 0.05 (Apr-8 master research § 5.5).

- **Check:** `candidate.oos_ic >= 0.05`.
- **Fail action:** `BLOCK` unless model is explicitly marked `mode=filter` (where IC stays low but meta-label Sharpe is the KPI) — then `WARN` only.
- **Note:** until Sprint 4 ships meta-labeling, the current LightGBM cannot satisfy this. Sprint 1 grants a **time-bounded exemption** through 2026-06-30: model can run live in "legacy" mode while rebuild proceeds.

### ML-004 — No data leakage
Training end-date strictly less than OOS test start-date. Embargo applied (≥ horizon length). No overlapping labels between train and test.

- **Check:** `train_end_date < oos_start_date`; `embargo_days >= label_horizon_days`; no `train_label_end > oos_label_start` overlap.
- **Fail action:** `BLOCK` — leakage taints all IC numbers.

### ML-005 — Walk-forward folds
≥ 12 folds. Positive IC in ≥ 60% of folds.

- **Check:** `walk_forward.n_folds >= 12 AND walk_forward.ic_positive_pct >= 60.0`.
- **Fail action:** `BLOCK`.
- **Note on May-13:** model had 16 folds (pass) but 56.2% positive (fail). Would have BLOCKED.

### ML-006 — Cost-corrected backtest
Net Sharpe at 10bps AND 15bps both reported. Net Sharpe at 10bps must be positive.

- **Check:** `backtest.cost_10bps.sharpe > 0 AND backtest.cost_15bps.sharpe is not null`.
- **Fail action:** `BLOCK` — paper Sharpe without cost reality is unsafe.

### ML-007 — Champion-challenger
Side-by-side replay vs current champion on identical OOS window. Diebold-Mariano test or bootstrap difference test for significance.

- **Check:** `verification_report.champion_challenger.dm_pvalue` exists; candidate must not be significantly worse (p > 0.05 means difference is noise; p < 0.05 with candidate < champion means clearly worse).
- **Fail action:** `BLOCK` if candidate significantly worse than champion.

### ML-008 — Reproducibility
SHA-256 of training data file, model file, and code commit recorded together. Re-running the pipeline must produce bit-identical model.

- **Check:** `verification_report.reproducibility` has `data_sha256`, `model_sha256`, `code_commit`; optional re-run check produces same `model_sha256`.
- **Fail action:** `BLOCK` if any hash missing; `WARN` if re-run differs (could be platform-dependent).

## Engine-Side Enforcement

Every engine, on startup, MUST call:
```python
from scripts.sarathi.verify import verify_model
verify_model("prototype/v4/models/lgbm_intraday.txt")  # raises if BLOCK
```

If `verification_report.json` is missing OR shows any BLOCK rule with no override → engine **refuses to load** that model. The engine boot crashes with a clear error pointing to the failed rule.

No more silent retrains. No more loading a model whose lineage is unknown.

## Output Schema

Per-model `verification_report.json`:
```json
{
  "model_path": "prototype/v4/models/lgbm_intraday.txt",
  "model_sha256": "...",
  "trained_at": "...",
  "verified_at": "...",
  "candidate": {"oos_ic": 0.0061, "oos_ic_pos_pct": 56.2, "best_iter": 1216, ...},
  "champion": {"oos_ic": 0.0048, ...},
  "cpcv": {"n_paths": 1000, "median_sharpe": 0.8, "pbo": 0.42},
  "walk_forward": {"n_folds": 16, "ic_positive_pct": 56.2},
  "backtest": {
    "cost_10bps": {"sharpe": 0.65, "net_pnl": 50000, "max_dd": 0.07},
    "cost_15bps": {"sharpe": 0.21, "net_pnl": 15000, "max_dd": 0.09}
  },
  "champion_challenger": {"dm_pvalue": 0.18, "candidate_better": true},
  "reproducibility": {"data_sha256":"...","code_commit":"abc1234"},
  "rules_evaluated": [
    {"rule":"ML-001","result":"PASS","evidence":"PBO 0.42 < 0.50"},
    {"rule":"ML-002","result":"PASS","evidence":"0.0061 >= 0.0048"},
    {"rule":"ML-003","result":"WARN","evidence":"0.0061 < 0.05, mode=legacy"},
    ...
  ],
  "overall": "PASS|BLOCK",
  "override": null
}
```

## Backward Sweep (Sprint 1)

Run ML-001 through ML-008 against the currently-deployed model. Expect: most rules fail. Document the gap. Tag current model with `mode=legacy` exemption until rebuild ships.
