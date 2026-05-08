#!/usr/bin/env bash
# Change-isolation diff — compares current state vs the last snapshot.
# Alerts if files outside the declared scope changed during the work session.
#
# Usage: ./scripts/scope-diff.sh
#
# Pairs with scope-snapshot.sh. See that script for context.

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

SNAPSHOT_DIR=".work-scope"
SNAPSHOT_FILE="$SNAPSHOT_DIR/snapshot.txt"
SCOPE_FILE="$SNAPSHOT_DIR/scope.txt"

if [ ! -f "$SNAPSHOT_FILE" ]; then
  echo "No snapshot found. Run scope-snapshot.sh <scope> before starting work."
  exit 1
fi

scope=$(head -1 "$SCOPE_FILE" 2>/dev/null || echo "unknown")
started=$(sed -n '2p' "$SCOPE_FILE" 2>/dev/null || echo "unknown")

changed=0
unchanged=0
new_files=0
declare -a violations

while read line; do
  hash=$(echo "$line" | awk '{print $1}')
  mtime=$(echo "$line" | awk '{print $2}')
  file=$(echo "$line" | awk '{$1=""; $2=""; sub(/^  /, ""); print}')

  if [ ! -f "$file" ]; then
    violations+=("DELETED: $file")
    changed=$((changed+1))
    continue
  fi

  current_hash=$(shasum -a 256 "$file" 2>/dev/null | awk '{print $1}')
  if [ "$current_hash" != "$hash" ]; then
    violations+=("MODIFIED: $file")
    changed=$((changed+1))
  else
    unchanged=$((unchanged+1))
  fi
done < "$SNAPSHOT_FILE"

echo ""
echo "=================================================================="
echo "  CHANGE-ISOLATION DIFF — scope: $scope"
echo "  $started"
echo "=================================================================="
echo "  Files unchanged: $unchanged"
echo "  Files changed:   $changed"
echo ""

if [ "$changed" -eq 0 ]; then
  echo "  ✅ NO VIOLATIONS — your work stayed within scope."
  echo "=================================================================="
  rm "$SNAPSHOT_FILE" "$SCOPE_FILE"
  exit 0
fi

echo "  🔴 SCOPE VIOLATIONS DETECTED — files OUTSIDE your declared $scope scope changed:"
echo ""
for v in "${violations[@]}"; do
  echo "    - $v"
done
echo ""
echo "  This is the same class of bug as 2026-05-08's cache poisoning"
echo "  (UI work overnight silently triggered engine cache write)."
echo ""
echo "  Review what happened, then either:"
echo "    1. git checkout the unintended files (if accidental)"
echo "    2. git commit them separately with a clear scope-violation note"
echo "    3. Rerun scope-snapshot.sh with the correct scope if intentional"
echo "=================================================================="
exit 1
