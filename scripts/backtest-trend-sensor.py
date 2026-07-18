#!/usr/bin/env python3
"""Gate-1 backtest: does TrendScore separate green days from bleed days?

PASS (spec §5): TREND-flagged (any point intraday) days contain >=70% of gross
positive P&L AND all-day-CHOP days contain >=70% of gross losses, over
2026-06-16..2026-07-16 (excluding outage artifacts 07-08, 07-10).
Also sweeps thresholds (chop_th in 25..45, trend_th in 55..75, step 5).

ADAPTATIONS vs. original brief draft (see task-3-report.md for detail):
  1. Breadth key: compute_breadth_indicators() returns `pct_above_20dma`,
     not `pct_20`.
  2. Breadth is date-parameterized in signature but the underlying daily
     stock CSVs (prototype/data/*_NS.csv) only extend through 2026-06-08 --
     well before this backtest's window (2026-06-16..07-16). Calling
     compute_breadth_indicators(date=<in-window date>) silently clamps to
     the last available bar (2026-06-08) instead of raising, so every day
     in the window would otherwise get the SAME stale breadth reading.
     Fix: _pct20() detects this clamp (returned 'date' != requested date)
     and returns None for those days. breadth_strength() already treats
     None inputs as 0.0 (fail-closed), so the gate verdict below is, in
     effect, judged on tape + regime only -- breadth contributes nothing.
  3. yfinance 1.2.0 returns MultiIndex columns (Price, Ticker) even for a
     single-ticker download, so `float(c)` on a "Close" cell throws
     TypeError (0-d array required). Columns are flattened after download.

Usage: python3 scripts/backtest-trend-sensor.py
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import yfinance as yf
from prototype.v5.trend_mode import tape_efficiency, breadth_strength, trend_score, mode_for
from prototype.v5.market_breadth import compute_breadth_indicators

START, END = "2026-06-16", "2026-07-16"
EXCLUDE = {"2026-07-08", "2026-07-10"}
REGIME_SCORE = {"BULL": 4, "BEAR": -4, "SIDEWAYS": 0}


def _sessions():
    out = []
    for f in sorted((ROOT / "docs/paper-trades/v5").glob("2026-0[67]-*.json")):
        d = f.name[:10]
        if d < START or d > END or d in EXCLUDE:
            continue
        if f.name != f"{d}.json":
            continue  # skip *_comparison.json siblings
        data = json.loads(f.read_text())
        s = data.get("summary", {})
        if not s.get("trades"):
            continue
        out.append({"date": d, "net": s.get("total_pnl_net", s.get("total_pnl", 0)),
                    "regime": data.get("regime", "SIDEWAYS")})
    return out


def _pct20(date):
    try:
        ind = compute_breadth_indicators(date=date)
        if ind.get("date") != date:
            # Underlying CSVs don't cover this date -- clamped to stale data.
            # Fail closed rather than reuse a stale reading across many days.
            return None
        return ind.get("pct_above_20dma")
    except Exception:
        return None


def _fetch_closes(date):
    """Download once per date (5m bars are expensive/rate-limited); cache result."""
    try:
        n = yf.download("^NSEI", start=date, end=None, interval="5m", progress=False)
        if isinstance(n.columns, pd.MultiIndex):
            n.columns = n.columns.get_level_values(0)
        n = n.loc[str(date)] if len(n) else n
    except KeyError:
        return None  # market holiday / no bars for this specific date -> NO-DATA
    if len(n) < 6:
        return None  # no intraday data -> exclude day from scoring, report it
    return [float(c) for c in n["Close"].dropna().values]


def _modes_for_closes(closes, regime, chop_th, trend_th, pct20_today, pct20_prev):
    """Walk the day's 5-min bars in 10-min steps; return set of modes seen."""
    modes, cur, pending = set(), "CHOP", None
    b = breadth_strength(pct20_today, pct20_prev)
    for i in range(6, len(closes), 2):          # ~every 10 min after first 30 min
        t = tape_efficiency(closes[:i])
        s = trend_score(t, b, REGIME_SCORE.get(regime, 0))
        cur, pending = mode_for(s, pending, cur, chop_th, trend_th)
        modes.add(cur)
    return modes


