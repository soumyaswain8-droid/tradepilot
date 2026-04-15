"""
TradePilot Multi-Source Data Provider
=====================================
Waterfall fallback system for stock market data.

Priority:
  1. yfinance (default, free, 15-min delayed)
  2. NSE India direct API (real-time, unofficial)
  3. BSE India API (real-time, public REST)
  4. Google Finance scrape (15-min delayed)
  5. Local CSV cache (stale but always available)

Usage:
    from data_providers import get_quote, get_history, get_index_quote

    quote = get_quote("RELIANCE.NS")  # tries all sources
    history = get_history("TCS.NS", period="1m")
    nifty = get_index_quote("NIFTY")
"""
import json
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# Track which providers are healthy
_provider_status = {
    "yfinance": {"healthy": True, "last_fail": 0, "cooldown": 60},
    "nse": {"healthy": True, "last_fail": 0, "cooldown": 30},
    "bse": {"healthy": True, "last_fail": 0, "cooldown": 30},
    "google": {"healthy": True, "last_fail": 0, "cooldown": 30},
}

def _is_healthy(provider):
    """Check if a provider is healthy (not in cooldown after failure)."""
    status = _provider_status.get(provider, {})
    if not status.get("healthy", True):
        if time.time() - status.get("last_fail", 0) > status.get("cooldown", 60):
            status["healthy"] = True  # Reset after cooldown
            return True
        return False
    return True

def _mark_failed(provider):
    """Mark a provider as temporarily failed."""
    if provider in _provider_status:
        _provider_status[provider]["healthy"] = False
        _provider_status[provider]["last_fail"] = time.time()

def _mark_success(provider):
    """Mark a provider as healthy."""
    if provider in _provider_status:
        _provider_status[provider]["healthy"] = True


# ═══════════════════════════════════════════════════
# 1. YFINANCE PROVIDER
# ═══════════════════════════════════════════════════

def _yf_quote(symbol):
    """Get quote from yfinance."""
    import yfinance as yf
    t = yf.Ticker(symbol)
    hist = t.history(period="2d")
    if len(hist) < 1:
        return None
    last = hist.iloc[-1]
    prev = hist.iloc[-2] if len(hist) > 1 else last
    return {
        "symbol": symbol,
        "price": round(float(last["Close"]), 2),
        "open": round(float(last["Open"]), 2),
        "high": round(float(last["High"]), 2),
        "low": round(float(last["Low"]), 2),
        "close": round(float(last["Close"]), 2),
        "prev_close": round(float(prev["Close"]), 2),
        "volume": int(last["Volume"]),
        "change": round(float(last["Close"] - prev["Close"]), 2),
        "change_pct": round((last["Close"] - prev["Close"]) / prev["Close"] * 100, 2),
        "source": "yfinance",
    }

def _yf_history(symbol, period="1m"):
    """Get history from yfinance."""
    import yfinance as yf
    t = yf.Ticker(symbol)
    df = t.history(period=period, interval="1d")
    if df.empty:
        return None
    df.index = df.index.tz_localize(None)
    return df


# ═══════════════════════════════════════════════════
# 2. NSE INDIA DIRECT API
# ═══════════════════════════════════════════════════

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

_nse_session_cookies = None

def _nse_get_cookies():
    """Get NSE session cookies (required for API access)."""
    global _nse_session_cookies
    if _nse_session_cookies and time.time() - _nse_session_cookies.get("_ts", 0) < 300:
        return _nse_session_cookies
    try:
        req = urllib.request.Request("https://www.nseindia.com/", headers=NSE_HEADERS)
        resp = urllib.request.urlopen(req, timeout=5)
        cookies = resp.headers.get("Set-Cookie", "")
        _nse_session_cookies = {"cookie": cookies, "_ts": time.time()}
        return _nse_session_cookies
    except Exception:
        return None

def _nse_quote(symbol):
    """Get quote from NSE India API."""
    clean = symbol.replace(".NS", "").replace(".BO", "")
    cookies = _nse_get_cookies()
    if not cookies:
        return None

    headers = dict(NSE_HEADERS)
    headers["Cookie"] = cookies.get("cookie", "")

    url = f"https://www.nseindia.com/api/quote-equity?symbol={clean}"
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())

        price_info = data.get("priceInfo", {})
        if not price_info:
            return None

        return {
            "symbol": symbol,
            "price": price_info.get("lastPrice", 0),
            "open": price_info.get("open", 0),
            "high": price_info.get("intraDayHighLow", {}).get("max", 0),
            "low": price_info.get("intraDayHighLow", {}).get("min", 0),
            "close": price_info.get("close", 0),
            "prev_close": price_info.get("previousClose", 0),
            "volume": data.get("securityWiseDP", {}).get("quantityTraded", 0),
            "change": price_info.get("change", 0),
            "change_pct": price_info.get("pChange", 0),
            "source": "nse_direct",
        }
    except Exception:
        return None

