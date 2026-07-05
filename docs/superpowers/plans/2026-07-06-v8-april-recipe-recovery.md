# v8 Twin-Shadow (April-Recipe Recovery) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two paper-trade shadow engines — `v8` (a clean-room April-recipe replica: NIFTY-50, top-5, long-only, +1.5/−0.75 fixed bracket, early entry, flat by EOD) and its twin `v8_ml` (identical + a 5-tree ML tilt) — to test whether reverting to the April config recovers the +1%/day, 65%+ win-rate profile, and whether a minimal ML tie-breaker adds marginal value.

**Architecture:** Both engines are thin `runpy` wrappers over the shared `scripts/v5-paper-trade.py`, differing from live v5 only by env vars. The April params that aren't yet env-exposed (position cap, bracket, stop mode, ML model path) get env-gated overrides that **default to today's exact values**, so every existing engine stays byte-for-byte unchanged. `v8` and `v8_ml` differ by exactly one variable (`ML_SCORE_WEIGHT` + model path), making their P&L delta the 5-tree's marginal contribution.

**Tech Stack:** Python 3, the existing paper-trade engine + env-wrapper pattern, LightGBM (existing `ml_engine` pipeline), launchd auto-launch, the smoke gate (`scripts/sarathi-verify.sh --smoke`).

## Global Constraints

- **Never change any running engine's behaviour.** Every new code path is env-gated and defaults to the current value, so v5/v5_classic/v5_long/v5_cut/v5_flip are unaffected when the new vars are unset. This is verified by an env-check after each base-code change.
- **Shadow-first, additive-only.** New engines are paper shadows; real validation is the live A/B over ≥2 weeks incl. ≥1 green + ≥1 red day.
- **Retire nothing; comment out, never delete** (data-safety rule).
- **Verification per base-code change = `python3 -m py_compile` (success) + env-check one-liner (default unset == current value; override works) + `./scripts/sarathi-verify.sh --smoke --quiet` (exit 0).** This codebase has no pytest for the engines; the smoke gate is the launch preflight.
- **Capital = ₹10,00,000 per engine** (`TOTAL_CAPITAL`, unchanged).
- **April recipe values (exact):** universe = NIFTY-50; `MAX_POSITIONS_TOTAL=5`; `TARGET_PCT=1.5`; `STOP_PCT=0.75`; `STOP_MODE=fixed`; long-only (`SHORT_REQ_MAX_SCORE=-1`, `SHORT_REQ_CHG_PCT=-999`); early-entry-and-hold (`RESCORE_INTERVAL_MIN=999`); flat by EOD (existing default). v8 `ML_SCORE_WEIGHT=0`; v8_ml `ML_SCORE_WEIGHT=0.10`.
- **Spec:** `docs/superpowers/specs/2026-07-06-v8-april-recipe-recovery-design.md`.

---

# PHASE 1 — v8 control (the April replica)

### Task 1: Create the NIFTY-50 universe file

**Files:**
- Create: `quant/universe_nifty50.txt`

**Interfaces:**
- Produces: a plain-text universe file (one ticker per line, no `.NS` suffix, `#` comments allowed — same format as `quant/universe_expanded.txt`) that `v8` will point at via the existing `UNIVERSE_FILE` env var (proven by `v5_cut`).

- [ ] **Step 1: Generate the file from the cached NIFTY-50 quote batch.**

```bash
cd ~/Documents/tinker/projects/tradepilot
LATEST_CACHE=$(ls -t prototype/data/cache/*/nifty50_quotes_batch.json | head -1)
echo "source: $LATEST_CACHE"
python3 - "$LATEST_CACHE" > quant/universe_nifty50.txt <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
# batch file is {symbol: {...quote...}} or {"quotes": {...}}; handle both
syms = data.get("quotes", data)
tickers = sorted(k.replace(".NS", "").strip().upper() for k in syms.keys() if k and not k.startswith("^"))
print("# NIFTY-50 universe — v8 April-recipe replica (generated 2026-07-06 from " + sys.argv[1].split("/")[-2] + " cache)")
for t in tickers:
    print(t)
PY
echo "count: $(grep -vc '^#' quant/universe_nifty50.txt)"
```
Expected: `count:` prints a number between 45 and 52 (NIFTY-50 membership drifts slightly; 50 nominal).

