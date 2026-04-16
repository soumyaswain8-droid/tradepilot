"""
Darvas Box Theory — Stock Price Box Detection & Breakout Scoring
================================================================
Detects consolidation "boxes" from recent price action and scores breakout potential.

How it works:
1. Look at last N days of daily OHLC data
2. Find the recent HIGH (box ceiling) and LOW (box floor)
3. Check if price is consolidating within the box (low volatility)
4. Score the breakout: price above ceiling with volume = BUY signal
5. Set dynamic stop-loss at box floor (not fixed %)

Box rules:
- A box forms when a stock makes a new high, then pulls back but stays above the prior low
- The ceiling = recent high, floor = recent low after the high
- Breakout = close above ceiling + volume > 1.2x average
- Breakdown = close below floor = EXIT
- New box forms when price consolidates at higher level (staircase)

Usage:
    from prototype.v5_6.darvas_box import detect_boxes, score_box_breakout

    boxes = detect_boxes("RELIANCE", lookback_days=20)
    score = score_box_breakout("RELIANCE", current_price, current_volume)
"""

import warnings
warnings.filterwarnings("ignore")


def _get_daily_data(symbol, days=60):
    """Fetch daily OHLCV data for a stock."""
    import yfinance as yf
    ticker = symbol if ".NS" in symbol else f"{symbol}.NS"
    try:
        df = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
        if hasattr(df.columns, 'droplevel') and len(df.columns.names) > 1:
            df.columns = df.columns.droplevel(1)
        if len(df) < 10:
            return None
        return df
    except Exception:
        return None


def detect_boxes(symbol, lookback_days=20, min_box_days=3):
    """
    Detect Darvas boxes in recent price history.

    Returns list of boxes, newest first:
    [
        {
            "ceiling": 2950.0,      # Box top (recent high)
            "floor": 2820.0,        # Box bottom (low after the high)
            "width_days": 8,        # How many days the box lasted
            "ceiling_date": "2026-04-10",
            "floor_date": "2026-04-12",
            "active": True,         # Price is currently inside this box
            "breakout": False,      # Price broke above ceiling
            "breakdown": False,     # Price broke below floor
        }
    ]
    """
    df = _get_daily_data(symbol, days=lookback_days + 30)
    if df is None or len(df) < lookback_days:
        return []

    df = df.tail(lookback_days).copy()
    closes = df["Close"].values
    highs = df["High"].values
    lows = df["Low"].values
    dates = df.index

    boxes = []
    i = 0

    while i < len(closes) - min_box_days:
        # Find local high (ceiling)
        ceiling = highs[i]
        ceiling_idx = i
        for j in range(i + 1, min(i + 5, len(highs))):
            if highs[j] > ceiling:
                ceiling = highs[j]
                ceiling_idx = j

        # Find floor after ceiling (lowest low after the high)
        floor = float('inf')
        floor_idx = ceiling_idx
        box_end = min(ceiling_idx + 15, len(lows))

        for j in range(ceiling_idx + 1, box_end):
            if lows[j] < floor:
                floor = lows[j]
                floor_idx = j
            # If price breaks above ceiling, box is done — breakout
            if closes[j] > ceiling * 1.005:  # 0.5% above ceiling = breakout
                break

        if floor == float('inf'):
            i += 1
            continue

        width = floor_idx - ceiling_idx + 1
        if width < min_box_days:
            i = floor_idx + 1
            continue

        # Check current state
        current_price = float(closes[-1])
        active = floor <= current_price <= ceiling
        breakout = current_price > ceiling * 1.005
        breakdown = current_price < floor * 0.995

        box = {
            "ceiling": round(float(ceiling), 2),
            "floor": round(float(floor), 2),
            "width_days": width,
            "ceiling_date": str(dates[ceiling_idx].date()) if ceiling_idx < len(dates) else "?",
            "floor_date": str(dates[floor_idx].date()) if floor_idx < len(dates) else "?",
            "range_pct": round((ceiling - floor) / floor * 100, 2),
            "active": active,
            "breakout": breakout,
            "breakdown": breakdown,
            "current_price": current_price,
        }
        boxes.append(box)

        # Move past this box
        i = floor_idx + 1

    # Return newest boxes first
    boxes.reverse()
    return boxes


