#!/bin/bash
# WiFi Watchdog — keeps the laptop on a target hotspot for travel / bike rides.
#
# Every CHECK_INTERVAL seconds:
#   1. Ping a reliable host (1.1.1.1). If reachable -> do nothing.
#   2. If not reachable:
#      - Grab current SSID.
#      - If WiFi is OFF, turn it ON.
#      - If not connected to the target SSID, switch to it.
#      - If already on target but still offline, cycle WiFi (off -> on).
#      - Re-ping after the action to confirm recovery.
#   3. Any recovery action pings Telegram so the rider knows.
#
# Designed for macOS.  Uses only built-in tools (networksetup, ipconfig, ping).
#
# Config via env vars (defaults shown):
#   WIFI_TARGET_SSID="Pro"
#   WIFI_INTERFACE="en0"
#   WIFI_CHECK_INTERVAL=30
#   WIFI_OFFLINE_THRESHOLD=2          (consecutive failed pings before acting)
#   WIFI_POST_ACTION_WAIT=8           (seconds to wait after a switch/cycle)
#
# Logs:
#   logs/wifi-watchdog.log            (rolling, appended forever)
#
# Start:   ./scripts/launch-wifi-watchdog.sh
# Stop:    ./scripts/launch-wifi-watchdog.sh --stop
# Status:  ./scripts/launch-wifi-watchdog.sh --status

set -u

ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"
mkdir -p logs

TARGET_SSID="${WIFI_TARGET_SSID:-Pro}"
IFACE="${WIFI_INTERFACE:-en0}"
CHECK_INTERVAL="${WIFI_CHECK_INTERVAL:-30}"
OFFLINE_THRESHOLD="${WIFI_OFFLINE_THRESHOLD:-2}"
POST_ACTION_WAIT="${WIFI_POST_ACTION_WAIT:-8}"
LOG="logs/wifi-watchdog.log"
PING_HOSTS=(1.1.1.1 8.8.8.8)    # try both, one may be blocked

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG"
}

telegram() {
  local msg="$1"
  if [ -f .env ]; then
    local token chat
    token=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2 | tr -d '"')
    chat=$(grep '^TELEGRAM_CHAT_ID=' .env | cut -d= -f2 | tr -d '"')
    if [ -n "$token" ] && [ -n "$chat" ]; then
      curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${msg}" --max-time 5 > /dev/null 2>&1 || true
    fi
  fi
}

current_ssid() {
  # Most reliable on modern macOS.  Returns empty string if not associated.
  ipconfig getsummary "$IFACE" 2>/dev/null \
    | awk -F': ' '/  SSID :/{gsub(/^[ \t]+|[ \t]+$/,"",$2); print $2; exit}'
}

wifi_power_state() {
  # Returns "On" or "Off"
  networksetup -getairportpower "$IFACE" 2>/dev/null | awk '{print $NF}'
}

is_online() {
  local host
  for host in "${PING_HOSTS[@]}"; do
    if ping -c 1 -W 2000 -t 3 "$host" > /dev/null 2>&1; then
      return 0
    fi
  done
  return 1
}

wifi_on() {
  log "wifi power -> ON"
  networksetup -setairportpower "$IFACE" on 2>&1 | tee -a "$LOG" >/dev/null
}

wifi_cycle() {
  log "cycling wifi off -> on to force reconnect"
  networksetup -setairportpower "$IFACE" off 2>&1 | tee -a "$LOG" >/dev/null
  sleep 3
  networksetup -setairportpower "$IFACE" on  2>&1 | tee -a "$LOG" >/dev/null
}

connect_to_target() {
  log "connecting to '$TARGET_SSID' (password from keychain)..."
  # No password arg -> macOS uses the one saved in keychain.
  networksetup -setairportnetwork "$IFACE" "$TARGET_SSID" 2>&1 | tee -a "$LOG"
}

# ═════════════════════════ main loop ═════════════════════════

log "=========================================="
log "wifi-watchdog starting"
log "target SSID     : $TARGET_SSID"
log "interface       : $IFACE"
log "check interval  : ${CHECK_INTERVAL}s"
log "offline thresh  : ${OFFLINE_THRESHOLD} consecutive misses"
log "=========================================="

consecutive_miss=0
last_ssid=""
last_state="unknown"

while :; do
  if is_online; then
    ssid="$(current_ssid)"
    # Only log when state changes, to keep log manageable
    if [ "$last_state" != "online" ] || [ "$ssid" != "$last_ssid" ]; then
      log "ONLINE  ssid='${ssid:-(none)}'"
      last_state="online"
      last_ssid="$ssid"
    fi
    consecutive_miss=0
    sleep "$CHECK_INTERVAL"
    continue
  fi

  # ── Offline branch ────────────────────────────────────────
  consecutive_miss=$((consecutive_miss + 1))
  ssid="$(current_ssid)"
  power="$(wifi_power_state)"
  log "OFFLINE miss=${consecutive_miss}/${OFFLINE_THRESHOLD} wifi=${power} ssid='${ssid:-(none)}'"

  if [ "$consecutive_miss" -lt "$OFFLINE_THRESHOLD" ]; then
    sleep "$CHECK_INTERVAL"
    continue
  fi

  # Threshold exceeded -> act.
  if [ "$power" = "Off" ]; then
    wifi_on
    sleep "$POST_ACTION_WAIT"
  elif [ "$ssid" != "$TARGET_SSID" ]; then
    prev="${ssid:-(none)}"
    connect_to_target
    sleep "$POST_ACTION_WAIT"
    new_ssid="$(current_ssid)"
    if [ "$new_ssid" = "$TARGET_SSID" ]; then
      telegram "[wifi-watchdog] Switched from '$prev' to '$TARGET_SSID' (hotspot)."
    fi
  else
    wifi_cycle
    sleep "$POST_ACTION_WAIT"
    if is_online; then
      telegram "[wifi-watchdog] Recovered '$TARGET_SSID' after cycle."
    fi
  fi

  # Re-check quickly to see if the action worked
  if is_online; then
    log "RECOVERED after action"
    consecutive_miss=0
    last_state="online"
    last_ssid="$(current_ssid)"
  else
    log "still OFFLINE after action — will retry next tick"
  fi

  sleep "$CHECK_INTERVAL"
done
