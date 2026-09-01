### Task 1: Users table and user records

**Files:**
- Modify: `prototype/app_store.py` (the `SCHEMA` string)
- Create: `prototype/accounts.py`
- Test: `tests/test_accounts.py`

**Interfaces:**
- Consumes: `app_store.get_db(path=None)`, `app_store.init_db(conn)`
- Produces:
  - `accounts.create_user(conn, email, password) -> str` (the new user id; raises `ValueError` if the email exists)
  - `accounts.check_login(conn, email, password) -> str | None` (user id on success, `None` for every failure)
  - `accounts.LOCKOUT_THRESHOLD = 10`, `accounts.LOCKOUT_MINUTES = 15`

- [ ] **Step 1: Add the users table to the schema**

Append to the `SCHEMA` string in `prototype/app_store.py`, after the existing `positions` index:

```sql
CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    email          TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    disabled_at    TEXT,
    failed_count   INTEGER NOT NULL DEFAULT 0,
    locked_until   TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email
    ON users (lower(email));
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_accounts.py`:

```python
"""Users and sessions.

One rule dominates the login path: a failure must not say WHICH failure.
An unknown email and a wrong password are the same answer, or the form
becomes an account enumerator.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, app_store


@pytest.fixture
def conn(tmp_path):
    c = app_store.get_db(str(tmp_path / "accounts.db"))
    app_store.init_db(c)
    yield c
    c.close()


def test_creating_a_user_returns_an_id(conn):
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    assert uid
    assert isinstance(uid, str)


def test_the_password_is_not_stored_in_the_clear(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert "correct horse" not in stored


def test_a_duplicate_email_is_refused(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    with pytest.raises(ValueError):
        accounts.create_user(conn, "priya@example.com", "another one")


def test_email_uniqueness_ignores_case(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    with pytest.raises(ValueError):
        accounts.create_user(conn, "Priya@Example.com", "another one")


def test_the_right_password_returns_the_user_id(conn):
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    assert accounts.check_login(conn, "priya@example.com", "correct horse") == uid


def test_signing_in_is_case_insensitive_on_the_email(conn):
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    assert accounts.check_login(conn, "PRIYA@example.com", "correct horse") == uid


def test_the_wrong_password_returns_none(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    assert accounts.check_login(conn, "priya@example.com", "wrong") is None


def test_an_unknown_email_returns_none_exactly_like_a_wrong_password(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    assert accounts.check_login(conn, "nobody@example.com", "anything") is None


def test_a_disabled_account_cannot_sign_in(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    conn.execute("UPDATE users SET disabled_at = '2026-01-01T00:00:00+00:00'")
    conn.commit()
    assert accounts.check_login(conn, "priya@example.com", "correct horse") is None


def test_repeated_failures_lock_the_account(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    for _ in range(accounts.LOCKOUT_THRESHOLD):
        accounts.check_login(conn, "priya@example.com", "wrong")
    # The correct password is now refused, because the account is locked.
    assert accounts.check_login(conn, "priya@example.com", "correct horse") is None


def test_a_lock_expires(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    for _ in range(accounts.LOCKOUT_THRESHOLD):
        accounts.check_login(conn, "priya@example.com", "wrong")
    conn.execute("UPDATE users SET locked_until = '2020-01-01T00:00:00+00:00'")
    conn.commit()
    assert accounts.check_login(conn, "priya@example.com", "correct horse")


def test_a_successful_login_clears_the_failure_count(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    for _ in range(3):
        accounts.check_login(conn, "priya@example.com", "wrong")
    accounts.check_login(conn, "priya@example.com", "correct horse")
    row = conn.execute("SELECT failed_count, locked_until FROM users").fetchone()
    assert row["failed_count"] == 0
    assert row["locked_until"] is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_accounts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prototype.accounts'`

- [ ] **Step 4: Write the module**

Create `prototype/accounts.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_accounts.py -q`
Expected: PASS, 12 tests.

- [ ] **Step 6: Prove the enumeration test binds**

Change `check_login`'s `if row is None: return None` to `raise ValueError("no such user")`, run `python3 -m pytest tests/test_accounts.py -q`, and confirm `test_an_unknown_email_returns_none_exactly_like_a_wrong_password` goes RED. Restore the line and confirm GREEN. Report both observations.

A test that cannot fail is worse than no test, and this one guards the rule that stops the login form enumerating accounts.

- [ ] **Step 7: Commit**

```bash
git add prototype/app_store.py prototype/accounts.py tests/test_accounts.py
git commit -m "feat(accounts): users table and password checking

Lockout at 10 failures for 15 minutes. One return value for every
failure mode, so the form cannot be used to discover whether an
address has an account."
```

---

