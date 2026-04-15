#!/bin/bash
# TradePilot Full Day Runner -- Apr 8, 2026
# Runs validation captures + paper trading engine in parallel
#
# Usage: ./scripts/run-tomorrow.sh
# Start before 9:15 AM IST

cd "$(dirname "$0")/.."
mkdir -p logs

echo "=== TradePilot Full Day Runner ==="
echo "Starting at $(date '+%H:%M IST')"

# 1. Start Flask server if not running
if ! curl -s http://localhost:5050/api/model > /dev/null 2>&1; then
    echo "Starting Flask server..."
    cd prototype && nohup python3 app.py > ../logs/flask-server.log 2>&1 &
    sleep 5
    cd ..
fi

# 2. Start intraday capture daemon (v2 scores)
echo "Starting intraday capture daemon..."
nohup python3 scripts/intraday-capture.py --daemon > logs/intraday-capture.log 2>&1 &

# 3. Start autonomous monitor (v2 vs v3 comparisons + EOD report)
echo "Starting autonomous monitor..."
nohup python3 scripts/autonomous-monitor.py > logs/autonomous-monitor.log 2>&1 &

# 4. Start paper trading engine (3 portfolios)
echo "Starting paper trading engine..."
nohup python3 scripts/paper-trade-engine.py > logs/paper-trade.log 2>&1 &

echo ""
echo "All systems launched:"
echo "  Flask server:     http://localhost:5050"
echo "  Intraday daemon:  captures at 09:30, 11:30, 13:30, 15:30"
echo "  Autonomous monitor: v2 vs v3 comparisons + EOD report"
echo "  Paper trading:    3 portfolios x Rs 5,00,000 each"
echo ""
echo "Check status:"
echo "  python3 scripts/paper-trade-engine.py --status"
echo "  python3 scripts/paper-trade-engine.py --summary"
echo "  cat logs/paper-trade.log"
echo "  cat logs/autonomous-monitor.log"
