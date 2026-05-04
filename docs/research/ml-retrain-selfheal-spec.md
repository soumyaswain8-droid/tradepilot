# ML Auto-Retrain Self-Healing on Engine Startup — Spec

**Date:** 2026-04-27
**Owner:** Soumya
**Status:** SPEC ONLY — engine code stays uncommitted until weekend review (Thu 04-30)
**Source incident:** This morning's startup outage (2026-04-27, 09:15-11:00 IST)
**Position in tonight's queue:** Item #1 in `docs/TONIGHT_TUNEUPS_2026-04-27.md`

---

## 1. Problem Statement

This morning (2026-04-27) v5/v5_6/v5_7 all refused to start because the ML model file at `prototype/v4/models/lgbm_intraday.txt` was 6 days old. The freshness guard in `prototype/utils/signal_guards.py:203` (`check_model_freshness`) raised `SystemExit` with the message:

```
ML model is 6 days old (max allowed: 3). Retrain likely failing silently.
Check logs/ml-retrain.log. Refusing to trade with stale model.
```

The freshness guard worked exactly as designed — it caught the stale model. But the surrounding system did not:

- Saturday's scheduled retrain did not run (cron / launchd misfire — root cause TBD).
- All three engines died on boot at ~09:15 IST.
- We had to manually run `scripts/retrain-ml.sh` (~5 min) before any engine could start.
- Net trading time burned: **~2 hours** (engines back up at ~11:05 IST, missed the high-volume open + first hour).

### Cost in context

| Loss | Value |
|---|---:|
| Trading hours lost (3 engines × ~2 h) | 6 engine-hours |
| Counterfactual P&L on a normal day (avg ~+Rs 1k/engine/morning) | ~Rs 3,000 forgone |
| Operator time to diagnose + manual retrain + relaunch | ~30 min |
| Pre-market Telegram alerts noise (3× SystemExit messages) | UX cost |

The freshness check is **doing the right thing** (refusing to trade with a stale model is correct). The fix is to make the system **self-healing**: if the model is stale at startup, attempt to retrain automatically before aborting. Only escalate to a hard SystemExit if the retrain itself fails or the model remains stale after retrain.

---

## 2. Spec — Self-Healing Freshness Check

### 2.1 New helper: `check_and_refresh_model()`

A wrapper around the existing `check_model_freshness()` that adds automatic retrain on stale-detection. The existing function stays untouched (used by code paths that should NOT auto-retrain — e.g., mid-trading-day re-validation).

**Signature:**
```python
def check_and_refresh_model(
    model_path: Path | str = None,
    max_age_days: int = 3,
    auto_refresh: bool = True,
    refresh_window_start: str = "08:00",
    refresh_window_end:   str = "09:30",
    refresh_timeout_secs: int = 480,   # 8 min — typical retrain ~5 min
    alert: bool = True,
) -> bool:
    ...
```

### 2.2 Behavior matrix

