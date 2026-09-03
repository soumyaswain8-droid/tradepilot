# Accounts Front Door Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give people a way in — a public waitlist, a CLI to approve from it, an invite that turns approval into an account, and password reset.

**Architecture:** One `auth_tokens` table serves both the invite link and the reset link, distinguished by `purpose`. Clicking an invite both proves control of the address and is where the password is chosen, so there is no separate verification step and no account until the link is used. A `mailer` module takes an injectable transport so tests never open a socket.

**Tech Stack:** Flask 3.1.1, Jinja, stdlib `sqlite3` / `secrets` / `hashlib` / `smtplib` / `email.message`, `werkzeug.security` for hashing. No new dependencies. No JavaScript on any page this plan adds.

**Spec:** `docs/superpowers/specs/2026-09-03-accounts-signup-design.md`

## Global Constraints

- No new dependencies. `requirements.txt` must be byte-identical at the end of this plan.
- All DDL uses `IF NOT EXISTS`, in `prototype/app_store.py`'s `SCHEMA` string.
- Never store a raw token — session, invite or reset. Hash through `accounts._hash_token`; never reimplement that transformation.
- Every POST route added here calls `client_auth.foreign_origin()` and returns 403 when it is true.
- `/app/signup` and `/app/forgot` return an identical response whether the address is unknown, already waitlisted, or already has an account.
- Server-rendered Jinja only. No JavaScript on these pages. `fetch` stays confined to `prototype/static/app/api.js`.
- Invite tokens live 72 hours; reset tokens live 1 hour.
- Do not run build commands. The `pytest` invocations in each task are required and are the exception.
- Port 5050 belongs to a separate running process. Use 5051 or above, and kill only what you start.
- `node --test tests/js/` fails with `MODULE_NOT_FOUND` on Node 22 — use `node --test "tests/js/*.test.js"`.

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `prototype/app_store.py` | modify | `SCHEMA` gains `waitlist` and `auth_tokens` |
| `prototype/accounts.py` | modify | token issue/peek/consume; `set_password`; `revoke_all_sessions` |
| `prototype/mailer.py` | create | SMTP send with an injectable transport; no Flask import |
| `prototype/accounts_web.py` | modify | `/app/signup`, `/app/forgot`, `/app/set-password` |
| `prototype/templates/signup.html` | create | one email field |
| `prototype/templates/forgot.html` | create | one email field |
| `prototype/templates/set-password.html` | create | password field, or the link-expired message |
| `scripts/waitlist.py` | create | `list` and `approve` |
| `tests/test_auth_tokens.py` | create | token lifecycle |
| `tests/test_mailer.py` | create | message shape, unconfigured behaviour |
| `tests/test_signup_web.py` | create | the three routes |
| `tests/test_waitlist_cli.py` | create | the CLI |

`prototype/mailer.py` imports no Flask, matching `accounts.py` — it takes values and a transport, so it is testable without a request context.

---

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

### Task 3: The mailer

**Files:**
- Create: `prototype/mailer.py`
- Test: `tests/test_mailer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `mailer.send(to, subject, body, transport=None) -> None`
  - `mailer.FROM_ADDRESS = "soumya@sidewall.in"`
  - `mailer.SMTP_HOST = "smtp.gmail.com"`, `mailer.SMTP_PORT = 587`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mailer.py`:

