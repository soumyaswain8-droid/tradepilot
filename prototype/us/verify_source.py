#!/usr/bin/env python3
"""
verify_source — cross-check the US data feed against an independent second source.

WHY THIS EXISTS
On 2026-08-03 the US tab confidently displayed 30 Indian NSE tickers priced in "$",
and the coverage panel read "TRADING DAYS 2" with every quality check green. Neither
was an outage. Both were SILENT CORRUPTION, and a single data source cannot detect
its own corruption — it has nothing to disagree with. The guards in data_us.py check
a frame's internal consistency; this checks it against the outside world.

WHAT IT CATCHES (each maps to a bug that actually shipped)
  identity  symbols returned are not the symbols requested   -> the .NS contamination
  extent    our history is far shorter than the reference    -> the 2-day frame
  values    closes disagree beyond tolerance                 -> silent price corruption

WHY FMP AND NOT A "BETTER" FEED
Not because it is better than yfinance — it may not be. Because it is DIFFERENT.
The value is disagreement, not pedigree. Verified 2026-08-03: FMP and yfinance agree
to the cent on AAPL/MSFT/NVDA/TSLA/AMZN closes, so a divergence is a real signal
rather than a known offset. Closing prices are a matter of record; sources agreeing
on them is the null hypothesis.

CALL BUDGET
FMP's free plan allows 250 calls/day and does NOT support multiple symbols per call
(the comma list is a premium parameter — tested, not assumed). So each symbol costs
one call. Usage is tracked on disk and the run REFUSES to exceed the cap rather than
burning the day's quota.

COVERAGE — READ THIS BEFORE TRUSTING A PASS
The free plan also restricts the SYMBOL UNIVERSE, which no plan comparison mentions.
Probed all 87 tickers on 2026-08-03: 17 are available (20%), 70 return HTTP 402.
The 17 are mega-caps — AAPL, MSFT, NVDA, AMZN, GOOGL, META, TSLA, COST, NFLX, AMD,
PEP, ADBE and a few more. So this is a CANARY, not an audit:
  detected     systemic faults — contamination, truncation, a poisoned cache — which
               hit every symbol at once and therefore show up in the mega-cap subset.
               Both bugs found on 2026-08-03 were of exactly this kind.
  NOT detected corruption confined to the other 70 tickers.
A PASS here means "no systemic fault visible in 20% of the universe", not "the data
is good". The 402 set is cached in fmp_unsupported.json so the daily run never spends
calls rediscovering it.

Run:
    python3 prototype/us/verify_source.py                 # sample of 20
    python3 prototype/us/verify_source.py --sample 40
    python3 prototype/us/verify_source.py --symbols AAPL,MSFT
    python3 prototype/us/verify_source.py --json          # machine-readable
"""
from __future__ import annotations

import argparse
import io
import json
import contextlib
import logging
import os
import sys
import time
import urllib.error
import urllib.request
import warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

BUDGET_FILE = ROOT / "prototype" / "data" / "us_cache" / "fmp_calls.json"
DAILY_CAP = 200                 # of FMP's 250 — leaves 50 for ad-hoc/manual use
TOLERANCE_PCT = 0.50            # closes differing by more than this are flagged
MIN_EXTENT_RATIO = 0.80         # our history vs the reference's
REQUEST_SPACING_S = 0.30        # be a polite client on a free tier
MIN_CHECKED_RATIO = 0.50        # below this, the run is INCONCLUSIVE, never "pass"

# FMP's free plan restricts the SYMBOL UNIVERSE, not only the endpoints: mega-caps
# answer fine while others return HTTP 402 Payment Required. Discovered by running
# it — the plan comparison never mentions this. A 402 is permanent for that symbol
# on this plan, so it is remembered; re-probing it every day would burn the daily
# quota discovering the same "no" over and over.
UNSUPPORTED_FILE = ROOT / "prototype" / "data" / "us_cache" / "fmp_unsupported.json"


# ------------------------------------------------------------------ budget

def _budget() -> dict:
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        d = json.loads(BUDGET_FILE.read_text())
        if d.get("date") == today:
            return d
    except Exception:
        pass
    return {"date": today, "calls": 0}


def _spend(n: int) -> None:
    d = _budget()
    d["calls"] = d.get("calls", 0) + n
    BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    BUDGET_FILE.write_text(json.dumps(d))


