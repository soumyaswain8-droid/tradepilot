#!/bin/bash
# Battle-ready check — verifies battle components are ready after laptop restart.

set -u
ROOT="/Users/soumyaswain/Documents/tinker/projects/tradepilot"
cd "$ROOT"

PASS=0
FAIL=0

chk() {
  if [ -e "$2" ]; then
    echo "  OK    $1"
    PASS=$((PASS+1))
  else
    echo "  MISS  $1 -- $2"
    FAIL=$((FAIL+1))
  fi
}

chk_env() {
  if grep -q "^$1=" .env 2>/dev/null; then
    echo "  OK    .env $1"
    PASS=$((PASS+1))
  else
    echo "  MISS  .env $1"
    FAIL=$((FAIL+1))
  fi
}

echo "========================================="
echo "  BATTLE-READY CHECK -- $(date '+%Y-%m-%d %H:%M')"
echo "========================================="
echo ""
echo "[launchers]"
chk "launch-market.sh"    "scripts/launch-market.sh"
chk "crash-watchdog.sh"   "scripts/crash-watchdog.sh"
chk "telegram-digest.sh"  "scripts/telegram-digest.sh"
chk "laptop-heartbeat.sh" "scripts/laptop-heartbeat.sh"
chk "auto-stop-eod.sh"    "scripts/auto-stop-eod.sh"
chk "satish-schedule.sh"  "scripts/satish-schedule.sh"
chk "sanity-check.sh"     "scripts/sanity-check.sh"
echo ""
echo "[engines]"
for eng in v4 v5 v5_classic v5_2 v5_3 v5_6 v5_7; do
  chk "${eng}"  "scripts/${eng}-paper-trade.py"
done
echo ""
echo "[python utilities]"
chk "satish-digest.py"       "scripts/satish-digest.py"
chk "eod-insights.py"        "scripts/eod-insights.py"
chk "status-digest.py"       "scripts/status-digest.py"
chk "classify-universe.py"   "scripts/classify-universe.py"
chk "train-tiered-models.py" "scripts/train-tiered-models.py"
echo ""
echo "[rust engine]"
chk "Rust source (main)"    "engine/src/main.rs"
chk "Rust source (risk)"    "engine/src/risk/mod.rs"
chk "Rust release binary"   "engine/target/release/tradepilot-engine"
echo ""
echo "[ML models]"
chk "production model"      "prototype/v4/models/lgbm_intraday.txt"
chk "production meta"       "prototype/v4/models/lgbm_meta.json"
chk "elite tier"            "prototype/v4/models/tiered/elite_lgbm.txt"
chk "large_cap tier"        "prototype/v4/models/tiered/large_cap_lgbm.txt"
chk "mid_cap tier"          "prototype/v4/models/tiered/mid_cap_lgbm.txt"
chk "broad tier"            "prototype/v4/models/tiered/broad_lgbm.txt"
chk "today's archive"       "prototype/v4/models/archive/2026-04-21/"
chk "rollback archive"      "prototype/v4/models/archive/2026-04-20-pre-fix/"
echo ""
echo "[config and infra]"
chk ".env"                  ".env"
chk "tiers.json"            "prototype/v4/config/tiers.json"
chk "Flask app"             "prototype/app.py"
chk "rust_bridge.py"        "prototype/v5/rust_bridge.py"
chk "signal_guards.py"      "prototype/utils/signal_guards.py"
echo ""
echo "[env vars]"
chk_env "TELEGRAM_BOT_TOKEN"
chk_env "TELEGRAM_CHAT_ID"
chk_env "RUST_MAX_TOTAL_POSITIONS"
chk_env "RUST_MAX_POSITIONS_PER_SYMBOL"
chk_env "RUST_MAX_DAILY_LOSS"
if grep -q "^SATISH_TELEGRAM_CHAT_ID=[0-9]" .env 2>/dev/null; then
  echo "  OK    .env SATISH_TELEGRAM_CHAT_ID set"
else
  echo "  NOTE  SATISH_TELEGRAM_CHAT_ID not set (Satish msgs will fall back to Soumya)"
fi
echo ""
echo "[data]"
CSV_COUNT=$(ls prototype/data/*.csv 2>/dev/null | wc -l | tr -d ' ')
echo "  CSVs: $CSV_COUNT (need >= 2000)"
if [ "$CSV_COUNT" -ge 2000 ]; then PASS=$((PASS+1)); else FAIL=$((FAIL+1)); fi
echo ""
echo "[smoke tests]"
python3 -c "from prototype.v4 import ml_engine" 2>/dev/null && { echo "  OK    ml_engine imports"; PASS=$((PASS+1)); } || { echo "  FAIL  ml_engine"; FAIL=$((FAIL+1)); }
python3 -c "from prototype.v5 import rust_bridge" 2>/dev/null && { echo "  OK    rust_bridge imports"; PASS=$((PASS+1)); } || { echo "  FAIL  rust_bridge"; FAIL=$((FAIL+1)); }
python3 -c "from prototype.v4 import tiered_scorer" 2>/dev/null && { echo "  OK    tiered_scorer imports"; PASS=$((PASS+1)); } || { echo "  FAIL  tiered_scorer"; FAIL=$((FAIL+1)); }
echo ""
echo "========================================="
echo "  Passed: $PASS   Failed: $FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "  STATUS: BATTLE READY"
  echo ""
  echo "  Next: ./scripts/launch-market.sh"
  exit 0
else
  echo "  STATUS: NOT READY -- fix above"
  exit 1
fi