- [ ] **Step 2: Sanity-check the contents.**

Run: `head -6 quant/universe_nifty50.txt && echo "---" && grep -vc '^#' quant/universe_nifty50.txt`
Expected: a comment header then uppercase tickers like `HDFCBANK`, `RELIANCE`, `INFY`; count 45–52. If the count is outside that range, the cache schema differed — inspect the JSON and adjust the extraction before proceeding.

- [ ] **Step 3: Commit.**

```bash
git add quant/universe_nifty50.txt
git commit -m "feat(v8): add NIFTY-50 universe file for April-recipe replica"
```

---

### Task 2: Env-gate the position cap (`MAX_POSITIONS_TOTAL`)

**Files:**
- Modify: `prototype/v5/risk_manager.py:50`

**Interfaces:**
- Consumes: env `MAX_POSITIONS_TOTAL` (default `20` = current behaviour).
- Produces: module constant `MAX_POSITIONS_TOTAL: int`, read by `RiskManager.check_can_trade` (line 287). At `5`, the total-position cap binds before any regime long/short slot split, giving true top-5 concentration.

- [ ] **Step 1: Make the constant env-overridable.** Replace line 50:

```python
MAX_POSITIONS_TOTAL = 20
```
with:
```python
import os as _os  # local alias; module already imports pathlib etc. above
MAX_POSITIONS_TOTAL = int(_os.environ.get("MAX_POSITIONS_TOTAL", "20"))
```
(If `import os` already exists at the top of `risk_manager.py`, drop the `import os as _os` line and use `os.environ` directly — check the file header first.)

- [ ] **Step 2: Compile.** Run: `python3 -m py_compile prototype/v5/risk_manager.py` — Expected: no output (success).

- [ ] **Step 3: Env-check — default preserved AND override works.**

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -c "import importlib,prototype.v5.risk_manager as r; print('default:', r.MAX_POSITIONS_TOTAL)"
MAX_POSITIONS_TOTAL=5 python3 -c "import prototype.v5.risk_manager as r; print('override:', r.MAX_POSITIONS_TOTAL)"
```
Expected: `default: 20` then `override: 5`.

- [ ] **Step 4: Smoke gate.** Run: `./scripts/sarathi-verify.sh --smoke --quiet; echo "exit $?"` — Expected: `PASS`, `exit 0`.

- [ ] **Step 5: Commit.**

```bash
git add prototype/v5/risk_manager.py
git commit -m "feat(v8): env-gate MAX_POSITIONS_TOTAL (default 20 = unchanged)"
```

---

### Task 3: Env-gate the bracket + fixed-stop mode

**Files:**
- Modify: `scripts/v5-paper-trade.py` — config block (~line 71, after `WRONGWAY_CUT_PCT`), `deploy_signals` sl/tgt (lines 493–495), trailing gate (lines 650, 660)

**Interfaces:**
- Consumes: env `TARGET_PCT` (default unset → None), `STOP_PCT` (default unset → None), `STOP_MODE` (`"trailing"` default | `"fixed"`).
- Produces: module constants `TARGET_PCT: float|None`, `STOP_PCT: float|None`, `STOP_MODE: str`. When both `TARGET_PCT` and `STOP_PCT` are set, they replace the computed sl/tgt in `deploy_signals` with a fixed % bracket off entry price. When `STOP_MODE == "fixed"`, the trailing-stop branch is skipped so the stop stays at the fixed level.

- [ ] **Step 1: Add the env constants** in the config block, immediately after the `WRONGWAY_CUT_PCT` line (line 71):

```python
# v8 April-recipe bracket (env-gated, default None/"trailing" so all other engines are unchanged).
# When TARGET_PCT and STOP_PCT are both set, deploy_signals uses a fixed % bracket off entry.
# STOP_MODE="fixed" disables the trailing-stop trigger so the stop stays at the fixed level.
_tp = os.environ.get("TARGET_PCT"); TARGET_PCT = float(_tp) if _tp is not None else None
_sp = os.environ.get("STOP_PCT");   STOP_PCT   = float(_sp) if _sp is not None else None
STOP_MODE = os.environ.get("STOP_MODE", "trailing")
```

- [ ] **Step 2: Override the bracket in `deploy_signals`.** Replace lines 493–495:

```python
        _sl_pct = 0.0225 if _gap > 0.5 else 0.015
        sl = sig.get("sl_price", price * ((1 - _sl_pct) if sig["direction"] == "BUY" else (1 + _sl_pct)))
        tgt = sig.get("target_price", price * (1.02 if sig["direction"] == "BUY" else 0.98))
