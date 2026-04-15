"""
TradePilot v3.1 Precision Tuning Experiment

Tests 3 label configurations to push precision toward 80%:
  a. CURRENT:  forward_return > 0.5% in 5 days
  b. HARDER:   forward_return > 1.5% in 5 days (fewer positives, higher quality)
  c. SHORTER:  forward_return > 0.5% in 3 days (faster signal)

Uses the same V3_FEATURE_COLS and feature engineering from trading_engine_v3.py.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.metrics import accuracy_score, precision_score, recall_score
from datetime import datetime

from data_engine import load_all_stock_data, load_stock_data, compute_indicators
from trading_engine_v3 import (
    V3_FEATURE_COLS, enhanced_features_v3, compute_market_regime,
)

# ── Label configurations ──────────────────────────────────────
LABEL_CONFIGS = {
    "CURRENT": {"threshold": 0.005, "forward_days": 5, "desc": ">0.5% in 5d"},
    "HARDER":  {"threshold": 0.015, "forward_days": 5, "desc": ">1.5% in 5d"},
    "SHORTER": {"threshold": 0.005, "forward_days": 3, "desc": ">0.5% in 3d"},
}


def make_labels(df, threshold, forward_days):
    """Create binary label and sample weights for a given config."""
    fwd_ret = df["Close"].shift(-forward_days) / df["Close"] - 1
    df["forward_return"] = fwd_ret
    df["label"] = (fwd_ret > threshold).astype(int)
    # Sample weights: reward big movers
    df["sample_weight"] = 1.0
    df.loc[fwd_ret > 0.03, "sample_weight"] = 3.0
    df.loc[fwd_ret > 0.01, "sample_weight"] = 2.0
    df.loc[fwd_ret < -0.03, "sample_weight"] = 2.0
    return df


def prepare_data(all_data, market_df, threshold, forward_days):
    """Prepare combined training data for one label config."""
    if market_df is not None and len(market_df) > 50:
        mkt = compute_market_regime(market_df)
    else:
        mkt = market_df

    frames = []
    for symbol, df in all_data.items():
        try:
            df = enhanced_features_v3(df, mkt)
            df = make_labels(df, threshold, forward_days)
            df["symbol"] = symbol
            frames.append(df)
        except Exception:
            pass

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.dropna(subset=V3_FEATURE_COLS + ["label"])
    return combined


def train_and_evaluate(df, forward_days, config_name):
    """Train XGB+LGB ensemble, evaluate, find optimal threshold, run backtest."""
    X = df[V3_FEATURE_COLS].values
    y = df["label"].values
    weights = df["sample_weight"].values

    # 80/20 time-based split
    split_idx = int(len(X) * 0.8)
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]
    w_train = weights[:split_idx]

    pos_rate_train = np.mean(y_train)
    pos_rate_test = np.mean(y_test)

    # XGBoost
    xgb_model = xgb.XGBClassifier(
        n_estimators=500, max_depth=5, learning_rate=0.02,
        subsample=0.75, colsample_bytree=0.75, min_child_weight=10,
        reg_alpha=0.5, reg_lambda=2.0, gamma=0.1,
        scale_pos_weight=1.0, random_state=42, eval_metric="logloss",
    )
    xgb_model.fit(X_train, y_train, sample_weight=w_train,
                  eval_set=[(X_test, y_test)], verbose=False)
    xgb_prob = xgb_model.predict_proba(X_test)[:, 1]

    # LightGBM
    lgb_model = lgb.LGBMClassifier(
        n_estimators=500, max_depth=5, learning_rate=0.02,
        subsample=0.75, colsample_bytree=0.75, min_child_weight=10,
        reg_alpha=0.5, reg_lambda=2.0, min_gain_to_split=0.1,
        random_state=42, verbose=-1,
    )
    lgb_model.fit(X_train, y_train, sample_weight=w_train,
                  eval_set=[(X_test, y_test)])
    lgb_prob = lgb_model.predict_proba(X_test)[:, 1]

    # Ensemble (precision-weighted)
    xgb_prec_base = precision_score(y_test, (xgb_prob >= 0.5).astype(int), zero_division=0)
    lgb_prec_base = precision_score(y_test, (lgb_prob >= 0.5).astype(int), zero_division=0)
    total_prec = max(xgb_prec_base + lgb_prec_base, 0.01)
    w_xgb = xgb_prec_base / total_prec
    w_lgb = lgb_prec_base / total_prec
    ensemble_prob = w_xgb * xgb_prob + w_lgb * lgb_prob

    # Metrics at threshold 0.5
    pred_50 = (ensemble_prob >= 0.5).astype(int)
    acc_50 = accuracy_score(y_test, pred_50)
    prec_50 = precision_score(y_test, pred_50, zero_division=0)
    rec_50 = recall_score(y_test, pred_50, zero_division=0)
    trades_50 = int(pred_50.sum())

    # Find optimal threshold for 70%+ precision
    best_thresh = 0.5
    best_score = 0
    for thresh in np.arange(0.45, 0.85, 0.005):
        pred = (ensemble_prob >= thresh).astype(int)
        prec = precision_score(y_test, pred, zero_division=0)
        n = pred.sum()
        if prec >= 0.70 and n >= 10:
            rec = recall_score(y_test, pred, zero_division=0)
            f1 = 2 * prec * rec / max(prec + rec, 0.01)
            if f1 > best_score:
                best_score = f1
                best_thresh = thresh

    pred_opt = (ensemble_prob >= best_thresh).astype(int)
    prec_opt = precision_score(y_test, pred_opt, zero_division=0)
    rec_opt = recall_score(y_test, pred_opt, zero_division=0)
    trades_opt = int(pred_opt.sum())

    # Precision in 70-100% confidence bucket
    hi_mask = ensemble_prob >= 0.70
    hi_prec = float(y_test[hi_mask].mean()) if hi_mask.sum() > 5 else np.nan
    hi_count = int(hi_mask.sum())

    # Simple backtest: buy when prob > optimal threshold, hold forward_days
    test_df = df.iloc[split_idx:].copy()
    test_df["ensemble_prob"] = ensemble_prob
    bt = simple_backtest(test_df, best_thresh, forward_days)

    # Feature importance (top 5)
    xgb_imp = dict(zip(V3_FEATURE_COLS, xgb_model.feature_importances_))
    lgb_raw = lgb_model.feature_importances_
    lgb_imp = dict(zip(V3_FEATURE_COLS, lgb_raw / max(lgb_raw.sum(), 1)))
    importance = {f: round((xgb_imp.get(f, 0) + lgb_imp.get(f, 0)) / 2, 4) for f in V3_FEATURE_COLS}
    top5 = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "config": config_name,
        "samples_train": len(X_train),
        "samples_test": len(X_test),
        "pos_rate_train": pos_rate_train,
        "pos_rate_test": pos_rate_test,
        # At threshold 0.5
        "acc_50": acc_50,
        "prec_50": prec_50,
        "rec_50": rec_50,
        "trades_50": trades_50,
        # At optimal threshold
        "opt_thresh": best_thresh,
        "prec_opt": prec_opt,
        "rec_opt": rec_opt,
        "trades_opt": trades_opt,
        # High confidence bucket
        "hi_conf_prec": hi_prec,
        "hi_conf_count": hi_count,
        # Backtest
        "bt_win_rate": bt["win_rate"],
        "bt_total_return": bt["total_return"],
        "bt_trades": bt["n_trades"],
        "bt_sharpe": bt["sharpe"],
        "bt_profit_factor": bt["profit_factor"],
        # Top features
        "top5_features": top5,
        # Weights
        "w_xgb": w_xgb,
        "w_lgb": w_lgb,
    }


def simple_backtest(test_df, threshold, forward_days, initial_capital=1_000_000):
    """Simple backtest: buy when prob > threshold, use actual forward return."""
    signals = test_df[test_df["ensemble_prob"] >= threshold].copy()
    trades = []
    capital = initial_capital
    peak = capital

    for _, row in signals.iterrows():
        ret = float(row.get("forward_return", 0))
        if np.isnan(ret):
            continue
        prob = float(row["ensemble_prob"])
        atr_pct = float(row.get("atr_14_pct", 3))
        regime = float(row.get("regime", 0))

        sl_pct = min(atr_pct * 1.5, 10) / 100
        reward_risk = 2.0
        kelly = (prob * reward_risk - (1 - prob)) / reward_risk
        kelly = max(0, min(kelly, 0.25))
        if regime < 0:
            kelly *= 0.5
        elif regime == 0:
            kelly *= 0.75

        pos = capital * kelly
        if pos < 1000:
            continue

        if ret > 0:
            pnl = pos * min(ret, sl_pct * 2)
            won = True
        else:
            pnl = -pos * min(abs(ret), sl_pct)
            won = False

        capital += pnl
        peak = max(peak, capital)
        trades.append({"pnl": pnl, "won": won, "ret": ret})

    if not trades:
        return {"win_rate": 0, "total_return": 0, "n_trades": 0, "sharpe": 0, "profit_factor": 0}

    wins = sum(1 for t in trades if t["won"])
    n = len(trades)
    win_rate = wins / n * 100
    total_return = (capital - initial_capital) / initial_capital * 100
    rets = [t["pnl"] / initial_capital for t in trades]
    sharpe = float(np.mean(rets) / max(np.std(rets), 0.0001) * np.sqrt(252))
    avg_win = np.mean([t["pnl"] for t in trades if t["won"]]) if wins > 0 else 0
    avg_loss = np.mean([t["pnl"] for t in trades if not t["won"]]) if wins < n else 0
    profit_factor = abs(avg_win * wins / (avg_loss * (n - wins))) if (n - wins) > 0 and avg_loss != 0 else 99

    return {
        "win_rate": round(win_rate, 1),
        "total_return": round(total_return, 2),
        "n_trades": n,
        "sharpe": round(sharpe, 2),
        "profit_factor": round(profit_factor, 2),
    }


def main():
    print("=" * 80)
    print("TradePilot v3.1 Precision Tuning Experiment")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Load data once
    print("\nLoading stock data...")
    all_data = load_all_stock_data()
    print(f"  Loaded {len(all_data)} stocks")

    print("Loading NIFTY 50 index data...")
    nifty_df = load_stock_data("^NSEI")
    if nifty_df is None:
        print("  NIFTY data not cached, downloading...")
        import yfinance as yf
        nifty_df = yf.Ticker("^NSEI").history(period="2y", interval="1d")
        if not nifty_df.empty:
            nifty_df.index = nifty_df.index.tz_localize(None)
    if nifty_df is not None:
        print(f"  NIFTY data: {len(nifty_df)} rows, {nifty_df.index[0].date()} to {nifty_df.index[-1].date()}")

    results = []
    for name, cfg in LABEL_CONFIGS.items():
        print(f"\n{'─' * 70}")
        print(f"Config: {name} ({cfg['desc']})")
        print(f"  threshold={cfg['threshold']}, forward_days={cfg['forward_days']}")
        print(f"{'─' * 70}")

        df = prepare_data(all_data, nifty_df, cfg["threshold"], cfg["forward_days"])
        print(f"  Samples: {len(df)}, Positive rate: {df['label'].mean():.2%}")

        res = train_and_evaluate(df, cfg["forward_days"], name)
        results.append(res)

        print(f"  @0.5 threshold: Acc={res['acc_50']:.2%}, Prec={res['prec_50']:.2%}, Rec={res['rec_50']:.2%}, Trades={res['trades_50']}")
        print(f"  @optimal ({res['opt_thresh']:.3f}): Prec={res['prec_opt']:.2%}, Rec={res['rec_opt']:.2%}, Trades={res['trades_opt']}")
        hi_str = f"{res['hi_conf_prec']:.1%}" if not np.isnan(res['hi_conf_prec']) else "N/A"
        print(f"  70-100% conf bucket: Prec={hi_str} ({res['hi_conf_count']} samples)")
        print(f"  Backtest: WinRate={res['bt_win_rate']}%, Return={res['bt_total_return']}%, Sharpe={res['bt_sharpe']}, PF={res['bt_profit_factor']}")
        print(f"  Ensemble weights: XGB={res['w_xgb']:.2f}, LGB={res['w_lgb']:.2f}")
        print(f"  Top features: {', '.join(f'{f}({v:.3f})' for f, v in res['top5_features'])}")

    # ── Comparison table ──────────────────────────────────────
    print("\n\n" + "=" * 100)
    print("COMPARISON TABLE")
    print("=" * 100)

    header = f"{'Config':<12} {'Label':<14} {'Pos%':>6} {'Acc@.5':>7} {'Prec@.5':>8} {'OptThr':>7} {'Prec@Opt':>9} {'Trades':>7} {'HiConf%':>8} {'WinRate':>8} {'Return':>8} {'Sharpe':>7} {'PF':>6}"
    print(header)
    print("-" * len(header))

    for r, (name, cfg) in zip(results, LABEL_CONFIGS.items()):
        hi_str = f"{r['hi_conf_prec']:.1%}" if not np.isnan(r['hi_conf_prec']) else "N/A"
        print(
            f"{name:<12} {cfg['desc']:<14} "
            f"{r['pos_rate_test']:>5.1%} "
            f"{r['acc_50']:>6.1%} "
            f"{r['prec_50']:>7.1%} "
            f"{r['opt_thresh']:>7.3f} "
            f"{r['prec_opt']:>8.1%} "
            f"{r['trades_opt']:>7d} "
            f"{hi_str:>8} "
            f"{r['bt_win_rate']:>7.1f}% "
            f"{r['bt_total_return']:>7.1f}% "
            f"{r['bt_sharpe']:>7.2f} "
            f"{r['bt_profit_factor']:>5.1f}"
        )

    print("\n" + "=" * 100)
    print("RECOMMENDATIONS")
    print("=" * 100)

    # Find best config by precision at optimal threshold
    best_prec = max(results, key=lambda r: r["prec_opt"])
    best_bt = max(results, key=lambda r: r["bt_win_rate"])
    best_sharpe = max(results, key=lambda r: r["bt_sharpe"])

    print(f"  Highest precision:    {best_prec['config']} ({best_prec['prec_opt']:.1%} @ {best_prec['opt_thresh']:.3f}, {best_prec['trades_opt']} trades)")
    print(f"  Highest win rate:     {best_bt['config']} ({best_bt['bt_win_rate']}% over {best_bt['bt_trades']} trades)")
    print(f"  Best Sharpe:          {best_sharpe['config']} ({best_sharpe['bt_sharpe']})")

    # Check if any config hits 70%+ precision with reasonable trade count
    viable = [r for r in results if r["prec_opt"] >= 0.70 and r["trades_opt"] >= 20]
    if viable:
        best_viable = max(viable, key=lambda r: r["prec_opt"])
        print(f"\n  BEST VIABLE (70%+ prec, 20+ trades): {best_viable['config']}")
        print(f"    Precision={best_viable['prec_opt']:.1%}, Trades={best_viable['trades_opt']}, WinRate={best_viable['bt_win_rate']}%")
    else:
        print("\n  WARNING: No config achieved 70%+ precision with 20+ trades.")
        print("  Consider: stricter features, longer forward horizon, or ensemble stacking.")

    print(f"\nCompleted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
