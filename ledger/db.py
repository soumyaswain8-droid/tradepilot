"""Connection + migration helpers. Never prints the DSN.

Env: TP_LEDGER_DSN (default: local DevPilot Postgres), TP_LEDGER_SCHEMA (default `tradepilot`;
tests point this at a throwaway schema). Driver: psycopg (3) if importable, else psycopg2.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_DSN = "postgresql://devpilot:CV1TZAjNYd7Y4KkT9agnlUdVYJ7pBLRe@localhost:5499/devpilot"
DEFAULT_SCHEMA = "tradepilot"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

try:  # pragma: no cover - which driver is present is an environment fact
    import psycopg as _drv  # type: ignore
    DRIVER = "psycopg"
except ImportError:  # pragma: no cover
    import psycopg2 as _drv  # type: ignore
    DRIVER = "psycopg2"


def dsn() -> str:
    return os.environ.get("TP_LEDGER_DSN") or DEFAULT_DSN


def schema() -> str:
    s = os.environ.get("TP_LEDGER_SCHEMA") or DEFAULT_SCHEMA
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", s):
        raise ValueError("TP_LEDGER_SCHEMA must be a plain lowercase identifier")
    return s


def connect(autocommit: bool = False):
    """DB-API connection; raises the driver's OperationalError when unreachable."""
    conn = _drv.connect(dsn())
    conn.autocommit = autocommit
    return conn


def reachable() -> bool:
    try:
        conn = connect(autocommit=True)
    except Exception:
        return False
    conn.close()
    return True


def migration_sql(target_schema: str | None = None) -> str:
    """Text of 001_ledger.sql, re-pointed at `target_schema` (only schema-qualified
    identifiers are rewritten; the 'tradepilot' tenant default is untouched)."""
    sql = (MIGRATIONS_DIR / "001_ledger.sql").read_text()
    target = target_schema or schema()
    if target != DEFAULT_SCHEMA:
        sql = re.sub(r"\btradepilot\.", f"{target}.", sql)
        sql = sql.replace(f"CREATE SCHEMA IF NOT EXISTS {DEFAULT_SCHEMA}", f"CREATE SCHEMA IF NOT EXISTS {target}")
    return sql


def apply_migration(conn, target_schema: str | None = None) -> None:
    """Idempotent: safe to call on every start."""
    sql = migration_sql(target_schema)
    with conn.cursor() as cur:
        cur.execute(sql)
    if not conn.autocommit:
        conn.commit()


def rows_as_dicts(cur) -> list[dict]:
    cols = [d[0] for d in cur.description]
    out = []
    for r in cur.fetchall():
        d = dict(zip(cols, r))
        for k, v in d.items():
            if hasattr(v, "as_integer_ratio") and type(v).__name__ == "Decimal":
                d[k] = float(v)
        out.append(d)
    return out