```
with:
```python
        if TARGET_PCT is not None and STOP_PCT is not None:
            # v8: fixed April bracket off entry, ignoring signal-supplied sl/tgt
            _is_buy = sig["direction"] == "BUY"
            sl  = price * ((1 - STOP_PCT / 100)   if _is_buy else (1 + STOP_PCT / 100))
            tgt = price * ((1 + TARGET_PCT / 100) if _is_buy else (1 - TARGET_PCT / 100))
        else:
            _sl_pct = 0.0225 if _gap > 0.5 else 0.015
            sl = sig.get("sl_price", price * ((1 - _sl_pct) if sig["direction"] == "BUY" else (1 + _sl_pct)))
            tgt = sig.get("target_price", price * (1.02 if sig["direction"] == "BUY" else 0.98))
```

- [ ] **Step 3: Gate the trailing branches on `STOP_MODE`.** At line 650 replace:

```python
            elif pnl_pct >= TRAILING_TRIGGER_PCT:
```
with (SHORT branch):
```python
            elif STOP_MODE != "fixed" and pnl_pct >= TRAILING_TRIGGER_PCT:
```
and at line 660 replace the identical LONG-branch line:
```python
            elif pnl_pct >= TRAILING_TRIGGER_PCT:
```
with:
```python
            elif STOP_MODE != "fixed" and pnl_pct >= TRAILING_TRIGGER_PCT:
```
(There are exactly two occurrences — one in the `if is_short:` block, one in the `else:` block. Edit both.)

- [ ] **Step 4: Compile.** Run: `python3 -m py_compile scripts/v5-paper-trade.py` — Expected: no output (success).

- [ ] **Step 5: Env-check — defaults preserved AND override works.**

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -c "
import importlib.util,sys
s=importlib.util.spec_from_file_location('m','scripts/v5-paper-trade.py'); m=importlib.util.module_from_spec(s); sys.modules['m']=m; s.loader.exec_module(m)
print('default:', m.TARGET_PCT, m.STOP_PCT, m.STOP_MODE)
"
TARGET_PCT=1.5 STOP_PCT=0.75 STOP_MODE=fixed python3 -c "
import importlib.util,sys
s=importlib.util.spec_from_file_location('m','scripts/v5-paper-trade.py'); m=importlib.util.module_from_spec(s); sys.modules['m']=m; s.loader.exec_module(m)
print('override:', m.TARGET_PCT, m.STOP_PCT, m.STOP_MODE)
"
```
Expected: `default: None None trailing` then `override: 1.5 0.75 fixed`.

- [ ] **Step 6: Smoke gate.** Run: `./scripts/sarathi-verify.sh --smoke --quiet; echo "exit $?"` — Expected: `PASS`, `exit 0`.

- [ ] **Step 7: Commit.**

```bash
git add scripts/v5-paper-trade.py
git commit -m "feat(v8): env-gate TARGET_PCT/STOP_PCT/STOP_MODE bracket (default = unchanged)"
```

---

### Task 4: Build the `v8` wrapper

**Files:**
- Create: `scripts/v8-paper-trade.py`

