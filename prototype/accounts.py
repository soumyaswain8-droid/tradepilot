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
    """ISO-8601 UTC, always microsecond-width.

    The sessions sweep compares these as TEXT in SQL, so the string order
    has to equal the chronological order. isoformat() drops the microsecond
    field when it is zero, which happens to still sort correctly because
    '+' < '.' in ASCII -- a coincidence, not a guarantee. Forcing the width
    makes the comparison sound by construction rather than by luck.
    """
    return dt.isoformat(timespec="microseconds")


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


SESSION_SLIDING_DAYS = 30
SESSION_MAX_DAYS = 90


def _hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(conn, user_id):
    """Start a session. Returns the raw token -- the caller puts it in a cookie."""
    token = secrets.token_urlsafe(32)
    now = _now()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen) "
        "VALUES (?, ?, ?, ?, ?)",
        (_hash_token(token), user_id, _iso(now),
         _iso(now + timedelta(days=SESSION_SLIDING_DAYS)), _iso(now)))
    # Opportunistic sweep. A scheduled job for a table this size would be
    # machinery without a purpose.
    conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_iso(now),))
    conn.commit()
    return token


def lookup_session(conn, token):
    """The user id behind a token, or None. Slides the expiry as a side effect."""
    if not token:
        return None
    row = conn.execute("SELECT * FROM sessions WHERE token_hash = ?",
                       (_hash_token(token),)).fetchone()
    if row is None:
        return None

    now = _now()
    cap = _parse(row["created_at"]) + timedelta(days=SESSION_MAX_DAYS)
    if _parse(row["expires_at"]) <= now or cap <= now:
        return None

    slid = min(now + timedelta(days=SESSION_SLIDING_DAYS), cap)
    conn.execute("UPDATE sessions SET expires_at = ?, last_seen = ? WHERE token_hash = ?",
                 (_iso(slid), _iso(now), row["token_hash"]))
    conn.commit()
    return row["user_id"]


def revoke_session(conn, token):
    """Delete a session. The row is the authority, so this is a real logout."""
    if not token:
        return
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash_token(token),))
    conn.commit()
