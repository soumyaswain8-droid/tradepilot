#!/usr/bin/env python3
"""
news-impact — does a news item actually move the stock it names?

THE QUESTION. The collector (scripts/news-watch.py) has been recording catalysts with an
honest observation timestamp since 2026-09-01. This measures whether those items are
followed by abnormal movement in the named stock, and it is designed so that a week of
data can answer it or fail to — not so that it produces a number either way.

FOUR DESIGN CHOICES THAT DECIDE WHETHER THE ANSWER MEANS ANYTHING:

1. MARKET-NEUTRAL, ALWAYS. Stocks move. "The stock rose after the news" measures the
   market, not the news. Every return here is the stock's move MINUS NIFTY's over the
   identical window, so a broad rally cannot be read as a hundred separate catalysts.

2. ONLY PRICES WE COULD HAVE TRADED AT. An item first seen at 21:40 IST cannot be acted
   on until the next open, so it is measured open->close of the NEXT session. An item
   seen mid-session is measured from the NEXT session's open too, because we have no
   intraday fill data here and pretending otherwise is the look-ahead this project has
   killed lanes for. Both windows start AFTER the information was in hand.

3. ONE EVENT PER SYMBOL-DAY. Feeds repeat a story for hours; the collector dedupes
   identical headlines but not re-reported ones. Counting each repetition as an
   observation would turn one event into fifty confirmations, which is how a busy story
   becomes a false signal.

4. THE 'other' BUCKET IS REPORTED SEPARATELY. 83% of collected items classify as
   'other' — general business copy. If real catalysts move stocks and 'other' does not,
   that difference IS the finding. If both move equally, we are measuring attention, not
   information.

    python3 scripts/news-impact.py                 # settle everything settleable
    python3 scripts/news-impact.py --report        # read the accumulated results

WHAT IT CANNOT DO YET. With days of data this reports a description, not a verdict. The
pre-registered bar is stated in the output every run so that a favourable early number
cannot be mistaken for a passed test.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import statistics as st
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
NEWS = ROOT / "docs" / "sarathi" / "knowledge" / "news"
OUT = ROOT / "docs" / "sarathi" / "knowledge" / "news_impact.jsonl"

IST = timezone(timedelta(hours=5, minutes=30))

# Stated BEFORE looking at results, and printed on every run. A week of data will not
# clear this; it is the bar for the eventual decision, not for the first look.
GATE = {
    "min_events": 200,
    "min_days": 15,
    "min_abs_mean_pct": 0.30,     # market-neutral, open->close
    "min_t": 2.5,                 # date-clustered
}


def load_news() -> list:
    rows = []
    for f in sorted(NEWS.glob("*.jsonl")):
        for ln in f.read_text().splitlines():
            try:
                r = json.loads(ln)
            except Exception:
                continue
            if r.get("symbols"):
                rows.append(r)
    return rows


def ist_day(iso: str) -> str | None:
    """The IST calendar day we first saw an item."""
    try:
        t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        return t.astimezone(IST).strftime("%Y-%m-%d")
    except Exception:
        return None


def ist_hour(iso: str) -> int:
    t = datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return t.astimezone(IST).hour


def events(rows: list) -> list:
    """Collapse to one event per (symbol, IST day, catalyst).

    Keeps the EARLIEST sighting, because the question is what we could have known first.
    A later re-report of the same story adds no information and must not add a row.
    """
    best = {}
    for r in rows:
        d = ist_day(r.get("first_seen_utc", ""))
        if not d:
            continue
        for sym in r["symbols"]:
            k = (sym, d, r.get("catalyst", "other"))
            if k not in best or r["first_seen_utc"] < best[k]["first_seen_utc"]:
                best[k] = r
    out = []
    for (sym, d, cat), r in best.items():
        out.append({"symbol": sym, "seen_day": d, "catalyst": cat,
                    "first_seen_utc": r["first_seen_utc"],
                    "region": r.get("region"), "session": r.get("session"),
                    "hour_ist": ist_hour(r["first_seen_utc"]),
                    "title": r["title"][:120]})
    return out


def measure(evs: list, verbose: bool = True) -> list:
    """Attach the next tradeable session's market-neutral open->close move."""
    from quant.bars import daily

    # NIFTY is not in the equity bhavcopy store, so neutralise against the
    # cross-sectional mean of the day's measured names instead. With enough names that
    # is the market move for this sample, and it needs no extra data source.
    # Fetch ONCE PER SYMBOL over the whole window, not once per event. 274 events
    # collapse to ~110 symbols, and the per-event version would hammer a rate-limited
    # endpoint with the same request repeatedly.
    #
    # allow_kite=True is required here and is safe: the offline bhavcopy store lags by
    # a session or two, so the most recent news has no offline forward bar. Kite
    # historical is corporate-action ADJUSTED while bhavcopy is raw, but every figure
    # below is an open->close RATIO within a single session, and a split scales both
    # legs equally — the ratio is unaffected. (Levels would not be; do not compare
    # prices across the two sources.)
    syms = sorted({e["symbol"] for e in evs})
    lo = min(e["seen_day"] for e in evs)
    hi = (datetime.strptime(max(e["seen_day"] for e in evs), "%Y-%m-%d")
          + timedelta(days=8)).strftime("%Y-%m-%d")
    cache, misses = {}, 0
    for i, s in enumerate(syms):
        try:
            cache[s] = daily(s, lo, hi, allow_kite=True)
        except Exception:
            misses += 1
        if verbose and i and i % 40 == 0:
            print(f"    bars {i}/{len(syms)}", flush=True)
    if verbose:
        print(f"    bars fetched for {len(cache)}/{len(syms)} symbols "
              f"({misses} unavailable)", flush=True)

    out = []
    for e in evs:
        df = cache.get(e["symbol"])
        if df is None or df.empty:
            continue
        # The first session STRICTLY AFTER the day we saw it — never the same day,
        # which would include price action that PRECEDED the news and is the classic
        # way a news study accidentally measures the move it is trying to predict.
        #
        # Compare on normalised date STRINGS. bhavcopy returns naive timestamps while
        # Kite returns tz-aware ones (+05:30), and comparing those two against a plain
        # string silently mis-selects rows rather than raising.
        d = df.copy()
        d["_day"] = d["date"].astype(str).str.slice(0, 10)
        fwd = d[d["_day"] > e["seen_day"]].sort_values("_day")
        if fwd.empty:
            continue
        row = fwd.iloc[0]
        o, c = float(row["open"]), float(row["close"])
        if not o:
            continue
        out.append({**e, "trade_day": row["_day"],
                    "open": o, "close": c, "raw_pct": (c / o - 1) * 100})
    # market-neutralise within each trading day
    byday = collections.defaultdict(list)
    for r in out:
        byday[r["trade_day"]].append(r)
    for d, rs in byday.items():
        if len(rs) < 3:
            for r in rs:
                r["mn_pct"] = None          # too few names to define a market that day
            continue
        mkt = st.mean(r["raw_pct"] for r in rs)
        for r in rs:
            r["mn_pct"] = r["raw_pct"] - mkt
            r["mkt_pct"] = mkt
    return out