**Interfaces:**
- Consumes: env levers from Tasks 1–3 + existing `SHORT_REQ_*`, `RESCORE_INTERVAL_MIN`, `UNIVERSE_FILE`, `ENGINE_NAME`, `ML_SCORE_WEIGHT`, `TELEGRAM_DISABLE`.
- Produces: a paper-trade engine writing to `docs/paper-trades/v8/`.

- [ ] **Step 1: Create the wrapper:**

```python
#!/usr/bin/env python3
"""
v8 — the April-recipe replica (control twin). TP-V8, 2026-07-06.

WHY: DEGRADATION_ANALYSIS_Apr-Jul_2026 shows v5 decayed from +1.35%/day @ 77% WR (April)
to -0.24%/day @ 46% (July) via a complexity cascade. This is a clean-room revert to the
proven April engine — NIFTY-50, top-5, long-only, +1.5/-0.75 FIXED bracket, early entry,
flat by EOD. All params are env-gated on the shared v5 engine (zero change to live v5).

Twin: v8_ml is identical except ML_SCORE_WEIGHT=0.10 (5-tree tilt). v8 - v8_ml isolates
the ML's marginal effect. Target: recover +1%/day, 65%+ WR on Rs10L.
Compare vs live v5 over >=2 weeks incl. >=1 green + >=1 red day.
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]          = "v8"
os.environ["UNIVERSE_FILE"]        = str(ROOT / "quant" / "universe_nifty50.txt")  # NIFTY-50
os.environ["MAX_POSITIONS_TOTAL"]  = "5"        # top-5 concentration (binds before slot split)
os.environ["TARGET_PCT"]           = "1.5"      # April fixed target
os.environ["STOP_PCT"]             = "0.75"     # April fixed stop
os.environ["STOP_MODE"]            = "fixed"    # no trailing — hold the fixed bracket
os.environ["SHORT_REQ_MAX_SCORE"]  = "-1"       # long-only (score never < -1)
os.environ["SHORT_REQ_CHG_PCT"]    = "-999"     # belt-and-suspenders long-only
os.environ["RESCORE_INTERVAL_MIN"] = "999"      # enter early on first scan, hold to bracket
os.environ["ML_SCORE_WEIGHT"]      = "0"        # control twin: no ML
os.environ["TELEGRAM_DISABLE"]     = "1"

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
```

- [ ] **Step 2: Compile.** Run: `python3 -m py_compile scripts/v8-paper-trade.py` — Expected: no output (success).

- [ ] **Step 3: Commit.**

```bash
git add scripts/v8-paper-trade.py
git commit -m "feat(v8): April-recipe replica wrapper (NIFTY-50/top-5/long-only/fixed bracket)"
```

---

### Task 5: Wire `v8` into launch + watchdog + compare, then dry-replay verify

**Files:**
- Modify: `scripts/launch-market.sh` (ENGINES array — add after `v5_flip`)
- Modify: `scripts/crash-watchdog.sh` (ENGINES array — add after `v5_flip`, line 55)
- Modify: `scripts/engine-compare.py:18-19` (ENGINES list + LABELS)

**Interfaces:**
- Produces: a 6-engine roster (`v5 v5_classic v5_long v5_cut v5_flip v8`) consistent across launch, watchdog, and compare.

- [ ] **Step 1: launch-market.sh** — add after the `"v5_flip|scripts/v5_flip-paper-trade.py"` line:

```bash
  # V8 (TP-V8, 2026-07-06): April-recipe replica — NIFTY-50, top-5, long-only, +1.5/-0.75
  # fixed bracket, early entry. Control twin (no ML). Target: recover April +1%/65%-WR profile.
  "v8|scripts/v8-paper-trade.py"
```

- [ ] **Step 2: crash-watchdog.sh** — add after the `"v5_flip|..."` line (line 55):

```bash
  # V8 (TP-V8 2026-07-06): April-recipe replica (control twin).
  "v8|scripts/v8-paper-trade.py|docs/paper-trades/v8/${TODAY}.json|python3 scripts/v8-paper-trade.py"
```

