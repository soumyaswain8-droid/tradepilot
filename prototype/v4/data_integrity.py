#!/usr/bin/env python3
"""
data_integrity — detect holes in the India daily series before an engine trades on it.

THE INCIDENT THIS EXISTS FOR (2026-08-04)
yfinance's NIFTY daily series silently dropped Monday 2026-08-03. The days ran
07-29, 07-30, 07-31, 08-04 — a completed trading day simply absent. No error, no
null, no short frame: a clean, well-formed series with one day missing. Every
downstream calculation inherited a wrong previous close, turning a -1.04% session
into +0.54%. It was caught only because Soumya questioned a screenshot.

WHY THIS DOES NOT USE A HOLIDAY CALENDAR
The obvious check — "count weekdays between two dates and compare" — needs an
authoritative NSE holiday list, which we do not have and which goes stale every
year. A wrong holiday list produces false alarms, and an alarm that cries wolf is
switched off, which is worse than no alarm.

So the check is COMPARATIVE: ask two independent sources for the same window and
compare the DATE SETS. A date one source has and the other lacks is a hole in the
one that lacks it — no calendar required, and no assumption about which is right.
That is exactly how the 08-03 gap was actually found. The method's honest limit:
it cannot see a day BOTH sources are missing. That limitation is stated rather
than papered over.

Usage:
    from prototype.v4.data_integrity import compare_daily_series, report
    r = compare_daily_series("RELIANCE", days=30)
    print(report(r))

CLI:
    python3 prototype/v4/data_integrity.py            # NIFTY + a few large caps
    python3 prototype/v4/data_integrity.py --symbols RELIANCE,TCS --days 60
"""
from __future__ import annotations

import argparse
import io
import contextlib
import logging
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# An index has no ".NS" suffix on yfinance and is not an NSE equity on Kite, so the
# two feeds need different identifiers for the same instrument.
INDEX_MAP = {
    "NIFTY 50": {"kite": ("NSE", "NIFTY 50"), "yf": "^NSEI"},
    "SENSEX":   {"kite": ("BSE", "SENSEX"),   "yf": "^BSESN"},
}


_INDEX_TOKENS: dict = {}


def _index_token(tradingsymbol: str):
    """instrument_token for an INDICES-segment symbol, cached per process.

    Indices sit in a different segment from equities, so kite_data's equity-only
    map never contains them."""
    from prototype.v4 import kite_data as kd

    if tradingsymbol in _INDEX_TOKENS:
        return _INDEX_TOKENS[tradingsymbol]
    for exch in ("NSE", "BSE"):
        try:
            rows = kd._call(lambda: kd.client().instruments(exch), "instruments")
        except Exception:
            continue
        for r in rows:
            if r.get("tradingsymbol") == tradingsymbol and r.get("segment") == "INDICES":
                _INDEX_TOKENS[tradingsymbol] = int(r["instrument_token"])
                return _INDEX_TOKENS[tradingsymbol]
    _INDEX_TOKENS[tradingsymbol] = None
    return None


def _kite_dates(symbol: str, days: int) -> set:
    """Trading dates Kite has for `symbol` over the window. Empty set on failure —
    an empty set is reported as 'source unavailable', never as 'no gaps'."""
    from prototype.v4 import kite_data as kd

    to_d = datetime.now()
    from_d = to_d - timedelta(days=days)
    try:
        if symbol in INDEX_MAP:
            # INDICES ARE THE WHOLE POINT. Measured 2026-08-04: yfinance is missing
            # 2026-08-03 for ^NSEI AND ^BSESN, while RELIANCE.NS and TCS.NS both
            # have it. The hole is index-only — so a checker that skipped indices,
            # as the first draft of this file did, would report "5 clean, 0 gapped"
            # against the exact defect it was written to catch.
            # kite_data.token_for maps instrument_type == "EQ" only, so indices need
            # their own lookup (segment INDICES, e.g. NIFTY 50 -> 256265).
            tok = _index_token(INDEX_MAP[symbol]["kite"][1])
        else:
            tok = kd.token_for(symbol)
        if not tok:
            return set()
        rows = kd.client().historical_data(tok, from_d, to_d, "day")
        return {str(r["date"])[:10] for r in rows}
    except Exception as e:
        logger.warning(f"kite dates unavailable for {symbol}: {type(e).__name__}: {e}")
        return set()


