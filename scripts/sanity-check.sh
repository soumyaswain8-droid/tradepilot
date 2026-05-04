#!/bin/bash
# Sanity check: capture checksums of protected files BEFORE and AFTER
# tonight's prep work. If any protected file changed, raise the alarm.
#
# Usage:
#   ./scripts/sanity-check.sh before    # snapshot before prep work
#   ./scripts/sanity-check.sh after     # snapshot after + diff

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"

MODE="${1:-after}"
BEFORE_FILE="/tmp/tradepilot-protected-before.txt"
AFTER_FILE="/tmp/tradepilot-protected-after.txt"

# List of protected paths (files or directories)
PROTECTED_PATHS=(
  "prototype/v4/models/lgbm_intraday.txt"
  "prototype/v4/models/lgbm_meta.json"
  "engine/target/release/tradepilot-engine"
  ".env"
  "scripts/v5-paper-trade.py"
  "scripts/crash-watchdog.sh"
  "scripts/launch-market.sh"
  "scripts/telegram-digest.sh"
  "scripts/auto-stop-eod.sh"
  "scripts/laptop-heartbeat.sh"
  "engine/src/risk/mod.rs"
  "engine/src/main.rs"
  "prototype/v5/rust_bridge.py"
)

# Also protect: any existing CSV file in prototype/data/
# (new CSVs are allowed, but existing ones must stay byte-identical)

compute_snapshot() {
  local out="$1"
  : > "$out"
  for p in "${PROTECTED_PATHS[@]}"; do
    if [ -f "$p" ]; then
      echo "$(md5 -q "$p" 2>/dev/null)  $p" >> "$out"
    fi
  done
  # Also all existing CSVs under prototype/data/
  find prototype/data -type f -name "*.csv" 2>/dev/null | sort | while read -r csv; do
    echo "$(md5 -q "$csv" 2>/dev/null)  $csv" >> "$out"
  done
}

if [ "$MODE" = "before" ]; then
  compute_snapshot "$BEFORE_FILE"
  count=$(wc -l < "$BEFORE_FILE" | tr -d ' ')
  echo "[$(date +%H:%M:%S)] BEFORE snapshot: ${count} protected files logged -> $BEFORE_FILE"

elif [ "$MODE" = "after" ]; then
  if [ ! -f "$BEFORE_FILE" ]; then
    echo "ERROR: no BEFORE snapshot at $BEFORE_FILE — run 'sanity-check.sh before' first"
    exit 2
  fi
  compute_snapshot "$AFTER_FILE"
  count_before=$(wc -l < "$BEFORE_FILE" | tr -d ' ')
  count_after=$(wc -l < "$AFTER_FILE" | tr -d ' ')

  # Compare: any CHANGED file will show up in diff
  if diff -q "$BEFORE_FILE" "$AFTER_FILE" > /dev/null; then
    echo "[$(date +%H:%M:%S)] SAFE ✓ All ${count_before} protected files unchanged."
    exit 0
  fi

  echo "[$(date +%H:%M:%S)] ⚠ DRIFT DETECTED"
  echo "  Before: ${count_before} files, After: ${count_after} files"
  echo ""
  echo "Changed files (differences in checksum):"
  diff "$BEFORE_FILE" "$AFTER_FILE" | grep -E "^[<>]" | awk '{print "  ",$0}'
  exit 1

else
  echo "Usage: $0 before|after"
  exit 2
fi
