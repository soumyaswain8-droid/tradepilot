# Accounts Auth Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `current_user()` stub with real sessions, so the client dashboard's five gated endpoints answer to whoever is actually signed in.

**Architecture:** A `users` table and a `sessions` table in the existing `tradepilot_app.db`. Sign-in is a server-rendered form POST that creates a session row and sets a cookie carrying an opaque random token; every gated request resolves that token to a user id through one indexed read. No `SECRET_KEY` is introduced because the token needs no signature.

**Tech Stack:** Flask 3.1.1, Jinja, stdlib `sqlite3` / `secrets` / `hashlib` / `getpass`, `werkzeug.security` for password hashing. No new dependencies. No JavaScript on the login page.

**Spec:** `docs/superpowers/specs/2026-08-31-accounts-auth-core-design.md`

## Global Constraints

- No new dependencies. `requirements.txt` must be unchanged at the end of this plan.
- All DDL uses `IF NOT EXISTS`. Schema lives in `prototype/app_store.py`'s `SCHEMA` string and runs through `init_db`.
- Passwords go through `werkzeug.security.generate_password_hash` / `check_password_hash` using werkzeug's **default** method — never a pinned algorithm.
- Session tokens are `secrets.token_urlsafe(32)`, stored as a `hashlib.sha256` hex digest. Never store the raw token.
- Login failures return one identical message for an unknown email and a wrong password.
- The login page is server-rendered and contains no JavaScript.
- `fetch` stays confined to `prototype/static/app/api.js`. Any client-side work is ES5: no arrow functions, no `const`/`let`, no template literals.
- Cookie: name `tp_session`, `HttpOnly`, `SameSite=Lax`, `Path=/`, and `Secure` only when the request is HTTPS.
- Lockout: 10 consecutive failures, `locked_until` 15 minutes ahead.
- Session lifetime: sliding 30 days, absolute cap 90 days from `created_at`.
- Port 5050 belongs to a separate running process. Use 5051 or above, and kill only what you start.
- Do not run build commands as part of a task. `pytest` runs are specified per task and are the exception.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `prototype/app_store.py` | modify | `SCHEMA` gains `users` and `sessions` |
| `prototype/accounts.py` | create | user and session data access; no Flask imports |
| `prototype/client_auth.py` | rewrite | `current_user()` reads the cookie; guard gains the `Origin` check |
| `prototype/accounts_web.py` | create | `/app/login`, `/app/logout` blueprint |
| `prototype/templates/login.html` | create | Jinja form, no JavaScript |
| `prototype/app.py` | modify | register the blueprint; scope CORS |
| `scripts/add-client.py` | create | create an account from the terminal |
| `prototype/static/app/main.js` | modify | populate `#who` from `/api/app/me` |
| `docs/APP_MANUAL_CHECKS.md` | modify | replace the edit-the-source signed-out procedure |
| `tests/test_accounts.py` | create | data layer |
| `tests/test_accounts_web.py` | create | login, logout, redirects, cookie flags |
| `tests/test_client_auth.py` | modify | two tests assume the stub and must sign in instead |
| `tests/test_cors_scope.py` | create | `/api/app/*` carries no CORS headers |

`prototype/accounts.py` imports no Flask. It takes a connection and returns plain values, so the data layer is testable without a request context and the web layer holds all the Flask concerns.

---

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

### Task 2: Sessions

**Files:**
- Modify: `prototype/app_store.py` (the `SCHEMA` string)
- Modify: `prototype/accounts.py`
- Test: `tests/test_accounts.py`

**Interfaces:**
- Consumes: `accounts.create_user`, `accounts._now`, `accounts._iso`
- Produces:
  - `accounts.create_session(conn, user_id) -> str` (the raw token; only the hash is stored)
  - `accounts.lookup_session(conn, token) -> str | None` (user id; slides `expires_at`, honours the cap)
  - `accounts.revoke_session(conn, token) -> None`
  - `accounts.SESSION_SLIDING_DAYS = 30`, `accounts.SESSION_MAX_DAYS = 90`

- [ ] **Step 1: Add the sessions table to the schema**

Append to `SCHEMA` in `prototype/app_store.py`:

```sql
CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id),
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_sessions_user
    ON sessions (user_id);
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_accounts.py`:

