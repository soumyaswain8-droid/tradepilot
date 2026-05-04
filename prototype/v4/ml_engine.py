"""
TradePilot v4 ML Engine — LightGBM Regression
================================================
Predicts intraday return magnitude: (close - open) / open
Uses walk-forward validation with 5-day embargo.

Usage:
    # Train & save model
    python3 -m prototype.v4.ml_engine --train

    # Evaluate with walk-forward IC
    python3 -m prototype.v4.ml_engine --evaluate

    # Quick check
    python3 -m prototype.v4.ml_engine --info
"""

import json
import logging
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)

logger = logging.getLogger("v4.ml_engine")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_V4_DIR = Path(__file__).resolve().parent
_DATA_DIR = _V4_DIR.parent / "data"
_MODEL_DIR = _V4_DIR / "models"
_MODEL_DIR.mkdir(exist_ok=True)

MODEL_PATH = _MODEL_DIR / "lgbm_intraday.txt"
META_PATH = _MODEL_DIR / "lgbm_meta.json"

# ---------------------------------------------------------------------------
# Training feature set (computable from daily OHLCV)
# ---------------------------------------------------------------------------
# --- Daily features (available for full 2-year history) ---
DAILY_FEATURES = [
    "stock_change_pct",       # (close - prev_close) / prev_close
    "gap_pct",                # (open - prev_close) / prev_close
    "return_5d",              # 5-day cumulative return
    "return_20d",             # 20-day cumulative return
    "prev_day_range_pct",     # (high - low) / close
    "atr_norm",               # ATR(14) / close
    "stock_volume_ratio",     # volume / 20-day avg volume
    "rsi_14",                 # RSI(14)
    "macd_hist",              # MACD histogram
    "bollinger_pctb",         # Bollinger %B
    "adx_14",                 # ADX(14)
    "sma20_rel",              # (close - SMA20) / SMA20
    "sma50_rel",              # (close - SMA50) / SMA50
    "nifty_change_pct",       # Nifty 50 daily return
    "india_vix",              # India VIX level
    "rs_vs_nifty_5d",         # stock 5d return - nifty 5d return
    "rs_vs_nifty_20d",        # stock 20d return - nifty 20d return
]

# --- Intraday features (available for last ~60 days from 5-min candles) ---
INTRADAY_FEATURES = [
    "orb_breakout",           # +1 above 15-min high, -1 below low, 0 inside
    "orb_range_pct",          # (15min_high - 15min_low) / open * 100
    "first_hour_return",      # return from 9:15 to 10:15 AM
    "vwap_position",          # (close - VWAP) / VWAP * 100 at EOD
    "volume_profile",         # first-hour volume / total volume (front-loaded = trend)
]

# Combined: all features for training
TRAINING_FEATURES = DAILY_FEATURES + INTRADAY_FEATURES

_INTRADAY_DIR = _DATA_DIR / "intraday"

LGBM_PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "num_leaves": 15,
    "max_depth": 4,
    "min_child_samples": 50,
    "reg_alpha": 0.3,             # Was 0.5 — partial loosen for Nifty-200 dataset (middle ground)
    "reg_lambda": 1.0,            # Was 2.0 — partial loosen for Nifty-200 dataset (middle ground)
    "subsample": 0.6,
    "colsample_bytree": 0.6,
    "learning_rate": 0.05,
    "n_estimators": 2000,
    "verbose": -1,
}

# Early stopping rounds — increased from 50, middle ground (not 200)
EARLY_STOPPING_ROUNDS = 100