```python
"""Sending mail.

The transport is injected so tests never open a socket. Testing by mocking
smtplib's internals would couple these tests to the standard library's shape
rather than to the message we send.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import mailer


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "soumya@sidewall.in")
    monkeypatch.setenv("SMTP_PASS", "an-app-password")


def recorder():
    sent = []

    def transport(host, port, user, password, msg):
        sent.append({"host": host, "port": port, "user": user,
                     "password": password, "msg": msg})
    return sent, transport


def test_it_sends_to_the_right_recipient(creds):
    sent, transport = recorder()
    mailer.send("priya@example.com", "Your invite", "Body here",
                transport=transport)
    assert len(sent) == 1
    assert sent[0]["msg"]["To"] == "priya@example.com"


def test_the_message_carries_the_subject_and_body(creds):
    sent, transport = recorder()
    mailer.send("priya@example.com", "Your invite", "Click this link",
                transport=transport)
    msg = sent[0]["msg"]
    assert msg["Subject"] == "Your invite"
    assert "Click this link" in msg.get_content()


def test_it_sends_from_the_configured_address(creds):
    sent, transport = recorder()
    mailer.send("priya@example.com", "s", "b", transport=transport)
    assert sent[0]["msg"]["From"] == mailer.FROM_ADDRESS


def test_it_uses_the_workspace_smtp_endpoint(creds):
    sent, transport = recorder()
    mailer.send("priya@example.com", "s", "b", transport=transport)
    assert sent[0]["host"] == "smtp.gmail.com"
    assert sent[0]["port"] == 587


def test_sending_without_credentials_raises(monkeypatch):
    """A mailer that silently does nothing when unconfigured is how a
    deployment discovers weeks later that no invite ever arrived."""
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    _, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)


def test_a_missing_password_alone_also_raises(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "soumya@sidewall.in")
    monkeypatch.delenv("SMTP_PASS", raising=False)
    _, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)


def test_nothing_is_sent_when_credentials_are_missing(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    sent, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)
    assert sent == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_mailer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prototype.mailer'`

- [ ] **Step 3: Write the module**

Create `prototype/mailer.py`:

```python
"""Outbound mail.

No Flask import: this takes values and a transport, so it is testable without
a request context and the tests never open a socket.

sidewall.in publishes SPF and a DKIM key at selector `google`. If either stops
resolving, mail still sends and silently lands in spam, because the domain's
DMARC policy is p=quarantine. Run scripts/check-mail-dns.sh sidewall.in to
check that from outside the app -- nothing in here can detect it.
"""
import os
import smtplib
from email.message import EmailMessage

FROM_ADDRESS = "soumya@sidewall.in"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _smtp_transport(host, port, user, password, msg):
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def send(to, subject, body, transport=None):
    """Send one plain-text message. Raises if SMTP is not configured."""
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if not user or not password:
        raise RuntimeError(
            "SMTP_USER and SMTP_PASS must be set to send mail")

    msg = EmailMessage()
    msg["From"] = FROM_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    (transport or _smtp_transport)(SMTP_HOST, SMTP_PORT, user, password, msg)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mailer.py -q`
Expected: PASS, 7 tests.

- [ ] **Step 5: Confirm the sending domain still authenticates**

Run: `./scripts/check-mail-dns.sh sidewall.in`
Expected: exit 0, with SPF, DKIM and MX all OK.

The spec makes this B2's gate for a reason. `sidewall.in` publishes DMARC
`p=quarantine`, so if SPF or the DKIM key ever stops resolving, mail still
sends successfully and silently lands in spam. Nothing inside the application
can detect that — the SMTP call returns success either way. If this exits
non-zero, stop and report it: the mailer is correct but undeliverable, and
building the rest of B2 on top would produce a signup flow that appears to
work and reaches nobody.

- [ ] **Step 6: Confirm nothing opens a socket**

Run the whole suite with networking unavailable to prove the seam holds:

```bash
python3 -m pytest tests/ -q
```

Then read `tests/test_mailer.py` and confirm every test passes a `transport=` argument. Report whether any test path could reach `_smtp_transport`. A test that accidentally used the real transport would hang on connect rather than fail cleanly, so this is worth checking by eye rather than inferring from a green run.

- [ ] **Step 7: Commit**

```bash
git add prototype/mailer.py tests/test_mailer.py
git commit -m "feat(mail): stdlib SMTP with an injectable transport

Raises when SMTP_USER or SMTP_PASS is unset. A mailer that no-ops when
unconfigured is how you find out weeks later that no invite ever arrived."
```

---

### Task 4: Signup and forgot

**Files:**
- Modify: `prototype/accounts_web.py`
- Create: `prototype/templates/signup.html`, `prototype/templates/forgot.html`
- Test: `tests/test_signup_web.py`

**Interfaces:**
- Consumes: `accounts.issue_token`, `accounts.RESET_HOURS`, `mailer.send`, `client_auth.foreign_origin`, `accounts_web.open_store`
- Produces:
  - routes `/app/signup` and `/app/forgot`
  - `accounts_web.WAITLIST_ACK` and `accounts_web.FORGOT_ACK` — the strings each form shows on success
  - `accounts_web.reset_body(token)` — the reset email body
  - `accounts_web.send_mail(to, subject, body)` — the seam tests replace

