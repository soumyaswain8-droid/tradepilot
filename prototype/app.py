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

from data_engine import get_market_indices, NIFTY_STOCKS
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

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))
CORS(app)  # Allow Flutter web app to call API from different port


def get_model_meta():
    # Prefer v2 meta
    v2_path = os.path.join(os.path.dirname(__file__), "models", "model_meta_v2.json")
    v1_path = os.path.join(os.path.dirname(__file__), "models", "model_meta.json")
    for path in [v2_path, v1_path]:
        if os.path.exists(path):
            with open(path) as f:
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

    # Cache for 5 minutes on Render (reduce API calls)
    cache_key = category
    now = time.time()
    if _score_cache["data"] and (now - _score_cache["time"]) < 300 and _score_cache.get("key") == cache_key:
        return jsonify(_score_cache["data"])

    try:
        from data_engine import STOCK_CATEGORIES, NIFTY_50
        cat_stocks = STOCK_CATEGORIES.get(category, {}).get('stocks', NIFTY_50)

        # Try trained model first
        raw_scores = None
        if ensure_data():
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
            vol = safe(s.get("volatility"), 20)

            # Skip entries with no valid price
            if price == 0:
                continue

            reasons = []
            for r in s.get("reasons", []):
                reasons.append({
                    "text": r.get("text", ""),
                    "type": r.get("impact", "neutral"),
                })

            stocks.append({
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
            })

        _score_cache["data"] = stocks
        _score_cache["time"] = now
        _score_cache["key"] = cache_key
        return jsonify(stocks)
    except Exception as e:
        traceback.print_exc()
        return jsonify([]), 500


@app.route("/api/model")
def api_model():
    """Get model metadata -- formatted for frontend."""
    try:
        meta = get_model_meta()
        backtest = get_backtest_results()

        if not meta:
            return jsonify({"accuracy": 0, "trainingSamples": 0, "lastTrained": "Not trained"})

        # Transform feature importance to frontend format
        features = []
        fi = meta.get("feature_importance", {})
        max_imp = max(fi.values()) if fi else 1

        # Friendly names for features
        friendly = {
            "rsi_14": "RSI", "macd": "MACD", "macd_signal": "MACD Signal",
            "macd_hist": "MACD Histogram", "sma_20": "SMA 20", "sma_50": "SMA 50",
            "ema_9": "EMA 9", "ema_21": "EMA 21", "atr_14": "ATR",
            "bb_pct": "Bollinger %B", "volume_ratio": "Volume", "adx": "ADX/Trend",
            "pct_from_high": "52W High Dist", "pct_from_low": "52W Low Dist",
            "return_1d": "1-Day Return", "return_5d": "5-Day Return",
            "return_10d": "10-Day Return", "volatility_20d": "Volatility",
        }

        for feat, imp in sorted(fi.items(), key=lambda x: x[1], reverse=True)[:8]:
            features.append({
                "name": friendly.get(feat, feat),
                "importance": round(imp / max_imp, 2),  # normalize to 0-1
            })

        # Transform backtest to frontend format
        backtest_bins = []
        if backtest and "confidence_breakdown" in backtest:
            for b in backtest["confidence_breakdown"]:
                backtest_bins.append({
                    "bin": b.get("range", b.get("confidence", "")),
                    "trades": b.get("trades", 0),
                    "winRate": b.get("actual_profit_rate", 0),
                    "avgProfit": b.get("avg_return_pct", 0),
                    "maxDrawdown": 0,
                })

        trained_at = meta.get("trained_at", "Unknown")
        if "T" in trained_at:
            trained_at = trained_at.split("T")[0]  # just date

        # Support both v1 (accuracy) and v2 (ensemble_accuracy) formats
        acc = meta.get("ensemble_accuracy", meta.get("accuracy", 0))
        # v2 stores as 0.66, v1 as 0.61 -- both need * 100
        if acc < 1:
            acc = round(acc * 100, 1)

        # v2 backtest is embedded in meta
        bt = meta.get("backtest", {})
        if bt and "total_return_pct" in bt:
            backtest_bins = [{
                "bin": "Overall",
                "trades": bt.get("total_trades", 0),
                "winRate": bt.get("win_rate_pct", 0),
                "avgProfit": bt.get("total_return_pct", 0),
                "maxDrawdown": bt.get("max_drawdown_pct", 0),
                "sharpe": bt.get("sharpe_ratio", 0),
                "profitFactor": bt.get("profit_factor", 0),
            }]

        result = {
            "accuracy": acc,
            "version": meta.get("version", "v1"),
            "trainingSamples": meta.get("train_samples", 0) + meta.get("test_samples", 0),
            "lastTrained": trained_at,
            "features": features,
            "backtest": backtest_bins,
        }

        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"accuracy": 0, "trainingSamples": 0, "lastTrained": "Error"})


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

        # Fallback if indices fetch failed
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


