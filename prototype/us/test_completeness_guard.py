#!/usr/bin/env python3
"""
Tests for the get_history() completeness gate (added 2026-08-03).

WHY SYNTHETIC DAMAGE
The incident that motivated the gate — 12,716 missing cells on a window that
returns 0 on every repeat — was never reproduced. A guard tested only against
data that happens to be clean proves nothing. So these tests take a REAL frame
and damage it in specific, known ways, then assert the gate reacts correctly.

_download is monkeypatched so the retry path is exercised deterministically
without hammering yfinance.

Run:  python3 prototype/us/test_completeness_guard.py
"""
from __future__ import annotations

import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from prototype.us import data_us as d  # noqa: E402

PASS, FAIL = [], []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{('  — ' + detail) if detail else ''}")


def fetch_clean():
    syms = d.load_universe("nasdaq100")[:8]
    df = d.get_history(syms, years=3, strict=False)
    assert df is not None and not df.empty, "could not fetch a baseline frame"
    return syms, df


def damage(df, symbol: str, rows: slice):
    """Blank Close for one symbol over a row range, returning a copy."""
    out = df.copy()
    if hasattr(out.columns, "levels") and out.columns.nlevels > 1:
        out.loc[out.index[rows], ("Close", symbol)] = float("nan")
    else:
        out.loc[out.index[rows], "Close"] = float("nan")
    return out


