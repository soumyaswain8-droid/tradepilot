### Task 1: Token storage

**Files:**
- Modify: `prototype/app_store.py` (the `SCHEMA` string)
- Modify: `prototype/accounts.py`
- Test: `tests/test_auth_tokens.py`

**Interfaces:**
- Consumes: `accounts._hash_token`, `accounts._now`, `accounts._iso`, `accounts._parse`
- Produces:
  - `accounts.INVITE_HOURS = 72`, `accounts.RESET_HOURS = 1`
  - `accounts.issue_token(conn, purpose, email, hours) -> str` (the raw token)
  - `accounts.peek_token(conn, token) -> str | None` (the purpose if live; read-only)
  - `accounts.consume_token(conn, token) -> tuple` (`(purpose, email)` or `(None, None)`)

- [ ] **Step 1: Add both tables to the schema**

Append to the `SCHEMA` string in `prototype/app_store.py`, after the existing `sessions` index:

```sql
CREATE TABLE IF NOT EXISTS waitlist (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL,
    requested_at  TEXT NOT NULL,
    approved_at   TEXT,
    user_id       TEXT REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS ix_waitlist_pending
    ON waitlist (approved_at, requested_at);

CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash  TEXT PRIMARY KEY,
    purpose     TEXT NOT NULL,
    email       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT
);

CREATE INDEX IF NOT EXISTS ix_auth_tokens_email
    ON auth_tokens (email, purpose);
```

There is deliberately no unique index on `waitlist.email` — duplicates are accepted, and a person submitting twice appears twice.

- [ ] **Step 2: Write the failing tests**

Create `tests/test_auth_tokens.py`:

```python
"""Invite and reset links.

A link is single-use, time-limited, and stored only as a digest. The
single-use property is claimed by the UPDATE that checks it -- a read
followed by a write can let two nearly simultaneous clicks both succeed,
and mail clients that prefetch links make that real rather than theoretical.
"""
import os
import sys
from datetime import timedelta

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, app_store


@pytest.fixture
def conn(tmp_path):
    c = app_store.get_db(str(tmp_path / "tokens.db"))
    app_store.init_db(c)
    yield c
    c.close()


def test_issuing_returns_a_token(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com",
                                 accounts.INVITE_HOURS)
    assert token
    assert len(token) > 20


def test_the_raw_token_is_never_stored(conn):
    import hashlib
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    stored = conn.execute("SELECT token_hash FROM auth_tokens").fetchone()[0]
    assert token not in stored
    assert stored == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_peek_reports_the_purpose_without_consuming(conn):
    token = accounts.issue_token(conn, "reset", "priya@example.com", 1)
    assert accounts.peek_token(conn, token) == "reset"
    # Still usable afterwards -- peeking must not spend the link.
    assert accounts.consume_token(conn, token) == ("reset", "priya@example.com")


def test_consuming_returns_the_purpose_and_email(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    assert accounts.consume_token(conn, token) == ("invite", "priya@example.com")


def test_a_token_can_only_be_consumed_once(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    first = accounts.consume_token(conn, token)
    second = accounts.consume_token(conn, token)
    assert first == ("invite", "priya@example.com")
    assert second == (None, None)


def test_a_used_token_no_longer_peeks(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    accounts.consume_token(conn, token)
    assert accounts.peek_token(conn, token) is None


def test_an_expired_token_is_refused(conn):
    token = accounts.issue_token(conn, "reset", "priya@example.com", 1)
    conn.execute("UPDATE auth_tokens SET expires_at = '2020-01-01T00:00:00.000000+00:00'")
    conn.commit()
    assert accounts.peek_token(conn, token) is None
    assert accounts.consume_token(conn, token) == (None, None)


def test_an_unknown_token_is_refused(conn):
    accounts.issue_token(conn, "invite", "priya@example.com", 72)
    assert accounts.consume_token(conn, "not-a-real-token") == (None, None)
    assert accounts.peek_token(conn, "not-a-real-token") is None


def test_an_empty_token_is_refused(conn):
    assert accounts.consume_token(conn, "") == (None, None)
    assert accounts.consume_token(conn, None) == (None, None)
    assert accounts.peek_token(conn, "") is None


def test_two_tokens_for_one_address_are_independent(conn):
    a = accounts.issue_token(conn, "reset", "priya@example.com", 1)
    b = accounts.issue_token(conn, "reset", "priya@example.com", 1)
    accounts.consume_token(conn, a)
    assert accounts.consume_token(conn, b) == ("reset", "priya@example.com")


def test_the_expiry_honours_the_hours_given(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    row = conn.execute("SELECT created_at, expires_at FROM auth_tokens").fetchone()
    span = accounts._parse(row["expires_at"]) - accounts._parse(row["created_at"])
    assert timedelta(hours=71) < span < timedelta(hours=73)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_auth_tokens.py -q`
