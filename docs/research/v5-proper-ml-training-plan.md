# v5 Proper ML Training Plan

> ## ⚠️ DEFERRED — DO NOT START
>
> **Status (updated 2026-04-27 evening):** This plan is **on hold** until the
> 2026-05-25 decision gate passes. See `docs/IMPLEMENTATION_BRIEF_2026-04-27.md`
> for the authoritative tonight-and-this-week plan.
>
> **Why deferred:** The validation work in `docs/2026-04-27_VALIDATION_HONEST.md`
> shows we have only 11 trading days of data. That is too small a sample to
> justify any ML rebuild — the "edge" we'd train on is statistically
> indistinguishable from noise. Lopez de Prado's deflated Sharpe + 95% CI gates
> require >=30 days of trading per engine before the signal is real.
>
> **What replaces this plan in the meantime:**
> - **This week (Phase 1):** ship 4 tactical rule fixes from
>   `IMPLEMENTATION_BRIEF_2026-04-27.md` §2 — premarket SHORT block, winner
>   re-arm, time-exit tightening, cost modeling.
> - **Next 4 weeks (Phase 2):** observation freeze. NO engine code changes.
>   Weekly stats tracker only.
> - **2026-05-25:** decision gate evaluates 4 criteria (95% CI > 0, drawdown
>   observed and recovered, deflated Sharpe >= 2.0, etc.). If passed, ML
>   rebuild begins per `docs/2026-04-27_SOLUTION_AND_ML_PLAN.md` §2.
>
> **What to do with this doc:** keep for reference. The Phase A / Phase B
> structure below remains a useful starting point if/when ML work is unblocked.
> But do NOT execute any of it before 2026-05-25.

---

**Date:** 2026-04-27
**Owner:** Soumya
**Trigger:** 2026-04-27 retirement of v4 / v5_2 / v5_3 (`scripts/launch-market.sh`). Decision: concentrate ML training effort on the v5 lineage (v5, v5_classic, v5_6, v5_7).
**Position in tonight's queue:** Item #8 (added after retirement decision) — **superseded by IMPLEMENTATION_BRIEF**

---

## 1. Where we are today

The v5 family currently shares the v4 ML stack underneath:

| Layer | File | Built / trained |
|---|---|---|
| Main ML model | `prototype/v4/models/lgbm_intraday.txt` | LightGBM, 22 features, 50,563 rows, retrained daily |
| Tiered models (4) | `prototype/v4/models/tiered/{elite,large_cap,mid_cap,broad}_lgbm.txt` | LightGBM per stock-cap tier |
| Composite scorer | `prototype/v4/composite_scorer.py` | Weighted percentile-ranker over 7 sub-scores |
| Signal engine | `prototype/v5/signal_engine.py` | v5-specific layer on top of v4 composite |
| Risk gate | `prototype/v5/risk_manager.py` | Slot partition (15/5 SIDEWAYS), pool caps |
| Strategy variants | `scripts/v5_6-*.py` (Darvas Box), `scripts/v5_7-*.py` (Intraday Box) | Strategy overlays on the same signals |

**v5 does NOT have its own trained model.** It uses v4's. That's by design (v4 is the ML layer; v5 is the strategy layer). When the user says "proper ML training for v5", we have two interpretations to pick from:

- **Interpretation A — Improve the shared v4 ML stack**: better features, better validation, better hyperparameters, more data. v5 inherits the upgrade automatically.
- **Interpretation B — Train a v5-specific model**: separate model that learns from v5's actual trade outcomes (entries, exits, P&L) rather than generic next-bar returns. Pure v5 attribution.

Both are valid. A is faster to deliver (1 weekend) and lifts all engines. B is more ambitious (2-3 weekends) and gives v5 a unique edge. We can do A first, then B.

---

## 2. Interpretation A — Strengthen the v4/v5 shared ML stack (Phase 1)

These are the highest-leverage improvements achievable in one weekend.

### A1. Expand training universe and history

Today: 199 stocks, 50,563 rows, 2024-06-26 → 2026-04-27 (1.84 years).

