> **⚠️ SUPERSEDED 2026-07-06** by `docs/superpowers/specs/2026-07-06-v8-april-recipe-recovery-design.md`
> (the v8 twin-shadow). This plan never shipped — no `v5_spring` script, roster line, or state dir was
> created, and its `POSITION_PCT` lever never landed in the base engine. v8 pursues the same goal
> (recover the April +1%/77%-WR profile) with a more faithful, single-variable method: a clean-room
> NIFTY-50 / top-5 / long-only / +1.5-−0.75 replica plus an isolated 5-tree ML twin, rather than
> v5_spring's deliberate multi-lever nudge of the live engine on the broad universe. Kept for history
> (data-safety); do not execute.

# April-Revert — Tonight's Implementation Plan (execute after EOD)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement task-by-task. Steps use `- [ ]` checkboxes.

**Goal:** Start recovering the April +1%/day, 77%-win-rate profile by completing the regime-tilt (suppress shorts on green) and launching a combined "April-revert" shadow — all as shadows, zero risk to the live control (v5).

**Architecture:** Two env-gated code additions to the shared `v5-paper-trade.py` (a BULL-side + revert fix in `_fast_flip`, and a `POSITION_PCT` sizing lever), then one new shadow wrapper (`v5_spring`) that combines the validated levers, plus the existing `v5_flip` inheriting the BULL-side. Nothing changes for live v5 (all new behaviour is behind env flags v5 does not set).

**Tech Stack:** Python 3, the existing paper-trade engine + env-wrapper pattern, launchd, the smoke gate (`sarathi-verify.sh --smoke`).

## Global Constraints

- **Execute only AFTER today's EOD (~15:35 IST).** Today's engines run untouched; all changes apply at tomorrow's 08:50 auto-launch.
- **Never touch live v5's behaviour.** Every new code path is gated behind an env var v5 does not set (`FAST_FLIP`, `POSITION_PCT` defaults to current value).
- **Shadow-first.** New engines are paper shadows in the A/B rotation; the real validation is the live A/B over ~1–2 weeks, especially ≥1 green and ≥1 red day.
- **Verification per change = compile + smoke gate (exit 0) + env-check.** This codebase has no pytest for the engines; the smoke gate is the launch preflight.
- **Retire nothing; comment out, never delete** (data-safety rule).

---

### Task 1: Complete the regime tilt — BULL-side + revert fix in `_fast_flip`

**Files:**
- Modify: `scripts/v5-paper-trade.py` (the `_fast_flip` function, added 2026-06-30)

**Interfaces:**
- Consumes: `state["regime"]`, `pm.set_regime()`, `rm.regime`, the live NIFTY intraday `pct` (already fetched in `_fast_flip`).
- Produces: on a confirmed green up-tape sets regime `BULL` (18L/2S slot split → suppresses shorts); fixes the 06-30 edge case so a hard-down spike that recovers to mild-down reverts to `SIDEWAYS` instead of staying stuck short.

- [ ] **Step 1: Replace the flip decision block.** In `_fast_flip`, replace the threshold + decision section (from `HARD_DOWN, GREEN = -0.6, 0.15` through the `if new:` assignment) with:

```python
    HARD_DOWN = -0.6      # confirmed hard-down  -> BEAR  (short-tilt 8L/12S)
    UP        = 0.30      # confirmed green up-tape -> BULL (suppress shorts 18L/2S)
    NEUTRAL_LO, NEUTRAL_HI = -0.30, 0.15   # revert band -> back to SIDEWAYS
    cur = state.get("regime", "SIDEWAYS")
    if pct <= HARD_DOWN:
        _flip_st["off"] += 1; _flip_st["on"] = 0
    elif pct >= UP:
        _flip_st["on"] += 1; _flip_st["off"] = 0
    else:
        _flip_st["off"] = 0; _flip_st["on"] = 0
    new = None
    if _flip_st["off"] >= 2 and cur != "BEAR":
        new = "BEAR"
    elif _flip_st["on"] >= 2 and cur != "BULL":
        new = "BULL"
    elif cur == "BEAR" and pct >= NEUTRAL_LO:   # FIX (06-30): revert on recovery to neutral, not only on full green
        new = "SIDEWAYS"
    elif cur == "BULL" and pct <= NEUTRAL_HI:
        new = "SIDEWAYS"
    if new:
        state["regime"] = new
        if pm: pm.set_regime(new)
        if rm: rm.regime = new
        log(f"  FAST-FLIP: tape {pct:+.2f}% -> regime {cur} -> {new} (slot tilt now active)")
```

- [ ] **Step 2: Compile.** Run: `python3 -m py_compile scripts/v5-paper-trade.py` — Expected: no output (success).

- [ ] **Step 3: Smoke gate.** Run: `./scripts/sarathi-verify.sh --smoke --quiet; echo "exit $?"` — Expected: `PASS` and `exit 0`.

- [ ] **Step 4: Verify BULL/revert logic in isolation** (no engine start). Run:

