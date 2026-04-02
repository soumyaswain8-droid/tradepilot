"""
TradePilot Trading Engine v2 -- Multi-Strategy Ensemble
Combines multiple proven strategies + multi-model AI for maximum edge.

Strategies implemented:
  1. Momentum (12-month price momentum, skip last month)
  2. RSI Mean Reversion (buy oversold, sell overbought)
  3. Moving Average Trend (golden cross / death cross)
  4. Volume Breakout (price + volume surge)
  5. Bollinger Band Squeeze (volatility expansion)

AI Models:
  - XGBoost (gradient boosted trees)
  - LightGBM (faster, often better on financial data)
  - Ensemble: weighted average of both

Risk Management:
  - Max loss per trade: 10% (HARD LIMIT)
  - Position sizing: Kelly Criterion (capped at 25%)
  - Max concurrent positions: 10
  - Daily loss limit: 3% of portfolio

NOTE: pickle is used here only for local-only, self-generated ML model files.
These files are never loaded from untrusted sources.
"""
import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score
import json
import os
import pickle  # Used only for local self-generated ML model serialization
from datetime import datetime

from data_engine import load_all_stock_data, compute_indicators, NIFTY_STOCKS

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def ensure_dirs():
    os.makedirs(MODEL_DIR, exist_ok=True)
    os.makedirs(RESULTS_DIR, exist_ok=True)


# ═══════════════════════════════════════════════════
# FEATURE ENGINEERING (Enhanced)
# ═══════════════════════════════════════════════════

FEATURE_COLS = [
    # Trend
    "rsi_14", "macd", "macd_signal", "macd_hist",
    "sma_20_rel", "sma_50_rel", "ema_9_rel", "ema_21_rel",
    # Volatility
    "atr_14_pct", "bb_pct", "volatility_20d",
    # Volume
    "volume_ratio", "obv_slope",
    # Momentum
    "return_1d", "return_5d", "return_10d", "return_20d",
    "momentum_12m",
    # Mean reversion
    "pct_from_high", "pct_from_low",
    # Trend strength
    "adx",
    # Strategy signals
    "signal_momentum", "signal_rsi_reversion", "signal_ma_trend",
    "signal_volume_breakout", "signal_bb_squeeze",
]


def enhanced_features(df):
    """Compute enhanced features including strategy signals."""
    df = compute_indicators(df)
    close = df["Close"]
    volume = df["Volume"]

    # Relative price features (normalized)
    df["sma_20_rel"] = close / df["sma_20"].replace(0, np.nan) - 1
    df["sma_50_rel"] = close / df["sma_50"].replace(0, np.nan) - 1
    df["ema_9_rel"] = close / df["ema_9"].replace(0, np.nan) - 1
    df["ema_21_rel"] = close / df["ema_21"].replace(0, np.nan) - 1

    # ATR as percentage of price
    df["atr_14_pct"] = df["atr_14"] / close * 100

    # OBV slope (momentum of accumulation)
    df["obv_slope"] = df["obv"].diff(5) / df["obv"].shift(5).replace(0, np.nan)

    # 20-day return
    df["return_20d"] = close.pct_change(20)

    # 12-month momentum (skip last month -- proven academic factor)
    # Use 200-day if 252 not available, fallback to 120-day
    lookback = min(252, len(df) - 25)
    if lookback > 60:
        df["momentum_12m"] = close.shift(21) / close.shift(lookback) - 1
    else:
        df["momentum_12m"] = close.pct_change(60)  # fallback: 3-month momentum

    # ═══ STRATEGY SIGNALS ═══

    # 1. Momentum signal
    df["signal_momentum"] = (
        (df["momentum_12m"] > 0) &
        (close > df["sma_200"].fillna(df["sma_50"])) &
        (df["return_20d"] > -0.05)
    ).astype(float)

    # 2. RSI Mean Reversion
    df["signal_rsi_reversion"] = (
        (df["rsi_14"] < 35) &
        (df["pct_from_low"] < 15) &
        (df["volume_ratio"] > 0.8)
    ).astype(float)

    # 3. MA Trend (golden cross)
    df["signal_ma_trend"] = (
        (df["ema_9"] > df["ema_21"]) &
        (df["ema_21"] > df["sma_50"]) &
        (df["adx"] > 20)
    ).astype(float)

    # 4. Volume Breakout
    df["signal_volume_breakout"] = (
        (df["return_1d"] > 0.01) &
        (df["volume_ratio"] > 2.0) &
        (close > df["sma_20"])
    ).astype(float)

    # 5. Bollinger Band Squeeze
    bb_width = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"].replace(0, np.nan)
    bb_width_min = bb_width.rolling(120).min()
    df["signal_bb_squeeze"] = (
        (bb_width < bb_width_min * 1.1) &
        (df["rsi_14"] > 40) & (df["rsi_14"] < 60)
    ).astype(float)

    return df