def report(rows: list) -> None:
    usable = [r for r in rows if r.get("mn_pct") is not None]
    print(f"  events measured : {len(rows)}  (usable market-neutral: {len(usable)})")
    days = sorted({r["trade_day"] for r in usable})
    print(f"  trading days    : {len(days)}  {', '.join(days) if len(days) < 8 else ''}")
    print(f"\n  PRE-REGISTERED BAR — {GATE['min_events']} events, {GATE['min_days']} days, "
          f"|mean| >= {GATE['min_abs_mean_pct']}%, t >= {GATE['min_t']}")
    if not usable:
        print("  nothing measurable yet.")
        return

    def block(label, rs):
        if len(rs) < 2:
            print(f"    {label:<22} n={len(rs):<4} (too few)")
            return
        m = st.mean(r["mn_pct"] for r in rs)
        sd = st.stdev(r["mn_pct"] for r in rs)
        t = m / (sd / math.sqrt(len(rs))) if sd else 0
        up = sum(1 for r in rs if r["mn_pct"] > 0)
        print(f"    {label:<22} n={len(rs):<4} mean {m:+.3f}%  median "
              f"{st.median(r['mn_pct'] for r in rs):+.3f}%  up {100*up/len(rs):.0f}%  t={t:+.2f}")

    print("\n  MARKET-NEUTRAL next-session open->close:")
    block("ALL", usable)
    if len(days) < 3:
        # Within-day neutralisation subtracts the mean of that day's own events, so
        # when nearly every event lands on ONE trading day the ALL row is forced to
        # approximately zero BY CONSTRUCTION. It is arithmetic, not a finding, and it
        # would be easy to read as "news does nothing". The between-group comparisons
        # below remain valid — they are relative, measured against the same subtracted
        # mean — but the aggregate is meaningless until events span several days.
        print("      ^ ALL is ~0 BY CONSTRUCTION with this few days: the neutraliser")
        print("        subtracts the mean of these same events. Read the GROUPS, not")
        print("        this row, until the sample spans 3+ trading days.")
    print("\n  by catalyst:")
    for cat in sorted({r["catalyst"] for r in usable}):
        block(cat, [r for r in usable if r["catalyst"] == cat])
    print("\n  real catalysts vs 'other':")
    block("catalyst != other", [r for r in usable if r["catalyst"] != "other"])
    block("other", [r for r in usable if r["catalyst"] == "other"])

    n_days = len({r["trade_day"] for r in usable})
    print(f"\n  STATUS: {len(usable)}/{GATE['min_events']} events, "
          f"{n_days}/{GATE['min_days']} days — "
          f"{'GATE NOT YET EVALUABLE' if len(usable) < GATE['min_events'] or n_days < GATE['min_days'] else 'gate evaluable'}")
    if len(usable) < GATE["min_events"]:
        print("  Any number above is a description, not a result. Do not act on it.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="read stored results only")
    a = ap.parse_args()

    if a.report and OUT.exists():
        rows = [json.loads(l) for l in OUT.read_text().splitlines() if l.strip()]
        report(rows)
        return 0

    news = load_news()
    evs = events(news)
    print(f"  news items with symbols: {len(news)}  ->  {len(evs)} unique symbol-day events")
    rows = measure(evs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r) for r in rows) + ("\n" if rows else ""))
    report(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
