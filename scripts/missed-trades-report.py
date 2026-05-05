#!/usr/bin/env python3
"""
TradePilot Missed-Trades EOD Report
====================================
Compares BUY signals captured at market open against engines' actual entries.
Identifies stocks scored BUY but skipped by all 7 engines, then evaluates
whether skipping was a right call (stock dropped) or wrong call (stock rose).

Inputs:
  docs/dashboard-scores/{date}.json         — pre-market BUY/HOLD/SELL universe
  docs/paper-trades/{engine}/{date}.json    — per-engine actual entries

Outputs:
  Console summary (always)
  docs/reports/missed-trades-{date}.md       — markdown report

Usage:
  python3 scripts/missed-trades-report.py                # most recent trading day
  python3 scripts/missed-trades-report.py 2026-05-05      # specific date
  python3 scripts/missed-trades-report.py --no-fetch      # skip yfinance EOD lookup
"""
from __future__ import annotations
import json
import sys
from datetime import datetime, date as date_cls, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
ENGINES = ['v4', 'v5', 'v5_classic', 'v5_6', 'v5_7', 'v5_8', 'v6']
REPORTS_DIR = ROOT / 'docs' / 'reports'


def resolve_target(argv: list[str]) -> tuple[str, bool]:
    """Returns (date_string, fetch_eod_flag)."""
    fetch = '--no-fetch' not in argv
    args = [a for a in argv[1:] if not a.startswith('--')]
    if args:
        return args[0], fetch
    # No date arg — pick the most recent date with a dashboard-scores archive
    archives = sorted((ROOT / 'docs/dashboard-scores').glob('*.json'),
                      key=lambda p: p.stat().st_mtime, reverse=True)
    if archives:
        return archives[0].stem.split('_')[0], fetch
    return datetime.now().strftime('%Y-%m-%d'), fetch


def load_buy_list(target: str) -> tuple[set[str], dict, dict]:
    """Returns (buy_symbols_set, full_stocks_dict, archive_meta_dict)."""
    f = ROOT / f'docs/dashboard-scores/{target}.json'
    if not f.exists():
        return set(), {}, {}
    d = json.loads(f.read_text())
    buy_set = set(d.get('buy_list', []))
    stocks = d.get('stocks', {})
    meta = {k: d.get(k) for k in ('captured_at', 'scorer', 'total_scored',
                                  'buy_count', 'score_threshold_buy')}
    return buy_set, stocks, meta


def load_engine_entries(target: str) -> dict[str, set[str]]:
    """For each engine returns the set of symbols touched today (open or closed)."""
    entries = {e: set() for e in ENGINES}
    for v in ENGINES:
        f = ROOT / f'docs/paper-trades/{v}/{target}.json'
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        # v5 family — multi-pool shape
        for p in d.get('pools', {}).values():
            for pos in p.get('positions', []):
                if (s := pos.get('symbol')):
                    entries[v].add(s)
            for ct in p.get('closed', []):
                if (s := ct.get('symbol')):
                    entries[v].add(s)
        # v4 — flat shape
        for pos in d.get('positions', []):
            if (s := pos.get('symbol')):
                entries[v].add(s)
        for ct in d.get('closed_trades', []):
            if (s := ct.get('symbol')):
                entries[v].add(s)
    return entries


