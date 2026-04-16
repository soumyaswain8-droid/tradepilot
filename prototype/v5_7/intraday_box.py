"""
Intraday Box Theory — Mean Reversion Strategy
===============================================
Simple but powerful: use previous day's HIGH and LOW as a box.
Buy at the bottom, sell at the top, do nothing in the middle.

Rules:
  1. Box ceiling = previous day's HIGH
  2. Box floor   = previous day's LOW
  3. On 5-min chart today:
     - Price near TOP (within 0.3% of ceiling) → look for SHORT
       Wait for 1 red candle closing below previous candle → SELL
       SL = that candle's high
     - Price near BOTTOM (within 0.3% of floor) → look for LONG
       Wait for 1 green candle closing above previous candle → BUY
       SL = that candle's low
     - Price in MIDDLE → DO NOTHING
  4. Target = opposite side of box (buy at bottom, target = top)

Usage:
    from prototype.v5_7.intraday_box import get_box, scan_for_signals

    box = get_box("RELIANCE")
    signals = scan_for_signals(["RELIANCE", "TCS", "INFY"])
"""

import warnings
warnings.filterwarnings("ignore")


# How close to ceiling/floor counts as "near" (percentage)
NEAR_THRESHOLD_PCT = 0.5  # Within 0.5% of ceiling/floor

# What portion of the box is the "dead zone" (middle, do nothing)
DEAD_ZONE_PCT = 0.3  # Middle 30% of box = no trade


def get_box(symbol, use_cache=True):
    """
    Get the box for a stock: previous day's HIGH and LOW.

    Returns:
        {
            "symbol": "RELIANCE",
            "ceiling": 2940.50,    # Previous day's high
            "floor": 2871.20,      # Previous day's low
            "range": 69.30,        # Ceiling - floor
            "range_pct": 2.41,     # Range as % of floor
            "prev_close": 2912.80, # Previous day's close
            "prev_date": "2026-04-16",
        }
    """
    import yfinance as yf

    ticker = symbol if ".NS" in symbol else f"{symbol}.NS"
    try:
        df = yf.download(ticker, period="5d", interval="1d", progress=False)
        if hasattr(df.columns, 'droplevel') and len(df.columns.names) > 1:
            df.columns = df.columns.droplevel(1)
        if len(df) < 2:
            return None

        # Previous day = second-to-last row (last row is today, may be partial)
        prev = df.iloc[-2]
        return {
            "symbol": symbol,
            "ceiling": round(float(prev["High"]), 2),
            "floor": round(float(prev["Low"]), 2),
            "range": round(float(prev["High"] - prev["Low"]), 2),
            "range_pct": round(float((prev["High"] - prev["Low"]) / prev["Low"] * 100), 2),
            "prev_close": round(float(prev["Close"]), 2),
            "prev_open": round(float(prev["Open"]), 2),
            "prev_date": str(df.index[-2].date()),
        }
    except Exception:
        return None


def get_current_price_and_candles(symbol):
    """
    Get current price + last few 5-min candles for confirmation check.

    Returns:
        {
            "price": 2925.50,
            "candles": [
                {"open": 2928, "high": 2930, "low": 2924, "close": 2925, "green": False},
                {"open": 2922, "high": 2929, "low": 2921, "close": 2928, "green": True},
            ]
        }
    """
    import yfinance as yf

    ticker = symbol if ".NS" in symbol else f"{symbol}.NS"
    try:
        df = yf.download(ticker, period="1d", interval="5m", progress=False)
        if hasattr(df.columns, 'droplevel') and len(df.columns.names) > 1:
            df.columns = df.columns.droplevel(1)
        if len(df) < 3:
            return None

        candles = []
        for _, row in df.tail(5).iterrows():
            candles.append({
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "green": float(row["Close"]) >= float(row["Open"]),
            })

        return {
            "price": round(float(df["Close"].iloc[-1]), 2),
            "candles": candles,
        }
    except Exception:
        return None