def score_box_breakout(symbol, current_price=None, current_volume=None, lookback_days=20):
    """
    Score a stock's Darvas Box status (0-100).

    Scoring:
        80-100: Active breakout above ceiling with volume — STRONG BUY
        60-79:  Price at top of box, testing ceiling — WATCH
        40-59:  Inside box, consolidating — NEUTRAL
        20-39:  Near box floor — CAUTION
        0-19:   Below box floor (breakdown) — AVOID

    Returns:
        {
            "darvas_score": 85,
            "signal": "BREAKOUT",
            "box_ceiling": 2950.0,
            "box_floor": 2820.0,
            "dynamic_sl": 2820.0,     # Stop-loss at box floor
            "dynamic_target": 3080.0,  # Target = ceiling + box range
            "box_count": 3,
            "staircase": True,         # Multiple ascending boxes
            "reasons": ["Breakout above 2950 box ceiling", "Volume 1.8x confirms"]
        }
    """
    boxes = detect_boxes(symbol, lookback_days=lookback_days)

    result = {
        "darvas_score": 50,
        "signal": "NEUTRAL",
        "box_ceiling": 0,
        "box_floor": 0,
        "dynamic_sl": 0,
        "dynamic_target": 0,
        "box_count": len(boxes),
        "staircase": False,
        "reasons": [],
    }

    if not boxes:
        result["reasons"].append("No clear box formation detected")
        return result

    box = boxes[0]  # Most recent box
    ceiling = box["ceiling"]
    floor = box["floor"]
    box_range = ceiling - floor
    price = current_price or box["current_price"]

    result["box_ceiling"] = ceiling
    result["box_floor"] = floor
    result["dynamic_sl"] = round(floor * 0.995, 2)  # SL just below box floor
    result["dynamic_target"] = round(ceiling + box_range, 2)  # Target = ceiling + 1x range

    # Check for staircase (ascending boxes)
    if len(boxes) >= 2:
        ascending = all(boxes[i]["ceiling"] > boxes[i + 1]["ceiling"] for i in range(len(boxes) - 1))
        result["staircase"] = ascending
        if ascending:
            result["reasons"].append(f"Staircase pattern: {len(boxes)} ascending boxes")

    # Score based on price position relative to box
    if box["breakout"]:
        # Above ceiling — breakout!
        pct_above = (price - ceiling) / ceiling * 100
        result["darvas_score"] = min(100, 80 + int(pct_above * 5))
        result["signal"] = "BREAKOUT"
        result["reasons"].append(f"Breakout above box ceiling {ceiling:.0f}")

        # Volume confirmation bonus
        if current_volume:
            df = _get_daily_data(symbol, days=30)
            if df is not None and len(df) > 5:
                avg_vol = float(df["Volume"].tail(20).mean())
                if avg_vol > 0:
                    vol_ratio = current_volume / avg_vol
                    if vol_ratio > 1.2:
                        result["darvas_score"] = min(100, result["darvas_score"] + 10)
                        result["reasons"].append(f"Volume {vol_ratio:.1f}x confirms breakout")
                    elif vol_ratio < 0.8:
                        result["darvas_score"] = max(60, result["darvas_score"] - 10)
                        result["reasons"].append(f"Low volume {vol_ratio:.1f}x — weak breakout")

    elif box["breakdown"]:
        # Below floor — breakdown
        result["darvas_score"] = max(0, 15 - int((floor - price) / floor * 100 * 5))
        result["signal"] = "BREAKDOWN"
        result["reasons"].append(f"Below box floor {floor:.0f} — EXIT")

    elif box["active"]:
        # Inside box — score by position
        position_in_box = (price - floor) / box_range if box_range > 0 else 0.5
        result["darvas_score"] = int(40 + position_in_box * 30)  # 40-70 range

        if position_in_box > 0.85:
            result["signal"] = "CEILING_TEST"
            result["reasons"].append(f"Testing ceiling at {ceiling:.0f} — potential breakout")
        elif position_in_box < 0.15:
            result["signal"] = "FLOOR_TEST"
            result["reasons"].append(f"Near floor at {floor:.0f} — caution")
        else:
            result["signal"] = "CONSOLIDATING"
            result["reasons"].append(f"Inside box ({floor:.0f}-{ceiling:.0f}), consolidating")

    # Staircase bonus
    if result["staircase"]:
        result["darvas_score"] = min(100, result["darvas_score"] + 5)

    # Box tightness bonus (tight box = coiled spring)
    if box["range_pct"] < 3.0 and box["width_days"] >= 5:
        result["darvas_score"] = min(100, result["darvas_score"] + 5)
        result["reasons"].append(f"Tight box ({box['range_pct']:.1f}%) — coiled spring potential")

    return result


def scan_universe_boxes(symbols, top_n=20):
    """
    Scan all stocks and return top N by Darvas box score.
    Prioritizes breakouts and ceiling tests.
    """
    results = []
    for sym in symbols:
        try:
            score = score_box_breakout(sym)
            if score["darvas_score"] > 40:  # Skip neutral/weak
                score["symbol"] = sym
                results.append(score)
        except Exception:
            continue

    results.sort(key=lambda x: x["darvas_score"], reverse=True)
    return results[:top_n]


# ═══ CLI for testing ═══
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        symbol = sys.argv[1]
    else:
        symbol = "RELIANCE"

    print(f"Darvas Box Analysis: {symbol}")
    print("=" * 50)

    boxes = detect_boxes(symbol)
    if boxes:
        for i, box in enumerate(boxes):
            print(f"\nBox {i + 1}:")
            print(f"  Ceiling: Rs {box['ceiling']:,.2f} ({box['ceiling_date']})")
            print(f"  Floor:   Rs {box['floor']:,.2f} ({box['floor_date']})")
            print(f"  Range:   {box['range_pct']:.2f}% | Width: {box['width_days']} days")
            print(f"  Status:  {'BREAKOUT' if box['breakout'] else 'BREAKDOWN' if box['breakdown'] else 'ACTIVE' if box['active'] else 'INACTIVE'}")
    else:
        print("  No boxes detected")

    print(f"\nScore:")
    score = score_box_breakout(symbol)
    print(f"  Darvas Score: {score['darvas_score']}/100")
    print(f"  Signal:       {score['signal']}")
    print(f"  Box Ceiling:  Rs {score['box_ceiling']:,.2f}")
    print(f"  Box Floor:    Rs {score['box_floor']:,.2f}")
    print(f"  Dynamic SL:   Rs {score['dynamic_sl']:,.2f}")
    print(f"  Dynamic TGT:  Rs {score['dynamic_target']:,.2f}")
    print(f"  Staircase:    {score['staircase']}")
    for r in score["reasons"]:
        print(f"  - {r}")
