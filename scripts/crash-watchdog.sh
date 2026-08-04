#!/bin/bash
# TradePilot crash watchdog — market-hours-aware, heartbeat-based engine monitor.
#
# Design (2026-04-21, v3):
#   - Only acts during 09:00–15:30 IST (silent outside)
#   - Liveness check: each engine writes to docs/paper-trades/{engine}/{DATE}.json
#     during its scan loop. If mtime is older than HEARTBEAT_MAX_AGE_SEC → dead.
#   - No port checks (engines are background loops, not HTTP servers)
#   - No pgrep self-match bug (we check output files, not process lists)
#   - v5_3 whitelisted post-14:45 (exits by design)
#   - First scan after open = grace period (engines take ~30s to warm up)
#
# Usage:
#   ./scripts/crash-watchdog.sh           # foreground
#   nohup ./scripts/crash-watchdog.sh > /tmp/watchdog.log 2>&1 &

set -u

ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"

# ------- Market hours (IST) -------
MARKET_OPEN_MIN=$((9 * 60))         # 09:00 (engines can warm up before 09:15 open)
MARKET_CLOSE_MIN=$((15 * 60 + 30))  # 15:30
EOD_CUTOFF_MIN=$((14 * 60 + 45))    # v5_3 allowed to exit after 14:45

# ------- Heartbeat threshold (fallback only) -------
# Primary liveness check is pgrep (process-based). This mtime threshold is the
# secondary check: if process is gone AND file hasn't been updated in this long,
# engine is confirmed dead.
HEARTBEAT_MAX_AGE_SEC=2700

