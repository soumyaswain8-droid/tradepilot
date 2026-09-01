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