def fetch_eod_moves(symbols: list[str], target: str,
                    batch_size: int = 25) -> dict[str, float]:
    """Fetch open/close for each symbol on target date via yfinance.
    Returns {symbol: pct_move_from_open_to_close}.

    Uses 5-minute intraday bars as primary data source — Yahoo's daily EOD
    is unreliable for Indian stocks for 12+ hours after market close (NaN
    Close even with valid Open + Volume). Intraday is current within minutes.

    First 5m bar (~09:15 IST = 03:45 UTC) is the open, last bar (~15:25 IST
    = 09:55 UTC) is effectively the close. Same metric as a daily candle."""
    try:
        import yfinance as yf
    except ImportError:
        print('  [warn] yfinance not installed — skipping EOD fetch', file=sys.stderr)
        return {}
    if not symbols:
        return {}
    target_dt = datetime.strptime(target, '%Y-%m-%d').date()

    moves: dict[str, float] = {}
    total_batches = (len(symbols) + batch_size - 1) // batch_size

    for batch_idx, i in enumerate(range(0, len(symbols), batch_size)):
        chunk = symbols[i:i + batch_size]
        yf_syms = [s + '.NS' for s in chunk]
        try:
            df = yf.download(yf_syms, period='2d', interval='5m', progress=False,
                             auto_adjust=False, threads=False)
        except Exception as e:
            print(f'  [warn] batch {batch_idx + 1}/{total_batches} failed: {e}',
                  file=sys.stderr)
            continue
        if len(df) == 0:
            continue
        # Filter to bars whose date matches target (in UTC, but date roughly aligns)
        # Indian market 09:15-15:30 IST = 03:45-10:00 UTC, so target_dt UTC == target_dt IST
        target_bars = df[df.index.date == target_dt]
        if len(target_bars) == 0:
            continue
        if hasattr(df.columns, 'levels') and len(df.columns.levels) > 1:
            opens = target_bars['Open']
            closes = target_bars['Close']
            for s in chunk:
                ys = s + '.NS'
                if ys not in opens.columns:
                    continue
                op_series = opens[ys].dropna()
                cl_series = closes[ys].dropna()
                if len(op_series) == 0 or len(cl_series) == 0:
                    continue
                try:
                    o = float(op_series.iloc[0])
                    c = float(cl_series.iloc[-1])
                    if o > 0:
                        moves[s] = (c - o) / o * 100
                except (ValueError, TypeError):
                    continue
        elif len(chunk) == 1:
            op_series = target_bars['Open'].dropna()
            cl_series = target_bars['Close'].dropna()
            if len(op_series) and len(cl_series):
                try:
                    o = float(op_series.iloc[0])
                    c = float(cl_series.iloc[-1])
                    if o > 0:
                        moves[chunk[0]] = (c - o) / o * 100
                except (ValueError, TypeError):
                    pass
        print(f'  batch {batch_idx + 1}/{total_batches} ({len(chunk)} syms): '
              f'cumulative {len(moves)}/{len(symbols)}', file=sys.stderr)
    return moves


def build_report(target: str, buy_set: set[str], entries: dict[str, set[str]],
                 moves: dict[str, float], meta: dict) -> str:
    """Returns markdown report text."""
    lines: list[str] = []
    lines.append(f'# TradePilot Missed-Trades Report — {target}')
    lines.append('')
    lines.append(f'**Captured at**: {meta.get("captured_at", "?")} IST  ·  '
                 f'**Scorer**: `{meta.get("scorer", "?")}`')
    lines.append(f'**Total scored**: {meta.get("total_scored", "?")}  ·  '
                 f'**BUY count**: {meta.get("buy_count", len(buy_set))}  ·  '
                 f'**Threshold**: {meta.get("score_threshold_buy", "?")}')
    lines.append('')

    all_entered = set().union(*entries.values()) if entries else set()
    entered_buys = buy_set & all_entered
    missed = buy_set - all_entered

    lines.append('## Coverage Summary')
    lines.append('')
    lines.append('| Metric | Value |')
    lines.append('|:--|--:|')
    lines.append(f'| BUY signals at open | {len(buy_set)} |')
    lines.append(f'| Entered by at least one engine | {len(entered_buys)} |')
    lines.append(f'| Missed by ALL engines | {len(missed)} |')
    if buy_set:
        lines.append(f'| Coverage rate | {len(entered_buys) / len(buy_set) * 100:.0f}% |')
    lines.append('')

    lines.append('## Per-Engine Coverage')
    lines.append('')
    lines.append('| Engine | Entered (of BUY universe) | Missed |')
    lines.append('|:--|--:|--:|')
    for v in ENGINES:
        entered = entries.get(v, set()) & buy_set
        miss = buy_set - entries.get(v, set())
        lines.append(f'| {v} | {len(entered)} / {len(buy_set)} | {len(miss)} |')
    lines.append('')

    if not moves:
        lines.append('_No EOD price data available — skipping right-call/wrong-call analysis._')
        return '\n'.join(lines)

    scored = [(s, moves[s]) for s in missed if s in moves]
    scored.sort(key=lambda x: x[1], reverse=True)
    winners = [x for x in scored if x[1] > 0.5]   # >0.5% intraday counts
    losers = [x for x in scored if x[1] < -0.5]
    flat = [x for x in scored if -0.5 <= x[1] <= 0.5]

    lines.append('## What We Missed (EOD scored)')
    lines.append('')
    lines.append('| Outcome | Count | What it means |')
    lines.append('|:--|--:|:--|')
    lines.append(f'| Wrong call (stock UP >0.5%) | {len(winners)} | Money left on the table |')
    lines.append(f'| Right call (stock DOWN >0.5%) | {len(losers)} | Loss avoided |')
    lines.append(f'| Neutral (move within ±0.5%) | {len(flat)} | No material miss |')
    lines.append('')

    if winners:
        avg_w = sum(m for _, m in winners) / len(winners)
        lines.append(f'### Top 15 missed winners (avg +{avg_w:.2f}%)')
        lines.append('')
        lines.append('| Symbol | Day move |')
        lines.append('|:--|--:|')
        for s, m in winners[:15]:
            lines.append(f'| {s} | +{m:.2f}% |')
        lines.append('')

    if losers:
        avg_l = sum(m for _, m in losers) / len(losers)
        lines.append(f'### Top 15 correctly-skipped losers (avg {avg_l:.2f}%)')
        lines.append('')
        lines.append('| Symbol | Day move |')
        lines.append('|:--|--:|')
        for s, m in losers[-15:][::-1]:  # most negative first
            lines.append(f'| {s} | {m:.2f}% |')
        lines.append('')

    if scored:
        avg_all = sum(m for _, m in scored) / len(scored)
        lines.append('## Bottom Line')
        lines.append('')
        verdict = ('positive — we left money on the table'
                   if avg_all > 0.2 else
                   ('negative — we dodged a weak day' if avg_all < -0.2 else
                    'roughly neutral'))
        lines.append(f'Average move of {len(scored)} missed BUY-signal stocks: '
                     f'**{avg_all:+.2f}%** ({verdict}).')
        lines.append('')

    return '\n'.join(lines)