- [ ] **Step 3: engine-compare.py** — replace lines 18–19:

```python
ENGINES = ["v5", "v5_long", "v5_classic", "v5_cut", "v5_flip"]   # active lean roster
LABELS = {"v5": "v5 (live)", "v5_long": "v5_long (RC-1 long-only)",
```
with:
```python
ENGINES = ["v5", "v5_long", "v5_classic", "v5_cut", "v5_flip", "v8"]   # active lean roster
LABELS = {"v5": "v5 (live)", "v5_long": "v5_long (RC-1 long-only)", "v8": "v8 (April replica)",
```

- [ ] **Step 4: Verify roster consistency + syntax.**

```bash
cd ~/Documents/tinker/projects/tradepilot
bash -n scripts/launch-market.sh && bash -n scripts/crash-watchdog.sh && python3 -m py_compile scripts/engine-compare.py && echo "syntax OK"
echo "launch:   $(grep -E '^\s*"v[0-9_a-z]+\|scripts/' scripts/launch-market.sh | sed 's/|.*//;s/[ \"]//g' | tr '\n' ' ')"
echo "watchdog: $(grep -E '^\s*"v[0-9_a-z]+\|scripts/' scripts/crash-watchdog.sh | sed 's/|.*//;s/[ \"]//g' | tr '\n' ' ')"
```
Expected: `syntax OK`; both lines end with `... v5_flip v8` (6 engines, consistent).

