#!/usr/bin/env python3
"""
kite-setup-auto — add the automated-login credentials to .env, safely and verifiably.

Run this YOURSELF in a terminal. It prompts for the three values the daily auto-login
needs, never echoes the password, and writes them atomically.

    python3 scripts/kite-setup-auto.py

WHY A SCRIPT RATHER THAN EDITING .env BY HAND. Two of the three values fail SILENTLY
when wrong, and both failures surface at 08:30 on a trading morning:

  - a TOTP seed with a typo, a space, or the 6-digit CODE pasted instead of the SEED
    produces a valid-looking token that Zerodha rejects
  - a trailing space or a quote around a value changes the string that gets sent

So this validates before writing: it generates a TOTP code from the seed you give it and
asks you to confirm it matches your authenticator app RIGHT NOW. If it does not match,
nothing is written. That check catches the overwhelmingly common mistake at the moment
you can still fix it, rather than during tomorrow's open.

WHAT YOU ARE AGREEING TO. The seed lets this machine generate your second factor. Anyone
who can read .env can then log into the trading account and place orders. Until now the
seed lived only on your phone, which meant a compromised laptop could not by itself reach
the account — that stops being true. .env is 0600 and gitignored, and the login script
never logs a credential, but those mitigations do not restore the old property. This is a
deliberate trade of security for autonomy, and the script says so out loud before asking.
"""
from __future__ import annotations

import getpass
import os
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
KEYS = ("KITE_USER_ID", "KITE_PASSWORD", "KITE_TOTP_SECRET")


def main() -> int:
    print(__doc__.split("WHAT YOU ARE AGREEING TO.")[1].split("script says so out loud")[0]
          .strip().replace("\n", " ").replace("  ", " "))
    print()
    if input("  Proceed? [y/N] ").strip().lower() != "y":
        print("  nothing written.")
        return 1

    if not ENV.exists():
        print(f"  {ENV} does not exist — aborting rather than creating a new one.")
        return 2
    if ENV.stat().st_mode & (stat.S_IRGRP | stat.S_IROTH):
        print("  .env is group/world readable. Run: chmod 600 .env")
        return 2

    print()
    user = input("  Zerodha user ID (e.g. AB1234): ").strip()
    pwd = getpass.getpass("  Zerodha password (not echoed): ").strip()
    seed = getpass.getpass("  TOTP seed, the base32 string (not echoed): ").strip()
    seed = seed.replace(" ", "").upper()

    if not (user and pwd and seed):
        print("  a value was empty — nothing written.")
        return 2
    if len(seed) < 16:
        print(f"  that seed is {len(seed)} characters, which is too short to be a base32")
        print("  secret. You may have pasted the 6-digit CODE instead of the SEED.")
        return 2

    # Validate the seed against the user's own authenticator before writing anything.
    try:
        import pyotp
        code = pyotp.TOTP(seed).now()
    except Exception as e:
        print(f"  that seed is not valid base32 ({type(e).__name__}) — nothing written.")
        return 2

    print()
    print(f"  This seed generates:  {code}")
    print("  Open your authenticator app and compare RIGHT NOW.")
    if input("  Does it match? [y/N] ").strip().lower() != "y":
        print("  Not written. Re-run and paste the SEED shown when 2FA was set up —")
        print("  not the rotating 6-digit code. If it is lost, re-enrol 2FA in Kite.")
        return 2

    vals = {"KITE_USER_ID": user, "KITE_PASSWORD": pwd, "KITE_TOTP_SECRET": seed}
    lines = [l for l in ENV.read_text().splitlines()
             if not any(l.startswith(k + "=") for k in KEYS)]
    lines += [f"{k}={v}" for k, v in vals.items()]

    # Atomic: same-directory temp then os.replace, so a crash leaves .env either
    # untouched or complete — never truncated. The Flask callback's in-place rewrite is
    # what this deliberately avoids.
    fd, tmp = tempfile.mkstemp(dir=str(ROOT), prefix=".env.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        os.chmod(tmp, 0o600)
        os.replace(tmp, ENV)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise

    print()
    print("  Written. Verify with:")
    print("    python3 scripts/kite-auto-login.py --dry-run")
    print("  Then a real refresh (safe — it refuses if the current token still works):")
    print("    python3 scripts/kite-auto-login.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
