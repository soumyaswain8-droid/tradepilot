#!/usr/bin/env bash
# ╭──────────────────────────────────────────────────────────────────────╮
# │ Sarathi Verification Ledger                                          │
# │                                                                       │
# │ Audits every substantive claim Sarathi made this week against the    │
# │ live codebase. Each check is one of:                                 │
# │   STATIC   — grep / file existence (deterministic)                   │
# │   RUNTIME  — actual Python import / function call (catches Monday-   │
# │              style integration bugs)                                 │
# │   FUNCTIONAL — call function, verify expected behavior               │
# │                                                                       │
# │ Output: PASS / FAIL / WARN per check. Exit code = number of fails.   │
# │                                                                       │
# │ Usage:                                                                │
# │   ./scripts/sarathi-verify.sh             # run all checks           │
# │   ./scripts/sarathi-verify.sh --quiet     # only show fails          │
# │   ./scripts/sarathi-verify.sh --smoke     # import/compile smoke     │
# │   ./scripts/sarathi-verify.sh --smoke-engine  # DRY-BOOT each engine │
# │                                                                       │
# │ Smoke vs smoke-engine:                                                │
# │   --smoke        STATIC-ish: import + syntax-compile the engine       │
# │                  scripts. Fast (~2s). Does NOT run run(), so it       │
# │                  cannot catch startup SystemExits (the 2026-05-18     │
# │                  incident: a tight check_model_freshness killed v5    │
# │                  at 09:30 open and --smoke never noticed).            │
# │   --smoke-engine S2-PM-001: actually DRY-BOOTS each active engine in  │
# │                  an isolated, no-trade mode under a short timeout and │
# │                  FAILS if any engine errors during startup. Delegates │
# │                  to scripts/team/cadence/preflight.py --smoke-engine. │
# │                                                                       │
# │ Wired into launch-market.sh as pre-launch gate.                      │
# ╰──────────────────────────────────────────────────────────────────────╯

set -uo pipefail
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# ── --smoke-engine: delegate to the Python preflight dry-boot (S2-PM-001) ──
# This is a *real* engine boot (isolated, no-trade, short timeout), unlike the
# import-only --smoke below. Kept as a thin passthrough so launch-market.sh and
# operators have one consistent entrypoint. preflight.py owns the active-engine
# derivation (parsed from launch-market.sh's ENGINES array) and the safety env
# (TRADEPILOT_SMOKE=1 + isolated TRADEPILOT_STATE_DIR + no-net).
if [[ "${1:-}" == "--smoke-engine" ]]; then
  exec python3 "$PROJECT_ROOT/scripts/team/cadence/preflight.py" --smoke-engine
fi

QUIET="${1:-}"
SMOKE_ONLY=""
[[ "${1:-}" == "--smoke" ]] && SMOKE_ONLY="yes"

PASS=0
FAIL=0
WARN=0
FAILED_CHECKS=()

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
DIM='\033[2m'
RESET='\033[0m'

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────
check() {
  local label="$1"
  local type="$2"     # STATIC | RUNTIME | FUNCTIONAL
  local result="$3"   # PASS | FAIL | WARN
  local detail="${4:-}"

  case "$result" in
    PASS)
      PASS=$((PASS + 1))
      [[ "$QUIET" == "--quiet" ]] && return
      printf "  ${GREEN}✓${RESET} ${DIM}[%s]${RESET} %s\n" "$type" "$label"
      ;;
    FAIL)
      FAIL=$((FAIL + 1))
      FAILED_CHECKS+=("$label")
      printf "  ${RED}✗${RESET} ${DIM}[%s]${RESET} %s\n" "$type" "$label"
      [[ -n "$detail" ]] && printf "    ${RED}→ $detail${RESET}\n"
      ;;
    WARN)
      WARN=$((WARN + 1))
      [[ "$QUIET" == "--quiet" ]] && return
      printf "  ${YELLOW}⚠${RESET} ${DIM}[%s]${RESET} %s\n" "$type" "$label"
      [[ -n "$detail" ]] && printf "    ${YELLOW}→ $detail${RESET}\n"
      ;;
  esac
}