# ------- Engine registry: (name|output_file|launch_cmd) -------
# output_file = heartbeat (engine writes to this during each scan)
# launch_cmd = how to restart if crashed
TODAY=$(date +%Y-%m-%d)
declare -a ENGINES=(
  # Active engines (12) — must match launch-market.sh ENGINES array.
  # Count corrected 2026-07-30: the array had 9 uncommented entries while this
  # comment still said 5, which sent a live outage diagnosis down the wrong path.
  # TP-RCA 2026-06-26 lightweight roster: v5 (live) + v5_classic (frozen benchmark)
  # + v5_long (RC-1 long-only fix) + v5_cut (profit experiment). Retired v5_noml/v5_apr/v7_regime.
  # "v4|scripts/v4-paper-trade.py|docs/paper-trades/v4/${TODAY}.json|python3 scripts/v4-paper-trade.py"
  "v5|scripts/v5-paper-trade.py|docs/paper-trades/v5/${TODAY}.json|python3 scripts/v5-paper-trade.py"
  "v5_classic|scripts/v5_classic-paper-trade.py|docs/paper-trades/v5_classic/${TODAY}.json|python3 scripts/v5_classic-paper-trade.py"
  # RC-1 (TP-RCA 2026-06-26): v5_long = long-only NIFTY-200 (shorts disabled). Primary fix experiment.
  "v5_long|scripts/v5_long-paper-trade.py|docs/paper-trades/v5_long/${TODAY}.json|python3 scripts/v5_long-paper-trade.py"
  # RETIRED 2026-06-26 (TP-RCA audit): v7_regime flat vs v5 + WFO-negative (DSR 0.12). State preserved.
  # "v7_regime|scripts/v7_regime-paper-trade.py|docs/paper-trades/v7_regime/${TODAY}.json|python3 scripts/v7_regime-paper-trade.py"
  # RETIRED 2026-06-26 (TP-RCA audit): v5_noml redundant (ml=0 already global -> ran v5 twice).
  # "v5_noml|scripts/v5_noml-paper-trade.py|docs/paper-trades/v5_noml/${TODAY}.json|python3 scripts/v5_noml-paper-trade.py"
  # RETIRED 2026-06-26 (TP-RCA audit): v5_apr tracked v5 within +Rs78/9d — no info value.
  # "v5_apr|scripts/v5_apr-paper-trade.py|docs/paper-trades/v5_apr/${TODAY}.json|python3 scripts/v5_apr-paper-trade.py"
  # SHADOW (TP-QUANT): v5_cut = ML-removed + wrong-way-cut + tighter short + wide universe.
  "v5_cut|scripts/v5_cut-paper-trade.py|docs/paper-trades/v5_cut/${TODAY}.json|python3 scripts/v5_cut-paper-trade.py"
  # SHADOW (TP-RCA 2026-06-30): v5_flip = fast intraday regime-flip (5-min tape, BEAR 8/12 tilt on hard-down).
  "v5_flip|scripts/v5_flip-paper-trade.py|docs/paper-trades/v5_flip/${TODAY}.json|python3 scripts/v5_flip-paper-trade.py"
  "v5_chop|scripts/v5_chop-paper-trade.py|docs/paper-trades/v5_chop/${TODAY}.json|python3 scripts/v5_chop-paper-trade.py"
  # SHADOW (RRG Gate-1 PASS 2026-07-20): v5_rrg = v5_chop ladder, RRG rotation-count score producer.
  "v5_rrg|scripts/v5_rrg-paper-trade.py|docs/paper-trades/v5_rrg/${TODAY}.json|python3 scripts/v5_rrg-paper-trade.py"
  # SHADOW (Gate-2, spec 2026-07-20_risk_gate_three_state_verdict.md): v5_gate = RiskGate DRIVES execution + invalidation monitor, no CHOP_FILTER.
  "v5_gate|scripts/v5_gate-paper-trade.py|docs/paper-trades/v5_gate/${TODAY}.json|python3 scripts/v5_gate-paper-trade.py"
  # MIGRATION CANARY (2026-08-04): v5_kite = v5 + NSE_DATA_SOURCE=kite, one variable vs live v5.
  "v5_kite|scripts/v5_kite-paper-trade.py|docs/paper-trades/v5_kite/${TODAY}.json|python3 scripts/v5_kite-paper-trade.py"

  # SELECTIVITY SHADOW (2026-08-04): v5_pick = v5 + MIN_ENTRY_SCORE=70.
  "v5_pick|scripts/v5_pick-paper-trade.py|docs/paper-trades/v5_pick/${TODAY}.json|python3 scripts/v5_pick-paper-trade.py"

  # DEPLOYMENT SHADOW (2026-08-04): v5_deploy = v5 + POOL_ALLOC INTRADAY 60 / SWING 40.
  "v5_deploy|scripts/v5_deploy-paper-trade.py|docs/paper-trades/v5_deploy/${TODAY}.json|python3 scripts/v5_deploy-paper-trade.py"
  # V8 (TP-V8 2026-07-06): April-recipe replica (control twin).
  # RETIRED 2026-07-30, superseded by v10 (see launch-market.sh ENGINES for why).
  # "v8|scripts/v8-paper-trade.py|docs/paper-trades/v8/${TODAY}.json|python3 scripts/v8-paper-trade.py"
  # V10 (2026-07-30): frozen April engine, vendored from git 9d7db34.
  "v10|scripts/v10-paper-trade.py|docs/paper-trades/v10/${TODAY}.json|python3 scripts/v10-paper-trade.py"
  "v5_1L|scripts/v5_1L-paper-trade.py|docs/paper-trades/v5_1L/${TODAY}.json|python3 scripts/v5_1L-paper-trade.py"
  "v5_cut_1L|scripts/v5_cut_1L-paper-trade.py|docs/paper-trades/v5_cut_1L/${TODAY}.json|python3 scripts/v5_cut_1L-paper-trade.py"
  "v5_long_1L|scripts/v5_long_1L-paper-trade.py|docs/paper-trades/v5_long_1L/${TODAY}.json|python3 scripts/v5_long_1L-paper-trade.py"
  # Small-capital shadows (2026-08-03) — Rs 10,000 variants.
  # Retired 2026-05-15 (Sprint 1) — re-enable here AND in launch-market.sh together (~2026-07-15):
  # "v5_6|scripts/v5_6-paper-trade.py|docs/paper-trades/v5_6/${TODAY}.json|python3 scripts/v5_6-paper-trade.py"
  # "v5_7|scripts/v5_7-paper-trade.py|docs/paper-trades/v5_7/${TODAY}.json|python3 scripts/v5_7-paper-trade.py"
  # "v6|scripts/v6-paper-trade.py|docs/paper-trades/v6/${TODAY}.json|python3 scripts/v6-paper-trade.py"
  # "v5_8|scripts/v5_8-paper-trade.py|docs/paper-trades/v5_8/${TODAY}.json|python3 scripts/v5_8-paper-trade.py"
  # Still retired (uncomment if re-enabled in launch-market.sh):
  # "v5_3|scripts/v5_3-paper-trade.py|docs/paper-trades/v5_3/${TODAY}.json|python3 scripts/v5_3-paper-trade.py"
)
# v5_2 still retired — F&O engine that exits intentionally.

