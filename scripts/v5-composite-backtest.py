#!/usr/bin/env python3
"""
TradePilot v5 COMPOSITE Backtester
====================================
Backtests the FULL 7-signal composite scoring system on historical data.

Unlike v5-backtest.py (ML-only, IC=0.03, -32%), this tests what LIVE v5
actually uses: ML + RelativeStrength + ORB + VWAP + FII + OI + Volume.

Since we can't call score_all_stocks() historically (it fetches LIVE data),
we SIMULATE each signal from daily OHLCV using proxy calculations.

Usage:
    python3 scripts/v5-composite-backtest.py                # full backtest
    python3 scripts/v5-composite-backtest.py --no-regime     # without regime filter
    python3 scripts/v5-composite-backtest.py --signal-analysis  # test each signal alone
"""

import argparse
import json
import logging
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_DIR = _SCRIPT_DIR.parent
_PROTO_DIR = _PROJECT_DIR / "prototype"

sys.path.insert(0, str(_PROJECT_DIR))

from prototype.v4.ml_engine import (
    TRAINING_FEATURES,
    compute_features,
    load_nifty_data,
    load_stock_data,
    load_vix_data,
)
from prototype.v4.config import NIFTY_50_SYMBOLS, COMPOSITE_WEIGHTS

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("v5-composite")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INITIAL_CAPITAL = 10_00_000  # Rs 10 lakh
TRANSACTION_COST_PCT = 0.001  # 0.1% per side
TOP_N = 10
OUTPUT_DIR = _PROJECT_DIR / "docs" / "backtest"


# ---------------------------------------------------------------------------
# 1. Load all stock data + precompute daily features
# ---------------------------------------------------------------------------
def load_all_data() -> dict:
    """Load daily OHLCV for all stocks, Nifty, VIX. Returns dict of DataFrames."""
    nifty_df = load_nifty_data()
    vix_df = load_vix_data()

    stocks = {}
    for sym in NIFTY_50_SYMBOLS:
        df = load_stock_data(sym)
        if df.empty or len(df) < 60:
            continue
        df = df.sort_values("Date").reset_index(drop=True)
        # Precompute rolling stats
        df["prev_close"] = df["Close"].shift(1)
        df["return_1d"] = df["Close"].pct_change()
        df["return_5d"] = df["Close"].pct_change(5)
        df["vol_20d_avg"] = df["Volume"].rolling(20).mean()
        df["gap_pct"] = (df["Open"] - df["prev_close"]) / df["prev_close"].replace(0, np.nan)
        df["typical_price"] = (df["High"] + df["Low"] + df["Close"]) / 3
        stocks[sym] = df

    logger.info(f"Loaded {len(stocks)} stocks, Nifty: {len(nifty_df)} rows, VIX: {len(vix_df)} rows")
    return {"stocks": stocks, "nifty": nifty_df, "vix": vix_df}


# ---------------------------------------------------------------------------
# 2. ML Signal (uses trained LightGBM model)
# ---------------------------------------------------------------------------
def compute_ml_signals(data: dict) -> pd.DataFrame:
    """Compute ML predicted return for each (date, symbol) using the trained model."""
    import lightgbm as lgb

    model_path = _PROTO_DIR / "v4" / "models" / "lgbm_intraday.txt"
    if not model_path.exists():
        logger.error(f"Model not found at {model_path}")
        sys.exit(1)

    model = lgb.Booster(model_file=str(model_path))
    nifty_df = data["nifty"]
    vix_df = data["vix"]

    all_rows = []
    for sym, stock_df in data["stocks"].items():
        feat_df = compute_features(stock_df, nifty_df, vix_df, symbol=sym)
        if feat_df.empty:
            continue
        valid = feat_df.dropna(subset=TRAINING_FEATURES)
        if valid.empty:
            continue

        preds = model.predict(valid[TRAINING_FEATURES].values)
        # Normalize to 0-1 via sigmoid (same as predict_ml_score)
        ml_scores = 1.0 / (1.0 + np.exp(-preds * 50))

        rows = valid[["Date", "Open", "Close"]].copy()
        rows["symbol"] = sym
        rows["ml_signal"] = ml_scores
        rows["actual_return"] = (rows["Close"] - rows["Open"]) / rows["Open"].replace(0, np.nan)
        all_rows.append(rows)

    return pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()