# Reject model if best_iteration is below this floor — guards against silent
# regressions like 2026-04-21's best_iter=2 incident (sequential split landed
# on a different regime). Healthy retrains hit 1500-3000+. 100 is the floor.
MIN_BEST_ITERATION = 100


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------
def _load_csv(filepath: Path) -> pd.DataFrame:
    """Load a single OHLCV CSV file."""
    df = pd.read_csv(filepath, parse_dates=["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    df = df.rename(columns=str.strip)
    return df


def load_stock_data(symbol: str) -> pd.DataFrame:
    """Load daily OHLCV for a stock from local CSV."""
    # Try with .NS suffix first
    path = _DATA_DIR / f"{symbol}_NS.csv"
    if not path.exists():
        path = _DATA_DIR / f"{symbol}.NS.csv"
    if not path.exists():
        path = _DATA_DIR / f"{symbol}.csv"
    if not path.exists():
        return pd.DataFrame()
    return _load_csv(path)


def load_nifty_data() -> pd.DataFrame:
    """Load Nifty 50 index daily data."""
    path = _DATA_DIR / "^NSEI.csv"
    if not path.exists():
        return pd.DataFrame()
    return _load_csv(path)


def load_vix_data() -> pd.DataFrame:
    """Load India VIX daily data."""
    path = _DATA_DIR / "^INDIAVIX.csv"
    if not path.exists():
        return pd.DataFrame()
    return _load_csv(path)


# ---------------------------------------------------------------------------
# Feature Engineering
# ---------------------------------------------------------------------------
def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0.0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    plus_dm = high.diff().clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    # Zero out when the other is larger
    plus_dm[plus_dm < minus_dm] = 0
    minus_dm[minus_dm < plus_dm] = 0
    atr = _atr(high, low, close, period)
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr.replace(0, np.nan))
    minus_di = 100 * (minus_dm.rolling(period).mean() / atr.replace(0, np.nan))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return dx.rolling(period).mean()


def _macd_histogram(close: pd.Series) -> pd.Series:
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line - signal_line


def _bollinger_pctb(close: pd.Series, period: int = 20) -> pd.Series:
    sma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = sma + 2 * std
    lower = sma - 2 * std
    band_width = (upper - lower).replace(0, np.nan)
    return (close - lower) / band_width


def compute_intraday_features_for_day(day_candles: pd.DataFrame) -> dict:
    """
    Compute intraday features from 5-min candles for a single trading day.
    Returns dict with feature values or None if insufficient data.
    """
    if day_candles.empty or len(day_candles) < 10:
        return None

    # Sort by time
    dc = day_candles.sort_values("Date").reset_index(drop=True)
    day_open = dc.iloc[0]["Open"]
    day_close = dc.iloc[-1]["Close"]

    if day_open == 0:
        return None

    # ORB: first 15 minutes (first 3 candles of 5-min)
    orb_candles = dc.head(3)
    orb_high = orb_candles["High"].max()
    orb_low = orb_candles["Low"].min()
    orb_range_pct = (orb_high - orb_low) / day_open * 100

    # ORB breakout: did price close above ORB high or below ORB low?
    after_orb = dc.iloc[3:] if len(dc) > 3 else dc
    if not after_orb.empty:
        max_after = after_orb["High"].max()
        min_after = after_orb["Low"].min()
        if max_after > orb_high and (max_after - orb_high) > (orb_low - min_after):
            orb_breakout = 1
        elif min_after < orb_low and (orb_low - min_after) > (max_after - orb_high):
            orb_breakout = -1
        else:
            orb_breakout = 0
    else:
        orb_breakout = 0

    # First hour return: 9:15 to 10:15 (first 12 candles of 5-min)
    first_hour = dc.head(12)
    first_hour_close = first_hour.iloc[-1]["Close"] if len(first_hour) >= 12 else dc.iloc[-1]["Close"]
    first_hour_return = (first_hour_close - day_open) / day_open * 100

    # VWAP position at end of day
    if "Volume" in dc.columns and dc["Volume"].sum() > 0:
        typical_price = (dc["High"] + dc["Low"] + dc["Close"]) / 3
        vwap = (typical_price * dc["Volume"]).sum() / dc["Volume"].sum()
        vwap_position = (day_close - vwap) / vwap * 100 if vwap > 0 else 0.0
    else:
        vwap_position = 0.0

    # Volume profile: first-hour volume / total volume
    first_hour_vol = dc.head(12)["Volume"].sum() if "Volume" in dc.columns else 0
    total_vol = dc["Volume"].sum() if "Volume" in dc.columns else 1
    volume_profile = first_hour_vol / max(total_vol, 1)

    return {
        "orb_breakout": orb_breakout,
        "orb_range_pct": orb_range_pct,
        "first_hour_return": first_hour_return,
        "vwap_position": vwap_position,
        "volume_profile": volume_profile,
    }


def load_intraday_features(symbol: str) -> pd.DataFrame:
    """
    Load 5-min candles and compute per-day intraday features.
    Returns DataFrame with Date + 5 intraday feature columns.
    """
    path = _INTRADAY_DIR / f"{symbol}_5m.csv"
    if not path.exists():
        return pd.DataFrame()

    candles = pd.read_csv(path, parse_dates=["Date"])
    if candles.empty:
        return pd.DataFrame()

    # Convert UTC to IST if needed
    if candles["Date"].dt.tz is not None:
        candles["Date"] = candles["Date"].dt.tz_convert("Asia/Kolkata").dt.tz_localize(None)

    candles["trade_date"] = candles["Date"].dt.date

    results = []
    for trade_date, group in candles.groupby("trade_date"):
        feats = compute_intraday_features_for_day(group)
        if feats:
            feats["Date"] = pd.Timestamp(trade_date)
            results.append(feats)

    if not results:
        return pd.DataFrame()

    return pd.DataFrame(results)


def compute_features(stock_df: pd.DataFrame, nifty_df: pd.DataFrame,
                     vix_df: pd.DataFrame, symbol: str = None) -> pd.DataFrame:
    """
    Compute all training features from daily OHLCV data.
    Returns DataFrame indexed by Date with feature columns + target.
    """
    df = stock_df.copy()
    if df.empty:
        return pd.DataFrame()

    # Ensure sorted
    df = df.sort_values("Date").reset_index(drop=True)

    prev_close = df["Close"].shift(1)

    # Target: intraday return (same-day open to close)
    df["target"] = (df["Close"] - df["Open"]) / df["Open"].replace(0, np.nan)
    # Winsorize at 1st/99th percentile
    q01 = df["target"].quantile(0.01)
    q99 = df["target"].quantile(0.99)
    df["target"] = df["target"].clip(q01, q99)

    # --- Price & Momentum ---
    df["stock_change_pct"] = (df["Close"] - prev_close) / prev_close.replace(0, np.nan) * 100
    df["gap_pct"] = (df["Open"] - prev_close) / prev_close.replace(0, np.nan) * 100
    df["return_5d"] = df["Close"].pct_change(5) * 100
    df["return_20d"] = df["Close"].pct_change(20) * 100

    # --- Volatility ---
    df["prev_day_range_pct"] = ((df["High"].shift(1) - df["Low"].shift(1))
                                 / prev_close.replace(0, np.nan) * 100)
    atr_series = _atr(df["High"], df["Low"], df["Close"])
    df["atr_norm"] = atr_series / df["Close"].replace(0, np.nan) * 100

    # --- Volume ---
    vol_20d = df["Volume"].rolling(20).mean().replace(0, np.nan)
    df["stock_volume_ratio"] = df["Volume"] / vol_20d

    # --- Technical Indicators ---
    df["rsi_14"] = _rsi(df["Close"])
    df["macd_hist"] = _macd_histogram(df["Close"])
    df["bollinger_pctb"] = _bollinger_pctb(df["Close"])
    df["adx_14"] = _adx(df["High"], df["Low"], df["Close"])
    sma20 = df["Close"].rolling(20).mean()
    sma50 = df["Close"].rolling(50).mean()
    df["sma20_rel"] = (df["Close"] - sma20) / sma20.replace(0, np.nan) * 100
    df["sma50_rel"] = (df["Close"] - sma50) / sma50.replace(0, np.nan) * 100

    # --- Market Context (merge Nifty + VIX) ---
    if not nifty_df.empty:
        nifty = nifty_df[["Date", "Close"]].copy()
        nifty = nifty.rename(columns={"Close": "nifty_close"})
        nifty["nifty_change_pct"] = nifty["nifty_close"].pct_change() * 100
        nifty["nifty_5d_return"] = nifty["nifty_close"].pct_change(5) * 100
        nifty["nifty_20d_return"] = nifty["nifty_close"].pct_change(20) * 100
        df = df.merge(nifty[["Date", "nifty_change_pct", "nifty_5d_return", "nifty_20d_return"]],
                       on="Date", how="left")
    else:
        df["nifty_change_pct"] = 0.0
        df["nifty_5d_return"] = 0.0
        df["nifty_20d_return"] = 0.0

    if not vix_df.empty:
        vix = vix_df[["Date", "Close"]].copy().rename(columns={"Close": "india_vix"})
        df = df.merge(vix[["Date", "india_vix"]], on="Date", how="left")
    else:
        df["india_vix"] = 15.0  # default neutral

    # --- Relative Strength ---
    stock_5d = df["Close"].pct_change(5) * 100
    stock_20d = df["Close"].pct_change(20) * 100
    df["rs_vs_nifty_5d"] = stock_5d - df.get("nifty_5d_return", 0.0)
    df["rs_vs_nifty_20d"] = stock_20d - df.get("nifty_20d_return", 0.0)

    # --- Merge intraday features (available for last ~60 days) ---
    if symbol:
        intraday_feats = load_intraday_features(symbol)
        if not intraday_feats.empty:
            df = df.merge(intraday_feats, on="Date", how="left")

    # Fill missing intraday features with 0 (for days without intraday data)
    # LightGBM handles this well — learns to rely on daily features when intraday = 0
    for feat in INTRADAY_FEATURES:
        if feat not in df.columns:
            df[feat] = 0.0
        else:
            df[feat] = df[feat].fillna(0.0)

    # ============================================================
    # CRITICAL: Lag ALL features by 1 day to prevent look-ahead bias
    # Features on day T must use ONLY data available on day T-1.
    # Target on day T = intraday return on day T (using today's open/close).
    # Without this lag, the model sees today's close in both features
    # and target → IC=0.97 data leakage (pitfall #4 from research).
    # ============================================================
    for feat in TRAINING_FEATURES:
        if feat in df.columns:
            df[feat] = df[feat].shift(1)

    # Forward-fill then drop remaining NaN
    df[TRAINING_FEATURES] = df[TRAINING_FEATURES].ffill()

    return df


# ---------------------------------------------------------------------------
# Training Dataset Builder
# ---------------------------------------------------------------------------
def build_training_dataset(symbols: list = None) -> pd.DataFrame:
    """
    Build combined training dataset from all Nifty 50 stocks.
    Returns DataFrame with TRAINING_FEATURES + 'target' + 'Date' + 'symbol'.
    """
    from .config import ACTIVE_SYMBOLS

    if symbols is None:
        symbols = ACTIVE_SYMBOLS

    nifty_df = load_nifty_data()
    vix_df = load_vix_data()

    all_data = []
    loaded = 0

    for sym in symbols:
        stock_df = load_stock_data(sym)
        if stock_df.empty or len(stock_df) < 60:
            logger.debug(f"Skipping {sym}: insufficient data ({len(stock_df)} rows)")
            continue

        features_df = compute_features(stock_df, nifty_df, vix_df, symbol=sym)
        if features_df.empty:
            continue

        features_df["symbol"] = sym
        # Keep only rows with complete features
        cols_needed = TRAINING_FEATURES + ["target", "Date", "symbol"]
        features_df = features_df[cols_needed].dropna(subset=TRAINING_FEATURES + ["target"])

        if len(features_df) > 0:
            all_data.append(features_df)
            loaded += 1

    if not all_data:
        logger.error("No training data loaded!")
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)
    combined = combined.sort_values("Date").reset_index(drop=True)
    logger.info(f"Training dataset: {len(combined):,} rows from {loaded} stocks, "
                f"date range: {combined['Date'].min().date()} to {combined['Date'].max().date()}")
    return combined


