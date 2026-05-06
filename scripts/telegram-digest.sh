#!/bin/bash
# Send status digest to Telegram every 2 hours during market hours.
#
# Design (updated 2026-04-28 to reduce noise):
#   - Active 09:15–15:30 IST (sends digest every 2 hours)
#   - Sends EOD summary at 15:30
#   - Silent outside market hours
#   - Uses scripts/status-digest.py for the digest content
#   - Tunable via DIGEST_INTERVAL_SEC env var (e.g. 7200 = 2h, 1800 = 30m, 3600 = 1h)

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"

MARKET_OPEN_MIN=$((9 * 60 + 15))    # 09:15
MARKET_CLOSE_MIN=$((15 * 60 + 30))  # 15:30
INTERVAL_SEC=${DIGEST_INTERVAL_SEC:-7200}   # default 2 hours (was 30 min)

now_min() {
  echo $((10#$(date +%H) * 60 + 10#$(date +%M)))
}

in_market_hours() {
  local nm
  nm=$(now_min)
  [ "$nm" -ge "$MARKET_OPEN_MIN" ] && [ "$nm" -le "$MARKET_CLOSE_MIN" ]
}

send_telegram() {
  # 2026-05-07: parse_mode=HTML so <pre>...</pre> from status-digest.py
  # renders as monospace (editorial-voice column-aligned tables).
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
        --data-urlencode "parse_mode=HTML" \
        --data-urlencode "disable_web_page_preview=true" \
        --max-time 10 > /dev/null 2>&1
    fi
  fi
}

_hours=$((INTERVAL_SEC / 3600))
_mins_total=$((INTERVAL_SEC / 60))
echo "[$(date '+%H:%M:%S')] telegram-digest started — will send every ${_mins_total} min during 09:15–15:30 IST"
send_telegram "<b>TRADEPILOT</b>  ·  digest monitor online  ·  cadence ${_hours}h"

while true; do
  if ! in_market_hours; then
    sleep 300  # Check every 5 min when outside hours
    continue
  fi

  # Generate digest and send
  digest=$(python3 scripts/status-digest.py 2>&1)
  if [ -n "$digest" ]; then
    send_telegram "$digest"
    echo "[$(date '+%H:%M:%S')] digest sent"
  else
    echo "[$(date '+%H:%M:%S')] digest empty — skipped"
  fi

  # EOD summary
  nm=$(now_min)
  if [ "$nm" -ge "$MARKET_CLOSE_MIN" ]; then
    send_telegram "<b>MARKET CLOSED</b>  ·  final digest above  ·  silent until tomorrow"
    echo "[$(date '+%H:%M:%S')] EOD digest sent, exiting"
    exit 0
  fi

  sleep $INTERVAL_SEC
done