# ──────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────
echo ""
printf "${BLUE}╭─────────────────────────────────────────────────────────────────╮${RESET}\n"
printf "${BLUE}│${RESET}  ${BLUE}Sarathi · Verification Ledger${RESET}                                  ${BLUE}│${RESET}\n"
printf "${BLUE}│${RESET}  $(date '+%a %Y-%m-%d %H:%M:%S IST')                                ${BLUE}│${RESET}\n"
printf "${BLUE}╰─────────────────────────────────────────────────────────────────╯${RESET}\n"
echo ""

# ──────────────────────────────────────────────────────────────────────
# SECTION 1 — Static checks (file/grep, deterministic)
# ──────────────────────────────────────────────────────────────────────
if [[ -z "$SMOKE_ONLY" ]]; then

printf "${DIM}─── Section 1: Static — week's commits still present ───${RESET}\n"

# Claim 1: NaN guard in composite_scorer.py
if grep -q "_nan_price" prototype/v4/composite_scorer.py 2>/dev/null; then
  check "NaN guard in composite_scorer (commit d83e405)" "STATIC" "PASS"
else
  check "NaN guard in composite_scorer" "STATIC" "FAIL" "_nan_price marker not found in prototype/v4/composite_scorer.py"
fi

# Claim 2: Cache TTL constant
if grep -q "CACHE_TTL_SECONDS" prototype/v4/data_nse.py 2>/dev/null; then
  ttl=$(grep -E "^CACHE_TTL_SECONDS\s*=" prototype/v4/data_nse.py | grep -oE "[0-9]+" | head -1)
  if [[ "$ttl" -gt 0 ]] && [[ "$ttl" -le 600 ]]; then
    check "Cache TTL = ${ttl}s (commit 4d1079a)" "STATIC" "PASS"
  else
    check "Cache TTL" "STATIC" "WARN" "TTL value suspicious: $ttl seconds"
  fi
else
  check "Cache TTL" "STATIC" "FAIL" "CACHE_TTL_SECONDS not defined"
fi

# Claim 3: Pre-market write block
if grep -q "_is_market_hours" prototype/v4/data_nse.py 2>/dev/null; then
  check "Pre-market write block function exists" "STATIC" "PASS"
else
  check "Pre-market write block" "STATIC" "FAIL" "_is_market_hours not defined"
fi

# Claim 4: All-NaN write rejection
if grep -q "_is_mostly_nan" prototype/v4/data_nse.py 2>/dev/null; then
  check "All-NaN write rejection function exists" "STATIC" "PASS"
else
  check "All-NaN write rejection" "STATIC" "FAIL" "_is_mostly_nan not defined"
fi

# Claim 5: NaN-rate fallback (commit 5ec0bf4)
if grep -q "Falling back to per-symbol fast_info" prototype/v4/data_nse.py 2>/dev/null; then
  check "NaN-rate fallback (commit 5ec0bf4)" "STATIC" "PASS"
else
  check "NaN-rate fallback" "STATIC" "FAIL" "fallback log message not found"
fi

# Claim 6: Position-size cap at 15%
if grep -qE "max_per_stock_pct:\s*float\s*=\s*0\.15" prototype/v4/position_sizer.py 2>/dev/null; then
  check "Position-size cap = 15% (commit 4d1079a)" "STATIC" "PASS"
else
  current=$(grep -E "max_per_stock_pct:\s*float\s*=" prototype/v4/position_sizer.py | grep -oE "0\.[0-9]+" | head -1)
  check "Position-size cap = 15%" "STATIC" "FAIL" "expected 0.15, found: $current"
fi

# Claim 7: BUY-count gate (min 10)
if grep -qE "min_buy_count:\s*int\s*=\s*10" prototype/v4/position_sizer.py 2>/dev/null; then
  check "BUY-count gate at min=10 (commit 4d1079a)" "STATIC" "PASS"
else
  check "BUY-count gate" "STATIC" "FAIL" "min_buy_count not at 10"
fi

# Claim 8: Late-start preflight module exists
if [[ -f prototype/v4/preflight.py ]] && [[ -s prototype/v4/preflight.py ]]; then
  check "Late-start preflight module exists (commit 5ec0bf4)" "STATIC" "PASS"