# ---------------------------------------------------------------------------
# Walk-Forward Validation
# ---------------------------------------------------------------------------
def walk_forward_validation(dataset: pd.DataFrame,
                            train_months: int = 6,
                            test_months: int = 1,
                            embargo_days: int = 5) -> dict:
    """
    Walk-forward validation with embargo gap.
    Returns dict with IC per fold, mean IC, hit rates.
    """
    import lightgbm as lgb

    dates = sorted(dataset["Date"].unique())
    min_date = dates[0]
    max_date = dates[-1]

    # Generate fold boundaries
    folds = []
    current_test_start = min_date + pd.DateOffset(months=train_months) + timedelta(days=embargo_days)

    while current_test_start + pd.DateOffset(months=test_months) <= max_date:
        train_end = current_test_start - timedelta(days=embargo_days)
        train_start = train_end - pd.DateOffset(months=train_months)
        test_end = current_test_start + pd.DateOffset(months=test_months)

        folds.append({
            "train_start": max(train_start, min_date),
            "train_end": train_end,
            "test_start": current_test_start,
            "test_end": test_end,
        })
        current_test_start += pd.DateOffset(months=test_months)

    if not folds:
        logger.warning("Not enough data for walk-forward validation. Training on all data.")
        return {"folds": [], "mean_ic": 0.0, "ic_positive_pct": 0.0}

    logger.info(f"Walk-forward: {len(folds)} folds, "
                f"train={train_months}mo, test={test_months}mo, embargo={embargo_days}d")

    results = []
    best_model = None
    best_ic = -999

    for i, fold in enumerate(folds):
        train_mask = (dataset["Date"] >= fold["train_start"]) & (dataset["Date"] <= fold["train_end"])
        test_mask = (dataset["Date"] >= fold["test_start"]) & (dataset["Date"] <= fold["test_end"])

        train_data = dataset[train_mask]
        test_data = dataset[test_mask]

        if len(train_data) < 100 or len(test_data) < 20:
            continue

        X_train = train_data[TRAINING_FEATURES].values
        y_train = train_data["target"].values
        X_test = test_data[TRAINING_FEATURES].values
        y_test = test_data["target"].values

        model = lgb.LGBMRegressor(**LGBM_PARAMS)
        model.fit(
            X_train, y_train,
            eval_set=[(X_test, y_test)],
            callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False), lgb.log_evaluation(0)],
        )

        y_pred = model.predict(X_test)

        # Information Coefficient = Spearman correlation
        from scipy.stats import spearmanr
        ic, p_value = spearmanr(y_pred, y_test)
        if np.isnan(ic):
            ic = 0.0

        # Hit rate: predicted direction matches actual direction
        pred_dir = (y_pred > 0).astype(int)
        actual_dir = (y_test > 0).astype(int)
        hit_rate = (pred_dir == actual_dir).mean()

        # Long-short spread: avg return of top quintile - bottom quintile
        df_eval = pd.DataFrame({"pred": y_pred, "actual": y_test})
        q80 = df_eval["pred"].quantile(0.8)
        q20 = df_eval["pred"].quantile(0.2)
        long_return = df_eval[df_eval["pred"] >= q80]["actual"].mean()
        short_return = df_eval[df_eval["pred"] <= q20]["actual"].mean()
        ls_spread = long_return - short_return

        fold_result = {
            "fold": i + 1,
            "train_rows": len(train_data),
            "test_rows": len(test_data),
            "ic": round(ic, 4),
            "p_value": round(p_value, 4),
            "hit_rate": round(hit_rate, 4),
            "ls_spread": round(ls_spread, 4),
            "train_period": f"{fold['train_start'].date()} to {fold['train_end'].date()}",
            "test_period": f"{fold['test_start'].date()} to {fold['test_end'].date()}",
        }
        results.append(fold_result)

        if ic > best_ic:
            best_ic = ic
            best_model = model

        logger.info(f"  Fold {i+1}: IC={ic:.4f}, hit={hit_rate:.1%}, L-S={ls_spread:.4f} "
                     f"[{fold['test_start'].date()} to {fold['test_end'].date()}]")

    if not results:
        return {"folds": [], "mean_ic": 0.0, "ic_positive_pct": 0.0, "model": None}

    ics = [r["ic"] for r in results]
    mean_ic = np.mean(ics)
    ic_positive_pct = (sum(1 for ic in ics if ic > 0) / len(ics)) * 100
    mean_hit_rate = np.mean([r["hit_rate"] for r in results])
    mean_ls_spread = np.mean([r["ls_spread"] for r in results])

    logger.info(f"\nWalk-Forward Summary:")
    logger.info(f"  Mean IC:          {mean_ic:.4f}")
    logger.info(f"  IC positive:      {ic_positive_pct:.0f}% of folds")
    logger.info(f"  Mean hit rate:    {mean_hit_rate:.1%}")
    logger.info(f"  Mean L-S spread:  {mean_ls_spread:.4f}")

    return {
        "folds": results,
        "mean_ic": round(mean_ic, 4),
        "ic_positive_pct": round(ic_positive_pct, 1),
        "mean_hit_rate": round(mean_hit_rate, 4),
        "mean_ls_spread": round(mean_ls_spread, 4),
        "model": best_model,
    }


