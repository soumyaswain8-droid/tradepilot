#!/bin/bash
# TradePilot ML Model Retrain
# Run weekly (or before market open) to incorporate new data
#
# Usage: ./scripts/retrain-ml.sh

cd "$(dirname "$0")/.."
mkdir -p logs

echo "=== TradePilot ML Retrain ==="
echo "$(date '+%Y-%m-%d %H:%M IST')"

# Step 1: Refresh data
echo "[1/2] Refreshing market data..."
python3 -c "
import yfinance as yf
import pandas as pd
from pathlib import Path
from prototype.v4.config import NIFTY_50_YF, NIFTY_50_SYMBOLS

DATA_DIR = Path('prototype/data')
INTRA_DIR = DATA_DIR / 'intraday'

# Daily OHLCV
data = yf.download(NIFTY_50_YF + ['^NSEI', '^INDIAVIX'], period='2y', auto_adjust=False, threads=True, progress=False)
if hasattr(data.columns, 'levels') and len(data.columns.levels) > 1:
    for sym_yf, sym in zip(NIFTY_50_YF, NIFTY_50_SYMBOLS):
        try:
            stock = data.xs(sym_yf, level=1, axis=1)
            stock.to_csv(DATA_DIR / f'{sym}_NS.csv')
        except: pass
    for idx in ['^NSEI', '^INDIAVIX']:
        try:
            d = data.xs(idx, level=1, axis=1)
            d.to_csv(DATA_DIR / f'{idx}.csv')
        except: pass

# 5-min intraday
for sym_yf, sym in zip(NIFTY_50_YF, NIFTY_50_SYMBOLS):
    try:
        df = yf.download(sym_yf, period='60d', interval='5m', progress=False)
        if hasattr(df.columns, 'droplevel') and isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        if len(df) > 0:
            df = df.reset_index()
            if 'Datetime' in df.columns: df = df.rename(columns={'Datetime': 'Date'})
            df.to_csv(INTRA_DIR / f'{sym}_5m.csv', index=False)
    except: pass
print('Data refreshed')
" 2>&1
echo "  Done"

# Step 2: Retrain
echo "[2/2] Training ML model..."
python3 -m prototype.v4.ml_engine --train 2>&1 | tee logs/ml-retrain.log | tail -15

echo ""
echo "Retrain complete. Check: python3 -m prototype.v4.ml_engine --info"
