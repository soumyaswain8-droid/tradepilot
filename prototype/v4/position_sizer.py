"""
TradePilot v4 — Position Sizer
===============================
Determines HOW MUCH to invest in each stock based on signal confidence.

Input:  Scored BUY signals from composite_scorer (ranked by score)
Output: Position sizes, quantities, SL/target prices, risk metrics

Daily capital pool: Rs 10,00,000 (configurable)
"""

import math
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# Kelly Criterion
# ---------------------------------------------------------------------------

def kelly_fraction(win_rate: float, avg_win_pct: float, avg_loss_pct: float) -> float:
    """
    Half-Kelly fraction for position sizing.

    Kelly formula: f = p - q/b
    where p = win_rate, q = 1-p, b = avg_win / avg_loss (payoff ratio)

    Returns fraction of capital to risk (0 to max 0.25).
    Uses HALF Kelly for safety. Capped at 25%.
    """
    if avg_loss_pct <= 0 or avg_win_pct <= 0:
        return 0.0
    if not (0.0 < win_rate < 1.0):
        return 0.0

    p = win_rate
    q = 1.0 - p
    b = avg_win_pct / avg_loss_pct  # payoff ratio

    full_kelly = p - (q / b)

    if full_kelly <= 0:
        return 0.0

    half_kelly = full_kelly / 2.0
    return min(half_kelly, 0.25)


# ---------------------------------------------------------------------------
# Position Sizing
# ---------------------------------------------------------------------------

def size_positions(
    scored_stocks: List[Dict],
    capital: float = 1_000_000.0,
    max_per_stock_pct: float = 0.20,
    min_per_stock_rs: float = 20_000.0,
    default_sl_pct: float = 1.0,
    default_target_pct: float = 2.0,
) -> List[Dict]:
    """
    Size positions for all BUY signals based on composite score.

    Allocation logic:
    1. Score-weighted: higher composite score = larger allocation
       weight_i = score_i / sum(all_scores)
       base_alloc_i = weight_i * capital
    2. Cap at max_per_stock_pct * capital
    3. Floor at min_per_stock_rs (skip if below after capping)
    4. Redistribute excess from capped stocks to uncapped ones
    5. Compute qty = int(position_size / price)
    6. SL/target from scorer if available, else use defaults
    """
    if not scored_stocks:
        return []

    # Filter out stocks with no valid price
    stocks = [s for s in scored_stocks if s.get("price", 0) > 0]
    if not stocks:
        return []

    max_alloc = max_per_stock_pct * capital
    scores = [s.get("score", 0) for s in stocks]
    total_score = sum(scores)

    if total_score <= 0:
        return []

    # --- Step 1: Score-weighted base allocation ---
    allocations = [(s["score"] / total_score) * capital for s in stocks]

    # --- Step 2-4: Cap, floor, redistribute ---
    # Iterative redistribution (converges in 2-3 passes)
    for _ in range(5):
        excess = 0.0
        uncapped_score = 0.0

        for i, alloc in enumerate(allocations):
            if alloc > max_alloc:
                excess += alloc - max_alloc
                allocations[i] = max_alloc
            elif alloc >= min_per_stock_rs:
                uncapped_score += scores[i]

        if excess <= 0 or uncapped_score <= 0:
            break

        # Redistribute proportionally to uncapped stocks
        for i, alloc in enumerate(allocations):
            if alloc < max_alloc and alloc >= min_per_stock_rs:
                share = (scores[i] / uncapped_score) * excess
                allocations[i] = min(alloc + share, max_alloc)

    # --- Build output ---
    positions = []
    for i, stock in enumerate(stocks):
        alloc = allocations[i]

        # Skip positions below minimum
        if alloc < min_per_stock_rs:
            continue

        price = stock["price"]
        qty = int(alloc / price)
        if qty <= 0:
            continue

        # Actual position size after rounding to whole shares
        position_size = qty * price
        position_pct = position_size / capital

        # SL and target from composite scorer or defaults
        sl_pct = stock.get("stopLoss", default_sl_pct)
        target_pct = stock.get("target", default_target_pct)

        sl_price = round(price * (1 - sl_pct / 100), 2)
        target_price = round(price * (1 + target_pct / 100), 2)

        risk_rs = round(qty * price * (sl_pct / 100), 2)
        reward_rs = round(qty * price * (target_pct / 100), 2)
        rr = round(reward_rs / risk_rs, 2) if risk_rs > 0 else 0.0

        pos = {
            # Carry forward all existing fields
            **stock,
            # Position sizing fields
            "position_size_rs": round(position_size, 2),
            "position_pct": round(position_pct, 4),
            "qty": qty,
            "sl_price": sl_price,
            "target_price": target_price,
            "sl_pct": sl_pct,
            "target_pct": target_pct,
            "risk_rs": risk_rs,
            "reward_rs": reward_rs,
            "risk_reward": rr,
        }
        positions.append(pos)

    return positions


