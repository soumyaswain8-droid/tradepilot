#!/usr/bin/env python3
"""Gate-1 backtest: approach (b) RRG regime sensor -- defensive-vs-cyclical
relative-return spread (no JdK EMA machinery), per
docs/superpowers/specs/2026-07-20-rrg-regime-sensor-design.md §3b/§4/§6/§7.

PASS bar (same as trend-sensor Gate-1, spec §6.5): the best (form, set-
variant, lookback, threshold) combo must reach >=70% profit-capture (gross
positive P&L on non-CHOP-flagged days) AND >=70% loss-capture (gross losses
on CHOP-flagged days), over 2026-06-16..2026-07-16 excluding the 07-08/07-10
outage days. Ground truth = docs/paper-trades/v5/*.json net P&L, same as
scripts/backtest-trend-sensor.py.

Sensor (approach b): daily close-to-close relative return of each sector
index vs ^NSEI, over lookback N in {1,3,5} trading days. Two signal forms:
  spread = mean(defensive rel) - mean(cyclical rel)
  count  = frac(defensive rel>0) - frac(cyclical rel>0)   [normalized by
           the number of *present* members in each set that day, per the
           fail-closed rule below]
Day t is classified CHOP (risk-off / throttle) when the signal >= threshold
(defensive leadership dominant), else TREND. This is a single-threshold
binary classifier -- unlike TrendScore's 3-tier chop_th/trend_th hysteresis,
approach (b) has no momentum/direction term to justify a NEUTRAL band.

NO-LOOKAHEAD (hard requirement, spec STATUS block): the signal for session
date t uses daily closes up to and including t-1 ONLY -- never a same-day
close. Enforced by construction (rel returns are computed from
trading_days[pos-1] and earlier, where `pos` is the position t would occupy
in the NSEI trading-day calendar) plus an explicit assertion per session.

FAIL-CLOSED (spec §4): a sector with a missing/NaN close for a needed date
is excluded from its set that day. If either set (defensive/cyclical) then
has <2 present members, the day is NO-DATA (excluded from capture stats,
counted and reported).

Usage: python3 scripts/backtest-rrg-sensor.py
"""
import bisect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import yfinance as yf

START, END = "2026-06-16", "2026-07-16"
EXCLUDE = {"2026-07-08", "2026-07-10"}
# Fetch window: warmup for N=5 trading-day lookback plus margin before START,
# through END (one day of intraday spillover in the end bound is harmless --
# only closes strictly before each session date are ever used).
FETCH_START, FETCH_END = "2026-05-01", "2026-07-17"
MIN_SCORABLE_DAYS = 15  # per task CONSTRAINTS: abort if coverage can't clear this

BENCHMARK = "^NSEI"
DEFENSIVE = ["^CNXPHARMA", "^CNXFMCG", "NIFTY_HEALTHCARE.NS"]
CYCLICAL_BASE = ["^NSEBANK", "^CNXAUTO", "^CNXMETAL", "^CNXREALTY"]
CYCLICAL_EXT_ADD = ["^CNXPSUBANK", "NIFTYPVTBANK.NS", "NIFTY_FIN_SERVICE.NS"]
CYCLICAL_EXTENDED = CYCLICAL_BASE + CYCLICAL_EXT_ADD
SET_VARIANTS = {"base": CYCLICAL_BASE, "extended": CYCLICAL_EXTENDED}
N_GRID = (1, 3, 5)
FORMS = ("spread", "count")
ALL_TICKERS = sorted(set([BENCHMARK] + DEFENSIVE + CYCLICAL_EXTENDED))


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


def _fetch_daily(ticker):
    """Fetch once per ticker (daily bars, cheap/not rate-limited like 5m); cache in-memory."""
    try:
        df = yf.download(ticker, start=FETCH_START, end=FETCH_END, interval="1d", progress=False)
    except Exception as e:
        print(f"  {ticker}: FETCH ERROR {e}", file=sys.stderr)
        return {}
    if df is None or len(df) == 0:
        return {}
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    closes = df["Close"].dropna()
    return {str(idx.date()): float(v) for idx, v in closes.items()}


def _rel(closes, ticker, trading_days, pos, N):
    """N-day close-to-close return for `ticker`, using only trading_days[pos-1] and
    trading_days[pos-1-N] -- both strictly before position `pos` (session date t)."""
    i1 = pos - 1
    i0 = pos - 1 - N
    if i0 < 0:
        return None
    c1 = closes[ticker].get(trading_days[i1])
    c0 = closes[ticker].get(trading_days[i0])
    if c1 is None or c0 is None:
        return None
    return c1 / c0 - 1


