#!/bin/bash
# FULL BATTLE LAUNCH — everything needed for today's market.
# Use this as the single command after laptop restart or every morning.
# Triggered automatically Mon-Fri 09:10 IST via launchd (com.tradepilot.v2.launch-market).
#
# Launches:
#   1. Rust engine (execution/risk layer)
#   2. Flask dashboard (localhost:5050) — also serves /team agent dashboard
#   3. daily-scores archiver (snapshots dashboard BUY/HOLD list — added 2026-04-23)
#   4. 3 paper-trade engines (v4, v5, v5_classic) — see Sprint 1 consolidation below
#   5. crash-watchdog (restart crashed engines)
#   6. telegram-digest (30-min P&L updates to Soumya)
#   7. laptop-heartbeat (15-min "alive" ping)
#   8. auto-stop-eod (kills everything at 15:35)
#   9. satish-schedule (4 trade-data updates/day — only if SATISH_TELEGRAM_CHAT_ID set)
#
# SPRINT 1 CONSOLIDATION (2026-05-15, CEO option 3B):
#   Active: v4 (control), v5 (primary rebuild target), v5_classic (frozen baseline)
#   Retired (commented in ENGINES array; state preserved, scripts unchanged):
#     v5_6  Darvas-box breakout
#     v5_7  Box mean-reversion
#     v5_8  v5 with regime slot-partition disabled
#     v6    v4 raw signals + Track A bolt-on
#   To re-enable: uncomment in ENGINES array. Re-introduction planned post-rebuild (~2026-07-15).
#
# Usage:
#   ./scripts/launch-market.sh              # full launch
#   ./scripts/launch-market.sh --stop       # kill everything
#   ./scripts/launch-market.sh --status     # show what's running
#
# EXIT CODES (S2-PM-006 — consumed by scripts/team/cadence/market_go.py).
# Any non-zero exit is treated as a SARATHI-CDE BLOCK by market_go.py: it pages
# Telegram and refuses to let the session pass silently. Distinct codes let the
# pager say *what* failed without scraping the log.
#
#   0   SUCCESS         Full happy-path launch (all critical components up).
#   2   SMOKE_FAILED    Pre-launch smoke test (sarathi-verify --smoke) failed —
#                       engines NOT started (hard gate, before anything deploys).
#   3   RUST_MISSING    Rust engine binary absent — the execution/risk layer never
#                       started. The rest of the stack is still launched (so the
#                       dashboard/engines come up), but we exit non-zero at the end
#                       so market_go.py pages: trades have no execution backstop.
#   4   ENGINE_MISSING  One or more paper-trade engine scripts were missing on disk;
#                       fewer engines launched than ENGINES defines. Stack continues,
#                       non-zero exit at the end so the shortfall is paged.
#
# Codes are reserved sequentially; --stop / --status always exit 0.

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"
mkdir -p logs

TODAY=$(date +%Y-%m-%d)
STAMP=$(date +%H%M%S)

# ──────────────────────── Exit codes (see header) ────────────────────────
# S2-PM-006: distinct, documented codes so market_go.py can page on the exact
# failure class. SMOKE_FAILED is a hard gate (exit immediately, no engines).
# RUST_MISSING / ENGINE_MISSING are *deferred* — the rest of the stack still
# launches (best-effort partial day), but EXIT_CODE is set and returned at the
# very end so a non-zero exit reaches market_go.py.
readonly EX_SMOKE_FAILED=2
readonly EX_RUST_MISSING=3
readonly EX_ENGINE_MISSING=4
EXIT_CODE=0   # promoted to a non-zero EX_* by deferred failures below

# ──────────────────────────── Sleep prevention ────────────────────────────
# Wednesday 2026-05-27 lost an entire trading session because the laptop slept
# at 08:45 right after engines warmed up. Until then, this script relied on a
# separately-managed caffeinate that wasn't guaranteed to exist. Now we own it:
# launch starts a dedicated caffeinate that survives until --stop (or auto-stop-eod).
CAFFEINATE_PID_FILE="/tmp/tradepilot-caffeinate.pid"

start_caffeinate() {
  if [ -f "$CAFFEINATE_PID_FILE" ] && kill -0 "$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null)" 2>/dev/null; then
    echo "  ✓ caffeinate already running (PID $(cat "$CAFFEINATE_PID_FILE"))"
    return 0
  fi
  # -d: prevent display sleep; -i: idle; -m: disk; -s: system; -u: user-active assertion
  nohup caffeinate -dimsu > /dev/null 2>&1 &
  local pid=$!
  echo "$pid" > "$CAFFEINATE_PID_FILE"
  echo "  ✓ caffeinate started (PID $pid) — laptop locked awake until --stop or 15:35 EOD"
}

stop_caffeinate() {
  if [ -f "$CAFFEINATE_PID_FILE" ]; then
    local pid
    pid=$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null)
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null && echo "  ✓ caffeinate stopped (PID $pid)"
    fi
    rm -f "$CAFFEINATE_PID_FILE"
  fi
}

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

  # Opt-in A/B (uncomment to run alongside v4/v5):
  # "v7_regime|scripts/v7_regime-paper-trade.py"   # regime-gated long/short/flip (A/B vs v4/v5)

  # Still retired from earlier rounds:
  # "v5_2|scripts/v5_2-paper-trade.py"
  # "v5_3|scripts/v5_3-paper-trade.py"
)

