#!/bin/bash
# EOD driver for the 2026-09-08 shadow experiments + the left-on-table report. Run after 15:20.
#   ./scripts/eod-experiments.sh [date]
set -u; cd "$(dirname "$0")/.."; D=${1:-$(date +%F)}; S=/tmp/tp-eod-$D; mkdir -p "$S" docs/watchdog/reports/${D}_eod
echo "[1/5] candle replay"; python3 scripts/eod-replay-candles.py "$S/replay.json" "$D" v5,v5_wide 2>&1 | grep -E "^v5"
cp "$S/replay.json" docs/watchdog/reports/${D}_eod/left-on-table.json
echo "[2/5] arm-band shadow"; python3 scripts/shadow-armband.py "$D" v5,v5_wide "$S/replay.json" 2>&1 | grep -vE "delisted|Failed" | tail -3
echo "[3/5] regime shadow"; python3 scripts/shadow-regime-eod.py "$D" v5 "$S/replay.json" 2>&1 | grep -vE "delisted|Failed" | tail -1
echo "[4/5] DAYGAIN baseline"; python3 scripts/daygain-baseline.py eod "$D" 2>&1 | grep -vE "delisted|Failed" | tail -1
echo "[5/5] missed calls + report"; python3 scripts/missed-trades-report.py "$D" > "$S/missed.out" 2>&1; tail -1 "$S/missed.out"
echo "now: python3 scripts/eod-left-on-table.py $D $S/replay.json <notes.json>"
