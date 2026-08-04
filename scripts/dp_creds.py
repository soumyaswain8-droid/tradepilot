"""Resolve the DevPilot DB password without hardcoding it in tracked files.

Lookup order:
  1. $DEVPILOT_DB_PW
  2. DB_PASSWORD= in ~/.devpilot/credentials.env  (mode 600, outside every git repo)

The file fallback is not optional. These scripts run under launchd, and launchd
does not inherit the login shell environment — an env-var-only resolver would
leave every scheduled run unable to authenticate.

Raises rather than returning a default: failing closed beats connecting with a
stale credential.
"""
import os
from pathlib import Path

_CRED_FILE = Path.home() / ".devpilot" / "credentials.env"
_KEY = "DB_PASSWORD="


def devpilot_db_password() -> str:
    pw = os.environ.get("DEVPILOT_DB_PW")
    if pw:
        return pw
    try:
        for line in _CRED_FILE.read_text().splitlines():
            if line.startswith(_KEY):
                value = line[len(_KEY):].strip()
                if value:
                    return value
    except OSError:
        pass
    raise RuntimeError(
        "DevPilot DB password not found. Set $DEVPILOT_DB_PW, or ensure a "
        f"DB_PASSWORD= line exists in {_CRED_FILE}"
    )