```python
def _user(conn):
    return accounts.create_user(conn, "priya@example.com", "correct horse")


def test_a_session_resolves_to_its_user(conn):
    uid = _user(conn)
    token = accounts.create_session(conn, uid)
    assert accounts.lookup_session(conn, token) == uid


def test_the_raw_token_is_never_stored(conn):
    token = accounts.create_session(conn, _user(conn))
    stored = conn.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert stored != token
    assert token not in stored


def test_an_unknown_token_resolves_to_nothing(conn):
    accounts.create_session(conn, _user(conn))
    assert accounts.lookup_session(conn, "not-a-real-token") is None


def test_an_empty_token_resolves_to_nothing(conn):
    accounts.create_session(conn, _user(conn))
    assert accounts.lookup_session(conn, "") is None
    assert accounts.lookup_session(conn, None) is None


def test_an_expired_session_resolves_to_nothing(conn):
    token = accounts.create_session(conn, _user(conn))
    conn.execute("UPDATE sessions SET expires_at = '2020-01-01T00:00:00+00:00'")
    conn.commit()
    assert accounts.lookup_session(conn, token) is None


def test_using_a_session_slides_its_expiry_forward(conn):
    token = accounts.create_session(conn, _user(conn))
    conn.execute("UPDATE sessions SET expires_at = ?",
                 (accounts._iso(accounts._now() + timedelta(days=1)),))
    conn.commit()
    accounts.lookup_session(conn, token)
    fresh = conn.execute("SELECT expires_at FROM sessions").fetchone()[0]
    assert accounts._parse(fresh) > accounts._now() + timedelta(days=29)


def test_sliding_cannot_push_past_the_absolute_cap(conn):
    token = accounts.create_session(conn, _user(conn))
    old = accounts._now() - timedelta(days=89)
    conn.execute("UPDATE sessions SET created_at = ?", (accounts._iso(old),))
    conn.commit()
    accounts.lookup_session(conn, token)
    fresh = conn.execute("SELECT expires_at FROM sessions").fetchone()[0]
    # 89 days old, so the 90-day cap leaves at most one day, not thirty.
    assert accounts._parse(fresh) < accounts._now() + timedelta(days=2)


def test_a_session_past_the_cap_resolves_to_nothing(conn):
    token = accounts.create_session(conn, _user(conn))
    old = accounts._now() - timedelta(days=91)
    conn.execute("UPDATE sessions SET created_at = ?, expires_at = ?",
                 (accounts._iso(old), accounts._iso(accounts._now() + timedelta(days=30))))
    conn.commit()
    assert accounts.lookup_session(conn, token) is None


def test_revoking_a_session_kills_it_immediately(conn):
    token = accounts.create_session(conn, _user(conn))
    accounts.revoke_session(conn, token)
    assert accounts.lookup_session(conn, token) is None


def test_two_sessions_for_one_user_are_independent(conn):
    uid = _user(conn)
    a = accounts.create_session(conn, uid)
    b = accounts.create_session(conn, uid)
    accounts.revoke_session(conn, a)
    assert accounts.lookup_session(conn, a) is None
    assert accounts.lookup_session(conn, b) == uid
```

Add `from datetime import timedelta` to the test file's imports.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_accounts.py -q`
Expected: FAIL — `AttributeError: module 'prototype.accounts' has no attribute 'create_session'`

- [ ] **Step 4: Write the session functions**

Append to `prototype/accounts.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_accounts.py -q`
Expected: PASS, 22 tests.

- [ ] **Step 6: Prove the cap test binds**

In `lookup_session`, change `slid = min(now + timedelta(days=SESSION_SLIDING_DAYS), cap)` to drop the `min` and use only `now + timedelta(days=SESSION_SLIDING_DAYS)`. Run the tests and confirm `test_sliding_cannot_push_past_the_absolute_cap` goes RED. Restore and confirm GREEN. Report both observations.

- [ ] **Step 7: Commit**

```bash
git add prototype/app_store.py prototype/accounts.py tests/test_accounts.py
git commit -m "feat(accounts): server-side sessions with opaque tokens

30-day sliding expiry under a 90-day absolute cap. Only the SHA-256 of
the token is stored, so a database leak yields digests rather than
working cookies. Revocation is a DELETE, which is the property signed
cookies cannot offer."
```

