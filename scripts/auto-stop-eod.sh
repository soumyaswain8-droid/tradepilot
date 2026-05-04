#!/bin/bash
# Automatic shutdown at EOD (15:35 IST).
# Stops all engines, watchdog, and digest monitor, then generates EOD report.

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"

STOP_MIN=$((15 * 60 + 35))  # 15:35 IST
SAFETY_CUTOFF_MIN=$((16 * 60))  # 16:00 — if we're past this, exit immediately (shouldn't run overnight)

now_min() {
  echo $((10#$(date +%H) * 60 + 10#$(date +%M)))
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

echo "[$(date '+%H:%M:%S')] auto-stop-eod armed, will fire at 15:35 IST"

# Wait until stop time
while true; do
  nm=$(now_min)

  # Safety: if it's past 16:00 and we're still running, something's wrong — exit
  if [ "$nm" -ge "$SAFETY_CUTOFF_MIN" ] && [ "$nm" -le $((22 * 60)) ]; then
    echo "[$(date '+%H:%M:%S')] past safety cutoff, firing now"
    break
  fi

  # If we've reached stop time, fire
  if [ "$nm" -ge "$STOP_MIN" ] && [ "$nm" -lt "$SAFETY_CUTOFF_MIN" ]; then
    echo "[$(date '+%H:%M:%S')] STOP_MIN reached — shutting down"
    break
  fi

  sleep 60
done

# ========== SHUTDOWN SEQUENCE ==========
echo "[$(date '+%H:%M:%S')] Starting EOD shutdown..."

# 1. Stop watchdog FIRST (so it doesn't restart engines we're killing)
pkill -f "scripts/crash-watchdog.sh" 2>/dev/null
echo "  ✓ watchdog stopped"

# 2. Stop telegram digest
pkill -f "scripts/telegram-digest.sh" 2>/dev/null
echo "  ✓ telegram-digest stopped"

# 3. Stop all paper-trade engines
pkill -f "scripts/v[45].*paper-trade.py" 2>/dev/null
sleep 2
echo "  ✓ all 7 engines stopped"

# 3a. Stop profit-watchdog, heartbeat, satish-schedule (supplementary monitors)
pkill -f "scripts/profit-watchdog.py"   2>/dev/null && echo "  ✓ profit-watchdog stopped"
pkill -f "scripts/laptop-heartbeat.sh"  2>/dev/null && echo "  ✓ laptop-heartbeat stopped"
pkill -f "scripts/satish-schedule.sh"   2>/dev/null && echo "  ✓ satish-schedule stopped"

# 3b. Stop Rust engine (execution layer) — was surviving shutdown previously
pkill -f "tradepilot-engine"            2>/dev/null && echo "  ✓ Rust engine stopped"

# 4. Send Telegram summary (pull final digest)
digest=$(python3 scripts/status-digest.py 2>&1 || echo "(digest failed)")
send_telegram "🛑 EOD auto-stop complete at $(date +%H:%M).

Final standings:
${digest}

All engines + watchdog + digest monitor shut down. See you tomorrow 09:00 IST."

# 5. Run EOD insights watchdog — sends improvement suggestions to Telegram
echo "[$(date '+%H:%M:%S')] Running EOD insights..."
python3 scripts/eod-insights.py > "/tmp/eod-insights-$(date +%Y%m%d).log" 2>&1 || echo "  (eod-insights failed, see /tmp/eod-insights-*.log)"

# 5a. Generate the EOD side-by-side comparison report (HTML + PDF + charts)
echo "[$(date '+%H:%M:%S')] Generating EOD comparison report..."
python3 scripts/eod-comparison-report.py > "/tmp/eod-report-$(date +%Y%m%d).log" 2>&1 \
  && echo "  ✓ EOD report: docs/watchdog/reports/$(date +%Y-%m-%d)_eod/report.pdf" \
  || echo "  (eod-comparison-report failed, see /tmp/eod-report-*.log)"

# 5. Verify nothing left
remaining=$(ps aux | grep -E "paper-trade|crash-watchdog|telegram-digest" | grep -v grep | grep -v Docker | grep -v watchdogd | wc -l | tr -d ' ')
echo "[$(date '+%H:%M:%S')] Shutdown complete. Remaining processes: $remaining"

if [ "$remaining" -gt "0" ]; then
  echo "WARNING: $remaining processes still alive — manual check needed"
  ps aux | grep -E "paper-trade|crash-watchdog|telegram-digest" | grep -v grep | grep -v Docker | grep -v watchdogd
fi

exit 0
