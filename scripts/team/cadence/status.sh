#!/usr/bin/env bash
# Operational status — what's scheduled and when did each cron job last fire.
# Reads the cron schedule and the auto-log files.

set -u
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"

cyan="\033[36m"; gray="\033[37m"; reset="\033[0m"
echo -e "${cyan}=== TradePilot Quant Desk · Automation Status ===${reset}"
echo ""

echo -e "${cyan}--- Cron schedule (TRADEPILOT block) ---${reset}"
crontab -l 2>/dev/null | sed -n '/# TRADEPILOT-BEGIN/,/# TRADEPILOT-END/p' || echo "(no TRADEPILOT block installed yet)"
echo ""

echo -e "${cyan}--- Last firing time per job ---${reset}"
for log in logs/auto/*.log; do
  [ -f "$log" ] || continue
  name="$(basename "$log" .log)"
  if [ -s "$log" ]; then
    last_mtime="$(stat -f '%Sm' -t '%Y-%m-%d %H:%M' "$log" 2>/dev/null)"
    last_line="$(tail -1 "$log" | cut -c1-100)"
    printf "  %-20s last fire %s\n" "$name" "$last_mtime"
    printf "      ${gray}%s${reset}\n" "$last_line"
  else
    printf "  %-20s (never fired)\n" "$name"
  fi
done
echo ""

echo -e "${cyan}--- Pending LLM-agent tasks (due markers) ---${reset}"
python3 scripts/team/cadence/check-due.py 2>/dev/null || echo "(check-due.py not available)"
echo ""

echo -e "${cyan}--- Engine processes (right now) ---${reset}"
pgrep -fl 'v[0-9].*paper-trade' | head -10 || echo "(no engines running)"
echo ""

echo -e "${cyan}--- Today's audit count ---${reset}"
TODAY=$(date +%Y-%m-%d)
if [ -f "docs/team/audit/$TODAY.jsonl" ]; then
  total=$(wc -l < "docs/team/audit/$TODAY.jsonl")
  blocks=$(grep -c '"decision":"BLOCK"' "docs/team/audit/$TODAY.jsonl" || true)
  warns=$(grep -c '"decision":"WARN"' "docs/team/audit/$TODAY.jsonl" || true)
  passes=$(grep -c '"decision":"PASS"' "docs/team/audit/$TODAY.jsonl" || true)
  echo "  $total entries · $passes PASS · $warns WARN · $blocks BLOCK"
else
  echo "  no audit log for today yet"
fi
