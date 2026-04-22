#!/bin/bash
# Launch the profit-watchdog in the background until 15:35.
# Usage:
#   ./scripts/launch-profit-watchdog.sh           # start
#   ./scripts/launch-profit-watchdog.sh --status  # show
#   ./scripts/launch-profit-watchdog.sh --stop    # kill

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"
mkdir -p logs

TODAY=$(date +%Y-%m-%d)
LOG="logs/profit-watchdog-${TODAY}.log"

case "${1:-}" in
  --status)
    pid=$(pgrep -f "profit-watchdog.py" | head -1 || true)
    if [ -n "$pid" ]; then
      echo "profit-watchdog RUNNING (PID $pid)"
      echo "log: $LOG"
      tail -5 "$LOG" 2>/dev/null || true
    else
      echo "profit-watchdog NOT RUNNING"
    fi
    exit 0
    ;;
  --stop)
    pkill -f "profit-watchdog.py" 2>/dev/null && echo "stopped" || echo "nothing to stop"
    exit 0
    ;;
esac

# Don't double-launch
if pgrep -f "profit-watchdog.py" >/dev/null 2>&1; then
  echo "profit-watchdog already running (PID $(pgrep -f 'profit-watchdog.py' | head -1))"
  exit 0
fi

nohup python3 "$ROOT/scripts/profit-watchdog.py" > "$LOG" 2>&1 &
PID=$!
sleep 1
if kill -0 "$PID" 2>/dev/null; then
  echo "profit-watchdog started (PID $PID)"
  echo "log: $LOG"
  echo "snapshots: docs/watchdog/${TODAY}_snapshots.jsonl"
else
  echo "FAILED to start — see $LOG"
  exit 1
fi
