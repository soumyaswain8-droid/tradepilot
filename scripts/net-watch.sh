#!/bin/bash
# net-watch — one line per minute on link health, so a flaky session is EVIDENCE.
# Probes the two things that actually matter: Kite REST (quotes/scouts) and DNS.
set -u
cd "$(dirname "$0")/.." || exit 1
LOG="logs/net-watch-$(date +%Y-%m-%d).log"
mkdir -p logs
while :; do
  m=$(( 10#$(date +%H) * 60 + 10#$(date +%M) ))
  [ "$m" -ge 935 ] && break
  k=$(curl -s -o /dev/null -w "%{http_code}:%{time_total}" --max-time 8 https://api.kite.trade/ 2>/dev/null || echo "ERR:0")
  p=$(ping -c 2 -t 4 1.1.1.1 2>/dev/null | awk -F'/' '/round-trip/{printf "%.0fms",$5}')
  [ -z "$p" ] && p="LOSS"
  echo "$(date '+%H:%M:%S') kite=$k ping=$p" >> "$LOG"
  sleep 60
done
