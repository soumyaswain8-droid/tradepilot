### Task 1: The auth seam, the guard, and the enumeration test

This task ships no client data. It ships the boundary every later endpoint lands inside, which is why it comes first.

**Files:**
- Create: `prototype/client_auth.py`
- Create: `prototype/client_api.py` (blueprint + `/api/app/me` only)
- Modify: `prototype/app.py` (register the blueprint)
- Create: `tests/test_client_auth.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `client_auth.current_user()` → `str` user id or `None`. Stub returns `"demo-user"`.
  - `client_auth.PUBLIC_ENDPOINTS` → `frozenset[str]` of blueprint endpoint names, e.g. `{"client_api.calls_list", ...}`.
  - `client_auth.GATED_ENDPOINTS` → `frozenset[str]`.
  - `client_auth.install_guard(app)` → registers a `before_request` that 401s gated endpoints when `current_user()` is `None`.
  - `client_api.bp` → `flask.Blueprint("client_api", __name__, url_prefix="/api/app")`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client_auth.py`:

```python
"""The auth boundary, and the test that keeps it honest.

This app has roughly seventy routes and none of them are protected. The whole
argument for putting client endpoints under one prefix is that protection
becomes a property a test can enumerate, rather than a decorator someone has
to remember. That enumeration is the most important test in this file.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import client_auth


def _app_endpoints(flask_app):
    """Every blueprint endpoint mounted under /api/app."""
    return {r.endpoint for r in flask_app.url_map.iter_rules()
            if str(r.rule).startswith("/api/app")}


def test_every_client_route_is_classified(flask_app):
    """A new endpoint in neither list fails the suite.

    This is the whole payoff of the shared prefix: "did we forget to protect
    something?" stops being a review question and becomes a test result.
    """
    classified = client_auth.PUBLIC_ENDPOINTS | client_auth.GATED_ENDPOINTS
    unclassified = _app_endpoints(flask_app) - classified
    assert unclassified == set(), (
        "these /api/app routes are in neither PUBLIC_ENDPOINTS nor "
        "GATED_ENDPOINTS: %s" % sorted(unclassified))


def test_no_endpoint_is_both_public_and_gated(flask_app):
    """An endpoint in both lists has an ambiguous policy."""
    assert client_auth.PUBLIC_ENDPOINTS & client_auth.GATED_ENDPOINTS == frozenset()


def test_registries_name_only_real_endpoints(flask_app):
    """A registry entry with no matching route is a stale name protecting nothing."""
    declared = client_auth.PUBLIC_ENDPOINTS | client_auth.GATED_ENDPOINTS
    assert declared - _app_endpoints(flask_app) == set()


def test_gated_endpoint_401s_without_a_user(client, monkeypatch):
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/app/me").status_code == 401


def test_gated_endpoint_allows_a_user(client):
    assert client.get("/api/app/me").status_code == 200


def test_me_returns_the_current_user(client):
    body = client.get("/api/app/me").get_json()
    assert body["user_id"] == "demo-user"
    assert body["plan"] == "none"


def test_401_body_leaks_nothing_internal(client, monkeypatch):
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    body = client.get("/api/app/me").get_data(as_text=True).lower()
    for leak in ("sqlite", "traceback", "prototype/", "select ", "/users/"):
        assert leak not in body


def test_the_operator_surface_is_untouched(client):
    """The guard must apply to /api/app only, never to the existing app."""
    assert client.get("/api/indices").status_code == 200
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/test_client_auth.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'prototype.client_auth'`.

- [ ] **Step 3: Write the auth seam**

Create `prototype/client_auth.py`:

```python
"""The auth seam for the client API.

Project B (accounts) does not exist yet. Everything the client API assumes
about identity is in this file, and it is three things: current_user() returns
an id or None, gated endpoints are protected, and positions.user_id is stable.
Swapping the stub for real sessions is a one-function change.

The registries are the point. This app has roughly seventy unprotected routes;
scattering client endpoints among them would make auth a per-route audit where
one missed decorator is a data leak. One prefix plus two explicit lists makes
"is everything classified?" a question the test suite answers by enumeration.
"""
from flask import jsonify, request

# Blueprint endpoint names, not URL paths -- Flask dispatches on endpoints, and
# a path string would silently stop matching if a route were reworded.
PUBLIC_ENDPOINTS = frozenset({
    "client_api.calls_list",
    "client_api.call_detail",
    "client_api.record",
})

GATED_ENDPOINTS = frozenset({
    "client_api.me",
    "client_api.positions_list",
    "client_api.position_create",
    "client_api.position_update",
    "client_api.position_delete",
})


def current_user():
    """The signed-in user's id, or None.

    STUB. Returns a fixed id until project B lands. Every gated endpoint reads
    identity through this one function, so replacing it with a real session
    lookup is the entire integration.
    """
    return "demo-user"


def install_guard(app):
    """Refuse gated client endpoints when nobody is signed in."""

    @app.before_request
    def _guard_client_api():
        endpoint = request.endpoint
        if endpoint in GATED_ENDPOINTS and current_user() is None:
            return jsonify({"error": "sign in to see this"}), 401
        return None
```

- [ ] **Step 4: Write the blueprint with `/api/app/me`**

Create `prototype/client_api.py`:

```python
"""The client dashboard's API. Eight endpoints, one prefix, one guard.

Everything here is client-facing, which sets rules the operator surface does
not have: no engine names, no strategy internals, no agent vocabulary, and no
internal detail in any error message. A client sees what was called and what
happened -- never which engine said so.
"""
from flask import Blueprint, jsonify

from prototype import client_auth

bp = Blueprint("client_api", __name__, url_prefix="/api/app")


@bp.route("/me")
def me():
    """The signed-in user and their plan. Project B owns this shape later."""
    return jsonify({"user_id": client_auth.current_user(), "plan": "none"})
```

- [ ] **Step 5: Register the blueprint in `app.py`**

Find the line where the Flask app is created (`app = Flask(__name__)`) and add exactly these FOUR lines after it, keeping everything else untouched:

```python
from prototype import client_auth                        # noqa: E402
from prototype.client_api import bp as _client_api_bp    # noqa: E402
app.register_blueprint(_client_api_bp)
client_auth.install_guard(app)
```

Do not reorder, reformat, or otherwise touch any existing line in `app.py`. `git diff prototype/app.py` must show four added lines and zero removed.

- [ ] **Step 6: Run to verify they pass**

```bash
python3 -m pytest tests/test_client_auth.py -q
```

Expected: 8 passed.

- [ ] **Step 7: Confirm the whole suite still passes**

```bash
python3 -m pytest tests/ -q
```

Expected: 242 passed (234 + 8).

- [ ] **Step 8: Commit**

```bash
git add prototype/client_auth.py prototype/client_api.py prototype/app.py tests/test_client_auth.py
git commit -m "feat(client-api): the auth boundary, and a test that enumerates it

Seventy routes in this app are unprotected. Putting the client API under one
prefix turns 'did we forget to protect something?' from a review question into
a test result: an endpoint in neither registry fails the suite.

current_user() is a stub. It is also the entire contract project B has to
satisfy -- an id or None, read through one function."
```

---