---

### Task 3: The trust boundary

Rewrites `current_user()` to read the cookie, adds the `Origin` check to the guard, and scopes CORS so `/api/app/*` is outside it.

**Files:**
- Rewrite: `prototype/client_auth.py`
- Modify: `prototype/app.py:53` (the `CORS(...)` call)
- Test: `tests/test_client_auth.py` (two existing tests change), `tests/test_cors_scope.py` (create)

**Interfaces:**
- Consumes: `accounts.lookup_session(conn, token) -> str | None`, `app_store.get_db()`
- Produces:
  - `client_auth.current_user() -> str | None` — unchanged signature, real behaviour
  - `client_auth.COOKIE_NAME = "tp_session"`
  - `client_auth.open_store()` — a seam tests monkeypatch to point at a throwaway database, mirroring `client_api.open_store`
  - `PUBLIC_ENDPOINTS` and `GATED_ENDPOINTS` keep their existing names and contents

- [ ] **Step 1: Write the failing tests for the seam**

Replace these two tests in `tests/test_client_auth.py` — they currently pass only because the stub returns a fixed id, and must now sign in:

```python
def test_gated_endpoint_allows_a_user(client, signed_in):
    assert client.get("/api/app/me").status_code == 200


def test_me_returns_the_current_user(client, signed_in):
    body = client.get("/api/app/me").get_json()
    assert body["user_id"] == signed_in
    assert body["plan"] == "none"
```

Add this fixture near the top of the same file, after the imports:

```python
import pytest

from prototype import accounts, app_store, client_auth


@pytest.fixture
def signed_in(client, tmp_path, monkeypatch):
    """A real session, cookie set on the test client. Returns the user id."""
    path = str(tmp_path / "auth.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_auth, "open_store", lambda: app_store.get_db(path))
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    token = accounts.create_session(conn, uid)
    client.set_cookie("localhost", client_auth.COOKIE_NAME, token)
    conn.close()
    return uid
```

Then add these new tests to the same file:

```python
def test_no_cookie_means_no_user(client):
    assert client.get("/api/app/me").status_code == 401


def test_a_forged_token_means_no_user(client, signed_in):
    client.set_cookie("localhost", client_auth.COOKIE_NAME, "forged-token")
    assert client.get("/api/app/me").status_code == 401


def test_an_unsafe_method_from_a_foreign_origin_is_refused(client, signed_in):
    r = client.post("/api/app/positions",
                    json={"symbol": "CIPLA", "qty": 1, "avg_price": 10.0},
                    headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403



def test_a_missing_origin_is_not_treated_as_foreign(client, signed_in):
    """CSRF requires a browser sending cookies, and browsers always send
    Origin on an unsafe cross-origin request. A request with no Origin at all
    is curl or a test -- not the threat model -- and rejecting it would break
    every non-browser caller for no security gain."""
    r = client.post("/api/app/positions", json={"symbol": "CIPLA", "qty": 1,
                                                "avg_price": 10.0})
    assert r.status_code != 403
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_client_auth.py -q`
Expected: FAIL — `AttributeError: module 'prototype.client_auth' has no attribute 'COOKIE_NAME'`

- [ ] **Step 3: Rewrite the auth seam**

Replace `current_user` and `install_guard` in `prototype/client_auth.py`, keeping the module docstring's explanation of why the registries exist, and keeping both registries exactly as they are:

```python
from flask import jsonify, request

from prototype import accounts, app_store

COOKIE_NAME = "tp_session"

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def open_store():
    """Open the store. A named function so tests can point at a throwaway file."""
    return app_store.get_db()


def current_user():
    """The signed-in user's id, or None.

    One indexed read per gated request. The cookie carries an opaque random
    token and nothing else, so there is no signature to verify and no
    SECRET_KEY to manage -- and logout can actually revoke, because the row
    is the authority rather than the cookie.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    conn = open_store()
    try:
        return accounts.lookup_session(conn, token)
    finally:
        conn.close()


def install_guard(app):
    """Refuse gated client endpoints when nobody is signed in."""

    @app.before_request
    def _guard_client_api():
        endpoint = request.endpoint
        if endpoint not in GATED_ENDPOINTS:
            return None
        if current_user() is None:
            return jsonify({"error": "sign in to see this"}), 401
        if request.method in UNSAFE_METHODS:
            origin = request.headers.get("Origin")
            # Only a PRESENT and mismatched Origin is refused. Browsers always
            # send it on an unsafe cross-origin request, so the attack is
            # caught; a request with none is not a browser and therefore not
            # the CSRF threat model.
            if origin is not None and origin != request.host_url.rstrip("/"):
                return jsonify({"error": "bad origin"}), 403
        return None
```