def main() -> int:
    target, fetch = resolve_target(sys.argv)
    print(f'TradePilot Missed-Trades Report — {target}')
    print('=' * 60)

    buy_set, _stocks, meta = load_buy_list(target)
    if not buy_set:
        print(f'ERROR: No dashboard-scores archive at '
              f'docs/dashboard-scores/{target}.json', file=sys.stderr)
        return 1

    entries = load_engine_entries(target)
    all_entered = set().union(*entries.values()) if entries else set()
    missed = buy_set - all_entered

    print(f'BUY signals at open : {len(buy_set)}')
    print(f'Entered by ≥1 engine : {len(buy_set & all_entered)}')
    print(f'Missed by all       : {len(missed)}')
    print()
    for v in ENGINES:
        e = entries.get(v, set()) & buy_set
        print(f'  {v:<12} entered {len(e):>3} of {len(buy_set)} BUYs')
    print()

    moves: dict[str, float] = {}
    if fetch and missed:
        print(f'Fetching EOD prices for {len(missed)} missed stocks...')
        moves = fetch_eod_moves(sorted(missed), target)
        print(f'  got {len(moves)} of {len(missed)}')
        print()

    md = build_report(target, buy_set, entries, moves, meta)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORTS_DIR / f'missed-trades-{target}.md'
    out.write_text(md)
    print(f'Report saved: {out}')

    # Console summary of right/wrong
    if moves:
        scored = [(s, moves[s]) for s in missed if s in moves]
        winners = sorted([x for x in scored if x[1] > 0.5], key=lambda x: -x[1])
        losers = sorted([x for x in scored if x[1] < -0.5], key=lambda x: x[1])
        print()
        print(f'Top 5 missed winners (we should have entered):')
        for s, m in winners[:5]:
            print(f'  {s:<14} +{m:.2f}%')
        print()
        print(f'Top 5 correctly skipped (would have lost money):')
        for s, m in losers[:5]:
            print(f'  {s:<14} {m:.2f}%')
        if scored:
            avg = sum(m for _, m in scored) / len(scored)
            print()
            print(f'Average move of missed set: {avg:+.2f}%')

    return 0


if __name__ == '__main__':
    sys.exit(main())