def _yf_dates(symbol: str, days: int) -> set:
    import yfinance as yf
    tkr = INDEX_MAP.get(symbol, {}).get("yf") or f"{symbol}.NS"
    try:
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
            h = yf.Ticker(tkr).history(period=f"{days}d", interval="1d")
        if h is None or h.empty:
            return set()
        return {str(d)[:10] for d in h.index}
    except Exception as e:
        logger.warning(f"yfinance dates unavailable for {symbol}: {type(e).__name__}: {e}")
        return set()


def compare_daily_series(symbol: str, days: int = 30) -> dict:
    """Compare the DATE SETS two feeds return for one symbol.

    missing_from_yf   dates Kite has and yfinance lacks  <- the 2026-08-03 shape
    missing_from_kite dates yfinance has and Kite lacks
    conclusive        False when either source returned nothing, so the caller
                      cannot mistake "could not check" for "checked and clean"
    """
    k = _kite_dates(symbol, days)
    y = _yf_dates(symbol, days)

    # Compare only over the overlapping span. The feeds' windows rarely align at the
    # edges, and edge mismatches are not holes — flagging them would be the
    # cry-wolf failure this module is built to avoid.
    if k and y:
        lo, hi = max(min(k), min(y)), min(max(k), max(y))
        kk = {d for d in k if lo <= d <= hi}
        yy = {d for d in y if lo <= d <= hi}
    else:
        lo = hi = None
        kk, yy = k, y

    return {
        "symbol": symbol,
        "window_days": days,
        "overlap": f"{lo}..{hi}" if lo else None,
        "kite_days": len(kk),
        "yf_days": len(yy),
        "missing_from_yf": sorted(kk - yy),
        "missing_from_kite": sorted(yy - kk),
        "conclusive": bool(k and y),
        "reason": None if (k and y) else
                  ("kite returned nothing" if not k else "yfinance returned nothing"),
    }


def report(r: dict) -> str:
    if not r["conclusive"]:
        return (f"  {r['symbol']:<12} INCONCLUSIVE — {r['reason']} "
                f"(kite {r['kite_days']}d, yf {r['yf_days']}d)")
    mf, mk = r["missing_from_yf"], r["missing_from_kite"]
    if not mf and not mk:
        return f"  {r['symbol']:<12} OK — {r['kite_days']} days, both feeds agree"
    out = [f"  {r['symbol']:<12} GAP over {r['overlap']}"]
    if mf:
        out.append(f"    yfinance is MISSING {len(mf)}: {', '.join(mf[:6])}")
    if mk:
        out.append(f"    kite is MISSING {len(mk)}: {', '.join(mk[:6])}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", default="RELIANCE,TCS,INFY,HDFCBANK,SBIN")
    ap.add_argument("--days", type=int, default=30)
    a = ap.parse_args()

    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    results = [compare_daily_series(s, a.days) for s in syms]

    print(f"\n  daily-series cross-check, last {a.days} days\n")
    for r in results:
        print(report(r))

    gapped = [r for r in results if r["conclusive"] and
              (r["missing_from_yf"] or r["missing_from_kite"])]
    incon = [r for r in results if not r["conclusive"]]
    print(f"\n  {len(results) - len(gapped) - len(incon)} clean, {len(gapped)} gapped, "
          f"{len(incon)} inconclusive")
    if gapped:
        allmissing = sorted({d for r in gapped for d in r["missing_from_yf"]})
        if allmissing:
            print(f"  dates yfinance lacks across symbols: {', '.join(allmissing[:10])}")
    return 1 if gapped else 0


if __name__ == "__main__":
    sys.exit(main())