def main() -> int:
    syms, clean = fetch_clean()
    sym = syms[0]
    n = len(clean)
    print(f"\nbaseline: {len(syms)} symbols x {n} rows (real yfinance data)\n")

    # --- 1. audit_frame separates leading absence from interior holes ---------
    print("audit_frame — the leading-vs-interior distinction")
    a_clean = d.audit_frame(clean)
    check("clean frame reports zero interior gaps", a_clean["interior_gaps"] == 0,
          f"interior_gaps={a_clean['interior_gaps']}")

    lead = damage(clean, sym, slice(0, 100))          # first 100 rows blank
    a_lead = d.audit_frame(lead)
    check("leading NaNs are NOT counted as interior gaps",
          a_lead["symbols"][sym]["interior_gaps"] == 0,
          f"a stock listing mid-window is not a defect (coverage "
          f"{a_lead['symbols'][sym]['coverage_pct']:.0%})")

    hole = damage(clean, sym, slice(300, 400))        # 100 rows blank mid-series
    a_hole = d.audit_frame(hole)
    check("interior NaNs ARE counted",
          a_hole["symbols"][sym]["interior_gaps"] == 100,
          f"interior_gaps={a_hole['symbols'][sym]['interior_gaps']}")

    check("identical NaN counts, opposite verdicts",
          a_lead["symbols"][sym]["interior_gaps"] == 0
          and a_hole["symbols"][sym]["interior_gaps"] == 100,
          "100 blanks each — leading is fine, interior is not")

    # --- 2. clean data still passes -------------------------------------------
    print("\nget_history — clean data must not be harmed")
    d._download = lambda s, y, i: clean
    got = d.get_history(syms, years=3)
    check("clean frame passes the gate", got is not None and not got.empty)
    check("no symbols dropped from clean data",
          got is not None and d.close_block(got).shape[1] == len(syms),
          f"{d.close_block(got).shape[1]}/{len(syms)} kept")

    # --- 3. one bad symbol is dropped, the rest survive ------------------------
    print("\nget_history — one damaged symbol")
    d._download = lambda s, y, i: hole
    got = d.get_history(syms, years=3)
    kept = list(d.close_block(got).columns) if got is not None else []
    check("damaged symbol dropped", sym not in kept, f"{sym} excluded")
    check("undamaged symbols retained", len(kept) == len(syms) - 1,
          f"{len(kept)}/{len(syms)-1} survivors")
    check("no fabricated values in survivors",
          got is not None and int(d.close_block(got).isna().sum().sum()) == 0,
          "gaps are dropped, never filled")

    # --- 4. a frame-wide partial fetch is retried, then refused ---------------
    print("\nget_history — frame-wide partial fetch (the 12,716 scenario)")
    wrecked = clean.copy()
    for s in syms:                                    # blank 40% of every symbol
        wrecked = damage(wrecked, s, slice(200, 200 + int(n * 0.4)))
    a_wr = d.audit_frame(wrecked)
    check("wrecked frame exceeds the frame-wide threshold",
          a_wr["interior_pct"] > d.MAX_FRAME_INTERIOR_GAP_PCT,
          f"{a_wr['interior_pct']:.1%} > {d.MAX_FRAME_INTERIOR_GAP_PCT:.0%}")

    calls = {"n": 0}

    def flaky(s, y, i):
        calls["n"] += 1
        return wrecked if calls["n"] == 1 else clean   # transient, recovers on retry

    d._download = flaky
    got = d.get_history(syms, years=3)
    check("transient partial fetch is retried", calls["n"] == 2,
          f"_download called {calls['n']}x")
    check("retry result is returned", got is not None and not got.empty)

    calls["n"] = 0
    d._download = lambda s, y, i: wrecked              # persistently bad
    got = d.get_history(syms, years=3)
    check("persistent partial fetch returns None", got is None,
          "engine gets nothing rather than garbage")

    # --- 4b. TRUNCATION: short frame, zero holes, must still be refused ------
    # Found live on 2026-08-03: the UI showed "TRADING DAYS 2" with gaps 0 and
    # dropped 0. Every density check passes on a truncated frame because there is
    # nothing missing INSIDE the two days it returned.
    print("\nget_history — truncated fetch (extent, not density)")
    tiny = clean.iloc[-2:].copy()
    a_tiny = d.audit_frame(tiny)
    check("truncated frame has NO interior gaps (why density alone fails)",
          a_tiny["interior_gaps"] == 0,
          f"{a_tiny['trading_days']} days, {a_tiny['interior_gaps']} gaps — looks perfect")

    calls["n"] = 0
    d._download = lambda s, y, i: tiny
    got = d.get_history(syms, years=3)
    check("truncated frame is refused", got is None,
          "2 days for a 3y request is not data")

    calls["n"] = 0

    def flaky_trunc(s, y, i):
        calls["n"] += 1
        return tiny if calls["n"] == 1 else clean

    d._download = flaky_trunc
    got = d.get_history(syms, years=3)
    check("transient truncation is retried and recovers",
          got is not None and calls["n"] == 2, f"_download called {calls['n']}x")

    # --- 4c. CACHE: stable key + poison detection ---------------------------
    print("\nget_quotes — cache key stability and poison rejection")
    import subprocess
    keys = set()
    for _ in range(3):
        r = subprocess.run(
            [sys.executable, "-c",
             "import hashlib;print(hashlib.sha1(','.join(['AAPL','MSFT']).encode())"
             ".hexdigest()[:16])"],
            capture_output=True, text=True)
        keys.add(r.stdout.strip())
    check("cache key is identical across processes", len(keys) == 1,
          f"sha1 -> {keys.pop() if len(keys)==1 else keys} (hash() gave 3 different values)")

    import hashlib
    want = ["AAPL", "MSFT"]
    key = f"quotes_{hashlib.sha1(','.join(sorted(want)).encode()).hexdigest()[:16]}.json"
    d._write_cache(key, {"RELIANCE.NS": {"price": 1310.0, "prev_close": 1307.8,
                                         "change": 2.2, "change_pct": 0.17}})
    q = d.get_quotes(want)
    check("poisoned cache entry is rejected",
          not any(str(k).endswith(".NS") for k in q),
          f"returned {sorted(q)[:4]} — India data discarded, not served")

    # --- 5. strict=False bypasses, for diagnostics only ----------------------
    print("\nget_history — strict=False escape hatch")
    got = d.get_history(syms, years=3, strict=False)
    check("strict=False returns unaudited data", got is not None and not got.empty)

    print(f"\n{'-'*54}\n  {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for f in FAIL:
            print(f"    FAILED: {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
