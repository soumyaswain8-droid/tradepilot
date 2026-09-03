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
