"""
Scrape NIFTY 50 stock data from yfinance, compute technical indicators.
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math
import json
import os

# Index symbols for NIFTY and BANKNIFTY
INDEX_SYMBOLS = {
    "NIFTY50": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}

# ═══ STOCK UNIVERSE — imported from stock_universe.py ═══
from stock_universe import (
    NIFTY_50, NIFTY_NEXT_50, NIFTY_100, NIFTY_200, NIFTY_500,
    BSE_SENSEX_30, NIFTY_BANK, NIFTY_IT, NIFTY_PHARMA, NIFTY_AUTO,
    NIFTY_FMCG, NIFTY_METAL, NIFTY_ENERGY, NIFTY_REALTY, NIFTY_INFRA,
    ALL_NSE, get_stocks_by_tier,
)

# Popular mid-cap stocks (high beginner interest, affordable prices)
MIDCAP_POPULAR = [
    "TATACHEM.NS", "VOLTAS.NS", "PAGEIND.NS", "OFSS.NS", "ASTRAL.NS",
    "NYKAA.NS", "PAYTM.NS", "POLICYBZR.NS", "DELHIVERY.NS", "MAPMYINDIA.NS",
    "DEEPAKNTR.NS", "NAVINFLUOR.NS", "ATUL.NS", "AUROPHARMA.NS", "MANAPPURAM.NS",
    "LTTS.NS", "MPHASIS.NS", "MINDTREE.NS", "LTIM.NS", "CROMPTON.NS",
    "PRESTIGE.NS", "OBEROIRLTY.NS", "PHOENIXLTD.NS", "SUNDARMFIN.NS", "KALYANKJIL.NS",
    "TATAINVEST.NS", "NHPC.NS", "SJVN.NS", "IREDA.NS", "CESC.NS",
    "IDBI.NS", "CENTRALBK.NS", "INDIANB.NS", "MAHABANK.NS", "UNIONBANK.NS",
    "SUZLON.NS", "TATAELXSI.NS", "SONACOMS.NS", "SOLARINDS.NS", "JUBLFOOD.NS",
    "MRF.NS", "CONCOR.NS", "ACC.NS", "BIOCON.NS", "IPCALAB.NS",
    "ABFRL.NS", "RAYBAN.NS", "METROPOLIS.NS", "KEI.NS", "RATNAMANI.NS",
]

# Affordable stocks for beginners (price typically under Rs 500)
BEGINNER_FRIENDLY = [
    "IDEA.NS", "YESBANK.NS", "SUZLON.NS", "IRFC.NS", "NHPC.NS",
    "SJVN.NS", "IEX.NS", "TATAPOWER.NS", "PNB.NS", "CANBK.NS",
    "BANKBARODA.NS", "INDIANB.NS", "IOC.NS", "HINDPETRO.NS", "BPCL.NS",
    "SAIL.NS", "NMDC.NS", "NATIONALUM.NS", "COALINDIA.NS", "GAIL.NS",
    "BHEL.NS", "BEL.NS", "HAL.NS", "IREDA.NS", "ZOMATO.NS",
    "PAYTM.NS", "NYKAA.NS", "ITC.NS", "SBIN.NS", "TATASTEEL.NS",
    "HINDALCO.NS", "VEDL.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS",
    "RECLTD.NS", "PFC.NS", "MANAPPURAM.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS",
]

# BSE-only popular stocks (use .BO suffix)
BSE_POPULAR = [
    "ADANIGREEN.BO", "ADANIENSOL.BO", "ADANITRANS.BO",
    "ATGL.BO", "AWL.BO", "JSWENERGY.BO", "JINDALSTEL.BO",
    "LLOYDSME.BO", "MAZDOCK.BO", "COCHINSHIP.BO",
]

# Combined universe (deduplicated) — NIFTY 500 + midcap + beginner + BSE
ALL_STOCKS = list(dict.fromkeys(NIFTY_500 + MIDCAP_POPULAR + BEGINNER_FRIENDLY + BSE_POPULAR))

# Backward compatibility
NIFTY_STOCKS = ALL_STOCKS

# Stock categories for the UI
STOCK_CATEGORIES = {
    "nifty50": {"name": "NIFTY 50", "desc": "Top 50 large-cap", "stocks": NIFTY_50},
    "nifty100": {"name": "NIFTY 100", "desc": "Top 100 stocks", "stocks": NIFTY_100},
    "nifty200": {"name": "NIFTY 200", "desc": "Top 200 stocks", "stocks": NIFTY_200},
    "nifty500": {"name": "NIFTY 500", "desc": "Top 500 (94% market cap)", "stocks": NIFTY_500},
    "midcap": {"name": "Mid Cap", "desc": "Popular mid-caps", "stocks": MIDCAP_POPULAR},
    "beginner": {"name": "Beginner Picks", "desc": "Affordable stocks under Rs 500", "stocks": BEGINNER_FRIENDLY},
    "bank": {"name": "NIFTY Bank", "desc": "Banking sector", "stocks": NIFTY_BANK},
    "it": {"name": "NIFTY IT", "desc": "IT sector", "stocks": NIFTY_IT},
    "pharma": {"name": "NIFTY Pharma", "desc": "Pharma sector", "stocks": NIFTY_PHARMA},
    "auto": {"name": "NIFTY Auto", "desc": "Auto sector", "stocks": NIFTY_AUTO},
    "energy": {"name": "NIFTY Energy", "desc": "Energy sector", "stocks": NIFTY_ENERGY},
    "metal": {"name": "NIFTY Metal", "desc": "Metal sector", "stocks": NIFTY_METAL},
    "fmcg": {"name": "NIFTY FMCG", "desc": "FMCG sector", "stocks": NIFTY_FMCG},
    "realty": {"name": "NIFTY Realty", "desc": "Real estate", "stocks": NIFTY_REALTY},
    "all": {"name": "All Stocks", "desc": "Full universe (~500+ stocks)", "stocks": ALL_STOCKS},
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def download_stock_data(symbols=None, period="2y"):
    """Download historical OHLCV data for stocks."""
    ensure_data_dir()
    symbols = symbols or NIFTY_STOCKS
    all_data = {}

    print(f"Downloading data for {len(symbols)} stocks...")
    for i, symbol in enumerate(symbols):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval="1d")
            if len(df) > 50:  # need enough data for indicators
                df.index = df.index.tz_localize(None)  # remove timezone
                all_data[symbol] = df
                print(f"  [{i+1}/{len(symbols)}] {symbol}: {len(df)} days")
            else:
                print(f"  [{i+1}/{len(symbols)}] {symbol}: SKIPPED (only {len(df)} days)")
        except Exception as e:
            print(f"  [{i+1}/{len(symbols)}] {symbol}: ERROR - {e}")

    # Save to parquet
    for symbol, df in all_data.items():
        safe_name = symbol.replace(".", "_").replace("&", "_")
        df.to_csv(os.path.join(DATA_DIR, f"{safe_name}.csv"))

    print(f"Downloaded {len(all_data)} stocks successfully")
    return all_data


def load_stock_data(symbol):
    """Load saved stock data."""
    safe_name = symbol.replace(".", "_").replace("&", "_")
    path = os.path.join(DATA_DIR, f"{safe_name}.csv")
    if os.path.exists(path):
        return pd.read_csv(path, index_col=0, parse_dates=True)
    return None


def load_all_stock_data():
    """Load all saved stock data."""
    ensure_data_dir()
    all_data = {}
    for f in os.listdir(DATA_DIR):
        if f.endswith(".csv"):
            symbol = f.replace(".csv", "").replace("_NS", ".NS").replace("M_M", "M&M")
            df = pd.read_csv(os.path.join(DATA_DIR, f), index_col=0, parse_dates=True)
            all_data[symbol] = df
    return all_data


def compute_indicators(df):
    """Compute technical indicators for a stock DataFrame."""
    df = df.copy()
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # RSI (14)
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    df["rsi_14"] = 100 - (100 / (1 + rs))

    # MACD
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # Moving Averages
    df["sma_20"] = close.rolling(20).mean()
    df["sma_50"] = close.rolling(50).mean()
    df["sma_200"] = close.rolling(min(200, len(close) - 1)).mean()
    df["ema_9"] = close.ewm(span=9, adjust=False).mean()
    df["ema_21"] = close.ewm(span=21, adjust=False).mean()

    # ATR (14)
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(14).mean()

    # Bollinger Bands
    df["bb_mid"] = df["sma_20"]
    df["bb_std"] = close.rolling(20).std()
    df["bb_upper"] = df["bb_mid"] + 2 * df["bb_std"]
    df["bb_lower"] = df["bb_mid"] - 2 * df["bb_std"]
    df["bb_pct"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    # Volume indicators
    df["volume_sma_20"] = volume.rolling(20).mean()
    df["volume_ratio"] = volume / df["volume_sma_20"].replace(0, np.nan)

    # OBV
    obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
    df["obv"] = obv

    # Price position (% from 52-week high/low)
    lookback_52w = min(252, len(high) - 1)
    df["high_52w"] = high.rolling(lookback_52w).max()
    df["low_52w"] = low.rolling(lookback_52w).min()
    df["pct_from_high"] = (close - df["high_52w"]) / df["high_52w"] * 100
    df["pct_from_low"] = (close - df["low_52w"]) / df["low_52w"] * 100

    # Daily returns
    df["return_1d"] = close.pct_change()
    df["return_5d"] = close.pct_change(5)
    df["return_10d"] = close.pct_change(10)

    # Volatility
    df["volatility_20d"] = df["return_1d"].rolling(20).std() * np.sqrt(252) * 100

    # ADX (simplified)
    plus_dm = high.diff()
    minus_dm = -low.diff()
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)
    atr_smooth = tr.rolling(14).mean()
    plus_di = 100 * (plus_dm.rolling(14).mean() / atr_smooth.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(14).mean() / atr_smooth.replace(0, np.nan))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    df["adx"] = dx.rolling(14).mean()

    return df


def get_live_quotes(symbols=None):
    """Get current live quotes for stocks."""
    symbols = symbols or NIFTY_STOCKS
    quotes = []

    for symbol in symbols:
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            hist = ticker.history(period="2d")

            if len(hist) >= 2:
                current = hist.iloc[-1]
                prev = hist.iloc[-2]
                change = current["Close"] - prev["Close"]
                change_pct = (change / prev["Close"]) * 100

                quotes.append({
                    "symbol": symbol,
                    "name": symbol.replace(".NS", ""),
                    "price": round(current["Close"], 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                    "open": round(current["Open"], 2),
                    "high": round(current["High"], 2),
                    "low": round(current["Low"], 2),
                    "volume": int(current["Volume"]),
                    "prev_close": round(prev["Close"], 2),
                })
        except Exception as e:
            pass

    return quotes


def get_market_indices():
    """Get NIFTY 50 and SENSEX indices."""
    indices = []
    for idx_symbol, idx_name in [("^NSEI", "NIFTY 50"), ("^BSESN", "SENSEX")]:
        try:
            ticker = yf.Ticker(idx_symbol)
            hist = ticker.history(period="2d")
            if len(hist) >= 2:
                current = hist.iloc[-1]
                prev = hist.iloc[-2]
                change = current["Close"] - prev["Close"]
                change_pct = (change / prev["Close"]) * 100
                indices.append({
                    "name": idx_name,
                    "value": round(current["Close"], 2),
                    "change": round(change, 2),
                    "change_pct": round(change_pct, 2),
                })
        except:
            pass
    return indices


def get_index_data(index_symbol, period="1d", interval="5m"):
    """Get intraday/historical data for NIFTY/BANKNIFTY indices."""
    ticker = yf.Ticker(index_symbol)
    df = ticker.history(period=period, interval=interval)
    df.index = df.index.tz_localize(None)
    return df


def get_options_chain_data(index_name):
    """Get simulated options chain for NIFTY/BANKNIFTY.
    Since yfinance doesn't have NSE options, we simulate using index price + Black-Scholes-like estimates.
    """
    symbol = INDEX_SYMBOLS.get(index_name)
    if not symbol:
        return None

    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="2d")
    if len(hist) < 1:
        return None

    current_price = float(hist.iloc[-1]["Close"])
    prev_close = float(hist.iloc[-2]["Close"]) if len(hist) > 1 else current_price

    # Generate strike prices around current price
    # NIFTY: strike interval = 50, BANKNIFTY: strike interval = 100
    strike_interval = 100 if "BANK" in index_name else 50
    atm_strike = round(current_price / strike_interval) * strike_interval

    strikes = []
    for i in range(-10, 11):  # 21 strikes around ATM
        strike = atm_strike + (i * strike_interval)
        diff = current_price - strike

        # Simplified option pricing (not real Black-Scholes, but gives realistic-looking data)
        days_to_expiry = 7  # weekly expiry
        volatility = 0.15

        # Intrinsic value
        ce_intrinsic = max(0, current_price - strike)
        pe_intrinsic = max(0, strike - current_price)

        # Time value (simplified)
        time_value = current_price * volatility * math.sqrt(days_to_expiry / 365) * 0.4
        time_decay = max(0, time_value * (1 - abs(i) * 0.08))  # decay away from ATM

        ce_price = round(ce_intrinsic + time_decay + np.random.uniform(0.5, 3), 2)
        pe_price = round(pe_intrinsic + time_decay + np.random.uniform(0.5, 3), 2)

        # Simulated OI and volume
        oi_base = 50000 - abs(i) * 3000
        ce_oi = max(1000, int(oi_base + np.random.randint(-5000, 5000)))
        pe_oi = max(1000, int(oi_base + np.random.randint(-5000, 5000)))
        ce_vol = max(100, int(ce_oi * np.random.uniform(0.05, 0.3)))
        pe_vol = max(100, int(pe_oi * np.random.uniform(0.05, 0.3)))

        # Change from previous
        ce_change = round(np.random.uniform(-15, 15), 2)
        pe_change = round(np.random.uniform(-15, 15), 2)

        # Greeks (simplified)
        delta_ce = round(max(0, min(1, 0.5 + (diff / (current_price * 0.05)))), 3)
        delta_pe = round(delta_ce - 1, 3)
        iv = round(volatility * 100 * (1 + abs(i) * 0.02) + np.random.uniform(-2, 2), 1)

        strikes.append({
            "strike": strike,
            "isATM": i == 0,
            "isITM_CE": strike < current_price,
            "isITM_PE": strike > current_price,
            "ce": {
                "price": ce_price,
                "change": ce_change,
                "changePct": round(ce_change / max(ce_price, 1) * 100, 2),
                "oi": ce_oi,
                "volume": ce_vol,
                "iv": iv,
                "delta": delta_ce,
                "theta": round(-time_decay / days_to_expiry, 2),
                "gamma": round(0.01 / (1 + abs(i) * 0.3), 4),
                "vega": round(time_decay * 0.1, 2),
            },
            "pe": {
                "price": pe_price,
                "change": pe_change,
                "changePct": round(pe_change / max(pe_price, 1) * 100, 2),
                "oi": pe_oi,
                "volume": pe_vol,
                "iv": iv,
                "delta": delta_pe,
                "theta": round(-time_decay / days_to_expiry, 2),
                "gamma": round(0.01 / (1 + abs(i) * 0.3), 4),
                "vega": round(time_decay * 0.1, 2),
            },
        })

    # Calculate next Thursday for expiry
    from datetime import datetime
    today = datetime.now()
    days_until_thursday = (3 - today.weekday()) % 7
    if days_until_thursday == 0:
        days_until_thursday = 7
    next_thursday = today + timedelta(days=days_until_thursday)
    expiry_date = next_thursday.strftime("%Y-%m-%d")

    return {
        "index": index_name,
        "spotPrice": round(current_price, 2),
        "prevClose": round(prev_close, 2),
        "change": round(current_price - prev_close, 2),
        "changePct": round((current_price - prev_close) / prev_close * 100, 2),
        "atmStrike": atm_strike,
        "expiryDate": expiry_date,
        "strikes": strikes,
    }


if __name__ == "__main__":
    print("=== TradePilot Data Engine ===")
    data = download_stock_data()

    # Compute indicators for all
    for symbol, df in data.items():
        df_ind = compute_indicators(df)
        safe_name = symbol.replace(".", "_").replace("&", "_")
        df_ind.to_csv(os.path.join(DATA_DIR, f"{safe_name}.csv"))

    print(f"\nData + indicators saved for {len(data)} stocks")