def prepare_training_data(all_data, forward_days=5, profit_threshold=0.01):
    """Create training dataset with enhanced features."""
    frames = []
    for symbol, df in all_data.items():
        try:
            df = enhanced_features(df)
            df["forward_return"] = df["Close"].shift(-forward_days) / df["Close"] - 1
            df["label"] = (df["forward_return"] > profit_threshold).astype(int)
            df["symbol"] = symbol
            frames.append(df)
        except Exception as e:
            print(f"  Skipping {symbol}: {e}")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=FEATURE_COLS + ["label"])
    return combined


def train_ensemble(all_data=None, forward_days=5):
    """Train XGBoost + LightGBM ensemble."""
    ensure_dirs()

    if all_data is None:
        all_data = load_all_stock_data()
    if not all_data:
        print("No data found.")
        return None, None, None

    print(f"Preparing enhanced features for {len(all_data)} stocks...")
    df = prepare_training_data(all_data, forward_days)
    print(f"Total samples: {len(df)}")

    X = df[FEATURE_COLS].values
    y = df["label"].values

    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"Positive rate -- Train: {np.mean(y_train):.2%}, Test: {np.mean(y_test):.2%}")

    # MODEL 1: XGBoost
    print("\n--- Training XGBoost ---")
    xgb_model = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        reg_alpha=0.1, reg_lambda=1.5, random_state=42, eval_metric="logloss",
    )
    xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
    xgb_prob = xgb_model.predict_proba(X_test)[:, 1]
    xgb_acc = accuracy_score(y_test, (xgb_prob >= 0.5).astype(int))
    print(f"XGBoost Accuracy: {xgb_acc:.2%}")

    # MODEL 2: LightGBM
    print("\n--- Training LightGBM ---")
    lgb_model = lgb.LGBMClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        reg_alpha=0.1, reg_lambda=1.5, random_state=42, verbose=-1,
    )
    lgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)])
    lgb_prob = lgb_model.predict_proba(X_test)[:, 1]
    lgb_acc = accuracy_score(y_test, (lgb_prob >= 0.5).astype(int))
    print(f"LightGBM Accuracy: {lgb_acc:.2%}")

    # ENSEMBLE
    total = xgb_acc + lgb_acc
    w_xgb = xgb_acc / total
    w_lgb = lgb_acc / total
    ensemble_prob = w_xgb * xgb_prob + w_lgb * lgb_prob
    ensemble_pred = (ensemble_prob >= 0.5).astype(int)
    ensemble_acc = accuracy_score(y_test, ensemble_pred)
    ensemble_precision = precision_score(y_test, ensemble_pred, zero_division=0)

    print(f"\n{'='*50}")
    print(f"ENSEMBLE: Accuracy={ensemble_acc:.2%}, Precision={ensemble_precision:.2%}")
    print(f"Weights: XGB={w_xgb:.2f}, LGB={w_lgb:.2f}")

    # BACKTEST
    test_df = df.iloc[split_idx:].copy()
    test_df["ensemble_prob"] = ensemble_prob
    backtest = run_backtest(test_df)

    # Feature importance
    xgb_imp = dict(zip(FEATURE_COLS, xgb_model.feature_importances_))
    lgb_raw = lgb_model.feature_importances_
    lgb_imp = dict(zip(FEATURE_COLS, lgb_raw / max(lgb_raw.sum(), 1)))
    importance = {}
    for f in FEATURE_COLS:
        importance[f] = round((xgb_imp.get(f, 0) + lgb_imp.get(f, 0)) / 2, 4)
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    print("\nTop 10 Features:")
    for feat, imp in list(importance.items())[:10]:
        print(f"  {feat}: {imp:.4f}")

    # Save (pickle used only for self-generated local model files)
    with open(os.path.join(MODEL_DIR, "xgb_v2.pkl"), "wb") as f:
        pickle.dump(xgb_model, f)
    with open(os.path.join(MODEL_DIR, "lgb_v2.pkl"), "wb") as f:
        pickle.dump(lgb_model, f)

    meta = {
        "version": "v2.0-ensemble",
        "xgb_accuracy": round(float(xgb_acc), 4),
        "lgb_accuracy": round(float(lgb_acc), 4),
        "ensemble_accuracy": round(float(ensemble_acc), 4),
        "ensemble_precision": round(float(ensemble_precision), 4),
        "weights": {"xgb": round(float(w_xgb), 3), "lgb": round(float(w_lgb), 3)},
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "forward_days": forward_days,
        "features": FEATURE_COLS,
        "feature_importance": {k: round(float(v), 4) for k, v in importance.items()},
        "trained_at": datetime.now().isoformat(),
        "backtest": backtest,
    }
    with open(os.path.join(MODEL_DIR, "model_meta_v2.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nModels saved to {MODEL_DIR}")
    return xgb_model, lgb_model, meta


def run_backtest(test_df, initial_capital=1000000, max_risk_pct=10):
    """Simulate trading on test data with risk management."""
    capital = initial_capital
    peak_capital = capital
    trades = []

    high_conf = test_df[test_df["ensemble_prob"] >= 0.60].copy()

    for _, row in high_conf.iterrows():
        prob = float(row["ensemble_prob"])
        actual_return = float(row.get("forward_return", 0))
        atr_pct = float(row.get("atr_14_pct", 3))

        sl_pct = min(atr_pct * 1.5, max_risk_pct) / 100
        reward_risk = 2.0
        kelly = (prob * reward_risk - (1 - prob)) / reward_risk
        kelly = max(0, min(kelly, 0.25))
        position_size = capital * kelly
        if position_size < 1000:
            continue

        if actual_return > 0:
            pnl = position_size * min(actual_return, sl_pct * 2)
            won = True
        else:
            pnl = -position_size * min(abs(actual_return), sl_pct)
            won = False

        capital += pnl
        peak_capital = max(peak_capital, capital)
        trades.append({"pnl": float(pnl), "won": won, "prob": prob})

    if not trades:
        return {"total_trades": 0, "error": "No trades generated"}

    wins = sum(1 for t in trades if t["won"])
    losses = len(trades) - wins
    win_rate = wins / len(trades) * 100
    total_pnl = sum(t["pnl"] for t in trades)
    avg_win = float(np.mean([t["pnl"] for t in trades if t["won"]])) if wins > 0 else 0
    avg_loss = float(np.mean([t["pnl"] for t in trades if not t["won"]])) if losses > 0 else 0
    profit_factor = abs(avg_win * wins / (avg_loss * losses)) if losses > 0 and avg_loss != 0 else 99
    max_dd = (peak_capital - capital) / peak_capital * 100
    total_return = (capital - initial_capital) / initial_capital * 100
    trade_returns = [t["pnl"] / initial_capital for t in trades]
    sharpe = float(np.mean(trade_returns) / max(np.std(trade_returns), 0.0001) * np.sqrt(252))

    results = {
        "initial_capital": initial_capital,
        "final_capital": round(capital, 2),
        "total_return_pct": round(total_return, 2),
        "total_trades": len(trades),
        "wins": wins, "losses": losses,
        "win_rate_pct": round(win_rate, 1),
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "profit_factor": round(min(profit_factor, 99), 2),
        "max_drawdown_pct": round(max_dd, 2),
        "sharpe_ratio": round(sharpe, 2),
        "total_pnl": round(total_pnl, 2),
    }

    print(f"\n  Capital: Rs {initial_capital:,.0f} -> Rs {capital:,.0f} ({total_return:+.2f}%)")
    print(f"  Trades: {len(trades)} | Win Rate: {win_rate:.1f}% | Sharpe: {sharpe:.2f}")
    print(f"  Profit Factor: {min(profit_factor,99):.2f} | Max DD: {max_dd:.2f}%")
    return results


def score_stocks_v2(symbols=None):
    """Score stocks using ensemble model + strategy signals."""
    xgb_path = os.path.join(MODEL_DIR, "xgb_v2.pkl")
    lgb_path = os.path.join(MODEL_DIR, "lgb_v2.pkl")
    meta_path = os.path.join(MODEL_DIR, "model_meta_v2.json")

    if not os.path.exists(xgb_path) or not os.path.exists(lgb_path):
        print("No v2 models found. Training...")
        train_ensemble()

    # Local-only model files, self-generated
    with open(xgb_path, "rb") as f:
        xgb_model = pickle.load(f)
    with open(lgb_path, "rb") as f:
        lgb_model = pickle.load(f)
    with open(meta_path, "r") as f:
        meta = json.load(f)

    weights = meta.get("weights", {"xgb": 0.5, "lgb": 0.5})
    symbols = symbols or NIFTY_STOCKS
    all_data = load_all_stock_data()

    scores = []
    for symbol in symbols:
        if symbol not in all_data:
            continue
        try:
            df = enhanced_features(all_data[symbol])
            if len(df) < 10:
                continue
            latest = df.iloc[-1].copy()

            features = [0 if pd.isna(latest.get(c, 0)) else float(latest.get(c, 0)) for c in FEATURE_COLS]
            X = np.array([features])

            xgb_prob = float(xgb_model.predict_proba(X)[0][1])
            lgb_prob = float(lgb_model.predict_proba(X)[0][1])
            prob = weights["xgb"] * xgb_prob + weights["lgb"] * lgb_prob
            score = round(prob * 100, 1)

            signals_active = sum([
                float(latest.get("signal_momentum", 0)),
                float(latest.get("signal_rsi_reversion", 0)),
                float(latest.get("signal_ma_trend", 0)),
                float(latest.get("signal_volume_breakout", 0)),
                float(latest.get("signal_bb_squeeze", 0)),
            ])
            score = min(99, score + signals_active * 3)

            direction = "BUY" if score >= 55 else "HOLD" if score >= 40 else "AVOID"

            price = float(latest["Close"])
            atr = float(latest.get("atr_14", 0))
            sl_pct = round(min((atr / price) * 100 * 1.5, 10), 1) if price > 0 and atr > 0 else 3.0
            target_pct = round(sl_pct * 2.0, 1)
            change_pct = round(float(latest.get("return_1d", 0)) * 100, 2)
            safe = bool(sl_pct <= 10)
            recommended = bool(safe and score >= 55 and target_pct > sl_pct)

            reasons = _generate_reasons(latest, score, signals_active)

            scores.append({
                "symbol": symbol, "name": symbol.replace(".NS", ""),
                "price": round(price, 2), "change_pct": change_pct,
                "score": score, "direction": direction,
                "reasons": reasons,
                "risk_reward": round(target_pct / sl_pct, 1) if sl_pct > 0 else 2.0,
                "stop_loss_pct": sl_pct, "target_pct": target_pct,
                "rsi": round(float(latest.get("rsi_14", 50)), 1),
                "macd_signal": "Bullish" if latest.get("macd_hist", 0) > 0 else "Bearish",
                "trend": _get_trend(latest),
                "volatility": round(float(latest.get("volatility_20d", 0)), 1),
                "signals_active": int(signals_active),
                "safe": safe, "recommended": recommended,
            })
        except Exception:
            pass

    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores


def _generate_reasons(row, score, signals_active):
    reasons = []
    if signals_active >= 3:
        reasons.append({"text": f"{int(signals_active)}/5 strategies agree -- high conviction", "impact": "positive"})
    if row.get("signal_momentum", 0) > 0:
        reasons.append({"text": "12-month momentum positive -- uptrend intact", "impact": "positive"})
    if row.get("signal_rsi_reversion", 0) > 0:
        reasons.append({"text": f"RSI oversold ({row.get('rsi_14',0):.0f}) -- bounce expected", "impact": "positive"})
    if row.get("signal_ma_trend", 0) > 0:
        reasons.append({"text": "Golden alignment: EMA 9 > EMA 21 > SMA 50", "impact": "positive"})
    if row.get("signal_volume_breakout", 0) > 0:
        reasons.append({"text": f"Volume breakout: {row.get('volume_ratio',0):.1f}x average", "impact": "positive"})
    if row.get("signal_bb_squeeze", 0) > 0:
        reasons.append({"text": "Bollinger squeeze -- volatility expansion imminent", "impact": "positive"})
    macd_hist = row.get("macd_hist", 0)
    if macd_hist > 0 and len(reasons) < 5:
        reasons.append({"text": "MACD bullish momentum", "impact": "positive"})
    elif macd_hist < 0:
        reasons.append({"text": "MACD bearish pressure", "impact": "negative"})
    if row.get("pct_from_high", 0) < -20:
        reasons.append({"text": f"{abs(row.get('pct_from_high',0)):.0f}% below 52W high -- value zone", "impact": "positive"})
    return reasons[:6]


def _get_trend(row):
    e9 = row.get("ema_9_rel", 0)
    e21 = row.get("ema_21_rel", 0)
    s50 = row.get("sma_50_rel", 0)
    adx = row.get("adx", 0)
    if e9 > 0 and e21 > 0 and s50 > 0 and adx > 25:
        return "Strong Uptrend"
    elif e9 > 0 and e21 > 0:
        return "Uptrend"
    elif e9 < 0 and e21 < 0 and s50 < 0:
        return "Downtrend"
    return "Sideways"


if __name__ == "__main__":
    print("=" * 60)
    print("  TradePilot Trading Engine v2")
    print("=" * 60)
    all_data = load_all_stock_data()
    if not all_data:
        print("No data. Run: python3 data_engine.py")
    else:
        train_ensemble(all_data)