# ---------------------------------------------------------------------------
# Full Training (final model on all data)
# ---------------------------------------------------------------------------
def train_and_save(dataset: pd.DataFrame = None) -> dict:
    """
    Train LightGBM on full dataset and save model.
    Also runs walk-forward validation for metrics.
    """
    import lightgbm as lgb

    if dataset is None:
        dataset = build_training_dataset()

    if dataset.empty:
        return {"error": "No training data available"}

    # Walk-forward validation first
    wf_results = walk_forward_validation(dataset)

    # Train final model on ALL data
    X = dataset[TRAINING_FEATURES].values
    y = dataset["target"].values

    # Random 10% validation for early stopping
    # Previously used last-10% sequential, which landed on a recent regime
    # and early-stopped at iteration 2. Random split gives a representative
    # validation signal across the full training period.
    # Walk-forward validation (above) provides the time-series-clean metrics;
    # this split only gates early stopping of the final model.
    from sklearn.model_selection import train_test_split
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.1, random_state=42, shuffle=True
    )
    logger.info(f"Train split: {len(X_train):,} rows · Val split: {len(X_val):,} rows (random)")

    model = lgb.LGBMRegressor(**LGBM_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(EARLY_STOPPING_ROUNDS, verbose=False), lgb.log_evaluation(0)],
    )

    # Feature importance
    importance = dict(zip(TRAINING_FEATURES, model.feature_importances_.tolist()))
    importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))

    # Quality guardrail — reject degenerate models BEFORE they overwrite the live one.
    # A best_iteration < MIN_BEST_ITERATION means early stopping fired before the
    # model meaningfully learned the signal. Shipping such a model produces near-random
    # predictions and silently destroys engine P&L (see 2026-04-21 best_iter=2 incident).
    best_iter = model.best_iteration_
    if best_iter < MIN_BEST_ITERATION:
        raise RuntimeError(
            f"REFUSING TO SAVE: best_iteration={best_iter} < MIN_BEST_ITERATION={MIN_BEST_ITERATION}. "
            f"Model is degenerate. Live model at {MODEL_PATH} is untouched. "
            f"Investigate training data and hyperparameters before retrying."
        )

    # Atomic candidate → live promote. Write to .candidate first; only rename to
    # live paths after the metadata write also succeeds. If anything fails midway,
    # the live model is preserved.
    candidate_model = MODEL_PATH.with_suffix(MODEL_PATH.suffix + ".candidate")
    candidate_meta = META_PATH.with_suffix(META_PATH.suffix + ".candidate")

    model.booster_.save_model(str(candidate_model))

    # Save metadata
    meta = {
        "trained_at": datetime.now().isoformat(),
        "training_rows": len(dataset),
        "training_stocks": dataset["symbol"].nunique(),
        "date_range": f"{dataset['Date'].min().date()} to {dataset['Date'].max().date()}",
        "features": TRAINING_FEATURES,
        "n_features": len(TRAINING_FEATURES),
        "lgbm_params": LGBM_PARAMS,
        "best_iteration": best_iter,
        "walk_forward": {
            "mean_ic": wf_results.get("mean_ic", 0),
            "ic_positive_pct": wf_results.get("ic_positive_pct", 0),
            "mean_hit_rate": wf_results.get("mean_hit_rate", 0),
            "mean_ls_spread": wf_results.get("mean_ls_spread", 0),
            "n_folds": len(wf_results.get("folds", [])),
        },
        "feature_importance": importance,
    }

    with open(candidate_meta, "w") as f:
        json.dump(meta, f, indent=2)

    # Both candidates written successfully — atomic promote.
    candidate_model.replace(MODEL_PATH)
    candidate_meta.replace(META_PATH)

    logger.info(f"\nModel saved: {MODEL_PATH} (best_iter={best_iter}, guardrail passed)")
    logger.info(f"Metadata saved: {META_PATH}")
    logger.info(f"Top 5 features: {list(importance.keys())[:5]}")

    return meta