def calls_remaining() -> int:
    return max(0, DAILY_CAP - _budget().get("calls", 0))


# ------------------------------------------------------------------ source

def api_key() -> str | None:
    k = os.environ.get("FMP_API_KEY")
    if k:
        return k.strip()
    env = ROOT / ".env"
    if env.exists():
        for ln in env.read_text().splitlines():
            if ln.startswith("FMP_API_KEY="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def load_unsupported() -> set:
    try:
        return set(json.loads(UNSUPPORTED_FILE.read_text()))
    except Exception:
        return set()


def mark_unsupported(symbol: str) -> None:
    s = load_unsupported()
    s.add(symbol)
    UNSUPPORTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    UNSUPPORTED_FILE.write_text(json.dumps(sorted(s)))


def fmp_history(symbol: str, key: str) -> dict:
    """{date: close} for one symbol. One API call. Returns {} on any failure —
    a verifier that crashes the caller is worse than one that reports nothing."""
    url = ("https://financialmodelingprep.com/stable/historical-price-eod/light"
           f"?symbol={symbol}&apikey={key}")
    try:
        with urllib.request.urlopen(url, timeout=45) as r:
            rows = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 402:      # not on this plan — permanent, remember it
            mark_unsupported(symbol)
            logger.info(f"fmp: {symbol} not available on the free plan (402)")
        else:
            logger.warning(f"fmp fetch failed for {symbol}: HTTP {e.code}")
        return {}
    except Exception as e:
        logger.warning(f"fmp fetch failed for {symbol}: {type(e).__name__}: {e}")
        return {}
    if not isinstance(rows, list):
        logger.warning(f"fmp returned non-list for {symbol}: {str(rows)[:120]}")
        return {}
    out = {}
    for r in rows:
        try:
            out[str(r["date"])[:10]] = float(r["price"])
        except (KeyError, TypeError, ValueError):
            continue
    return out


# ------------------------------------------------------------------ compare

def verify(symbols: list, key: str, years: int = 3) -> dict:
    from prototype.us.data_us import get_history

    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        df = get_history(symbols, years=years)
    if df is None:
        return {"ok": False, "error": "local get_history returned None (failed its own gate)"}

    from prototype.us.data_us import close_block
    close = close_block(df)
    ours = set(str(c).upper() for c in close.columns)

    # IDENTITY — the .NS bug. Checked before any price comparison, because
    # comparing prices of the wrong instrument produces confident nonsense.
    asked = set(s.upper() for s in symbols)
    stray = sorted(ours - asked)

    checked, diffs, missing, extent = [], [], [], []
    unsupported = load_unsupported()
    for sym in sorted(ours & asked):
        if sym in unsupported:
            continue                      # known 402 — do not spend a call on it
        if calls_remaining() <= 0:
            logger.warning("FMP daily budget exhausted — stopping early")
            break
        ref = fmp_history(sym, key)
        _spend(1)
        time.sleep(REQUEST_SPACING_S)
        if not ref:
            missing.append(sym)
            continue
        checked.append(sym)

        col = close[sym].dropna()
        # EXTENT — the 2-day-frame bug. Two traps here, both hit while building this:
        #   1. Comparing our 3y bar count against FMP's full ~5y default flags clean
        #      data at 60%. NVDA and TSLA were both false-positived that way.
        #   2. Fixing (1) by scoping the window to OUR data's own min/max makes the
        #      check CIRCULAR — truncated data redefines the yardstick and scores
        #      100%. A 40-bar frame passed cleanly under that version.
        # The window must come from the REQUEST, which neither source controls:
        # `years` back from the reference's most recent date.
        ref_hi = max(ref)
        ref_lo = f"{int(ref_hi[:4]) - years}{ref_hi[4:]}"
        ref_win = {d: p for d, p in ref.items() if ref_lo <= d <= ref_hi}
        ours_win = [d for d in col.index if ref_lo <= str(d)[:10] <= ref_hi]
        if len(ref_win) > 30:
            ratio = len(ours_win) / len(ref_win)
            if ratio < MIN_EXTENT_RATIO:
                extent.append({"symbol": sym, "ours": len(ours_win),
                               "reference": len(ref_win),
                               "window": f"{ref_lo}..{ref_hi}",
                               "ratio": round(ratio, 3)})

        # VALUES — compare only on dates BOTH sources have.
        worst = None
        for d in list(col.index)[-60:]:
            ds = str(d)[:10]
            if ds not in ref:
                continue
            a, b = float(col.loc[d]), ref[ds]
            if b == 0:
                continue
            pct = abs(a - b) / b * 100
            if worst is None or pct > worst["pct"]:
                worst = {"date": ds, "ours": round(a, 2), "reference": round(b, 2),
                         "pct": round(pct, 4)}
        if worst and worst["pct"] > TOLERANCE_PCT:
            diffs.append({"symbol": sym, **worst})

    # A verifier that reports PASS having verified nothing is worse than no
    # verifier — it converts "unknown" into "fine". The first live run of this
    # file did exactly that: every symbol 402'd, zero comparisons ran, and it
    # printed "PASS — sources agree". `ok` therefore requires evidence, not just
    # an absence of complaints.
    problems = bool(stray or diffs or extent)
    conclusive = len(checked) >= max(1, int(len(symbols) * MIN_CHECKED_RATIO))
    return {
        "ok": conclusive and not problems,
        "conclusive": conclusive,
        "verdict": ("pass" if (conclusive and not problems)
                    else "fail" if problems else "inconclusive"),
        "checked": len(checked),
        "requested": len(symbols),
        "stray_symbols": stray,          # returned but never requested
        "value_divergence": diffs,
        "extent_shortfall": extent,
        "no_reference_data": missing,    # informational, not a failure
        "calls_remaining": calls_remaining(),
        "tolerance_pct": TOLERANCE_PCT,
        "checked_at": datetime.now().isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--symbols", default="")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    key = api_key()
    if not key:
        print("  FMP_API_KEY not found in environment or .env", file=sys.stderr)
        return 2

    from prototype.us.data_us import load_universe
    if a.symbols:
        syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    else:
        uni = [s for s in load_universe("nasdaq100") if s not in load_unsupported()]
        if not uni:
            print("  every universe symbol is unsupported on this plan — cannot verify",
                  file=sys.stderr)
            return 2
        # Rotate the sample by day so coverage accumulates across the week rather
        # than re-checking the same alphabetical head every morning.
        off = (datetime.now().timetuple().tm_yday * a.sample) % len(uni)
        syms = (uni + uni)[off:off + a.sample]

    if calls_remaining() < len(syms):
        print(f"  budget: {calls_remaining()} calls left today, {len(syms)} requested — "
              f"trimming", file=sys.stderr)
        syms = syms[:calls_remaining()]
    if not syms:
        print("  no FMP call budget left today", file=sys.stderr)
        return 0

    res = verify(syms, key)
    if a.json:
        print(json.dumps(res, indent=2))
        return 0 if res.get("ok") else 1

    if not res.get("ok") and "error" in res:
        print(f"  FAIL  {res['error']}")
        return 1
    print(f"\n  cross-check vs FMP — {res['checked']} symbols, "
          f"{res['calls_remaining']} calls left today")
    if res["stray_symbols"]:
        print(f"  CONTAMINATION  data contains symbols never requested: "
              f"{', '.join(res['stray_symbols'][:10])}")
    for e in res["extent_shortfall"]:
        print(f"  SHORT HISTORY  {e['symbol']}: {e['ours']} bars vs {e['reference']} "
              f"at the reference over {e.get('window','same window')} ({e['ratio']:.0%})")
    for d in res["value_divergence"]:
        print(f"  PRICE DIVERGE  {d['symbol']} {d['date']}: ours {d['ours']} vs "
              f"reference {d['reference']} ({d['pct']:.2f}%)")
    if res["no_reference_data"]:
        print(f"  (no reference data for {len(res['no_reference_data'])}: "
              f"{', '.join(res['no_reference_data'][:6])})")
    verdict = {
        "pass": f"PASS — {res['checked']}/{res['requested']} symbols agree",
        "fail": "PROBLEMS FOUND (above)",
        "inconclusive": (f"INCONCLUSIVE — only {res['checked']}/{res['requested']} "
                         f"symbols could be compared; this is NOT a pass"),
    }[res["verdict"]]
    print(f"  {verdict}\n")
    return 0 if res["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
