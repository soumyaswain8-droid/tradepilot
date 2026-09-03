### Task 2: Changing a password, and ending sessions

**Files:**
- Modify: `prototype/accounts.py`
- Test: `tests/test_accounts.py`

**Interfaces:**
- Consumes: `accounts.create_user`, `accounts.create_session`, `accounts.lookup_session`, `accounts.check_login`
- Produces:
  - `accounts.set_password(conn, user_id, password) -> None`
  - `accounts.revoke_all_sessions(conn, user_id) -> int` (rows deleted)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_accounts.py`:

```python
def test_setting_a_password_replaces_the_old_one(conn):
    uid = accounts.create_user(conn, "priya@example.com", "old password")
    accounts.set_password(conn, uid, "new password")
    assert accounts.check_login(conn, "priya@example.com", "new password") == uid
    assert accounts.check_login(conn, "priya@example.com", "old password") is None


def test_setting_a_password_stores_a_hash_not_the_password(conn):
    uid = accounts.create_user(conn, "priya@example.com", "old password")
    accounts.set_password(conn, uid, "new password")
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert "new password" not in stored


def test_setting_a_password_clears_a_lockout(conn):
    """Someone locked out is exactly who reaches for a reset link."""
    uid = accounts.create_user(conn, "priya@example.com", "old password")
    for _ in range(accounts.LOCKOUT_THRESHOLD):
        accounts.check_login(conn, "priya@example.com", "wrong")
    accounts.set_password(conn, uid, "new password")
    assert accounts.check_login(conn, "priya@example.com", "new password") == uid


def test_revoking_kills_every_session_for_that_user(conn):
    uid = accounts.create_user(conn, "priya@example.com", "pw")
    a = accounts.create_session(conn, uid)
    b = accounts.create_session(conn, uid)
    assert accounts.revoke_all_sessions(conn, uid) == 2
    assert accounts.lookup_session(conn, a) is None
    assert accounts.lookup_session(conn, b) is None


def test_revoking_leaves_other_users_alone(conn):
    mine = accounts.create_user(conn, "priya@example.com", "pw")
    theirs = accounts.create_user(conn, "rahul@example.com", "pw")
    my_token = accounts.create_session(conn, mine)
    their_token = accounts.create_session(conn, theirs)
    accounts.revoke_all_sessions(conn, mine)
    assert accounts.lookup_session(conn, my_token) is None
    assert accounts.lookup_session(conn, their_token) == theirs


def test_revoking_a_user_with_no_sessions_is_harmless(conn):
    uid = accounts.create_user(conn, "priya@example.com", "pw")
    assert accounts.revoke_all_sessions(conn, uid) == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_accounts.py -q`
Expected: FAIL — `AttributeError: module 'prototype.accounts' has no attribute 'set_password'`

- [ ] **Step 3: Write both functions**

Append to `prototype/accounts.py`:

```python
def set_password(conn, user_id, password):
    """Replace a password, and clear any lockout with it.

    Someone locked out is exactly the person who reaches for a reset link, so
    leaving failed_count at the threshold would let them set a new password
    and still be refused by it.
    """
    conn.execute(
        "UPDATE users SET password_hash = ?, failed_count = 0, locked_until = NULL "
        "WHERE id = ?",
        (generate_password_hash(password), user_id))
    conn.commit()


def revoke_all_sessions(conn, user_id):
    """Delete every session for a user. Returns how many were removed.

    A password reset must end existing sessions. Someone resetting because
    they believe their account is compromised gains nothing if the attacker's
    cookie keeps working for the rest of its ninety days.
    """
    cur = conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    return cur.rowcount
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_accounts.py -q`
Expected: PASS.

- [ ] **Step 5: Prove the lockout-clearing binds**

Remove `failed_count = 0, locked_until = NULL` from `set_password`'s UPDATE. Confirm `test_setting_a_password_clears_a_lockout` goes RED, restore, confirm GREEN. Report both lines.

- [ ] **Step 6: Commit**

```bash
git add prototype/accounts.py tests/test_accounts.py
git commit -m "feat(accounts): set_password and revoke_all_sessions

Reset needs both. Setting a password clears any lockout, because a
locked-out user is exactly who reaches for a reset link."
```

---

