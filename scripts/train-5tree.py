#!/usr/bin/env python3
"""Train a 5-tree LightGBM (April-recipe ML tilt) on the existing candle-feature pipeline
and evaluate whether it improves top-5 selection over no-ML (the ship-gate).

Writes ONLY prototype/v4/models/lgbm_5tree.txt. Never touches lgbm_intraday.txt or the
tiered models. Reuses ml_engine.build_training_dataset (same features/labels as the retired
big model), so this is apples-to-apples with the model it replaces.
"""
import sys
from pathlib import Path
import numpy as np
import lightgbm as lgb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "prototype"))
from prototype.v4 import ml_engine  # noqa: E402

OUT = ROOT / "prototype" / "v4" / "models" / "lgbm_5tree.txt"
PARAMS = dict(n_estimators=5, num_leaves=8, max_depth=3, min_child_samples=50,
              learning_rate=0.15, subsample=0.8, colsample_bytree=0.8, random_state=42)


def main():
    ds = ml_engine.build_training_dataset()
    feats = ml_engine.TRAINING_FEATURES
    ds = ds.dropna(subset=feats + ["target"]).reset_index(drop=True)
    print(f"dataset rows: {len(ds):,}  features: {len(feats)}", flush=True)
    X, y = ds[feats].values, ds["target"].values
    # time-ordered holdout (last 20% as test) — no shuffle, to respect time
    n = len(ds); cut = int(n * 0.8)
    X_tr, X_te, y_tr, y_te = X[:cut], X[cut:], y[:cut], y[cut:]
    model = lgb.LGBMRegressor(**PARAMS)
    model.fit(X_tr, y_tr)
    preds = model.predict(X_te)
    # SHIP-GATE: does ranking by the 5-tree beat ranking by nothing?
    # Proxy: mean forward-return of the model's top-5% picks vs the overall mean.
    k = max(1, len(preds) // 20)
    top_idx = np.argsort(preds)[-k:]
    top_mean = float(np.mean(y_te[top_idx])); overall = float(np.mean(y_te))
    lift = top_mean - overall
    print(f"top-5% picks mean target: {top_mean:+.4f}  overall mean: {overall:+.4f}  LIFT: {lift:+.4f}", flush=True)
    model.booster_.save_model(str(OUT))
    print(f"saved: {OUT}", flush=True)
    verdict = "PASS" if lift > 0 else "FAIL"
    print(f"SHIP-GATE: {verdict}  (wire into v8_ml only if PASS; else launch v8_ml at weight 0)", flush=True)
    return 0 if lift > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
