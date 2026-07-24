#!/bin/bash
# EOD artifact auto-commit (2026-07-24). Commits the day's generated artifacts
# (paper-trade dailies, audits, EOD summaries, dashboard scores, reports),
# pushes dev, and fast-forwards main so the default branch stays current.
# Runs from cron after EOD generation (~16:11 IST). Untracked files only —
# live mutable state (positions_active/carry_forward, tracked-modified) is
# never committed by this script.
# Manual: ./scripts/eod-git-commit.sh [--dry-run]

set -u
cd "$(dirname "$0")/.." || exit 1
TODAY=$(date +%F)
DRY=${1:-}

# -DRAFT files are pending human review — never auto-publish them
FILES=$(git ls-files --others --exclude-standard | grep "$TODAY" | grep -v "DRAFT" || true)
if [ -z "$FILES" ]; then
  echo "[$(date +%H:%M:%S)] no untracked ${TODAY} artifacts — nothing to commit"
  exit 0
fi

COUNT=$(echo "$FILES" | wc -l | tr -d ' ')
echo "[$(date +%H:%M:%S)] ${COUNT} artifact file(s) for ${TODAY}:"
echo "$FILES" | sed 's/^/  /'

if [ "$DRY" = "--dry-run" ]; then
  echo "[dry-run] would commit + push dev + fast-forward main"
  exit 0
fi

echo "$FILES" | tr '\n' '\0' | xargs -0 git add

if git diff --cached --quiet; then
  echo "nothing staged after add — exiting"
  exit 0
fi

git commit -m "chore(artifacts): ${TODAY} daily artifacts — EOD auto-commit" \
           -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" || exit 1

# push dev; retry once on transient failure (network / index race)
git push origin dev || { sleep 15; git push origin dev; } || exit 1

# fast-forward main; a diverged main is a deliberate state — log, don't force
if ! git push origin dev:main; then
  echo "WARN: main did not fast-forward (diverged?) — dev pushed, main left as-is"
fi

echo "[$(date +%H:%M:%S)] done — ${COUNT} files committed and pushed"
