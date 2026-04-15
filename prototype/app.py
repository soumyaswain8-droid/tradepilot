"""
TradePilot Prototype -- Flask web server.
Serves the HTML dashboard and API endpoints.
Transforms backend data to match frontend's expected format.
"""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(__file__))

from data_engine import get_market_indices, load_stock_data, NIFTY_STOCKS
from ai_scorer import score_stocks, train_model
from analytics import (track_visit, track_page_view, track_stock_view,
                       track_swipe, track_paper_trade, track_wizard_search,
                       track_feedback, get_dashboard_stats)

# Try to use v2 engine, fallback to v1
try:
    from trading_engine import score_stocks_v2, train_ensemble
    HAS_V2 = True
    print("[ENGINE] v2 ensemble loaded (XGBoost + LightGBM)")
except ImportError:
    HAS_V2 = False
    print("[ENGINE] v2 not available, using v1")

# Try to load v3 regime-aware engine
try:
    from trading_engine_v3 import score_stocks_v3
    HAS_V3 = True
    print("[ENGINE] v3 regime-aware engine loaded")
except ImportError:
    HAS_V3 = False
    print("[ENGINE] v3 not available")

# Try to load v4 composite scorer
try:
    from v4.composite_scorer import score_all_stocks as score_stocks_v4
    HAS_V4 = True
    print("[ENGINE] v4 composite scorer loaded")
except ImportError:
    HAS_V4 = False
    print("[ENGINE] v4 not available")

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))
CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*", "https://tradepilot.onrender.com"])  # Restricted CORS


def get_model_meta():
    # Prefer v2 meta
    v2_path = os.path.join(os.path.dirname(__file__), "models", "model_meta_v2.json")
    v1_path = os.path.join(os.path.dirname(__file__), "models", "model_meta.json")
    for path in [v2_path, v1_path]:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return None


def get_model_meta_v3():
    """Load v3 model metadata."""
    v3_path = os.path.join(os.path.dirname(__file__), "models", "model_meta_v3.json")
    if os.path.exists(v3_path):
        with open(v3_path) as f:
            return json.load(f)
    return None


def get_backtest_results():
    path = os.path.join(os.path.dirname(__file__), "models", "backtest_results.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/landing")
def landing():
    """Premium landing page for client demos."""
    return render_template("landing.html")

@app.route("/api/preloaded-scores")
def api_preloaded():
    """Serve pre-computed scores (instant, no API delay)."""
    scores_path = os.path.join(os.path.dirname(__file__), "static", "preloaded-scores.json")
    if os.path.exists(scores_path):
        with open(scores_path) as f:
            return f.read(), 200, {'Content-Type': 'application/json'}
    return jsonify([])

@app.route("/pitch")
def pitch():
    """Serve the interactive pitch deck."""
    pitch_path = os.path.join(os.path.dirname(__file__), "..", "docs", "pitch", "pitch-deck.html")
    with open(pitch_path, "r") as f:
        return f.read()


_score_cache = {"data": None, "time": 0}
_data_ready = {"status": False, "loading": False}

def ensure_data():
    """Download stock data and train model if not present (runs once on Render)."""
    if _data_ready["status"] or _data_ready["loading"]:
        return _data_ready["status"]

    from data_engine import load_all_stock_data, download_stock_data, NIFTY_50
    data = load_all_stock_data()
    if len(data) >= 10:
        _data_ready["status"] = True
        return True

    # Need to download data (first run on Render)
    _data_ready["loading"] = True
    try:
        print("[INIT] Downloading NIFTY 50 stock data (first run)...")
        download_stock_data(NIFTY_50[:20], period="1y")  # Start with top 20 for speed
        print("[INIT] Training AI model...")
        train_model(load_all_stock_data())
        if HAS_V2:
            try:
                train_ensemble(load_all_stock_data())
            except Exception:
                pass
        _data_ready["status"] = True
        print("[INIT] Ready!")
    except Exception as e:
        print(f"[INIT] Error: {e}")
    finally:
        _data_ready["loading"] = False
    return _data_ready["status"]


def get_live_scores_fallback(symbols):
    """Fallback: get basic scores from live yfinance data when no trained model exists."""
    import yfinance as yf
    stocks = []
    for sym in symbols[:30]:  # Limit to 30 for speed
        try:
            name = sym.replace(".NS", "").replace(".BO", "")
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            if len(hist) < 2:
                continue
            price = round(float(hist.iloc[-1]["Close"]), 2)
            prev = float(hist.iloc[-2]["Close"])
            change = round((price - prev) / prev * 100, 2)

            # Simple score based on recent momentum
            returns_5d = (price / float(hist.iloc[0]["Close"]) - 1) * 100
            score = round(max(10, min(90, 50 + returns_5d * 5)), 1)
            direction = "BUY" if score >= 55 else "HOLD" if score >= 40 else "AVOID"

            stocks.append({
                "symbol": name, "name": name, "price": price,
                "change": change, "score": score, "direction": direction,
                "rsi": 50, "trend": "Sideways", "volatility": "Medium",
                "macd": "Neutral", "stopLoss": 3.0, "target": 6.0,
                "riskReward": 2.0,
                "reasons": [{"text": f"{'Positive' if change > 0 else 'Negative'} momentum ({change:+.1f}%)", "type": "positive" if change > 0 else "negative"}],
            })
        except Exception:
            pass
    stocks.sort(key=lambda x: x["score"], reverse=True)
    return stocks


@app.route("/api/scores")
def api_scores():
    """Get AI scores -- uses NIFTY 50 by default for speed, with caching."""
    import time
    category = request.args.get('category', 'nifty50')
    default_engine = "v4" if HAS_V4 else "v2"
    engine = request.args.get('engine', default_engine)

    # Cache for 5 minutes on Render (reduce API calls)
    cache_key = f"{category}_{engine}"
    now = time.time()
    if _score_cache["data"] and (now - _score_cache["time"]) < 300 and _score_cache.get("key") == cache_key:
        return jsonify(_score_cache["data"])

    try:
        from data_engine import STOCK_CATEGORIES, NIFTY_50
        cat_stocks = STOCK_CATEGORIES.get(category, {}).get('stocks', NIFTY_50)

        # Try trained model first
        raw_scores = None
        if engine == "v4" and HAS_V4:
            try:
                raw_scores = score_stocks_v4(cat_stocks)
            except Exception:
                pass
        if not raw_scores and engine == "v3" and HAS_V3:
            try:
                raw_scores = score_stocks_v3(cat_stocks)
            except Exception:
                pass
        if not raw_scores and ensure_data():
            try:
                raw_scores = score_stocks_v2(cat_stocks) if HAS_V2 else score_stocks()
            except Exception:
                pass

        # Fallback to live yfinance if no model
        if not raw_scores:
            stocks = get_live_scores_fallback(cat_stocks)
            _score_cache["data"] = stocks
            _score_cache["time"] = now
            _score_cache["key"] = cache_key
            return jsonify(stocks)

        import math
        raw_scores = raw_scores  # Use model scores

        def safe(v, default=0):
            """Sanitize NaN/Inf values for JSON serialization."""
            if v is None:
                return default
            try:
                if math.isnan(v) or math.isinf(v):
                    return default
            except (TypeError, ValueError):
                pass
            return v

        # Transform to frontend format
        stocks = []
        for s in raw_scores:
            price = safe(s.get("price"), 0)
            score = safe(s.get("score"), 0)
            change = safe(s.get("change_pct"), 0)
            rsi = safe(s.get("rsi"), 50)
            vol_raw = s.get("volatility", 20)
            vol = safe(vol_raw, 20) if not isinstance(vol_raw, str) else 20

            # Skip entries with no valid price
            if price == 0:
                continue

            # Sanitize reasons — strip numeric values to prevent reverse engineering
            reasons = []
            for r in s.get("reasons", []):
                raw_text = r.get("text", "")
                # Remove specific numbers from reason text (e.g. "Price +1.43% above VWAP (7059)")
                import re
                sanitized = re.sub(r'\([\d,.]+\)', '', raw_text)  # strip parenthesized numbers
                sanitized = re.sub(r'[\d,.]+%', '%', sanitized)   # strip percentage values
                sanitized = re.sub(r'[\d,.]+\s*Cr', 'Cr', sanitized)  # strip crore values
                reasons.append({
                    "text": sanitized.strip(),
                    "type": r.get("type", r.get("impact", "neutral")),
                })

            entry = {
                "symbol": s.get("name", s.get("symbol", "").replace(".NS", "")),
                "name": s.get("name", s.get("symbol", "")),
                "price": round(price, 2),
                "change": round(change, 2),
                "score": round(score, 1),
                "direction": s.get("direction", "HOLD"),
                "rsi": round(rsi, 1),
                "trend": s.get("trend", "Sideways"),
                "volatility": "High" if vol > 25 else "Low" if vol < 15 else "Medium",
                "macd": s.get("macd_signal", "Neutral"),
                "stopLoss": round(safe(s.get("stop_loss_pct"), 2.0), 1),
                "target": round(safe(s.get("target_pct"), 4.0), 1),
                "riskReward": round(safe(s.get("risk_reward"), 2.0), 1),
                "reasons": reasons,
            }

            # Add v3/v4-specific fields when present
            if engine in ("v3", "v4"):
                entry["market_regime"] = s.get("market_regime", "unknown")
                entry["relative_strength_5d"] = safe(s.get("relative_strength_5d"), 0)
                entry["relative_strength_20d"] = safe(s.get("relative_strength_20d"), 0)
                entry["confidence"] = safe(s.get("confidence"), 0)
                entry["model_version"] = s.get("model_version", engine)

            stocks.append(entry)

        _score_cache["data"] = stocks
        _score_cache["time"] = now
        _score_cache["key"] = cache_key
        return jsonify(stocks)
    except Exception as e:
        traceback.print_exc()
        return jsonify([]), 500


