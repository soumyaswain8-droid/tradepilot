#!/usr/bin/env bash
# Change-isolation snapshot — captures state of critical files before a work session.
# Run BEFORE starting any work. Run scope-diff.sh AFTER to verify nothing outside
# the declared scope changed.
#
# Usage:
#   ./scripts/scope-snapshot.sh ui          # working on dashboard/landing
#   ./scripts/scope-snapshot.sh engine      # working on engine code
#   ./scripts/scope-snapshot.sh docs        # working on docs/research
#   ./scripts/scope-snapshot.sh deploy      # working on launch scripts / Docker / cloud
#
# Background:
# Created 2026-05-08 after a session of UI work at 03:00 IST silently triggered
# the engine's data-fetch path during pre-market hours, poisoning the cache
# and crippling v4 the next day (-Rs 6,884). The principle: when working on
# system A, the system should refuse to let unrelated system B mutate.

set -e
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

SCOPE="${1:-general}"
SNAPSHOT_DIR=".work-scope"
SNAPSHOT_FILE="$SNAPSHOT_DIR/snapshot.txt"
SCOPE_FILE="$SNAPSHOT_DIR/scope.txt"

mkdir -p "$SNAPSHOT_DIR"

# Record declared scope
echo "$SCOPE" > "$SCOPE_FILE"
echo "Started: $(date '+%Y-%m-%d %H:%M:%S %Z')" >> "$SCOPE_FILE"

# What gets snapshotted depends on scope. Each scope tracks
# the files OUTSIDE its boundary that should NOT change.
#
# UI scope: should not touch engine code, ML models, state files, or scripts
# Engine scope: should not touch UI templates, landing pages
# Docs scope: should not touch any code or state
# Deploy scope: can touch launch scripts but not engine internals or models

# macOS bash 3.2 doesn't support associative arrays — use case statement instead
case "$SCOPE" in
  ui)
    paths="prototype/v4 prototype/v5 prototype/v5_6 prototype/v5_7 prototype/data scripts engine/src" ;;
  engine)
    paths="prototype/templates prototype/static docs/branding" ;;
  docs)
    paths="prototype/v4 prototype/v5 prototype/v5_6 prototype/v5_7 scripts engine/src prototype/data prototype/templates" ;;
  deploy)
    paths="prototype/v4 prototype/v5" ;;
  general)
    paths="prototype/v4 prototype/v5 prototype/v5_6 prototype/v5_7 prototype/data scripts prototype/templates" ;;
  *)
    echo "Unknown scope: $SCOPE"
    echo "Valid scopes: ui, engine, docs, deploy, general"
    exit 1 ;;
esac

# Snapshot: hash + mtime of every tracked file
> "$SNAPSHOT_FILE"
for path in $paths; do
  if [ -e "$path" ]; then
    find "$path" -type f \( \
      -name "*.py" -o -name "*.html" -o -name "*.json" -o -name "*.yaml" -o \
      -name "*.yml" -o -name "*.sh" -o -name "*.txt" -o -name "*.toml" -o \
      -name "*.rs" -o -name "*.css" -o -name "*.js" \
    \) ! -path "*/__pycache__/*" ! -path "*/target/*" ! -path "*/cache/*" \
       ! -name "*.pyc" \
       2>/dev/null \
    | while read f; do
      # Format: hash | mtime | path
      hash=$(shasum -a 256 "$f" 2>/dev/null | awk '{print $1}')
      mtime=$(stat -f "%m" "$f" 2>/dev/null)
      echo "$hash $mtime $f" >> "$SNAPSHOT_FILE"
    done
  fi
done

count=$(wc -l < "$SNAPSHOT_FILE" | tr -d ' ')
echo ""
echo "=================================================================="
echo "  CHANGE-ISOLATION SNAPSHOT — scope: $SCOPE"
echo "=================================================================="
echo "  Files tracked: $count"
echo "  Watch paths:   $paths"
echo "  Snapshot at:   $SNAPSHOT_FILE"
echo ""
echo "  When you finish your work session, run:"
echo "    ./scripts/scope-diff.sh"
echo ""
echo "  This will alert if any file outside your declared scope changed."
echo "=================================================================="
