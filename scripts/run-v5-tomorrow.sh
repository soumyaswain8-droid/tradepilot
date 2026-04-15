#!/bin/bash
# TradePilot v5 Full Day Runner (Multi-Horizon + Regime-Aware)
# Start BEFORE 9:15 AM IST
#
# Runs v5 ALONGSIDE v4 for comparison
# Usage: ./scripts/run-v5-tomorrow.sh

cd "$(dirname "$0")/.."
mkdir -p logs docs/paper-trades/v5

echo "╔══════════════════════════════════════════════════════╗"
echo "║  TradePilot v5 — Multi-Horizon Regime-Aware Engine  ║"
echo "║  Starting at $(date '+%H:%M IST')                            ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# 0. Refresh market data
echo "[0/7] Refreshing market data..."
python3 -c "
import yfinance as yf
import pandas as pd
from pathlib import Path
from prototype.v4.config import NIFTY_50_YF, NIFTY_50_SYMBOLS

DATA_DIR = Path('prototype/data')
INTRA_DIR = DATA_DIR / 'intraday'
INTRA_DIR.mkdir(exist_ok=True)

# Daily + index + VIX
for idx in ['^NSEI', '^INDIAVIX']:
    d = yf.download(idx, period='2y', auto_adjust=False, progress=False)
    if hasattr(d.columns, 'droplevel') and isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.droplevel(1)
    d.to_csv(DATA_DIR / f'{idx}.csv')

# Batch stocks
data = yf.download(NIFTY_50_YF, period='2y', auto_adjust=False, threads=True, progress=False)
if hasattr(data.columns, 'levels') and len(data.columns.levels) > 1:
    for sym_yf, sym in zip(NIFTY_50_YF, NIFTY_50_SYMBOLS):
        try:
            stock = data.xs(sym_yf, level=1, axis=1)
            stock.to_csv(DATA_DIR / f'{sym}_NS.csv')
        except: pass

# 5-min intraday
count = 0
for sym_yf, sym in zip(NIFTY_50_YF, NIFTY_50_SYMBOLS):
    try:
        df = yf.download(sym_yf, period='60d', interval='5m', progress=False)
        if hasattr(df.columns, 'droplevel') and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if len(df) > 0:
            df = df.reset_index()
            if 'Datetime' in df.columns: df = df.rename(columns={'Datetime': 'Date'})
            df.to_csv(INTRA_DIR / f'{sym}_5m.csv', index=False)
            count += 1
    except: pass
print(f'Data refreshed: {count}/50 stocks')
" > logs/data-refresh.log 2>&1
echo "  Done (see logs/data-refresh.log)"

# 1. Retrain ML model
echo "[1/7] Retraining ML model..."
python3 -m prototype.v4.ml_engine --train > logs/ml-retrain.log 2>&1
echo "  Done (see logs/ml-retrain.log)"

# 2. Pre-market intelligence
echo "[2/7] Pre-market analysis..."
python3 -m prototype.v5.premarket_intel 2>/dev/null
echo ""

# 3. Regime detection
echo "[3/7] Regime detection..."
python3 -m prototype.v5.regime_detector 2>/dev/null
echo ""

# 4. Start Flask server
if ! curl -s http://localhost:5050/api/model > /dev/null 2>&1; then
    echo "[4/7] Starting Flask server..."
    cd prototype && nohup python3 app.py > ../logs/flask-server.log 2>&1 &
    sleep 5
    cd ..
else
    echo "[4/7] Flask server already running"
fi

# 5. Start v4 paper trading (control group)
echo "[5/7] Starting v4 paper trading (Rs 10L, control)..."
nohup python3 scripts/v4-paper-trade.py > /dev/null 2>&1 &
echo "  v4 PID: $!"

# 6. Start v5 paper trading (test group)
echo "[6/7] Starting v5 paper trading (Rs 10L, multi-horizon)..."
nohup python3 scripts/v5-paper-trade.py > /dev/null 2>&1 &
echo "  v5 PID: $!"

# 7. Start v5.2 F&O Options Experiment (separate capital pool)
echo "[7/8] Starting v5.2 F&O options experiment (Rs 10L, options)..."
mkdir -p docs/paper-trades/v5_2
nohup python3 scripts/v5_2-paper-trade.py > logs/v5_2-paper-trade.log 2>&1 &
echo "  v5.2 PID: $!"

# 8. Start v5.3 Staged Entry Experiment
echo "[8/8] Starting v5.3 staged entry experiment (Rs 10L)..."
mkdir -p docs/paper-trades/v5_3
nohup python3 scripts/v5_3-paper-trade.py > logs/v5_3-paper-trade.log 2>&1 &
echo "  v5.3 PID: $!"

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  All 4 engines running in parallel                  ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  v4:   Rs 10L, composite scorer, long-only          ║"
echo "║  v5:   Rs 10L, 4 pools, longs+shorts, regime-aware  ║"
echo "║  v5.2: Rs 10L, F&O options, regime-driven           ║"
echo "║  v5.3: Rs 10L, 3-stage entry, conviction tiers      ║"
echo "║                                                      ║"
echo "║  v5.2 strategies:                                    ║"
echo "║    Protective Puts   → BEAR regime insurance         ║"
echo "║    Straddle Selling  → SIDEWAYS + expiry week        ║"
echo "║    Directional Opts  → high-confidence BULL/BEAR     ║"
echo "║    Covered Calls     → passive income on holdings    ║"
echo "║                                                      ║"
echo "║  v5.3 staged entry:                                  ║"
echo "║    Stage 1 (09:35)   → Tier 1 HIGH @ 50% size       ║"
echo "║    Stage 2 (10:15)   → ORB confirmation + Tier 2     ║"
echo "║    Stage 3 (11:30)   → Midday rescore + Tier 3       ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""
echo "Check status:"
echo "  python3 scripts/v4-paper-trade.py --status"
echo "  python3 scripts/v5-paper-trade.py --status"
echo "  python3 scripts/v5_2-paper-trade.py --status"
echo "  python3 scripts/v5_2-paper-trade.py --summary"
echo "  python3 scripts/v5_3-paper-trade.py --status"
echo "  python3 scripts/v5_3-paper-trade.py --summary"
echo "  python3 scripts/v5-paper-trade.py --compare"
echo "  python3 -m prototype.v5.regime_detector"
echo "  python3 -m prototype.v5_2.options_engine"
