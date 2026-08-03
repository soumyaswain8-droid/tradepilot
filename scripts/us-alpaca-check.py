#!/usr/bin/env python3
"""
us-alpaca-check — verify Alpaca paper credentials before trusting them.

Run:  python3 scripts/us-alpaca-check.py

Checks, in order, and stops at the first real problem:
  1. keys present in .env or environment
  2. keys authenticate against the PAPER host
  3. account is active and is genuinely a paper account
  4. alpaca-py SDK importable (needed by broker.py)
  5. our AlpacaBroker reports itself configured

WHY THIS EXISTS: the status codes are easy to misread, and the widely-circulated
advice about them is STALE. Verified live against paper-api.alpaca.markets on
2026-08-03 from this machine:

    no auth headers   -> 401 {"message": "unauthorized."}
    wrong keys        -> 401 {"message": "unauthorized."}
    (a 2023-era example returned 403 for the no-auth case — that behaviour changed)

So on the current API a 401 means "credentials missing or wrong", and a **403 does
NOT mean missing credentials**. If you send valid-looking keys and get 403, the
request was refused for some other reason, and a region/IP restriction is the main
suspect — Alpaca's own docs contradict themselves on India RESIDENCY (their worked
example is an Indian *citizen* residing in the UK). That is a live-eligibility
question, not a key problem. See docs/research/us-market/01-brokers-and-apis.md

NOTE: uses the PAPER host only. It never touches api.alpaca.markets (live).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER_HOST = "https://paper-api.alpaca.markets"


def load_keys() -> tuple:
    key = os.environ.get("ALPACA_API_KEY")
    sec = os.environ.get("ALPACA_SECRET_KEY")
    env = ROOT / ".env"
    if (not key or not sec) and env.exists():
        for ln in env.read_text().splitlines():
            ln = ln.strip()
            if ln.startswith("ALPACA_API_KEY=") and not key:
                key = ln.split("=", 1)[1].strip().strip('"').strip("'")
            elif ln.startswith("ALPACA_SECRET_KEY=") and not sec:
                sec = ln.split("=", 1)[1].strip().strip('"').strip("'")
    return key, sec


def call(path: str, key: str, sec: str):
    req = urllib.request.Request(
        f"{PAPER_HOST}{path}",
        headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec,
                 "accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:200]
        return e.code, body
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main() -> int:
    print("Alpaca PAPER credential check")
    print("=" * 52)

    key, sec = load_keys()
    if not key or not sec:
        missing = [n for n, v in (("ALPACA_API_KEY", key), ("ALPACA_SECRET_KEY", sec)) if not v]
        print(f"  [1] keys           MISSING: {', '.join(missing)}")
        print()
        print("  Add to .env (paper keys — signup needs no funding and no KYC):")
        print("      ALPACA_API_KEY=PK...")
        print("      ALPACA_SECRET_KEY=...")
        print("  Generate them at app.alpaca.markets -> Paper Trading -> API Keys.")
        print("  Pick the TRADING API product, not Broker API.")
        return 1
    print(f"  [1] keys           found (id starts {key[:4]}..., secret {len(sec)} chars)")

    status, body = call("/v2/account", key, sec)
    # 401 vs 403 mean DIFFERENT things, and Alpaca changed this. Verified live on
    # 2026-08-03: an unauthenticated request returns 401 {"message":"unauthorized."}.
    # A 2023-era example returned 403 for the same request, so older docs and forum
    # posts describing "403 = missing credentials" are stale.
    if status == 401:
        print("  [2] auth           401 UNAUTHORIZED — keys rejected")
        print(f"      response: {body}")
        print("      Causes: wrong keys, LIVE keys used against the paper host,")
        print("      keys regenerated in the dashboard, or whitespace in .env.")
        return 1
    if status == 403:
        print("  [2] auth           403 FORBIDDEN — NOT a missing-credential error")
        print(f"      response: {body}")
        print("      Verified 2026-08-03: missing credentials return 401, not 403.")
        print("      So a 403 with keys present suggests the request was refused for")
        print("      another reason — region/IP restriction is the main suspect.")
        print("      Alpaca's own docs contradict themselves on India RESIDENCY")
        print("      (their worked example is an Indian citizen residing in the UK),")
        print("      so treat a 403 from an Indian IP as a live-eligibility question,")
        print("      not a key problem. See docs/research/us-market/01-brokers-and-apis.md")
        return 1
    if status != 200:
        print(f"  [2] auth           unexpected status {status}: {body}")
        return 1
    print("  [2] auth           OK (200 from /v2/account)")

    acct = body if isinstance(body, dict) else {}
    st = acct.get("status")
    num = str(acct.get("account_number", ""))
    cash = acct.get("cash")
    buying = acct.get("buying_power")
    shorting = acct.get("shorting_enabled")
    print(f"  [3] account        status={st} number={num[:6]}... cash={cash} buying_power={buying}")
    if st != "ACTIVE":
        print(f"      WARNING account is not ACTIVE — orders will be rejected")
    if shorting:
        print("      NOTE shorting_enabled=True on the broker side, but our engine blocks")
        print("           shorts in broker.py regardless (RBI LRS margin ban).")

    try:
        import alpaca  # noqa: F401
        print("  [4] alpaca-py SDK  installed")
    except ImportError:
        print("  [4] alpaca-py SDK  NOT installed  ->  pip install alpaca-py")
        print("      (credentials are fine; the SDK is what broker.py imports)")
        return 1

    sys.path.insert(0, str(ROOT))
    from prototype.us.broker import AlpacaBroker
    ok, detail = AlpacaBroker().configured()
    print(f"  [5] AlpacaBroker   {'configured' if ok else 'NOT configured'}  {detail if not ok else ''}")

    print()
    if ok:
        print("  READY. Switch the engine over with:")
        print("      python3 scripts/us-paper-trade.py --once --broker alpaca")
        print("  Then set US_BROKER=alpaca in the launchd plist to make it permanent.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
