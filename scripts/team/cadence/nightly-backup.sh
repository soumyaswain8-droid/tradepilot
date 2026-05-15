#!/usr/bin/env bash
# Nightly backup — Sprint 1 automation.
# Tars the immutable / hard-to-regenerate artefacts into ~/tradepilot-backups/
# Runs nightly at 23:00 IST (cron).
#
# Backs up:
#   - docs/team/audit/        (immutable audit log)
#   - docs/team/activity/     (event feed)
#   - docs/sarathi/ledger/    (Sarathi decisions)
#   - docs/sarathi/reports/   (per-subject verification records)
#   - prototype/v4/models/    (live model + archive + verification reports)
#   - docs/team/standup/      (daily cards)
#   - docs/exec/              (daily slippage summaries)
#
# Retention: keep last 30 daily backups + 12 weekly + 12 monthly.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
BACKUP_ROOT="${TRADEPILOT_BACKUP_DIR:-$HOME/tradepilot-backups}"
DATE="$(date +%Y-%m-%d)"
DAY_OF_WEEK="$(date +%u)"   # 1-7, Mon=1
DAY_OF_MONTH="$(date +%d)"

mkdir -p "$BACKUP_ROOT/daily" "$BACKUP_ROOT/weekly" "$BACKUP_ROOT/monthly"

cd "$PROJECT_ROOT"

# Build tarball. Use --no-mac-metadata to avoid extended-attribute noise.
TAR_NAME="tradepilot-backup-${DATE}.tar.gz"
TMP_TAR="/tmp/${TAR_NAME}"

tar -czf "$TMP_TAR" \
    --exclude='__pycache__' \
    docs/team \
    docs/sarathi \
    docs/exec \
    docs/slippage \
    prototype/v4/models 2>/dev/null

# Daily slot
mv "$TMP_TAR" "$BACKUP_ROOT/daily/$TAR_NAME"

# Weekly slot on Sunday
if [ "$DAY_OF_WEEK" = "7" ]; then
  cp "$BACKUP_ROOT/daily/$TAR_NAME" "$BACKUP_ROOT/weekly/$TAR_NAME"
fi

# Monthly slot on 1st of month
if [ "$DAY_OF_MONTH" = "01" ]; then
  cp "$BACKUP_ROOT/daily/$TAR_NAME" "$BACKUP_ROOT/monthly/$TAR_NAME"
fi

# Retention: keep last N per slot. Portable (no GNU xargs -r required).
keep_last() {
  local dir="$1" keep="$2"
  local files
  files=$(ls -1t "$dir"/*.tar.gz 2>/dev/null | tail -n +"$((keep+1))" || true)
  [ -n "$files" ] && echo "$files" | xargs rm -- || true
}
keep_last "$BACKUP_ROOT/daily" 30
keep_last "$BACKUP_ROOT/weekly" 12
keep_last "$BACKUP_ROOT/monthly" 12

# Audit log entry
python3 -c "
import sys; sys.path.insert(0, '$PROJECT_ROOT')
from scripts.team.log import log_activity
import os, json
size = os.path.getsize('$BACKUP_ROOT/daily/$TAR_NAME')
log_activity('knowledge-archivist', 'nightly-backup',
             f'Backed up to $BACKUP_ROOT/daily/$TAR_NAME ({size//1024} KB)',
             links={'path': '$BACKUP_ROOT/daily/$TAR_NAME'})
" 2>/dev/null || true

echo "Backup OK: $BACKUP_ROOT/daily/$TAR_NAME"
