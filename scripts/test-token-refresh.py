#!/usr/bin/env python3
"""
Regression test for the 2026-08-27 dead-token bug.

THE FAILURE, exactly as it happened. A long-running process (Flask) touched Kite at
08:40, before the daily login. client() saw a new calendar day, rebuilt with the
PREVIOUS day's expired token, and cached that for the rest of the day. The 09:00
login wrote a fresh token to .env and nothing noticed. Every quote failed until the
process was restarted -- and it would have recurred every morning.

This reproduces that sequence against the real module and asserts the cache now
heals itself. It uses a throwaway .env copy and never touches the live one.

    python3 scripts/test-token-refresh.py
"""
from __future__ import annotations
import sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prototype.v4 import kite_data as kd

FAILS = []


def check(name, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{'  — ' + detail if detail else ''}")
    if not ok:
        FAILS.append(name)


def main():
    live = ROOT / ".env"
    original = live.read_text()
    real_tok = None
    for ln in original.splitlines():
        if ln.startswith("KITE_ACCESS_TOKEN="):
            real_tok = ln.split("=", 1)[1].strip().strip('"').strip("'")
    if not real_tok:
        print("  no KITE_ACCESS_TOKEN in .env — cannot run")
        return 1

    # SANDBOX — the live .env is never written. This file's docstring always CLAIMED
    # "a throwaway .env copy", but until 2026-09-03 it wrote DEADTOKEN_FROM_YESTERDAY
    # straight into the real one and restored it afterwards. Scheduled at 09:12, four
    # minutes before the floor starts, that put a deliberately invalid credential into
    # the live secrets file during the exact window every process reads it — a
    # regression test for the dead-token bug, injecting the dead-token bug.
    #
    # The redirect has to be on envcfg.ENV_FILE, not on kd.ROOT: _creds() delegates to
    # envcfg.get(), which resolves the path itself. Pointing kd.ROOT at a temp dir
    # would look right and change nothing.
    import shutil
    import tempfile

    from prototype import envcfg
    tmpdir = Path(tempfile.mkdtemp(prefix="tokentest-"))
    env = tmpdir / ".env"
    shutil.copy(live, env)
    real_env_file = envcfg.ENV_FILE
    envcfg.ENV_FILE = env
    live_before = live.read_text()

    try:
        # 1. poison the cache exactly as the morning did: a stale token, cached today
        env.write_text(original.replace(real_tok, "DEADTOKEN_FROM_YESTERDAY"))
        kd._kite = kd._kite_day = kd._kite_tok = None
        c1 = kd.client()
        check("a dead token still builds a client (as it did at 08:40)",
              c1 is not None)

        # 2. the login writes a fresh token — the process is NOT restarted
        env.write_text(original)
        c2 = kd.client()
        check("client is REBUILT after .env changes, with no restart",
              c2 is not c1,
              "same object returned — the bug is back" if c2 is c1 else "new object")
        check("the rebuilt client carries the NEW token",
              kd._kite_tok == real_tok)

        # 3. and it actually works against the API
        try:
            uid = c2.profile().get("user_id")
            check("the refreshed client authenticates", bool(uid), f"user {uid}")
        except Exception as e:
            check("the refreshed client authenticates", False, str(e)[:60])

        # 4. an unchanged token must NOT rebuild — otherwise we hammer the API
        c3 = kd.client()
        check("an unchanged token reuses the cache", c3 is c2)

        # 5. the console must never present a stale quote as live
        from prototype import floor_live as fl
        fl._CACHE["quotes"] = {"NSE:FAKE": {"last_price": 999.0}}
        fl._CACHE["quotes_at"] = 0            # ancient
        kd._kite = kd._kite_day = kd._kite_tok = None
        env.write_text(original.replace(real_tok, "DEADTOKEN_AGAIN"))
        got = fl._quotes(["FAKE"])
        check("a stale quote is DISCARDED, not served as live",
              not got, f"served {len(got)} stale rows" if got else "returned empty")
    finally:
        envcfg.ENV_FILE = real_env_file
        kd._kite = kd._kite_day = kd._kite_tok = None
        shutil.rmtree(tmpdir, ignore_errors=True)
        # Assert the live file was never touched. The previous version restored the
        # live .env from a variable and called that "intact" — which is only true if
        # nothing crashed between poisoning and restoring. Comparing the file against
        # what it held on entry is the check that would actually have caught this.
        untouched = live.read_text() == live_before
        print(f"\n  live .env untouched: {'yes' if untouched else 'NO — INVESTIGATE'}")
        if not untouched:
            FAILS.append("live .env was modified")

    print()
    if FAILS:
        print(f"  {len(FAILS)} FAILURE(S): {', '.join(FAILS)}")
        return 1
    print("  all checks passed — the morning-token bug cannot recur silently")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ── run me from the morning preflight ────────────────────────────────────────
# Registered so this is exercised every trading day, not only when someone
# remembers. A regression test that is never run is documentation.