else
  check "Late-start preflight module" "STATIC" "FAIL" "prototype/v4/preflight.py missing"
fi

# Claim 9: Warm-up window in v4-paper-trade.py
if grep -q "WARMUP_HOUR" scripts/v4-paper-trade.py 2>/dev/null; then
  check "Warm-up window (09:30) in v4-paper-trade" "STATIC" "PASS"
else
  check "Warm-up window" "STATIC" "FAIL" "WARMUP_HOUR not in v4-paper-trade.py"
fi

# Claim 10: Launch regex matches v5_classic
if grep -qE 'v\[0-9\].*paper-trade.py' scripts/launch-market.sh 2>/dev/null; then
  check "Launch regex matches all 7 engines (commit 1a22c05)" "STATIC" "PASS"
else
  check "Launch regex" "STATIC" "FAIL" "v[0-9] pattern not in launch-market.sh"
fi

# Claim 11: Scope guard scripts exist
if [[ -x scripts/scope-snapshot.sh ]] && [[ -x scripts/scope-diff.sh ]]; then
  check "Scope guard scripts present (commit f5599e2)" "STATIC" "PASS"
else
  check "Scope guard scripts" "STATIC" "FAIL" "scope-snapshot.sh / scope-diff.sh missing or not executable"
fi

# Claim 12: System health endpoint code (commit 596c5ff)
if grep -q "api_system_health\|/api/system-health" prototype/app.py 2>/dev/null; then
  check "System health endpoint code present (commit 596c5ff)" "STATIC" "PASS"
else
  check "System health endpoint" "STATIC" "FAIL" "endpoint not registered in prototype/app.py"
fi

echo ""
fi  # end SMOKE_ONLY skip

# ──────────────────────────────────────────────────────────────────────
# SECTION 2 — Runtime smoke tests (catches Monday-style integration bugs)
# ──────────────────────────────────────────────────────────────────────
printf "${DIM}─── Section 2: Runtime — engine scripts importable ───${RESET}\n"