Task 6's CLI does NOT reuse `reset_body`. That function builds its link from
`request.host_url`, which needs a request context a CLI does not have, so the
script builds its own from a `TRADEPILOT_URL` environment variable. Two similar
strings in two places is correct here; sharing one would drag Flask into the
script.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_signup_web.py`:

```python
"""The public forms.

Both take an email address, and both must answer identically whether that
address is unknown, already waitlisted, or already has an account. Anything
else turns either form into an account enumerator.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, accounts_web, app_store, client_api, client_auth


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / "web.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    for mod in (client_auth, accounts_web, client_api):
        monkeypatch.setattr(mod, "open_store", lambda: app_store.get_db(path))
    yield conn
    conn.close()


@pytest.fixture
def sent(monkeypatch):
    box = []
    monkeypatch.setattr(accounts_web, "send_mail",
                        lambda to, subject, body: box.append((to, subject, body)))
    return box


def test_the_signup_page_renders(client, store):
    r = client.get("/app/signup")
    assert r.status_code == 200
    assert b"email" in r.data.lower()


def test_signing_up_records_a_waitlist_row(client, store, sent):
    client.post("/app/signup", data={"email": "priya@example.com"})
    rows = store.execute("SELECT email FROM waitlist").fetchall()
    assert [r["email"] for r in rows] == ["priya@example.com"]


def test_signing_up_sends_no_mail(client, store, sent):
    """Joining a list is not an event anyone needs to be emailed about."""
    client.post("/app/signup", data={"email": "priya@example.com"})
    assert sent == []


def test_signup_answers_the_same_for_an_address_that_already_has_an_account(
        client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    known = client.post("/app/signup", data={"email": "priya@example.com"})
    fresh = client.post("/app/signup", data={"email": "nobody@example.com"})
    assert known.get_data(as_text=True) == fresh.get_data(as_text=True)
    assert known.status_code == fresh.status_code


def test_signing_up_twice_is_accepted(client, store, sent):
    client.post("/app/signup", data={"email": "priya@example.com"})
    client.post("/app/signup", data={"email": "priya@example.com"})
    assert store.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 2


def test_signup_from_a_foreign_origin_is_refused(client, store, sent):
    r = client.post("/app/signup", data={"email": "priya@example.com"},
                    headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403
    assert store.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 0


def test_the_forgot_page_renders(client, store):
    assert client.get("/app/forgot").status_code == 200


def test_forgot_mails_a_reset_link_to_a_real_account(client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    client.post("/app/forgot", data={"email": "priya@example.com"})
    assert len(sent) == 1
    to, subject, body = sent[0]
    assert to == "priya@example.com"
    assert "/app/set-password?t=" in body


def test_forgot_issues_a_reset_token(client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    client.post("/app/forgot", data={"email": "priya@example.com"})
    row = store.execute("SELECT purpose FROM auth_tokens").fetchone()
    assert row["purpose"] == "reset"


def test_forgot_sends_nothing_for_an_unknown_address(client, store, sent):
    client.post("/app/forgot", data={"email": "nobody@example.com"})
    assert sent == []
    assert store.execute("SELECT COUNT(*) FROM auth_tokens").fetchone()[0] == 0


def test_forgot_answers_the_same_whether_or_not_the_account_exists(
        client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    known = client.post("/app/forgot", data={"email": "priya@example.com"})
    unknown = client.post("/app/forgot", data={"email": "nobody@example.com"})
    assert known.get_data(as_text=True) == unknown.get_data(as_text=True)
    assert known.status_code == unknown.status_code


def test_forgot_still_answers_normally_when_mail_fails(client, store, monkeypatch):
    """The visitor cannot be told, because telling them would reveal that the
    account exists. The failure is logged server-side instead."""
    accounts.create_user(store, "priya@example.com", "pw")

    def explode(to, subject, body):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(accounts_web, "send_mail", explode)

    r = client.post("/app/forgot", data={"email": "priya@example.com"})
    assert r.status_code == 200
    assert accounts_web.FORGOT_ACK.encode() in r.data


def test_forgot_from_a_foreign_origin_is_refused(client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    r = client.post("/app/forgot", data={"email": "priya@example.com"},
                    headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403
    assert sent == []
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_signup_web.py -q`
Expected: FAIL — 404s, because the routes do not exist.

- [ ] **Step 3: Write the templates**

Create `prototype/templates/signup.html`:

```html
<!doctype html>
<meta charset="utf-8">
<title>Request access — TradePilot</title>
<link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
<div class="content" style="max-width:24rem;margin:4rem auto">
  <h1>Request access</h1>
  {% if done %}
    <div class="empty">{{ ack }}</div>
  {% else %}
    <p class="thin">Leave your email and we will be in touch.</p>
    <form method="post" action="/app/signup">
      <label for="email">Email</label>
      <input id="email" name="email" type="email" autocomplete="email" required>
      <button type="submit">Request access</button>
    </form>
  {% endif %}
</div>
```

Create `prototype/templates/forgot.html` with the same shape, `<h1>Reset your password</h1>`, the explanatory line "If that address has an account, we will email a link.", and `action="/app/forgot"`.

- [ ] **Step 4: Write the routes**

Add to `prototype/accounts_web.py`, after the existing logout route. Add `import secrets` and `from prototype import accounts, app_store, client_auth, mailer` at the top (extend the existing import rather than duplicating it):

```python
WAITLIST_ACK = "Thanks -- we will be in touch."
FORGOT_ACK = "If that address has an account, a reset link is on its way."


def send_mail(to, subject, body):
    """Indirection so tests replace one function instead of the mailer."""
    mailer.send(to, subject, body)


def reset_body(token):
    return ("Someone asked to reset the password on your TradePilot account.\n\n"
            "If that was you, set a new one here -- the link is good for an hour:\n"
            "%s/app/set-password?t=%s\n\n"
            "If it was not you, ignore this. Nothing has changed.\n"
            % (request.host_url.rstrip("/"), token))


@bp.route("/app/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", done=False, ack=WAITLIST_ACK)
    if client_auth.foreign_origin():
        return jsonify({"error": "bad origin"}), 403

    email = (request.form.get("email") or "").strip()
    if email:
        conn = open_store()
        try:
            conn.execute(
                "INSERT INTO waitlist (id, email, requested_at) VALUES (?, ?, ?)",
                ("w-" + secrets.token_hex(4), email, accounts._iso(accounts._now())))
            conn.commit()
        finally:
            conn.close()
    # The same page whether the address is new, repeated, or already an
    # account. Anything else makes this form an account enumerator.
    return render_template("signup.html", done=True, ack=WAITLIST_ACK)


@bp.route("/app/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "GET":
        return render_template("forgot.html", done=False, ack=FORGOT_ACK)
    if client_auth.foreign_origin():
        return jsonify({"error": "bad origin"}), 403

    email = (request.form.get("email") or "").strip()
    if email:
        conn = open_store()
        try:
            row = conn.execute(
                "SELECT id FROM users WHERE lower(email) = lower(?)",
                (email,)).fetchone()
            if row is not None:
                token = accounts.issue_token(conn, "reset", email,
                                             accounts.RESET_HOURS)
                try:
                    send_mail(email, "Reset your TradePilot password",
                              reset_body(token))
                except Exception:
                    # Cannot be surfaced: saying "we could not send it" would
                    # confirm the account exists. Log it and answer normally.
                    current_app.logger.exception("reset mail failed")
        finally:
            conn.close()
    return render_template("forgot.html", done=True, ack=FORGOT_ACK)
```

Add `current_app` to the existing `from flask import (...)` line.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_signup_web.py -q`
Expected: PASS, 13 tests.

- [ ] **Step 6: Prove the identical-response tests bind**

Change `forgot` so the unknown-address branch renders `done=False` instead of `done=True`. Confirm `test_forgot_answers_the_same_whether_or_not_the_account_exists` goes RED. Restore and confirm GREEN. Report both lines.

- [ ] **Step 7: Run the whole suite**

Run: `python3 -m pytest tests/ -q`. Report the count. Any neighbouring failure is a real regression — report it rather than editing the failing test.

- [ ] **Step 8: Commit**

```bash
git add prototype/accounts_web.py prototype/templates/signup.html prototype/templates/forgot.html tests/test_signup_web.py
git commit -m "feat(auth): public waitlist and password-reset request

Both forms answer identically whatever is known about the address, and
both refuse a foreign Origin. A failed reset send is logged, never shown,
because showing it would confirm the account exists."
```

---

### Task 5: Setting a password

**Files:**
- Modify: `prototype/accounts_web.py`
- Create: `prototype/templates/set-password.html`
- Test: `tests/test_signup_web.py`

**Interfaces:**
- Consumes: `accounts.peek_token`, `accounts.consume_token`, `accounts.create_user`, `accounts.set_password`, `accounts.revoke_all_sessions`, `accounts.create_session`, `client_auth.COOKIE_NAME`, `accounts.SESSION_MAX_DAYS`
- Produces: route `/app/set-password`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_signup_web.py`:

```python
def _invite(store, email="priya@example.com"):
    return accounts.issue_token(store, "invite", email, accounts.INVITE_HOURS)


def test_a_live_invite_renders_the_form(client, store):
    token = _invite(store)
    r = client.get("/app/set-password?t=" + token)
    assert r.status_code == 200
    assert b"password" in r.data.lower()


def test_an_expired_link_says_so_without_revealing_anything(client, store):
    token = _invite(store)
    store.execute("UPDATE auth_tokens SET expires_at = '2020-01-01T00:00:00.000000+00:00'")
    store.commit()
    body = client.get("/app/set-password?t=" + token).get_data(as_text=True)
    unknown = client.get("/app/set-password?t=never-existed").get_data(as_text=True)
    assert body == unknown


def test_completing_an_invite_creates_the_account_and_signs_them_in(client, store):
    token = _invite(store)
    r = client.post("/app/set-password", data={"t": token, "password": "a good one"})
    assert r.status_code == 302
    assert accounts.check_login(store, "priya@example.com", "a good one")
    assert client.get("/api/app/me").status_code == 200


def test_an_invite_link_cannot_be_used_twice(client, store):
    token = _invite(store)
    client.post("/app/set-password", data={"t": token, "password": "a good one"})
    again = client.post("/app/set-password", data={"t": token, "password": "another"})
    assert again.status_code != 302
    assert store.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_a_reset_changes_the_password_and_the_old_one_stops_working(client, store):
    uid = accounts.create_user(store, "priya@example.com", "old password")
    token = accounts.issue_token(store, "reset", "priya@example.com",
                                 accounts.RESET_HOURS)
    client.post("/app/set-password", data={"t": token, "password": "new password"})
    assert accounts.check_login(store, "priya@example.com", "new password") == uid
    assert accounts.check_login(store, "priya@example.com", "old password") is None


def test_a_reset_ends_sessions_that_already_existed(client, store):
    """Re-present the OLD token explicitly. The client's cookie jar has moved
    on, so merely re-requesting would prove nothing about the server."""
    uid = accounts.create_user(store, "priya@example.com", "old password")
    stale = accounts.create_session(store, uid)
    token = accounts.issue_token(store, "reset", "priya@example.com",
                                 accounts.RESET_HOURS)
    client.post("/app/set-password", data={"t": token, "password": "new password"})
    assert accounts.lookup_session(store, stale) is None


def test_the_browser_completing_a_reset_is_left_signed_in(client, store):
    """Revocation must happen BEFORE the new session is issued, or the fresh
    one is deleted along with the old and the user lands back at login."""
    uid = accounts.create_user(store, "priya@example.com", "old password")
    accounts.create_session(store, uid)
    token = accounts.issue_token(store, "reset", "priya@example.com",
                                 accounts.RESET_HOURS)
    client.post("/app/set-password", data={"t": token, "password": "new password"})
    assert client.get("/api/app/me").status_code == 200


def test_set_password_from_a_foreign_origin_is_refused(client, store):
    token = _invite(store)
    r = client.post("/app/set-password",
                    data={"t": token, "password": "a good one"},
                    headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403
    assert store.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_an_empty_password_is_refused(client, store):
    token = _invite(store)
    r = client.post("/app/set-password", data={"t": token, "password": ""})
    assert r.status_code != 302
    assert store.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_signup_web.py -q`
Expected: FAIL — 404 on `/app/set-password`.

- [ ] **Step 3: Write the template**

Create `prototype/templates/set-password.html`:

```html
<!doctype html>
<meta charset="utf-8">
<title>Set your password — TradePilot</title>
<link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
<div class="content" style="max-width:24rem;margin:4rem auto">
  {% if not live %}
    <h1>That link is no longer valid</h1>
    <p class="thin">Links expire after a while and can only be used once.</p>
  {% else %}
    <h1>Set your password</h1>
    {% if error %}<div class="empty">{{ error }}</div>{% endif %}
    <form method="post" action="/app/set-password">
      <input type="hidden" name="t" value="{{ token }}">
      <label for="password">Password</label>
      <input id="password" name="password" type="password"
             autocomplete="new-password" required>
      <button type="submit">Set password and sign in</button>
    </form>
  {% endif %}
</div>
```

The expired page says nothing about whether the token ever existed, which is why the test compares it byte-for-byte against a made-up token's page.

- [ ] **Step 4: Write the route**

Add to `prototype/accounts_web.py`:

```python
@bp.route("/app/set-password", methods=["GET", "POST"])
def set_password():
    token = request.args.get("t") or request.form.get("t") or ""

    if request.method == "GET":
        conn = open_store()
        try:
            live = accounts.peek_token(conn, token) is not None
        finally:
            conn.close()
        return render_template("set-password.html", live=live, token=token,
                               error=None)

    if client_auth.foreign_origin():
        return jsonify({"error": "bad origin"}), 403

    password = request.form.get("password") or ""
    if not password:
        return render_template("set-password.html", live=True, token=token,
                               error="Choose a password."), 400

    conn = open_store()
    try:
        purpose, email = accounts.consume_token(conn, token)
        if purpose is None:
            return render_template("set-password.html", live=False, token="",
                                   error=None), 400

        row = conn.execute("SELECT id FROM users WHERE lower(email) = lower(?)",
                           (email,)).fetchone()
        if row is None:
            uid = accounts.create_user(conn, email, password)
            conn.execute("UPDATE waitlist SET user_id = ? WHERE lower(email) = lower(?)",
                         (uid, email))
            conn.commit()
        else:
            uid = row["id"]
            accounts.set_password(conn, uid, password)
            # Revoke BEFORE issuing, or the new session is deleted with the old.
            accounts.revoke_all_sessions(conn, uid)

        session_token = accounts.create_session(conn, uid)
    finally:
        conn.close()

    resp = make_response(redirect("/app"))
    resp.set_cookie(client_auth.COOKIE_NAME, session_token,
                    httponly=True, samesite="Lax", path="/",
                    secure=request.is_secure,
                    max_age=accounts.SESSION_MAX_DAYS * 24 * 3600)
    return resp
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_signup_web.py -q`
Expected: PASS, 22 tests.

- [ ] **Step 6: Prove the revoke ordering binds**

Move `accounts.revoke_all_sessions(conn, uid)` to AFTER `accounts.create_session(...)`. Confirm `test_the_browser_completing_a_reset_is_left_signed_in` goes RED. Restore and confirm GREEN. Report both lines.

Then separately: comment out the `revoke_all_sessions` call entirely and confirm `test_a_reset_ends_sessions_that_already_existed` goes RED. Restore, confirm GREEN. Report those lines too. Two different failures, two different tests — if either stays green, say so rather than proceeding.

- [ ] **Step 7: Run the whole suite**

Run: `python3 -m pytest tests/ -q` and `node --test "tests/js/*.test.js"`. Report both counts.

- [ ] **Step 8: Commit**

```bash
git add prototype/accounts_web.py prototype/templates/set-password.html tests/test_signup_web.py
git commit -m "feat(auth): set-password completes an invite or a reset

One page for both. A reset revokes every existing session before issuing
the new one -- an attacker's cookie must not outlive the reset that was
meant to lock them out."
```

---

### Task 6: The approval CLI

**Files:**
- Create: `scripts/waitlist.py`
- Test: `tests/test_waitlist_cli.py`

**Interfaces:**
- Consumes: `accounts.issue_token`, `accounts.INVITE_HOURS`, `app_store.get_db`, `app_store.init_db`
- Produces: `waitlist.main(argv, send=..., out=...) -> int`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_waitlist_cli.py`:

```python
"""Approving from the waitlist.

