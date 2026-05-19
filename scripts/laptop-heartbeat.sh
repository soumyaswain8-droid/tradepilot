#!/bin/bash
# Laptop-alive heartbeat — sends Telegram ping during market hours.
# If pings stop, user knows laptop slept / network died / something broke.
#
# 2026-05-19 fixes (in-place per CEO option A):
#  - PATH: explicitly include /sbin + /usr/sbin so `route` is found under launchd
#    (launchd's default PATH excludes /sbin; was causing "net ✗ (offline)" false positives)
#  - Engine list: 3 active engines (v4/v5/v5_classic), not the stale 7-engine list
#  - Interval: 60 min instead of 15 min (less Telegram noise; dashboard is the live truth)

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"

# Ensure /sbin and /usr/sbin are in PATH for route/ifconfig under launchd.
export PATH="/sbin:/usr/sbin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

MARKET_OPEN_MIN=$((9 * 60))
MARKET_CLOSE_MIN=$((15 * 60 + 35))
INTERVAL_SEC=3600  # 60 min (was 15 min — too noisy)

now_min() {
  echo $((10#$(date +%H) * 60 + 10#$(date +%M)))
}

in_market_hours() {
  local nm
  nm=$(now_min)
  [ "$nm" -ge "$MARKET_OPEN_MIN" ] && [ "$nm" -le "$MARKET_CLOSE_MIN" ]
}

get_network_info() {
  local iface
  local ip
  iface=$(route get default 2>/dev/null | grep 'interface:' | awk '{print $2}')
  ip=$(ifconfig "$iface" 2>/dev/null | grep "inet " | awk '{print $2}' | head -1)
  if [ -z "$iface" ] || [ -z "$ip" ]; then
    echo "offline"
  else
    echo "${iface}:${ip}"
  fi
}

check_internet() {
  # Quick 2-second ping to Google DNS
  ping -c 1 -W 2000 8.8.8.8 > /dev/null 2>&1
}

send_telegram() {
  local msg="$1"
  if [ -f .env ]; then
    local token
    local chat
    token=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2 | tr -d '"')
    chat=$(grep '^TELEGRAM_CHAT_ID=' .env | cut -d= -f2 | tr -d '"')
    if [ -n "$token" ] && [ -n "$chat" ]; then
      curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${msg}" \
        --max-time 10 > /dev/null 2>&1
    fi
  fi
}

PREV_NET=""
OFFLINE_COUNT=0

echo "[$(date '+%H:%M:%S')] laptop-heartbeat started — pings every 15 min during market hours"
send_telegram "💻 Laptop heartbeat online. Pings every 15 min. Silence = laptop died or network dropped."

while true; do
  if ! in_market_hours; then
    sleep 300
    continue
  fi

  net=$(get_network_info)
  online="?"
  if check_internet; then
    online="✓"
    OFFLINE_COUNT=0
  else
    online="✗"
    OFFLINE_COUNT=$((OFFLINE_COUNT + 1))
  fi

  # Alert on network change
  if [ -n "$PREV_NET" ] && [ "$net" != "$PREV_NET" ]; then
    send_telegram "📶 Network changed: ${PREV_NET} → ${net} (at $(date +%H:%M))"
  fi
  PREV_NET="$net"

  # Alert on sustained offline (only if we can queue it — next successful send will deliver)
  if [ "$online" = "✗" ] && [ "$OFFLINE_COUNT" -ge 2 ]; then
    echo "[$(date '+%H:%M:%S')] WARN: offline for ${OFFLINE_COUNT} cycles (${net})"
    # Try sending anyway — queued or buffered connections may still work
  fi

  # Count alive engines via heartbeat files (3 active post Sprint-1 consolidation)
  TODAY=$(date +%Y-%m-%d)
  alive=0
  total=0
  for e in v4 v5 v5_classic; do
    total=$((total + 1))
    hb="docs/paper-trades/${e}/${TODAY}.json"
    if [ -f "$hb" ]; then
      mtime=$(stat -f "%m" "$hb" 2>/dev/null || echo 0)
      now_ts=$(date +%s)
      age=$((now_ts - mtime))
      # 60-min freshness window (matches new INTERVAL_SEC)
      if [ "$age" -lt 3600 ]; then
        alive=$((alive + 1))
      fi
    fi
  done

  msg="💻 $(date +%H:%M) · net ${online} (${net}) · engines ${alive}/${total} alive"
  send_telegram "$msg"
  echo "[$(date '+%H:%M:%S')] ping sent: $msg"

  sleep $INTERVAL_SEC
done
