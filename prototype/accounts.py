"""Users and sessions for the client product.

No Flask imports. This module takes a connection and returns plain values,
so the data layer is testable without a request context and every Flask
concern lives in accounts_web.py and client_auth.py.

Two different hashes on purpose. Passwords go through werkzeug's slow KDF,
because a password is drawn from a space an attacker can enumerate. Session
tokens get a plain SHA-256, because 256 bits of secrets output has no
dictionary behind it -- a slow hash would buy nothing and would charge its
cost on every gated request rather than once per login. Hashing the token at
all still matters: a database leak then yields digests, not live cookies.
"""
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.security import check_password_hash, generate_password_hash

LOCKOUT_THRESHOLD = 10
LOCKOUT_MINUTES = 15


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _parse(text):
    return datetime.fromisoformat(text)


def create_user(conn, email, password):
    """Create an account. Returns the new id. Raises ValueError if it exists."""
    uid = "u-" + secrets.token_hex(4)
    try:
        conn.execute(
            "INSERT INTO users (id, email, password_hash, created_at) "
            "VALUES (?, ?, ?, ?)",
            (uid, email, generate_password_hash(password), _iso(_now())))
    except sqlite3.IntegrityError:
        raise ValueError("that email already has an account")
    conn.commit()
    return uid


def check_login(conn, email, password):
    """The user id on success, None on every failure.

    Deliberately one return value for unknown-email, wrong-password, locked
    and disabled. A caller that could tell them apart would leak whether an
    address has an account here.
    """
    row = conn.execute(
        "SELECT * FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()
    if row is None:
        return None
    if row["disabled_at"] is not None:
        return None
    if row["locked_until"] and _parse(row["locked_until"]) > _now():
        return None
    if row["locked_until"] and _parse(row["locked_until"]) <= _now():
        conn.execute("UPDATE users SET failed_count = 0, locked_until = NULL WHERE id = ?",
                     (row["id"],))
        conn.commit()
        row = conn.execute(
            "SELECT * FROM users WHERE lower(email) = lower(?)", (email,)).fetchone()

    if not check_password_hash(row["password_hash"], password):
        failed = row["failed_count"] + 1
        locked = None
        if failed >= LOCKOUT_THRESHOLD:
            locked = _iso(_now() + timedelta(minutes=LOCKOUT_MINUTES))
        conn.execute("UPDATE users SET failed_count = ?, locked_until = ? WHERE id = ?",
                     (failed, locked, row["id"]))
        conn.commit()
        return None

    conn.execute("UPDATE users SET failed_count = 0, locked_until = NULL WHERE id = ?",
                 (row["id"],))
    conn.commit()
    return row["id"]
