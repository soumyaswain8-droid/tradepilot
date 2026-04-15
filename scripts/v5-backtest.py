#!/usr/bin/env python3
"""
TradePilot v5 Backtester
=========================
Backtests composite scoring signals on Nifty 50 daily OHLCV data.

Uses the trained LightGBM model to rank stocks daily, then simulates
long-short intraday trades (buy at open, exit at close).

Usage:
    python3 scripts/v5-backtest.py                  # full backtest (~1 year)
    python3 scripts/v5-backtest.py --long-only      # longs only, no shorts
    python3 scripts/v5-backtest.py --period 6m      # last 6 months only
    python3 scripts/v5-backtest.py --top 5          # top/bottom 5 instead of 10
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

# Ensure prototype is importable
sys.path.insert(0, str(_PROJECT_DIR))

from prototype.v4.ml_engine import (
    TRAINING_FEATURES,
    compute_features,
    load_nifty_data,
    load_stock_data,
    load_vix_data,
)
from prototype.v4.config import NIFTY_50_SYMBOLS

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("v5-backtest")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INITIAL_CAPITAL = 10_00_000  # Rs 10 lakh
TRANSACTION_COST_PCT = 0.001  # 0.1% per trade (entry + exit = 0.2% round trip)
TOP_N = 10  # default: top 10 longs, bottom 10 shorts
OUTPUT_DIR = _PROJECT_DIR / "docs" / "backtest"


# ---------------------------------------------------------------------------
# 1. Build daily feature matrix for all stocks
# ---------------------------------------------------------------------------
def build_feature_matrix() -> pd.DataFrame:
    """
    For every (date, symbol), compute features and predicted return.
    Returns DataFrame with columns: Date, symbol, Open, Close, predicted_return.
    """
    import lightgbm as lgb

    model_path = _PROTO_DIR / "v4" / "models" / "lgbm_intraday.txt"
    if not model_path.exists():
        logger.error(f"Model not found at {model_path}. Run: python3 -m prototype.v4.ml_engine --train")
        sys.exit(1)

    model = lgb.Booster(model_file=str(model_path))
    nifty_df = load_nifty_data()
    vix_df = load_vix_data()

    all_rows = []
    loaded_count = 0

    for sym in NIFTY_50_SYMBOLS:
        stock_df = load_stock_data(sym)
        if stock_df.empty or len(stock_df) < 60:
            continue

        feat_df = compute_features(stock_df, nifty_df, vix_df, symbol=sym)
        if feat_df.empty:
            continue

        # Keep rows that have all features (after lagging, first ~50 rows are NaN)
        valid = feat_df.dropna(subset=TRAINING_FEATURES)
        if valid.empty:
            continue

        # Predict
        X = valid[TRAINING_FEATURES].values
        preds = model.predict(X)

        rows = valid[["Date", "Open", "Close"]].copy()
        rows["symbol"] = sym
        rows["predicted_return"] = preds
        rows["actual_return"] = (rows["Close"] - rows["Open"]) / rows["Open"].replace(0, np.nan)
        all_rows.append(rows)
        loaded_count += 1

    if not all_rows:
        logger.error("No stock data loaded. Check prototype/data/ directory.")
        sys.exit(1)

    matrix = pd.concat(all_rows, ignore_index=True)
    matrix = matrix.sort_values("Date").reset_index(drop=True)
    logger.info(f"Feature matrix: {len(matrix):,} rows, {loaded_count} stocks, "
                f"{matrix['Date'].nunique()} trading days")
    return matrix


# ---------------------------------------------------------------------------
# 2. Generate daily signals (rank-based)
# ---------------------------------------------------------------------------
def generate_signals(matrix: pd.DataFrame, top_n: int = TOP_N) -> pd.DataFrame:
    """
    For each day, rank stocks by predicted return.
    Top N = LONG, Bottom N = SHORT, rest = HOLD.
    """
    signals = []

    for date, group in matrix.groupby("Date"):
        if len(group) < 2 * top_n:
            continue  # need enough stocks to rank

        ranked = group.sort_values("predicted_return", ascending=False).reset_index(drop=True)
        ranked["rank"] = range(1, len(ranked) + 1)
        ranked["signal"] = "HOLD"
        ranked.loc[ranked["rank"] <= top_n, "signal"] = "LONG"
        ranked.loc[ranked["rank"] > len(ranked) - top_n, "signal"] = "SHORT"
        signals.append(ranked)

    return pd.concat(signals, ignore_index=True)


# ---------------------------------------------------------------------------
# 3. Simulate daily P&L
# ---------------------------------------------------------------------------
def simulate(signals_df: pd.DataFrame, long_only: bool = False,
             capital: float = INITIAL_CAPITAL) -> pd.DataFrame:
    """
    Simulate intraday long-short portfolio.
    Equal-weight allocation across long (and short) baskets each day.
    Entry at Open, exit at Close. Transaction costs on both sides.
    """
    daily_results = []

    for date, day_df in signals_df.groupby("Date"):
        longs = day_df[day_df["signal"] == "LONG"]
        shorts = day_df[day_df["signal"] == "SHORT"] if not long_only else pd.DataFrame()

        n_positions = len(longs) + len(shorts)
        if n_positions == 0:
            continue

        # Equal weight per position
        weight_per_pos = 1.0 / n_positions if not long_only else 1.0 / max(len(longs), 1)

        # Long P&L: buy at open, sell at close
        long_returns = longs["actual_return"].values
        long_pnl = 0.0
        if len(long_returns) > 0:
            # Gross return per position, then subtract transaction costs (entry + exit)
            long_gross = np.sum(long_returns * weight_per_pos)
            long_costs = len(longs) * weight_per_pos * 2 * TRANSACTION_COST_PCT
            long_pnl = long_gross - long_costs

        # Short P&L: sell at open, buy at close (profit when price drops)
        short_returns = shorts["actual_return"].values if not shorts.empty else np.array([])
        short_pnl = 0.0
        if len(short_returns) > 0:
            short_gross = np.sum(-short_returns * weight_per_pos)
            short_costs = len(shorts) * weight_per_pos * 2 * TRANSACTION_COST_PCT
            short_pnl = short_gross - short_costs

        total_return = long_pnl + short_pnl

        daily_results.append({
            "Date": date,
            "long_pnl_pct": long_pnl * 100,
            "short_pnl_pct": short_pnl * 100,
            "total_return_pct": total_return * 100,
            "n_longs": len(longs),
            "n_shorts": len(shorts) if not long_only else 0,
            "long_avg_pred": longs["predicted_return"].mean() if len(longs) > 0 else 0,
            "short_avg_pred": shorts["predicted_return"].mean() if not shorts.empty else 0,
        })

    results = pd.DataFrame(daily_results)
    results["Date"] = pd.to_datetime(results["Date"])
    results = results.sort_values("Date").reset_index(drop=True)

    # Compute cumulative equity curve
    results["daily_pnl_rs"] = results["total_return_pct"] / 100 * capital
    results["cumulative_pnl_rs"] = results["daily_pnl_rs"].cumsum()
    results["equity"] = capital + results["cumulative_pnl_rs"]

    # Drawdown
    results["peak"] = results["equity"].cummax()
    results["drawdown_pct"] = (results["equity"] - results["peak"]) / results["peak"] * 100

    return results


# ---------------------------------------------------------------------------
# 4. Compute performance metrics
# ---------------------------------------------------------------------------
def compute_metrics(results: pd.DataFrame, capital: float = INITIAL_CAPITAL) -> dict:
    """Compute comprehensive backtest metrics."""
    if results.empty:
        return {"error": "No results to compute metrics from"}

    total_days = len(results)
    daily_returns = results["total_return_pct"].values / 100  # as decimal

    # Total & annualized return
    final_equity = results["equity"].iloc[-1]
    total_return = (final_equity - capital) / capital
    trading_days_per_year = 252
    years = total_days / trading_days_per_year
    annualized_return = (1 + total_return) ** (1 / max(years, 0.01)) - 1

    # Risk metrics
    daily_std = np.std(daily_returns, ddof=1) if total_days > 1 else 0
    annualized_vol = daily_std * np.sqrt(trading_days_per_year)

    # Sharpe ratio (risk-free = 6.5% for India, ~0.026% daily)
    risk_free_daily = 0.065 / trading_days_per_year
    excess_returns = daily_returns - risk_free_daily
    sharpe = np.mean(excess_returns) / max(np.std(excess_returns, ddof=1), 1e-10) * np.sqrt(trading_days_per_year)

    # Sortino ratio (downside deviation only)
    downside = excess_returns[excess_returns < 0]
    downside_std = np.std(downside, ddof=1) if len(downside) > 1 else 1e-10
    sortino = np.mean(excess_returns) / max(downside_std, 1e-10) * np.sqrt(trading_days_per_year)

    # Max drawdown
    max_dd = results["drawdown_pct"].min()

    # Max drawdown duration (in trading days)
    in_dd = results["equity"] < results["peak"]
    dd_groups = (~in_dd).cumsum()
    dd_durations = in_dd.groupby(dd_groups).sum()
    max_dd_duration = int(dd_durations.max()) if len(dd_durations) > 0 else 0

    # Calmar ratio
    calmar = annualized_return / max(abs(max_dd / 100), 1e-10)

    # Win rate
    winning_days = (daily_returns > 0).sum()
    win_rate = winning_days / total_days if total_days > 0 else 0

    # Profit factor
    gross_profit = daily_returns[daily_returns > 0].sum()
    gross_loss = abs(daily_returns[daily_returns < 0].sum())
    profit_factor = gross_profit / max(gross_loss, 1e-10)

    # Best / worst day
    best_day_idx = results["total_return_pct"].idxmax()
    worst_day_idx = results["total_return_pct"].idxmin()

    return {
        "total_return_pct": round(total_return * 100, 2),
        "annualized_return_pct": round(annualized_return * 100, 2),
        "annualized_volatility_pct": round(annualized_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "sortino_ratio": round(sortino, 3),
        "calmar_ratio": round(calmar, 3),
        "max_drawdown_pct": round(max_dd, 2),
        "max_drawdown_duration_days": max_dd_duration,
        "win_rate_pct": round(win_rate * 100, 2),
        "profit_factor": round(profit_factor, 3),
        "avg_daily_pnl_rs": round(results["daily_pnl_rs"].mean(), 2),
        "total_pnl_rs": round(final_equity - capital, 2),
        "final_equity_rs": round(final_equity, 2),
        "total_trading_days": total_days,
        "best_day": {
            "date": str(results.loc[best_day_idx, "Date"].date()),
            "return_pct": round(results.loc[best_day_idx, "total_return_pct"], 3),
        },
        "worst_day": {
            "date": str(results.loc[worst_day_idx, "Date"].date()),
            "return_pct": round(results.loc[worst_day_idx, "total_return_pct"], 3),
        },
        "capital": capital,
        "transaction_cost_pct": TRANSACTION_COST_PCT * 100,
    }


# ---------------------------------------------------------------------------
# 5. VIX regime analysis
# ---------------------------------------------------------------------------
def vix_regime_analysis(results: pd.DataFrame) -> dict:
    """Split performance by VIX regime."""
    vix_df = load_vix_data()
    if vix_df.empty:
        return {"error": "VIX data not available"}

    vix_daily = vix_df[["Date", "Close"]].rename(columns={"Close": "vix"})
    merged = results.merge(vix_daily, on="Date", how="left")
    merged["vix"] = merged["vix"].ffill()

    # Drop rows without VIX
    merged = merged.dropna(subset=["vix"])
    if merged.empty:
        return {"error": "No overlapping VIX data"}

    def regime(v):
        if v < 15:
            return "Low (<15)"
        elif v <= 20:
            return "Normal (15-20)"
        else:
            return "High (>20)"

    merged["regime"] = merged["vix"].apply(regime)

    regime_stats = {}
    for name, grp in merged.groupby("regime"):
        daily_ret = grp["total_return_pct"].values / 100
        regime_stats[name] = {
            "days": len(grp),
            "avg_daily_return_pct": round(np.mean(daily_ret) * 100, 4),
            "win_rate_pct": round((daily_ret > 0).mean() * 100, 2),
            "avg_vix": round(grp["vix"].mean(), 2),
            "total_return_pct": round(np.sum(daily_ret) * 100, 2),
            "sharpe_approx": round(
                np.mean(daily_ret) / max(np.std(daily_ret, ddof=1), 1e-10) * np.sqrt(252), 3
            ) if len(grp) > 1 else 0.0,
        }

    return regime_stats


# ---------------------------------------------------------------------------
# 6. Monthly returns
# ---------------------------------------------------------------------------
def monthly_returns(results: pd.DataFrame) -> pd.DataFrame:
    """Compute monthly return aggregates."""
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


# ---------------------------------------------------------------------------
# 7. Output
# ---------------------------------------------------------------------------
def print_summary(metrics: dict, vix_stats: dict, monthly_df: pd.DataFrame,
                  long_only: bool, period_label: str):
    """Print formatted summary to console."""
    mode = "Long-Only" if long_only else "Long-Short"
    print("\n" + "=" * 65)
    print(f"  TradePilot v5 Backtest Results ({mode})")
    print(f"  Period: {period_label}")
    print("=" * 65)

    print(f"\n  Capital:              Rs {metrics['capital']:,.0f}")
    print(f"  Final Equity:         Rs {metrics['final_equity_rs']:,.2f}")
    print(f"  Total P&L:            Rs {metrics['total_pnl_rs']:,.2f}")
    print(f"  Total Return:         {metrics['total_return_pct']:+.2f}%")
    print(f"  Annualized Return:    {metrics['annualized_return_pct']:+.2f}%")
    print(f"  Annualized Volatility:{metrics['annualized_volatility_pct']:.2f}%")

    print(f"\n  --- Risk Metrics ---")
    print(f"  Sharpe Ratio:         {metrics['sharpe_ratio']:.3f}")
    print(f"  Sortino Ratio:        {metrics['sortino_ratio']:.3f}")
    print(f"  Calmar Ratio:         {metrics['calmar_ratio']:.3f}")
    print(f"  Max Drawdown:         {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Max DD Duration:      {metrics['max_drawdown_duration_days']} days")

    print(f"\n  --- Trade Stats ---")
    print(f"  Trading Days:         {metrics['total_trading_days']}")
    print(f"  Win Rate:             {metrics['win_rate_pct']:.1f}%")
    print(f"  Profit Factor:        {metrics['profit_factor']:.3f}")
    print(f"  Avg Daily P&L:        Rs {metrics['avg_daily_pnl_rs']:,.2f}")
    print(f"  Best Day:             {metrics['best_day']['date']} ({metrics['best_day']['return_pct']:+.3f}%)")
    print(f"  Worst Day:            {metrics['worst_day']['date']} ({metrics['worst_day']['return_pct']:+.3f}%)")
    print(f"  Transaction Cost:     {metrics['transaction_cost_pct']}% per trade")

    # VIX regime
    if isinstance(vix_stats, dict) and "error" not in vix_stats:
        print(f"\n  --- VIX Regime Analysis ---")
        print(f"  {'Regime':<18} {'Days':>5} {'Avg Ret%':>9} {'Win%':>7} {'Sharpe':>7}")
        print(f"  {'-'*48}")
        for regime in ["Low (<15)", "Normal (15-20)", "High (>20)"]:
            if regime in vix_stats:
                s = vix_stats[regime]
                print(f"  {regime:<18} {s['days']:>5} {s['avg_daily_return_pct']:>+9.4f} "
                      f"{s['win_rate_pct']:>6.1f}% {s['sharpe_approx']:>7.3f}")

    # Monthly returns
    if not monthly_df.empty:
        print(f"\n  --- Monthly Returns ---")
        print(f"  {'Month':<10} {'Return%':>9} {'Days':>5} {'Win%':>7}")
        print(f"  {'-'*35}")
        for _, row in monthly_df.iterrows():
            label = f"{row['month_name']} {row['year']}"
            print(f"  {label:<10} {row['total_return_pct']:>+9.2f} {int(row['trading_days']):>5} "
                  f"{row['win_rate_pct']:>6.1f}%")

    print("\n" + "=" * 65)


def save_results(metrics: dict, vix_stats: dict, monthly_df: pd.DataFrame,
                 long_only: bool):
    """Save results to JSON and CSV."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Full results JSON
    output = {
        "generated_at": datetime.now().isoformat(),
        "mode": "long_only" if long_only else "long_short",
        "metrics": metrics,
        "vix_regime": vix_stats,
    }

    json_path = OUTPUT_DIR / "v5_backtest_results.json"
    with open(json_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    logger.info(f"Results saved: {json_path}")

    # Monthly CSV
    csv_path = OUTPUT_DIR / "v5_monthly_returns.csv"
    if not monthly_df.empty:
        monthly_df.to_csv(csv_path, index=False)
        logger.info(f"Monthly returns saved: {csv_path}")


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="TradePilot v5 Backtester")
    parser.add_argument("--long-only", action="store_true", help="Long positions only (no shorts)")
    parser.add_argument("--period", type=str, default="12m",
                        help="Backtest period: 3m, 6m, 12m, 18m, 24m (default: 12m)")
    parser.add_argument("--top", type=int, default=TOP_N,
                        help=f"Number of top/bottom stocks to trade (default: {TOP_N})")
    args = parser.parse_args()

    # Parse period
    period_str = args.period.lower().replace("mo", "m")
    if period_str.endswith("m"):
        months = int(period_str[:-1])
    else:
        months = 12
    cutoff_date = datetime.now() - timedelta(days=months * 30)

    print(f"\nTradePilot v5 Backtester")
    print(f"Mode: {'Long-Only' if args.long_only else 'Long-Short'}")
    print(f"Period: last {months} months (from {cutoff_date.date()})")
    print(f"Top/Bottom: {args.top} stocks")
    print(f"Capital: Rs {INITIAL_CAPITAL:,.0f}")
    print(f"\nBuilding feature matrix for {len(NIFTY_50_SYMBOLS)} stocks...")

    # Step 1: Build features + predictions
    matrix = build_feature_matrix()

    # Filter to backtest period
    matrix["Date"] = pd.to_datetime(matrix["Date"])
    matrix = matrix[matrix["Date"] >= pd.Timestamp(cutoff_date)]

    if matrix.empty:
        logger.error(f"No data after {cutoff_date.date()}. Check data freshness.")
        sys.exit(1)

    date_range = f"{matrix['Date'].min().date()} to {matrix['Date'].max().date()}"
    logger.info(f"Backtest window: {date_range} ({matrix['Date'].nunique()} days)")

    # Step 2: Generate signals
    signals = generate_signals(matrix, top_n=args.top)
    n_long_days = signals[signals["signal"] == "LONG"].groupby("Date").size().mean()
    n_short_days = signals[signals["signal"] == "SHORT"].groupby("Date").size().mean()
    logger.info(f"Signals: avg {n_long_days:.0f} longs, {n_short_days:.0f} shorts per day")

    # Step 3: Simulate
    results = simulate(signals, long_only=args.long_only, capital=INITIAL_CAPITAL)
    if results.empty:
        logger.error("No simulation results. Check signal generation.")
        sys.exit(1)

    # Step 4: Metrics
    metrics = compute_metrics(results, capital=INITIAL_CAPITAL)

    # Step 5: VIX analysis
    vix_stats = vix_regime_analysis(results)

    # Step 6: Monthly returns
    monthly_df = monthly_returns(results)

    # Step 7: Output
    period_label = f"{results['Date'].min().date()} to {results['Date'].max().date()}"
    print_summary(metrics, vix_stats, monthly_df, args.long_only, period_label)
    save_results(metrics, vix_stats, monthly_df, args.long_only)

    # Compare long-only vs long-short if running long-short
    if not args.long_only:
        print("\n  --- Long-Only Comparison ---")
        lo_results = simulate(signals, long_only=True, capital=INITIAL_CAPITAL)
        if not lo_results.empty:
            lo_metrics = compute_metrics(lo_results, capital=INITIAL_CAPITAL)
            print(f"  Long-Only Return:     {lo_metrics['total_return_pct']:+.2f}%  "
                  f"(Sharpe: {lo_metrics['sharpe_ratio']:.3f})")
            print(f"  Long-Short Return:    {metrics['total_return_pct']:+.2f}%  "
                  f"(Sharpe: {metrics['sharpe_ratio']:.3f})")
            diff = metrics['total_return_pct'] - lo_metrics['total_return_pct']
            print(f"  Short Alpha:          {diff:+.2f}%")
        print("=" * 65)

    print(f"\nDone. Results at: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
