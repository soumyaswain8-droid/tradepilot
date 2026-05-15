#!/bin/bash
# FULL BATTLE LAUNCH — everything needed for today's market.
# Use this as the single command after laptop restart or every morning.
#
# Launches:
#   1. Rust engine (execution/risk layer)
#   2. Flask dashboard (localhost:5050)
#   3. daily-scores archiver (snapshots dashboard BUY/HOLD list — added 2026-04-23)
#   4. 4 paper-trade engines (v5, v5_classic, v5_6, v5_7) — see RETIRED list below
#   5. crash-watchdog (restart crashed engines)
#   6. telegram-digest (30-min P&L updates to Soumya)
#   7. laptop-heartbeat (15-min "alive" ping)
#   8. auto-stop-eod (kills everything at 15:35)
#   9. satish-schedule (4 trade-data updates/day — only if SATISH_TELEGRAM_CHAT_ID set)
#
# RETIRED 2026-04-27 (no longer auto-launched, scripts and models preserved):
#   v4    — original engine. Code at scripts/v4-paper-trade.py and prototype/v4/
#           kept indefinitely; v4's ml_engine + composite_scorer + tiered models
#           are STILL used by v5/v5_6/v5_7 as the underlying ML layer.
#   v5_2  — F&O straddle experiment. Cycle-based, not continuous. Insights logged.
#   v5_3  — over-filtered variant. Carrying -Rs 52,864 cumulative loss.
#   To re-enable: uncomment the relevant entry in the ENGINES array below.
#
# Usage:
#   ./scripts/launch-market.sh              # full launch
#   ./scripts/launch-market.sh --stop       # kill everything
#   ./scripts/launch-market.sh --status     # show what's running

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"
mkdir -p logs

TODAY=$(date +%Y-%m-%d)
STAMP=$(date +%H%M%S)

ENGINES=(
  # Active engines: 3 (post-Sprint-1 consolidation per CEO option 3B, 2026-05-15).
  # Rationale: focus rebuild effort on a smaller A/B set. v5_6/v5_7/v5_8/v6
  # explore different strategies and add maintenance cost during the 8-week rebuild.
  # State files preserved; can be revived after rebuild via uncomment.
  "v4|scripts/v4-paper-trade.py"
  "v5|scripts/v5-paper-trade.py"
  "v5_classic|scripts/v5_classic-paper-trade.py"

  # Retired 2026-05-15 (Sprint 1) — state files preserved, scripts unchanged.
  # Uncomment to re-introduce after primary rebuild completes (~2026-07-15).
  # "v5_6|scripts/v5_6-paper-trade.py"     # Darvas-box breakout
  # "v5_7|scripts/v5_7-paper-trade.py"     # Box mean-reversion
  # "v5_8|scripts/v5_8-paper-trade.py"     # v5 with regime slot-partition disabled
  # "v6|scripts/v6-paper-trade.py"         # v4 raw signals + Track A bolt-on

  # Still retired from earlier rounds:
  # "v5_2|scripts/v5_2-paper-trade.py"
  # "v5_3|scripts/v5_3-paper-trade.py"
)

send_telegram() {
  local msg="$1"
  if [ -f .env ]; then
    local token chat
    token=$(grep '^TELEGRAM_BOT_TOKEN=' .env | cut -d= -f2 | tr -d '"')
    chat=$(grep '^TELEGRAM_CHAT_ID=' .env | cut -d= -f2 | tr -d '"')
    if [ -n "$token" ] && [ -n "$chat" ]; then
      curl -s -X POST "https://api.telegram.org/bot${token}/sendMessage" \
        --data-urlencode "chat_id=${chat}" \
        --data-urlencode "text=${msg}" --max-time 5 > /dev/null 2>&1
    fi
  fi
}

