# Open-Source Trading Algorithms & ML Research — 2026-04-08

## Top 10 GitHub Projects

| # | Project | Stars | What It Does |
|---|---------|-------|-------------|
| 1 | [machine-learning-for-trading](https://github.com/stefan-jansen/machine-learning-for-trading) | 17,009 | Complete ML trading cookbook (LightGBM, XGBoost, LSTM, RL, NLP) |
| 2 | [QuantConnect/Lean](https://github.com/quantconnect/Lean) | 18,288 | Industrial-grade algo trading engine |
| 3 | [FinRL](https://github.com/AI4Finance-Foundation/FinRL) | 14,698 | Reinforcement learning trading (PPO, A2C, DDPG) |
| 4 | [backtesting.py](https://github.com/kernc/backtesting.py) | 8,168 | Lightweight Python backtesting |
| 5 | [vectorbt](https://github.com/polakowo/vectorbt) | 7,107 | Vectorized fast backtesting |
| 6 | [mlfinlab](https://github.com/hudson-and-thames/mlfinlab) | 4,656 | Lopez de Prado's "Advances in Financial ML" |
| 7 | [OpenAlgo](https://github.com/marketcalls/openalgo) | 1,608 | Algo trading platform, 30+ Indian brokers |
| 8 | [jugaad-data](https://github.com/jugaad-py/jugaad-data) | 504 | Free NSE historical data |
| 9 | [PKScreener](https://github.com/pkjmesra/PKScreener) | 327 | NSE screener with AI prediction |
| 10 | [NSE-Stock-Scanner](https://github.com/deshwalmahesh/NSE-Stock-Scanner) | 300 | NSE screener + Zerodha integration |

### India-Specific
- [OpenChart](https://github.com/marketcalls/openchart) — free 1-min candle data NSE/NFO
- [nifty-banknifty-intraday-data](https://github.com/aeron7/nifty-banknifty-intraday-data) — pre-downloaded 1-min data
- [NIFTY50 Pairs Trading](https://github.com/arnavkohli/statistical-arbitrage-pairs-trading) — 4.97% return, 2.57% max DD

## 5 Proven Strategies

### 1. Opening Range Breakout (ORB)
- First 5-15 min high/low → trade breakout with volume
- Sharpe 2.396, outperformed buy-hold 68% of time
- Filter with VWAP confirmation + ATR stop

### 2. VWAP Mean Reversion / Trend
- Long above VWAP with volume, short below
- Sharpe 3.57, 501% return over 5 years, 16% max DD
- Close all EOD

### 3. Momentum Factor + Ranking
- Rank universe by 6-12mo momentum adjusted for volatility
- NSE Momentum 50 Index consistently beats Nifty 50
- Long top decile, rebalance monthly

### 4. Pairs Trading (Statistical Arbitrage)
- Cointegrated pairs in Nifty 50, trade spread mean reversion
- 4.97% annual, max DD 2.57%, market-neutral

### 5. ML-Enhanced (LightGBM)
- Predict 30-min direction, trade high-confidence (>0.6)
- LightGBM R-squared 2.13% monthly (2x OLS)
- Retrain weekly, walk-forward validation

## ML Model Consensus

- **LightGBM > LSTM** for stock prediction (faster, less data needed, interpretable)
- **Regression** for long-term, **Classification** for intraday direction
- **Walk-forward validation** is non-negotiable
- Top features: volatility (ATR), volume (OBV), momentum (RSI, MACD), VWAP deviation
- Retrain monthly, 6-12 month training window

## Free Training Data Sources

| Source | Data | History | Granularity |
|--------|------|---------|-------------|
| OpenChart | NSE + NFO OHLCV | ~5 years | 1-min candles |
| jugaad-data | NSE stock + index | 10+ years | Daily |
| DhanHQ API | NSE + NFO | 5 years | 1/5/15/60 min |
| yfinance | NSE (.NS) | 5+ years daily | Daily + 7 days 1-min |
| NSE website | FII/DII flows | Years | Daily |
