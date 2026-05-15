#!/usr/bin/env bash
# Remove the TRADEPILOT cron block. Preserves all other cron entries.
set -euo pipefail
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
crontab -l 2>/dev/null | awk '
  /^# TRADEPILOT-BEGIN/ { in_block=1; next }
  /^# TRADEPILOT-END/   { in_block=0; next }
  !in_block { print }
' > "$TMP"
crontab "$TMP"
echo "TRADEPILOT cron block removed. Other entries preserved."
echo "Verify: crontab -l"