# ---------------------------------------------------------------------------
# Portfolio Risk Metrics
# ---------------------------------------------------------------------------

def compute_portfolio_risk(
    positions: List[Dict],
    capital: float = 1_000_000.0,
    assumed_win_rate: float = 0.55,
) -> Dict:
    """
    Portfolio-level risk metrics.

    Returns aggregated risk/reward summary across all positions.
    """
    if not positions:
        return {
            "total_deployed": 0,
            "total_deployed_pct": 0.0,
            "max_single_risk": 0,
            "total_risk": 0,
            "total_risk_pct": 0.0,
            "total_reward": 0,
            "expected_pnl": 0,
            "positions_count": 0,
            "avg_position_size": 0,
            "cash_remaining": capital,
            "cash_remaining_pct": 1.0,
        }

    deployed = sum(p["position_size_rs"] for p in positions)
    risks = [p["risk_rs"] for p in positions]
    rewards = [p["reward_rs"] for p in positions]
    total_risk = sum(risks)
    total_reward = sum(rewards)

    # Expected PnL: win_rate * reward - (1 - win_rate) * risk, per position
    expected = sum(
        assumed_win_rate * p["reward_rs"] - (1 - assumed_win_rate) * p["risk_rs"]
        for p in positions
    )

    n = len(positions)
    return {
        "total_deployed": round(deployed, 2),
        "total_deployed_pct": round(deployed / capital, 4),
        "max_single_risk": round(max(risks), 2),
        "total_risk": round(total_risk, 2),
        "total_risk_pct": round(total_risk / capital, 4),
        "total_reward": round(total_reward, 2),
        "total_reward_pct": round(total_reward / capital, 4),
        "expected_pnl": round(expected, 2),
        "expected_pnl_pct": round(expected / capital, 4),
        "positions_count": n,
        "avg_position_size": round(deployed / n, 2),
        "cash_remaining": round(capital - deployed, 2),
        "cash_remaining_pct": round((capital - deployed) / capital, 4),
        "portfolio_risk_reward": round(total_reward / total_risk, 2) if total_risk > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Demo / Self-Test
# ---------------------------------------------------------------------------

def _demo():
    """Run with sample data matching v4 composite scorer output format."""

    # Simulated BUY signals (10 stocks, scores in 64-74 range as per today's data)
    sample_stocks = [
        {"symbol": "BHARTIARTL", "name": "BHARTIARTL", "price": 1580.50, "change_pct": 1.82, "score": 74.2, "direction": "BUY", "stopLoss": 1.0, "target": 2.5, "volatility": "Medium"},
        {"symbol": "RELIANCE",   "name": "RELIANCE",   "price": 1265.30, "change_pct": 1.45, "score": 72.8, "direction": "BUY", "stopLoss": 1.0, "target": 2.0, "volatility": "Medium"},
        {"symbol": "TCS",        "name": "TCS",        "price": 3520.00, "change_pct": 0.92, "score": 71.5, "direction": "BUY", "stopLoss": 1.0, "target": 2.5, "volatility": "Low"},
        {"symbol": "INFY",       "name": "INFY",       "price": 1480.75, "change_pct": 1.10, "score": 70.3, "direction": "BUY", "stopLoss": 1.0, "target": 2.0, "volatility": "Low"},
        {"symbol": "HDFCBANK",   "name": "HDFCBANK",   "price": 1620.40, "change_pct": 0.75, "score": 69.1, "direction": "BUY", "stopLoss": 1.5, "target": 2.0, "volatility": "Low"},
        {"symbol": "ICICIBANK",  "name": "ICICIBANK",  "price": 1090.25, "change_pct": 0.68, "score": 68.0, "direction": "BUY", "stopLoss": 1.5, "target": 2.0, "volatility": "Low"},
        {"symbol": "SBIN",       "name": "SBIN",       "price": 780.60,  "change_pct": 1.35, "score": 67.2, "direction": "BUY", "stopLoss": 1.5, "target": 2.0, "volatility": "Medium"},
        {"symbol": "BAJFINANCE", "name": "BAJFINANCE", "price": 6890.00, "change_pct": 0.55, "score": 66.0, "direction": "BUY", "stopLoss": 1.0, "target": 2.0, "volatility": "Medium"},
        {"symbol": "LT",         "name": "LT",         "price": 3280.15, "change_pct": 0.42, "score": 65.1, "direction": "BUY", "stopLoss": 1.5, "target": 2.0, "volatility": "Low"},
        {"symbol": "MARUTI",     "name": "MARUTI",     "price": 12450.00,"change_pct": 0.30, "score": 64.0, "direction": "BUY", "stopLoss": 1.0, "target": 2.0, "volatility": "Low"},
    ]

    capital = 1_000_000.0
    print(f"\n{'='*80}")
    print(f"  TradePilot v4 Position Sizer — Demo")
    print(f"  Capital: Rs {capital:,.0f} | Stocks: {len(sample_stocks)} BUY signals")
    print(f"{'='*80}")

    # --- Kelly demo ---
    print(f"\n--- Kelly Criterion (reference) ---")
    kf = kelly_fraction(win_rate=0.55, avg_win_pct=2.0, avg_loss_pct=1.0)
    print(f"  Win rate: 55%, Avg win: 2%, Avg loss: 1%")
    print(f"  Half-Kelly fraction: {kf:.4f} ({kf*100:.1f}% of capital per trade)")

    # --- Size positions ---
    positions = size_positions(sample_stocks, capital=capital)

    print(f"\n--- Sized Positions ---")
    print(f"{'Symbol':>12}  {'Score':>5}  {'Alloc Rs':>10}  {'Alloc%':>7}  "
          f"{'Qty':>5}  {'SL':>8}  {'Target':>8}  {'Risk Rs':>8}  {'R:R':>5}")
    print(f"{'-'*80}")

    for p in positions:
        print(
            f"{p['symbol']:>12}  {p['score']:5.1f}  "
            f"{p['position_size_rs']:>10,.0f}  {p['position_pct']*100:>6.1f}%  "
            f"{p['qty']:>5}  {p['sl_price']:>8,.2f}  {p['target_price']:>8,.2f}  "
            f"{p['risk_rs']:>8,.0f}  {p['risk_reward']:>5.1f}"
        )

    # --- Portfolio risk ---
    risk = compute_portfolio_risk(positions, capital=capital)

    print(f"\n--- Portfolio Risk Summary ---")
    print(f"  Deployed:       Rs {risk['total_deployed']:>10,.0f}  ({risk['total_deployed_pct']*100:.1f}%)")
    print(f"  Cash remaining: Rs {risk['cash_remaining']:>10,.0f}  ({risk['cash_remaining_pct']*100:.1f}%)")
    print(f"  Positions:      {risk['positions_count']}")
    print(f"  Avg size:       Rs {risk['avg_position_size']:>10,.0f}")
    print(f"  Total risk:     Rs {risk['total_risk']:>10,.0f}  ({risk['total_risk_pct']*100:.1f}%)")
    print(f"  Total reward:   Rs {risk['total_reward']:>10,.0f}  ({risk['total_reward_pct']*100:.1f}%)")
    print(f"  Max single risk:Rs {risk['max_single_risk']:>10,.0f}")
    print(f"  Portfolio R:R:  {risk['portfolio_risk_reward']:.2f}")
    print(f"  Expected PnL:   Rs {risk['expected_pnl']:>10,.0f}  ({risk['expected_pnl_pct']*100:.2f}% of capital)")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    _demo()
