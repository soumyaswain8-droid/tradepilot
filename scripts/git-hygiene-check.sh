#!/usr/bin/env bash
# Git-hygiene guard — alert when live engine CODE is uncommitted so production
# changes don't silently drift. Root-caused 2026-07-06: the _fast_flip/v5_flip
# roster ran uncommitted for 15+ days, masked by daily paper-trade JSON churn in
# `git status`. NON-BLOCKING: always exits 0 (never stops trading).
#
# Scope = code only (*.py/*.sh under scripts/ & prototype/, quant/*.txt).
# Data/state noise (docs/paper-trades/, caches, logs) is excluded by design —
# those JSONs are intentionally tracked and churn daily.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 0   # repo root; never fail the caller

# while-read (not mapfile) for macOS bash 3.2 compatibility — no homebrew bash on PATH.
DIRTY=()
while IFS= read -r f; do
  [ -n "$f" ] && DIRTY+=("$f")
done < <(
  { git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } \
    | grep -E '(^scripts/|^prototype/).*\.(py|sh)$|^quant/.*\.txt$' \
    | grep -vE '^docs/paper-trades/|/cache/|\.log$|\.aide$|^\.superpowers/' \
    | sort -u
)

if [ "${#DIRTY[@]}" -eq 0 ]; then
  exit 0   # clean — stay silent
fi

TS=$(date '+%Y-%m-%d %H:%M:%S')
mkdir -p logs
{
  echo "=================================================================="
  echo "  GIT HYGIENE WARNING @ ${TS}"
  echo "  ${#DIRTY[@]} uncommitted CODE file(s) running live — commit before drift:"
  printf '    - %s\n' "${DIRTY[@]}"
  echo "  (root cause: 2026-07-06 — do not let code drift uncommitted)"
  echo "=================================================================="
} | tee -a logs/git-hygiene.log

# Best-effort telegram alert (same pattern as scripts/crash-watchdog.sh).
if [ -f .env ]; then
  token=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2 | tr -d '"')
  chat=$(grep '^TELEGRAM_CHAT_ID=' .env | cut -d= -f2 | tr -d '"')
  if [ -n "${token:-}" ] && [ -n "${chat:-}" ]; then
    msg="⚠️ TradePilot git hygiene: ${#DIRTY[@]} uncommitted code file(s) running live — commit before drift:"$'\n'
    for f in "${DIRTY[@]}"; do msg="${msg}- ${f}"$'\n'; done
    curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
      --data-urlencode "chat_id=${chat}" \
      --data-urlencode "text=${msg}" \
      --max-time 5 > /dev/null 2>&1 || true
  fi
fi
exit 0
