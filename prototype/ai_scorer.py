"""
XGBoost-based trade scoring model.
Trains on historical data, predicts profit probability for each stock.
"""
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import json
import os
import pickle
from data_engine import load_all_stock_data, compute_indicators, NIFTY_STOCKS

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def ensure_dirs():
    os.makedirs(MODEL_DIR, exist_ok=True)


FEATURE_COLS = [
    "rsi_14", "macd", "macd_signal", "macd_hist",
    "sma_20", "sma_50", "ema_9", "ema_21",
    "atr_14", "bb_pct",
    "volume_ratio", "adx",
    "pct_from_high", "pct_from_low",
    "return_1d", "return_5d", "return_10d",
    "volatility_20d",
]


def prepare_training_data(all_data, forward_days=5):
    """
    Create training dataset from all stocks.
    Label: 1 if price goes up by > 1% in forward_days, else 0
    """
    frames = []

    for symbol, df in all_data.items():
        df = compute_indicators(df)

        # Forward return (label)
        df["forward_return"] = df["Close"].shift(-forward_days) / df["Close"] - 1
        df["label"] = (df["forward_return"] > 0.01).astype(int)  # >1% profit = positive

        # Add price-relative features (normalize SMAs relative to price)
        df["sma_20_rel"] = df["Close"] / df["sma_20"].replace(0, np.nan) - 1
        df["sma_50_rel"] = df["Close"] / df["sma_50"].replace(0, np.nan) - 1

        # Replace absolute SMA values with relative ones
        df["sma_20"] = df["sma_20_rel"]
        df["sma_50"] = df["sma_50_rel"]
        df["ema_9"] = df["Close"] / df["ema_9"].replace(0, np.nan) - 1
        df["ema_21"] = df["Close"] / df["ema_21"].replace(0, np.nan) - 1

        df["symbol"] = symbol
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=FEATURE_COLS + ["label"])

    return combined


