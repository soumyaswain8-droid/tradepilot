#!/bin/bash
# Single entry point for the small-capital lanes, so capital and mode are set in ONE
# place. Wednesday's switch to real money is: LANE_MODE=real in this file.
#
#   ./scripts/run-lane.sh real       card the equity slots
#   ./scripts/run-lane.sh opt        card the option
#   ./scripts/run-lane.sh sarathi    agent chart read
#   ./scripts/run-lane.sh squareoff  square-off reminder
set -u
cd "$(dirname "$0")/.." || exit 1

export LANE_CAPITAL="${LANE_CAPITAL:-3000}"
export LANE_MODE="${LANE_MODE:-paper}"          # <- flip to "real" on Wednesday
PY=/Users/soumyaswain/anaconda3/bin/python3
LOG="logs/lane-$(date +%Y-%m-%d).log"
mkdir -p logs

# Weekday + session guard at the shell level too. The Python lanes each guard
# themselves, but a launchd job that fires on a holiday should not even start —
# silent no-ops are how a dead lane goes unnoticed for a week.
DOW=$(date +%u)
if [ "$DOW" -ge 6 ]; then
  echo "$(date '+%H:%M:%S') [$1] weekend — skipped" >> "$LOG"
  exit 0
fi

echo "=== $(date '+%Y-%m-%d %H:%M:%S') lane=$1 capital=$LANE_CAPITAL mode=$LANE_MODE ===" >> "$LOG"
case "$1" in
  tokencheck)
             # Runs before the first lane each morning. The dead-token bug of
             # 2026-08-27 was invisible for 90 minutes; this makes it loud.
             $PY scripts/test-token-refresh.py >> "$LOG" 2>&1 || \
               echo "$(date '+%H:%M:%S') TOKEN REFRESH TEST FAILED" >> "$LOG" ;;
  real)      $PY scripts/real1k.py --card       >> "$LOG" 2>&1 ;;
  opt)       $PY scripts/opt1k.py  --card       >> "$LOG" 2>&1 ;;
  sarathi)   $PY scripts/sarathi-lane.py --watch --limit 8 >> "$LOG" 2>&1 ;;
  shadow)    $PY scripts/shadow-settle.py       >> "$LOG" 2>&1 ;;
  squareoff) $PY scripts/real1k.py --status     >> "$LOG" 2>&1
             $PY scripts/opt1k.py  --status     >> "$LOG" 2>&1 ;;
  *) echo "usage: run-lane.sh tokencheck|real|opt|sarathi|shadow|squareoff"; exit 2 ;;
esac
tail -20 "$LOG"
