#!/bin/bash
# post-open-check.sh — runs ~10 min after the 09:15 open. Confirms every active
# engine is alive (heartbeat = today's state file written in the last 20 min) and
# Telegrams a "N/N engines trading" confirmation. If any are down, it relaunches
# the stack (idempotent) and pages — so a failed morning launch can never pass
# silently again. Belt-and-suspenders on top of the AbandonProcessGroup fix.
set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"
TODAY=$(date +%Y-%m-%d)
HEARTBEAT_MAX_AGE=1200   # 20 min — engine is "alive" if its state file is fresher

# Active roster = uncommented "name|script" lines in launch-market.sh (single source).
# while-read (not mapfile) for macOS bash 3.2 compatibility.
ENGINES=()
while IFS= read -r e; do [ -n "$e" ] && ENGINES+=("$e"); done < <(
  sed -n '/^ENGINES=(/,/^)/p' scripts/launch-market.sh \
  | grep -vE '^\s*#' | grep -oE '"[a-z0-9_]+\|' | tr -d '"|')

now=$(date +%s); alive=0; dead=()
for e in "${ENGINES[@]}"; do
  f="docs/paper-trades/$e/${TODAY}.json"
  if [ -f "$f" ]; then
    age=$(( now - $(stat -f %m "$f") ))
    if [ "$age" -lt "$HEARTBEAT_MAX_AGE" ]; then alive=$((alive+1)); else dead+=("$e"); fi
  else
    dead+=("$e")
  fi
done
total=${#ENGINES[@]}

send_telegram() {
  local msg="$1"
  [ -f .env ] || return
  local token chat
  token=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2 | tr -d '"')
  chat=$(grep '^TELEGRAM_CHAT_ID=' .env | cut -d= -f2 | tr -d '"')
  [ -n "$token" ] && [ -n "$chat" ] && curl -s -X POST \
    "https://api.telegram.org/bot${token}/sendMessage" \
    --data-urlencode "chat_id=${chat}" --data-urlencode "text=${msg}" --max-time 8 >/dev/null 2>&1
}

if [ "$alive" -eq "$total" ] && [ "$total" -gt 0 ]; then
  send_telegram "✅ TradePilot: ${alive}/${total} engines trading at open ($(date +%H:%M)). All systems go."
  echo "[$(date +%H:%M)] OK ${alive}/${total} engines alive"
else
  echo "[$(date +%H:%M)] DOWN: ${dead[*]:-none} (${alive}/${total} alive) — relaunching"
  send_telegram "⚠️ TradePilot: only ${alive}/${total} engines up (down: ${dead[*]:-?}). Relaunching now."
  ./scripts/launch-market.sh > "logs/post-open-relaunch-${TODAY}.log" 2>&1
  send_telegram "🔄 TradePilot: relaunch fired at $(date +%H:%M). Check dashboard."
fi