def _nse_index_quote(index_name):
    """Get index quote from NSE India API."""
    cookies = _nse_get_cookies()
    if not cookies:
        return None

    headers = dict(NSE_HEADERS)
    headers["Cookie"] = cookies.get("cookie", "")

    idx_map = {"NIFTY": "NIFTY 50", "NIFTY50": "NIFTY 50", "BANKNIFTY": "NIFTY BANK"}
    nse_name = idx_map.get(index_name.upper(), index_name)

    url = "https://www.nseindia.com/api/allIndices"
    try:
        req = urllib.request.Request(url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())

        for idx in data.get("data", []):
            if idx.get("index") == nse_name:
                return {
                    "name": nse_name,
                    "price": idx.get("last", 0),
                    "change": idx.get("variation", 0),
                    "change_pct": idx.get("percentChange", 0),
                    "open": idx.get("open", 0),
                    "high": idx.get("high", 0),
                    "low": idx.get("low", 0),
                    "prev_close": idx.get("previousClose", 0),
                    "source": "nse_direct",
                }
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════
# 3. BSE INDIA API
# ═══════════════════════════════════════════════════

def _bse_quote(symbol):
    """Get quote from BSE India API."""
    clean = symbol.replace(".BO", "").replace(".NS", "")
    url = f"https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w?scripcode=&flag=0&fromdate=&todate=&seriesid="
    # BSE needs scrip code, not symbol — skip for now
    return None

def _bse_index_quote(index_name):
    """Get BSE index quote."""
    try:
        url = "https://api.bseindia.com/BseIndiaAPI/api/Sensex/getSensexData?json=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=8)
        data = json.loads(resp.read())

        if data and len(data) > 0:
            sensex = data[0]
            return {
                "name": "SENSEX",
                "price": float(sensex.get("currentvalue", "0").replace(",", "")),
                "change": float(sensex.get("change", "0").replace(",", "")),
                "change_pct": float(sensex.get("perchange", "0").replace(",", "")),
                "source": "bse_direct",
            }
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════
# 4. GOOGLE FINANCE
# ═══════════════════════════════════════════════════

def _google_quote(symbol):
    """Get quote from Google Finance (scrape)."""
    clean = symbol.replace(".NS", "").replace(".BO", "")
    url = f"https://www.google.com/finance/quote/{clean}:NSE"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        resp = urllib.request.urlopen(req, timeout=8)
        html = resp.read().decode("utf-8")

        # Extract price from meta tag
        import re
        price_match = re.search(r'data-last-price="([0-9,.]+)"', html)
        change_match = re.search(r'data-last-normal-market-timestamp', html)

        if price_match:
            price = float(price_match.group(1).replace(",", ""))
            return {
                "symbol": symbol,
                "price": price,
                "source": "google",
            }
        return None
    except Exception:
        return None


# ═══════════════════════════════════════════════════
# 5. LOCAL CSV CACHE (always works)
# ═══════════════════════════════════════════════════

def _local_quote(symbol):
    """Get quote from local CSV data."""
    safe_name = symbol.replace(".", "_").replace("&", "_")
    path = os.path.join(DATA_DIR, f"{safe_name}.csv")
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if len(df) < 2:
            return None
        last = df.iloc[-1]
        prev = df.iloc[-2]
        return {
            "symbol": symbol,
            "price": round(float(last["Close"]), 2),
            "open": round(float(last["Open"]), 2),
            "high": round(float(last["High"]), 2),
            "low": round(float(last["Low"]), 2),
            "close": round(float(last["Close"]), 2),
            "prev_close": round(float(prev["Close"]), 2),
            "volume": int(last.get("Volume", 0)),
            "change": round(float(last["Close"] - prev["Close"]), 2),
            "change_pct": round((last["Close"] - prev["Close"]) / prev["Close"] * 100, 2),
            "source": "local_csv",
            "stale": True,
            "last_date": str(df.index[-1].date()) if hasattr(df.index[-1], 'date') else str(df.index[-1]),
        }
    except Exception:
        return None