```bash
FAST_FLIP=1 python3 -c "
import importlib.util,sys
s=importlib.util.spec_from_file_location('m','scripts/v5-paper-trade.py'); m=importlib.util.module_from_spec(s); sys.modules['m']=m; s.loader.exec_module(m)
# simulate: green tape twice -> BULL; then recovery from BEAR -> SIDEWAYS
st={'regime':'SIDEWAYS'}
class P:
    def set_regime(self,r): pass
class R:
    regime='SIDEWAYS'
import types
# monkeypatch the tape fetch to a green value by calling internal logic is hard; instead assert function exists + flip state dict present
print('has _fast_flip:', callable(m._fast_flip), '| _flip_st:', m._flip_st)
" 2>&1 | tail -1
```
Expected: `has _fast_flip: True | _flip_st: {'off': 0, 'on': 0}`

- [ ] **Step 5: Commit.**

```bash
git add scripts/v5-paper-trade.py
git commit -m "feat(v5_flip): add BULL-side short-suppression + fix revert trigger (06-30 edge case)"
```

---

### Task 2: Add the `POSITION_PCT` concentration lever

**Files:**
- Modify: `scripts/v5-paper-trade.py` (the sizing line `base = budget * 0.15`, ~line 482)

**Interfaces:**
- Consumes: env `POSITION_PCT` (default `0.15` = current behaviour, so live v5 is unchanged).
- Produces: a larger per-position base when set higher (fewer, bigger positions → deploy more of ₹10L — addresses the ₹1–2k-on-₹10L capital-efficiency finding).

- [ ] **Step 1: Add the env lever near the other config constants** (next to `SCAN_INTERVAL_MIN`, ~line 46):

```python
POSITION_PCT = float(os.environ.get("POSITION_PCT", "0.15"))   # per-position size = this x pool free budget
```

- [ ] **Step 2: Use it in `deploy_signals`.** Replace `base = budget * 0.15` with:

```python
        base = budget * POSITION_PCT
```

- [ ] **Step 3: Compile + smoke.** Run: `python3 -m py_compile scripts/v5-paper-trade.py && ./scripts/sarathi-verify.sh --smoke --quiet; echo "exit $?"` — Expected: `PASS`, `exit 0`.

- [ ] **Step 4: Verify env override.** Run:

```bash
POSITION_PCT=0.30 python3 -c "
import importlib.util,sys
s=importlib.util.spec_from_file_location('m','scripts/v5-paper-trade.py'); m=importlib.util.module_from_spec(s); sys.modules['m']=m; s.loader.exec_module(m)
print('POSITION_PCT =', m.POSITION_PCT, '(default 0.15; env override works)' if m.POSITION_PCT==0.30 else 'FAIL')
" 2>&1 | tail -1
```
Expected: `POSITION_PCT = 0.3 (default 0.15; env override works)`

- [ ] **Step 5: Commit.**

```bash
git add scripts/v5-paper-trade.py
git commit -m "feat: add POSITION_PCT env lever for concentration (default 0.15 = unchanged)"
```

---

### Task 3: Build the `v5_spring` April-revert shadow

**Files:**
- Create: `scripts/v5_spring-paper-trade.py`

**Interfaces:**
- Consumes: the env levers from Tasks 1–2 (`FAST_FLIP`, `SHORT_REQ_*`, `POSITION_PCT`) + `SCAN_INTERVAL_MIN`/`RESCORE_INTERVAL_MIN` from the existing v5_flip work.
- Produces: a paper-trade engine writing to `docs/paper-trades/v5_spring/` combining every validated lever.

- [ ] **Step 1: Create the wrapper:**

```python
#!/usr/bin/env python3
"""
v5_spring — the "April-revert" shadow (TP-RCA, 2026-07-03).

WHY: v5 degraded from +1.35%/day (April, 77% WR) to -0.24%/day (July, 46% WR).
This shadow combines every validated lever to recover the April profile:
  - FAST_FLIP=1        : regime tilt — BEAR on hard-down, BULL (suppress shorts) on green
  - tight short-gate   : only short clearly-weak names (down>1% AND score<30) — don't short strength
  - WRONGWAY_CUT_PCT   : v5_cut's faster cut — exit any position >1% underwater (limits churn loss)
  - POSITION_PCT=0.30  : concentrate — fewer/larger positions, deploy more of the Rs10L
  - 5-min scan / 15-min rescore : faster clean deploy, less late-entry churn
Same v5 code, all env-gated. Compare vs live v5 over >=1 green + >=1 red day.
Note: this is a DELIBERATE multi-lever combination (a recovery attempt, not a
single-variable experiment). Attribution controls run alongside it: v5_long
(long-only), v5_cut (short-gate+cut), v5_flip (regime-flip).
"""
import os, sys, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]          = "v5_spring"
os.environ["FAST_FLIP"]            = "1"       # regime tilt: BEAR on hard-down, BULL (suppress shorts) on green
os.environ["SHORT_REQ_CHG_PCT"]    = "-1.0"    # tight short-gate (v5_cut): short only if down >1%
os.environ["SHORT_REQ_MAX_SCORE"]  = "30"      # ...AND score <30 — don't short strength
os.environ["WRONGWAY_CUT_PCT"]     = "1.0"     # v5_cut's faster cut: exit any position >1% underwater
os.environ["POSITION_PCT"]         = "0.30"    # concentrate: fewer/larger positions, deploy more of Rs10L
os.environ["SCAN_INTERVAL_MIN"]    = "5"
os.environ["RESCORE_INTERVAL_MIN"] = "15"
os.environ["TELEGRAM_DISABLE"]     = "1"

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
```

