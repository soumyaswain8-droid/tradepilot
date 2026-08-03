#!/usr/bin/env python3
"""
kite-token-check — is today's Kite access token actually valid?

Zerodha's access_token expires EVERY trading day. The failure is silent and
late: engines start fine at 08:50, then every Kite call fails once the market
opens. This turns that into a loud 08:50 failure instead.

Exit 0 = token valid (or Kite not in use at all, which is not an error)
Exit 1 = credentials present but the token is missing/expired -> ACT NOW

Wire into preflight so it pages before the open, not during it.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v5 import kite_broker as kb  # noqa: E402


def main() -> int:
    c = kb.credentials()
    if not c["api_key"]:
        print("  kite: not configured — engines use yfinance. Not an error.")
        return 0
    if not kb.sdk_available():
        print("  kite: KITE_API_KEY set but kiteconnect NOT installed")
        return 1
    if not c["access_token"]:
        print("  kite: NO ACCESS TOKEN — expired or never generated.")
        print("        Fix now: open http://localhost:5050/kite/login")
        return 1
    try:
        from kiteconnect import KiteConnect
        k = KiteConnect(api_key=c["api_key"])
        k.set_access_token(c["access_token"])
        p = k.profile()
        print(f"  kite: token VALID — {p.get('user_name','?')} ({p.get('user_id','?')})")
        return 0
    except Exception as e:
        msg = str(e)[:90]
        print(f"  kite: token REJECTED — {type(e).__name__}: {msg}")
        print("        Almost always daily expiry. Fix: http://localhost:5050/kite/login")
        return 1


if __name__ == "__main__":
    sys.exit(main())