def _local_history(symbol, period="1m"):
    """Get history from local CSV."""
    safe_name = symbol.replace(".", "_").replace("&", "_")
    path = os.path.join(DATA_DIR, f"{safe_name}.csv")
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        period_days = {"1d": 1, "5d": 5, "1w": 7, "1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730, "ytd": 365}
        days = period_days.get(period, 30)
        return df.tail(days)
    except Exception:
        return None


# ═══════════════════════════════════════════════════
# PUBLIC API: WATERFALL FALLBACK
# ═══════════════════════════════════════════════════

def get_quote(symbol):
    """
    Get stock quote using waterfall fallback.
    Tries: yfinance -> NSE direct -> Google -> local CSV
    """
    providers = [
        ("yfinance", _yf_quote),
        ("nse", _nse_quote),
        ("google", _google_quote),
    ]

    for name, func in providers:
        if not _is_healthy(name):
            continue
        try:
            result = func(symbol)
            if result and result.get("price", 0) > 0:
                _mark_success(name)
                return result
        except Exception:
            _mark_failed(name)

    # Final fallback: local CSV
    return _local_quote(symbol)


def get_history(symbol, period="1m"):
    """
    Get stock history using waterfall fallback.
    Tries: yfinance -> local CSV
    """
    if _is_healthy("yfinance"):
        try:
            result = _yf_history(symbol, period)
            if result is not None and len(result) > 0:
                _mark_success("yfinance")
                return result
        except Exception:
            _mark_failed("yfinance")

    return _local_history(symbol, period)


def get_index_quote(index_name):
    """
    Get market index quote using waterfall fallback.
    Tries: NSE direct -> BSE direct -> yfinance -> local CSV

    Args:
        index_name: "NIFTY", "SENSEX", "BANKNIFTY"
    """
    # Try NSE direct first (fastest for Indian indices)
    if _is_healthy("nse"):
        try:
            result = _nse_index_quote(index_name)
            if result and result.get("price", 0) > 0:
                _mark_success("nse")
                return result
        except Exception:
            _mark_failed("nse")

    # Try BSE for SENSEX
    if index_name.upper() in ("SENSEX", "BSE") and _is_healthy("bse"):
        try:
            result = _bse_index_quote(index_name)
            if result and result.get("price", 0) > 0:
                _mark_success("bse")
                return result
        except Exception:
            _mark_failed("bse")

    # yfinance fallback
    yf_map = {"NIFTY": "^NSEI", "NIFTY50": "^NSEI", "SENSEX": "^BSESN", "BANKNIFTY": "^NSEBANK"}
    yf_symbol = yf_map.get(index_name.upper(), index_name)
    if _is_healthy("yfinance"):
        try:
            result = _yf_quote(yf_symbol)
            if result and result.get("price", 0) > 0:
                _mark_success("yfinance")
                return {
                    "name": index_name,
                    "price": result["price"],
                    "change": result["change"],
                    "change_pct": result["change_pct"],
                    "source": "yfinance",
                }
        except Exception:
            _mark_failed("yfinance")

    # Local CSV fallback
    local = _local_quote(yf_symbol)
    if local:
        return {
            "name": index_name,
            "price": local["price"],
            "change": local["change"],
            "change_pct": local["change_pct"],
            "source": "local_csv",
            "stale": True,
        }
    return None


def get_provider_status():
    """Get status of all data providers."""
    return {
        name: {
            "healthy": _is_healthy(name),
            "last_fail": datetime.fromtimestamp(s["last_fail"]).isoformat() if s["last_fail"] > 0 else None,
        }
        for name, s in _provider_status.items()
    }


# ═══════════════════════════════════════════════════
# QUICK TEST
# ═══════════════════════════════════════════════════

if __name__ == "__main__":
    print("TradePilot Data Provider Test")
    print("=" * 50)

    # Test index quotes
    for idx in ["NIFTY", "SENSEX"]:
        result = get_index_quote(idx)
        if result:
            print(f"{idx}: {result['price']} ({result['change_pct']:+.2f}%) [source: {result.get('source')}]")
        else:
            print(f"{idx}: FAILED")

    # Test stock quote
    for sym in ["RELIANCE.NS", "TCS.NS", "TITAN.NS"]:
        result = get_quote(sym)
        if result:
            print(f"{sym}: {result['price']} ({result.get('change_pct', 0):+.2f}%) [source: {result.get('source')}]")
        else:
            print(f"{sym}: FAILED")

    print("\nProvider Status:")
    for name, status in get_provider_status().items():
        print(f"  {name}: {'OK' if status['healthy'] else 'DOWN'}")
