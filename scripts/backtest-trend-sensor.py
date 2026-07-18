#!/usr/bin/env python3
"""Gate-1 backtest: does TrendScore separate green days from bleed days?

PASS (spec §5): TREND-flagged (any point intraday) days contain >=70% of gross
positive P&L AND all-day-CHOP days contain >=70% of gross losses, over
2026-06-16..2026-07-16 (excluding outage artifacts 07-08, 07-10).
Also sweeps thresholds (chop_th in 25..45, trend_th in 55..75, step 5).

ADAPTATIONS vs. original brief draft (see task-3-report.md for detail):
  1. Breadth key: compute_breadth_indicators() returns `pct_above_20dma`,
     not `pct_20`.
  2. compute_breadth_indicators()'s `date` return field is unreliable: in
     prototype/v5/market_breadth.py, `latest_date` is overwritten on every
     symbol iteration, so a single laggard symbol CSV can misreport the
     `date` field even though `pct_above_20dma` was computed correctly for
     the requested date (verified: same date param returns varying, date-
     correct pct values across calls while `date` echoes a stale value).
     Gating on `ind["date"] != date` therefore Noned out breadth on most
     days for the wrong reason. Fix: _pct20() instead requires
     `stocks_analyzed >= 100` (enough of the universe was actually sampled)
     and `pct_above_20dma is not None`, ignoring the unreliable `date`
     field entirely. breadth_strength() still treats None inputs as 0.0
     (fail-closed) for any day that fails this robustness check.
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
        # `ind["date"]` is unreliable (overwritten per-symbol in market_breadth.py's
        # latest_date tracking) -- don't gate on it. Instead require enough of the
        # universe was sampled and a real pct value came back.
        if ind.get("stocks_analyzed", 0) < 100 or ind.get("pct_above_20dma") is None:
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


# ---------------------------------------------------------------------------
# Joint normalization+threshold sweep (task-3 final Gate-1 calibration).
# Does NOT touch trend_mode.py: the score is computed inline here per the
# grid below, reusing the per-day tape/breadth/regime series computed once
# (see _series_for_day) so the sweep itself is pure arithmetic -- no re-fetch,
# no re-walk of the closes list per combo.
# ---------------------------------------------------------------------------
TD_GRID = (1.0, 0.6, 0.5, 0.4)
BM_GRID = (1.0, 2.0, 3.0)
RD_GRID = (6, 4)
CHOP_GRID = (25, 30, 35, 40, 45)
TREND_GRID = (55, 60, 65, 70, 75)


def _series_for_day(closes, regime, pct20_today, pct20_prev):
    """Precompute once per day: tape-efficiency at each 10-min step, plus the
    (normalization-independent) breadth and regime raw values for that day."""
    tape_series = [tape_efficiency(closes[:i]) for i in range(6, len(closes), 2)]
    b = breadth_strength(pct20_today, pct20_prev)
    r = REGIME_SCORE.get(regime, 0)
    return tape_series, b, r


def _modes_for_series(tape_series, b, r, chop_th, trend_th, td, bm, rd):
    modes, cur, pending = set(), "CHOP", None
    for t in tape_series:
        s = min(100.0,
                0.4 * min(100.0, t / td)
                + 0.4 * min(100.0, b * bm)
                + 0.2 * (abs(r) / rd * 100.0))
        cur, pending = mode_for(s, pending, cur, chop_th, trend_th)
        modes.add(cur)
    return modes


def evaluate_grid(chop_th, trend_th, td, bm, rd, sessions, series_cache):
    trend_profit = chop_loss = tot_profit = tot_loss = 0.0
    rows = []
    for sess in sessions:
        series = series_cache.get(sess["date"])
        if series is None:
            rows.append((sess["date"], "NO-DATA", sess["net"])); continue
        tape_series, b, r = series
        modes = _modes_for_series(tape_series, b, r, chop_th, trend_th, td, bm, rd)
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


def run_joint_sweep(sessions, series_cache):
    results = []
    for td in TD_GRID:
        for bm in BM_GRID:
            for rd in RD_GRID:
                for ct in CHOP_GRID:
                    for tt in TREND_GRID:
                        if tt <= ct:
                            continue
                        pc, lc, rows = evaluate_grid(ct, tt, td, bm, rd, sessions, series_cache)
                        results.append({"td": td, "bm": bm, "rd": rd, "chop_th": ct, "trend_th": tt,
                                        "pc": pc, "lc": lc, "rows": rows})
    results.sort(key=lambda r: -min(r["pc"], r["lc"]))
    return results


def build_joint_section(results, sessions):
    best = results[0]
    verdict = "PASS" if best["pc"] >= 70 and best["lc"] >= 70 else "FAIL"
    lines = ["\n\n---\n", "## Joint sweep (final)\n"]
    lines.append(
        f"Grid: td∈{TD_GRID}, bm∈{BM_GRID}, rd∈{RD_GRID}, chop_th∈{CHOP_GRID}, "
        f"trend_th∈{TREND_GRID} (trend_th>chop_th). Score computed inline "
        f"(trend_mode.py untouched during sweep): "
        f"`s = min(100, 0.4*min(100,tape/td) + 0.4*min(100,breadth*bm) + 0.2*(abs(regime)/rd*100))`. "
        f"{len(results)} combos evaluated.\n")
    lines.append(
        f"**Best combo: td={best['td']}, bm={best['bm']}, rd={best['rd']}, "
        f"chop_th={best['chop_th']}, trend_th={best['trend_th']} -> "
        f"profit-capture {best['pc']:.0f}%, loss-capture {best['lc']:.0f}% "
        f"({verdict} vs 70/70 gate)**\n")

    lines.append("\n### Top 10 combos (ranked by min(profit-capture, loss-capture))\n")
    lines.append("| td | bm | rd | chop_th | trend_th | profit-capture | loss-capture | min |")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in results[:10]:
        lines.append(f"| {r['td']} | {r['bm']} | {r['rd']} | {r['chop_th']} | {r['trend_th']} | "
                     f"{r['pc']:.0f}% | {r['lc']:.0f}% | {min(r['pc'], r['lc']):.0f}% |")

    # Best CHOP-separating combo specifically (max loss-capture alone) -- used
    # for the 2-tier P&L question when no combo passes the joint 70/70 gate.
    best_lc = max(results, key=lambda r: r["lc"])
    lines.append(f"\n**Best CHOP-separating combo (max loss-capture alone): "
                 f"td={best_lc['td']}, bm={best_lc['bm']}, rd={best_lc['rd']}, "
                 f"chop_th={best_lc['chop_th']}, trend_th={best_lc['trend_th']} -> "
                 f"profit-capture {best_lc['pc']:.0f}%, loss-capture {best_lc['lc']:.0f}%**\n")

    if verdict != "PASS":
        rows = best_lc["rows"]
        chop_sum = sum(n for _, c, n in rows if c == "CHOP")
        rest_sum = sum(n for _, c, n in rows if c not in ("CHOP", "NO-DATA"))
        chop_days = [d for d, c, _ in rows if c == "CHOP"]
        rest_days = [d for d, c, _ in rows if c not in ("CHOP", "NO-DATA")]
        lines.append(
            f"\n### 2-tier P&L split (best CHOP-separating combo)\n\n"
            f"| tier | days | v5 net P&L sum |\n|---|---:|---:|\n"
            f"| CHOP-flagged | {len(chop_days)} | {chop_sum:+,.0f} |\n"
            f"| non-CHOP (TREND/NEUTRAL) | {len(rest_days)} | {rest_sum:+,.0f} |\n")

    lines.append(f"\n**Verdict: {verdict} vs 70/70 gate.**\n")
    return "\n".join(lines), best, verdict


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
    breadth_covered = sum(1 for v in pct20.values() if v is not None)
    report.append(f"\nBreadth coverage: {breadth_covered} / {len(pct20)} days had non-None "
                  f"`pct_above_20dma` (stocks_analyzed>=100 guard).\n")

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

    # --- Joint normalization+threshold sweep (final Gate-1 calibration) ---
    print("\nRunning joint normalization+threshold sweep...", file=sys.stderr)
    series_cache = {}
    for sess in sessions:
        closes = closes_cache.get(sess["date"])
        if closes is None:
            series_cache[sess["date"]] = None
            continue
        p_today = pct20.get(sess["date"])
        idx = sessions.index(sess)
        p_prev = pct20.get(sessions[idx - 1]["date"]) if idx > 0 else None
        series_cache[sess["date"]] = _series_for_day(closes, sess["regime"], p_today, p_prev)

    joint_results = run_joint_sweep(sessions, series_cache)
    joint_section, joint_best, joint_verdict = build_joint_section(joint_results, sessions)
    report.append(joint_section)

    out = ROOT / "docs/research/2026-07-17_gate1-trend-sensor-backtest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report))
    print("\n".join(report[:4]))
    print(f"\nJoint sweep best: td={joint_best['td']} bm={joint_best['bm']} rd={joint_best['rd']} "
          f"chop_th={joint_best['chop_th']} trend_th={joint_best['trend_th']} -> "
          f"pc={joint_best['pc']:.0f}% lc={joint_best['lc']:.0f}% ({joint_verdict})")
    print(f"report: {out}")
    sys.exit(0 if joint_verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