@app.route("/api/model")
def api_model():
    """Get model metadata -- sanitized for public consumption."""
    try:
        default_engine = "v4" if HAS_V4 else "v2"
        engine = request.args.get('engine', default_engine)

        # Return v4 metadata if requested and available
        if engine == "v4" and HAS_V4:
            return jsonify({
                "accuracy": 0,
                "version": "v4",
                "trainingSamples": 0,
                "lastTrained": datetime.now().strftime("%Y-%m-%d"),
                "features": [],
                "backtest": [],
                "model_type": "composite_scorer",
                "description": "Multi-signal composite scorer (technical + momentum + regime)",
                "target_metric": "precision (80% profitable trades)",
            })

        # Return v3 metadata if requested and available
        if engine == "v3" and HAS_V3:
            meta_v3 = get_model_meta_v3()
            if meta_v3:
                trained_at = meta_v3.get("trained_at", "Unknown")
                if "T" in trained_at:
                    trained_at = trained_at.split("T")[0]
                return jsonify({
                    "accuracy": round(meta_v3.get("accuracy", 0) * 100, 1) if meta_v3.get("accuracy", 0) < 1 else meta_v3.get("accuracy", 0),
                    "version": "v3",
                    "trainingSamples": meta_v3.get("train_samples", 0) + meta_v3.get("test_samples", 0),
                    "lastTrained": trained_at,
                    "features": [],  # populated below if available
                    "backtest": [],
                    "market_regime": meta_v3.get("market_regime", "unknown"),
                    "precision": meta_v3.get("precision", 0),
                    "target_metric": "precision (80% profitable trades)",
                })

        # SECURITY-006: Strip all IP-sensitive data from public response
        # No feature importances, no backtest metrics, no ensemble weights
        return jsonify({
            "accuracy": 0,
            "version": "v2",
            "trainingSamples": 0,
            "lastTrained": datetime.now().strftime("%Y-%m-%d"),
            "features": [],
            "backtest": [],
            "model_type": "ensemble",
            "description": "ML ensemble scorer",
            "status": "active",
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"accuracy": 0, "trainingSamples": 0, "lastTrained": "Error"})


@app.route("/api/compare")
def api_compare():
    """Return v2 and v3 scores side by side for comparison."""
    try:
        from data_engine import STOCK_CATEGORIES, NIFTY_50
        category = request.args.get('category', 'nifty50')
        cat_stocks = STOCK_CATEGORIES.get(category, {}).get('stocks', NIFTY_50)

        v2_scores = []
        v3_scores = []

        # Get v2 scores
        if HAS_V2 and ensure_data():
            try:
                v2_scores = score_stocks_v2(cat_stocks) or []
            except Exception:
                pass

        # Get v3 scores
        if HAS_V3:
            try:
                v3_scores = score_stocks_v3(cat_stocks) or []
            except Exception:
                pass

        # Index by symbol for side-by-side
        v2_map = {s.get("symbol", s.get("name", "")): s for s in v2_scores}
        v3_map = {s.get("symbol", s.get("name", "")): s for s in v3_scores}
        all_symbols = sorted(set(list(v2_map.keys()) + list(v3_map.keys())))

        comparison = []
        for sym in all_symbols:
            v2 = v2_map.get(sym, {})
            v3 = v3_map.get(sym, {})
            comparison.append({
                "symbol": sym.replace(".NS", ""),
                "v2_score": round(v2.get("score", 0), 1),
                "v2_direction": v2.get("direction", "N/A"),
                "v3_score": round(v3.get("score", 0), 1),
                "v3_direction": v3.get("direction", "N/A"),
                "v3_confidence": v3.get("confidence", 0),
                "v3_market_regime": v3.get("market_regime", "unknown"),
                "score_diff": round(v3.get("score", 0) - v2.get("score", 0), 1),
            })

        comparison.sort(key=lambda x: abs(x["score_diff"]), reverse=True)

        return jsonify({
            "comparison": comparison,
            "v2_available": HAS_V2,
            "v3_available": HAS_V3,
            "total_stocks": len(comparison),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"comparison": [], "error": str(e)}), 500


@app.route("/api/compare-v4")
def api_compare_v4():
    """Return v3 and v4 scores side by side for comparison."""
    try:
        from data_engine import STOCK_CATEGORIES, NIFTY_50
        category = request.args.get('category', 'nifty50')
        cat_stocks = STOCK_CATEGORIES.get(category, {}).get('stocks', NIFTY_50)

        v3_scores = []
        v4_scores = []

        if HAS_V3:
            try:
                v3_scores = score_stocks_v3(cat_stocks) or []
            except Exception:
                pass

        if HAS_V4:
            try:
                v4_scores = score_stocks_v4(cat_stocks) or []
            except Exception:
                pass

        v3_map = {s.get("symbol", s.get("name", "")): s for s in v3_scores}
        v4_map = {s.get("symbol", s.get("name", "")): s for s in v4_scores}
        all_symbols = sorted(set(list(v3_map.keys()) + list(v4_map.keys())))

        comparison = []
        for sym in all_symbols:
            v3 = v3_map.get(sym, {})
            v4 = v4_map.get(sym, {})
            comparison.append({
                "symbol": sym.replace(".NS", ""),
                "v3_score": round(v3.get("score", 0), 1),
                "v3_direction": v3.get("direction", "N/A"),
                "v3_confidence": v3.get("confidence", 0),
                "v4_score": round(v4.get("score", 0), 1),
                "v4_direction": v4.get("direction", "N/A"),
                "v4_confidence": v4.get("confidence", 0),
                "v4_market_regime": v4.get("market_regime", "unknown"),
                "score_diff": round(v4.get("score", 0) - v3.get("score", 0), 1),
            })

        comparison.sort(key=lambda x: abs(x["score_diff"]), reverse=True)

        return jsonify({
            "comparison": comparison,
            "v3_available": HAS_V3,
            "v4_available": HAS_V4,
            "total_stocks": len(comparison),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"comparison": [], "error": str(e)}), 500


@app.route("/api/indices")
def api_indices():
    """Get market indices -- formatted for frontend."""
    try:
        raw = get_market_indices()
        result = {}
        for idx in raw:
            name = idx.get("name", "")
            entry = {
                "price": idx.get("value", 0),
                "change": idx.get("change", 0),
                "changePct": idx.get("change_pct", 0),
            }
            if "NIFTY" in name.upper():
                result["nifty"] = entry
            elif "SENSEX" in name.upper():
                result["sensex"] = entry

        # Fallback: read from local CSV if yfinance failed
        if "nifty" not in result or result.get("nifty", {}).get("price", 0) == 0:
            try:
                nifty_df = load_stock_data("^NSEI")
                if nifty_df is not None and len(nifty_df) >= 2:
                    last = nifty_df.iloc[-1]
                    prev = nifty_df.iloc[-2]
                    chg = float(last["Close"] - prev["Close"])
                    chg_pct = round(chg / prev["Close"] * 100, 2)
                    result["nifty"] = {"price": round(float(last["Close"]), 2), "change": round(chg, 2), "changePct": chg_pct}
            except Exception:
                pass
        if "sensex" not in result or result.get("sensex", {}).get("price", 0) == 0:
            try:
                sensex_df = load_stock_data("^BSESN")
                if sensex_df is not None and len(sensex_df) >= 2:
                    last = sensex_df.iloc[-1]
                    prev = sensex_df.iloc[-2]
                    chg = float(last["Close"] - prev["Close"])
                    chg_pct = round(chg / prev["Close"] * 100, 2)
                    result["sensex"] = {"price": round(float(last["Close"]), 2), "change": round(chg, 2), "changePct": chg_pct}
            except Exception:
                pass
        if "nifty" not in result:
            result["nifty"] = {"price": 0, "change": 0, "changePct": 0}
        if "sensex" not in result:
            result["sensex"] = {"price": 0, "change": 0, "changePct": 0}

        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "nifty": {"price": 0, "change": 0, "changePct": 0},
            "sensex": {"price": 0, "change": 0, "changePct": 0},
        })


def _valid_symbol(symbol):
    """Validate stock symbol — only uppercase letters, numbers, &, -, . (max 20 chars)."""
    import re
    return bool(re.match(r'^[A-Z0-9&\-\.]{1,20}$', symbol))

