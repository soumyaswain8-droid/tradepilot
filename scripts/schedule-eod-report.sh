#!/bin/bash
# Schedule the EOD comparison report to fire at 15:40 today.
# Sleeps in 60-second chunks so it doesn't block anything heavy, waking
# every minute to check the clock.
#
# Usage:
#   ./scripts/schedule-eod-report.sh                    # schedule for today 15:40
#   ./scripts/schedule-eod-report.sh --at HH:MM         # custom time
#   ./scripts/schedule-eod-report.sh --status           # is it scheduled?
#   ./scripts/schedule-eod-report.sh --cancel           # kill the scheduler
#
# Telemetry:
#   logs/schedule-eod-YYYY-MM-DD.log  -- scheduler log
#   lock file: logs/.schedule-eod.pid

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"
mkdir -p logs

TODAY=$(date +%Y-%m-%d)
LOG="logs/schedule-eod-${TODAY}.log"
PIDFILE="logs/.schedule-eod.pid"
FIRE_AT="15:40"

# ── parse args ────────────────────────────────────────────────────────
case "${1:-}" in
  --status)
    if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
      echo "scheduler RUNNING (PID $(cat $PIDFILE))"
      echo "log: $LOG"
      tail -5 "$LOG" 2>/dev/null || true
    else
      echo "scheduler NOT RUNNING"
      [ -f "$PIDFILE" ] && rm -f "$PIDFILE"
    fi
    exit 0
    ;;
  --cancel)
    if [ -f "$PIDFILE" ]; then
      pid=$(cat "$PIDFILE")
      if kill "$pid" 2>/dev/null; then
        echo "cancelled (PID $pid)"
      else
        echo "PID $pid already gone"
      fi
      rm -f "$PIDFILE"
    else
      echo "no scheduler running"
    fi
    exit 0
    ;;
  --at)
    FIRE_AT="${2:-}"
    if [ -z "$FIRE_AT" ]; then
      echo "usage: $0 --at HH:MM"
      exit 2
    fi
    shift 2 || true
    ;;
esac

# Prevent double-scheduling
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "scheduler already running (PID $(cat $PIDFILE))"
  echo "use --cancel to stop it first"
  exit 1
fi

# ── the worker runs detached ──────────────────────────────────────────
# This heredoc is written to a temp script + launched with nohup so the
# scheduler survives this shell exiting.
WORKER="logs/.schedule-eod-worker-${TODAY}.sh"
cat > "$WORKER" <<WORKEREOF
#!/bin/bash
set -u
cd "$ROOT"
TARGET_HHMM="$FIRE_AT"
LOG="$LOG"

echo "[\$(date '+%H:%M:%S')] EOD scheduler armed — will fire at \${TARGET_HHMM}" >> "\$LOG"

# Sleep-and-check loop (60s tick)
while :; do
  NOW_HHMM=\$(date +%H:%M)
  if [[ "\$NOW_HHMM" > "\$TARGET_HHMM" ]] || [[ "\$NOW_HHMM" == "\$TARGET_HHMM" ]]; then
    break
  fi
  sleep 60
done

echo "[\$(date '+%H:%M:%S')] EOD report firing..." >> "\$LOG"

# Give the trading engines a moment to flush final state
sleep 20

# Run the report
python3 scripts/eod-comparison-report.py >> "\$LOG" 2>&1
RC=\$?
echo "[\$(date '+%H:%M:%S')] report exit code: \$RC" >> "\$LOG"

# Open the PDF + the watchdog folder in Finder (macOS)
REPORT_DIR="\$ROOT/docs/watchdog/reports/\$(date +%Y-%m-%d)_eod"
PDF="\$REPORT_DIR/report.pdf"
if [ -f "\$PDF" ]; then
  open "\$PDF" 2>> "\$LOG" || true
  open "\$REPORT_DIR" 2>> "\$LOG" || true
  echo "[\$(date '+%H:%M:%S')] opened \$PDF" >> "\$LOG"
fi

# Best-effort telegram ping (re-uses TradePilot's .env token)
if [ -f .env ]; then
  TOKEN=\$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2 | tr -d '"')
  CHAT=\$(grep '^TELEGRAM_CHAT_ID=' .env | cut -d= -f2 | tr -d '"')
  if [ -n "\$TOKEN" ] && [ -n "\$CHAT" ]; then
    MSG="EOD report ready. Check the opened PDF for today's engine scoreboard and tune-up suggestions."
    curl -s -X POST "https://api.telegram.org/bot\${TOKEN}/sendMessage" \
      --data-urlencode "chat_id=\${CHAT}" \
      --data-urlencode "text=\${MSG}" --max-time 5 >> "\$LOG" 2>&1 || true
  fi
fi

# Clean up pidfile + worker
rm -f "$PIDFILE" "$WORKER"
echo "[\$(date '+%H:%M:%S')] scheduler done" >> "\$LOG"
WORKEREOF
chmod +x "$WORKER"

# Launch detached
nohup "$WORKER" > /dev/null 2>&1 &
PID=$!
echo "$PID" > "$PIDFILE"

sleep 1
if kill -0 "$PID" 2>/dev/null; then
  echo "EOD report scheduled for $FIRE_AT (PID $PID)"
  echo "log: $LOG"
  echo "pidfile: $PIDFILE"
  echo ""
  echo "To cancel: $0 --cancel"
  echo "To check : $0 --status"
else
  echo "FAILED to start scheduler"
  rm -f "$PIDFILE" "$WORKER"
  exit 1
fi
