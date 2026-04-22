#!/bin/bash
# Launch / stop / check the WiFi watchdog.
# Usage:
#   ./scripts/launch-wifi-watchdog.sh              # start in background
#   ./scripts/launch-wifi-watchdog.sh --status     # is it running?
#   ./scripts/launch-wifi-watchdog.sh --stop       # stop it
#   ./scripts/launch-wifi-watchdog.sh --tail       # live tail of the log

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"
mkdir -p logs

LOG="logs/wifi-watchdog.log"
PIDFILE="logs/.wifi-watchdog.pid"
SCRIPT="$ROOT/scripts/wifi-watchdog.sh"

case "${1:-}" in
  --status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      pid=$(cat "$PIDFILE")
      echo "wifi-watchdog RUNNING (PID $pid)"
      echo "log: $LOG"
      tail -5 "$LOG" 2>/dev/null | sed 's/^/  /'
    else
      echo "wifi-watchdog NOT RUNNING"
      [ -f "$PIDFILE" ] && rm -f "$PIDFILE"
    fi
    exit 0
    ;;
  --stop)
    if [ -f "$PIDFILE" ]; then
      pid=$(cat "$PIDFILE")
      if kill "$pid" 2>/dev/null; then
        echo "stopped wifi-watchdog (PID $pid)"
      else
        echo "PID $pid already gone"
      fi
      rm -f "$PIDFILE"
    else
      pkill -f "wifi-watchdog.sh" 2>/dev/null && echo "stopped (via pkill)" || echo "nothing to stop"
    fi
    exit 0
    ;;
  --tail)
    tail -F "$LOG"
    exit 0
    ;;
esac

# Prevent double-launch
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "wifi-watchdog already running (PID $(cat $PIDFILE))"
  exit 0
fi

chmod +x "$SCRIPT"

# Use setsid if available (Linux) else nohup; on macOS nohup is the right call.
nohup "$SCRIPT" > /dev/null 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"

sleep 1
if kill -0 "$PID" 2>/dev/null; then
  echo "wifi-watchdog started (PID $PID)"
  echo "target SSID: ${WIFI_TARGET_SSID:-Pro}"
  echo "log: $LOG"
  echo ""
  tail -8 "$LOG" 2>/dev/null | sed 's/^/  /'
else
  echo "FAILED to start — see $LOG"
  rm -f "$PIDFILE"
  exit 1
fi