EOD_EXIT_WHITELIST=()

# ------- Telegram -------
send_alert() {
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
        --max-time 5 > /dev/null 2>&1
    fi
  fi
}

now_min() {
  # Force base-10 to avoid "08/09 = invalid octal" bug
  echo $((10#$(date +%H) * 60 + 10#$(date +%M)))
}

in_market_hours() {
  local nm=$(now_min)
  [ "$nm" -ge "$MARKET_OPEN_MIN" ] && [ "$nm" -le "$MARKET_CLOSE_MIN" ]
}

past_eod_cutoff() {
  [ "$(now_min)" -ge "$EOD_CUTOFF_MIN" ]
}

is_whitelisted_eod() {
  local name="$1"
  # bash 3.2 (macOS default) aborts on "${arr[@]}" for an empty array under
  # `set -u`. Guard explicitly — ${#arr[@]} is safe; element expansion is not.
  [ "${#EOD_EXIT_WHITELIST[@]}" -eq 0 ] && return 1
  for w in "${EOD_EXIT_WHITELIST[@]}"; do
    [ "$w" = "$name" ] && return 0
  done
  return 1
}

# Returns 0 if engine is alive, 1 otherwise.
# Primary check: is the exact script path running as a python3 process?
# Fallback: has its heartbeat file been updated in the last N seconds?
# (This catches case where process is running but wedged — rare but possible)
is_alive() {
  local script_path="$1"
  local hb_file="$2"

  # Primary: process existence by exact script path match (no self-match risk
  # because watchdog's own script is "scripts/crash-watchdog.sh", never "paper-trade.py")
  if pgrep -f "$script_path" > /dev/null 2>&1; then
    return 0
  fi

  # Fallback: fresh heartbeat file (engine may be between scans)
  if [ -f "$hb_file" ]; then
    local mtime
    local now_ts
    mtime=$(stat -f "%m" "$hb_file" 2>/dev/null || echo 0)
    now_ts=$(date +%s)
    local age=$((now_ts - mtime))
    [ "$age" -lt "$HEARTBEAT_MAX_AGE_SEC" ] && return 0
  fi

  return 1
}

# First-pass grace period — engines need time to warm up on morning start
FIRST_SCAN_DONE=false
GRACE_UNTIL_MIN=$((9 * 60 + 20))  # no restart alerts before 09:20

echo "[$(date '+%H:%M:%S')] crash-watchdog v3 started (heartbeat-based, market hours 09:00–15:30 IST)"
send_alert "🐕 Watchdog v3 online. Heartbeat-based. Will monitor 12 engines 09:00–15:30 IST."

while true; do
  if ! in_market_hours; then
    sleep 60
    continue
  fi

  # Grace period — let engines start up without spamming alerts
  if [ "$(now_min)" -lt "$GRACE_UNTIL_MIN" ]; then
    sleep 60
    continue
  fi

  for entry in "${ENGINES[@]}"; do
    IFS='|' read -r name script_path hb_file cmd <<< "$entry"

    if is_alive "$script_path" "$hb_file"; then
      continue
    fi

    # Not alive — check if this is expected EOD exit
    if is_whitelisted_eod "$name" && past_eod_cutoff; then
      continue
    fi

    # Genuine crash during market hours — restart
    echo "[$(date '+%H:%M:%S')] CRASH: $name process gone + heartbeat stale — restarting"
    send_alert "🚨 $name crashed — restarting"
    nohup $cmd > "/tmp/${name}.log" 2>&1 &
    sleep 3
  done

  sleep 60
done
