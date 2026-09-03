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

