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

