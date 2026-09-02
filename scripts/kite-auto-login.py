#!/usr/bin/env python3
"""
kite-auto-login — refresh the daily Kite access token without a human.

WHY THIS EXISTS. Zerodha invalidates the access token at 06:00 IST every day and the
replacement normally requires an interactive browser login with a TOTP code. Three
scheduled jobs existed purely to nag a human through that ritual, and it was the single
blocker on running this system unattended — on this Mac or anywhere else.

WHAT IT COSTS, stated plainly because it is a real change in posture. This reads a
password and a TOTP seed from .env. Anyone who can read that file can log into the
trading account and place orders. Until now the seed lived only on a phone, which meant
a compromised machine could not by itself reach the account. That is no longer true. The
mitigations below are real but they do not restore the old property:

  - .env is 0600 and gitignored (both verified), and .gitignore now covers .env.* after
    a stray backup was found unignored on 2026-09-01
  - this script NEVER logs or prints a credential, a TOTP code, or a token; failures
    report the STAGE that failed, never the payload
  - it writes the token atomically (temp file + os.replace) rather than the truncating
    full-file rewrite the Flask callback does, so a crash mid-write cannot leave .env
    empty and lock the system out entirely
  - it refuses to run if .env is group- or world-readable

ON ZERODHA'S TERMS. Kite Connect's documented flow is the interactive browser login;
programmatic login is not the published path, and Zerodha has historically discouraged
it. This automates access to the OWNER'S OWN account with the owner's own credentials,
which is the ordinary reading of personal automation — but the account holder carries
whatever terms risk exists. It is recorded here so the choice stays visible rather than
buried in a cron job.

    python3 scripts/kite-auto-login.py            # refresh now
    python3 scripts/kite-auto-login.py --check    # is the current token alive?
    python3 scripts/kite-auto-login.py --dry-run  # verify config, do not log in

Requires in .env: KITE_API_KEY, KITE_API_SECRET, KITE_USER_ID, KITE_PASSWORD,
KITE_TOTP_SECRET.
"""
from __future__ import annotations

import argparse
import os
import stat
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
ENV = ROOT / ".env"

LOGIN = "https://kite.zerodha.com/api/login"
TWOFA = "https://kite.zerodha.com/api/twofa"


def _fail(stage: str, detail: str = "") -> None:
    """Report the stage, never the payload — a login error can echo credentials.

    Also alerts. This runs unattended before the open, and a silent failure here means
    a dark session: no ticks, no screen, no floor. A log line nobody reads at 08:15 is
    indistinguishable from success until 09:16, which is far too late to fix it by hand.
    The alert carries the STAGE only — never the credential that failed.
    """
    msg = f"KITE AUTO-LOGIN FAILED at {stage}" + (f": {detail[:120]}" if detail else "")
    print(f"  {msg}", flush=True)
    # A preflight failure means "not configured yet" — a setup state the owner already
    # knows about, not a runtime fault. Alerting on it every weekday morning until the
    # credentials are added would train them to ignore the channel, and this alert has
    # to still mean something on the morning a password is actually rejected.
    if stage == "preflight":
        raise SystemExit(2)
    try:
        from prototype.v5 import telegram_bot as tb
        tb.send_alert(f"{msg}\nThe token is NOT refreshed. Log in manually before 09:15.")
    except Exception as e:
        print(f"  (alert could not be sent: {str(e)[:60]})", flush=True)
    raise SystemExit(2)


def check_perms() -> None:
    """Refuse to read secrets from a file others can read."""
    if not ENV.exists():
        _fail("preflight", f"{ENV} does not exist")
    mode = ENV.stat().st_mode
    if mode & (stat.S_IRGRP | stat.S_IROTH):
        _fail("preflight",
              f".env is group/world readable ({stat.filemode(mode)}) — run: chmod 600 .env")


def cfg() -> dict:
    from prototype.envcfg import get
    need = ("KITE_API_KEY", "KITE_API_SECRET", "KITE_USER_ID",
            "KITE_PASSWORD", "KITE_TOTP_SECRET")
    out = {k: get(k) for k in need}
    missing = [k for k, v in out.items() if not v]
    if missing:
        _fail("preflight", "missing from .env: " + ", ".join(missing))
    return out