@app.route("/api/stock/<symbol>")
def api_stock(symbol):
    """Get detailed data for a single stock."""
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


@app.route("/api/bots/geopolitical")
def api_bots_geopolitical():
    """Geopolitical analysis bot - events affecting Indian markets."""
    events = [
        {
            "title": "US Fed Signals Rate Pause",
            "impact": "positive",
            "severity": "high",
            "affected_sectors": ["Banking", "IT", "Auto"],
            "summary": "Federal Reserve hints at holding rates steady through Q2 2026. Positive for emerging market flows — FII inflows likely to increase.",
            "market_impact": "NIFTY may see 2-3% upside in coming weeks as FII buying resumes.",
            "timestamp": "2h ago"
        },
        {
            "title": "Crude Oil Drops Below $70",
            "impact": "positive",
            "severity": "medium",
            "affected_sectors": ["Oil & Gas", "Airlines", "Paint"],
            "summary": "Brent crude falls to $68/barrel on weak demand outlook. Reduces India's import bill significantly.",
            "market_impact": "ONGC, BPCL may see pressure. Indigo, Asian Paints benefit from lower input costs.",
            "timestamp": "4h ago"
        },
        {
            "title": "China-Taiwan Tensions Escalate",
            "impact": "negative",
            "severity": "high",
            "affected_sectors": ["IT", "Semiconductor", "Defence"],
            "summary": "Military exercises in Taiwan Strait spook global markets. Supply chain risks for chip-dependent sectors.",
            "market_impact": "IT sector may face selling pressure. Defence stocks like HAL, BEL could rally.",
            "timestamp": "6h ago"
        },
        {
            "title": "India-EU FTA Talks Progress",
            "impact": "positive",
            "severity": "medium",
            "affected_sectors": ["Pharma", "Textile", "Auto"],
            "summary": "India and EU reach agreement on key provisions. Pharma exports to benefit from reduced tariffs.",
            "market_impact": "Sun Pharma, Dr Reddy's, Cipla positioned for gains. Textile exporters also benefit.",
            "timestamp": "8h ago"
        },
        {
            "title": "RBI Liquidity Injection Rs 50,000 Cr",
            "impact": "positive",
            "severity": "high",
            "affected_sectors": ["Banking", "NBFC", "Real Estate"],
            "summary": "RBI announces OMO purchases to ease liquidity. Banking sector to benefit from improved NIM outlook.",
            "market_impact": "PSU banks and NBFCs could see 3-5% upside. Real estate sector also benefits.",
            "timestamp": "1d ago"
        },
        {
            "title": "Global Recession Fears Rise",
            "impact": "negative",
            "severity": "medium",
            "affected_sectors": ["Metal", "IT", "Export-heavy"],
            "summary": "Germany enters technical recession. US PMI data weakens. Risk-off sentiment building globally.",
            "market_impact": "Metal stocks (Tata Steel, JSW) under pressure. Defensive sectors (FMCG, Pharma) may outperform.",
            "timestamp": "1d ago"
        }
    ]
    return jsonify({"events": events, "overall_sentiment": "cautiously_bullish", "confidence": 72})


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

        gainers = sorted(clean, key=lambda x: x["change"], reverse=True)[:50]
        losers = sorted(clean, key=lambda x: x["change"])[:50]

        result = {"gainers": gainers, "losers": losers}
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
    """Analytics dashboard for founders."""
    stats = get_dashboard_stats()
    return jsonify(stats)


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

    app.run(host="0.0.0.0", port=5050, debug=False)
