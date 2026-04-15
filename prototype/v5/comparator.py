"""
TradePilot v5 Comparator — Daily v4 vs v5 Comparison
=====================================================
Runs alongside v4 paper trading. Logs what v5 WOULD have done differently.
At EOD, generates comparison report showing the delta.

Usage:
    python3 -m prototype.v5.comparator              # Run comparison for today
    python3 -m prototype.v5.comparator --report      # Generate EOD report
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("v5.comparator")

_PROJECT = Path(__file__).resolve().parent.parent.parent
_V4_TRADES = _PROJECT / "docs" / "paper-trades" / "v4"
_V5_DIR = _PROJECT / "docs" / "paper-trades" / "v5"
_V5_DIR.mkdir(parents=True, exist_ok=True)


def load_v4_state(date: str = None) -> dict:
    """Load v4 paper trading state for a given date."""
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")
    path = _V4_TRADES / f"{date}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def simulate_v5_decisions(date: str = None) -> dict:
    """
    Simulate what v5 would have decided today.
    Uses regime detector + premarket intel to calculate adjusted sizing.
    """
    from .regime_detector import detect_regime
    from .premarket_intel import get_premarket_intel

    regime = detect_regime()
    premarket = get_premarket_intel()

    regime_mult = regime.get("allocation", 0.75)
    premarket_mult = premarket.get("overall", {}).get("size_multiplier", 1.0)
    combined_mult = regime_mult * premarket_mult

    v4_state = load_v4_state(date)
    v4_pool = v4_state.get("daily_pool", 1_000_000)
    v4_deployed = v4_state.get("total_deployed", 0)
    v4_pnl = v4_state.get("realized_pnl", 0)
    v4_trades = len(v4_state.get("closed_trades", []))
    v4_wins = sum(1 for t in v4_state.get("closed_trades", []) if t.get("pnl", 0) > 0)

    # v5 would have deployed less capital
    v5_effective_pool = v4_pool * combined_mult
    # Estimate v5 P&L: same loss rate but on smaller capital
    v4_loss_rate = v4_pnl / max(v4_deployed, 1) if v4_deployed > 0 else 0
    v5_estimated_deployed = v4_deployed * combined_mult
    v5_estimated_pnl = v5_estimated_deployed * v4_loss_rate

    # v5 circuit breaker would have stopped after 5 consecutive losses
    closed = v4_state.get("closed_trades", [])
    consecutive = 0
    cb_trade_idx = None
    for i, t in enumerate(closed):
        if t.get("pnl", 0) <= 0:
            consecutive += 1
            if consecutive >= 5 and cb_trade_idx is None:
                cb_trade_idx = i + 1
        else:
            consecutive = 0

    # Calculate P&L if circuit breaker had fired
    if cb_trade_idx is not None and cb_trade_idx < len(closed):
        pnl_before_cb = sum(t.get("pnl", 0) for t in closed[:cb_trade_idx])
        pnl_after_cb = sum(t.get("pnl", 0) for t in closed[cb_trade_idx:])
        v5_cb_pnl = pnl_before_cb * combined_mult  # CB stops further losses
    else:
        pnl_before_cb = v4_pnl
        pnl_after_cb = 0
        v5_cb_pnl = v4_pnl * combined_mult

    # Max re-entry savings
    stock_entries = {}
    reentry_waste = 0
    for t in closed:
        sym = t.get("symbol", "")
        stock_entries[sym] = stock_entries.get(sym, 0) + 1
        if stock_entries[sym] > 2:  # v5 caps at 1 re-entry (2 total)
            reentry_waste += abs(t.get("pnl", 0))

    comparison = {
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "regime": {
            "state": regime.get("regime", "UNKNOWN"),
            "score": regime.get("score", 0),
            "allocation_mult": regime_mult,
        },
        "premarket": {
            "gap": premarket.get("gap", {}).get("direction", "UNKNOWN"),
            "gap_pct": premarket.get("gap", {}).get("magnitude_pct", 0),
            "fii": premarket.get("fii", {}).get("direction", "UNKNOWN"),
            "global": premarket.get("global", {}).get("direction", "UNKNOWN"),
            "size_mult": premarket_mult,
        },
        "combined_multiplier": round(combined_mult, 2),
        "v4": {
            "pool": v4_pool,
            "deployed": v4_deployed,
            "pnl": round(v4_pnl, 2),
            "pnl_pct": round(v4_pnl / v4_pool * 100, 2) if v4_pool else 0,
            "trades": v4_trades,
            "wins": v4_wins,
            "win_rate": round(v4_wins / v4_trades * 100, 1) if v4_trades else 0,
        },
        "v5_estimated": {
            "effective_pool": round(v5_effective_pool, 0),
            "deployed": round(v5_estimated_deployed, 0),
            "pnl_no_cb": round(v5_estimated_pnl, 2),
            "pnl_with_cb": round(v5_cb_pnl, 2),
            "trades_before_cb": cb_trade_idx or v4_trades,
            "savings_from_cb": round(abs(pnl_after_cb * combined_mult), 2),
            "savings_from_reentry_cap": round(reentry_waste * combined_mult, 2),
        },
        "delta": {
            "pnl_saved": round(v4_pnl - v5_cb_pnl, 2),
            "pnl_saved_pct": round((v4_pnl - v5_cb_pnl) / abs(v4_pnl) * 100, 1) if v4_pnl != 0 else 0,
        },
    }

    return comparison


def print_comparison(comp: dict):
    """Pretty-print the v4 vs v5 comparison."""
    print(f"\n{'='*65}")
    print(f"  v4 vs v5 COMPARISON  |  {comp['date']}")
    print(f"{'='*65}")

    r = comp["regime"]
    p = comp["premarket"]
    print(f"\n  REGIME: {r['state']} (score {r['score']}, alloc {r['allocation_mult']:.0%})")
    print(f"  PRE-MARKET: gap={p['gap']} {p['gap_pct']:+.2f}%, FII={p['fii']}, global={p['global']}")
    print(f"  COMBINED SIZE: {comp['combined_multiplier']:.0%}")

    v4 = comp["v4"]
    v5 = comp["v5_estimated"]
    print(f"\n  {'':>20s}  {'v4 (actual)':>14s}  {'v5 (estimated)':>14s}  {'Delta':>12s}")
    print(f"  {'-'*62}")
    print(f"  {'Pool':>20s}  Rs {v4['pool']:>10,.0f}  Rs {v5['effective_pool']:>10,.0f}")
    print(f"  {'Deployed':>20s}  Rs {v4['deployed']:>10,.0f}  Rs {v5['deployed']:>10,.0f}")
    print(f"  {'P&L':>20s}  Rs {v4['pnl']:>+10,.0f}  Rs {v5['pnl_with_cb']:>+10,.0f}  Rs {comp['delta']['pnl_saved']:>+10,.0f}")
    print(f"  {'P&L %':>20s}  {v4['pnl_pct']:>+10.2f}%  {v5['pnl_with_cb']/v4['pool']*100 if v4['pool'] else 0:>+10.2f}%")
    print(f"  {'Trades':>20s}  {v4['trades']:>10d}  {v5['trades_before_cb']:>10d}")
    print(f"  {'Win Rate':>20s}  {v4['win_rate']:>9.0f}%")

    d = comp["delta"]
    print(f"\n  SAVINGS:")
    print(f"    Regime + premarket sizing:  Rs {abs(v4['pnl'] - v5['pnl_with_cb']):>+,.0f}")
    print(f"    Circuit breaker:            Rs {v5['savings_from_cb']:>+,.0f}")
    print(f"    Re-entry cap:               Rs {v5['savings_from_reentry_cap']:>+,.0f}")
    print(f"    TOTAL SAVED:                Rs {d['pnl_saved']:>+,.0f} ({d['pnl_saved_pct']:+.0f}%)")
    print(f"{'='*65}")


def save_comparison(comp: dict):
    """Save comparison to JSON."""
    path = _V5_DIR / f"{comp['date']}_comparison.json"
    with open(path, "w") as f:
        json.dump(comp, f, indent=2)
    return path


def main():
    import sys
    logging.basicConfig(level=logging.WARNING)

    comp = simulate_v5_decisions()
    print_comparison(comp)
    path = save_comparison(comp)
    print(f"\n  Saved: {path}")


if __name__ == "__main__":
    main()