def write_token(token: str) -> None:
    """Replace KITE_ACCESS_TOKEN atomically.

    The Flask callback truncates and rewrites .env in place; a crash between truncate
    and write leaves an EMPTY secrets file, which locks the whole system out on a
    trading morning. Write a temp file in the same directory and os.replace() it, so
    the file is either the old content or the new one and never nothing.
    """
    lines = [l for l in ENV.read_text().splitlines()
             if not l.startswith("KITE_ACCESS_TOKEN=")]
    lines.append(f"KITE_ACCESS_TOKEN={token}")
    fd, tmp = tempfile.mkstemp(dir=str(ROOT), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, ENV)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def token_alive() -> bool:
    try:
        from prototype.v4 import kite_data as kd
        kd.invalidate()                      # never judge on a cached client
        return bool(kd.client().profile().get("user_name"))
    except Exception:
        return False


def login(c: dict, verbose: bool = True) -> str:
    import requests
    import pyotp
    from kiteconnect import KiteConnect

    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 TradePilot/kite-auto-login"

    # stage 1 — password
    try:
        r = s.post(LOGIN, data={"user_id": c["KITE_USER_ID"],
                                "password": c["KITE_PASSWORD"]}, timeout=20)
        j = r.json()
    except Exception as e:
        _fail("login/password", type(e).__name__)
    if r.status_code != 200 or "data" not in j:
        # j may echo the submitted user_id; report only the message field
        _fail("login/password", str(j.get("message", "rejected")))
    request_id = j["data"]["request_id"]
    if verbose:
        print("  stage 1/3 password accepted", flush=True)

    # stage 2 — TOTP
    try:
        code = pyotp.TOTP(c["KITE_TOTP_SECRET"].strip().replace(" ", "")).now()
        r = s.post(TWOFA, data={"user_id": c["KITE_USER_ID"], "request_id": request_id,
                                "twofa_value": code, "twofa_type": "totp"}, timeout=20)
    except Exception as e:
        _fail("login/totp", type(e).__name__)
    if r.status_code != 200:
        _fail("login/totp", "rejected — check the seed and the machine clock")
    if verbose:
        print("  stage 2/3 TOTP accepted", flush=True)

    # stage 3 — collect request_token from the redirect, exchange for access_token
    kc = KiteConnect(api_key=c["KITE_API_KEY"])
    try:
        r = s.get(kc.login_url(), timeout=20, allow_redirects=True)
        qs = parse_qs(urlparse(r.url).query)
        req_tok = (qs.get("request_token") or [None])[0]
        if not req_tok:
            for h in r.history:
                q = parse_qs(urlparse(h.headers.get("Location", "")).query)
                if q.get("request_token"):
                    req_tok = q["request_token"][0]
                    break
    except Exception as e:
        _fail("login/redirect", type(e).__name__)
    if not req_tok:
        _fail("login/redirect",
              "no request_token in the redirect — check the app's redirect_url")
    try:
        data = kc.generate_session(req_tok, api_secret=c["KITE_API_SECRET"])
    except Exception as e:
        _fail("login/exchange", type(e).__name__)
    if verbose:
        print("  stage 3/3 session exchanged", flush=True)
    return data["access_token"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report token liveness only")
    ap.add_argument("--dry-run", action="store_true", help="verify config, do not log in")
    ap.add_argument("--force", action="store_true", help="refresh even if the token works")
    a = ap.parse_args()

    check_perms()
    if a.check:
        alive = token_alive()
        print(f"  token: {'LIVE' if alive else 'DEAD'}")
        return 0 if alive else 1

    c = cfg()
    if a.dry_run:
        print("  config OK — all five credentials present, .env perms 0600")
        return 0

    # Do not burn a login when the current token is fine. Zerodha invalidates the
    # PREVIOUS token whenever a new session is created, so a redundant refresh would
    # kill a working token and break every process already streaming on it.
    if not a.force and token_alive():
        print(f"  {datetime.now():%H:%M:%S} token already live — nothing to do", flush=True)
        return 0

    print(f"  {datetime.now():%H:%M:%S} refreshing Kite token...", flush=True)
    tok = login(c)
    write_token(tok)

    if token_alive():
        print(f"  {datetime.now():%H:%M:%S} token refreshed and verified", flush=True)
        return 0
    _fail("verify", "wrote a token that does not authenticate")


if __name__ == "__main__":
    sys.exit(main())
