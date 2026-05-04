#!/bin/bash
# Quiet watchdog: same logic as the Claude-monitored v2, but all output goes to
# /tmp/watchdog-quiet.log and Telegram only. No stdout spam to Claude Code.

cd /Users/soumyaswain/Documents/tinker/projects/tradepilot

TOKEN=$(grep TELEGRAM_BOT_TOKEN .env | cut -d= -f2)
CHAT=$(grep TELEGRAM_CHAT_ID .env | cut -d= -f2)

tg() {
  curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${CHAT}" --data-urlencode "text=$1" > /dev/null 2>&1
}

echo "[ARMED quiet] $(date '+%Y-%m-%d %H:%M:%S') watchdog-quiet started, PID $$"
tg "🔕 Watchdog switched to quiet mode at $(date '+%H:%M IST') — auto-restart still on, no chat notifications."

# Crash watcher → Telegram only
(tail -F /tmp/v4.log /tmp/v5.log /tmp/v5_classic.log /tmp/v5_2.log /tmp/v5_3.log /tmp/v5_6.log /tmp/v5_7.log /tmp/rust_engine.log 2>/dev/null | \
  grep --line-buffered -E "Traceback|ValueError|NameError|AttributeError|KeyError|ZeroDivision|CRITICAL|FATAL|Killed|OOM|BLOCKED .reentry cap" | \
  grep --line-buffered -v -E "\.NS.*TypeError|possibly delisted|Quote not found" | \
  while read line; do
    case "$line" in
      *"reentry cap"*) tg "🛡️ REENTRY BLOCK: $line" ;;
      *) tg "🚨 CRASH: $line" ;;
    esac
  done) &

# Auto-restart loop
while true; do
  for name in v4 v5 v5_classic v5_2 v5_3 v5_6 v5_7; do
    if ! pgrep -f "scripts/${name}-paper-trade.py" > /dev/null 2>&1; then
      nohup python3 scripts/${name}-paper-trade.py >> /tmp/${name}.log 2>&1 &
      tg "🔁 RESTARTED ${name} as PID $! at $(date '+%H:%M:%S')"
    fi
  done
  if ! lsof -iTCP:8080 -sTCP:LISTEN > /dev/null 2>&1; then
    (cd engine && nohup ./target/release/tradepilot-engine >> /tmp/rust_engine.log 2>&1 &)
    tg "🔁 Rust engine restarted"
  fi
  if ! lsof -iTCP:5050 -sTCP:LISTEN > /dev/null 2>&1; then
    (cd prototype && nohup python3 app.py >> /tmp/flask.log 2>&1 &)
    tg "🔁 Flask restarted"
  fi
  sleep 60
done