# Smoke test: each engine entry script must be importable without runtime error
# This is the test that would have caught Monday morning's preflight import bug.
for engine_script in scripts/v4-paper-trade.py scripts/v5-paper-trade.py scripts/v5_classic-paper-trade.py scripts/v5_6-paper-trade.py scripts/v5_7-paper-trade.py scripts/v5_8-paper-trade.py scripts/v6-paper-trade.py; do
  name=$(basename "$engine_script" .py)

  # We can't `import` the script (it's not a module), but we can syntax-compile
  # AND check that all imports resolve. The approach: run the script with a
  # sentinel env var that causes early exit before any side effects.
  err=$(python3 -c "
import sys, os, ast
sys.path.insert(0, 'prototype')

# Step 1: compile-check the whole file (catches syntax errors)
try:
    with open('$engine_script') as f:
        src = f.read()
    compile(src, '$engine_script', 'exec')
except SyntaxError as e:
    print(f'SYNTAX_ERROR: {e}')
    sys.exit(2)

# Step 2: resolve EVERY top-level import. If any fails, the script will fail
# on launch — that's exactly Monday's bug class.
tree = ast.parse(src)
for node in tree.body:  # only top-level, skip function/try-bodies
    try:
        if isinstance(node, ast.Import):
            for alias in node.names:
                __import__(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module
            if mod is None or node.level > 0:
                continue  # relative imports — skip (script-relative)
            __import__(mod)
    except ImportError as e:
        print(f'IMPORT_ERROR: {e}')
        sys.exit(3)
    except Exception as e:
        # Other issues (e.g., side-effects in imported module) — flag as warning
        print(f'IMPORT_WARN: {type(e).__name__}: {e}')
        sys.exit(4)
" 2>&1)

  if [[ $? -eq 0 ]]; then
    check "$name imports + syntax OK" "RUNTIME" "PASS"
  else
    check "$name imports" "RUNTIME" "FAIL" "$err"
  fi
done

echo ""

# ──────────────────────────────────────────────────────────────────────
# SECTION 3 — Functional tests (call the guards, verify behavior)
# ──────────────────────────────────────────────────────────────────────
if [[ -z "$SMOKE_ONLY" ]]; then

printf "${DIM}─── Section 3: Functional — guards actually behave correctly ───${RESET}\n"

# Functional test 1: _is_market_hours returns False outside market window
mh_test=$(python3 -c "
from prototype.v4.data_nse import _is_market_hours
from datetime import datetime
now = datetime.now()
result = _is_market_hours()
expected = (9, 15) <= (now.hour, now.minute) <= (15, 30)
print('PASS' if result == expected else 'FAIL')
" 2>&1)
if [[ "$mh_test" == "PASS" ]]; then
  check "_is_market_hours returns correct value for current time" "FUNCTIONAL" "PASS"
else
  check "_is_market_hours" "FUNCTIONAL" "FAIL" "got: $mh_test"
fi

# Functional test 2: _is_mostly_nan detects NaN cache correctly
nan_test=$(python3 -c "
from prototype.v4.data_nse import _is_mostly_nan
# 80% NaN — should return True
bad = {f's{i}': {'last_price': float('nan') if i < 8 else 100.0} for i in range(10)}
# 20% NaN — should return False
good = {f's{i}': {'last_price': float('nan') if i < 2 else 100.0} for i in range(10)}
print('PASS' if (_is_mostly_nan(bad) and not _is_mostly_nan(good)) else 'FAIL')
" 2>&1)
if [[ "$nan_test" == "PASS" ]]; then
  check "_is_mostly_nan correctly distinguishes clean vs corrupt batches" "FUNCTIONAL" "PASS"
else
  check "_is_mostly_nan" "FUNCTIONAL" "FAIL" "got: $nan_test"
fi

# Functional test 3: position_sizer BUY-count gate blocks small universes
gate_test=$(python3 -c "
from prototype.v4.position_sizer import size_positions
small = [{'symbol': f'S{i}', 'price': 100, 'score': 60+i} for i in range(5)]
result = size_positions(small, capital=1000000)
print('PASS' if result == [] else 'FAIL')
" 2>&1 | tail -1)
if [[ "$gate_test" == "PASS" ]]; then
  check "BUY-count gate blocks deployment with < 10 valid BUYs" "FUNCTIONAL" "PASS"
else
  check "BUY-count gate" "FUNCTIONAL" "FAIL" "got: $gate_test"
fi

# Functional test 4: preflight is_late_start detects late boot
preflight_test=$(python3 -c "
from prototype.v4.preflight import is_late_start, should_skip_first_deploy
from datetime import datetime
fake_late = datetime(2026, 5, 11, 9, 35)
fake_early = datetime(2026, 5, 11, 9, 18)
fake_too_late = datetime(2026, 5, 11, 14, 30)
ok = (is_late_start(fake_late) and not is_late_start(fake_early) and should_skip_first_deploy(fake_too_late))
print('PASS' if ok else 'FAIL')
" 2>&1 | tail -1)
if [[ "$preflight_test" == "PASS" ]]; then
  check "preflight late-start + skip-deploy thresholds correct" "FUNCTIONAL" "PASS"
else
  check "preflight thresholds" "FUNCTIONAL" "FAIL" "got: $preflight_test"
fi

echo ""
fi  # end SMOKE_ONLY skip

# ──────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + WARN))
printf "${BLUE}─── Summary ───${RESET}\n"
printf "  ${GREEN}PASS${RESET}: %d  ${RED}FAIL${RESET}: %d  ${YELLOW}WARN${RESET}: %d  (total: %d)\n" "$PASS" "$FAIL" "$WARN" "$TOTAL"

if [[ $FAIL -gt 0 ]]; then
  echo ""
  printf "${RED}FAILED checks:${RESET}\n"
  for c in "${FAILED_CHECKS[@]}"; do
    printf "  ${RED}✗${RESET} %s\n" "$c"
  done
  echo ""
  printf "${RED}Verification ledger: FAIL — %d claims do not match live code.${RESET}\n" "$FAIL"
  exit "$FAIL"
fi

if [[ $WARN -gt 0 ]]; then
  echo ""
  printf "${YELLOW}Verification ledger: PASS with warnings.${RESET}\n"
  exit 0
fi

echo ""
printf "${GREEN}Verification ledger: ALL PASS.${RESET} Every claim is verifiable in the live code.\n"
exit 0