Expected: FAIL — `AttributeError: module 'prototype.accounts' has no attribute 'issue_token'`

- [ ] **Step 4: Write the token functions**

Append to `prototype/accounts.py`:

```python
INVITE_HOURS = 72
RESET_HOURS = 1


def issue_token(conn, purpose, email, hours):
    """Create a single-use link token. Returns the raw value for the email."""
    token = secrets.token_urlsafe(32)
    now = _now()
    conn.execute(
        "INSERT INTO auth_tokens (token_hash, purpose, email, created_at, expires_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (_hash_token(token), purpose, email, _iso(now),
         _iso(now + timedelta(hours=hours))))
    conn.commit()
    return token


def peek_token(conn, token):
    """The purpose of a live token, or None. Read-only -- does not spend it."""
    if not token:
        return None
    row = conn.execute(
        "SELECT purpose FROM auth_tokens "
        "WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
        (_hash_token(token), _iso(_now()))).fetchone()
    return row["purpose"] if row else None


def consume_token(conn, token):
    """Spend a token. Returns (purpose, email), or (None, None).

    The check and the claim are one statement on purpose. Reading the row,
    testing used_at, and then updating lets two nearly simultaneous requests
    both pass the test before either writes -- and double-clicks happen, as
    does link prefetching by mail clients. Zero rows affected means the token
    was already used, has expired, or never existed; all three are refused
    identically.
    """
    if not token:
        return (None, None)
    digest = _hash_token(token)
    now = _iso(_now())
    cur = conn.execute(
        "UPDATE auth_tokens SET used_at = ? "
        "WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
        (now, digest, now))
    conn.commit()
    if cur.rowcount != 1:
        return (None, None)
    row = conn.execute(
        "SELECT purpose, email FROM auth_tokens WHERE token_hash = ?",
        (digest,)).fetchone()
    return (row["purpose"], row["email"])
```

Add `from datetime import timedelta` to the existing datetime import if it is not already there — Task 2 of the previous project imported it, so check before adding a duplicate.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_auth_tokens.py -q`
Expected: PASS, 11 tests.

- [ ] **Step 6: Prove single-use binds**

Remove `AND used_at IS NULL` from `consume_token`'s UPDATE. Run the tests and confirm `test_a_token_can_only_be_consumed_once` goes RED. Restore it and confirm GREEN. Report both output lines.

Be precise about what this proves: the sequential test proves the link is single-use. It does not prove atomicity — that needs true concurrency, which SQLite in one process will not exhibit. The atomic UPDATE is what makes single-use hold when two requests arrive together, and the reason the plan specifies it rather than a read-then-write. Say so in your report rather than claiming the test covers the race.

- [ ] **Step 7: Commit**

```bash
git add prototype/app_store.py prototype/accounts.py tests/test_auth_tokens.py
git commit -m "feat(accounts): single-use, time-limited link tokens

One table serves invites and resets. The used_at check lives inside the
UPDATE that claims it, so two simultaneous clicks cannot both succeed."
```

---