- [ ] **Step 5: Dry-replay verify the April behaviour** (no live launch — runs the engine once against current/cached data and inspects one cycle). Run:

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 scripts/v8-paper-trade.py --status 2>&1 | tail -20
grep -E "LONG|SHORT|Scan|universe|positions" logs/v8-paper-trade.log 2>/dev/null | tail -20
```
Expected: engine identity `v8`, scans ~50 NIFTY-50 names, **only `LONG ` entries (zero `SHORT`)**, and any entries show `SL:`/`TGT:` at ~0.75%/1.5% off entry. If a full market-hours cycle isn't available (off-hours), confirm at minimum: `--status` runs without error, state dir `docs/paper-trades/v8/` is created, and the log shows the NIFTY-50 universe loaded. Record findings; a full green-day validation happens post-launch.

- [ ] **Step 6: Final smoke gate.** Run: `./scripts/sarathi-verify.sh --smoke --quiet; echo "exit $?"` — Expected: `PASS`, `exit 0` (guarantees the next 08:50 auto-launch is safe).

- [ ] **Step 7: Commit.**

```bash
git add scripts/launch-market.sh scripts/crash-watchdog.sh scripts/engine-compare.py
git commit -m "feat(v8): wire April-replica into launch + watchdog + compare (roster=6)"
```

---

# PHASE 2 — v8_ml treatment (the 5-tree twin)

### Task 6: Train the 5-tree model + ship-gate evaluation

**Files:**
- Create: `scripts/train-5tree.py`
- Create (output): `prototype/v4/models/lgbm_5tree.txt`

**Interfaces:**
- Consumes: `prototype.v4.ml_engine.build_training_dataset()` (returns a DataFrame with `TRAINING_FEATURES` + `target`), `ml_engine.TRAINING_FEATURES`.
- Produces: a LightGBM model file `lgbm_5tree.txt` (`n_estimators=5`) and a printed ship-gate verdict comparing 5-tree selection vs no-ML on a time-held-out slice.

- [ ] **Step 1: Write the trainer + ship-gate.** Create `scripts/train-5tree.py`:

```python
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
from sklearn.model_selection import train_test_split

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
    print(f"dataset rows: {len(ds):,}  features: {len(feats)}")
    X, y = ds[feats].values, ds["target"].values
    # time-ordered holdout (last 20% as test) — no shuffle, to respect time
    n = len(ds); cut = int(n * 0.8)
    X_tr, X_te, y_tr, y_te = X[:cut], X[cut:], y[:cut], y[cut:]
    model = lgb.LGBMRegressor(**PARAMS)
    model.fit(X_tr, y_tr)
    preds = model.predict(X_te)
    # SHIP-GATE: does ranking by the 5-tree beat ranking by nothing (random/flat)?
    # Proxy: mean forward-return of the model's top-5% picks vs the overall mean.
    k = max(1, len(preds) // 20)
    top_idx = np.argsort(preds)[-k:]
    top_mean = float(np.mean(y_te[top_idx])); overall = float(np.mean(y_te))
    lift = top_mean - overall
    print(f"top-5% picks mean target: {top_mean:+.4f}  overall mean: {overall:+.4f}  LIFT: {lift:+.4f}")
    model.booster_.save_model(str(OUT))
    print(f"saved: {OUT}")
    verdict = "PASS" if lift > 0 else "FAIL"
    print(f"SHIP-GATE: {verdict}  (wire into v8_ml only if PASS; else launch v8_ml at weight 0)")
    return 0 if lift > 0 else 2

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Compile.** Run: `python3 -m py_compile scripts/train-5tree.py` — Expected: no output (success).

- [ ] **Step 3: Train + read the ship-gate verdict.**

Run: `cd ~/Documents/tinker/projects/tradepilot && python3 scripts/train-5tree.py; echo "gate-exit $?"`
Expected: prints dataset rows, a `LIFT:` line, `saved: .../lgbm_5tree.txt`, and `SHIP-GATE: PASS` (`gate-exit 0`) or `FAIL` (`gate-exit 2`).
- **If PASS:** proceed to Task 7 and set v8_ml weight to 0.10.
- **If FAIL:** the 5-tree does not earn its slot. Still proceed to Task 7/8 but launch `v8_ml` with `ML_SCORE_WEIGHT=0` (recording "5-tree failed ship-gate" in the wrapper docstring). This is a clean negative result — a twin with no marginal ML — and the eval will confirm it tracks v8.

- [ ] **Step 4: Confirm the protected models are untouched.**

Run: `git status --porcelain prototype/v4/models/ | grep -vE "lgbm_5tree.txt" || echo "only lgbm_5tree.txt changed — OK"`
Expected: `only lgbm_5tree.txt changed — OK` (no modification to `lgbm_intraday.txt` or tiered models).

- [ ] **Step 5: Commit.**

```bash
git add scripts/train-5tree.py prototype/v4/models/lgbm_5tree.txt
git commit -m "feat(v8_ml): train 5-tree ML tilt + ship-gate eval (candle-feature pipeline)"
```

---

### Task 7: Env-gate the ML model path

**Files:**
- Modify: `prototype/v4/ml_engine.py:39`

**Interfaces:**
- Consumes: env `ML_MODEL_PATH` (default = current `lgbm_intraday.txt`).
- Produces: module constant `MODEL_PATH` pointing at the env-supplied model, loaded by the existing `lgb.Booster(model_file=str(MODEL_PATH))` at line 714. Only matters when `ML_SCORE_WEIGHT > 0` (v8_ml); with weight 0 the model is never consulted for scoring, so no existing engine is affected.

- [ ] **Step 1: Make the model path env-overridable.** Replace line 39:

```python
MODEL_PATH = _MODEL_DIR / "lgbm_intraday.txt"
```
with:
```python
import os as _os
MODEL_PATH = Path(_os.environ["ML_MODEL_PATH"]) if _os.environ.get("ML_MODEL_PATH") else _MODEL_DIR / "lgbm_intraday.txt"
```
(If `os` and `Path` are already imported at the top of `ml_engine.py` — check the header — drop the local `import os as _os` and use `os.environ` directly.)

- [ ] **Step 2: Compile.** Run: `python3 -m py_compile prototype/v4/ml_engine.py` — Expected: no output (success).

- [ ] **Step 3: Env-check — default preserved AND override works.**

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -c "import prototype.v4.ml_engine as m; print('default:', m.MODEL_PATH.name)"
ML_MODEL_PATH=$PWD/prototype/v4/models/lgbm_5tree.txt python3 -c "import prototype.v4.ml_engine as m; print('override:', m.MODEL_PATH.name)"
```
Expected: `default: lgbm_intraday.txt` then `override: lgbm_5tree.txt`.

- [ ] **Step 4: Smoke gate.** Run: `./scripts/sarathi-verify.sh --smoke --quiet; echo "exit $?"` — Expected: `PASS`, `exit 0`.

- [ ] **Step 5: Commit.**

```bash
git add prototype/v4/ml_engine.py
git commit -m "feat(v8_ml): env-gate ML_MODEL_PATH (default lgbm_intraday.txt = unchanged)"
```

---

### Task 8: Build `v8_ml` twin + wire into launch + watchdog + compare

**Files:**
- Create: `scripts/v8_ml-paper-trade.py`
- Modify: `scripts/launch-market.sh` (ENGINES — add after `v8`)
- Modify: `scripts/crash-watchdog.sh` (ENGINES — add after `v8`)
- Modify: `scripts/engine-compare.py:18-19` (ENGINES + LABELS)

**Interfaces:**
- Consumes: Task 4's env recipe + Task 7's `ML_MODEL_PATH` + Task 6's model.
- Produces: `v8_ml` writing to `docs/paper-trades/v8_ml/`; a 7-engine roster.

- [ ] **Step 1: Create the twin wrapper** (set `ML_SCORE_WEIGHT` to `"0.10"` if Task 6 ship-gate PASSed, else `"0"`):

```python
#!/usr/bin/env python3
"""
v8_ml — the April-recipe replica + 5-tree ML tilt (treatment twin). TP-V8, 2026-07-06.

Identical to v8 in EVERY parameter except ML_SCORE_WEIGHT (0.10 vs 0) + ML_MODEL_PATH
(the 5-tree). So v8_ml - v8 P&L/WR over the same market days IS the 5-tree's marginal
contribution — a controlled single-variable test of "does a minimal ML tie-breaker help
April-recipe selection?" (Set weight to 0 here if the 5-tree failed its ship-gate.)
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]          = "v8_ml"
os.environ["UNIVERSE_FILE"]        = str(ROOT / "quant" / "universe_nifty50.txt")
os.environ["MAX_POSITIONS_TOTAL"]  = "5"
os.environ["TARGET_PCT"]           = "1.5"
os.environ["STOP_PCT"]             = "0.75"
os.environ["STOP_MODE"]            = "fixed"
os.environ["SHORT_REQ_MAX_SCORE"]  = "-1"
os.environ["SHORT_REQ_CHG_PCT"]    = "-999"
os.environ["RESCORE_INTERVAL_MIN"] = "999"
os.environ["ML_SCORE_WEIGHT"]      = "0.10"      # <- 5-tree tilt (set "0" if ship-gate FAILed)
os.environ["ML_MODEL_PATH"]        = str(ROOT / "prototype" / "v4" / "models" / "lgbm_5tree.txt")
os.environ["TELEGRAM_DISABLE"]     = "1"

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
```

- [ ] **Step 2: Compile.** Run: `python3 -m py_compile scripts/v8_ml-paper-trade.py` — Expected: no output (success).

- [ ] **Step 3: launch-market.sh** — add after the `"v8|scripts/v8-paper-trade.py"` line:

```bash
  # V8_ML (TP-V8, 2026-07-06): April replica + 5-tree ML tilt (treatment twin of v8).
  "v8_ml|scripts/v8_ml-paper-trade.py"
```

- [ ] **Step 4: crash-watchdog.sh** — add after the `"v8|..."` line:

```bash
  # V8_ML (TP-V8 2026-07-06): April replica + 5-tree tilt (treatment twin).
  "v8_ml|scripts/v8_ml-paper-trade.py|docs/paper-trades/v8_ml/${TODAY}.json|python3 scripts/v8_ml-paper-trade.py"
```

- [ ] **Step 5: engine-compare.py** — replace lines 18–19:

```python
ENGINES = ["v5", "v5_long", "v5_classic", "v5_cut", "v5_flip", "v8"]   # active lean roster
LABELS = {"v5": "v5 (live)", "v5_long": "v5_long (RC-1 long-only)", "v8": "v8 (April replica)",
```
with:
```python
ENGINES = ["v5", "v5_long", "v5_classic", "v5_cut", "v5_flip", "v8", "v8_ml"]   # active lean roster
LABELS = {"v5": "v5 (live)", "v5_long": "v5_long (RC-1 long-only)", "v8": "v8 (April replica)",
          "v8_ml": "v8_ml (April + 5-tree)",
```

- [ ] **Step 6: Verify roster consistency + syntax + twin isolation.**

```bash
cd ~/Documents/tinker/projects/tradepilot
bash -n scripts/launch-market.sh && bash -n scripts/crash-watchdog.sh && python3 -m py_compile scripts/engine-compare.py && echo "syntax OK"
echo "launch:   $(grep -E '^\s*"v[0-9_a-z]+\|scripts/' scripts/launch-market.sh | sed 's/|.*//;s/[ \"]//g' | tr '\n' ' ')"
echo "watchdog: $(grep -E '^\s*"v[0-9_a-z]+\|scripts/' scripts/crash-watchdog.sh | sed 's/|.*//;s/[ \"]//g' | tr '\n' ' ')"
# twin isolation: v8 and v8_ml wrappers must differ ONLY in ENGINE_NAME + ML_SCORE_WEIGHT + ML_MODEL_PATH
diff <(grep os.environ scripts/v8-paper-trade.py) <(grep os.environ scripts/v8_ml-paper-trade.py)
```
Expected: `syntax OK`; both roster lines end `... v8 v8_ml` (7 engines); the `diff` shows changes on exactly the `ENGINE_NAME`, `ML_SCORE_WEIGHT`, and `ML_MODEL_PATH` lines (v8_ml adds ML_MODEL_PATH) — nothing else.

- [ ] **Step 7: Final smoke gate.** Run: `./scripts/sarathi-verify.sh --smoke --quiet; echo "exit $?"` — Expected: `PASS`, `exit 0`.

- [ ] **Step 8: Commit.**

```bash
git add scripts/v8_ml-paper-trade.py scripts/launch-market.sh scripts/crash-watchdog.sh scripts/engine-compare.py
git commit -m "feat(v8_ml): 5-tree treatment twin + wire into launch/watchdog/compare (roster=7)"
```

---

## Validation (post-launch, not part of this plan)

- Next 08:50 auto-launch: `v8` + `v8_ml` join the roster; daily compare is now 7-way.
- Watch ≥2 weeks incl. ≥1 green + ≥1 red day:
  - **v8 bar:** ≥ +1%/day and ≥ 65% WR → the April recipe recovered the edge (the load-bearing result).
  - **v8_ml verdict:** marginal lift over v8 (added net P&L/WR without added drawdown) → the 5-tree earns its slot; else the ML stays retired.
- **Verify (§6 of spec) — early entry:** on the first green day, confirm v8's avg entry time is near market open (~09:20), not ~11:00. If entries are still late, `RESCORE_INTERVAL_MIN=999` was insufficient and the entry timing needs a dedicated fix before judging the recipe.

## Self-review notes (author)

- **Spec coverage:** universe (T1), position cap (T2), bracket+fixed stop (T3), long-only/early-entry via env (T4), wiring+dry-replay (T5), 5-tree+ship-gate (T6), model-path knob (T7), twin+wiring (T8), eval bar (Validation). All spec §4–§10 items mapped.
- **No-op guarantee:** every base-code change (T2/T3/T7) has an env-check step proving default==current + a smoke gate. Existing engines untouched.
- **Ship-gate branch:** T6 handles both PASS and FAIL explicitly (weight 0.10 vs 0) — no dangling "if it works" placeholder.
- **Known assumption to verify at execution:** early-entry via `RESCORE_INTERVAL_MIN` (flagged in Validation) and the NIFTY-50 cache-JSON schema (T1 Step 2 guards it).