# ---------------------------------------------------------------------------
# Prediction (Live Inference)
# ---------------------------------------------------------------------------
_loaded_model = None


def _get_model():
    """Lazy-load the trained model."""
    global _loaded_model
    if _loaded_model is not None:
        return _loaded_model

    if not MODEL_PATH.exists():
        logger.warning(f"No trained model at {MODEL_PATH}. Using neutral prediction.")
        return None

    import lightgbm as lgb
    _loaded_model = lgb.Booster(model_file=str(MODEL_PATH))
    logger.info(f"Loaded ML model from {MODEL_PATH}")
    return _loaded_model


def predict_ml_score(symbol: str, features: dict, intraday_df=None) -> float:
    """
    Predict ML score for a stock. Returns float in [0.0, 1.0].
    0.0 = strong sell, 0.5 = neutral, 1.0 = strong buy.

    Args:
        symbol: Stock symbol (e.g. "RELIANCE")
        features: Dict with feature values. Must contain keys from TRAINING_FEATURES.
                  Missing keys default to 0.0.
        intraday_df: Optional, not used by current model (daily features only).

    Returns:
        Normalized score [0.0, 1.0].
    """
    model = _get_model()
    if model is None:
        return 0.5  # Fallback to neutral

    # Build feature vector in correct order
    feature_vector = []
    for feat in TRAINING_FEATURES:
        val = features.get(feat, 0.0)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            val = 0.0
        feature_vector.append(float(val))

    X = np.array([feature_vector])
    predicted_return = model.predict(X)[0]

    # Normalize to [0, 1] using sigmoid-like transform
    # predicted_return is typically in [-3%, +3%] range
    # sigmoid(x * 50) maps +-2% to roughly 0.27-0.73 range
    score = 1.0 / (1.0 + np.exp(-predicted_return * 50))

    return float(np.clip(score, 0.0, 1.0))