The mail goes out before the row is marked approved. The other order leaves a
row that says approved with no invite in existence and nothing signalling that
anything went wrong -- the operator sees a satisfied list, the client sees
silence.
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
    "waitlist_cli", os.path.join(REPO_ROOT, "scripts", "waitlist.py"))
waitlist = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(waitlist)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "wl.db")
    monkeypatch.setattr(waitlist, "open_store", lambda: app_store.get_db(path))
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    yield conn
    conn.close()


def _wait(conn, email):
    conn.execute("INSERT INTO waitlist (id, email, requested_at) VALUES (?, ?, ?)",
                 ("w-" + email[:4], email, accounts._iso(accounts._now())))
    conn.commit()


def _sink():
    sent = []
    return sent, (lambda to, subject, body: sent.append((to, subject, body)))


def test_list_shows_pending_entries(db, capsys):
    _wait(db, "priya@example.com")
    assert waitlist.main(["list"]) == 0
    assert "priya@example.com" in capsys.readouterr().out


def test_list_hides_already_approved_entries(db, capsys):
    _wait(db, "priya@example.com")
    db.execute("UPDATE waitlist SET approved_at = '2026-09-01T00:00:00.000000+00:00'")
    db.commit()
    waitlist.main(["list"])
    assert "priya@example.com" not in capsys.readouterr().out