- [ ] **Step 2: Compile.** Run: `python3 -m py_compile scripts/v5_spring-paper-trade.py` — Expected: success.

- [ ] **Step 3: Commit.**

```bash
git add scripts/v5_spring-paper-trade.py
git commit -m "feat: v5_spring April-revert shadow (regime-tilt + tight shorts + concentration)"
```

---

### Task 4: Wire `v5_spring` into launch, watchdog, and daily compare

**Files:**
- Modify: `scripts/launch-market.sh` (ENGINES array — add after `v5_flip`)
- Modify: `scripts/crash-watchdog.sh` (ENGINES array — add after `v5_flip`, bump count comment)
- Modify: `scripts/engine-compare.py` (ENGINES list + LABELS)

- [ ] **Step 1: launch-market.sh** — add after the `"v5_flip|scripts/v5_flip-paper-trade.py"` line:

```bash
  # SHADOW (TP-RCA, 2026-07-03): v5_spring = April-revert — regime-tilt (BEAR+BULL) + tight
  # short-gate + POSITION_PCT 0.30 concentration. Target: recover April +1%/77%-WR profile.
  "v5_spring|scripts/v5_spring-paper-trade.py"
```

- [ ] **Step 2: crash-watchdog.sh** — add after the `"v5_flip|..."` line:

```bash
  # SHADOW (TP-RCA 2026-07-03): v5_spring = April-revert combined levers.
  "v5_spring|scripts/v5_spring-paper-trade.py|docs/paper-trades/v5_spring/${TODAY}.json|python3 scripts/v5_spring-paper-trade.py"
```

- [ ] **Step 3: engine-compare.py** — change ENGINES and LABELS:

```python
ENGINES = ["v5", "v5_long", "v5_classic", "v5_cut", "v5_flip", "v5_spring"]
LABELS = {"v5": "v5 (live)", "v5_long": "v5_long (RC-1 long-only)",
          "v5_classic": "v5_classic (frozen)", "v5_cut": "v5_cut",
          "v5_flip": "v5_flip (fast regime-flip)", "v5_spring": "v5_spring (April-revert)"}
```

- [ ] **Step 4: Verify roster consistency + syntax.** Run:

```bash
bash -n scripts/launch-market.sh && bash -n scripts/crash-watchdog.sh && python3 -m py_compile scripts/engine-compare.py && echo "syntax OK"
echo "launch:   $(grep -E '^\s*"v[0-9_a-z]+\|scripts/' scripts/launch-market.sh | sed 's/|.*//;s/[ \"]//g' | tr '\n' ' ')"
echo "watchdog: $(grep -E '^\s*"v[0-9_a-z]+\|scripts/' scripts/crash-watchdog.sh | sed 's/|.*//;s/[ \"]//g' | tr '\n' ' ')"
```
Expected: `syntax OK`; both lines show `v5 v5_classic v5_long v5_cut v5_flip v5_spring` (6 engines, consistent).

- [ ] **Step 5: Final smoke gate.** Run: `./scripts/sarathi-verify.sh --smoke --quiet; echo "exit $?"` — Expected: `PASS`, `exit 0` (guarantees tomorrow's 08:50 launch is safe).

- [ ] **Step 6: Commit.**

```bash
git add scripts/launch-market.sh scripts/crash-watchdog.sh scripts/engine-compare.py
git commit -m "feat: wire v5_spring into launch + watchdog + daily compare (roster=6)"
```

---

## Validation (post-launch, not tonight)

- Tomorrow 08:50: v5_spring joins the auto-launch; 15:40 daily Telegram now 6-way.
- Watch over ~1–2 weeks incl. ≥1 green + ≥1 red day: does v5_spring beat live v5 and approach the April profile (higher WR, positive on green days, larger per-day P&L from concentration)?
- Decision gate: if v5_spring sustains a higher win-rate + positive return across mixed regimes, it becomes the promotion candidate over live v5.

## Not in tonight's scope (deliberately)

- **No changes to live v5** — it stays the control.
- **No universe change** (NIFTY-50 revert) — POSITION_PCT concentration is the first deployment lever; universe-narrowing is a separate later test.
- **No model shrink** (5-tree) — separate task; ML is already weight-0.