def _day_signal_inputs(closes, trading_days, pos, N, cyclical_set):
    """Fail-closed per spec §4: missing sector close -> excluded from its set;
    <2 present members in either set -> whole day NO-DATA (returns None)."""
    b = _rel(closes, BENCHMARK, trading_days, pos, N)
    if b is None:
        return None  # benchmark missing -> can't compute any rel return this day
    def_rels = []
    for t in DEFENSIVE:
        r = _rel(closes, t, trading_days, pos, N)
        if r is not None:
            def_rels.append(r - b)
    cyc_rels = []
    for t in cyclical_set:
        r = _rel(closes, t, trading_days, pos, N)
        if r is not None:
            cyc_rels.append(r - b)
    if len(def_rels) < 2 or len(cyc_rels) < 2:
        return None
    return {"def_rels": def_rels, "cyc_rels": cyc_rels}


def _signal(form, inputs):
    def_rels, cyc_rels = inputs["def_rels"], inputs["cyc_rels"]
    if form == "spread":
        return (sum(def_rels) / len(def_rels)) - (sum(cyc_rels) / len(cyc_rels))
    # form == "count": fraction (not raw count) so it's set-size-normalized
    pos_def = sum(1 for r in def_rels if r > 0) / len(def_rels)
    pos_cyc = sum(1 for r in cyc_rels if r > 0) / len(cyc_rels)
    return pos_def - pos_cyc


def _threshold_grid(values):
    """Deciles of the in-window signal distribution plus 0.0, per spec §3b."""
    if not values:
        return [0.0]
    s = pd.Series(values)
    qs = {round(float(s.quantile(q / 10.0)), 6) for q in range(1, 10)}
    qs.add(0.0)
    return sorted(qs)


def evaluate(form, sv_name, threshold, sessions, per_day):
    trend_profit = chop_loss = tot_profit = tot_loss = 0.0
    rows = []
    for sess in sessions:
        d, net = sess["date"], sess["net"]
        inputs = per_day.get(d)
        if inputs is None:
            rows.append((d, None, "NO-DATA", net))
            continue
        sig = _signal(form, inputs)
        cls = "CHOP" if sig >= threshold else "TREND"
        rows.append((d, sig, cls, net))
        if net > 0:
            tot_profit += net
            if cls == "TREND":
                trend_profit += net
        else:
            tot_loss += -net
            if cls == "CHOP":
                chop_loss += -net
    pc = 100 * trend_profit / tot_profit if tot_profit else 0.0
    lc = 100 * chop_loss / tot_loss if tot_loss else 0.0
    return pc, lc, rows


