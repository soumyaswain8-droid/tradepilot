#!/bin/bash
# Schedule Satish's Telegram digests during market hours.
#
# Schedule (all IST) — 4 messages per trading day:
#   09:00  — pre-market picks
#   11:15  — 2h report (covers 09:15–11:15 market open block)
#   13:15  — 2h report (covers 11:15–13:15)
#   15:15  — 2h report (covers 13:15–15:15 close)
#
# Trade data only, no system alerts.
#
# Usage:
#   ./scripts/satish-schedule.sh                 # production (sends to Satish)
#   ./scripts/satish-schedule.sh --test          # test mode (sends to Soumya)

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"

MODE="${1:---production}"

now_min() {
  echo $((10#$(date +%H) * 60 + 10#$(date +%M)))
}

send() {
  local mode="$1"      # premarket | hourly
  local lookback="$2"  # lookback minutes (hourly only)
  if [ "$mode" = "hourly" ]; then
    python3 scripts/satish-digest.py --mode hourly --lookback "$lookback" $MODE >> /tmp/satish-digest.log 2>&1
  else
    python3 scripts/satish-digest.py --mode "$mode" $MODE >> /tmp/satish-digest.log 2>&1
  fi
  echo "[$(date '+%H:%M:%S')] sent $mode"
}

echo "[$(date '+%H:%M:%S')] satish-schedule started (mode: $MODE, every 2h)"

# Fire times (minutes since midnight IST)
PREMARKET_MIN=$((9 * 60))              # 09:00
# 2-hourly slots: 11:15, 13:15, 15:15
TWOHOUR_MINS=(675 795 915)

# Track what we've already sent today to avoid duplicates
SENT_TODAY=""
LAST_DATE=""

while true; do
  today=$(date +%Y-%m-%d)
  # Reset tracking at midnight
  if [ "$today" != "$LAST_DATE" ]; then
    SENT_TODAY=""
    LAST_DATE="$today"
  fi

  nm=$(now_min)

  # Pre-market check
  if [ "$nm" -ge "$PREMARKET_MIN" ] && [ "$nm" -le $((PREMARKET_MIN + 5)) ] && [[ ! "$SENT_TODAY" == *"premarket"* ]]; then
    send premarket 0
    SENT_TODAY="$SENT_TODAY premarket"
  fi

  # 2-hourly checks (lookback 120 min)
  for target in "${TWOHOUR_MINS[@]}"; do
    if [ "$nm" -ge "$target" ] && [ "$nm" -le $((target + 5)) ] && [[ ! "$SENT_TODAY" == *"h${target}"* ]]; then
      send hourly 120
      SENT_TODAY="$SENT_TODAY h${target}"
    fi
  done

  # Stop after market close
  if [ "$nm" -ge $((16 * 60)) ]; then
    sleep 300
    continue
  fi

  sleep 60
done
