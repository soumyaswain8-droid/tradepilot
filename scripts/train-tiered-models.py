#!/usr/bin/env python3
"""Train tiered ML models from prototype/v4/config/tiers.json.

Safe by construction:
  - ONLY writes to prototype/v4/models/tiered/{tier}_lgbm.txt
  - NEVER touches prototype/v4/models/lgbm_intraday.txt
  - Uses separate LGBM hyperparameters per tier (not the global production ones)
  - --dry-run lists what it would do without training

Usage:
    python3 scripts/train-tiered-models.py --dry-run
    python3 scripts/train-tiered-models.py
    python3 scripts/train-tiered-models.py --tier elite
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(message)s")

OUT_DIR = ROOT / "prototype" / "v4" / "models" / "tiered"
TIERS_FILE = ROOT / "prototype" / "v4" / "config" / "tiers.json"
PROTECTED_MODEL = ROOT / "prototype" / "v4" / "models" / "lgbm_intraday.txt"

# Per-tier LGBM hyperparameters
TIER_PARAMS = {
    "elite": {
        "num_leaves": 15, "max_depth": 4, "min_child_samples": 50,
        "reg_alpha": 0.3, "reg_lambda": 1.0,
        "subsample": 0.6, "colsample_bytree": 0.6,
        "learning_rate": 0.05, "n_estimators": 2000,
    },
    "large_cap": {
        "num_leaves": 15, "max_depth": 4, "min_child_samples": 50,
        "reg_alpha": 0.3, "reg_lambda": 1.0,
        "subsample": 0.6, "colsample_bytree": 0.6,
        "learning_rate": 0.05, "n_estimators": 2000,
    },
    "mid_cap": {
        "num_leaves": 12, "max_depth": 4, "min_child_samples": 30,
        "reg_alpha": 0.5, "reg_lambda": 1.5,
        "subsample": 0.6, "colsample_bytree": 0.6,
        "learning_rate": 0.05, "n_estimators": 2000,
    },
    "broad": {
        "num_leaves": 10, "max_depth": 3, "min_child_samples": 20,
        "reg_alpha": 0.7, "reg_lambda": 2.0,
        "subsample": 0.6, "colsample_bytree": 0.6,
        "learning_rate": 0.05, "n_estimators": 2000,
    },
}


def assert_protected_untouched():
    """Abort if we somehow modified the protected model file."""
    if not PROTECTED_MODEL.exists():
        return
    # This is a weak check — real protection is in sanity-check.sh
    # But flag if file is tiny/empty suggesting corruption
    size = PROTECTED_MODEL.stat().st_size
    if size < 100000:
        raise RuntimeError(
            f"Protected model size suspicious: {size} bytes. "
            f"Expected >1MB. Aborting to prevent damage."
        )


def train_one_tier(tier_name, symbols, params, dry_run=False):
    """Train a single tier model using the v4 ml_engine machinery, but
    write to a tier-specific path instead of the global one."""
    target_file = OUT_DIR / f"{tier_name}_lgbm.txt"
    meta_file = OUT_DIR / f"{tier_name}_meta.json"

    print(f"\n[{tier_name}] {len(symbols)} symbols")
    if dry_run:
        print(f"  [DRY-RUN] Would build training dataset for {len(symbols)} stocks")
        print(f"  [DRY-RUN] Would train LGBM with: {list(params.keys())}")
        print(f"  [DRY-RUN] Would write: {target_file}")
        print(f"  [DRY-RUN] Would write: {meta_file}")
        return None

    # Real training
    from prototype.v4 import ml_engine
    import lightgbm as lgb
    from sklearn.model_selection import train_test_split

    assert_protected_untouched()

    # Build dataset for this tier's symbols only
    print(f"  Building dataset ({len(symbols)} stocks)...")
    dataset = ml_engine.build_training_dataset(symbols=list(symbols))
    if dataset.empty or len(dataset) < 500:
        print(f"  SKIP: dataset too small ({len(dataset)} rows)")
        return None

    print(f"  Dataset: {len(dataset):,} rows")

    X = dataset[ml_engine.TRAINING_FEATURES].values
    y = dataset["target"].values

    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.1, random_state=42, shuffle=True
    )

    full_params = {
        "objective": "regression",
        "metric": "mae",
        "verbose": -1,
        **params,
    }
    model = lgb.LGBMRegressor(**full_params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(100, verbose=False), lgb.log_evaluation(0)],
    )

    # SAFETY: verify we're not about to write over the protected path
    assert target_file.resolve() != PROTECTED_MODEL.resolve(), \
        "FATAL: target would overwrite protected model"

    model.booster_.save_model(str(target_file))

    importance = dict(zip(ml_engine.TRAINING_FEATURES, model.feature_importances_.tolist()))
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    meta = {
        "tier": tier_name,
        "trained_at": datetime.now().isoformat(),
        "training_rows": len(dataset),
        "training_stocks": len(symbols),
        "best_iteration": model.best_iteration_,
        "lgbm_params": full_params,
        "top_features": dict(list(importance.items())[:10]),
        "protected_model_untouched": True,
    }
    meta_file.write_text(json.dumps(meta, indent=2, default=str))

    print(f"  ✓ best_iteration={model.best_iteration_} "
          f"top feature: {list(importance.keys())[0]}={list(importance.values())[0]}")
    print(f"  → {target_file.name} ({target_file.stat().st_size//1024} KB)")

    assert_protected_untouched()
    return meta


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tier", choices=list(TIER_PARAMS.keys()) + ["all"], default="all")
    args = parser.parse_args()

    if not TIERS_FILE.exists():
        print(f"ERROR: {TIERS_FILE} not found. Run classify-universe.py first.")
        return 1

    tier_data = json.loads(TIERS_FILE.read_text())
    tiers = tier_data["tiers"]

    tiers_to_train = [args.tier] if args.tier != "all" else list(TIER_PARAMS.keys())

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Tiered training — {len(tiers_to_train)} tier(s)")
    print(f"Output dir:     {OUT_DIR}")
    print(f"PROTECTED:      {PROTECTED_MODEL}  (will NOT be touched)\n")

    results = {}
    for tier_name in tiers_to_train:
        if tier_name not in tiers:
            print(f"[{tier_name}] no symbols in tiers.json, skipping")
            continue
        symbols = list(tiers[tier_name].keys())
        if not symbols:
            print(f"[{tier_name}] empty symbol list, skipping")
            continue
        result = train_one_tier(
            tier_name, symbols, TIER_PARAMS[tier_name], dry_run=args.dry_run
        )
        if result:
            results[tier_name] = result

    if args.dry_run:
        print("\n[DRY-RUN] No models written. Protected model untouched.")
    else:
        print(f"\n✓ Trained {len(results)} tier models. All in {OUT_DIR}.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