| Scenario | `auto_refresh` | Within window? | Action |
|---|:---:|:---:|---|
| Model fresh (≤ 3 days) | any | any | Return True (no-op) |
| Model stale, `auto_refresh=False` | False | any | Existing behavior — `SystemExit` |
| Model stale, outside 08:00–09:30 IST | True | No | `SystemExit` (don't retrain mid-session) |
| Model stale, in window, retrain succeeds, model now fresh | True | Yes | Telegram alert "Auto-retrained ✓ — engines proceeding"; return True |
| Model stale, in window, retrain script exits non-zero | True | Yes | `SystemExit` with retrain stderr tail |
| Model stale, in window, retrain hangs > 8 min | True | Yes | `subprocess.TimeoutExpired` → kill child → `SystemExit` |
| Model stale, in window, retrain succeeds but model still > 3 days old | True | Yes | `SystemExit` (something is structurally broken) |

### 2.3 Window rationale (08:00–09:30 IST)

- Pre-market data refresh window. Yahoo Finance has fresh prior-day OHLCV by ~07:30 IST.
- Bounded: refusing to retrain after 09:30 prevents the engine from auto-retraining at, say, 14:00 IST after a config reload — which would cause a 5-min trading outage mid-session.
- 09:30 cap also matches market-open guard: if we can't finish retrain by then, hard-abort and let the operator decide.

### 2.4 Pre-flight retrain in launch script — `[3.5/9]`

**Critical:** without this, all 7 engines (v5, v5_6, v5_7, plus 4 future variants) will detect the stale model on boot and each spawn a concurrent `retrain-ml.sh` — 7 simultaneous Yahoo downloads + 7 LightGBM training runs. Yahoo will rate-limit, training will thrash, and we'll get a worse outage than today.

Add a single pre-flight check to `scripts/launch-market.sh` BEFORE any engine starts:

```
[1/9] Pre-market data refresh
[2/9] Health check
[3/9] Validate config
[3.5/9] Pre-flight ML model freshness  <-- NEW
[4/9] Launch v5
[5/9] Launch v5_6
...
```

Step 3.5 runs `check_and_refresh_model()` exactly once. If it returns True (fresh after retrain), all subsequent engine boots find a fresh model and skip their own auto-refresh (the `check_and_refresh_model()` call inside each engine becomes a fast no-op). If it raises `SystemExit`, the launch script aborts before spawning any engines — clean failure mode, no half-launched fleet.

### 2.5 Env var

```
ML_AUTO_RETRAIN_ON_STARTUP=true   # Default for v5, v5_6, v5_7
ML_AUTO_RETRAIN_ON_STARTUP=false  # Disable in CI/backtest contexts
```

Read in `scripts/launch-market.sh` step 3.5 and in each engine's startup. When `false`, `check_and_refresh_model()` falls through to the existing `check_model_freshness()` behavior (hard-abort on stale).

---

## 3. Implementation Sketch

### File: `prototype/utils/signal_guards.py`

Add new helper below the existing `check_model_freshness()`:

```python
import subprocess
import os
from datetime import datetime, time as dt_time

def check_and_refresh_model(
    model_path: Path | str = None,
    max_age_days: int = 3,
    auto_refresh: bool = True,
    refresh_window_start: str = "08:00",
    refresh_window_end:   str = "09:30",
    refresh_timeout_secs: int = 480,
    alert: bool = True,
) -> bool:
    """Self-healing freshness check. Auto-triggers retrain if stale and in window.

    Wraps check_model_freshness(). Used at engine startup; mid-session callers
    should keep using check_model_freshness() directly (no auto-retrain).
    """
    # Fast path: model is fresh
    if check_model_freshness(model_path, max_age_days, alert=False, abort=False):
        return True

    # Stale. Decide whether to auto-refresh.
    if not auto_refresh or os.getenv("ML_AUTO_RETRAIN_ON_STARTUP", "true").lower() != "true":
        # Fall through to existing behavior — hard abort
        return check_model_freshness(model_path, max_age_days, alert=alert, abort=True)

    # Window check
    now = datetime.now().time()
    win_start = dt_time(*map(int, refresh_window_start.split(":")))
    win_end   = dt_time(*map(int, refresh_window_end.split(":")))
    if not (win_start <= now <= win_end):
        msg = (f"⚠️ ML model stale and outside auto-refresh window "
               f"({refresh_window_start}-{refresh_window_end} IST). Aborting.")
        if alert:
            send_telegram_alert(msg)
        raise SystemExit(msg)

    # Trigger retrain
    repo_root = Path(__file__).resolve().parents[2]
    retrain_script = repo_root / "scripts" / "retrain-ml.sh"
    if alert:
        send_telegram_alert(f"⚙️ ML model stale — auto-retraining (timeout {refresh_timeout_secs}s)...")

    try:
        result = subprocess.run(
            ["bash", str(retrain_script)],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=refresh_timeout_secs,
        )
    except subprocess.TimeoutExpired:
        msg = f"⚠️ ML auto-retrain TIMED OUT after {refresh_timeout_secs}s. Aborting."
        if alert:
            send_telegram_alert(msg)
        raise SystemExit(msg)

    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "")[-400:]
        msg = f"⚠️ ML auto-retrain FAILED (exit {result.returncode}). Tail: {tail}"
        if alert:
            send_telegram_alert(msg)
        raise SystemExit(msg)

    # Re-check freshness — must be fresh now
    if not check_model_freshness(model_path, max_age_days, alert=False, abort=False):
        msg = "⚠️ ML auto-retrain completed but model is STILL stale. Aborting."
        if alert:
            send_telegram_alert(msg)
        raise SystemExit(msg)

    if alert:
        send_telegram_alert("✅ Auto-retrained stale model — engines proceeding")
    return True
```

### File: `scripts/launch-market.sh`

Insert step 3.5 between step 3 (config validation) and step 4 (first engine launch):

```bash
echo ""
echo "[3.5/9] Pre-flight ML model freshness check..."
python3 -c "
from prototype.utils.signal_guards import check_and_refresh_model
check_and_refresh_model(auto_refresh=True)
" || { echo "FATAL: ML pre-flight failed. Engines NOT launched."; exit 1; }
echo "  Done"
```

### Engine-side change (illustrative — not required for v5/v5_6/v5_7 if launch-script does pre-flight)

For engines that may be launched standalone (outside `launch-market.sh`), replace the existing `check_model_freshness()` call at engine startup with `check_and_refresh_model()`. With pre-flight from launch script, this becomes a fast no-op (model is already fresh).

**LOC estimate:** ~50 lines total (helper ~45, launch-script step ~5).

---

## 4. Acceptance Criteria

Before promoting to production (after weekend 04-30 → 05-02):

| Criterion | Target |
|---|---:|
| Engine launched with 6-day-old model + `ML_AUTO_RETRAIN_ON_STARTUP=true` | retrain triggers, completes, engine proceeds within 10 min |
| Engine launched with 6-day-old model + `ML_AUTO_RETRAIN_ON_STARTUP=false` | hard `SystemExit` (existing behavior preserved) |
| Engine launched with fresh model | no retrain triggered, fast-path return (latency < 50 ms) |
| Engine launched at 14:00 IST with stale model | hard `SystemExit` (outside window) — does NOT retrain mid-session |
| Pre-flight in `launch-market.sh` runs exactly once across 7 engine launches | confirmed via single `logs/ml-retrain.log` write per launch |
| Retrain hangs > 8 min | child killed, `SystemExit` with timeout message |
| Telegram alerts | exactly 2 messages on success: "auto-retraining..." + "✓ proceeding" |
| Retrain script exits non-zero | `SystemExit` with stderr tail (≤ 400 chars) in alert |

---

## 5. Risks and Open Questions

| Risk | Likelihood | Mitigation |
|---|---|---|
| 7 engines all spawn retrain concurrently (race condition) | High without pre-flight | **Pre-flight step 3.5 in launch-market.sh is the primary mitigation.** Without it, this risk is critical. |
| Retrain hangs on Yahoo Finance API rate limit | Medium | 8-min timeout kills the subprocess; operator falls back to manual retrain |
| Yahoo data fetch fails (network outage) | Medium | Retrain script returns non-zero; we abort with stderr tail; operator can rerun manually after fixing connectivity |
| Retrain succeeds but model file timestamp is in the past (clock skew) | Low | Re-check uses same `mtime` logic; if still > 3 days, hard-abort. Log file timestamps for diagnosis. |
| Pre-flight succeeds but engine crashes immediately after — operator confused about retrain status | Low | Telegram alert sequence is the audit trail; logs/ml-retrain.log is timestamped |
| Subprocess inherits stale env vars from launchd context | Low | Pass explicit `env=os.environ.copy()` if needed; current retrain script is env-agnostic |
| Auto-retrain disguises a real underlying problem (e.g., the cron itself broken) | Medium | Telegram alert is the signal — every "auto-retrained" message means "investigate why the scheduled retrain didn't fire"; do NOT treat as silent recovery |
| Retrain partially completes (data refreshed, training crashes) leaves data dir in mixed state | Low | Retrain script could move to atomic-write pattern in a follow-up; out of scope for this spec |

---

## 6. Phasing

| Phase | Scope | Timing |
|---|---|---|
| Phase 1 (this spec) | Spec only — `check_and_refresh_model()` + launch-script step 3.5 + env var | Tonight (04-27) |
| Phase 2 | Implement helper in `signal_guards.py`, add launch-script step | Weekend 04-30 → 05-02 |
| Phase 3 | Verify with intentional stale-model test (touch backdated mtime, run launch script) | 05-02 |
| Phase 4 | Production rollout (after Thu 04-30 v5 commit decision) | After weekend 05-02 |
| Phase 5 (follow-up) | Investigate root cause of Saturday cron miss; add cron health alert | Next week |

---

## 7. Tonight's Output Summary

This document is the deliverable for tonight's Item #1.

- ✓ Spec written (sections 1-6)
- ✓ Self-healing helper signature and behavior matrix defined
- ✓ Pre-flight launch-script step `[3.5/9]` specified to prevent 7-engine concurrent retrain race
- ✓ Env var `ML_AUTO_RETRAIN_ON_STARTUP` defined (default true for v5/v5_6/v5_7)
- ✓ Implementation sketch sized at ~50 LOC
- ✓ Acceptance criteria defined (8 measurable checks)
- ✓ Risk register with primary risk called out (concurrent retrain race)
- ✓ Phased rollout plan

**No engine code touched.** Per active rule, all code work happens after Thu 04-30 v5 observation decision.
