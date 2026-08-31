#!/usr/bin/env python3
"""
envcfg — the one place that reads configuration.

WHY THIS EXISTS. This project keeps its configuration in .env, but NOTHING loads .env
into the process environment — there is no python-dotenv call anywhere. So any module
that reaches for os.environ.get("SOMETHING") reads a variable that is never set, and
silently falls back to whatever default was hardcoded next to it.

That is not theoretical. On 2026-08-31 the broker's safety rails — the per-order cap,
the daily-loss circuit breaker, the open-position limit — were os.environ-only. The
.env file said 3200 / 1250 / 8 and the broker was enforcing 5000 / 1000 / 5, while
`kite-check` cheerfully PRINTED the enforced numbers as though they were the
configured ones. A cap that ignores its own configuration is worse than no cap,
because the screen tells you it is protecting you.

Three files had each hand-rolled their own .env parser by then — kite_data._creds(),
kite_broker._rail(), and Floor.start() — all slightly different, and any new code
naturally reached for os.environ and got nothing. One helper removes the whole class.

    from prototype.envcfg import get, get_float, get_int

    token = get("KITE_ACCESS_TOKEN")
    cap   = get_float("KITE_MAX_ORDER_VALUE", 5000)

PRECEDENCE: os.environ first, then .env, then the default. The environment winning
matters — it is how you override a single run without editing a file that other
processes are reading at the same time.

NOT CACHED, deliberately. Kite's access token is rewritten in .env every morning while
long-running processes are still up, and a cached read is how a process ends up
serving a credential that expired hours ago. These files are a few hundred bytes; the
read costs nothing next to being wrong.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"


def _from_file(key: str) -> Optional[str]:
    if not ENV_FILE.exists():
        return None
    try:
        for ln in ENV_FILE.read_text().splitlines():
            ln = ln.strip()
            if ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
    except Exception:
        return None                 # an unreadable .env must not take the caller down
    return None


def get(key: str, default: Optional[str] = None) -> Optional[str]:
    """os.environ, then .env, then the default."""
    v = os.environ.get(key)
    if v:
        return v
    v = _from_file(key)
    return v if v is not None else default


def get_float(key: str, default: float) -> float:
    v = get(key)
    try:
        return float(v) if v is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def get_int(key: str, default: int) -> int:
    v = get(key)
    try:
        return int(float(v)) if v is not None else int(default)
    except (TypeError, ValueError):
        return int(default)


def source_of(key: str) -> str:
    """Where a value actually came from — for diagnostics that must not guess.

    A rails display that cannot say whether it is showing the configured value or a
    hardcoded default is exactly how the 3200-vs-5000 discrepancy went unnoticed.
    """
    if os.environ.get(key):
        return "environ"
    return ".env" if _from_file(key) is not None else "default"


if __name__ == "__main__":
    import sys
    for k in sys.argv[1:] or ["KITE_MAX_ORDER_VALUE", "KITE_MAX_DAILY_LOSS",
                              "KITE_MAX_OPEN_POSITIONS"]:
        print(f"  {k:<28} {get(k)!r:<12} from {source_of(k)}")