def test_approving_sends_an_invite(db):
    _wait(db, "priya@example.com")
    sent, send = _sink()
    assert waitlist.main(["approve", "priya@example.com"], send=send) == 0
    assert len(sent) == 1
    assert sent[0][0] == "priya@example.com"
    assert "/app/set-password?t=" in sent[0][2]


def test_approving_issues_an_invite_token(db):
    _wait(db, "priya@example.com")
    _, send = _sink()
    waitlist.main(["approve", "priya@example.com"], send=send)
    row = db.execute("SELECT purpose FROM auth_tokens").fetchone()
    assert row["purpose"] == "invite"


def test_approving_marks_the_row(db):
    _wait(db, "priya@example.com")
    _, send = _sink()
    waitlist.main(["approve", "priya@example.com"], send=send)
    row = db.execute("SELECT approved_at FROM waitlist").fetchone()
    assert row["approved_at"] is not None


def test_a_failed_send_leaves_the_row_pending(db):
    """Send first, mark second. A row marked approved with no invite in
    existence is invisible to the operator and silent to the client."""
    _wait(db, "priya@example.com")

    def explode(to, subject, body):
        raise RuntimeError("smtp down")

    assert waitlist.main(["approve", "priya@example.com"], send=explode) != 0
    row = db.execute("SELECT approved_at FROM waitlist").fetchone()
    assert row["approved_at"] is None