def check_box_signal(symbol, box=None):
    """
    Check if a stock has a box theory signal right now.

    Returns:
        {
            "symbol": "RELIANCE",
            "signal": "BUY" | "SELL" | "NONE",
            "zone": "TOP" | "BOTTOM" | "MIDDLE" | "ABOVE" | "BELOW",
            "price": 2875.30,
            "box_ceiling": 2940.50,
            "box_floor": 2871.20,
            "entry_price": 2875.30,
            "sl_price": 2868.50,       # Previous candle's low (for BUY)
            "target_price": 2940.50,   # Opposite side of box
            "risk_reward": 2.8,
            "confirmed": True,         # Candle confirmation present
            "score": 85,               # 0-100
            "reasons": ["Price near box floor", "Green candle confirmation"]
        }
    """
    if box is None:
        box = get_box(symbol)
    if box is None:
        return {"symbol": symbol, "signal": "NONE", "zone": "UNKNOWN", "score": 0,
                "reasons": ["No box data available"]}

    candle_data = get_current_price_and_candles(symbol)
    if candle_data is None:
        return {"symbol": symbol, "signal": "NONE", "zone": "UNKNOWN", "score": 0,
                "reasons": ["No intraday data available"]}

    price = candle_data["price"]
    candles = candle_data["candles"]
    ceiling = box["ceiling"]
    floor = box["floor"]
    box_range = ceiling - floor

    if box_range <= 0:
        return {"symbol": symbol, "signal": "NONE", "zone": "UNKNOWN", "score": 0,
                "reasons": ["Invalid box range"]}

    # Determine zone
    position = (price - floor) / box_range  # 0 = at floor, 1 = at ceiling
    near_top = position >= (1 - NEAR_THRESHOLD_PCT / 100 * box_range / box_range)
    near_top = (ceiling - price) / ceiling * 100 <= NEAR_THRESHOLD_PCT
    near_bottom = (price - floor) / floor * 100 <= NEAR_THRESHOLD_PCT
    above_box = price > ceiling * 1.003  # 0.3% above ceiling = breakout
    below_box = price < floor * 0.997

    if above_box:
        zone = "ABOVE"
    elif below_box:
        zone = "BELOW"
    elif near_top:
        zone = "TOP"
    elif near_bottom:
        zone = "BOTTOM"
    else:
        zone = "MIDDLE"

    result = {
        "symbol": symbol,
        "signal": "NONE",
        "zone": zone,
        "price": price,
        "box_ceiling": ceiling,
        "box_floor": floor,
        "box_range": box_range,
        "box_range_pct": box["range_pct"],
        "entry_price": price,
        "sl_price": 0,
        "target_price": 0,
        "risk_reward": 0,
        "confirmed": False,
        "score": 0,
        "reasons": [],
    }

    # ═══ BOTTOM ZONE → Look for BUY (long) ═══
    if zone == "BOTTOM" and len(candles) >= 2:
        last = candles[-1]
        prev = candles[-2]

        # Confirmation: green candle closing above previous candle
        if last["green"] and last["close"] > prev["close"]:
            result["signal"] = "BUY"
            result["confirmed"] = True
            result["entry_price"] = last["close"]
            result["sl_price"] = round(last["low"] * 0.998, 2)  # Just below candle's low
            result["target_price"] = ceiling  # Target = top of box
            risk = result["entry_price"] - result["sl_price"]
            reward = result["target_price"] - result["entry_price"]
            result["risk_reward"] = round(reward / risk, 2) if risk > 0 else 0
            result["score"] = min(100, 70 + int(result["risk_reward"] * 5))
            result["reasons"].append(f"Price near box floor Rs {floor:.0f}")
            result["reasons"].append(f"Green candle confirmation ({last['close']:.0f} > {prev['close']:.0f})")
            result["reasons"].append(f"Target: box ceiling Rs {ceiling:.0f} (R:R {result['risk_reward']:.1f})")
        else:
            result["score"] = 40
            result["reasons"].append(f"Near floor Rs {floor:.0f} — waiting for green candle confirmation")

    # ═══ TOP ZONE → Look for SELL (short) ═══
    elif zone == "TOP" and len(candles) >= 2:
        last = candles[-1]
        prev = candles[-2]

        # Confirmation: red candle closing below previous candle
        if not last["green"] and last["close"] < prev["close"]:
            result["signal"] = "SELL"
            result["confirmed"] = True
            result["entry_price"] = last["close"]
            result["sl_price"] = round(last["high"] * 1.002, 2)  # Just above candle's high
            result["target_price"] = floor  # Target = bottom of box
            risk = result["sl_price"] - result["entry_price"]
            reward = result["entry_price"] - result["target_price"]
            result["risk_reward"] = round(reward / risk, 2) if risk > 0 else 0
            result["score"] = min(100, 70 + int(result["risk_reward"] * 5))
            result["reasons"].append(f"Price near box ceiling Rs {ceiling:.0f}")
            result["reasons"].append(f"Red candle confirmation ({last['close']:.0f} < {prev['close']:.0f})")
            result["reasons"].append(f"Target: box floor Rs {floor:.0f} (R:R {result['risk_reward']:.1f})")
        else:
            result["score"] = 40
            result["reasons"].append(f"Near ceiling Rs {ceiling:.0f} — waiting for red candle confirmation")

    # ═══ MIDDLE ZONE → Do nothing ═══
    elif zone == "MIDDLE":
        result["score"] = 20
        result["reasons"].append(f"Inside box ({floor:.0f}-{ceiling:.0f}), no edge — waiting")

    # ═══ ABOVE BOX → Breakout, don't short ═══
    elif zone == "ABOVE":
        result["score"] = 10
        result["reasons"].append(f"Above box ceiling — possible breakout, box strategy inactive")

    # ═══ BELOW BOX → Breakdown, don't buy ═══
    elif zone == "BELOW":
        result["score"] = 10
        result["reasons"].append(f"Below box floor — possible breakdown, box strategy inactive")

    return result


def scan_for_signals(symbols):
    """
    Scan all stocks for intraday box signals.
    Returns only stocks with BUY or SELL signals (confirmed).
    """
    signals = []
    for sym in symbols:
        try:
            result = check_box_signal(sym)
            if result["signal"] in ("BUY", "SELL") and result["confirmed"]:
                signals.append(result)
        except Exception:
            continue

    # Sort by score descending
    signals.sort(key=lambda x: x["score"], reverse=True)
    return signals


# ═══ CLI ═══
if __name__ == "__main__":
    import sys
    sys.path.insert(0, "prototype")

    if len(sys.argv) > 1:
        symbols = sys.argv[1:]
    else:
        from v4.config import NIFTY_50_SYMBOLS
        symbols = NIFTY_50_SYMBOLS[:10]

    print("Intraday Box Theory Scanner")
    print("=" * 60)

    for sym in symbols:
        box = get_box(sym)
        if not box:
            print(f"  {sym}: no data")
            continue

        result = check_box_signal(sym, box)
        sig = result["signal"]
        zone = result["zone"]
        score = result["score"]

        sig_str = f"\033[92m{sig}\033[0m" if sig == "BUY" else f"\033[91m{sig}\033[0m" if sig == "SELL" else sig
        print(f"  {sym:>14s} | Box: {box['floor']:.0f}-{box['ceiling']:.0f} ({box['range_pct']:.1f}%) | "
              f"Price: {result['price']:.0f} | Zone: {zone:>6s} | Signal: {sig_str:>4s} | Score: {score}")
        for r in result["reasons"]:
            print(f"  {'':>14s}   -> {r}")