# ---------------------------------------------------------------------------
# 3. Proxy signal computation (per-day, all stocks)
# ---------------------------------------------------------------------------
def compute_proxy_signals(data: dict, ml_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each (date, symbol), compute all 7 proxy signals.
    Uses PREVIOUS day's data (lagged 1 day) for signals, today's open/close for P&L.
    """
    nifty = data["nifty"].copy()
    nifty = nifty.sort_values("Date").reset_index(drop=True)
    nifty["nifty_return_1d"] = nifty["Close"].pct_change()
    nifty["nifty_return_5d"] = nifty["Close"].pct_change(5)
    nifty["nifty_sma50"] = nifty["Close"].rolling(50).mean()
    nifty_map = nifty.set_index("Date")[["nifty_return_1d", "nifty_return_5d",
                                          "Close", "nifty_sma50"]].to_dict("index")

    vix = data["vix"].copy()
    vix_map = vix.set_index("Date")["Close"].to_dict() if not vix.empty else {}

    # Get all trading dates from ML df
    dates = sorted(ml_df["Date"].unique())
    stocks = data["stocks"]

    all_signals = []

    for dt in dates:
        day_ml = ml_df[ml_df["Date"] == dt]
        if len(day_ml) < 2 * TOP_N:
            continue

        nifty_info = nifty_map.get(dt, {})
        nifty_ret_1d = nifty_info.get("nifty_return_1d", 0.0)
        nifty_ret_5d = nifty_info.get("nifty_return_5d", 0.0)
        nifty_close = nifty_info.get("Close", 0.0)
        nifty_sma50 = nifty_info.get("nifty_sma50", nifty_close)

        # Collect all stock returns for RS ranking
        stock_5d_returns = {}
        for sym in day_ml["symbol"].values:
            sdf = stocks.get(sym)
            if sdf is None:
                continue
            mask = sdf["Date"] == dt
            if not mask.any():
                continue
            idx = sdf.index[mask][0]
            r5 = sdf.loc[idx, "return_5d"] if not pd.isna(sdf.loc[idx, "return_5d"]) else 0.0
            stock_5d_returns[sym] = r5

        # Rank 5d returns for RS percentile
        if stock_5d_returns:
            sorted_returns = sorted(stock_5d_returns.values())
            n_stocks = len(sorted_returns)
        else:
            sorted_returns = []
            n_stocks = 1

        # FII proxy (same for all stocks on this day)
        if nifty_ret_1d is not None and not np.isnan(nifty_ret_1d):
            if nifty_ret_1d > 0.005:
                fii_signal = 0.7
            elif nifty_ret_1d < -0.005:
                fii_signal = 0.3
            else:
                fii_signal = 0.5
        else:
            fii_signal = 0.5

        # VIX for regime
        vix_val = vix_map.get(dt, None)
        # Try nearby dates for VIX
        if vix_val is None:
            for offset in range(1, 5):
                vix_val = vix_map.get(dt - pd.Timedelta(days=offset), None)
                if vix_val is not None:
                    break
        if vix_val is None:
            vix_val = 15.0

        for _, row in day_ml.iterrows():
            sym = row["symbol"]
            sdf = stocks.get(sym)
            if sdf is None:
                continue

            mask = sdf["Date"] == dt
            if not mask.any():
                continue
            idx = sdf.index[mask][0]
            srow = sdf.loc[idx]

            # Signal 1: ML (already computed)
            ml_sig = row["ml_signal"]

            # Signal 2: Relative Strength (5d return vs Nifty, percentile ranked)
            r5 = stock_5d_returns.get(sym, 0.0)
            nifty_r5 = nifty_ret_5d if nifty_ret_5d is not None and not np.isnan(nifty_ret_5d) else 0.0
            rs_excess = r5 - nifty_r5
            if sorted_returns and n_stocks > 1:
                rank = np.searchsorted(sorted_returns, r5, side="right")
                rs_signal = rank / n_stocks
            else:
                rs_signal = 0.5

            # Signal 3: ORB proxy (gap%)
            gap = srow["gap_pct"] if not pd.isna(srow["gap_pct"]) else 0.0
            if gap > 0.003:
                orb_signal = 0.7
            elif gap < -0.003:
                orb_signal = 0.3
            else:
                orb_signal = 0.5

            # Signal 4: VWAP proxy (close vs typical price)
            tp = srow["typical_price"] if not pd.isna(srow["typical_price"]) else srow["Close"]
            if srow["Close"] > tp:
                vwap_signal = 0.7
            elif srow["Close"] < tp:
                vwap_signal = 0.3
            else:
                vwap_signal = 0.5

            # Signal 5: FII proxy (already computed, same for all)
            # fii_signal set above

            # Signal 6: OI proxy (volume change + price direction)
            vol = srow["Volume"] if not pd.isna(srow["Volume"]) else 0
            vol_avg = srow["vol_20d_avg"] if not pd.isna(srow["vol_20d_avg"]) else vol
            vol_ratio = vol / max(vol_avg, 1)
            price_up = srow["Close"] > srow["Open"] if srow["Open"] > 0 else False

            if vol_ratio > 1.5 and price_up:
                oi_signal = 0.7  # long buildup proxy
            elif vol_ratio > 1.5 and not price_up:
                oi_signal = 0.3  # short buildup proxy
            else:
                oi_signal = 0.5

            # Signal 7: Volume confirmation
            if vol_ratio > 1.5:
                vol_signal = 0.8
            elif vol_ratio >= 1.0:
                vol_signal = 0.6
            elif vol_ratio < 0.7:
                vol_signal = 0.3
            else:
                vol_signal = 0.5

            # Composite score (weighted sum, 0-100)
            composite = (
                COMPOSITE_WEIGHTS["ml_score"] * ml_sig +
                COMPOSITE_WEIGHTS["rs_score"] * rs_signal +
                COMPOSITE_WEIGHTS["orb_score"] * orb_signal +
                COMPOSITE_WEIGHTS["vwap_score"] * vwap_signal +
                COMPOSITE_WEIGHTS["fii_score"] * fii_signal +
                COMPOSITE_WEIGHTS["oi_score"] * oi_signal +
                COMPOSITE_WEIGHTS["vol_score"] * vol_signal
            ) * 100

            all_signals.append({
                "Date": dt,
                "symbol": sym,
                "Open": row["Open"],
                "Close": row["Close"],
                "actual_return": row["actual_return"],
                "composite_score": composite,
                "ml_signal": ml_sig,
                "rs_signal": rs_signal,
                "orb_signal": orb_signal,
                "vwap_signal": vwap_signal,
                "fii_signal": fii_signal,
                "oi_signal": oi_signal,
                "vol_signal": vol_signal,
                "vix": vix_val,
                "nifty_above_sma50": 1 if (nifty_close and nifty_sma50 and nifty_close > nifty_sma50) else 0,
            })

    df = pd.DataFrame(all_signals)
    logger.info(f"Composite signals: {len(df):,} rows, {df['Date'].nunique()} trading days")
    return df


# ---------------------------------------------------------------------------
# 4. Generate signals (rank by composite score)
# ---------------------------------------------------------------------------
def generate_signals(df: pd.DataFrame, top_n: int = TOP_N,
                     use_regime: bool = True) -> pd.DataFrame:
    """Rank stocks daily by composite score. Apply regime filter if enabled."""
    signals = []

    for date, group in df.groupby("Date"):
        if len(group) < 2 * top_n:
            continue

        ranked = group.sort_values("composite_score", ascending=False).reset_index(drop=True)
        ranked["rank"] = range(1, len(ranked) + 1)
        ranked["signal"] = "HOLD"
        ranked.loc[ranked["rank"] <= top_n, "signal"] = "LONG"
        ranked.loc[ranked["rank"] > len(ranked) - top_n, "signal"] = "SHORT"

        # Regime filter: adjust position sizing
        if use_regime:
            vix_val = ranked["vix"].iloc[0]
            nifty_bull = ranked["nifty_above_sma50"].iloc[0]

            if vix_val > 20 or not nifty_bull:
                # BEAR regime: reduce longs, increase shorts
                ranked["regime"] = "BEAR"
                ranked["long_weight"] = 0.5
                ranked["short_weight"] = 1.5
            elif vix_val < 15 and nifty_bull:
                # BULL regime: full longs, reduce shorts
                ranked["regime"] = "BULL"
                ranked["long_weight"] = 1.0
                ranked["short_weight"] = 0.5
            else:
                ranked["regime"] = "NEUTRAL"
                ranked["long_weight"] = 1.0
                ranked["short_weight"] = 1.0
        else:
            ranked["regime"] = "NONE"
            ranked["long_weight"] = 1.0
            ranked["short_weight"] = 1.0

        signals.append(ranked)

    return pd.concat(signals, ignore_index=True)


# ---------------------------------------------------------------------------
# 5. Simulate daily P&L
# ---------------------------------------------------------------------------
def simulate(signals_df: pd.DataFrame, capital: float = INITIAL_CAPITAL) -> pd.DataFrame:
    """Simulate intraday long-short portfolio with regime-adjusted weights."""
    daily_results = []

    for date, day_df in signals_df.groupby("Date"):
        longs = day_df[day_df["signal"] == "LONG"]
        shorts = day_df[day_df["signal"] == "SHORT"]

        n_positions = len(longs) + len(shorts)
        if n_positions == 0:
            continue

        long_w = longs["long_weight"].iloc[0] if len(longs) > 0 else 1.0
        short_w = shorts["short_weight"].iloc[0] if len(shorts) > 0 else 1.0

        # Equal weight per position, adjusted by regime
        base_weight = 1.0 / n_positions

        # Long P&L
        long_returns = longs["actual_return"].values
        long_pnl = 0.0
        if len(long_returns) > 0:
            long_gross = np.sum(long_returns * base_weight * long_w)
            long_costs = len(longs) * base_weight * long_w * 2 * TRANSACTION_COST_PCT
            long_pnl = long_gross - long_costs

        # Short P&L
        short_returns = shorts["actual_return"].values
        short_pnl = 0.0
        if len(short_returns) > 0:
            short_gross = np.sum(-short_returns * base_weight * short_w)
            short_costs = len(shorts) * base_weight * short_w * 2 * TRANSACTION_COST_PCT
            short_pnl = short_gross - short_costs

        total_return = long_pnl + short_pnl
        regime = day_df["regime"].iloc[0]

        daily_results.append({
            "Date": date,
            "long_pnl_pct": long_pnl * 100,
            "short_pnl_pct": short_pnl * 100,
            "total_return_pct": total_return * 100,
            "n_longs": len(longs),
            "n_shorts": len(shorts),
            "regime": regime,
            "vix": day_df["vix"].iloc[0],
        })

    results = pd.DataFrame(daily_results)
    if results.empty:
        return results

    results["Date"] = pd.to_datetime(results["Date"])
    results = results.sort_values("Date").reset_index(drop=True)
    results["daily_pnl_rs"] = results["total_return_pct"] / 100 * capital
    results["cumulative_pnl_rs"] = results["daily_pnl_rs"].cumsum()
    results["equity"] = capital + results["cumulative_pnl_rs"]
    results["peak"] = results["equity"].cummax()
    results["drawdown_pct"] = (results["equity"] - results["peak"]) / results["peak"] * 100

    return results


# ---------------------------------------------------------------------------
# 6. Compute metrics (reuse from v5-backtest pattern)
# ---------------------------------------------------------------------------
def compute_metrics(results: pd.DataFrame, capital: float = INITIAL_CAPITAL) -> dict:
    if results.empty:
        return {"error": "No results"}

    total_days = len(results)
    daily_returns = results["total_return_pct"].values / 100

    final_equity = results["equity"].iloc[-1]
    total_return = (final_equity - capital) / capital
    years = total_days / 252
    annualized_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1

    daily_std = np.std(daily_returns, ddof=1) if total_days > 1 else 0
    annualized_vol = daily_std * np.sqrt(252)

    risk_free_daily = 0.065 / 252
    excess_returns = daily_returns - risk_free_daily
    sharpe = np.mean(excess_returns) / max(np.std(excess_returns, ddof=1), 1e-10) * np.sqrt(252)

    downside = excess_returns[excess_returns < 0]
    downside_std = np.std(downside, ddof=1) if len(downside) > 1 else 1e-10
    sortino = np.mean(excess_returns) / max(downside_std, 1e-10) * np.sqrt(252)

    max_dd = results["drawdown_pct"].min()

    winning_days = (daily_returns > 0).sum()
    win_rate = winning_days / total_days

    gross_profit = daily_returns[daily_returns > 0].sum()
    gross_loss = abs(daily_returns[daily_returns < 0].sum())
    profit_factor = gross_profit / max(gross_loss, 1e-10)

    return {
        "total_return_pct": round(total_return * 100, 2),
        "annualized_return_pct": round(annualized_return * 100, 2),
        "annualized_volatility_pct": round(annualized_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "win_rate_pct": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 3),
        "avg_daily_pnl_rs": round(results["daily_pnl_rs"].mean(), 2),
        "total_pnl_rs": round(final_equity - capital, 2),
        "final_equity_rs": round(final_equity, 2),
        "total_trading_days": total_days,
        "capital": capital,
    }


# ---------------------------------------------------------------------------
# 7. Signal contribution analysis
# ---------------------------------------------------------------------------
def signal_contribution_analysis(composite_df: pd.DataFrame) -> dict:
    """Test each signal ALONE as a ranking criterion and measure performance."""
    signal_cols = {
        "ML": "ml_signal",
        "Relative Str": "rs_signal",
        "ORB proxy": "orb_signal",
        "VWAP proxy": "vwap_signal",
        "FII proxy": "fii_signal",
        "OI proxy": "oi_signal",
        "Volume": "vol_signal",
    }

    results = {}
    for name, col in signal_cols.items():
        weight = list(COMPOSITE_WEIGHTS.values())[list(signal_cols.keys()).index(name)]
        daily_pnl = []

        for date, group in composite_df.groupby("Date"):
            if len(group) < 2 * TOP_N:
                continue
            ranked = group.sort_values(col, ascending=False).reset_index(drop=True)
            longs = ranked.head(TOP_N)
            shorts = ranked.tail(TOP_N)

            n = len(longs) + len(shorts)
            w = 1.0 / n

            long_ret = np.sum(longs["actual_return"].values * w)
            short_ret = np.sum(-shorts["actual_return"].values * w)
            cost = n * w * 2 * TRANSACTION_COST_PCT
            daily_pnl.append(long_ret + short_ret - cost)

        if daily_pnl:
            arr = np.array(daily_pnl)
            total_ret = np.sum(arr) * 100
            sharpe = np.mean(arr) / max(np.std(arr, ddof=1), 1e-10) * np.sqrt(252) if len(arr) > 1 else 0
            win_rate = (arr > 0).mean() * 100
            results[name] = {
                "return_pct": round(total_ret, 2),
                "sharpe": round(sharpe, 3),
                "win_rate_pct": round(win_rate, 1),
                "weight_pct": int(weight * 100),
                "contribution": "Positive" if total_ret > 0 else "Negative",
            }

    return results


# ---------------------------------------------------------------------------
# 8. Monthly returns & VIX regime breakdown
# ---------------------------------------------------------------------------
def monthly_returns(results: pd.DataFrame) -> pd.DataFrame:
    df = results.copy()
    df["year"] = df["Date"].dt.year
    df["month"] = df["Date"].dt.month
    monthly = df.groupby(["year", "month"]).agg(
        total_return_pct=("total_return_pct", "sum"),
        trading_days=("Date", "count"),
        win_days=("total_return_pct", lambda x: (x > 0).sum()),
        avg_daily_pnl=("daily_pnl_rs", "mean"),
    ).reset_index()
    monthly["win_rate_pct"] = (monthly["win_days"] / monthly["trading_days"] * 100).round(1)
    monthly["month_name"] = monthly["month"].apply(
        lambda m: ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][m]
    )
    return monthly


def vix_regime_breakdown(results: pd.DataFrame) -> dict:
    if "vix" not in results.columns:
        return {}
    merged = results.dropna(subset=["vix"])
    if merged.empty:
        return {}

    def regime(v):
        if v < 15: return "Low (<15)"
        elif v <= 20: return "Normal (15-20)"
        else: return "High (>20)"

    merged["vix_regime"] = merged["vix"].apply(regime)
    stats = {}
    for name, grp in merged.groupby("vix_regime"):
        dr = grp["total_return_pct"].values / 100
        stats[name] = {
            "days": len(grp),
            "avg_daily_return_pct": round(np.mean(dr) * 100, 4),
            "win_rate_pct": round((dr > 0).mean() * 100, 1),
            "total_return_pct": round(np.sum(dr) * 100, 2),
            "sharpe": round(np.mean(dr) / max(np.std(dr, ddof=1), 1e-10) * np.sqrt(252), 3) if len(grp) > 1 else 0,
        }
    return stats


# ---------------------------------------------------------------------------
# 9. Output
# ---------------------------------------------------------------------------
def print_results(metrics_no_regime: dict, metrics_regime: dict,
                  signal_analysis: dict, monthly_df: pd.DataFrame,
                  vix_stats: dict, period_label: str):
    print("\n" + "=" * 65)
    print(f"  TradePilot v5 COMPOSITE Backtest Results")
    print(f"  Period: {period_label}")
    print(f"  Signals: ML(25%) + RS(20%) + ORB(15%) + VWAP(10%)")
    print(f"           + FII(10%) + OI(10%) + Volume(10%)")
    print("=" * 65)

    for label, m in [("Without Regime Filter", metrics_no_regime),
                     ("With Regime Filter", metrics_regime)]:
        print(f"\n  --- {label} ---")
        print(f"  Capital:          Rs {m['capital']:,.0f}")
        print(f"  Final Equity:     Rs {m['final_equity_rs']:,.2f}")
        print(f"  Total Return:     {m['total_return_pct']:+.2f}%")
        print(f"  Annualized:       {m['annualized_return_pct']:+.2f}%")
        print(f"  Sharpe:           {m['sharpe_ratio']:.3f}")
        print(f"  Sortino:          {m['sortino_ratio']:.3f}")
        print(f"  Max Drawdown:     {m['max_drawdown_pct']:.2f}%")
        print(f"  Win Rate:         {m['win_rate_pct']:.1f}%")
        print(f"  Profit Factor:    {m['profit_factor']:.3f}")
        print(f"  Avg Daily P&L:    Rs {m['avg_daily_pnl_rs']:,.2f}")
        print(f"  Trading Days:     {m['total_trading_days']}")

    print(f"\n  --- Signal Contribution Analysis ---")
    print(f"  {'Signal':<16} {'Alone%':>8} {'Weight':>7} {'Sharpe':>7} {'Win%':>6} {'Contrib':>10}")
    print(f"  {'-'*56}")
    for name, s in signal_analysis.items():
        print(f"  {name:<16} {s['return_pct']:>+7.2f}% {s['weight_pct']:>5}% "
              f"{s['sharpe']:>7.3f} {s['win_rate_pct']:>5.1f}% {s['contribution']:>10}")

    if not monthly_df.empty:
        print(f"\n  --- Monthly Returns (with regime) ---")
        print(f"  {'Month':<10} {'Return%':>9} {'Days':>5} {'Win%':>7}")
        print(f"  {'-'*35}")
        for _, row in monthly_df.iterrows():
            label = f"{row['month_name']} {row['year']}"
            print(f"  {label:<10} {row['total_return_pct']:>+9.2f} {int(row['trading_days']):>5} "
                  f"{row['win_rate_pct']:>6.1f}%")

    if vix_stats:
        print(f"\n  --- VIX Regime Breakdown ---")
        print(f"  {'Regime':<18} {'Days':>5} {'Avg Ret%':>9} {'Win%':>7} {'Sharpe':>7}")
        print(f"  {'-'*48}")
        for regime in ["Low (<15)", "Normal (15-20)", "High (>20)"]:
            if regime in vix_stats:
                s = vix_stats[regime]
                print(f"  {regime:<18} {s['days']:>5} {s['avg_daily_return_pct']:>+9.4f} "
                      f"{s['win_rate_pct']:>6.1f}% {s['sharpe']:>7.3f}")

    print("\n" + "=" * 65)


def save_results(metrics_no_regime: dict, metrics_regime: dict,
                 signal_analysis: dict, monthly_df: pd.DataFrame,
                 vix_stats: dict):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    output = {
        "generated_at": datetime.now().isoformat(),
        "type": "composite_7_signal_backtest",
        "weights": COMPOSITE_WEIGHTS,
        "without_regime": metrics_no_regime,
        "with_regime": metrics_regime,
        "signal_analysis": signal_analysis,
        "vix_regime": vix_stats,
    }
    json_path = OUTPUT_DIR / "v5_composite_backtest_results.json"
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    logger.info(f"Results saved: {json_path}")

    csv_path = OUTPUT_DIR / "v5_composite_monthly.csv"
    if not monthly_df.empty:
        monthly_df.to_csv(csv_path, index=False)
        logger.info(f"Monthly CSV saved: {csv_path}")


# ---------------------------------------------------------------------------
# 10. Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="TradePilot v5 Composite Backtester")
    parser.add_argument("--no-regime", action="store_true", help="Skip regime filter comparison")
    parser.add_argument("--signal-analysis", action="store_true", help="Run signal-by-signal analysis only")
    parser.add_argument("--period", type=str, default="12m", help="Backtest period (e.g. 6m, 12m, 24m)")
    parser.add_argument("--top", type=int, default=TOP_N, help="Top/bottom N stocks to trade")
    args = parser.parse_args()

    period_str = args.period.lower().replace("mo", "m")
    months = int(period_str.replace("m", "")) if period_str.endswith("m") else 12
    cutoff_date = datetime.now() - timedelta(days=months * 30)

    print(f"\nTradePilot v5 COMPOSITE Backtester")
    print(f"7 signals: ML + RS + ORB + VWAP + FII + OI + Volume")
    print(f"Period: last {months} months | Top/Bottom: {args.top}")
    print(f"Capital: Rs {INITIAL_CAPITAL:,.0f}\n")

    # Step 1: Load data
    print("Loading data...")
    data = load_all_data()

    # Step 2: Compute ML signals (the expensive part)
    print("Computing ML signals...")
    ml_df = compute_ml_signals(data)
    if ml_df.empty:
        logger.error("No ML signals computed. Check data.")
        sys.exit(1)

    ml_df["Date"] = pd.to_datetime(ml_df["Date"])
    ml_df = ml_df[ml_df["Date"] >= pd.Timestamp(cutoff_date)]

    # Step 3: Compute all 7 proxy signals
    print("Computing composite signals (7 signals)...")
    composite_df = compute_proxy_signals(data, ml_df)
    if composite_df.empty:
        logger.error("No composite signals computed.")
        sys.exit(1)

    period_label = f"{composite_df['Date'].min().date()} to {composite_df['Date'].max().date()}"

    # Signal analysis mode
    if args.signal_analysis:
        print("\nRunning signal-by-signal analysis...")
        sa = signal_contribution_analysis(composite_df)
        print(f"\n  {'Signal':<16} {'Alone%':>8} {'Weight':>7} {'Sharpe':>7} {'Win%':>6}")
        print(f"  {'-'*45}")
        for name, s in sa.items():
            print(f"  {name:<16} {s['return_pct']:>+7.2f}% {s['weight_pct']:>5}% "
                  f"{s['sharpe']:>7.3f} {s['win_rate_pct']:>5.1f}%")
        return

    # Step 4: Backtest WITHOUT regime filter
    print("Simulating without regime filter...")
    signals_no_regime = generate_signals(composite_df, top_n=args.top, use_regime=False)
    results_no_regime = simulate(signals_no_regime)
    metrics_no_regime = compute_metrics(results_no_regime)

    # Step 5: Backtest WITH regime filter
    if not args.no_regime:
        print("Simulating with regime filter...")
        signals_regime = generate_signals(composite_df, top_n=args.top, use_regime=True)
        results_regime = simulate(signals_regime)
        metrics_regime = compute_metrics(results_regime)
    else:
        results_regime = results_no_regime
        metrics_regime = metrics_no_regime

    # Step 6: Signal contribution analysis
    print("Analyzing signal contributions...")
    signal_analysis = signal_contribution_analysis(composite_df)

    # Step 7: Monthly returns & VIX breakdown (from regime-filtered results)
    monthly_df = monthly_returns(results_regime if not args.no_regime else results_no_regime)
    vix_stats = vix_regime_breakdown(results_regime if not args.no_regime else results_no_regime)

    # Step 8: Print & save
    print_results(metrics_no_regime, metrics_regime, signal_analysis, monthly_df, vix_stats, period_label)
    save_results(metrics_no_regime, metrics_regime, signal_analysis, monthly_df, vix_stats)

    print(f"\nDone. Results at: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
