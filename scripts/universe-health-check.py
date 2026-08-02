#!/usr/bin/env python3
"""
universe-health-check — catch dead/renamed tickers before they cost a session.

WHY: On 2026-08-02 `/api/scores` was hanging past 300s. The investigation found a
dead ticker (TATAMOTORS.NS, 0 bars after the Tata Motors demerger — TMPV.NS is the
live successor) sitting in the scan universe. The dead ticker turned out NOT to be
the cause of the hang, but it had been silently failing every fetch, on every scan,
for an unknown length of time, and nothing surfaced it.

A ticker does not announce that it has been renamed, merged or delisted. It just
returns zero rows forever, and the engines quietly score 199 stocks instead of 200.
This makes that failure loud.

Exit codes:
    0  all tickers healthy
    1  one or more dead/thin tickers found (details on stdout)

Run:
    python3 scripts/universe-health-check.py
    python3 scripts/universe-health-check.py --json
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import logging
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
logging.disable(logging.CRITICAL)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MIN_BARS = 3          # over a 5-day window, fewer than 3 sessions is suspicious


def check_india() -> dict:
    from prototype.v4.config import ACTIVE_SYMBOLS_YF
    import yfinance as yf
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        df = yf.download(ACTIVE_SYMBOLS_YF, period="5d", interval="1d",
                         progress=False, auto_adjust=False,
                         group_by="column", threads=True)
    close = df["Close"]
    dead, thin, ok = [], [], []
    for s in ACTIVE_SYMBOLS_YF:
        if s not in close.columns:
            dead.append(s); continue
        n = close[s].dropna().shape[0]
        (ok if n >= MIN_BARS else (thin if n > 0 else dead)).append(s)
    return {"market": "india", "total": len(ACTIVE_SYMBOLS_YF),
            "ok": len(ok), "dead": dead, "thin": thin}


def check_us() -> dict:
    from prototype.us.data_us import load_universe
    import yfinance as yf
    syms = load_universe("nasdaq100")
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
        df = yf.download(syms, period="5d", interval="1d", progress=False,
                         auto_adjust=False, group_by="column", threads=True)
    close = df["Close"]
    dead, thin, ok = [], [], []
    for s in syms:
        if s not in close.columns:
            dead.append(s); continue
        n = close[s].dropna().shape[0]
        (ok if n >= MIN_BARS else (thin if n > 0 else dead)).append(s)
    return {"market": "us", "total": len(syms),
            "ok": len(ok), "dead": dead, "thin": thin}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--market", choices=["india", "us", "all"], default="all")
    a = ap.parse_args()

    reports = []
    if a.market in ("india", "all"):
        try:
            reports.append(check_india())
        except Exception as e:
            reports.append({"market": "india", "error": f"{type(e).__name__}: {e}"})
    if a.market in ("us", "all"):
        try:
            reports.append(check_us())
        except Exception as e:
            reports.append({"market": "us", "error": f"{type(e).__name__}: {e}"})

    bad = False
    if a.json:
        print(json.dumps(reports, indent=2))
        bad = any(r.get("dead") or r.get("thin") or r.get("error") for r in reports)
    else:
        for r in reports:
            if r.get("error"):
                print(f"  {r['market']:<6} ERROR: {r['error']}")
                bad = True
                continue
            status = "OK" if not (r["dead"] or r["thin"]) else "PROBLEM"
            print(f"  {r['market']:<6} {r['ok']}/{r['total']} healthy   [{status}]")
            if r["dead"]:
                print(f"         DEAD ({len(r['dead'])}): {', '.join(r['dead'])}")
                bad = True
            if r["thin"]:
                print(f"         THIN ({len(r['thin'])}): {', '.join(r['thin'])}")
                bad = True
        if not bad:
            print("  all universes healthy")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
