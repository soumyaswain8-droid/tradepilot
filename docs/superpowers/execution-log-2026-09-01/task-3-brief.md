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