# ═══════════════════════════ STATUS ═══════════════════════════
if [ "${1:-}" = "--status" ]; then
  echo "═══ TradePilot process status ═══"
  echo ""
  echo "Rust engine:     $(pgrep -lf 'tradepilot-engine' | head -1 || echo 'NOT RUNNING')"
  echo "Flask dashboard: $(lsof -iTCP:5050 -sTCP:LISTEN -n -P 2>/dev/null | tail -1 | awk '{print $1, $2}' || echo 'NOT RUNNING')"
  echo ""
  echo "Engines:"
  for entry in "${ENGINES[@]}"; do
    IFS='|' read -r name script <<< "$entry"
    pid=$(pgrep -f "$script" | head -1)
    printf "  %-12s %s\n" "$name" "${pid:-NOT RUNNING}"
  done
  echo ""
  echo "Monitors:"
  printf "  %-18s %s\n" "crash-watchdog"   "$(pgrep -f 'crash-watchdog.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "telegram-digest"  "$(pgrep -f 'telegram-digest.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "laptop-heartbeat" "$(pgrep -f 'laptop-heartbeat.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "auto-stop-eod"    "$(pgrep -f 'auto-stop-eod.sh' | head -1 || echo '-')"
  printf "  %-18s %s\n" "satish-schedule"  "$(pgrep -f 'satish-schedule.sh' | head -1 || echo '-')"
  echo ""
  echo "Caffeinate:      $(pgrep caffeinate | head -1 || echo 'NOT RUNNING (laptop may sleep)')"
  exit 0
fi

# ═══════════════════════════ STOP ═══════════════════════════
if [ "${1:-}" = "--stop" ]; then
  echo "Stopping TradePilot stack..."
  pkill -f "scripts/v[0-9].*paper-trade.py" 2>/dev/null
  pkill -f "scripts/crash-watchdog.sh"  2>/dev/null
  pkill -f "scripts/telegram-digest.sh" 2>/dev/null
  pkill -f "scripts/laptop-heartbeat.sh" 2>/dev/null
  pkill -f "scripts/auto-stop-eod.sh"   2>/dev/null
  pkill -f "scripts/satish-schedule.sh" 2>/dev/null
  pkill -f "tradepilot-engine"          2>/dev/null
  sleep 2
  remaining=$(ps aux | grep -cE "paper-trade|crash-watchdog|telegram-digest|laptop-heartbeat|auto-stop-eod|satish-schedule|tradepilot-engine" | grep -v grep)
  echo "Remaining: ${remaining}"
  send_telegram "🛑 TradePilot stopped at $(date +%H:%M). Full stack shut down."
  exit 0
fi

# ═══════════════════════════ LAUNCH ═══════════════════════════
echo "════════════════════════════════════════════════════════════"
echo "  TradePilot FULL LAUNCH — $TODAY $STAMP"
echo "════════════════════════════════════════════════════════════"

# [0/9] Kill stale processes
echo "[0/9] Cleaning stale processes..."
pkill -f "scripts/v[0-9].*paper-trade.py" 2>/dev/null
pkill -f "scripts/crash-watchdog.sh"  2>/dev/null
pkill -f "scripts/telegram-digest.sh" 2>/dev/null
pkill -f "scripts/laptop-heartbeat.sh" 2>/dev/null
pkill -f "scripts/auto-stop-eod.sh"   2>/dev/null
pkill -f "scripts/satish-schedule.sh" 2>/dev/null
pkill -f "tradepilot-engine"          2>/dev/null
sleep 2

# [0.5/9] Pre-launch verification — catches import/syntax bugs BEFORE engines deploy.
# Added 2026-05-11 after Monday morning's v4 crash (preflight import path was wrong,
# crashed at 09:30 IST market open). Runs only the smoke section (~2s) for speed.
#
# 2026-05-12 FIX: previous version was `if cmd 2>&1 | tail -5; then` which checks
# tail's exit code (always 0), NOT the upstream verify script's. Result: gate
# always passed even when smoke failed. Fixed by capturing output first, then
# checking the script's actual exit code separately.
echo "[0.5/9] Pre-launch verification (smoke test — would have caught Monday's crash)..."
SMOKE_OUTPUT=$(./scripts/sarathi-verify.sh --smoke --quiet 2>&1)
SMOKE_EXIT=$?
echo "$SMOKE_OUTPUT" | tail -5
if [ "$SMOKE_EXIT" -eq 0 ]; then
  echo "  ✓ All 7 engine scripts import + compile clean"
else
  echo ""
  echo "  ✗ PRE-LAUNCH SMOKE FAILED (exit $SMOKE_EXIT) — refusing to start engines."
  echo "  → Run: ./scripts/sarathi-verify.sh   (full output)"
  echo "  → Fix the issue, then re-launch."
  exit 2
fi

# [1/9] Rust engine
echo "[1/9] Starting Rust engine (execution + risk)..."
if [ -f "./engine/target/release/tradepilot-engine" ]; then
  nohup ./engine/target/release/tradepilot-engine > /tmp/rust-engine.log 2>&1 &
  echo "  ✓ Rust engine launched (PID $!)"
  sleep 2
  # Health check
  if curl -s http://localhost:8080/health | grep -q success; then
    echo "  ✓ Rust /health OK (risk config loaded from .env)"
  else
    echo "  ⚠ Rust started but /health not responding — continuing"
  fi
else
  echo "  ✗ Rust binary missing at ./engine/target/release/tradepilot-engine"
  echo "    Run: cd engine && cargo build --release"
fi

# [2/9] Flask dashboard
echo "[2/9] Starting Flask dashboard (localhost:5050)..."
if lsof -iTCP:5050 -sTCP:LISTEN -n -P > /dev/null 2>&1; then
  echo "  ✓ already running on :5050"
else
  cd prototype && nohup python3 app.py > /tmp/flask.log 2>&1 &
  cd "$ROOT"
  echo "  ✓ Flask launched (PID $!)"
fi

# [3/9] Capture today's dashboard score snapshot (added 2026-04-23)
# Foundation for consensus-pick analysis: archives the BUY/HOLD list BEFORE
# engines start trading. ~10-15s. Run in background so it doesn't gate engines.
echo "[3/9] Archiving today's dashboard scores in background..."
nohup python3 ./scripts/archive-daily-scores.py > "logs/archive-scores-${TODAY}.log" 2>&1 &
echo "  ✓ daily scores archiver (PID $!) → docs/dashboard-scores/${TODAY}.json"

# [4/9] Engines
echo "[4/9] Launching 7 paper-trade engines..."
for entry in "${ENGINES[@]}"; do
  IFS='|' read -r name script <<< "$entry"
  if [ ! -f "$script" ]; then
    echo "  ✗ $name — script missing"
    continue
  fi
  nohup python3 "$script" > "logs/${name}-${TODAY}.log" 2>&1 &
  echo "  ✓ $name (PID $!)"
  sleep 1
done

# [5/9] Crash watchdog
echo "[5/9] Launching crash-watchdog..."
nohup ./scripts/crash-watchdog.sh > "logs/watchdog-${TODAY}.log" 2>&1 &
echo "  ✓ watchdog (PID $!)"

# [6/9] Telegram digest (30-min)
echo "[6/9] Launching telegram-digest (30-min Soumya updates)..."
nohup ./scripts/telegram-digest.sh > "logs/telegram-digest-${TODAY}.log" 2>&1 &
echo "  ✓ digest (PID $!)"

# [7/9] Laptop heartbeat (15-min)
echo "[7/9] Launching laptop-heartbeat..."
nohup ./scripts/laptop-heartbeat.sh > "logs/laptop-heartbeat-${TODAY}.log" 2>&1 &
echo "  ✓ heartbeat (PID $!)"

# [8/9] Auto-stop-EOD
echo "[8/9] Launching auto-stop-eod (fires 15:35)..."
nohup ./scripts/auto-stop-eod.sh > "logs/auto-stop-${TODAY}.log" 2>&1 &
echo "  ✓ auto-stop (PID $!)"

# [9/9] Satish schedule — only if his chat ID is set
echo "[9/9] Satish schedule check..."
if grep -q "^SATISH_TELEGRAM_CHAT_ID=[0-9]" .env 2>/dev/null; then
  nohup ./scripts/satish-schedule.sh > "logs/satish-schedule-${TODAY}.log" 2>&1 &
  echo "  ✓ satish-schedule launched (PID $!) — will send 4 trade reports to Satish today"
else
  echo "  ⊘ SATISH_TELEGRAM_CHAT_ID not set — skipping. Run manually once Satish messages bot."
fi

# Verify
echo ""
echo "[verify] Checking process health..."
sleep 3
alive=$(pgrep -f "scripts/v[0-9].*paper-trade.py" | wc -l | tr -d ' ')
wd=$(pgrep -f "scripts/crash-watchdog.sh" | wc -l | tr -d ' ')
rust=$(pgrep -f "tradepilot-engine" | wc -l | tr -d ' ')
echo "  Engines: $alive/7  |  Watchdog: $wd/1  |  Rust: $rust/1"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  FULL LAUNCH COMPLETE — $(date +%H:%M:%S)"
echo "  Status check:  ./scripts/launch-market.sh --status"
echo "  Quick digest:  python3 scripts/status-digest.py"
echo "  Stop all:      ./scripts/launch-market.sh --stop"
echo "════════════════════════════════════════════════════════════"

send_telegram "🚀 TradePilot FULL LAUNCH at $(date +%H:%M).
Engines: ${alive}/7 · Rust: ${rust}/1 · Watchdog: ${wd}/1
ML model: fixed (best_iter=1726, india_vix #1)
Rust cap: 150 (was 30)
Ready for battle."