def test_approving_someone_not_on_the_list_is_refused(db):
    _, send = _sink()
    assert waitlist.main(["approve", "nobody@example.com"], send=send) != 0


def test_approving_an_address_that_already_has_an_account_is_refused(db):
    _wait(db, "priya@example.com")
    accounts.create_user(db, "priya@example.com", "pw")
    sent, send = _sink()
    assert waitlist.main(["approve", "priya@example.com"], send=send) != 0
    assert sent == []


def test_it_requires_a_known_subcommand(db):
    assert waitlist.main([]) != 0
    assert waitlist.main(["frobnicate"]) != 0
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_waitlist_cli.py -q`
Expected: FAIL — the script does not exist.

- [ ] **Step 3: Write the script**

Create `scripts/waitlist.py`:

```python
#!/usr/bin/env python3
"""The waitlist.

    $ python3 scripts/waitlist.py list
    $ python3 scripts/waitlist.py approve priya@example.com

Approving emails a one-time link that both proves the person controls the
address and is where they choose a password. Nothing exists as an account
until that link is used.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prototype import accounts, app_store, mailer  # noqa: E402

BASE_URL = os.environ.get("TRADEPILOT_URL", "https://tradepilot.onrender.com")


def open_store():
    conn = app_store.get_db()
    app_store.init_db(conn)
    return conn


def _default_send(to, subject, body):
    mailer.send(to, subject, body)


def _invite_body(token):
    return ("You have been approved for TradePilot.\n\n"
            "Set your password here -- the link is good for 72 hours:\n"
            "%s/app/set-password?t=%s\n" % (BASE_URL.rstrip("/"), token))


def cmd_list(conn):
    rows = conn.execute(
        "SELECT email, requested_at FROM waitlist "
        "WHERE approved_at IS NULL ORDER BY requested_at").fetchall()
    print("%d waiting" % len(rows))
    for r in rows:
        print("  %-32s %s" % (r["email"], r["requested_at"][:10]))
    return 0


def cmd_approve(conn, email, send):
    row = conn.execute(
        "SELECT id FROM waitlist WHERE lower(email) = lower(?) "
        "AND approved_at IS NULL", (email,)).fetchone()
    if row is None:
        print("%s is not waiting" % email, file=sys.stderr)
        return 1

    existing = conn.execute("SELECT id FROM users WHERE lower(email) = lower(?)",
                            (email,)).fetchone()
    if existing is not None:
        print("%s already has an account" % email, file=sys.stderr)
        return 1

    token = accounts.issue_token(conn, "invite", email, accounts.INVITE_HOURS)
    try:
        send(email, "Your TradePilot invite", _invite_body(token))
    except Exception as e:
        # Marking approved now would leave a satisfied-looking list and a
        # client who never hears anything. Leave it pending.
        print("could not send: %s" % e, file=sys.stderr)
        return 2

    conn.execute("UPDATE waitlist SET approved_at = ? WHERE id = ?",
                 (accounts._iso(accounts._now()), row["id"]))
    conn.commit()
    print("invite sent, expires in %dh" % accounts.INVITE_HOURS)
    return 0


def main(argv, send=_default_send):
    if not argv:
        print("usage: waitlist.py list | approve <email>", file=sys.stderr)
        return 2

    conn = open_store()
    try:
        if argv[0] == "list":
            return cmd_list(conn)
        if argv[0] == "approve":
            if len(argv) != 2:
                print("usage: waitlist.py approve <email>", file=sys.stderr)
                return 2
            return cmd_approve(conn, argv[1], send)
        print("unknown command: %s" % argv[0], file=sys.stderr)
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_waitlist_cli.py -q`
Expected: PASS, 9 tests.

- [ ] **Step 5: Prove the send-before-mark ordering binds**

Move the `UPDATE waitlist SET approved_at` above the `try/except` that sends. Confirm `test_a_failed_send_leaves_the_row_pending` goes RED. Restore and confirm GREEN. Report both lines.

- [ ] **Step 6: Verify the live database is untouched**

Run:

```bash
python3 -c "import sqlite3;print(sqlite3.connect('prototype/tradepilot_app.db').execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall())"
```

Report the tables present. `waitlist` and `auth_tokens` must NOT appear — their absence proves no test reached the real product database through an unpatched seam. If they are there, that is a real defect: report it rather than deleting them.

- [ ] **Step 7: Run everything**

Run: `python3 -m pytest tests/ -q` and `node --test "tests/js/*.test.js"`. Report both counts and confirm `requirements.txt` is unchanged with `git diff --stat requirements.txt`.

- [ ] **Step 8: Commit**

```bash
git add scripts/waitlist.py tests/test_waitlist_cli.py
git commit -m "feat(accounts): waitlist list and approve

Sends the invite before marking the row approved, and exits non-zero
having changed nothing if the send fails."
```

---

## What this plan does not build

No admin web surface and no `is_admin`. No rate limiting on either public form. No decline state — ignoring a row is declining it. No "resend my invite" for the person waiting; re-approval is the operator's, which is what makes the waitlist a gate. No email change and no account deletion.

**The SEBI Research Analyst / Investment Adviser question still gates linking the signup form where the public can find it.** Everything here can be built, tested and merged without settling it — the machinery is inert until the form is reachable and someone is approved. Building it is not the decision; publishing the link is.
