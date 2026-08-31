#!/usr/bin/env python3
"""
kite-check — Zerodha Kite Connect setup and safety verification.

Run:  python3 scripts/kite-check.py

Reports exactly which of the three modes you are in and what is still missing:
    DATA_ONLY  no credentials — everything falls back to yfinance, nothing can trade
    PAPER      real Kite data, orders simulated locally and never submitted
    LIVE       real money (requires credentials + TWO env flags + no kill switch)

It also prints the safety rails currently in force, because those are the numbers
that will actually stop a runaway engine, and they should never be a surprise.

IMPORTANT — the access token expires DAILY. Kite's login flow issues a request_token
that you exchange for an access_token, and it is only valid for that trading day.
Any "it worked yesterday" failure is almost always this.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prototype.v5 import kite_broker as kb  # noqa: E402


def main() -> int:
    st = kb.KiteBroker().status()
    print("Zerodha Kite Connect — setup & safety check")
    print("=" * 56)
    print(f"  MODE: {st['mode']}")
    print()

    print("  credentials & sdk")
    print(f"    kiteconnect installed : {st['sdk_installed']}")
    print(f"    KITE_API_KEY          : {'present' if st['has_api_key'] else 'MISSING'}")
    print(f"    KITE_ACCESS_TOKEN     : {'present' if st['has_access_token'] else 'MISSING'}")
    print()

    print("  live-order gate (ALL must be true to place real orders)")
    print(f"    KITE_LIVE_ORDERS=1                        : {st['live_orders_env']}")
    print(f"    KITE_LIVE_CONFIRM=I_UNDERSTAND_REAL_MONEY : {st['live_confirm_env']}")
    print(f"    kill switch absent                        : {not st['kill_switch']}")
    print()

    r = st["rails"]
    # Show WHERE each value came from. Without this, a rail silently falling back to a
    # hardcoded default is indistinguishable from one you configured — which is exactly
    # how .env saying 3200 while the broker enforced 5000 went unnoticed on 2026-08-31.
    prov = kb.rails_provenance()
    print("  safety rails currently in force")
    print(f"    max order value    : Rs {r['max_order_value']:,.0f}"
          f"   [{prov['KITE_MAX_ORDER_VALUE']}]")
    print(f"    max daily loss     : Rs {r['max_daily_loss']:,.0f}"
          f"   [{prov['KITE_MAX_DAILY_LOSS']}]")
    print(f"    max open positions : {r['max_open_positions']}"
          f"       [{prov['KITE_MAX_OPEN_POSITIONS']}]")
    if any(v == "default" for v in prov.values()):
        print("    NOTE: a rail reading 'default' is NOT coming from your .env —")
        print("          check the key name if you expected it to be configured.")
    print(f"    kill switch file   : {kb.KILL_SWITCH}  (create it to halt everything)")
    print()

    if st["mode"] == "DATA_ONLY":
        print("  TO REACH PAPER MODE (real Kite data, simulated orders):")
        if not st["sdk_installed"]:
            print("    1. pip install kiteconnect")
        print("    2. Get Kite Connect credentials at developers.kite.trade")
        print("       (paid monthly subscription — confirm the current price yourself)")
        print("    3. Add to .env:")
        print("         KITE_API_KEY=...")
        print("         KITE_API_SECRET=...")
        print("    4. Run the login flow to get a DAILY access token, then add:")
        print("         KITE_ACCESS_TOKEN=...")
        print("    5. Re-run this script — it should report PAPER.")
        print()
        print("  Nothing can trade in DATA_ONLY. Engines keep using yfinance.")
        return 1

    if st["mode"] == "PAPER":
        print("  PAPER MODE ACTIVE — real Kite market data, orders simulated only.")
        print("  This is the intended state until the live A/B picks an engine.")
        print("  Real orders stay blocked until BOTH env flags are set deliberately.")
        return 0

    print("  *** LIVE MODE — REAL ORDERS WILL BE PLACED WITH REAL MONEY ***")
    print("  If this is unintended, unset KITE_LIVE_ORDERS immediately,")
    print(f"  or create the kill switch: touch {kb.KILL_SWITCH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
