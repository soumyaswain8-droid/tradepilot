#!/bin/bash
# net-exposure-watcher.sh — watches for services exposed to the WiFi (0.0.0.0 binds),
# WiFi network changes, and firewall stealth-mode drops. Fires a macOS notification
# on any change. Zero tokens: pure shell, sleeps between checks.
#
# Usage:   ./net-exposure-watcher.sh [interval_seconds]
# Log:     ~/net-exposure-watch.log
# Stop:    kill $(cat ~/.net-exposure-watcher.pid)

INTERVAL="${1:-60}"
LOG="$HOME/net-exposure-watch.log"
PIDFILE="$HOME/.net-exposure-watcher.pid"
AIRPORT="/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
FW="/usr/libexec/ApplicationFirewall/socketfilterfw"

echo $$ > "$PIDFILE"

notify() { osascript -e "display notification \"$2\" with title \"$1\" sound name \"Ping\"" 2>/dev/null; }
ts()     { date "+%Y-%m-%d %H:%M:%S"; }

# Known-benign Apple services (still reported, but not treated as alerts on their own)
APPLE_RE='rapportd|ControlCe|sharingd|AirPlay'

snapshot() {
  # Network identity: gateway + SSID
  GW=$(netstat -rn 2>/dev/null | awk '/^default/ && $2 ~ /[0-9]/ {print $2; exit}')
  SSID=$($AIRPORT -I 2>/dev/null | awk -F': ' '/ SSID/{print $2; exit}')
  [ -z "$SSID" ] && SSID="(unknown)"
  STEALTH=$($FW --getstealthmode 2>/dev/null | grep -q "on" && echo on || echo off)
  # Services listening on all interfaces (*:port) — the actual exposure
  EXPOSED=$(lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk '$9 ~ /\*:/ {split($9,a,":"); print a[2]"("$1")"}' | sort -un | tr '\n' ' ')
}

log_state() {
  {
    echo "[$(ts)] net=$SSID gw=$GW stealth=$STEALTH"
    echo "           exposed: ${EXPOSED:-none}"
  } >> "$LOG"
}

echo "[$(ts)] WATCHER STARTED (interval=${INTERVAL}s, pid=$$)" >> "$LOG"
snapshot
log_state
PREV_NET="$SSID|$GW"
PREV_EXPOSED="$EXPOSED"
PREV_STEALTH="$STEALTH"

while true; do
  sleep "$INTERVAL"
  snapshot
  CUR_NET="$SSID|$GW"

  # 1. Network changed → re-check prompt
  if [ "$CUR_NET" != "$PREV_NET" ]; then
    echo "[$(ts)] ALERT network changed: $PREV_NET -> $CUR_NET" >> "$LOG"
    notify "Network changed" "Now on $SSID ($GW). ${EXPOSED:+Exposed: $EXPOSED}"
    log_state
    PREV_NET="$CUR_NET"
  fi

  # 2. New service exposed on 0.0.0.0
  if [ "$EXPOSED" != "$PREV_EXPOSED" ]; then
    NEWPORTS=""
    for p in $EXPOSED; do echo "$PREV_EXPOSED" | grep -q "$p" || NEWPORTS="$NEWPORTS $p"; done
    if [ -n "$NEWPORTS" ]; then
      echo "[$(ts)] ALERT new exposed service(s):$NEWPORTS  (net=$SSID)" >> "$LOG"
      notify "New service exposed to WiFi" "$NEWPORTS on $SSID — anyone on this network can reach it"
    else
      echo "[$(ts)] info exposure reduced -> ${EXPOSED:-none}" >> "$LOG"
    fi
    PREV_EXPOSED="$EXPOSED"
  fi

  # 3. Firewall stealth dropped
  if [ "$STEALTH" = "off" ] && [ "$PREV_STEALTH" = "on" ]; then
    echo "[$(ts)] ALERT firewall stealth mode turned OFF" >> "$LOG"
    notify "Firewall stealth OFF" "Your Mac is now answering probes on $SSID"
  fi
  PREV_STEALTH="$STEALTH"
done