Targets:
- Universe: extend from Nifty 50 + selected mid-caps (199 stocks today) to **Nifty 500 (462 active stocks)**. The intraday-capture script already handles 381 stocks for the dashboard.
- History: extend from 1.84 years to **3 years minimum** (2023-04-01 onwards). LightGBM benefits from more regime variety (BULL of 2024, correction of late 2024, recovery of 2025).
- Estimated row count after expansion: **~250,000 rows** (5x today's data).
- Cost: one-time data download via `scripts/download-all-data.py`. ~30 min.

### A2. Add 8-10 new features the engine already has but the model doesn't see

Current 22 features include the basics (RSI, MACD, Bollinger, ATR, returns, gap, ORB, vwap_position, india_vix, nifty_change_pct, RS).

Missing features that the engine logs already capture:
- `fii_dii_net_flow_5d_avg` — institutional flow trend
- `sector_relative_strength_5d` — sector-level momentum (today's bleed root cause was sector rotation traps)
- `breadth_pct_green` — market breadth (signals regime override)
- `intraday_volume_vs_5d` — volume surge vs average
- `volatility_regime` — VIX bucket (LOW < 15, MED 15-22, HIGH > 22)
- `time_of_day_bucket` — engineering feature; 09:15-10:00 vs 10:00-13:00 vs 13:00-15:30 perform differently
- `option_chain_pcr` — put-call ratio if available from NSE feed
- `spread_to_target` — engine's own predicted upside, fed back as a feature

Each of these is one column added to the dataset builder. Estimated lift: +5-10% IC based on similar additions in the 04-21 fix.

### A3. Replace random validation with proper purged time-series CV

Current: `train_test_split(test_size=0.1, random_state=42, shuffle=True)` for the FINAL model. Walk-forward CV (15 folds, 6mo train / 1mo test / 5d embargo) is correctly used for metrics.

Problem: the random validation for the final model leaks future information into the past. Healthy IC of 0.05 may be optimistic by 30-50%.

Fix: replace with a single **purged final fold** — train on first 90% chronologically, embargo 5 days, validate on last 10%. Same regime mix achieved by stratifying on volatility quartile. ~30 LOC change in `ml_engine.py`.

### A4. Hyperparameter search (currently fixed, never tuned)

Current LGBM_PARAMS are hand-set:
```
num_leaves=15, max_depth=4, min_child_samples=50,
reg_alpha=0.3, reg_lambda=1.0, subsample=0.6, colsample_bytree=0.6
```

These are reasonable defaults but never verified empirically. Run an Optuna search with:
- 50 trials, 4-hour budget
- Bayesian optimization on a held-out 2024-Q4 window
- Search space: num_leaves ∈ [7, 63], max_depth ∈ [3, 8], reg_alpha ∈ [0, 5], reg_lambda ∈ [0, 5], min_child_samples ∈ [20, 200], learning_rate ∈ [0.01, 0.1]
- Optimize: walk-forward mean IC

If best params materially differ from current, pin them as new defaults.

### A5. Per-tier hyperparameter search (extend A4 to the 4 tiered models)

Same Optuna sweep but per tier. Elite (49 stocks) likely wants more regularization; broad (50 stocks) wants different hyperparameters than the main intraday model.

### A6. Model freshness coverage extension

Today's freshness check at `prototype/utils/signal_guards.py:203` only watches `lgbm_intraday.txt`. The 4 tiered models can silently age. **Item #8 from the model-comparison output**: extend the check to cover all 5 model files. ~10 LOC in signal_guards.py.

### Combined A1-A6 estimated impact

| Lever | Estimated IC lift | Estimated WR lift | Effort |
|---|---:|---:|---|
| A1 (more data) | +0.005 | +1-2% | 30 min |
| A2 (more features) | +0.010 | +3-5% | 4 hr |
| A3 (purged CV) | -0.015 (more honest) | 0% (just less inflated) | 30 min |
| A4 (Optuna main) | +0.005 | +1-2% | 4 hr (compute time) |
| A5 (Optuna tiered) | +0.005 | +1-2% | 4 hr |
| A6 (freshness coverage) | 0 | preventive | 30 min |
| **Combined** | **+0.010 net** | **+5-10%** | **~14 hr / one weekend** |

Realistic outcome: today's IC of 0.0242 lifts to ~0.034 with honest CV. WR baseline of 48-92% across days lifts the floor (lower-WR days improve more than already-strong days). Translating to P&L: ~+₹2-5K per engine per day average uplift, with more volatility-day improvement.

---

## 3. Interpretation B — Train a v5-specific model on actual trade outcomes (Phase 2)

After Phase 1 lands, this is the next leap. v5 has accumulated ~5,000 paper trades across all variants (v5/v5_classic/v5_6/v5_7 over 2 weeks). Each trade has:
- Entry features (the 22-feature snapshot at entry time)
- Strategy variant (which engine deployed it)
- Outcome (P&L, win/loss, time-to-exit, exit reason)
- Market context (regime, Nifty, FII/DII, VIX)

This is gold for a **v5-specific outcome model** that predicts not "will the stock move +1% in next bar" (today's target) but **"given this signal at this market state by this strategy variant, what's the expected P&L and probability of stop-loss"**.

### B1. Build the v5 trade outcome dataset

One-time pull: scrape every closed trade from `docs/paper-trades/v5/*.json`, `v5_6/*.json`, `v5_7/*.json` from 2026-04-08 onwards. Join with the entry-time snapshot from logs. Output: `prototype/v5/data/v5_trade_outcomes.parquet`.

Estimated rows: 5,000-8,000 trades by mid-May.

### B2. Two-head v5 model

Train a **multi-output LightGBM** with two heads:
- Head 1: regression — expected P&L in % terms
- Head 2: classification — probability the trade hits stop-loss before target

Inputs: same 22 features + variant_id (v5/v5_6/v5_7) + market regime.

This model lives at `prototype/v5/models/v5_outcome.lgbm` and is consulted at deploy time:
- If predicted P&L < +0.5% AND P(stop-loss) > 0.4, veto the trade.

### B3. Online learning loop

Every EOD, retrain the v5 outcome model with the new trade outcomes from that day. Walk-forward over the previous 30 days. Catches regime shifts within a week of them happening.

### B4. Per-variant attribution

The model learns variant-specific edges. v5_6 (Darvas) likely has different feature importances than v5_7 (Intraday Box). Store separate feature-importance maps per variant; surface the differences in tonight's EOD reports.

### Phase B effort and expected impact

| Step | Effort | Expected impact |
|---|---|---|
| B1 dataset build | 4 hr | enables everything downstream |
| B2 two-head model | 6 hr | adds a P&L-aware veto layer (estimate +₹1-2K/engine/day) |
| B3 online retrain | 4 hr | regime adaptation (estimate +₹1K/engine/day) |
| B4 per-variant attribution | 3 hr | informs which variant to trust per regime |
| **Combined Phase B** | **~17 hr / second weekend** | **+₹2-3K/engine/day on top of Phase A** |

---

## 4. What we kept from v4 (per "keep the learning")

The user asked to preserve v4's learnings. This is what's preserved and remains in active use:

| v4 asset | Status | Why kept |
|---|:---:|---|
| `prototype/v4/ml_engine.py` | KEPT — actively used | The training pipeline. v5 has no replacement; v5 uses it. |
| `prototype/v4/composite_scorer.py` | KEPT — actively used | The 7-sub-score scorer. v5's signal_engine wraps this. |
| `prototype/v4/models/lgbm_intraday.txt` | KEPT — live | Today's trained model. Used by all v5 engines. |
| `prototype/v4/models/tiered/*.txt` | KEPT — live | 4 tier models. Used by composite_scorer. |
| `prototype/v4/models/archive/*` | KEPT — historical | Rollback insurance. 5 historical snapshots preserved. |
| `prototype/v4/features_intraday.py` | KEPT — actively used | Feature engineering. |
| `prototype/v4/features_institutional.py` | KEPT — actively used | FII/DII features. |
| `prototype/v4/data_nse.py` | KEPT — actively used | NSE data loaders. |
| `prototype/v4/position_sizer.py` | KEPT — actively used | Position sizing. v5 inherits Kelly cap. |
| `prototype/v4/tiered_scorer.py` | KEPT — actively used | Loads the 4 tiered models. |
| `prototype/v4/config.py` | KEPT — actively used | Universe + symbol mapping. |
| `scripts/v4-paper-trade.py` | KEPT — retired from launch | Reference implementation. Can re-enable if needed. |
| `docs/paper-trades/v4/*.json` | KEPT — history | All v4 trade history. ~3 weeks of data. Useful for v5 outcome model (Phase B). |
| `logs/v4-*.log` | KEPT — history | All v4 logs. Pattern mining for v5 improvements. |

**Nothing from v4 is deleted.** v4 retires from the daily launch but remains the substrate v5 stands on.

---

## 5. Recommended path

Pick Interpretation A (Phase 1) for **next weekend (May 2-3)**. This is the highest-leverage spend and lifts every active engine (v5/v5_classic/v5_6/v5_7) immediately.

If Phase 1 results validate (+5-10% WR uplift over 1 week of paper trading after deployment), commit to Phase B for the weekend after (May 9-10).

Do NOT attempt Phase A and Phase B in the same weekend. The validation period in between is the whole point — without it, we can't tell which improvement caused which lift.

---

## 6. Tonight's deliverable

This document itself. No code touched (except the retirement edit to `launch-market.sh` and the guardrail edit to `ml_engine.py` made earlier tonight).

---

## 7. Acceptance criteria for Phase A (next weekend)

| Criterion | Target |
|---|---:|
| Training universe expanded from 199 → 462 stocks | ✓ |
| History extended from 1.84 → 3+ years | ✓ |
| 6-8 new features added to the dataset | ✓ |
| Purged time-series CV replaces random split | ✓ |
| Optuna search completes 50 trials per model | ✓ |
| All 5 models (main + 4 tiered) covered by freshness check | ✓ |
| Retrain runs end-to-end without guardrail rejection | ✓ |
| Walk-forward IC improves vs current 0.0242 baseline | ≥ 0.030 |
| Paper trading week-over-week WR improves | +3% minimum |

---

## 8. Risks for Phase A

| Risk | Likelihood | Mitigation |
|---|---|---|
| Larger universe overwhelms LightGBM with noise | Medium | Per-tier models already partition; same approach scales |
| 3-year history includes regime shifts model can't generalize | Low | Walk-forward CV catches this; also ADD `volatility_regime` feature |
| Optuna picks overfitting hyperparameters | Medium | Validation is on held-out 2024-Q4 — out-of-sample by design |
| New features introduce NaN explosion | Medium | Add `assert dataset.isna().sum().sum() == 0` guard before training |
| Retrain time grows from 5 min to 30 min | Low | Acceptable; runs at 02:00 IST overnight |
| New model is WORSE than current on live trading | Medium | Atomic candidate→live promote (already implemented tonight) preserves rollback |
