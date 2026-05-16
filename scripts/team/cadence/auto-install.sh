#!/usr/bin/env bash
# Idempotent installer for TradePilot Quant Desk automation (launchd).
#
# Generates 9 plists from scripts/team/cadence/_plist_gen.py,
# bootouts any existing v2 jobs, bootstraps fresh.
#
# Schedule (IST):
#   Weekday 08:55  Sarathi DAT pre-market
#   Weekday 09:10  launch-market (DAT-gated via launch-with-gate.sh)
#   Weekday 11:00  Sarathi DAT mid-market
#   Weekday 15:31  Execution Analyst slippage aggregate
#   Weekday 15:50  Knowledge Archivist standup
#   Friday  16:00  Mark Alpha Hunter due
#   Sunday  19:00  Mark Competitive Intel due
#   Sunday  19:05  Mark Architect due
#   Daily   23:00  Nightly backup
#
# Migrated from cron 2026-05-16 — cron was hitting macOS TCC EX_CONFIG
# errors when launchd-spawned bash tried to write to "tainted" log paths.
# launchd is the macOS-native scheduler and inherits user permissions.
#
# Uninstall: bash scripts/team/cadence/auto-uninstall.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"
mkdir -p logs/auto/v2 docs/team/due

LABELS=(
  com.tradepilot.v2.dqo-premarket
  com.tradepilot.v2.launch-market
  com.tradepilot.v2.dqo-mid
  com.tradepilot.v2.exec-eod
  com.tradepilot.v2.standup
  com.tradepilot.v2.due-alpha-hunter
  com.tradepilot.v2.due-competitive-intel
  com.tradepilot.v2.due-architect
  com.tradepilot.v2.bk-daily
)

echo "Generating plists..."
python3 scripts/team/cadence/_plist_gen.py >/dev/null

echo "Bootouting any existing v2 jobs..."
for label in "${LABELS[@]}"; do
  launchctl bootout "gui/$UID/$label" 2>/dev/null || true
done

echo "Bootstrapping fresh..."
fail=0
for label in "${LABELS[@]}"; do
  plist="$HOME/Library/LaunchAgents/$label.plist"
  if launchctl bootstrap "gui/$UID" "$plist" 2>&1; then
    echo "  ✓ $label"
  else
    echo "  ✗ $label — bootstrap failed"
    fail=1
  fi
done

if [ "$fail" = "1" ]; then
  echo ""
  echo "Some jobs failed to bootstrap. Check ~/Library/LaunchAgents/com.tradepilot.v2.*.plist"
  exit 1
fi

echo ""
echo "Installed 9 launchd jobs. Verify:"
echo "  launchctl list | grep com.tradepilot.v2"
echo ""
echo "Operational status anytime:"
echo "  bash scripts/team/cadence/status.sh"
