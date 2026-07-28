#!/bin/bash
# post-open-check.sh — runs ~10 min after the 09:15 open. Confirms every active
# engine is alive (heartbeat = today's state file written in the last 20 min) and
# Telegrams a "N/N engines trading" confirmation. If any are down, it relaunches
# the stack and pages — so a failed morning launch can never pass silently again.
# Belt-and-suspenders on top of the AbandonProcessGroup fix.
#
# ─── TWO KNOWN DEFECTS, both hit live on 2026-07-28 ──────────────────────────
#
# 1. REQUIRES an anaconda-first PATH on its launchd plist. This script calls
#    launch-market.sh, which spawns engines with a bare `python3` (line ~380) and
#    sets no PATH of its own — so the interpreter is inherited from whoever
#    invoked it. The plist originally had NO EnvironmentVariables, so it got
#    launchd's bare /usr/bin:/bin and `python3` resolved to /usr/bin/python3,
#    which has NO numpy. On 2026-07-28 that relaunched 9 engines in a degraded
#    state ("[WARN] regime/premarket/signals: No module named 'numpy'").
#    The 08:50 com.soumya.tradepilot-launch job avoids this only because it uses
#    `bash -l`. Fixed by adding EnvironmentVariables/PATH to the plist — a copy
#    lives at scripts/launchagents/com.tradepilot.post-open-check.plist.
#    Verify with: env -i PATH=<plist PATH> HOME=$HOME /bin/bash -c 'which python3'
#    (measuring from an interactive shell gives the WRONG answer — your own PATH
#    leaks in.)
#
# 2. The relaunch is NOT idempotent, despite what this header used to claim.
#    It runs the FULL launch-market.sh when even ONE engine is down, and
#    launch-market.sh has no per-engine already-running guard — so on 2026-07-28
#    a single dead v5_cut caused a SECOND complete fleet of 9 to spawn alongside
#    the 8 healthy originals. Two fleets then shared the same
#    positions_active.json / carry_forward state for ~45 minutes. The `>` redirect
#    on line ~49 also TRUNCATES the originals' per-day logs, destroying evidence.
#    TODO: restart only what is dead, guard against already-running instances,
#    and append (>>) rather than truncate.
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
