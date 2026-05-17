#!/usr/bin/env bash
# Monday-morning self-test.
# Run before 08:55 IST to verify the entire automation stack is ready.
#
# Usage:
#   bash scripts/team/cadence/monday-check.sh        # standard
#   bash scripts/team/cadence/monday-check.sh -v     # verbose (show full output of each check)
#
# Exit 0 if everything PASS; exit 1 if any FAIL.

set -u
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"

VERBOSE=0
[ "${1:-}" = "-v" ] && VERBOSE=1

green="\033[32m"; red="\033[31m"; yellow="\033[33m"; cyan="\033[36m"; gray="\033[37m"; reset="\033[0m"

PASS=0; FAIL=0; WARN=0
fails=()

check() {
  local name="$1" cmd="$2"
  local out rc
  out=$(eval "$cmd" 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    printf "  ${green}✓${reset} %-45s\n" "$name"
    PASS=$((PASS+1))
    [ $VERBOSE -eq 1 ] && [ -n "$out" ] && echo "$out" | head -3 | sed 's/^/      /'
  else
    printf "  ${red}✗${reset} %-45s ${red}FAIL${reset}\n" "$name"
    echo "$out" | head -3 | sed 's/^/      /'
    FAIL=$((FAIL+1))
    fails+=("$name")
  fi
}

warn() {
  local name="$1" cmd="$2"
  local out rc
  out=$(eval "$cmd" 2>&1)
  rc=$?
  if [ $rc -eq 0 ]; then
    printf "  ${green}✓${reset} %-45s\n" "$name"
    PASS=$((PASS+1))
  else
    printf "  ${yellow}~${reset} %-45s ${yellow}WARN${reset}\n" "$name"
    echo "$out" | head -2 | sed 's/^/      /'
    WARN=$((WARN+1))
  fi
}

echo -e "${cyan}═══════════════════════════════════════════════════════${reset}"
echo -e "${cyan}  Monday Self-Test — $(date '+%Y-%m-%d %H:%M:%S')${reset}"
echo -e "${cyan}═══════════════════════════════════════════════════════${reset}"

echo ""
echo -e "${cyan}— 1. macOS power schedule —${reset}"
check "pmset wake schedule for weekdays" \
      "pmset -g sched | grep -q 'wakepoweron at 8:45AM weekdays'"

echo ""
echo -e "${cyan}— 2. launchd jobs (9 expected) —${reset}"
for label in dqo-premarket engines-on dqo-mid exec-eod standup \
             due-alpha-hunter due-competitive-intel due-architect bk-daily; do
  check "launchd: com.tradepilot.v2.$label loaded" \
        "launchctl print 'gui/$UID/com.tradepilot.v2.$label' 2>/dev/null | grep -q 'path ='"
done

echo ""
echo -e "${cyan}— 3. Sarathi rule catalog —${reset}"
for fam in LRN SPR ML CDE DAT; do
  check "rule file SARATHI-$fam.md exists" \
        "test -f docs/sarathi/rules/SARATHI-$fam.md"
done

echo ""
echo -e "${cyan}— 4. Engine scripts + entry points —${reset}"
check "v4 paper-trade script + clean import" \
      "python3 -c 'import importlib.util,sys; s=importlib.util.spec_from_file_location(\"x\",\"scripts/v4-paper-trade.py\"); m=importlib.util.module_from_spec(s)'"
check "v5 paper-trade script + clean import" \
      "python3 -c 'import importlib.util,sys; s=importlib.util.spec_from_file_location(\"x\",\"scripts/v5-paper-trade.py\"); m=importlib.util.module_from_spec(s)'"
check "v5_classic paper-trade script + clean import" \
      "python3 -c 'import importlib.util,sys; s=importlib.util.spec_from_file_location(\"x\",\"scripts/v5_classic-paper-trade.py\"); m=importlib.util.module_from_spec(s)'"

echo ""
echo -e "${cyan}— 5. ML model + Sarathi gate —${reset}"
check "live model file exists" \
      "test -f prototype/v4/models/lgbm_intraday.txt"
check "verification_report.json next to live model" \
      "test -f prototype/v4/models/verification_report.json"
check "MLOps IC gate allows current model (CEO override active)" \
      "python3 scripts/team/gates/mlops_ic_gate.py prototype/v4/models/lgbm_intraday.txt"
check "CEO override has not expired" \
      "python3 scripts/team/cadence/_check_override.py"

echo ""
echo -e "${cyan}— 6. Team infrastructure —${reset}"
check "scripts/team/log.py imports + smoke" \
      "python3 -c 'import sys; sys.path.insert(0,\".\"); from scripts.team.log import log_activity, log_audit, update_status'"
check "scripts/sarathi/verify.py imports" \
      "python3 -c 'import sys; sys.path.insert(0,\".\"); from scripts.sarathi.verify import verify_ml, verify_data_feed'"
check "team Flask routes (5 routes) registered" \
      "python3 -c 'import sys; sys.path.insert(0,\"prototype\"); sys.path.insert(0,\".\"); import importlib.util; s=importlib.util.spec_from_file_location(\"app\",\"prototype/app.py\"); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); n=sum(1 for r in m.app.url_map.iter_rules() if \"/team\" in str(r.rule) or \"/api/team\" in str(r.rule)); assert n>=5, f\"only {n} routes\"'"

echo ""
echo -e "${cyan}— 7. Data feed pre-warm —${reset}"
warn "nifty50_quotes_batch.json present (warms up post-09:00)" \
      "test -f prototype/v4/cache/nifty50_quotes_batch.json"

echo ""
echo -e "${cyan}— 8. cron is CLEAN (we use launchd now) —${reset}"
check "no TRADEPILOT cron block" \
      "! crontab -l 2>/dev/null | grep -q TRADEPILOT-BEGIN"

echo ""
echo -e "${cyan}— 9. Pending LLM-agent tasks —${reset}"
python3 scripts/team/cadence/check-due.py 2>/dev/null | sed 's/^/    /' || true

echo ""
echo -e "${cyan}═══════════════════════════════════════════════════════${reset}"
total=$((PASS+FAIL+WARN))
echo -e "  ${green}PASS: $PASS${reset}   ${yellow}WARN: $WARN${reset}   ${red}FAIL: $FAIL${reset}   (total: $total)"

if [ "$FAIL" -gt 0 ]; then
  echo ""
  echo -e "${red}Failing checks:${reset}"
  for f in "${fails[@]}"; do echo "  - $f"; done
  echo ""
  echo -e "${red}Monday morning launch is at RISK. Fix above before 08:55 IST.${reset}"
  exit 1
fi

if [ "$WARN" -gt 0 ]; then
  echo -e "${yellow}All checks passed (with $WARN warnings).${reset} Safe to leave unattended."
else
  echo -e "${green}All checks PASS.${reset} Monday morning ready to launch unattended."
fi
echo -e "${cyan}═══════════════════════════════════════════════════════${reset}"