# Expected number of active engines — derived from the ENGINES array length so the
# verify/launch lines never drift from reality (S2-PM-004: the old hardcoded "/7"
# was a leftover from the retired 7-engine setup; only 3 are active post-Sprint-1).
EXPECTED_ENGINES=${#ENGINES[@]}

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
  # Show OUR caffeinate (PID-tracked, owned by launch-market.sh) rather than any
  # stranger caffeinate that might happen to be on the system.
  if [ -f "$CAFFEINATE_PID_FILE" ] && kill -0 "$(cat "$CAFFEINATE_PID_FILE" 2>/dev/null)" 2>/dev/null; then
    echo "Caffeinate (ours): $(cat "$CAFFEINATE_PID_FILE") — wake-lock held"
  else
    echo "Caffeinate (ours): NOT RUNNING — laptop free to sleep (Wed-2026-05-27 risk)"
  fi
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
  if [ -f /tmp/tradepilot-wifi-watchdog.pid ]; then
    kill "$(cat /tmp/tradepilot-wifi-watchdog.pid)" 2>/dev/null && echo "  ✓ wifi-watchdog stopped"
    rm -f /tmp/tradepilot-wifi-watchdog.pid
  fi
  pkill -f "scripts/wifi-watchdog.sh" 2>/dev/null
  stop_caffeinate
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

# [0/9] Sleep prevention FIRST — before anything else can fail and leave the
# laptop free to nap through the market session (lost Wed 2026-05-27 this way).
echo "[0/9] Locking laptop awake (caffeinate)..."
start_caffeinate

# [0/9] Network guardian — keep laptop on hotspot "Pro" through the session (2026-06-05)
WIFI_WATCHDOG_PID_FILE="/tmp/tradepilot-wifi-watchdog.pid"
mkdir -p "$HOME/Library/Logs/tradepilot"
if [ -f "$WIFI_WATCHDOG_PID_FILE" ] && kill -0 "$(cat "$WIFI_WATCHDOG_PID_FILE" 2>/dev/null)" 2>/dev/null; then
  echo "[0/9] wifi-watchdog already running (PID $(cat "$WIFI_WATCHDOG_PID_FILE"))"
else
  echo "[0/9] Starting wifi-watchdog (network -> hotspot 'Pro')..."
  WIFI_TARGET_SSID="Pro" nohup bash "$ROOT/scripts/wifi-watchdog.sh" > "$HOME/Library/Logs/tradepilot/wifi-watchdog.log" 2>&1 &
  echo $! > "$WIFI_WATCHDOG_PID_FILE"
  echo "  ✓ wifi-watchdog started (PID $!) — target SSID 'Pro'"
fi

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
  echo "  ✓ Engine scripts import + compile clean"
else
  echo ""
  echo "  ✗ PRE-LAUNCH SMOKE FAILED (exit $SMOKE_EXIT) — refusing to start engines."
  echo "  → Run: ./scripts/sarathi-verify.sh   (full output)"
  echo "  → Fix the issue, then re-launch."
  exit $EX_SMOKE_FAILED
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
  echo "  - Rust engine DISABLED (2026-06-05 decision: dropped as optional layer)."
  echo "    Python engines run solo via rust_bridge offline-fallback. To re-enable:"
  echo "    cd engine && cargo build --release"
  # Rust is OPTIONAL now — do NOT set RUST_MISSING; this is not a failure.
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
echo "[4/9] Launching ${EXPECTED_ENGINES} paper-trade engines..."
for entry in "${ENGINES[@]}"; do
  IFS='|' read -r name script <<< "$entry"
  if [ ! -f "$script" ]; then
    echo "  ✗ $name — script missing"
    # Deferred failure (S2-PM-006): a defined engine is missing on disk. Don't
    # clobber a prior RUST_MISSING (3) — only set ENGINE_MISSING if still clean.
    [ "$EXIT_CODE" -eq 0 ] && EXIT_CODE=$EX_ENGINE_MISSING
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
echo "  Engines: $alive/${EXPECTED_ENGINES}  |  Watchdog: $wd/1  |  Rust: $rust/1"

# If fewer engines came up alive than defined (e.g. one crashed on boot), flag a
# deferred ENGINE_MISSING — unless a higher-priority RUST_MISSING already stands.
if [ "$alive" -lt "$EXPECTED_ENGINES" ] && [ "$EXIT_CODE" -eq 0 ]; then
  EXIT_CODE=$EX_ENGINE_MISSING
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  FULL LAUNCH COMPLETE — $(date +%H:%M:%S)"
echo "  Status check:  ./scripts/launch-market.sh --status"
echo "  Quick digest:  python3 scripts/status-digest.py"
echo "  Stop all:      ./scripts/launch-market.sh --stop"
echo "════════════════════════════════════════════════════════════"

send_telegram "🚀 TradePilot FULL LAUNCH at $(date +%H:%M).
Engines: ${alive}/${EXPECTED_ENGINES} · Rust: ${rust}/1 · Watchdog: ${wd}/1
ML model: fixed (best_iter=1726, india_vix #1)
Rust cap: 150 (was 30)
Ready for battle."

# S2-PM-006: return the deferred failure code (0 on a clean happy-path launch).
# market_go.py reads this — any non-zero triggers a SARATHI-CDE BLOCK + page.
exit $EXIT_CODE