def evaluate(chop_th, trend_th, sessions, pct20, closes_cache):
    trend_profit = chop_loss = tot_profit = tot_loss = 0.0
    rows = []
    prev_p = None
    for sess in sessions:
        p_today = pct20.get(sess["date"])
        closes = closes_cache.get(sess["date"])
        modes = None if closes is None else _modes_for_closes(
            closes, sess["regime"], chop_th, trend_th, p_today, prev_p)
        prev_p = p_today
        if modes is None:
            rows.append((sess["date"], "NO-DATA", sess["net"])); continue
        day_class = "TREND" if "TREND" in modes else ("CHOP" if modes == {"CHOP"} else "NEUTRAL")
        rows.append((sess["date"], day_class, sess["net"]))
        if sess["net"] > 0:
            tot_profit += sess["net"]
            if day_class == "TREND": trend_profit += sess["net"]
        else:
            tot_loss += -sess["net"]
            if day_class == "CHOP": chop_loss += -sess["net"]
    pc = 100 * trend_profit / tot_profit if tot_profit else 0
    lc = 100 * chop_loss / tot_loss if tot_loss else 0
    return pc, lc, rows


def main():
    sessions = _sessions()
    pct20 = {s["date"]: _pct20(s["date"]) for s in sessions}
    breadth_available = any(v is not None for v in pct20.values())

    print(f"Fetching intraday data for {len(sessions)} sessions...", file=sys.stderr)
    closes_cache = {}
    for i, sess in enumerate(sessions):
        closes_cache[sess["date"]] = _fetch_closes(sess["date"])
        print(f"  [{i+1}/{len(sessions)}] {sess['date']}: "
              f"{'OK' if closes_cache[sess['date']] else 'NO-DATA'}", file=sys.stderr)

    report = ["# Gate-1 TrendScore backtest — generated by scripts/backtest-trend-sensor.py", ""]
    report.append(
        "**Breadth-key finding:** `compute_breadth_indicators()` returns `pct_above_20dma` "
        "(not `pct_20`). Its underlying daily CSVs (`prototype/data/*_NS.csv`) only extend "
        "through 2026-06-08, before this backtest's 2026-06-16..07-16 window, so every "
        "in-window `date=` request silently clamps to that stale bar. `_pct20()` detects the "
        "clamp and returns `None` for all days in this window; `breadth_strength()` treats "
        "`None` as 0.0, so **the gate verdict below is effectively tape+regime only — "
        "breadth contributes nothing.**\n" if not breadth_available else
        "**Breadth-key finding:** key is `pct_above_20dma`; live breadth data was available "
        "for at least one in-window day.\n"
    )

    best = None
    for ct in (25, 30, 35, 40, 45):
        for tt in (55, 60, 65, 70, 75):
            pc, lc, rows = evaluate(ct, tt, sessions, pct20, closes_cache)
            report.append(f"| chop<{ct} trend>={tt} | profit-capture {pc:.0f}% | loss-capture {lc:.0f}% |")
            if best is None or min(pc, lc) > min(best[0], best[1]):
                best = (pc, lc, ct, tt, rows)
    pc, lc, ct, tt, rows = best
    report.insert(2, f"**Best: chop_th={ct}, trend_th={tt} -> profit-capture {pc:.0f}%, loss-capture {lc:.0f}% "
                     f"({'PASS' if pc >= 70 and lc >= 70 else 'FAIL'} vs 70/70 gate)**\n")
    no_data = sum(1 for _, c, _ in rows if c == "NO-DATA")
    report.append(f"\nNO-DATA days: {no_data} / {len(rows)}\n")
    report.append("\n## Per-day (best thresholds)\n\n| date | class | v5 net |\n|---|---|---:|")
    report += [f"| {d} | {c} | {n:+,.0f} |" for d, c, n in rows]
    out = ROOT / "docs/research/2026-07-17_gate1-trend-sensor-backtest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report))
    print("\n".join(report[:4])); print(f"report: {out}")
    sys.exit(0 if pc >= 70 and lc >= 70 else 1)


if __name__ == "__main__":
    main()
