# Tomorrow Morning Checklist (Apr 8, 2026)

## Before Market Open (9:00 AM)

### 1. Wire data_providers.py into app.py
Replace direct yfinance calls with waterfall fallback:
- `/api/indices` → use `get_index_quote("NIFTY")` and `get_index_quote("SENSEX")`
- `/api/stock/<symbol>/history` → use `get_history()`
- Live quote fetches → use `get_quote()`

### 2. Start Paper Trading
```bash
cd ~/Documents/tinker/projects/tradepilot
./scripts/run-tomorrow.sh
```

### 3. Remaining UI Bugs
- Stock detail modal chart: verify it renders on click
- Gainers tab: verify it loads (first load takes ~40s)
- Market Pulse in Intel panel: fix content switching

### 4. Algorithm Validation
- Intraday captures run automatically at 09:30, 11:30, 13:30, 15:30
- v2 vs v3 comparison runs at 15:30 and 16:00
- Paper trading: 3 portfolios x Rs 5L each

## Data Provider Status
- NSE Direct: WORKING (real-time, fastest)
- BSE API: WORKING (for SENSEX)
- yfinance: SLOW (works but times out at night)
- Google Finance: Available as backup
- Local CSV: Always works (last known prices)