def main():
    sessions = _sessions()

    print(f"Fetching daily closes for {len(ALL_TICKERS)} tickers "
          f"({FETCH_START}..{FETCH_END})...", file=sys.stderr)
    closes = {}
    coverage = []
    for t in ALL_TICKERS:
        c = _fetch_daily(t)
        closes[t] = c
        if c:
            ds = sorted(c.keys())
            coverage.append({"ticker": t, "n": len(ds), "first": ds[0], "last": ds[-1]})
            print(f"  {t}: {len(c)} bars [{ds[0]}..{ds[-1]}]", file=sys.stderr)
        else:
            coverage.append({"ticker": t, "n": 0, "first": None, "last": None})
            print(f"  {t}: NO-DATA", file=sys.stderr)

    trading_days = sorted(closes.get(BENCHMARK, {}).keys())
    if not trading_days:
        print("FATAL: no ^NSEI benchmark data fetched -- cannot score any day, aborting.",
              file=sys.stderr)
        sys.exit(1)
    bench_span = f"{trading_days[0]}..{trading_days[-1]}"
    expected_days = [d for d in trading_days if FETCH_START <= d <= FETCH_END]

    # --- No-lookahead self-check (hard requirement) ---
    # pos = the position session date `d` would occupy in the ^NSEI trading-day
    # calendar (bisect_left); trading_days[pos-1] is therefore always strictly
    # before `d`, by construction. Assert it explicitly per session anyway.
    day_pos = {}
    lookahead_notes = []
    lookahead_ok = True
    for sess in sessions:
        d = sess["date"]
        pos = bisect.bisect_left(trading_days, d)
        day_pos[d] = pos
        if pos >= 1:
            last_used = trading_days[pos - 1]
            try:
                assert last_used < d, f"NO-LOOKAHEAD VIOLATION: last_used={last_used} >= t={d}"
            except AssertionError as e:
                lookahead_ok = False
                lookahead_notes.append(str(e))
        else:
            lookahead_notes.append(f"{d}: no prior trading day in fetch window (insufficient warmup)")

    # --- Build per (set-variant, N) signal-input cache (fail-closed) ---
    signal_inputs_cache = {}
    for sv_name, cyc_set in SET_VARIANTS.items():
        for N in N_GRID:
            per_day = {}
            for sess in sessions:
                d = sess["date"]
                pos = day_pos.get(d)
                per_day[d] = None if pos is None or pos < 1 else \
                    _day_signal_inputs(closes, trading_days, pos, N, cyc_set)
            signal_inputs_cache[(sv_name, N)] = per_day

    # --- Coverage gate (task CONSTRAINTS): abort if too broken to score ---
    scorable_days = {
        d for d in (s["date"] for s in sessions)
        if any(signal_inputs_cache[(sv, N)].get(d) is not None
               for sv in SET_VARIANTS for N in N_GRID)
    }
    if len(scorable_days) < MIN_SCORABLE_DAYS:
        report = ["# Gate-1 RRG sensor (approach b) backtest -- ABORTED (insufficient coverage)", ""]
        report.append(f"**ABORTED**: only {len(scorable_days)}/{len(sessions)} sessions "
                       f"scorable by any (set-variant, N) combo, below the "
                       f"{MIN_SCORABLE_DAYS}-day floor.\n")
        report.append("## Per-ticker coverage\n\n| ticker | bars | first | last |\n|---|---:|---|---|")
        for c in coverage:
            report.append(f"| {c['ticker']} | {c['n']} | {c['first'] or '-'} | {c['last'] or '-'} |")
        report.append(f"\n^NSEI trading-day calendar span in fetch window: {bench_span} "
                       f"({len(expected_days)} trading days)\n")
        out = ROOT / "docs/research/2026-07-20_gate1-rrg-sensor-backtest.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(report))
        print("\n".join(report[:3]))
        print(f"report: {out}")
        sys.exit(1)

    # --- Full sweep ---
    results = []
    grids_used = {}
    for form in FORMS:
        for sv_name in SET_VARIANTS:
            for N in N_GRID:
                per_day = signal_inputs_cache[(sv_name, N)]
                values = [_signal(form, per_day[d]) for d in per_day if per_day[d] is not None]
                grid = _threshold_grid(values)
                grids_used[(form, sv_name, N)] = grid
                for th in grid:
                    pc, lc, rows = evaluate(form, sv_name, th, sessions, per_day)
                    results.append({"form": form, "set": sv_name, "N": N, "threshold": th,
                                     "pc": pc, "lc": lc, "rows": rows})
    results.sort(key=lambda r: -min(r["pc"], r["lc"]))
    best = results[0]
    verdict = "PASS" if best["pc"] >= 70 and best["lc"] >= 70 else "FAIL"

    # --- NO-DATA summary per (set-variant, N) ---
    no_data_by_combo = {}
    for sv_name in SET_VARIANTS:
        for N in N_GRID:
            per_day = signal_inputs_cache[(sv_name, N)]
            no_data_by_combo[(sv_name, N)] = sum(1 for d in per_day if per_day[d] is None)
    best_no_data = sum(1 for r in best["rows"] if r[2] == "NO-DATA")

    # --- Report ---
    report = ["# Gate-1 RRG sensor (approach b) backtest — generated by "
              "scripts/backtest-rrg-sensor.py", ""]
    report.append(
        f"**Best: form={best['form']}, set={best['set']}, N={best['N']}, "
        f"threshold={best['threshold']:.4f} -> profit-capture {best['pc']:.0f}%, "
        f"loss-capture {best['lc']:.0f}% ({verdict} vs 70/70 gate)**\n")

    report.append(
        "Sensor: daily close-to-close relative return of each sector index vs ^NSEI "
        "(no JdK EMA machinery, per spec §3b), N-day lookback in {1,3,5}. `spread` form = "
        "mean(defensive rel) - mean(cyclical rel); `count` form = frac(defensive rel>0) - "
        "frac(cyclical rel>0), normalized by present-member set size that day. Day t is "
        "CHOP (risk-off/throttle) when signal >= threshold, else TREND -- a single-threshold "
        "binary classifier (approach b has no momentum term to justify a NEUTRAL band, "
        "unlike TrendScore's chop_th/trend_th hysteresis pair). Threshold grid = deciles of "
        "the in-window signal distribution plus 0.0, computed independently per "
        "(form, set-variant, N) combo.\n")

    report.append(f"\nNo-lookahead check: **{'PASSED' if lookahead_ok else 'FAILED'}** "
                   f"({len(sessions)} sessions verified: last close date used for day t is "
                   f"strictly < t, by construction from the ^NSEI trading-day calendar "
                   f"position + explicit per-session assertion).\n")
    if lookahead_notes:
        report.append("Lookahead notes:\n" + "\n".join(f"- {n}" for n in lookahead_notes) + "\n")

    report.append(f"\nNO-DATA days for best combo: {best_no_data} / {len(sessions)}\n")
    report.append("\n### NO-DATA count by (set-variant, N)\n\n"
                   "| set-variant | N | NO-DATA days |\n|---|---:|---:|")
    for sv_name in SET_VARIANTS:
        for N in N_GRID:
            report.append(f"| {sv_name} | {N} | {no_data_by_combo[(sv_name, N)]} |")

    report.append(f"\n\n### Threshold grid used (best combo: {best['form']}/{best['set']}/N={best['N']})\n\n"
                   + ", ".join(f"{v:.4f}" for v in grids_used[(best['form'], best['set'], best['N'])]) + "\n")

    report.append("\n## Top 10 combos (ranked by min(profit-capture, loss-capture))\n")
    report.append("| form | set-variant | N | threshold | profit-capture | loss-capture | min |")
    report.append("|---|---|---:|---:|---:|---:|---:|")
    for r in results[:10]:
        report.append(f"| {r['form']} | {r['set']} | {r['N']} | {r['threshold']:.4f} | "
                       f"{r['pc']:.0f}% | {r['lc']:.0f}% | {min(r['pc'], r['lc']):.0f}% |")

    report.append(f"\n## Per-day (best combo: {best['form']}/{best['set']}/N={best['N']}/"
                   f"th={best['threshold']:.4f})\n\n"
                   "| date | signal | class | v5 net |\n|---|---:|---|---:|")
    for d, sig, cls, net in best["rows"]:
        sig_str = f"{sig:.4f}" if sig is not None else "-"
        report.append(f"| {d} | {sig_str} | {cls} | {net:+,.0f} |")

    chop_sum = sum(net for _, _, cls, net in best["rows"] if cls == "CHOP")
    trend_sum = sum(net for _, _, cls, net in best["rows"] if cls == "TREND")
    chop_days = sum(1 for _, _, cls, _ in best["rows"] if cls == "CHOP")
    trend_days = sum(1 for _, _, cls, _ in best["rows"] if cls == "TREND")
    report.append(f"\n## CHOP vs non-CHOP P&L split (best combo)\n\n"
                   "| tier | days | v5 net P&L sum |\n|---|---:|---:|\n"
                   f"| CHOP-flagged | {chop_days} | {chop_sum:+,.0f} |\n"
                   f"| TREND (non-CHOP) | {trend_days} | {trend_sum:+,.0f} |\n")

    report.append("\n## Per-ticker coverage\n\n| ticker | class | bars | first | last |\n"
                   "|---|---|---:|---|---|")
    ticker_class = {}
    for t in DEFENSIVE:
        ticker_class[t] = "defensive"
    for t in CYCLICAL_BASE:
        ticker_class[t] = "cyclical (base)"
    for t in CYCLICAL_EXT_ADD:
        ticker_class[t] = "cyclical (extended-only)"
    ticker_class[BENCHMARK] = "benchmark"
    for c in coverage:
        flag = " ⚠ .NS gap-risk symbol" if c["ticker"].endswith(".NS") else ""
        report.append(f"| {c['ticker']} | {ticker_class.get(c['ticker'], '-')} | {c['n']} | "
                       f"{c['first'] or '-'} | {c['last'] or '-'}{flag} |")
    report.append(f"\n^NSEI trading-day calendar span in fetch window: {bench_span} "
                   f"({len(expected_days)} trading days).\n")

    out = ROOT / "docs/research/2026-07-20_gate1-rrg-sensor-backtest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report))
    print("\n".join(report[:3]))
    print(f"\nBest: form={best['form']} set={best['set']} N={best['N']} "
          f"threshold={best['threshold']:.4f} -> pc={best['pc']:.0f}% lc={best['lc']:.0f}% "
          f"({verdict})")
    print(f"No-lookahead check: {'PASSED' if lookahead_ok else 'FAILED'}")
    print(f"report: {out}")
    sys.exit(0 if verdict == "PASS" else 1)


if __name__ == "__main__":
    main()