def predict_batch(features_list: list) -> list:
    """
    Predict ML scores for multiple stocks at once.
    Args: list of (symbol, features_dict) tuples.
    Returns: list of floats [0.0, 1.0].
    """
    model = _get_model()
    if model is None:
        return [0.5] * len(features_list)

    X = []
    for symbol, features in features_list:
        row = []
        for feat in TRAINING_FEATURES:
            val = features.get(feat, 0.0)
            if val is None or (isinstance(val, float) and np.isnan(val)):
                val = 0.0
            row.append(float(val))
        X.append(row)

    X = np.array(X)
    predicted_returns = model.predict(X)
    scores = 1.0 / (1.0 + np.exp(-predicted_returns * 50))
    return [float(np.clip(s, 0.0, 1.0)) for s in scores]


def get_model_info() -> dict:
    """Return model metadata if available."""
    if META_PATH.exists():
        with open(META_PATH) as f:
            return json.load(f)
    return {"status": "no model trained yet"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    import sys
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if "--train" in sys.argv:
        print("=" * 60)
        print("TradePilot v4 ML Engine — Training")
        print("=" * 60)
        print("\nBuilding training dataset...")
        dataset = build_training_dataset()
        if dataset.empty:
            print("ERROR: No training data. Ensure CSV files exist in prototype/data/")
            sys.exit(1)
        print(f"\nDataset: {len(dataset):,} rows, {dataset['symbol'].nunique()} stocks")
        print(f"Date range: {dataset['Date'].min().date()} to {dataset['Date'].max().date()}")
        print(f"Target (intraday return): mean={dataset['target'].mean():.4f}, "
              f"std={dataset['target'].std():.4f}")
        print("\nTraining with walk-forward validation...")
        meta = train_and_save(dataset)
        if "error" in meta:
            print(f"ERROR: {meta['error']}")
            sys.exit(1)
        print("\n" + "=" * 60)
        print("Training Complete!")
        print(f"  Model: {MODEL_PATH}")
        print(f"  Rows: {meta['training_rows']:,}")
        print(f"  Best iteration: {meta['best_iteration']}")
        wf = meta.get("walk_forward", {})
        print(f"\n  Walk-Forward Results:")
        print(f"    Mean IC:       {wf.get('mean_ic', 'N/A')}")
        print(f"    IC positive:   {wf.get('ic_positive_pct', 'N/A')}% of folds")
        print(f"    Mean hit rate: {wf.get('mean_hit_rate', 'N/A')}")
        print(f"    Mean L-S:      {wf.get('mean_ls_spread', 'N/A')}")
        print(f"\n  Top 5 Features:")
        for i, (feat, imp) in enumerate(list(meta["feature_importance"].items())[:5]):
            print(f"    {i+1}. {feat}: {imp}")

    elif "--evaluate" in sys.argv:
        print("Building dataset for evaluation...")
        dataset = build_training_dataset()
        if dataset.empty:
            print("ERROR: No data")
            sys.exit(1)
        results = walk_forward_validation(dataset)
        print("\n" + "=" * 40)
        print(f"Mean IC: {results['mean_ic']}")
        print(f"IC positive: {results['ic_positive_pct']}%")
        if results.get("folds"):
            print("\nPer-fold details:")
            for fold in results["folds"]:
                print(f"  Fold {fold['fold']}: IC={fold['ic']}, "
                      f"hit={fold['hit_rate']:.1%}, L-S={fold['ls_spread']:.4f} "
                      f"[{fold['test_period']}]")

    elif "--info" in sys.argv:
        info = get_model_info()
        print(json.dumps(info, indent=2))

    else:
        print("Usage:")
        print("  python3 -m prototype.v4.ml_engine --train")
        print("  python3 -m prototype.v4.ml_engine --evaluate")
        print("  python3 -m prototype.v4.ml_engine --info")


if __name__ == "__main__":
    main()
