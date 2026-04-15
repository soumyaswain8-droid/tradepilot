#!/bin/bash
# TradePilot v5.2 F&O Experiment Launcher
# Runs ALONGSIDE v4 + v5 — separate capital pool
#
# Usage: ./scripts/run-v5_2-tomorrow.sh

cd "$(dirname "$0")/.."
mkdir -p logs docs/paper-trades/v5_2

echo "╔══════════════════════════════════════════════════════╗"
echo "║  TradePilot v5.2 — F&O Options Experiment           ║"
echo "║  Starting at $(date '+%H:%M IST')                            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# 1. Show regime + VIX + option signals
echo "[1/2] Generating F&O signals..."
python3 -m prototype.v5_2.options_engine 2>/dev/null
echo ""

# 2. Start v5.2 paper trading
echo "[2/2] Starting v5.2 F&O paper trading (Rs 10L, options)..."
nohup python3 scripts/v5_2-paper-trade.py > logs/v5_2-paper-trade.log 2>&1 &
echo "  v5.2 PID: $!"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  v5.2 F&O engine running                            ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Capital:  Rs 10L (separate pool)                   ║"
echo "║  Strategies:                                         ║"
echo "║    Protective Puts   → BEAR regime insurance         ║"
echo "║    Straddle Selling  → SIDEWAYS + expiry week        ║"
echo "║    Directional Opts  → high-confidence BULL/BEAR     ║"
echo "║    Covered Calls     → passive income on holdings    ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Check status:"
echo "  python3 scripts/v5_2-paper-trade.py --status"
echo "  python3 scripts/v5_2-paper-trade.py --summary"
echo "  python3 -m prototype.v5_2.options_engine"