- [ ] **Step 4: Run the auth tests to verify they pass**

Run: `python3 -m pytest tests/test_client_auth.py -q`
Expected: PASS. The enumeration tests (`test_every_client_route_is_classified` and the three beside it) must still be green.

- [ ] **Step 5: Write the failing CORS test**

Create `tests/test_cors_scope.py`:

```python
"""CORS must not cover the client's private endpoints.

/app and /api/app/* are served from one origin, and a same-origin request
never consults CORS. Leaving those paths outside the rule removes the
supports_credentials decision entirely, rather than requiring someone to
get it right later.
"""
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

ORIGIN = {"Origin": "http://localhost:3000"}


def test_the_legacy_api_still_answers_cross_origin(client):
    r = client.get("/api/indices", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" in r.headers


def test_the_client_api_carries_no_cors_headers(client):
    r = client.get("/api/app/calls", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" not in r.headers


def test_the_gated_client_api_carries_no_cors_headers(client):
    r = client.get("/api/app/positions", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" not in r.headers
```

- [ ] **Step 6: Run it to verify it fails**

Run: `python3 -m pytest tests/test_cors_scope.py -q`
Expected: FAIL on both `/api/app` tests — CORS is currently app-wide, so the header is present.

- [ ] **Step 7: Scope the CORS rule**

Replace line 53 of `prototype/app.py`:

```python
# CORS covers the legacy /api/* surface, which has external consumers.
# /api/app/* is deliberately excluded: the dashboard fetches it from the same
# origin that served /app, so it needs no CORS headers -- and excluding it
# means supports_credentials can never make localhost a credentialed wildcard
# over a client's private book.
CORS(app, resources={r"/api/(?!app/).*": {
    "origins": ["http://localhost:*", "http://127.0.0.1:*",
                "https://tradepilot.onrender.com"]}})
```

- [ ] **Step 8: Run both test files to verify they pass**

Run: `python3 -m pytest tests/test_cors_scope.py tests/test_client_auth.py -q`
Expected: PASS.

If the negative-lookahead pattern does not match the way flask-cors dispatches, the tests above are the contract — adjust the resource pattern until all three pass, and report what you changed.

- [ ] **Step 9: Run the whole suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS. Report the count. Any failure here is a real regression in a neighbouring test that assumed the stub — fix it by signing in, never by weakening an assertion.

- [ ] **Step 10: Commit**

```bash
git add prototype/client_auth.py prototype/app.py tests/test_client_auth.py tests/test_cors_scope.py
git commit -m "feat(auth): real sessions behind current_user, and scope CORS

current_user() now resolves the tp_session cookie through one indexed
read. The guard additionally refuses an unsafe method whose Origin is
present and foreign.

CORS is scoped off /api/app/* entirely rather than configured: those
paths are same-origin, so the supports_credentials hazard the dashboard
spec recorded can no longer be introduced."
```

---

### Task 4: The login page

**Files:**
- Create: `prototype/accounts_web.py`
- Create: `prototype/templates/login.html`
- Modify: `prototype/app.py` (register the blueprint, beside the existing client wiring at lines 56-60)
- Test: `tests/test_accounts_web.py`

