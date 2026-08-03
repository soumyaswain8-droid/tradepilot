#!/usr/bin/env python3
"""
kite-token-reminder — escalating nudges to re-auth Kite before the market opens.

Zerodha invalidates the access_token at 06:00 every day (their words: "regulatory
requirement"). The login needs interactive 2FA, so it cannot be automated without
storing a password and TOTP seed on disk — which collapses 2FA into 1FA and puts
full account credentials, not just a scoped API key, in a file. We chose not to.

So the real risk is simply FORGETTING, which is a notification problem:

    06:05  morning    token just expired — here is the link
    08:50  preflight  market opens in 25 minutes
    09:10  lastcall   5 minutes to open

SILENT WHEN THE TOKEN IS VALID. A reminder that fires every day regardless is a
reminder people learn to ignore, and this stack already has a live example of that
(preflight's stale ML failures). Noise is not safety.

Run:
    python3 scripts/kite-token-reminder.py --stage morning
    python3 scripts/kite-token-reminder.py --stage preflight
    python3 scripts/kite-token-reminder.py --stage lastcall

Exit 0 = token valid or Kite unused. Exit 1 = token dead, alert sent.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prototype.v5 import kite_broker as kb  # noqa: E402

LOGIN_URL = "http://localhost:5050/kite/login"

STAGES = {
    "morning":   ("Kite token expired",
                  "Zerodha invalidated it at 06:00 (their daily regulatory reset).",
                  "Plenty of time - market opens 09:15."),
    "preflight": ("Kite token STILL expired",
                  "Market opens in ~25 minutes and the token is not valid.",
                  "Engines will run on yfinance; Kite data and any Kite orders will fail."),
    "lastcall":  ("LAST CALL - Kite token expired",
                  "Market opens in ~5 minutes. This is the final reminder.",
                  "After this you are trading the session without Kite."),
}


def telegram(msg: str) -> bool:
    """Plain text only. A Markdown page died with 'can't parse entities' on
    2026-07-28 and never reached anyone — an alert that cannot be delivered is
    worse than no alert, because it looks like it worked."""
    env = ROOT / ".env"
    if not env.exists():
        return False
    tok = chat = None
    for ln in env.read_text().splitlines():
        if ln.startswith("TELEGRAM_BOT_TOKEN="):
            tok = ln.split("=", 1)[1].strip().strip('"')
        elif ln.startswith("TELEGRAM_CHAT_ID="):
            chat = ln.split("=", 1)[1].strip().strip('"')
    if not (tok and chat):
        return False
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        with urllib.request.urlopen(
                f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=10) as r:
            return r.status == 200
    except Exception as e:
        print(f"  telegram send failed: {e}", file=sys.stderr)
        return False


def token_ok() -> tuple:
    """(is_ok, human_reason). Makes a REAL API call — an expired token is
    present-but-rejected, so checking for a non-empty value proves nothing."""
    c = kb.credentials()
    if not c["api_key"]:
        return True, "kite not configured (engines use yfinance) - not an error"
    if not kb.sdk_available():
        return False, "kiteconnect SDK not installed"
    if not c["access_token"]:
        return False, "no access token in .env"
    try:
        from kiteconnect import KiteConnect
        k = KiteConnect(api_key=c["api_key"])
        k.set_access_token(c["access_token"])
        p = k.profile()
        return True, f"valid - {p.get('user_name','?')} ({p.get('user_id','?')})"
    except Exception as e:
        return False, f"rejected by Zerodha: {type(e).__name__}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=list(STAGES), default="morning")
    ap.add_argument("--force", action="store_true",
                    help="send even when the token is valid (for testing the path)")
    a = ap.parse_args()

    ok, reason = token_ok()
    stamp = datetime.now().strftime("%H:%M")

    if ok and not a.force:
        print(f"[{stamp}] kite token {reason} - no alert sent ({a.stage})")
        return 0

    title, urgency, consequence = STAGES[a.stage]
    msg = (f"{title}\n"
           f"{urgency}\n"
           f"{consequence}\n\n"
           f"Re-auth: {LOGIN_URL}\n"
           f"Then verify: python3 scripts/kite-token-check.py\n\n"
           f"(reason: {reason})")
    sent = telegram(msg)
    print(f"[{stamp}] {a.stage.upper()}: token NOT valid ({reason}) - "
          f"telegram {'sent' if sent else 'FAILED'}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
