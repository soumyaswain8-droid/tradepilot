#!/usr/bin/env bash
# Operational status — what's scheduled, last fire times, pending items.
set -u
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"

cyan="\033[36m"; gray="\033[37m"; reset="\033[0m"
echo -e "${cyan}=== TradePilot Quant Desk · Automation Status ===${reset}"
echo ""

echo -e "${cyan}--- pmset wake schedule ---${reset}"
pmset -g sched 2>/dev/null | head -3 || echo "(pmset unavailable)"
echo ""

echo -e "${cyan}--- launchd jobs (com.tradepilot.v2.*) ---${reset}"
LABELS=(
  com.tradepilot.v2.preflight
  com.tradepilot.v2.dqo-premarket
  com.tradepilot.v2.engines-on
  com.tradepilot.v2.dqo-mid
  com.tradepilot.v2.exec-eod
  com.tradepilot.v2.standup
  com.tradepilot.v2.due-alpha-hunter
  com.tradepilot.v2.due-competitive-intel
  com.tradepilot.v2.due-architect
  com.tradepilot.v2.bk-daily
)
for label in "${LABELS[@]}"; do
  state=$(launchctl print "gui/$UID/$label" 2>/dev/null | grep "^	state " | head -1 | awk -F'= ' '{print $2}')
  exit_line=$(launchctl print "gui/$UID/$label" 2>/dev/null | grep "last exit code" | head -1 | awk -F'= ' '{print $2}')
  short="${label#com.tradepilot.v2.}"
  printf "  %-25s state=%-15s last exit=%s\n" "$short" "${state:-(not loaded)}" "${exit_line:-(never run)}"
done
echo ""

echo -e "${cyan}--- Last fire log files (logs/auto/v2/) ---${reset}"
for log in logs/auto/v2/*.log; do
  [ -f "$log" ] || continue
  name="$(basename "$log" .log)"
  if [ -s "$log" ]; then
    last_mtime="$(stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$log" 2>/dev/null)"
    printf "  %-20s last write %s\n" "$name" "$last_mtime"
  else
    printf "  %-20s (empty)\n" "$name"
  fi
done
echo ""

echo -e "${cyan}--- Pending LLM-agent tasks (due markers) ---${reset}"
python3 scripts/team/cadence/check-due.py 2>/dev/null || echo "(check-due.py unavailable)"
echo ""

echo -e "${cyan}--- Engine processes (right now) ---${reset}"
pgrep -fl 'v[0-9].*paper-trade' | head -10 || echo "(no engines running)"
echo ""

TODAY=$(date +%Y-%m-%d)
echo -e "${cyan}--- Today's audit count ---${reset}"
if [ -f "docs/team/audit/$TODAY.jsonl" ]; then
  total=$(wc -l < "docs/team/audit/$TODAY.jsonl")
  blocks=$(grep -c '"decision":"BLOCK"' "docs/team/audit/$TODAY.jsonl" || true)
  warns=$(grep -c '"decision":"WARN"' "docs/team/audit/$TODAY.jsonl" || true)
  passes=$(grep -c '"decision":"PASS"' "docs/team/audit/$TODAY.jsonl" || true)
  echo "  $total entries · $passes PASS · $warns WARN · $blocks BLOCK"
else
  echo "  no audit log for today yet"
fi