**Interfaces:**
- Consumes: `accounts.check_login`, `accounts.create_session`, `accounts.revoke_session`, `client_auth.COOKIE_NAME`, `client_auth.open_store`
- Produces:
  - blueprint `accounts_web.bp` with `GET`/`POST /app/login` and `POST /app/logout`
  - `accounts_web.safe_next(target) -> str` (a local path, or `"/app"`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_accounts_web.py`:

```python
"""Signing in.

The open-redirect test is not a formality. A login page that redirects
anywhere is a phishing primitive: the attacker sends a link to the real
site, the victim signs in for real, and the redirect lands them on a copy
that asks again.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, accounts_web, app_store, client_auth


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / "web.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_auth, "open_store", lambda: app_store.get_db(path))
    monkeypatch.setattr(accounts_web, "open_store", lambda: app_store.get_db(path))
    accounts.create_user(conn, "priya@example.com", "correct horse")
    yield conn
    conn.close()


def test_the_login_page_renders(client, store):
    r = client.get("/app/login")
    assert r.status_code == 200
    assert b"password" in r.data.lower()


def test_the_login_page_contains_no_javascript(client, store):
    body = client.get("/app/login").get_data(as_text=True).lower()
    assert "<script" not in body


def test_signing_in_sets_a_session_cookie_and_redirects(client, store):
    r = client.post("/app/login",
                    data={"email": "priya@example.com", "password": "correct horse"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/app")
    assert client_auth.COOKIE_NAME in r.headers.get("Set-Cookie", "")


def test_the_cookie_is_httponly_and_samesite(client, store):
    r = client.post("/app/login",
                    data={"email": "priya@example.com", "password": "correct horse"})
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_a_wrong_password_does_not_sign_you_in(client, store):
    r = client.post("/app/login",
                    data={"email": "priya@example.com", "password": "wrong"})
    assert client_auth.COOKIE_NAME not in r.headers.get("Set-Cookie", "")


def test_the_refusal_is_identical_for_an_unknown_email(client, store):
    wrong = client.post("/app/login", data={"email": "priya@example.com",
                                            "password": "wrong"}).get_data(as_text=True)
    unknown = client.post("/app/login", data={"email": "nobody@example.com",
                                              "password": "wrong"}).get_data(as_text=True)
    assert wrong == unknown


def test_signing_in_then_reaching_the_book(client, store):
    client.post("/app/login",
                data={"email": "priya@example.com", "password": "correct horse"})
    assert client.get("/api/app/me").status_code == 200


def test_logging_out_revokes_the_session(client, store):
    client.post("/app/login",
                data={"email": "priya@example.com", "password": "correct horse"})
    client.post("/app/logout")
    assert client.get("/api/app/me").status_code == 401


@pytest.mark.parametrize("target", [
    "https://evil.example.com/phish",
    "//evil.example.com/phish",
    "http://evil.example.com",
    "\\\\evil.example.com",
])
def test_next_cannot_send_you_off_site(target):
    assert accounts_web.safe_next(target) == "/app"


@pytest.mark.parametrize("target", ["/app", "/app#book", "/app/login"])
def test_a_local_next_is_kept(target):
    assert accounts_web.safe_next(target) == target


def test_next_is_honoured_after_signing_in(client, store):
    r = client.post("/app/login?next=/app%23book",
                    data={"email": "priya@example.com", "password": "correct horse"})
    assert r.headers["Location"].endswith("/app#book")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_accounts_web.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prototype.accounts_web'`

- [ ] **Step 3: Write the blueprint**

Create `prototype/accounts_web.py`:

```python
"""Sign in and sign out.

Server-rendered on purpose. A real form POST means browser password managers
work, and credentials never pass through the fetch layer -- api.js does not
know this page exists.
"""
from flask import (Blueprint, make_response, redirect, render_template,
                   request, url_for)

from prototype import accounts, app_store, client_auth

bp = Blueprint("accounts_web", __name__)

REFUSAL = "That email and password did not match."


def open_store():
    """Open the store. A named function so tests can point at a throwaway file."""
    return app_store.get_db()


def safe_next(target):
    """A local path to redirect to after signing in, or /app.

    Anything that could leave this site is discarded. A protocol-relative
    "//evil.example.com" is a URL, not a path, which is why checking only for
    a leading slash is not enough.
    """
    if not target:
        return "/app"
    if not target.startswith("/"):
        return "/app"
    if target.startswith("//") or target.startswith("/\\"):
        return "/app"
    if "\\" in target or ":" in target:
        return "/app"
    return target


@bp.route("/app/login", methods=["GET", "POST"])
def login():
    nxt = safe_next(request.args.get("next"))
    if request.method == "GET":
        return render_template("login.html", error=None, next=nxt)

    conn = open_store()
    try:
        uid = accounts.check_login(conn, request.form.get("email", ""),
                                   request.form.get("password", ""))
        if uid is None:
            # One message for every failure. See accounts.check_login.
            return render_template("login.html", error=REFUSAL, next=nxt), 401
        token = accounts.create_session(conn, uid)
    finally:
        conn.close()

    resp = make_response(redirect(nxt))
    resp.set_cookie(client_auth.COOKIE_NAME, token,
                    httponly=True, samesite="Lax", path="/",
                    secure=request.is_secure,
                    max_age=accounts.SESSION_SLIDING_DAYS * 24 * 3600)
    return resp


@bp.route("/app/logout", methods=["POST"])
def logout():
    token = request.cookies.get(client_auth.COOKIE_NAME)
    conn = open_store()
    try:
        accounts.revoke_session(conn, token)
    finally:
        conn.close()
    resp = make_response(redirect(url_for("client_app")))
    resp.delete_cookie(client_auth.COOKIE_NAME, path="/")
    return resp
```

`secure=request.is_secure` is deliberate: setting `Secure` unconditionally makes sign-in fail silently on local HTTP — the cookie is sent, the browser discards it, and the only symptom is a login that appears to work and lands you signed out.

- [ ] **Step 4: Write the template**

Create `prototype/templates/login.html`:

```html
<!doctype html>
<meta charset="utf-8">
<title>Sign in — TradePilot</title>
<link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
<div class="content" style="max-width:24rem;margin:4rem auto">
  <h1>Sign in</h1>
  {% if error %}<div class="empty">{{ error }}</div>{% endif %}
  <form method="post" action="/app/login?next={{ next|urlencode }}">
    <label for="email">Email</label>
    <input id="email" name="email" type="email" autocomplete="username" required>
    <label for="password">Password</label>
    <input id="password" name="password" type="password"
           autocomplete="current-password" required>
    <button type="submit">Sign in</button>
  </form>
</div>
```

- [ ] **Step 5: Register the blueprint**

In `prototype/app.py`, beside the existing client wiring at lines 56-60, add one line after `app.register_blueprint(_client_api_bp)`:

```python
from prototype.accounts_web import bp as _accounts_web_bp  # noqa: E402
app.register_blueprint(_accounts_web_bp)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_accounts_web.py -q`
Expected: PASS, 16 tests (the two parametrised cases expand to 4 and 3).

- [ ] **Step 7: Prove the open-redirect test binds**

Change `safe_next` to `return target or "/app"`, run the tests, and confirm every `test_next_cannot_send_you_off_site` case goes RED. Restore and confirm GREEN. Report both observations.

- [ ] **Step 8: Commit**

```bash
git add prototype/accounts_web.py prototype/templates/login.html prototype/app.py tests/test_accounts_web.py
git commit -m "feat(auth): server-rendered sign-in and sign-out

Real form POST, so password managers work and credentials never touch
the fetch layer. ?next= is validated as a local path -- an open redirect
on a login page is a phishing primitive."
```

---

### Task 5: Creating an account from the terminal

**Files:**
- Create: `scripts/add-client.py`
- Test: `tests/test_add_client.py`

**Interfaces:**
- Consumes: `accounts.create_user(conn, email, password) -> str`, `app_store.get_db`, `app_store.init_db`
- Produces: `add_client.main(argv, prompt) -> int` (a process exit code; `prompt` is injected so tests never touch a terminal)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_add_client.py`:

```python
"""Creating an account from the terminal.

The password is read with getpass, never taken as an argument -- a password
on the command line lands in shell history and in the process list, where
any other user on the machine can read it.
"""
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, app_store

_spec = importlib.util.spec_from_file_location(
    "add_client", os.path.join(REPO_ROOT, "scripts", "add-client.py"))
add_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(add_client)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "add.db")
    monkeypatch.setattr(add_client, "open_store", lambda: app_store.get_db(path))
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    yield conn
    conn.close()


def test_it_creates_an_account(db, capsys):
    code = add_client.main(["priya@example.com"], prompt=lambda _: "correct horse")
    assert code == 0
    assert accounts.check_login(db, "priya@example.com", "correct horse")


def test_it_refuses_a_duplicate_rather_than_resetting_a_live_password(db, capsys):
    add_client.main(["priya@example.com"], prompt=lambda _: "correct horse")
    code = add_client.main(["priya@example.com"], prompt=lambda _: "new password")
    assert code != 0
    # The original password still works -- the second run changed nothing.
    assert accounts.check_login(db, "priya@example.com", "correct horse")


def test_it_refuses_when_the_two_entries_differ(db):
    answers = iter(["correct horse", "different"])
    code = add_client.main(["priya@example.com"], prompt=lambda _: next(answers))
    assert code != 0
    assert accounts.check_login(db, "priya@example.com", "correct horse") is None


def test_it_refuses_an_empty_password(db):
    code = add_client.main(["priya@example.com"], prompt=lambda _: "")
    assert code != 0


def test_it_requires_an_email(db):
    assert add_client.main([], prompt=lambda _: "correct horse") != 0


def test_the_password_never_appears_in_the_output(db, capsys):
    add_client.main(["priya@example.com"], prompt=lambda _: "correct horse")
    out = capsys.readouterr()
    assert "correct horse" not in out.out
    assert "correct horse" not in out.err
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_add_client.py -q`
Expected: FAIL — the script file does not exist.

- [ ] **Step 3: Write the script**

Create `scripts/add-client.py`:

```python
#!/usr/bin/env python3
"""Create a client account.

    $ python3 scripts/add-client.py priya@example.com
    Password: (not echoed)
    Confirm:  (not echoed)
    created user u-8f21c4

The password is prompted for, never passed as an argument: an argument
lands in shell history and in the process list.

This is the only account-creation path in B1. Self-serve signup is B2.
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prototype import accounts, app_store  # noqa: E402


def open_store():
    """Open the store. A named function so tests can point at a throwaway file."""
    conn = app_store.get_db()
    app_store.init_db(conn)
    return conn


def main(argv, prompt=getpass.getpass):
    if len(argv) != 1:
        print("usage: add-client.py <email>", file=sys.stderr)
        return 2
    email = argv[0]

    password = prompt("Password: ")
    if not password:
        print("password must not be empty", file=sys.stderr)
        return 2
    if prompt("Confirm:  ") != password:
        print("those did not match", file=sys.stderr)
        return 2

    conn = open_store()
    try:
        uid = accounts.create_user(conn, email, password)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    finally:
        conn.close()

    print("created user " + uid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_add_client.py -q`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/add-client.py tests/test_add_client.py
git commit -m "feat(accounts): add-client.py creates an account

Password via getpass, never an argument. Refuses a duplicate rather
than silently resetting a live account's password."
```

---

### Task 6: The shell knows who you are

Populates the `#who` element the dashboard review flagged as dead, using `/api/app/me` — the one endpoint no screen consumed. Then updates the manual checklist, whose signed-out procedure is now obsolete.

**Files:**
- Modify: `prototype/static/app/api.js` (add `me`)
- Modify: `prototype/static/app/main.js` (populate `#who` at boot)
- Modify: `prototype/static/app.css` (one rule for the sign-out button)
- Modify: `docs/APP_MANUAL_CHECKS.md`
- Test: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `GET /api/app/me` returning `{"user_id": ..., "plan": ...}` or 401; `TPApi` (the object in `api.js`); `TPApp.boot`
- Produces: nothing other tasks consume

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_screens.py`:

```python
def test_the_api_client_can_ask_who_is_signed_in(client):
    js = client.get("/static/app/api.js").get_data(as_text=True)
    assert "/api/app/me" in js


def test_the_shell_fills_the_who_element(client):
    js = client.get("/static/app/main.js").get_data(as_text=True)
    assert "\"who\"" in js or "'who'" in js


def test_the_shell_offers_a_way_in_and_a_way_out(client):
    js = client.get("/static/app/main.js").get_data(as_text=True)
    assert "/app/login" in js
    assert "/app/logout" in js
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_app_screens.py -q`
Expected: FAIL on all three.

- [ ] **Step 3: Add `me` to the API client**

In `prototype/static/app/api.js`, alongside the existing methods:

```javascript
me: function () { return get("/api/app/me"); },
```

Use whatever the file's existing internal helper is named — read it first. Do not introduce a second `fetch` call site.

- [ ] **Step 4: Populate `#who` at boot**

In `prototype/static/app/main.js`, add this function and call it from `boot`:

```javascript
function loadWho() {
  var node = el("who");
  if (!node) return;
  window.TPApi.me().then(function (m) {
    node.innerHTML = "";
    var name = window.TPScreens.el("span", "thin", m.user_id);
    var out = document.createElement("form");
    out.method = "post";
    out.action = "/app/logout";
    out.style.display = "inline";
    var b = document.createElement("button");
    b.type = "submit";
    b.className = "who-out";
    b.textContent = "Sign out";
    out.appendChild(b);
    node.appendChild(name);
    node.appendChild(out);
  }, function () {
    /* 401 is the ordinary signed-out case, not an error worth shouting about.
       Anything else lands here too, and the honest rendering is the same:
       offer the way in, claim nothing about who they are. */
    node.innerHTML = "";
    var a = document.createElement("a");
    a.href = "/app/login";
    a.textContent = "Sign in";
    node.appendChild(a);
  });
}
```

Sign-out is a form POST, not a link: a `GET /app/logout` could be triggered by any image tag on any page.

`app.css` has a `.who` rule but nothing for a button inside it, so add one — otherwise Sign out renders as a chunky default button in a 12px text header:

```css
.who-out {
  background: none; border: 0; padding: 0 0 0 0.5rem;
  font: inherit; color: var(--accent); cursor: pointer;
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_app_screens.py -q`
Expected: PASS.

- [ ] **Step 6: Verify ES5 and the single fetch site**

Run:

```bash
grep -nE "=>|\bconst \b|\blet \b|\`" prototype/static/app/main.js prototype/static/app/api.js
grep -rln "fetch(" prototype/static/app/
```

Expected: the first prints nothing outside comments; the second prints only `api.js`.

- [ ] **Step 7: Replace the obsolete section of the manual checklist**

In `docs/APP_MANUAL_CHECKS.md`, delete the procedure that instructs the reader to edit `prototype/client_auth.py` and revert it, including its bold warning. Replace it with:

```markdown
### Signing out

Click **Sign out** in the header. To sign back in, use the **Sign in** link,
or go to `/app/login` directly.

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | The header shows your email and a Sign out control when signed in |
| ☐ | The header shows a Sign in link when signed out |
| ☐ | After signing out, the Book reads "Sign in to see your book" and the link reaches `/app/login` |
| ☐ | Home and Calls still render fully when signed out -- they are public |
| ☐ | Signing in from `/app/login` returns you to `/app`, still signed in after a reload |
| ☐ | A wrong password says the same thing as an unknown email |

:::
```

Check the rest of the file for any other reference to editing `client_auth.py` and remove those too. A checklist that still tells a reader to modify source will be followed by someone who does not know it is obsolete.

- [ ] **Step 8: Run the whole suite**

Run: `python3 -m pytest tests/ -q` and `node --test "tests/js/*.test.js"`

Expected: both pass. Report both counts. Note that `node --test tests/js/` (with a trailing directory rather than the glob) fails with `MODULE_NOT_FOUND` on Node 22 and is not a real failure — use the quoted glob.

- [ ] **Step 9: Commit**

```bash
git add prototype/static/app/api.js prototype/static/app/main.js prototype/static/app.css docs/APP_MANUAL_CHECKS.md tests/test_app_screens.py
git commit -m "feat(app): the shell shows who is signed in

Populates #who, which the dashboard review found was never filled, using
/api/app/me, which was the one endpoint no screen consumed -- each was
the other's answer.

Sign-out is a form POST: a GET could be triggered by any image tag on
any page. The manual checklist's edit-the-source procedure for reaching
a signed-out screen is replaced by clicking Sign out."
```

---

## What this plan does not do

Self-serve signup, email verification, password reset, and the mail provider they depend on are **project B2**. Per-user Kite tokens, a closed-positions view and the `/classic` redirect are later still.

**The SEBI Research Analyst / Investment Adviser position remains a deploy gate.** Authentication does not change it; it only makes the audience easier to grow.
