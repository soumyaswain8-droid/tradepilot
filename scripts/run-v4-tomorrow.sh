#!/bin/bash
# TradePilot v4 Full Day Runner (with ML Engine)
# Start BEFORE 9:15 AM IST
#
# Usage: ./scripts/run-v4-tomorrow.sh

cd "$(dirname "$0")/.."
mkdir -p logs docs/paper-trades/v4 prototype/data/intraday

echo "=== TradePilot v4 Full Day Runner (ML-Powered) ==="
echo "Starting at $(date '+%H:%M IST')"
echo ""

# 0. Refresh market data (download latest daily + intraday candles)
echo "[0/5] Refreshing market data..."
python3 -c "
import yfinance as yf
import pandas as pd
from pathlib import Path
from prototype.v4.config import NIFTY_50_YF, NIFTY_50_SYMBOLS

DATA_DIR = Path('prototype/data')
INTRA_DIR = DATA_DIR / 'intraday'
INTRA_DIR.mkdir(exist_ok=True)

# Refresh daily OHLCV (2 years)
print('  Refreshing daily data...')
nifty = yf.download('^NSEI', period='2y', auto_adjust=False, progress=False)
if hasattr(nifty.columns, 'droplevel') and isinstance(nifty.columns, pd.MultiIndex):
    nifty.columns = nifty.columns.droplevel(1)
nifty.to_csv(DATA_DIR / '^NSEI.csv')

vix = yf.download('^INDIAVIX', period='2y', auto_adjust=False, progress=False)
if hasattr(vix.columns, 'droplevel') and isinstance(vix.columns, pd.MultiIndex):
    vix.columns = vix.columns.droplevel(1)
vix.to_csv(DATA_DIR / '^INDIAVIX.csv')

data = yf.download(NIFTY_50_YF, period='2y', auto_adjust=False, threads=True, progress=False)
if hasattr(data.columns, 'levels') and len(data.columns.levels) > 1:
    for sym_yf, sym in zip(NIFTY_50_YF, NIFTY_50_SYMBOLS):
        try:
            stock = data.xs(sym_yf, level=1, axis=1)
            stock.to_csv(DATA_DIR / f'{sym}_NS.csv')
        except:
            pass
print(f'  Daily: {len(nifty)} rows for Nifty, 50 stocks updated')

# Refresh 5-min intraday (60 days)
print('  Refreshing intraday candles...')
count = 0
for sym_yf, sym in zip(NIFTY_50_YF, NIFTY_50_SYMBOLS):
    try:
        df = yf.download(sym_yf, period='60d', interval='5m', progress=False)
        if hasattr(df.columns, 'droplevel') and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if len(df) > 0:
            df = df.reset_index()
            if 'Datetime' in df.columns:
                df = df.rename(columns={'Datetime': 'Date'})
            df.to_csv(INTRA_DIR / f'{sym}_5m.csv', index=False)
            count += 1
    except:
        pass
# Nifty index intraday
try:
    ni = yf.download('^NSEI', period='60d', interval='5m', progress=False)
    if hasattr(ni.columns, 'droplevel') and isinstance(ni.columns, pd.MultiIndex):
        ni.columns = ni.columns.droplevel(1)
    ni = ni.reset_index()
    if 'Datetime' in ni.columns:
        ni = ni.rename(columns={'Datetime': 'Date'})
    ni.to_csv(INTRA_DIR / 'NIFTY50_5m.csv', index=False)
except:
    pass
print(f'  Intraday: {count}/50 stocks updated (5-min candles)')
" > logs/data-refresh.log 2>&1
echo "  Data refresh complete (see logs/data-refresh.log)"

# 0b. Retrain ML model with fresh data
echo "[0b/5] Retraining ML model..."
python3 -m prototype.v4.ml_engine --train > logs/ml-retrain.log 2>&1
echo "  ML model retrained (see logs/ml-retrain.log)"

# 1. Start Flask server if not running
if ! curl -s http://localhost:5050/api/model > /dev/null 2>&1; then
    echo "[1/5] Starting Flask server (v4 engine)..."
    cd prototype && nohup python3 app.py > ../logs/flask-server.log 2>&1 &
    sleep 5
    cd ..
else
    echo "[1/5] Flask server already running"
fi

# 2. Start v4 paper trading engine (Rs 10L, v4 composite scorer + ML)
echo "[2/5] Starting v4 paper trading engine..."
nohup python3 scripts/v4-paper-trade.py > /dev/null 2>&1 &
echo "  PID: $!"

# 3. Start intraday capture daemon (validation snapshots)
echo "[3/5] Starting intraday capture daemon..."
nohup python3 scripts/intraday-capture.py --daemon > logs/intraday-capture.log 2>&1 &

# 4. Start autonomous monitor (v2 vs v3 comparison + EOD report)
echo "[4/5] Starting autonomous monitor..."
nohup python3 scripts/autonomous-monitor.py > logs/autonomous-monitor.log 2>&1 &

echo ""
echo "All systems launched:"
echo "  Data refresh:      Daily + 5-min intraday candles refreshed"
echo "  ML model:          LightGBM retrained with latest data"
echo "  Flask server:      http://localhost:5050 (v4 default)"
echo "  v4 Paper Trading:  Rs 10L pool, v4 composite + ML scorer"
echo "                     22 features (17 daily + 5 intraday)"
echo "                     10 BUY signals, Kelly-sized positions"
echo "                     Deploys at 9:35 AM, rescores every 30 min"
echo "                     Force exit at 3:15 PM"
echo "  Intraday capture:  09:30, 11:30, 13:30, 15:30"
echo "  Auto monitor:      v2 vs v3 EOD report"
echo ""
echo "Check status:"
echo "  python3 scripts/v4-paper-trade.py --status"
echo "  python3 scripts/v4-paper-trade.py --summary"
echo "  tail -f logs/v4-paper-trade.log"
echo "  python3 -m prototype.v4.ml_engine --info"