def train_model(all_data=None, forward_days=5):
    """Train XGBoost model and save it."""
    ensure_dirs()

    if all_data is None:
        all_data = load_all_stock_data()

    if not all_data:
        print("No data found. Run data_engine.py first.")
        return None

    print(f"Preparing training data from {len(all_data)} stocks...")
    df = prepare_training_data(all_data, forward_days)
    print(f"Training samples: {len(df)}")

    X = df[FEATURE_COLS].values
    y = df["label"].values

    # Time-based split (last 20% for testing -- don't shuffle time series!)
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    print(f"Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"Label distribution - Train: {np.mean(y_train):.2%} positive, Test: {np.mean(y_test):.2%} positive")

    # Train XGBoost
    model = xgb.XGBClassifier(
        n_estimators=200,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=5,
        reg_alpha=0.1,
        reg_lambda=1.0,
        random_state=42,
        eval_metric="logloss",
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=True,
    )

    # Evaluate
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)[:, 1]

    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n=== Model Performance ===")
    print(f"Accuracy: {accuracy:.2%}")
    print(classification_report(y_test, y_pred, target_names=["Loss/Flat", "Profit"]))

    # Feature importance
    importance = dict(zip(FEATURE_COLS, model.feature_importances_))
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
    print("\nTop features:")
    for feat, imp in list(importance.items())[:10]:
        print(f"  {feat}: {imp:.4f}")

    # Save model + metadata
    # Note: pickle is used here for XGBoost model serialization (standard practice for sklearn-compatible models)
    model_path = os.path.join(MODEL_DIR, "xgb_scorer.pkl")
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    meta = {
        "accuracy": round(accuracy, 4),
        "train_samples": int(len(X_train)),
        "test_samples": int(len(X_test)),
        "forward_days": forward_days,
        "features": FEATURE_COLS,
        "feature_importance": {k: round(float(v), 4) for k, v in importance.items()},
        "trained_at": pd.Timestamp.now().isoformat(),
        "positive_rate_train": round(float(np.mean(y_train)), 4),
        "positive_rate_test": round(float(np.mean(y_test)), 4),
    }
    with open(os.path.join(MODEL_DIR, "model_meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nModel saved to {model_path}")

    # Backtesting results
    backtest = compute_backtest_results(df, model, split_idx)
    with open(os.path.join(MODEL_DIR, "backtest_results.json"), "w") as f:
        json.dump(backtest, f, indent=2)

    return model, meta


def compute_backtest_results(df, model, split_idx):
    """Compute backtesting performance on test set."""
    test_df = df.iloc[split_idx:].copy()
    X_test = test_df[FEATURE_COLS].values

    test_df["pred_prob"] = model.predict_proba(X_test)[:, 1]
    test_df["pred_label"] = model.predict(X_test)

    # Bin by confidence level
    bins = [(0.7, 1.0, "High (70-100%)"), (0.5, 0.7, "Medium (50-70%)"), (0.3, 0.5, "Low (30-50%)"), (0.0, 0.3, "Very Low (0-30%)")]

    results = []
    for low, high, name in bins:
        mask = (test_df["pred_prob"] >= low) & (test_df["pred_prob"] < high)
        subset = test_df[mask]
        if len(subset) > 0:
            actual_profit_rate = subset["label"].mean()
            avg_return = subset["forward_return"].mean() * 100
            results.append({
                "confidence": name,
                "range": f"{low:.0%}-{high:.0%}",
                "trades": int(len(subset)),
                "actual_profit_rate": round(float(actual_profit_rate) * 100, 1),
                "avg_return_pct": round(float(avg_return), 2),
            })

    # Overall stats
    overall = {
        "total_test_trades": int(len(test_df)),
        "accuracy": round(float(accuracy_score(test_df["label"], test_df["pred_label"])) * 100, 1),
        "avg_predicted_prob": round(float(test_df["pred_prob"].mean()) * 100, 1),
        "confidence_breakdown": results,
    }

    return overall


def score_stocks(symbols=None):
    """Score current stocks using the trained model."""
    model_path = os.path.join(MODEL_DIR, "xgb_scorer.pkl")
    meta_path = os.path.join(MODEL_DIR, "model_meta.json")

    if not os.path.exists(model_path):
        print("No trained model found. Run train_model() first.")
        return []

    # Note: pickle used for loading XGBoost model (local-only, self-generated file)
    with open(model_path, "rb") as f:
        model = pickle.load(f)
    with open(meta_path, "r") as f:
        meta = json.load(f)

    symbols = symbols or NIFTY_STOCKS
    all_data = load_all_stock_data()

    scores = []
    for symbol in symbols:
        if symbol not in all_data:
            continue

        df = compute_indicators(all_data[symbol])
        if len(df) < 5:
            continue

        latest = df.iloc[-1].copy()

        # Normalize relative features (same as training)
        latest["sma_20"] = latest["Close"] / latest["sma_20"] - 1 if latest["sma_20"] > 0 else 0
        latest["sma_50"] = latest["Close"] / latest["sma_50"] - 1 if latest["sma_50"] > 0 else 0
        latest["ema_9"] = latest["Close"] / latest["ema_9"] - 1 if latest["ema_9"] > 0 else 0
        latest["ema_21"] = latest["Close"] / latest["ema_21"] - 1 if latest["ema_21"] > 0 else 0

        features = [latest.get(col, 0) for col in FEATURE_COLS]
        features = [0 if pd.isna(x) else float(x) for x in features]

        X = np.array([features])
        prob = float(model.predict_proba(X)[0][1])
        score = round(prob * 100, 1)

        # Generate reasons
        reasons = generate_reasons(latest, score)

        # Direction
        direction = "BUY" if score >= 50 else "HOLD" if score >= 35 else "AVOID"

        # Risk/reward estimate
        atr = latest.get("atr_14", 0)
        price = latest["Close"]
        sl_pct = round((atr / price) * 100 * 1.5, 1) if price > 0 and atr > 0 else 2.0
        target_pct = round(sl_pct * 2.0, 1)

        # Daily change
        change_pct = round(float(latest.get("return_1d", 0)) * 100, 2)

        scores.append({
            "symbol": symbol,
            "name": symbol.replace(".NS", ""),
            "price": round(float(price), 2),
            "change_pct": change_pct,
            "score": score,
            "direction": direction,
            "reasons": reasons,
            "risk_reward": round(target_pct / sl_pct, 1) if sl_pct > 0 else 2.0,
            "stop_loss_pct": sl_pct,
            "target_pct": target_pct,
            "rsi": round(float(latest.get("rsi_14", 50)), 1),
            "macd_signal": "Bullish" if latest.get("macd_hist", 0) > 0 else "Bearish",
            "trend": get_trend(latest),
            "volatility": round(float(latest.get("volatility_20d", 0)), 1),
        })

    # Sort by score descending
    scores.sort(key=lambda x: x["score"], reverse=True)
    return scores


def generate_reasons(row, score):
    """Generate human-readable reasons for the score."""
    reasons = []

    rsi = row.get("rsi_14", 50)
    if rsi < 30:
        reasons.append({"text": f"RSI oversold ({rsi:.0f}) -- bounce likely", "impact": "positive"})
    elif rsi > 70:
        reasons.append({"text": f"RSI overbought ({rsi:.0f}) -- pullback risk", "impact": "negative"})
    else:
        reasons.append({"text": f"RSI neutral ({rsi:.0f})", "impact": "neutral"})

    macd_hist = row.get("macd_hist", 0)
    if macd_hist > 0:
        reasons.append({"text": "MACD bullish crossover", "impact": "positive"})
    else:
        reasons.append({"text": "MACD bearish", "impact": "negative"})

    vol_ratio = row.get("volume_ratio", 1)
    if vol_ratio > 1.5:
        reasons.append({"text": f"Volume surge ({vol_ratio:.1f}x avg)", "impact": "positive"})
    elif vol_ratio < 0.5:
        reasons.append({"text": f"Low volume ({vol_ratio:.1f}x avg)", "impact": "negative"})

    bb_pct = row.get("bb_pct", 0.5)
    if bb_pct < 0.2:
        reasons.append({"text": "Near Bollinger lower band -- oversold", "impact": "positive"})
    elif bb_pct > 0.8:
        reasons.append({"text": "Near Bollinger upper band -- overbought", "impact": "negative"})

    pct_high = row.get("pct_from_high", 0)
    if pct_high < -20:
        reasons.append({"text": f"{abs(pct_high):.0f}% below 52-week high", "impact": "positive"})
    elif pct_high > -5:
        reasons.append({"text": "Near 52-week high", "impact": "neutral"})

    adx = row.get("adx", 0)
    if adx > 25:
        reasons.append({"text": f"Strong trend (ADX {adx:.0f})", "impact": "positive"})

    return reasons[:5]  # top 5 reasons


def get_trend(row):
    """Determine overall trend."""
    sma_20_rel = row.get("sma_20", 0)
    sma_50_rel = row.get("sma_50", 0)

    if sma_20_rel > 0 and sma_50_rel > 0:
        return "Strong Uptrend"
    elif sma_20_rel > 0:
        return "Uptrend"
    elif sma_20_rel < 0 and sma_50_rel < 0:
        return "Downtrend"
    else:
        return "Sideways"


if __name__ == "__main__":
    train_model()
