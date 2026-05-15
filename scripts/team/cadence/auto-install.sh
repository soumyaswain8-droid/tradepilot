#!/usr/bin/env bash
# Idempotent cron installer for TradePilot Quant Desk automation.
# Re-running replaces the TRADEPILOT-BEGIN/END block — preserves all other cron lines.
#
# Schedule (IST = local timezone on this Mac):
#
#   Weekday (Mon-Fri):
#     08:55  Sarathi DAT pre-market check    (gate)
#     09:10  Launch engines (if gate PASS)   (DQO blocks otherwise)
#     11:00  Sarathi DAT mid-market check
#     15:31  Execution Analyst slippage aggregate (engines auto-stop at 15:35 by launch-market.sh)
#     15:50  Knowledge Archivist standup card
#     16:00  Knowledge Archivist EOD sweep (mark Alpha Hunter due if Friday)
#
#   Sunday:
#     19:00  Mark Competitive Intel due (weekly research scan)
#     19:05  Mark Architect due (sprint planning prep)
#
#   Daily (every day, 23:00):
#     23:00  Nightly backup
#
# Uninstall: bash scripts/team/cadence/auto-uninstall.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
mkdir -p "$PROJECT_ROOT/logs/auto" "$PROJECT_ROOT/docs/team/due"

# Build the cron block. ${PROJECT_ROOT} expanded NOW into the heredoc.
BLOCK=$(cat <<EOF
# TRADEPILOT-BEGIN (managed by scripts/team/cadence/auto-install.sh — do not edit by hand)
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin:/Users/soumyaswain/anaconda3/bin

# Weekday — market schedule
55  8 * * 1-5  cd ${PROJECT_ROOT} && python3 scripts/sarathi/verify.py --family DAT --check pre-market >> logs/auto/dqo-premarket.log 2>&1
10  9 * * 1-5  cd ${PROJECT_ROOT} && python3 scripts/sarathi/verify.py --family DAT --check launch-gate >> logs/auto/launch.log 2>&1 && bash scripts/launch-market.sh >> logs/auto/launch.log 2>&1
0  11 * * 1-5  cd ${PROJECT_ROOT} && python3 scripts/sarathi/verify.py --family DAT --check mid-market >> logs/auto/dqo-mid.log 2>&1
31 15 * * 1-5  cd ${PROJECT_ROOT} && python3 scripts/team/slippage.py --aggregate >> logs/auto/exec-eod.log 2>&1
50 15 * * 1-5  cd ${PROJECT_ROOT} && bash .claude/team/cadence/daily-standup.sh >> logs/auto/standup.log 2>&1
0  16 * * 5    cd ${PROJECT_ROOT} && python3 scripts/team/cadence/check-due.py --mark alpha-hunter "Weekly IC + feature drift audit" >> logs/auto/due.log 2>&1

# Sunday — weekly cadence
0  19 * * 0    cd ${PROJECT_ROOT} && python3 scripts/team/cadence/check-due.py --mark competitive-intel "Weekly Qlib/FinRL/arxiv scan" >> logs/auto/due.log 2>&1
5  19 * * 0    cd ${PROJECT_ROOT} && python3 scripts/team/cadence/check-due.py --mark architect "Sprint review + next week planning" >> logs/auto/due.log 2>&1

# Daily — nightly backup
0  23 * * *    cd ${PROJECT_ROOT} && bash scripts/team/cadence/nightly-backup.sh >> logs/auto/backup.log 2>&1
# TRADEPILOT-END
EOF
)

# Capture existing crontab (or empty if none)
TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON" "$TMP_CRON.new"' EXIT
crontab -l 2>/dev/null > "$TMP_CRON" || true

# Strip any existing TRADEPILOT block from prior runs
awk '
  /^# TRADEPILOT-BEGIN/ { in_block=1; next }
  /^# TRADEPILOT-END/   { in_block=0; next }
  !in_block { print }
' "$TMP_CRON" > "$TMP_CRON.new"

# Append fresh block
{
  cat "$TMP_CRON.new"
  echo ""
  printf '%s\n' "$BLOCK"
} | crontab -

echo "Installed TRADEPILOT cron block. Verify with:"
echo "  crontab -l | sed -n '/# TRADEPILOT-BEGIN/,/# TRADEPILOT-END/p'"
echo ""
echo "Operational status anytime:"
echo "  bash scripts/team/cadence/status.sh"
