#!/usr/bin/env bash
# Remove all TradePilot launchd jobs (v2 namespace) — and any leftover
# TRADEPILOT cron block from the pre-migration cron-based version.

set -u
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

echo "Bootouting launchd jobs..."
for label in "${LABELS[@]}"; do
  if launchctl bootout "gui/$UID/$label" 2>/dev/null; then
    echo "  ✓ $label"
  else
    echo "  - $label (not loaded)"
  fi
  rm -f "$HOME/Library/LaunchAgents/$label.plist"
done

# Best-effort: also strip any old cron block (from pre-2026-05-16 setup)
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
if crontab -l 2>/dev/null | grep -q "TRADEPILOT-BEGIN"; then
  echo "Also removing legacy TRADEPILOT cron block..."
  crontab -l 2>/dev/null | awk '
    /^# TRADEPILOT-BEGIN/ { in_block=1; next }
    /^# TRADEPILOT-END/   { in_block=0; next }
    !in_block { print }
  ' > "$TMP"
  crontab "$TMP"
fi

echo ""
echo "TradePilot automation removed. Other launchd / cron entries preserved."
echo "Verify: launchctl list | grep com.tradepilot.v2  (should be empty)"