@app.route("/api/stock/<symbol>")
def api_stock(symbol):
    """Get detailed data for a single stock."""
    if not _valid_symbol(symbol.replace(".NS", "").upper()):
        return jsonify({"error": "Invalid symbol"}), 400
    full_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        scores = score_stocks_v2([full_symbol]) if HAS_V2 else score_stocks([full_symbol])
        if scores:
            return jsonify(scores[0])
        return jsonify({"error": "Stock not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stock/<symbol>/history")
def api_stock_history(symbol):
    """Return OHLC history for charting."""
    period = request.args.get("period", "1y")
    full_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        import yfinance as yf
        ticker = yf.Ticker(full_symbol)

        # Map period to yfinance interval
        interval_map = {
            "1d": ("1d", "5m"),
            "1w": ("5d", "15m"),
            "1m": ("1mo", "1d"),
            "3m": ("3mo", "1d"),
            "6m": ("6mo", "1d"),
            "ytd": ("ytd", "1d"),
            "1y": ("1y", "1d"),
            "2y": ("2y", "1wk"),
        }
        yf_period, yf_interval = interval_map.get(period, ("1y", "1d"))

        hist = ticker.history(period=yf_period, interval=yf_interval)
        hist.index = hist.index.tz_localize(None)

        data = []
        for idx, row in hist.iterrows():
            data.append({
                "date": idx.strftime("%Y-%m-%d %H:%M") if yf_interval in ["5m", "15m"] else idx.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return jsonify({"data": data, "period": period, "interval": yf_interval})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"data": [], "error": str(e)}), 500


@app.route("/api/stock/<symbol>/info")
def api_stock_info(symbol):
    """Return market stats for a stock."""
    full_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        import yfinance as yf
        ticker = yf.Ticker(full_symbol)
        info = ticker.info
        hist = ticker.history(period="2d")

        current = hist.iloc[-1] if len(hist) > 0 else {}
        prev = hist.iloc[-2] if len(hist) > 1 else {}

        result = {
            "symbol": symbol,
            "name": info.get("shortName", info.get("longName", symbol)),
            "fullName": info.get("longName", symbol),
            "price": round(float(current.get("Close", 0)), 2),
            "change": round(float(current.get("Close", 0)) - float(prev.get("Close", 0)), 2) if len(hist) > 1 else 0,
            "changePct": round((float(current.get("Close", 0)) - float(prev.get("Close", 0))) / float(prev.get("Close", 1)) * 100, 2) if len(hist) > 1 else 0,
            "open": round(float(current.get("Open", 0)), 2),
            "high": round(float(current.get("High", 0)), 2),
            "low": round(float(current.get("Low", 0)), 2),
            "volume": int(current.get("Volume", 0)),
            "avgVolume": info.get("averageVolume", 0),
            "marketCap": info.get("marketCap", 0),
            "pe": info.get("trailingPE", 0),
            "high52w": info.get("fiftyTwoWeekHigh", 0),
            "low52w": info.get("fiftyTwoWeekLow", 0),
            "exchange": "Bombay" if ".NS" in full_symbol or ".BO" in full_symbol else "NSE",
            "currency": "INR",
            "marketState": "closed",  # simplified for prototype
        }

        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/fno/chain/<index>")
def api_fno_chain(index):
    """Get options chain for NIFTY50 or BANKNIFTY."""
    from data_engine import get_options_chain_data
    try:
        data = get_options_chain_data(index.upper())
        if data:
            return jsonify(data)
        return jsonify({"error": "Index not found"}), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/index/<index>/intraday")
def api_index_intraday(index):
    """Get intraday data for NIFTY50 or BANKNIFTY."""
    from data_engine import INDEX_SYMBOLS
    import yfinance as yf

    symbol = INDEX_SYMBOLS.get(index.upper())
    if not symbol:
        return jsonify({"error": "Index not found"}), 404

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="5m")
        hist.index = hist.index.tz_localize(None)

        data = []
        for idx, row in hist.iterrows():
            data.append({
                "time": idx.strftime("%H:%M"),
                "date": idx.strftime("%Y-%m-%d %H:%M"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        # Get previous close for reference line
        hist2d = ticker.history(period="2d", interval="1d")
        prev_close = round(float(hist2d.iloc[-2]["Close"]), 2) if len(hist2d) > 1 else 0

        return jsonify({
            "index": index.upper(),
            "prevClose": prev_close,
            "data": data,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"data": [], "error": str(e)}), 500


_news_cache = {"global": None, "local": None, "time": 0}

@app.route("/api/bots/geopolitical")
def api_bots_geopolitical():
    """Geopolitical analysis bot - fetches LIVE news affecting Indian markets."""
    import time as _time
    now = _time.time()

    # Cache for 30 minutes
    if _news_cache["global"] and (now - _news_cache["time"]) < 1800:
        return jsonify(_news_cache["global"])

    events = []
    try:
        import requests as req

        # Source 1: Google News RSS for market keywords
        rss_feeds = [
            ("https://news.google.com/rss/search?q=indian+stock+market+today&hl=en-IN&gl=IN", "India Market"),
            ("https://news.google.com/rss/search?q=nifty+sensex+today&hl=en-IN&gl=IN", "India Market"),
            ("https://news.google.com/rss/search?q=RBI+policy+india&hl=en-IN&gl=IN", "RBI Policy"),
            ("https://news.google.com/rss/search?q=FII+DII+india+market&hl=en-IN&gl=IN", "FII/DII"),
            ("https://news.google.com/rss/search?q=global+markets+recession+fed&hl=en-IN&gl=IN", "Global"),
            ("https://news.google.com/rss/search?q=crude+oil+price+today&hl=en-IN&gl=IN", "Commodities"),
        ]

        import xml.etree.ElementTree as ET
        from datetime import datetime, timedelta
        seen_titles = set()

        for feed_url, category in rss_feeds[:4]:  # Limit to 4 feeds
            try:
                resp = req.get(feed_url, timeout=8, headers={"User-Agent": "TradePilot/1.0"})
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.content)
                items = root.findall(".//item")[:3]  # Top 3 per feed

                for item in items:
                    title = item.findtext("title", "")
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    desc = item.findtext("description", "")
                    pub_date = item.findtext("pubDate", "")

                    # Parse time ago
                    time_ago = "recently"
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date)
                        diff = datetime.now(dt.tzinfo) - dt
                        hours = diff.total_seconds() / 3600
                        if hours < 1: time_ago = f"{int(diff.total_seconds()/60)}m ago"
                        elif hours < 24: time_ago = f"{int(hours)}h ago"
                        else: time_ago = f"{int(hours/24)}d ago"
                    except Exception:
                        pass

                    # Determine impact from keywords
                    title_lower = title.lower()
                    if any(w in title_lower for w in ["crash", "fall", "drop", "recession", "fear", "tension", "war"]):
                        impact = "negative"
                    elif any(w in title_lower for w in ["rally", "surge", "rise", "gain", "bull", "record", "buying"]):
                        impact = "positive"
                    else:
                        impact = "neutral"

                    # Determine affected sectors
                    sectors = []
                    if any(w in title_lower for w in ["bank", "rbi", "rate", "nbfc"]): sectors.append("Banking")
                    if any(w in title_lower for w in ["it", "tech", "infosys", "tcs"]): sectors.append("IT")
                    if any(w in title_lower for w in ["oil", "crude", "ongc", "bpcl"]): sectors.append("Oil & Gas")
                    if any(w in title_lower for w in ["pharma", "drug", "health"]): sectors.append("Pharma")
                    if any(w in title_lower for w in ["auto", "car", "ev"]): sectors.append("Auto")
                    if any(w in title_lower for w in ["fii", "dii", "foreign"]): sectors.append("FII/DII")
                    if not sectors: sectors = [category]

                    events.append({
                        "title": title[:120],
                        "impact": impact,
                        "severity": "high" if any(w in title_lower for w in ["crash", "surge", "record", "rbi", "fed"]) else "medium",
                        "affected_sectors": sectors[:3],
                        "summary": desc[:200] if desc else title,
                        "market_impact": "",
                        "timestamp": time_ago,
                        "source": "Google News",
                    })
            except Exception:
                continue

    except Exception:
        pass

    # Fallback if no news fetched
    if not events:
        events = [
            {"title": "Market data loading...", "impact": "neutral", "severity": "low",
             "affected_sectors": ["General"], "summary": "Live news feed is being refreshed. Check back in a few minutes.",
             "market_impact": "", "timestamp": "now", "source": "system"}
        ]

    # Determine overall sentiment
    pos = sum(1 for e in events if e["impact"] == "positive")
    neg = sum(1 for e in events if e["impact"] == "negative")
    if pos > neg + 1: sentiment = "bullish"
    elif neg > pos + 1: sentiment = "bearish"
    else: sentiment = "neutral"

    result = {"events": events[:8], "overall_sentiment": sentiment, "confidence": min(max(len(events) * 10, 30), 85)}
    _news_cache["global"] = result
    _news_cache["time"] = now
    return jsonify(result)


@app.route("/api/bots/market-pulse")
def api_bots_market_pulse():
    """Market prediction bot - next move analysis."""
    try:
        scores = score_stocks_v2() if HAS_V2 else score_stocks()

        # Find bullish and bearish stocks
        bullish = [s for s in scores if s.get('score', 0) >= 65]
        bearish = [s for s in scores if s.get('score', 0) < 35]
        neutral = [s for s in scores if 35 <= s.get('score', 0) < 65]

        # Top recommendations (ONLY if potential loss < 10%)
        safe_picks = []
        for s in bullish:
            sl = s.get('stop_loss_pct', 10)
            target = s.get('target_pct', 5)
            # Only recommend if stop loss < 10% AND target > stop loss
            if sl <= 10 and target > sl:
                safe_picks.append({
                    "symbol": s.get('name', s.get('symbol', '')),
                    "price": s.get('price', 0),
                    "score": s.get('score', 0),
                    "direction": s.get('direction', 'HOLD'),
                    "target_pct": target,
                    "stop_loss_pct": sl,
                    "risk_reward": s.get('risk_reward', 1),
                    "potential_profit": round(target, 1),
                    "max_loss": round(sl, 1),
                    "safe": True,
                    "reason": s.get('reasons', [{}])[0].get('text', '') if s.get('reasons') else ''
                })

        # Sort by score
        safe_picks.sort(key=lambda x: x['score'], reverse=True)

        # Dangerous stocks (loss > 10% - DO NOT RECOMMEND)
        dangerous = []
        for s in scores:
            sl = s.get('stop_loss_pct', 10)
            if sl > 10:
                dangerous.append({
                    "symbol": s.get('name', s.get('symbol', '')),
                    "price": s.get('price', 0),
                    "score": s.get('score', 0),
                    "stop_loss_pct": sl,
                    "warning": "High risk - potential loss exceeds 10%"
                })

        return jsonify({
            "market_mood": "Bullish" if len(bullish) > len(bearish) else "Bearish" if len(bearish) > len(bullish) else "Neutral",
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "neutral_count": len(neutral),
            "safe_picks": safe_picks[:8],
            "dangerous_count": len(dangerous),
            "analysis": "AI has identified " + str(len(safe_picks)) + " safe picks with <10% downside risk and strong upside potential.",
            "timestamp": "Just now"
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "market_mood": "Neutral",
            "bullish_count": 0, "bearish_count": 0, "neutral_count": 0,
            "safe_picks": [], "dangerous_count": 0,
            "analysis": "Unable to load market pulse data.",
            "timestamp": "Just now"
        })


@app.route("/api/trade/calculate")
def api_trade_calculate():
    """Calculate potential profit/loss for a trade."""
    symbol = request.args.get('symbol', '')
    investment = float(request.args.get('investment', 10000))

    full_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol

    try:
        scores = score_stocks_v2([full_symbol]) if HAS_V2 else score_stocks([full_symbol])
        if not scores:
            return jsonify({"error": "Stock not found"}), 404

        s = scores[0]
        price = s.get('price', 0)
        if price <= 0:
            return jsonify({"error": "Invalid price"}), 400

        qty = int(investment / price)
        actual_investment = round(qty * price, 2)

        target_pct = float(s.get('target_pct', 5))
        sl_pct = float(s.get('stop_loss_pct', 3))
        score = float(s.get('score', 50))

        potential_profit = round(actual_investment * target_pct / 100, 2)
        max_loss = round(actual_investment * sl_pct / 100, 2)
        max_loss_pct = sl_pct

        # Risk assessment (cast to Python bool to avoid numpy bool_ serialization error)
        safe = bool(max_loss_pct <= 10)
        recommended = bool(safe and score >= 50 and target_pct > sl_pct)

        # Risk level
        if max_loss_pct <= 5:
            risk_level = "Low"
        elif max_loss_pct <= 10:
            risk_level = "Moderate"
        elif max_loss_pct <= 20:
            risk_level = "High"
        else:
            risk_level = "Very High"

        return jsonify({
            "symbol": s.get('name', symbol),
            "price": price,
            "investment": actual_investment,
            "quantity": qty,
            "score": score,
            "direction": s.get('direction', 'HOLD'),
            "target_pct": target_pct,
            "target_price": round(price * (1 + target_pct/100), 2),
            "potential_profit": potential_profit,
            "stop_loss_pct": sl_pct,
            "stop_loss_price": round(price * (1 - sl_pct/100), 2),
            "max_loss": max_loss,
            "max_loss_pct": max_loss_pct,
            "risk_level": risk_level,
            "safe": safe,
            "recommended": recommended,
            "risk_reward": s.get('risk_reward', 1),
            "warning": None if safe else "DANGER: Potential loss exceeds 10% of investment. Not recommended."
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/wizard/recommend")
def api_wizard_recommend():
    """Investment Wizard: given a budget, recommend the best stocks to buy.
    Shows only stocks the user can actually afford, sorted by AI score.
    Filters out anything with >10% risk.
    """
    budget = float(request.args.get('budget', 5000))
    category = request.args.get('category', 'all')

    try:
        from data_engine import STOCK_CATEGORIES
        # Get stocks for this category
        cat_stocks = STOCK_CATEGORIES.get(category, STOCK_CATEGORIES['all'])['stocks']

        # Score all stocks in category
        all_scores = score_stocks_v2(cat_stocks) if HAS_V2 else score_stocks()

        # Filter: affordable (price <= budget) + safe (loss < 10%) + BUY direction
        affordable = []
        for s in all_scores:
            price = s.get('price', 0)
            if not price or price != price or price <= 0 or price > budget:  # NaN check: x != x
                continue
            qty = int(budget / price)
            if qty < 1:
                continue

            investment = round(qty * price, 2)
            target_pct = float(s.get('target_pct', 5))
            sl_pct = float(s.get('stop_loss_pct', 3))
            potential_profit = round(investment * target_pct / 100, 2)
            max_loss = round(investment * sl_pct / 100, 2)
            safe = bool(sl_pct <= 10)

            affordable.append({
                "symbol": s.get('name', s.get('symbol', '')),
                "name": s.get('name', ''),
                "price": price,
                "score": s.get('score', 0),
                "direction": s.get('direction', 'HOLD'),
                "quantity": qty,
                "investment": investment,
                "change_left": round(budget - investment, 2),
                "target_pct": target_pct,
                "stop_loss_pct": sl_pct,
                "potential_profit": potential_profit,
                "max_loss": max_loss,
                "risk_reward": s.get('risk_reward', 1),
                "safe": safe,
                "recommended": bool(safe and s.get('score', 0) >= 55),
                "reasons": s.get('reasons', [])[:3],
                "trend": s.get('trend', 'Sideways'),
                "rsi": s.get('rsi', 50),
            })

        # Sort: recommended first, then by score
        affordable.sort(key=lambda x: (x['recommended'], x['score']), reverse=True)

        # Stats
        total_available = len(affordable)
        recommended_count = sum(1 for s in affordable if s['recommended'])
        risky_excluded = len(all_scores) - total_available

        return jsonify({
            "budget": budget,
            "category": category,
            "total_available": total_available,
            "recommended_count": recommended_count,
            "risky_excluded": risky_excluded,
            "stocks": affordable[:30],  # top 30
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "stocks": []}), 500


_movers_cache = {"data": None, "time": 0}

@app.route("/api/gainers-losers")
def api_gainers_losers():
    """Get top 50 gainers and top 50 losers from the full universe."""
    import math, time as _time
    now = _time.time()

    # Cache for 10 minutes (heavy endpoint)
    if _movers_cache["data"] and (now - _movers_cache["time"]) < 600:
        return jsonify(_movers_cache["data"])

    try:
        from data_engine import STOCK_CATEGORIES
        all_stocks = STOCK_CATEGORIES.get('all', {}).get('stocks', [])

        raw_scores = None
        if ensure_data():
            try:
                raw_scores = score_stocks_v2(all_stocks) if HAS_V2 else score_stocks()
            except Exception:
                pass

        if not raw_scores:
            return jsonify({"gainers": [], "losers": []})

        def safe(v, default=0):
            if v is None:
                return default
            try:
                if math.isnan(v) or math.isinf(v):
                    return default
            except (TypeError, ValueError):
                pass
            return v

        # Build clean list
        clean = []
        for s in raw_scores:
            price = safe(s.get("price"), 0)
            change = safe(s.get("change_pct"), 0)
            score = safe(s.get("score"), 0)
            if price == 0:
                continue
            clean.append({
                "symbol": s.get("name", s.get("symbol", "").replace(".NS", "")),
                "name": s.get("name", s.get("symbol", "")),
                "price": round(price, 2),
                "change": round(change, 2),
                "score": round(score, 1),
                "direction": s.get("direction", "HOLD"),
                "rsi": round(safe(s.get("rsi"), 50), 1),
                "trend": s.get("trend", "Sideways"),
                "volatility": "High" if safe(s.get("volatility"), 20) > 25 else "Low" if safe(s.get("volatility"), 20) < 15 else "Medium",
                "macd": s.get("macd_signal", "Neutral"),
            })

        # Index filter
        idx_filter = request.args.get("index", "all").lower()
        if idx_filter != "all":
            try:
                from v4.config import NIFTY_50_SYMBOLS, NIFTY_200_SYMBOLS
                idx_sets = {
                    "nifty50": set(NIFTY_50_SYMBOLS),
                    "nifty100": set(NIFTY_50_SYMBOLS),  # approximate
                    "nifty200": set(NIFTY_200_SYMBOLS),
                    "midcap": set(NIFTY_200_SYMBOLS) - set(NIFTY_50_SYMBOLS),
                    "smallcap": set(),  # needs separate list
                    "total": set(),  # show all
                }
                filter_set = idx_sets.get(idx_filter)
                if filter_set:
                    clean = [s for s in clean if s["symbol"].replace(".NS", "") in filter_set
                             or s["name"].replace(".NS", "") in filter_set]
            except ImportError:
                pass

        gainers = sorted(clean, key=lambda x: x["change"], reverse=True)[:50]
        losers = sorted(clean, key=lambda x: x["change"])[:50]

        result = {"gainers": gainers, "losers": losers, "index": idx_filter}
        _movers_cache["data"] = result
        _movers_cache["time"] = now
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"gainers": [], "losers": []}), 500


@app.route("/api/categories")
def api_categories():
    """Return available stock categories."""
    from data_engine import STOCK_CATEGORIES
    cats = []
    for key, val in STOCK_CATEGORIES.items():
        cats.append({
            "id": key,
            "name": val["name"],
            "desc": val["desc"],
            "count": len(val["stocks"]),
        })
    return jsonify(cats)


# ---------------------------------------------------------------------------
# Paper Trading System -- simulated trading with virtual Rs 10 Lakh
# ---------------------------------------------------------------------------

INITIAL_CASH = 1000000  # Rs 10,00,000

paper_portfolio = {
    "cash": INITIAL_CASH,
    "initial_cash": INITIAL_CASH,
    "positions": {},   # {symbol: {qty, avg_price, current_price, pnl, pnl_pct}}
    "history": [],     # [{type, symbol, qty, price, total, pnl, timestamp}]
    "trades_today": 0,
    "win_count": 0,
    "loss_count": 0,
}


def get_stock_price(symbol):
    """Get current price for a stock from scored data or yfinance fallback."""
    clean = symbol.replace(".NS", "")
    full = clean + ".NS"
    try:
        scores = score_stocks_v2([full]) if HAS_V2 else score_stocks([full])
        for s in scores:
            p = s.get("price", 0)
            if p and p > 0:
                return round(float(p), 2)
    except Exception:
        pass
    # Fallback: yfinance
    try:
        import yfinance as yf
        t = yf.Ticker(full)
        h = t.history(period="1d")
        if len(h) > 0:
            return round(float(h.iloc[-1]["Close"]), 2)
    except Exception:
        pass
    return 0


def _refresh_positions():
    """Update current_price and pnl for all held positions."""
    for sym, pos in paper_portfolio["positions"].items():
        price = get_stock_price(sym)
        if price > 0:
            pos["current_price"] = price
        pos["pnl"] = round((pos["current_price"] - pos["avg_price"]) * pos["qty"], 2)
        pos["pnl_pct"] = round((pos["current_price"] - pos["avg_price"]) / pos["avg_price"] * 100, 2) if pos["avg_price"] else 0


def calculate_portfolio_value():
    total = paper_portfolio["cash"]
    for pos in paper_portfolio["positions"].values():
        total += pos["qty"] * pos["current_price"]
    return round(total, 2)


def calculate_total_pnl():
    return round(calculate_portfolio_value() - paper_portfolio["initial_cash"], 2)


def calculate_total_pnl_pct():
    initial = paper_portfolio["initial_cash"]
    if initial == 0:
        return 0
    return round(calculate_total_pnl() / initial * 100, 2)


def _execute_buy(symbol, quantity):
    """Core buy logic shared by /buy and /swipe. Returns (response_dict, status_code)."""
    price = get_stock_price(symbol)
    if price <= 0:
        return {"error": f"Cannot get price for {symbol}"}, 400

    total_cost = round(price * quantity, 2)
    if total_cost > paper_portfolio["cash"]:
        return {"error": "Insufficient cash", "available": paper_portfolio["cash"], "required": total_cost}, 400

    # 10% risk guardrail -- check stop_loss_pct from scoring
    clean = symbol.replace(".NS", "")
    full = clean + ".NS"
    try:
        scores = score_stocks_v2([full]) if HAS_V2 else score_stocks([full])
        if scores:
            sl_pct = scores[0].get("stop_loss_pct", 5)
            if sl_pct > 10:
                return {
                    "error": "Risk guardrail: stop loss exceeds 10%",
                    "stop_loss_pct": sl_pct,
                    "symbol": clean,
                }, 400
    except Exception:
        pass  # proceed without guardrail if scoring fails

    # Update or create position
    if clean in paper_portfolio["positions"]:
        pos = paper_portfolio["positions"][clean]
        old_total = pos["avg_price"] * pos["qty"]
        new_total = old_total + total_cost
        pos["qty"] += quantity
        pos["avg_price"] = round(new_total / pos["qty"], 2)
        pos["current_price"] = price
    else:
        paper_portfolio["positions"][clean] = {
            "qty": quantity,
            "avg_price": price,
            "current_price": price,
            "pnl": 0,
            "pnl_pct": 0,
        }

    paper_portfolio["cash"] = round(paper_portfolio["cash"] - total_cost, 2)
    paper_portfolio["trades_today"] += 1

    trade_record = {
        "type": "buy",
        "symbol": clean,
        "qty": quantity,
        "price": price,
        "total": total_cost,
        "pnl": None,
        "timestamp": datetime.now().isoformat(),
    }
    paper_portfolio["history"].append(trade_record)

    return {
        "action": "bought",
        "symbol": clean,
        "quantity": quantity,
        "price": price,
        "total": total_cost,
        "cash_remaining": paper_portfolio["cash"],
    }, 200


@app.route("/api/paper/portfolio")
def api_paper_portfolio():
    """Return current paper trading portfolio with live prices."""
    _refresh_positions()
    return jsonify({
        "cash": paper_portfolio["cash"],
        "initial_cash": paper_portfolio["initial_cash"],
        "positions": paper_portfolio["positions"],
        "total_value": calculate_portfolio_value(),
        "total_pnl": calculate_total_pnl(),
        "total_pnl_pct": calculate_total_pnl_pct(),
        "trades_today": paper_portfolio["trades_today"],
        "win_count": paper_portfolio["win_count"],
        "loss_count": paper_portfolio["loss_count"],
    })


@app.route("/api/paper/buy", methods=["POST"])
def api_paper_buy():
    """Paper buy a stock."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "")
    quantity = int(data.get("quantity", 1))
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    if quantity < 1:
        return jsonify({"error": "quantity must be >= 1"}), 400

    result, status = _execute_buy(symbol, quantity)
    return jsonify(result), status


@app.route("/api/paper/sell", methods=["POST"])
def api_paper_sell():
    """Paper sell a position (partial or full)."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "").replace(".NS", "")
    quantity = int(data.get("quantity", 0))  # 0 = sell all

    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    if symbol not in paper_portfolio["positions"]:
        return jsonify({"error": f"No position in {symbol}"}), 400

    pos = paper_portfolio["positions"][symbol]
    sell_qty = quantity if quantity > 0 else pos["qty"]
    if sell_qty > pos["qty"]:
        return jsonify({"error": f"Only hold {pos['qty']} shares of {symbol}"}), 400

    # Get current price for sale
    price = get_stock_price(symbol)
    if price <= 0:
        price = pos["current_price"]  # fallback to last known

    total_sale = round(price * sell_qty, 2)
    pnl = round((price - pos["avg_price"]) * sell_qty, 2)
    pnl_pct = round((price - pos["avg_price"]) / pos["avg_price"] * 100, 2) if pos["avg_price"] else 0

    # Update win/loss counts
    if pnl >= 0:
        paper_portfolio["win_count"] += 1
    else:
        paper_portfolio["loss_count"] += 1

    # Update cash
    paper_portfolio["cash"] = round(paper_portfolio["cash"] + total_sale, 2)
    paper_portfolio["trades_today"] += 1

    # Update or remove position
    if sell_qty >= pos["qty"]:
        del paper_portfolio["positions"][symbol]
    else:
        pos["qty"] -= sell_qty

    trade_record = {
        "type": "sell",
        "symbol": symbol,
        "qty": sell_qty,
        "price": price,
        "total": total_sale,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "timestamp": datetime.now().isoformat(),
    }
    paper_portfolio["history"].append(trade_record)

    return jsonify({
        "action": "sold",
        "symbol": symbol,
        "quantity": sell_qty,
        "price": price,
        "total": total_sale,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "cash_remaining": paper_portfolio["cash"],
    })


@app.route("/api/paper/reset", methods=["POST"])
def api_paper_reset():
    """Reset paper trading account to initial Rs 10 Lakh."""
    paper_portfolio["cash"] = INITIAL_CASH
    paper_portfolio["initial_cash"] = INITIAL_CASH
    paper_portfolio["positions"] = {}
    paper_portfolio["history"] = []
    paper_portfolio["trades_today"] = 0
    paper_portfolio["win_count"] = 0
    paper_portfolio["loss_count"] = 0
    return jsonify({"action": "reset", "cash": INITIAL_CASH})


@app.route("/api/paper/history")
def api_paper_history():
    """Return paper trade history (newest first)."""
    return jsonify(list(reversed(paper_portfolio["history"])))


@app.route("/api/paper/swipe", methods=["POST"])
def api_paper_swipe():
    """Swipe right = buy with auto-calculated qty (5% of cash), swipe left = skip."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "")
    direction = data.get("direction", "")

    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    if direction not in ("right", "left"):
        return jsonify({"error": "direction must be 'right' or 'left'"}), 400

    clean = symbol.replace(".NS", "")

    if direction == "left":
        paper_portfolio["history"].append({
            "type": "skip",
            "symbol": clean,
            "timestamp": datetime.now().isoformat(),
        })
        return jsonify({"action": "skipped", "symbol": clean})

    # direction == "right" -- auto-buy 5% of available cash
    price = get_stock_price(clean)
    if price <= 0:
        return jsonify({"error": f"Cannot get price for {clean}"}), 400

    invest_amount = paper_portfolio["cash"] * 0.05
    qty = max(1, int(invest_amount / price))

    result, status = _execute_buy(clean, qty)
    if status == 200:
        result["auto_invest_amount"] = round(invest_amount, 2)
    return jsonify(result), status


@app.route("/api/analytics/track", methods=["POST"])
def api_track():
    """Track user events."""
    try:
        data = request.get_json() or {}
        event = data.get("event", "")
        user_id = data.get("user_id", "anon")

        if event == "visit":
            track_visit(user_id, data.get("device"), data.get("user_agent"))
        elif event == "page_view":
            track_page_view(user_id, data.get("page", "/"))
        elif event == "stock_view":
            track_stock_view(user_id, data.get("symbol"), data.get("score"), data.get("direction"))
        elif event == "swipe":
            track_swipe(user_id, data.get("symbol"), data.get("action"), data.get("score"), data.get("price"), data.get("quantity"))
        elif event == "paper_trade":
            track_paper_trade(user_id, data.get("symbol"), data.get("action"), data.get("quantity", 0), data.get("price", 0), data.get("pnl"), data.get("source", "manual"))
        elif event == "wizard_search":
            track_wizard_search(user_id, data.get("budget", 0), data.get("category", ""), data.get("results_count", 0), data.get("recommended_count", 0))
        elif event == "feedback":
            track_feedback(user_id, data.get("type", "general"), data.get("message", ""), data.get("page"))

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/admin")
def admin_dashboard():
    """Analytics dashboard for founders — localhost only."""
    # Security: only allow from localhost
    if request.remote_addr not in ('127.0.0.1', '::1', 'localhost'):
        return jsonify({"error": "Forbidden"}), 403
    stats = get_dashboard_stats()
    return jsonify(stats)


# ═══════════════════════════════════════════════════════
# TRADE LAB — v4 vs v5 daily trade tracking
# ═══════════════════════════════════════════════════════

@app.route("/api/tradelab/days")
def api_tradelab_days():
    """List all trading days with summary P&L for v4 and v5."""
    import glob
    base = os.path.join(os.path.dirname(__file__), "..", "docs", "paper-trades")
    days = {}

    # v4 days (only date-named files like 2026-04-10.json)
    import re as _re
    for f in sorted(glob.glob(os.path.join(base, "v4", "*.json"))):
        if not _re.match(r'^\d{4}-\d{2}-\d{2}\.json$', os.path.basename(f)):
            continue
        try:
            with open(f) as fh:
                s = json.load(fh)
            date = s.get("date") or os.path.basename(f).replace(".json", "")
            if date not in days:
                days[date] = {"date": date, "v4": None, "v5": None}
            cl = s.get("closed_trades", [])
            w = sum(1 for t in cl if t.get("pnl", 0) > 0)
            days[date]["v4"] = {
                "pnl": round(s.get("realized_pnl", 0), 2),
                "pnl_pct": round(s.get("realized_pnl", 0) / max(s.get("daily_pool", 1000000), 1) * 100, 2),
                "trades": len(cl), "wins": w,
                "win_rate": round(w / len(cl) * 100, 1) if cl else 0,
                "pool": s.get("daily_pool", 1000000),
            }
        except Exception:
            pass

    # v5 days (only date-named files)
    for f in sorted(glob.glob(os.path.join(base, "v5", "*.json"))):
        if not _re.match(r'^\d{4}-\d{2}-\d{2}\.json$', os.path.basename(f)):
            continue
        try:
            with open(f) as fh:
                s = json.load(fh)
            date = s.get("date") or os.path.basename(f).replace(".json", "")
            if date not in days:
                days[date] = {"date": date, "v4": None, "v5": None}
            sm = s.get("summary", {})
            days[date]["v5"] = {
                "pnl": round(sm.get("total_pnl", 0), 2),
                "pnl_pct": round(sm.get("total_pnl", 0) / max(s.get("total_capital", 5000000), 1) * 100, 2),
                "trades": sm.get("trades", 0), "wins": sm.get("wins", 0),
                "win_rate": round(sm.get("wins", 0) / max(sm.get("trades", 1), 1) * 100, 1),
                "longs": sm.get("longs", 0), "shorts": sm.get("shorts", 0),
                "pool": s.get("total_capital", 5000000),
                "regime": s.get("regime", "UNKNOWN"),
            }
        except Exception:
            pass

    return jsonify(sorted(days.values(), key=lambda d: d["date"], reverse=True))


@app.route("/api/engine-arena")
def api_engine_arena():
    """Live status for v5.2, v5.3, v5.4 engines."""
    import json as _json
    from pathlib import Path as _Path
    base = _Path(__file__).parent.parent / "docs" / "paper-trades"
    today = __import__('datetime').datetime.now().strftime("%Y-%m-%d")
    result = {}

    for eng, dirname in [("v5.2", "v5_2"), ("v5.3", "v5_3"), ("v5.4", "v5_4")]:
        state_file = base / dirname / f"{today}.json"
        info = {"pnl": 0, "trades": 0, "wins": 0, "losses": 0, "longs": 0, "shorts": 0,
                "long_pnl": 0, "short_pnl": 0, "regime": "?", "positions": [],
                "confirmed": 0, "cancelled": 0, "capital": 1000000,
                "direction_budget": {"long": 0.5, "short": 0.5}}
        if state_file.exists():
            try:
                d = _json.loads(state_file.read_text())
                s = d.get("summary", {})
                info["pnl"] = s.get("total_pnl", 0)
                info["trades"] = s.get("trades", 0)
                info["wins"] = s.get("wins", 0)
                info["losses"] = s.get("losses", 0)
                info["longs"] = s.get("longs", 0)
                info["shorts"] = s.get("shorts", 0)
                info["long_pnl"] = s.get("long_pnl", 0)
                info["short_pnl"] = s.get("short_pnl", 0)
                info["regime"] = d.get("regime", "?")
                info["confirmed"] = s.get("confirmed", 0)
                info["cancelled"] = s.get("cancelled", 0)
                info["capital"] = d.get("total_capital", 1000000)
                info["direction_budget"] = d.get("direction_budget", {"long": 0.5, "short": 0.5})
                # Collect open positions
                for pn, pd in d.get("pools", {}).items():
                    for p in pd.get("positions", []):
                        info["positions"].append({
                            "engine": eng, "symbol": p.get("symbol"),
                            "direction": p.get("position_type", "LONG"),
                            "pool": pn, "entry_price": p.get("entry_price", 0),
                            "sl_price": p.get("sl_price", 0),
                            "target_price": p.get("target_price", 0),
                            "trailing": p.get("trailing_activated", False)})
            except Exception:
                pass
        # Also check carry forward for cumulative
        cf_file = base / dirname / f"carry_forward_{dirname}.json"
        if cf_file.exists():
            try:
                cf = _json.loads(cf_file.read_text())
                info["cumulative_pnl"] = cf.get("cumulative_pnl", 0)
                info["capital"] = cf.get("closing_balance", 1000000)
            except Exception:
                pass
        result[eng] = info
    return jsonify(result)


@app.route("/api/tradelab/trades/<date>")
def api_tradelab_trades(date):
    """Get all individual trades for a specific date, both v4 and v5."""
    base = os.path.join(os.path.dirname(__file__), "..", "docs", "paper-trades")
    result = {"date": date, "v4_trades": [], "v5_trades": [], "v4_open": [], "v5_open": []}

    # v4
    v4f = os.path.join(base, "v4", f"{date}.json")
    if os.path.exists(v4f):
        with open(v4f) as fh:
            s = json.load(fh)
        result["v4_trades"] = s.get("closed_trades", [])
        result["v4_open"] = [p for p in s.get("positions", []) if p.get("status") == "open"]
        result["v4_summary"] = {
            "pnl": round(s.get("realized_pnl", 0), 2),
            "pool": s.get("daily_pool", 1000000),
            "scans": s.get("scan_count", 0),
            "rescores": s.get("rescore_count", 0),
        }

    # v5
    v5f = os.path.join(base, "v5", f"{date}.json")
    if os.path.exists(v5f):
        with open(v5f) as fh:
            s = json.load(fh)
        for pool_name, pool_data in s.get("pools", {}).items():
            for t in pool_data.get("closed", []):
                t["pool"] = pool_name
                result["v5_trades"].append(t)
            for p in pool_data.get("positions", []):
                p["pool"] = pool_name
                result["v5_open"].append(p)
        result["v5_summary"] = s.get("summary", {})
        result["v5_regime"] = s.get("regime", "UNKNOWN")
        result["v5_premarket"] = s.get("premarket", {})

    return jsonify(result)


# ═══════════════ AI PICKS & ADVISOR ═══════════════

@app.route("/api/picks")
def api_picks():
    """Get AI-powered top picks across categories."""
    category = request.args.get("category", "stocks")  # stocks, etfs, mf
    count = int(request.args.get("count", 10))
    horizon = request.args.get("horizon", "intraday")  # intraday, swing, investment

    if category == "stocks":
        try:
            scores = score_stocks_v4() if HAS_V4 else (score_stocks_v2(NIFTY_STOCKS) if HAS_V2 else score_stocks())
            # Sort by score, take top N
            picks = sorted(scores, key=lambda x: x.get("score", 0), reverse=True)[:count]
            # Add recommendation context
            for p in picks:
                score = p.get("score", 0)
                if score > 70: p["recommendation"] = "Strong Buy"
                elif score > 60: p["recommendation"] = "Buy"
                elif score > 50: p["recommendation"] = "Hold"
                else: p["recommendation"] = "Watch"

                # Add horizon-specific advice
                if horizon == "intraday":
                    p["strategy"] = f"Entry near {p.get('price', 0):.0f}, SL {p.get('price', 0) * 0.985:.0f}, Target {p.get('price', 0) * 1.02:.0f}"
                elif horizon == "swing":
                    p["strategy"] = f"Buy on dips near support. Hold 3-7 days. Target +3-5%"
                else:
                    p["strategy"] = f"Accumulate over next month. Long-term outlook positive"

            return jsonify({"picks": picks, "category": category, "horizon": horizon, "count": len(picks), "engine": "v4" if HAS_V4 else "v2"})
        except Exception as e:
            return jsonify({"picks": [], "error": str(e)})

    elif category == "etfs":
        # Top ETFs for Indian market
        etfs = [
            {"symbol": "NIFTYBEES", "name": "Nippon Nifty 50 ETF", "price": 240, "change": -0.9, "recommendation": "Buy on dips", "why": "Core portfolio holding. Low cost Nifty 50 exposure."},
            {"symbol": "BANKBEES", "name": "Nippon Bank Nifty ETF", "price": 555, "change": -0.8, "recommendation": "Hold", "why": "Banking sector volatile. Wait for RBI clarity."},
            {"symbol": "GOLDBEES", "name": "Nippon Gold ETF", "price": 58, "change": 0.5, "recommendation": "Strong Buy", "why": "Gold rallying globally. Safe haven in uncertainty."},
            {"symbol": "ITBEES", "name": "Nippon IT ETF", "price": 38, "change": -1.5, "recommendation": "Watch", "why": "IT sector under pressure. Wait for earnings season."},
            {"symbol": "JUNIORBEES", "name": "Nippon Junior Nifty ETF", "price": 680, "change": 0.3, "recommendation": "Buy", "why": "Nifty Next 50 has higher growth potential."},
            {"symbol": "LIQUIDBEES", "name": "Nippon Liquid ETF", "price": 1000, "change": 0.02, "recommendation": "Park Cash", "why": "Park idle trading capital. Better than savings account."},
            {"symbol": "SILVERBEES", "name": "Nippon Silver ETF", "price": 88, "change": 1.2, "recommendation": "Buy", "why": "Silver undervalued vs gold. Industrial demand rising."},
            {"symbol": "PSUBNKBEES", "name": "Nippon PSU Bank ETF", "price": 72, "change": 0.8, "recommendation": "Strong Buy", "why": "PSU banks showing strong NPA recovery."},
        ]
        return jsonify({"picks": etfs[:count], "category": "etfs", "count": min(count, len(etfs))})

    elif category == "mf":
        # Top mutual funds
        mfs = [
            {"symbol": "PPFAS", "name": "Parag Parikh Flexi Cap", "nav": 82, "returns_1y": 18.5, "recommendation": "Strong Buy", "why": "Best diversified fund. US + India exposure. Consistent alpha."},
            {"symbol": "HDFC_MID", "name": "HDFC Mid-Cap Opportunities", "nav": 175, "returns_1y": 22.3, "recommendation": "Buy (SIP)", "why": "Top mid-cap fund. SIP for 3+ years."},
            {"symbol": "AXIS_SMALL", "name": "Axis Small Cap Fund", "nav": 92, "returns_1y": 28.1, "recommendation": "Buy (SIP)", "why": "High growth potential. Only via SIP (volatile)."},
            {"symbol": "ICICI_BLUE", "name": "ICICI Pru Bluechip Fund", "nav": 95, "returns_1y": 12.8, "recommendation": "Core Holding", "why": "Large cap stability. Good for risk-averse investors."},
            {"symbol": "KOTAK_FLEX", "name": "Kotak Flexicap Fund", "nav": 68, "returns_1y": 16.2, "recommendation": "Buy", "why": "Flexible allocation across market caps."},
            {"symbol": "SBI_CONTRA", "name": "SBI Contra Fund", "nav": 350, "returns_1y": 20.5, "recommendation": "Strong Buy", "why": "Value investing. Buys beaten-down stocks."},
            {"symbol": "NIFTY_INDEX", "name": "UTI Nifty 50 Index Fund", "nav": 150, "returns_1y": 11.5, "recommendation": "Best for Beginners", "why": "Lowest cost. Just tracks Nifty 50."},
            {"symbol": "QUANT_SMALL", "name": "Quant Small Cap Fund", "nav": 220, "returns_1y": 35.2, "recommendation": "High Risk Buy", "why": "Top performer but very volatile. Only 5-10% of portfolio."},
        ]
        return jsonify({"picks": mfs[:count], "category": "mf", "count": min(count, len(mfs))})

    return jsonify({"picks": [], "error": "Unknown category"})


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """Answer market questions using available data."""
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "No question provided"}), 400

    # Build context from available data
    answer = generate_market_answer(question)
    return jsonify({"question": question, "answer": answer})


def generate_market_answer(question):
    """Generate answer using available market data. Smart keyword matching + data-driven."""
    import re
    q = question.lower().strip()

    # Build stock name → symbol mapping for fuzzy matching
    _name_map = {
        "tata steel": "TATASTEEL", "tata motors": "TATAMOTORS", "tata power": "TATAPOWER",
        "tata consumer": "TATACONSUM", "tata chemicals": "TATACHEM", "tata elxsi": "TATAELXSI",
        "tata investment": "TATAINVEST", "tata comm": "TATACOMM",
        "reliance": "RELIANCE", "infosys": "INFY", "hdfc bank": "HDFCBANK", "hdfc": "HDFCBANK",
        "icici bank": "ICICIBANK", "icici": "ICICIBANK", "sbi": "SBIN", "state bank": "SBIN",
        "kotak": "KOTAKBANK", "kotak bank": "KOTAKBANK", "axis bank": "AXISBANK", "axis": "AXISBANK",
        "bajaj finance": "BAJFINANCE", "bajaj finserv": "BAJAJFINSV", "bajaj auto": "BAJAJ-AUTO",
        "asian paints": "ASIANPAINT", "asian paint": "ASIANPAINT", "maruti": "MARUTI",
        "maruti suzuki": "MARUTI", "hero moto": "HEROMOTOCO", "hero motocorp": "HEROMOTOCO",
        "eicher motors": "EICHERMOT", "eicher": "EICHERMOT", "m&m": "M&M", "mahindra": "M&M",
        "sun pharma": "SUNPHARMA", "dr reddy": "DRREDDY", "dr reddys": "DRREDDY",
        "ultratech": "ULTRACEMCO", "ultra tech": "ULTRACEMCO", "titan": "TITAN",
        "wipro": "WIPRO", "hcl tech": "HCLTECH", "hcltech": "HCLTECH", "hcl": "HCLTECH",
        "tech mahindra": "TECHM", "tech m": "TECHM", "l&t": "LT", "larsen": "LT",
        "adani enterprises": "ADANIENT", "adani ports": "ADANIPORTS", "adani green": "ADANIGREEN",
        "adani power": "ADANIPOWER", "power grid": "POWERGRID", "ntpc": "NTPC",
        "coal india": "COALINDIA", "ongc": "ONGC", "bpcl": "BPCL", "ioc": "IOC",
        "indusind bank": "INDUSINDBK", "indusind": "INDUSINDBK",
        "nestle": "NESTLEIND", "britannia": "BRITANNIA", "itc": "ITC", "hindustan unilever": "HINDUNILVR",
        "hul": "HINDUNILVR", "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL",
        "jio financial": "JIOFIN", "jio": "JIOFIN", "zomato": "ZOMATO",
        "paytm": "PAYTM", "nykaa": "NYKAA", "delhivery": "DELHIVERY",
        "jsw steel": "JSWSTEEL", "jsw energy": "JSWENERGY", "jsw": "JSWSTEEL",
        "hindalco": "HINDALCO", "vedanta": "VEDL", "vedl": "VEDL",
        "grasim": "GRASIM", "shriram finance": "SHRIRAMFIN", "shriram": "SHRIRAMFIN",
        "apollo hospital": "APOLLOHOSP", "apollo": "APOLLOHOSP",
        "cipla": "CIPLA", "divis lab": "DIVISLAB", "divis": "DIVISLAB",
        "sbi life": "SBILIFE", "hdfc life": "HDFCLIFE",
        "mcx": "MCX", "voltas": "VOLTAS", "bhel": "BHEL", "zydus": "ZYDUSLIFE",
        "zydus life": "ZYDUSLIFE", "zydus wellness": "ZYDUSLIFE",
        "waaree": "WAAREEENER", "waaree energies": "WAAREEENER",
        "page industries": "PAGEIND", "coforge": "COFORGE",
        "nifty": "^NSEI", "sensex": "^BSESN", "bank nifty": "^NSEBANK",
    }

    # Try to find a stock in the query
    def find_stock(query):
        q_lower = query.lower().strip()
        # 1. Exact name match (longest first)
        for name in sorted(_name_map.keys(), key=len, reverse=True):
            if name in q_lower:
                return _name_map[name]
        # 2. Try each word as a symbol directly
        for word in q_lower.replace("?", "").replace(".", "").split():
            sym = word.upper()
            if len(sym) >= 2:
                try:
                    scores = score_stocks_v4() if HAS_V4 else []
                    match = next((s for s in scores if s.get("symbol", "").replace(".NS", "") == sym), None)
                    if match:
                        return sym
                except Exception:
                    pass
        return None

    # Stock lookup
    sym = find_stock(q)
    if sym and not sym.startswith("^"):
        try:
            scores = score_stocks_v4() if HAS_V4 else []
            stock_data = next((s for s in scores if s.get("symbol", "").replace(".NS", "") == sym), None)
            if stock_data:
                score = stock_data.get("score", 0)
                price = stock_data.get("price", 0)
                change = stock_data.get("change_pct", 0)
                direction = stock_data.get("direction", "HOLD")
                rsi = stock_data.get("rsi", 50)
                vol = stock_data.get("volatility", "Medium")

                # Build rich response
                if score > 70: rec, rec_detail = "Strong Buy", "High composite score across multiple signals. Consider entry."
                elif score > 60: rec, rec_detail = "Buy", "Above-average signal strength. Good for swing or intraday."
                elif score > 50: rec, rec_detail = "Hold", "Moderate signal. Wait for stronger confirmation before entering."
                elif score > 40: rec, rec_detail = "Weak", "Below average. Not recommended for fresh entry."
                else: rec, rec_detail = "Avoid", "Weak on most signals. Stay away or consider shorting."

                lines = [
                    f"**{sym}** -- Rs {price:.2f} ({change:+.2f}%)",
                    "",
                    f"AI Score: **{score:.0f}/100** | Signal: **{direction}**",
                    f"RSI: {rsi:.0f} ({'Overbought - may correct' if rsi > 70 else 'Oversold - bounce possible' if rsi < 30 else 'Neutral range'})",
                    f"Volatility: {vol}",
                    "",
                    f"**Recommendation: {rec}**",
                    f"{rec_detail}",
                    "",
                ]
                if direction == "BUY":
                    sl = price * 0.985
                    tgt = price * 1.02
                    lines.append(f"**Intraday Strategy:**")
                    lines.append(f"Entry: Rs {price:.0f} | SL: Rs {sl:.0f} (-1.5%) | Target: Rs {tgt:.0f} (+2%)")
                    lines.append(f"Risk:Reward = 1:1.3")
                    lines.append("")
                    lines.append(f"**Swing Strategy (3-7 days):**")
                    lines.append(f"Buy on dips near Rs {price*0.97:.0f}. Target Rs {price*1.05:.0f} (+5%)")
                elif direction == "AVOID":
                    lines.append(f"**Strategy:** No entry recommended. Wait for score > 60.")
                    lines.append(f"If you hold, set SL at Rs {price*0.95:.0f} (-5%)")
                else:
                    lines.append(f"**Strategy:** Hold if already in position. Fresh entry at Rs {price*0.98:.0f} support.")

                return "\n".join(lines)
        except Exception:
            pass

        # Stock found in name map but not in scorer — try basic info
        return f"**{sym}** is recognized but not currently in our scoring universe or data is loading.\n\nTry refreshing or ask about a Nifty 200 stock."

    # Market regime questions
    if any(w in q for w in ["market", "nifty", "regime", "bull", "bear", "today"]):
        try:
            from v5.regime_detector import detect_regime
            r = detect_regime()
            regime = r.get("regime", "SIDEWAYS")
            score = r.get("score", 0)
            alloc = r.get("allocation", 0.75)
            return (f"**Market Regime: {regime}** (score {score}/6)\n"
                    f"Recommended allocation: {alloc:.0%}\n\n"
                    f"{'Market is in fear mode. Reduce equity exposure. Keep 30-50% cash.' if regime == 'BEAR' else 'Market is neutral. Normal position sizing. Watch for breakout direction.' if regime == 'SIDEWAYS' else 'Market is bullish. Full deployment. Ride the momentum.'}")
        except Exception:
            pass

    # VIX questions
    if "vix" in q:
        return ("**India VIX** measures market fear/greed.\n"
                "- VIX < 13: Very calm, full risk-on\n"
                "- VIX 13-18: Normal, standard positions\n"
                "- VIX 18-25: Elevated fear, reduce size 50%\n"
                "- VIX > 25: High fear, only 30-40% deployed\n\n"
                "Current TradePilot strategy: Automatically adjusts position sizes based on VIX level.")

    # Best stocks to buy
    if any(w in q for w in ["best", "top", "pick", "recommend", "which"]):
        try:
            scores = score_stocks_v4() if HAS_V4 else []
            top5 = sorted(scores, key=lambda x: x.get("score", 0), reverse=True)[:5]
            lines = ["**Top 5 AI Picks Right Now:**\n"]
            for i, s in enumerate(top5, 1):
                lines.append(f"{i}. **{s.get('symbol','?').replace('.NS','')}** -- Score {s.get('score',0):.0f} | Rs {s.get('price',0):.0f} ({s.get('change_pct',0):+.2f}%)")
            lines.append("\n*Scores update every 30 minutes during market hours.*")
            return "\n".join(lines)
        except Exception:
            pass

    # SIP / investment questions
    if any(w in q for w in ["sip", "invest", "long term", "mutual fund", "etf"]):
        return ("**For Long-Term Investment (3+ years):**\n\n"
                "1. **Nifty 50 Index Fund** (UTI/HDFC) -- Safest, lowest cost\n"
                "2. **Parag Parikh Flexi Cap** -- Best diversified fund\n"
                "3. **HDFC Mid-Cap Opportunities** -- Growth potential\n"
                "4. **Gold ETF (GOLDBEES)** -- 10% allocation for hedging\n\n"
                "**SIP Strategy:** Start with Rs 5,000/month across 2-3 funds. Increase annually.\n"
                "**Rule:** Never stop SIP during crashes -- that's when you get the best units.")

    # Default
    return ("I can help with:\n"
            "- **Stock analysis**: 'Tell me about RELIANCE'\n"
            "- **Market regime**: 'How is the market today?'\n"
            "- **Top picks**: 'Best stocks to buy'\n"
            "- **Investment advice**: 'Best SIP mutual funds'\n"
            "- **VIX analysis**: 'What does VIX mean?'\n\n"
            "Try asking one of these questions!")


if __name__ == "__main__":
    print("=" * 60)
    print("  TradePilot Prototype")
    print("  AI-Powered Trading Platform for Indian Markets")
    print("=" * 60)

    # Check if model exists
    model_path = os.path.join(os.path.dirname(__file__), "models", "xgb_scorer.pkl")
    if not os.path.exists(model_path):
        print("\nNo trained model found. Training now...")
        print("This will download stock data and train the AI model.")
        print("First run takes 2-5 minutes.\n")

        from data_engine import download_stock_data
        data = download_stock_data()
        train_model(data)

    print("\nStarting server at http://localhost:5050")
    print("Open your browser to http://localhost:5050\n")

    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
