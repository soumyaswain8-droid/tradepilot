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

