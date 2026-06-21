#!/usr/bin/env bash
# Launch the two A/B CHALLENGER engines (caffeinated) for the day, alongside the
# live stack (which launch-market.sh / launchd brings up separately).
#   - old 5-tree v4   (~/Documents/tinker/projects/tradepilot-oldengine-ab)
#   - long-only v5    (~/Documents/tinker/projects/tradepilot-v5-longonly-ab)
# Both runners self-gate to market open (v4 has a 09:30 guard; v5 waits), so this
# is safe to run any time pre-open. Caffeinate keeps each alive through the session.
# Usage:  ./scripts/launch-ab.sh   (or --stop to kill them)
set -uo pipefail
PY=/Users/soumyaswain/anaconda3/bin/python3
DAY=$(date +%F)

if [[ "${1:-}" == "--stop" ]]; then
  pkill -f "tradepilot-oldengine-ab" 2>/dev/null && echo "stopped AB v4" || true
  pkill -f "tradepilot-v5-longonly-ab" 2>/dev/null && echo "stopped AB v5" || true
  exit 0
fi

start() { # dir, env, label
  local dir="$1" env="$2" label="$3"
  if pgrep -f "$dir" >/dev/null 2>&1; then echo "  $label already running"; return; fi
  mkdir -p "$HOME/Documents/tinker/projects/$dir/logs"
  ( cd "$HOME/Documents/tinker/projects/$dir" && \
    env $env nohup caffeinate -i "$PY" scripts/v$4-paper-trade.py \
      >> "logs/${label}-${DAY}.log" 2>&1 & echo "  $label PID $!" )
}

echo "[A/B] launching challengers ($DAY)..."
start "tradepilot-oldengine-ab"    ""              "oldengine-ab"   4
start "tradepilot-v5-longonly-ab"  "V5_LONG_ONLY=1" "v5-longonly-ab" 5
echo "[A/B] done. Compare EOD on the /lab dashboard (or per-dir compare scripts)."
