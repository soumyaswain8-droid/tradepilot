#!/usr/bin/env python3
"""Weekly TradePilot stats tracker.

Run every Monday morning. Outputs cumulative P&L, deflated Sharpe, and 95% CI per engine.
Anchored to the 2026-05-25 decision-gate criteria from IMPLEMENTATION_BRIEF_2026-04-27.md §4.

Usage:
    python3 scripts/weekly-stats-tracker.py
"""
import re
import sys
from pathlib import Path

import numpy as np

PT = Path(__file__).parent.parent / "docs/paper-trades"
ENGINES = ["v5", "v5_classic", "v5_6", "v5_7"]  # surviving engines (post 2026-04-27 retirement)
PNL_RE = re.compile(r"Net P&L\*\*\s*\|\s*\*\*Rs\s*([-\d,]+)")
WIN_RE = re.compile(r"Win Rate\s*\|\s*([\d]+)%")
CAPITAL = 1_000_000  # ₹10L paper book


def load_engine(engine: str):
    """Read all daily reports for the engine; return list of (date, pnl, win_rate)."""
    rows = []
    eng_dir = PT / engine
    if not eng_dir.exists():
        return rows
    for f in sorted(eng_dir.glob("2026-*_report.md")):
        text = f.read_text(errors="ignore")
        m = PNL_RE.search(text)
        w = WIN_RE.search(text)
        if m:
            rows.append({
                "date": f.stem.replace("_report", ""),
                "pnl": int(m.group(1).replace(",", "")),
                "win_rate": int(w.group(1)) if w else None,
            })
    return rows


def deflated_sharpe(pnls: np.ndarray, n_trials: int = 4) -> float | None:
    """Lopez de Prado's Deflated Sharpe Ratio (simplified).
    Adjusts for selection bias (n_trials engines) and sample size.
    """
    if len(pnls) < 2:
        return None
    daily_ret = pnls / CAPITAL
    if daily_ret.std() == 0:
        return 0.0
    raw_sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(252)
    selection_haircut = max(0.0, 1 - 0.05 * (n_trials - 1))
    sample_haircut = min(1.0, len(pnls) / 252) ** 0.5
    return raw_sharpe * selection_haircut * sample_haircut


def t_critical(df: int, alpha: float = 0.05) -> float:
    """Two-sided t critical without scipy. Approximation good for df>=2.
    Falls back to z=1.96 for df>=30 (CLT)."""
    if df >= 30:
        return 1.96
    # Hardcoded table for small df (two-sided 95%)
    table = {2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447,
             7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201,
             12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131, 16: 2.120,
             17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 25: 2.060}
    return table.get(df, 2.04)


def main():
    print(f"\n{'='*110}\nTradePilot Weekly Stats Tracker\n{'='*110}\n")
    print(f"{'Engine':<12} {'Days':>5} {'Total P&L':>14} {'Mean/day':>12} "
          f"{'95% CI':>30} {'Raw Sh.':>9} {'Defl. Sh.':>11} {'Win days':>10}")
    print("-" * 110)

    # Aggregate snapshots for the gate criteria evaluation
    summary = {}
    for eng in ENGINES:
        rows = load_engine(eng)
        if not rows:
            print(f"{eng:<12} {'0':>5} {'(no reports)':>14}")
            continue
        pnls = np.array([r["pnl"] for r in rows], dtype=float)
        n = len(pnls)
        mean = pnls.mean()
        std = pnls.std(ddof=1) if n > 1 else 0.0
        if n >= 2 and std > 0:
            t_crit = t_critical(n - 1)
            margin = t_crit * std / np.sqrt(n)
            ci_low = mean - margin
            ci_high = mean + margin
            ci_str = f"[Rs {ci_low:>+8,.0f}, Rs {ci_high:>+8,.0f}]"
        else:
            ci_low, ci_high = 0, 0
            ci_str = "n<2"
        sharpe = (pnls / CAPITAL).mean() / (pnls / CAPITAL).std(ddof=1) * np.sqrt(252) if n > 1 and std > 0 else 0
        defl = deflated_sharpe(pnls, n_trials=len(ENGINES)) or 0
        win_days = int((pnls > 0).sum())
        sig = " *" if (n >= 2 and ci_low > 0) else ""
        print(f"{eng:<12} {n:>5d} Rs {pnls.sum():>+11,.0f} Rs {mean:>+9,.0f} {ci_str:>30} "
              f"{sharpe:>+9.2f} {defl:>+10.2f} {win_days}/{n}{sig}")
        summary[eng] = dict(n=n, mean=mean, ci_low=ci_low, ci_high=ci_high,
                            sharpe=sharpe, defl=defl, win_days=win_days, total=pnls.sum())

    # Decision-gate criteria from brief §4
    print()
    print("=" * 110)
    print("Decision-gate criteria for 2026-05-25 (per IMPLEMENTATION_BRIEF §4):")
    print("=" * 110)
    print()
    v5 = summary.get("v5", {})
    v5_6 = summary.get("v5_6", {})
    v5_7 = summary.get("v5_7", {})
    crit1 = v5.get("ci_low", 0) > 3000 and v5.get("n", 0) >= 30
    crit2 = (v5_6.get("ci_low", 0) > 0 and v5_6.get("n", 0) >= 30) or \
            (v5_7.get("ci_low", 0) > 0 and v5_7.get("n", 0) >= 30)
    crit3 = False  # drawdown observed AND recovered — manual flag
    crit4 = v5.get("defl", 0) >= 2.0

    def mark(b): return "PASS" if b else "FAIL"
    print(f"  1. v5 95% CI > 0 (lower bound > Rs 3,000 AND days >= 30)            {mark(crit1)}")
    print(f"  2. v5_6 OR v5_7 95% CI > 0 (days >= 30)                              {mark(crit2)}")
    print(f"  3. >= 1 drawdown of 5%+ observed AND recovered within 5 days         {'PASS' if crit3 else 'PENDING (manual)'}")
    print(f"  4. v5 deflated Sharpe >= 2.0                                         {mark(crit4)}")
    print()
    n_pass = sum([crit1, crit2, crit3, crit4])
    print(f"  Criteria passed: {n_pass}/4")
    print()
    if n_pass == 4:
        action = "Start ML rebuild Track B + small-scale live trading at Rs 50k"
    elif n_pass == 3:
        action = "Extend observation by 30 days. Re-evaluate 2026-06-25"
    elif n_pass == 2:
        action = "Investigate root cause; possibly revert Track A changes"
    else:
        action = "Pause TradePilot indefinitely; reallocate engineering effort"
    print(f"  Suggested action: {action}")
    print()
    print("=" * 110)


if __name__ == "__main__":
    main()
