# Client API Layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serve everything the client dashboard needs from eight endpoints under one protected prefix, before any screen exists.

**Architecture:** A Flask Blueprint (`prototype/client_api.py`) mounted at `/api/app`, plus a separate auth seam (`prototype/client_auth.py`) holding a stubbed `current_user()`, the public/gated route registries, and a single `before_request` guard. `prototype/app.py` gains two lines and nothing else. Reads come from the `calls` and `positions` tables built by the capture pipeline; live prices come from `kite_data.get_quotes` in-process.

**Tech Stack:** Python 3, Flask (already a dependency), standard-library `sqlite3`, pytest 7.4.0. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-28-client-dashboard-design.md`

## Global Constraints

- **No new runtime dependencies.** No pip install, no `requirements.txt` change.
- **Every client endpoint lives under `/api/app/`.** The app has ~70 unprotected routes; one prefix means one guard instead of a per-route audit.
- **Auth boundary:** `/api/app/calls`, `/api/app/calls/<id>` and `/api/app/record` are PUBLIC. `/api/app/positions*` and `/api/app/me` are GATED.
- **`/api/picks` is never exposed to clients.** It computes live, so serving it would show a call that was never published or recorded. Client call data comes from the `calls` table only.
- **`/api/paper/*` is not reused.** It is a global in-process dict and operator-facing; `positions` replaces it. Two competing books is the failure this avoids.
- **Never zero-fill a missing price.** `kite_data.get_quotes` omits symbols it cannot fetch, deliberately — "a silent 0.0 price is how bad fills happen". A position whose quote is missing reports `price_unavailable`, never `0`.
- **`ungraded` calls are excluded from hit-rate arithmetic.** `resolved = hit + miss`. A call published without a target has no standard to be graded against.
- **No engine names, no strategy internals, no agent vocabulary** in any response. `signal` is plain English; `v5_size` and `alpha-hunter` never appear.
- Client-facing errors are sanitised — no SQL, no table names, no internal paths.
- Python style: 4-space indent, double-quoted strings, docstrings on functions.
- Run tests as `python3 -m pytest tests/ -q` — always scope to `tests/`. A repo-wide run fails collection on a pre-existing unrelated file (`scripts/test_baseline_protection.py` raises SystemExit).

## Verified Facts About This Codebase

These were checked against the running app. Do not re-derive them, and do not trust any contradicting assumption:

| Fact | Value |
|:--|:--|
| Batch quotes | `prototype/v4/kite_data.py: get_quotes(symbols) -> dict` returns `{SYMBOL: {last_price, change_pct, high, low, open, prev_close}}`. Symbols it cannot fetch are **omitted**, never zero-filled. |
| `/api/scores` | Returns an **empty list** on a cold cache by design (NEVER-BLOCK). Unusable for mark-to-market. |
| `data_providers.get_quote(sym)` | Returned `None` for `CIPLA`; Yahoo 404s without a `.NS` suffix. Not a reliable fallback. |
| Chart ranges | Whitelist: `1d 1w 1m 3m 1y 3y 5y`. `1mo` is invalid and 400s. |
| `/api/indices` | Returns a dict keyed `nifty`, `sensex`, `banknifty`, `niftyit`, `vix`. |
| `calls` columns | `id, symbol, side, published_at, price_at_call, score, signal, horizon, target, stop, outcome_price, outcome_at, outcome`. `outcome` is `NOT NULL DEFAULT 'open'`, values `open` / `hit` / `miss` / `ungraded`. |
| `positions` columns | `id, user_id, symbol, qty, avg_price, opened_at, closed_at, exit_price, source, broker_ref, call_id`. `source` defaults `'manual'`; `call_id` is a nullable FK to `calls(id)`. |
| Store access | `prototype/app_store.py: get_db(path=None)`, `init_db(conn)`, `DB_PATH`. Sets WAL, `busy_timeout=5000`, `PRAGMA foreign_keys=ON`, `row_factory=sqlite3.Row`. |
| Test harness | `tests/conftest.py` provides session-scoped `flask_app` and per-test `client` fixtures. |
| Baseline | 234 tests passing. |

## File Structure

| File | Responsibility |
|:--|:--|
| `prototype/client_auth.py` | **new** — the auth seam and nothing else: `current_user()` stub, `PUBLIC_ENDPOINTS`/`GATED_ENDPOINTS` registries, and `install_guard(app)`. Separate from the API so the enumeration test can import the registries without importing route handlers. |
| `prototype/client_api.py` | **new** — one Flask Blueprint holding all eight endpoints. Read-only helpers for shaping rows live here too. |
| `prototype/app.py` | **modify, 2 lines** — import the blueprint and register it. Nothing else in this 7,000-line file changes. |
| `tests/test_client_auth.py` | **new** — the enumeration test (the reason the prefix exists) and guard behaviour. |
| `tests/test_client_api_calls.py` | **new** — calls, call detail, record. |
| `tests/test_client_api_positions.py` | **new** — positions CRUD and mark-to-market. |

**Why the auth seam is its own file.** The enumeration test must be able to ask "is every `/api/app/` route classified?" without side effects. Importing a module of route handlers to answer that couples the test to the thing it audits. Two files keep the question answerable in isolation.

**Why a Blueprint rather than adding to `app.py`.** `app.py` is over 7,000 lines and carries the operator surface. A blueprint keeps the client API reviewable in one screen, gives the guard a single mount point, and makes "which routes are client-facing?" answerable by reading one file.

---

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

### Task 2: Calls and call detail

**Files:**
- Modify: `prototype/client_api.py`
- Modify: `prototype/client_auth.py` (endpoints already listed — verify, do not duplicate)
- Create: `tests/test_client_api_calls.py`

**Interfaces:**
- Consumes: `client_api.bp`, `client_auth.PUBLIC_ENDPOINTS`.
- Produces:
  - `GET /api/app/calls` → `{"calls": [...], "as_of": "<ISO>"}`, endpoint name `client_api.calls_list`
  - `GET /api/app/calls/<call_id>` → one call, or 404 `{"error": "no such call"}`, endpoint name `client_api.call_detail`
  - `client_api.shape_call(row)` → `dict` for one `sqlite3.Row`, keys exactly: `id`, `symbol`, `side`, `published_at`, `price_at_call`, `score`, `signal`, `horizon`, `target`, `stop`, `outcome`, `outcome_price`, `outcome_at`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client_api_calls.py`:

```python
"""Client-facing call data.

These endpoints read the `calls` table and nothing else. /api/picks computes
live and stores nothing, so serving it would show a client a call that was
never published and never recorded -- the distinction the whole track record
rests on.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store, client_api


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A throwaway database wired into the API, never the real record."""
    path = str(tmp_path / "api.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_api, "open_store", lambda: app_store.get_db(path))
    yield conn
    conn.close()


def _add_call(conn, cid, symbol, published_at, outcome="open", **kw):
    conn.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call,"
        " score, signal, horizon, target, stop, outcome, outcome_price)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, symbol, kw.get("side", "BUY"), published_at,
         kw.get("price_at_call", 1000.0), kw.get("score", 73.0),
         kw.get("signal", "Reclaimed VWAP; volume 2.1x"),
         kw.get("horizon", "intraday"), kw.get("target", 1020.0),
         kw.get("stop", 985.0), outcome, kw.get("outcome_price")))
    conn.commit()


def test_empty_table_returns_an_empty_list_not_an_error(client, store):
    r = client.get("/api/app/calls")
    assert r.status_code == 200
    assert r.get_json()["calls"] == []


def test_calls_are_returned_newest_first(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-26T09:20:00")
    _add_call(store, "c2", "TITAN", "2026-08-28T09:20:00")
    symbols = [c["symbol"] for c in client.get("/api/app/calls").get_json()["calls"]]
    assert symbols == ["TITAN", "CIPLA"]


def test_a_call_carries_its_plain_english_reason(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00")
    call = client.get("/api/app/calls").get_json()["calls"][0]
    assert call["signal"] == "Reclaimed VWAP; volume 2.1x"


def test_no_engine_vocabulary_leaks_to_a_client(client, store):
    """A client sees what was called, never which engine said so."""
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00")
    body = client.get("/api/app/calls").get_data(as_text=True).lower()
    for word in ("v4", "v5_size", "composite_scorer", "alpha-hunter", "engine"):
        assert word not in body


def test_call_detail_returns_one_call(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00")
    body = client.get("/api/app/calls/c1").get_json()
    assert body["id"] == "c1"
    assert body["target"] == 1020.0


def test_unknown_call_id_404s_without_leaking(client, store):
    r = client.get("/api/app/calls/nope")
    assert r.status_code == 404
    body = r.get_data(as_text=True).lower()
    for leak in ("sqlite", "select ", "traceback", "prototype/"):
        assert leak not in body


def test_an_open_call_reports_no_outcome(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00", outcome="open")
    call = client.get("/api/app/calls/c1").get_json()
    assert call["outcome"] == "open"
    assert call["outcome_price"] is None


def test_a_resolved_call_reports_its_outcome(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-26T09:20:00",
              outcome="hit", outcome_price=1030.0)
    call = client.get("/api/app/calls/c1").get_json()
    assert call["outcome"] == "hit"
    assert call["outcome_price"] == 1030.0


def test_calls_response_is_bounded_by_default(client, store):
    """The record grows every trading day; the response must not grow with it."""
    for i in range(60):
        _add_call(store, "c%02d" % i, "S%02d" % i, "2026-08-28T09:20:00")
    body = client.get("/api/app/calls").get_json()
    assert body["limit"] == 50
    assert len(body["calls"]) == 50


def test_a_client_cannot_request_the_whole_table(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00")
    assert client.get("/api/app/calls?limit=999999").get_json()["limit"] == 500


def test_calls_endpoint_is_public(client, store, monkeypatch):
    """Proof, not policy -- the acquisition surface must work signed out."""
    from prototype import client_auth
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/app/calls").status_code == 200
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_client_api_calls.py -q
```

Expected: failures — `open_store` does not exist and the routes 404.

- [ ] **Step 3: Add the store accessor and the two endpoints**

In `prototype/client_api.py`, add below the existing imports:

```python
from prototype import app_store
```

Then add, after the `me` endpoint:

```python
def open_store():
    """Open the calls/positions database.

    A named function rather than an inline call so tests can point the API at
    a throwaway file without touching the real record.
    """
    conn = app_store.get_db()
    app_store.init_db(conn)
    return conn


CALL_FIELDS = ("id", "symbol", "side", "published_at", "price_at_call",
               "score", "signal", "horizon", "target", "stop",
               "outcome", "outcome_price", "outcome_at")


def shape_call(row):
    """One `calls` row as the client sees it.

    An explicit field list rather than dict(row): it keeps internal columns
    from leaking into a client payload by accident when the schema grows.
    """
    return {k: row[k] for k in CALL_FIELDS}


# The record grows by roughly ten rows every trading day, so an unbounded
# response would be thousands of calls within a year while the Home screen
# shows a handful. Bounded by default, raisable by the caller, hard-capped so
# a client cannot ask for the whole table.
DEFAULT_CALL_LIMIT = 50
MAX_CALL_LIMIT = 500


@bp.route("/calls")
def calls_list():
    """Published calls, newest first. Reads the record -- never /api/picks."""
    try:
        limit = int(request.args.get("limit", DEFAULT_CALL_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_CALL_LIMIT
    limit = max(1, min(limit, MAX_CALL_LIMIT))

    conn = open_store()
    try:
        rows = conn.execute(
            "SELECT * FROM calls ORDER BY published_at DESC, symbol ASC"
            " LIMIT ?", (limit,)).fetchall()
        return jsonify({"calls": [shape_call(r) for r in rows],
                        "limit": limit,
                        "as_of": datetime.now().isoformat(timespec="seconds")})
    finally:
        conn.close()


@bp.route("/calls/<call_id>")
def call_detail(call_id):
    """One call, with the reasoning that was published alongside it."""
    conn = open_store()
    try:
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return jsonify({"error": "no such call"}), 404
    return jsonify(shape_call(row))
```

Add `from datetime import datetime` to the imports at the top of the file, and add `request` to the existing `from flask import ...` line — the limit is read from the query string.

- [ ] **Step 4: Run to verify they pass**

```bash
python3 -m pytest tests/test_client_api_calls.py -q
```

Expected: 11 passed.

- [ ] **Step 5: Confirm the enumeration test still passes**

```bash
python3 -m pytest tests/ -q
```

Expected: 253 passed (242 + 11). If `test_every_client_route_is_classified` fails, the new endpoint names are missing from `PUBLIC_ENDPOINTS` — that is the test doing its job, not a bug to work around.

- [ ] **Step 6: Commit**

```bash
git add prototype/client_api.py tests/test_client_api_calls.py
git commit -m "feat(client-api): serve published calls from the record

Reads the calls table, never /api/picks. Picks computes live and stores
nothing, so serving it would show a client a call that was never published
and never recorded -- which is the distinction the track record rests on.

Fields are listed explicitly rather than dict(row), so a column added to the
schema later cannot leak into a client payload by accident."
```

---

### Task 3: The track record endpoint

**Files:**
- Modify: `prototype/client_api.py`
- Create: `tests/test_client_api_record.py`

**Interfaces:**
- Consumes: `client_api.open_store`, `client_api.bp`.
- Produces:
  - `GET /api/app/record` → `{"total", "resolved", "hit", "miss", "ungraded", "open", "hit_rate", "since", "meaningful_from", "is_meaningful"}`, endpoint name `client_api.record`
  - `hit_rate` is `None` when `resolved == 0` — never `0.0`.
  - `meaningful_from` is the integer `100`; `is_meaningful` is `resolved >= 100`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client_api_record.py`:

```python
"""The track record -- the number this product is sold on.

Two rules matter more than the arithmetic. A hit rate over a small sample is
the easiest way to mislead a customer without lying, so the response always
carries the sample size and whether it is meaningful yet. And an `ungraded`
call -- one published without a target -- has no standard to be graded
against, so it is excluded rather than counted leniently.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store, client_api


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / "api.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_api, "open_store", lambda: app_store.get_db(path))
    yield conn
    conn.close()


def _add(conn, cid, outcome, day="2026-08-28"):
    conn.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call,"
        " target, outcome) VALUES (?,?,?,?,?,?,?)",
        (cid, "S" + cid, "BUY", day + "T09:20:00", 1000.0, 1020.0, outcome))
    conn.commit()


def test_empty_record_is_not_an_error(client, store):
    body = client.get("/api/app/record").get_json()
    assert body["total"] == 0
    assert body["hit_rate"] is None


def test_hit_rate_is_none_not_zero_when_nothing_resolved(client, store):
    """Zero reads as 'we get everything wrong'. None reads as 'not yet'."""
    _add(store, "c1", "open")
    body = client.get("/api/app/record").get_json()
    assert body["open"] == 1
    assert body["resolved"] == 0
    assert body["hit_rate"] is None


def test_hit_rate_counts_only_hits_and_misses(client, store):
    _add(store, "c1", "hit")
    _add(store, "c2", "miss")
    _add(store, "c3", "open")
    body = client.get("/api/app/record").get_json()
    assert body["resolved"] == 2
    assert body["hit_rate"] == 50.0


def test_ungraded_calls_are_excluded_from_the_rate(client, store):
    """A call with no published target has no standard to be graded against."""
    _add(store, "c1", "hit")
    _add(store, "c2", "miss")
    _add(store, "c3", "ungraded")
    body = client.get("/api/app/record").get_json()
    assert body["ungraded"] == 1
    assert body["resolved"] == 2
    assert body["hit_rate"] == 50.0


def test_small_samples_are_flagged_as_not_yet_meaningful(client, store):
    _add(store, "c1", "hit")
    body = client.get("/api/app/record").get_json()
    assert body["is_meaningful"] is False
    assert body["meaningful_from"] == 100


def test_since_reports_the_first_recorded_day(client, store):
    _add(store, "c1", "hit", day="2026-08-26")
    _add(store, "c2", "miss", day="2026-08-28")
    assert client.get("/api/app/record").get_json()["since"] == "2026-08-26"


def test_empty_record_reports_since_as_none(client, store):
    assert client.get("/api/app/record").get_json()["since"] is None


def test_record_is_public(client, store, monkeypatch):
    from prototype import client_auth
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/app/record").status_code == 200
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_client_api_record.py -q
```

Expected: failures — `/api/app/record` 404s.

- [ ] **Step 3: Add the endpoint**

In `prototype/client_api.py`, add:

```python
# A hit rate over a handful of calls is the easiest way to mislead a customer
# without lying to them. The response always carries the sample size and says
# plainly whether it is meaningful yet.
MEANINGFUL_FROM = 100


@bp.route("/record")
def record():
    """Aggregate outcomes. Ungraded calls are excluded, never counted softly."""
    conn = open_store()
    try:
        rows = conn.execute("SELECT published_at, outcome FROM calls").fetchall()
    finally:
        conn.close()

    hit = sum(1 for r in rows if r["outcome"] == "hit")
    miss = sum(1 for r in rows if r["outcome"] == "miss")
    ungraded = sum(1 for r in rows if r["outcome"] == "ungraded")
    open_ = sum(1 for r in rows if r["outcome"] == "open")
    resolved = hit + miss
    days = sorted({r["published_at"][:10] for r in rows})

    return jsonify({
        "total": len(rows),
        "resolved": resolved,
        "hit": hit,
        "miss": miss,
        "ungraded": ungraded,
        "open": open_,
        # None, never 0.0 -- an unresolved record is not a record of failure.
        "hit_rate": round(100.0 * hit / resolved, 1) if resolved else None,
        "since": days[0] if days else None,
        "meaningful_from": MEANINGFUL_FROM,
        "is_meaningful": resolved >= MEANINGFUL_FROM,
    })
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 -m pytest tests/test_client_api_record.py -q
```

Expected: 8 passed.

- [ ] **Step 5: Confirm the whole suite passes, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/client_api.py tests/test_client_api_record.py
git commit -m "feat(client-api): the track record, honest about its own sample size

Ungraded calls -- published without a target -- are excluded rather than
graded by a softer rule, because two standards behind one percentage is
indefensible however it is labelled.

The response carries resolved count, since-date and is_meaningful alongside
the rate, so a page cannot show 62% over eleven calls without also showing
that it is eleven calls."
```

---

### Task 4: Positions, marked to market

**Files:**
- Modify: `prototype/client_api.py`
- Create: `tests/test_client_api_positions.py`

**Interfaces:**
- Consumes: `client_api.open_store`, `client_auth.current_user`.
- Produces:
  - `GET /api/app/positions` → `{"positions": [...], "totals": {...}}`, endpoint `client_api.positions_list`
  - `POST /api/app/positions` → 201 with the created position, endpoint `client_api.position_create`
  - `PATCH /api/app/positions/<pid>` → 200, endpoint `client_api.position_update`
  - `DELETE /api/app/positions/<pid>` → 204, endpoint `client_api.position_delete`
  - `client_api.fetch_quotes(symbols)` → `dict` mapping symbol to `{"last_price": float, "change_pct": float}`; symbols with no quote are OMITTED.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_client_api_positions.py`:

```python
"""The client's own book.

One rule dominates: never zero-fill a missing price. kite_data.get_quotes
omits symbols it cannot fetch, deliberately -- "a silent 0.0 price is how bad
fills happen". A position whose quote is missing must say so, not report a
portfolio worth nothing.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store, client_api


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / "api.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_api, "open_store", lambda: app_store.get_db(path))
    monkeypatch.setattr(client_api, "fetch_quotes",
                        lambda syms: {s: {"last_price": 1100.0, "change_pct": 1.0}
                                      for s in syms})
    yield conn
    conn.close()


def _post(client, **kw):
    payload = {"symbol": "CIPLA", "qty": 10, "avg_price": 1000.0}
    payload.update(kw)
    return client.post("/api/app/positions", json=payload)


def test_empty_book_returns_an_empty_list(client, store):
    body = client.get("/api/app/positions").get_json()
    assert body["positions"] == []
    assert body["totals"]["value"] == 0


def test_logging_a_trade_returns_201_and_the_position(client, store):
    r = _post(client)
    assert r.status_code == 201
    assert r.get_json()["symbol"] == "CIPLA"


def test_a_logged_position_appears_in_the_book(client, store):
    _post(client)
    assert len(client.get("/api/app/positions").get_json()["positions"]) == 1


def test_positions_are_marked_to_market(client, store):
    _post(client)                       # 10 @ 1000, quote 1100
    pos = client.get("/api/app/positions").get_json()["positions"][0]
    assert pos["last_price"] == 1100.0
    assert pos["value"] == 11000.0
    assert pos["pnl"] == 1000.0
    assert pos["pnl_pct"] == 10.0


def test_a_missing_quote_is_reported_not_zero_filled(client, store, monkeypatch):
    """A silent 0.0 would show a real holding as worthless."""
    monkeypatch.setattr(client_api, "fetch_quotes", lambda syms: {})
    _post(client)
    pos = client.get("/api/app/positions").get_json()["positions"][0]
    assert pos["price_unavailable"] is True
    assert pos["last_price"] is None
    assert pos["value"] is None
    assert pos["pnl"] is None


def test_totals_exclude_positions_with_no_price(client, store, monkeypatch):
    """A portfolio total must never silently omit a holding's cost basis."""
    monkeypatch.setattr(client_api, "fetch_quotes",
                        lambda syms: {"CIPLA": {"last_price": 1100.0, "change_pct": 1.0}})
    _post(client, symbol="CIPLA")
    _post(client, symbol="TITAN")
    totals = client.get("/api/app/positions").get_json()["totals"]
    assert totals["value"] == 11000.0
    assert totals["priced"] == 1
    assert totals["unpriced"] == 1


def test_provenance_defaults_to_the_clients_own_idea(client, store):
    pos = _post(client).get_json()
    assert pos["call_id"] is None
    assert pos["source"] == "manual"


def test_a_position_can_cite_the_call_that_triggered_it(client, store):
    store.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call)"
        " VALUES ('c1','CIPLA','BUY','2026-08-28T09:20:00',1000.0)")
    store.commit()
    pos = _post(client, call_id="c1").get_json()
    assert pos["call_id"] == "c1"


def test_a_position_citing_an_unknown_call_is_rejected(client, store):
    r = _post(client, call_id="nope")
    assert r.status_code == 400


def test_missing_required_fields_are_rejected(client, store):
    assert client.post("/api/app/positions", json={"symbol": "CIPLA"}).status_code == 400


def test_a_non_positive_quantity_is_rejected(client, store):
    assert _post(client, qty=0).status_code == 400
    assert _post(client, qty=-5).status_code == 400


def test_closing_a_position_records_the_exit(client, store):
    pid = _post(client).get_json()["id"]
    r = client.patch("/api/app/positions/" + pid,
                     json={"closed_at": "2026-08-29T15:30:00", "exit_price": 1120.0})
    assert r.status_code == 200
    assert r.get_json()["exit_price"] == 1120.0


def test_deleting_a_position_removes_it(client, store):
    pid = _post(client).get_json()["id"]
    assert client.delete("/api/app/positions/" + pid).status_code == 204
    assert client.get("/api/app/positions").get_json()["positions"] == []


def test_deleting_an_unknown_position_404s(client, store):
    assert client.delete("/api/app/positions/nope").status_code == 404


def test_one_user_never_sees_anothers_book(client, store, monkeypatch):
    """The single most important property in this file."""
    from prototype import client_auth
    _post(client)
    monkeypatch.setattr(client_auth, "current_user", lambda: "someone-else")
    assert client.get("/api/app/positions").get_json()["positions"] == []


def test_positions_are_gated(client, store, monkeypatch):
    from prototype import client_auth
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/app/positions").status_code == 401
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_client_api_positions.py -q
```

Expected: failures — the routes 404 and `fetch_quotes` does not exist.

- [ ] **Step 3: Add the quote helper and the four endpoints**

In `prototype/client_api.py`, add these imports at the top:

```python
import uuid
from flask import request
```

Then add:

```python
def fetch_quotes(symbols):
    """Live prices for a set of symbols.

    Wraps kite_data.get_quotes, which OMITS symbols it cannot fetch rather
    than zero-filling them -- a silent 0.0 would render a real holding as
    worthless. That omission is preserved here on purpose: callers must handle
    a missing symbol, not receive a fake price for it.

    Returns {} rather than raising if the quote feed is unavailable, so a book
    still renders with its cost basis when prices are down.
    """
    if not symbols:
        return {}
    try:
        from prototype.v4 import kite_data
        return kite_data.get_quotes(sorted(set(symbols))) or {}
    except Exception:
        return {}


POSITION_FIELDS = ("id", "user_id", "symbol", "qty", "avg_price", "opened_at",
                   "closed_at", "exit_price", "source", "broker_ref", "call_id")


def shape_position(row, quote):
    """One position, marked to market where a price is available."""
    out = {k: row[k] for k in POSITION_FIELDS}
    last = (quote or {}).get("last_price")
    if last is None:
        out.update({"last_price": None, "value": None, "pnl": None,
                    "pnl_pct": None, "price_unavailable": True})
        return out
    value = round(float(last) * float(row["qty"]), 2)
    cost = float(row["avg_price"]) * float(row["qty"])
    out.update({
        "last_price": float(last),
        "value": value,
        "pnl": round(value - cost, 2),
        "pnl_pct": round(100.0 * (value - cost) / cost, 2) if cost else None,
        "price_unavailable": False,
    })
    return out


@bp.route("/positions")
def positions_list():
    """The signed-in user's open book, marked to market."""
    user = client_auth.current_user()
    conn = open_store()
    try:
        rows = conn.execute(
            "SELECT * FROM positions WHERE user_id = ? AND closed_at IS NULL"
            " ORDER BY opened_at DESC", (user,)).fetchall()
    finally:
        conn.close()

    quotes = fetch_quotes([r["symbol"] for r in rows])
    shaped = [shape_position(r, quotes.get(r["symbol"])) for r in rows]
    priced = [p for p in shaped if not p["price_unavailable"]]
    return jsonify({
        "positions": shaped,
        "totals": {
            "value": round(sum(p["value"] for p in priced), 2) if priced else 0,
            "pnl": round(sum(p["pnl"] for p in priced), 2) if priced else 0,
            "priced": len(priced),
            # Surfaced, never silently dropped: a total that omits a holding
            # without saying so understates the book.
            "unpriced": len(shaped) - len(priced),
        },
    })


@bp.route("/positions", methods=["POST"])
def position_create():
    """Log a trade the client placed at their own broker."""
    body = request.get_json(silent=True) or {}
    symbol = str(body.get("symbol", "")).upper().replace(".NS", "").strip()
    try:
        qty = float(body.get("qty"))
        avg_price = float(body.get("avg_price"))
    except (TypeError, ValueError):
        return jsonify({"error": "qty and avg_price must be numbers"}), 400
    if not symbol or qty <= 0 or avg_price <= 0:
        return jsonify({"error": "symbol, a positive qty and a positive "
                                 "avg_price are required"}), 400

    call_id = body.get("call_id") or None
    conn = open_store()
    try:
        if call_id is not None:
            exists = conn.execute("SELECT 1 FROM calls WHERE id = ?",
                                  (call_id,)).fetchone()
            if exists is None:
                return jsonify({"error": "no such call"}), 400
        pid = "pos-" + uuid.uuid4().hex[:12]
        conn.execute(
            "INSERT INTO positions (id, user_id, symbol, qty, avg_price,"
            " opened_at, source, call_id) VALUES (?,?,?,?,?,?,?,?)",
            (pid, client_auth.current_user(), symbol, qty, avg_price,
             body.get("opened_at") or datetime.now().isoformat(timespec="seconds"),
             "manual", call_id))
        conn.commit()
        row = conn.execute("SELECT * FROM positions WHERE id = ?", (pid,)).fetchone()
        return jsonify(shape_position(row, None)), 201
    finally:
        conn.close()


@bp.route("/positions/<pid>", methods=["PATCH"])
def position_update(pid):
    """Edit or close a position. Only the owner's rows are reachable."""
    body = request.get_json(silent=True) or {}
    allowed = ("qty", "avg_price", "closed_at", "exit_price")
    sets = [(k, body[k]) for k in allowed if k in body]
    if not sets:
        return jsonify({"error": "nothing to update"}), 400

    conn = open_store()
    try:
        clause = ", ".join("%s = ?" % k for k, _ in sets)
        params = [v for _, v in sets] + [pid, client_auth.current_user()]
        cur = conn.execute(
            "UPDATE positions SET " + clause + " WHERE id = ? AND user_id = ?",
            params)
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "no such position"}), 404
        row = conn.execute("SELECT * FROM positions WHERE id = ?", (pid,)).fetchone()
        return jsonify(shape_position(row, None))
    finally:
        conn.close()


@bp.route("/positions/<pid>", methods=["DELETE"])
def position_delete(pid):
    """Remove a mistaken entry. Scoped to the owner."""
    conn = open_store()
    try:
        cur = conn.execute("DELETE FROM positions WHERE id = ? AND user_id = ?",
                           (pid, client_auth.current_user()))
        conn.commit()
    finally:
        conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "no such position"}), 404
    return "", 204
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 -m pytest tests/test_client_api_positions.py -q
```

Expected: 15 passed.

- [ ] **Step 5: Confirm the whole suite passes**

```bash
python3 -m pytest tests/ -q
```

Expected: 276 passed (234 + 8 + 11 + 8 + 15).

- [ ] **Step 6: Exercise the API for real**

**Port 5050 may already belong to another process — check first and use 5051 if so.** Every command below uses `$PORT` so the two cannot drift apart:

```bash
PORT=5051
lsof -ti :$PORT >/dev/null 2>&1 && echo "pick another port" || echo "$PORT free"
FLASK_RUN_PORT=$PORT python3 prototype/app.py --port $PORT &
sleep 6
curl -s localhost:$PORT/api/app/record
curl -s localhost:$PORT/api/app/calls
curl -s -X POST localhost:$PORT/api/app/positions \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"CIPLA","qty":10,"avg_price":1420}'
curl -s localhost:$PORT/api/app/positions
```

If `prototype/app.py` does not accept a `--port` flag, read how it calls `app.run()` at the bottom of the file and start it the way that file expects — do not edit it.

Report the actual output verbatim. The record will be empty (the capture pipeline has not run yet), which is correct and must NOT be "fixed". Then kill the server YOU started, and delete the position you created:

```bash
python3 -c "import sys;sys.path.insert(0,'.');from prototype import app_store;c=app_store.get_db();c.execute(\"DELETE FROM positions WHERE user_id='demo-user'\");c.commit();print('positions remaining:', list(c.execute('SELECT COUNT(*) FROM positions'))[0][0])"
```

- [ ] **Step 7: Commit**

```bash
git add prototype/client_api.py tests/test_client_api_positions.py
git commit -m "feat(client-api): the client's book, marked to market

Never zero-fills. kite_data.get_quotes omits symbols it cannot fetch, and
that omission is carried through rather than smoothed over -- a silent 0.0
renders a real holding as worthless. A position with no quote reports
price_unavailable, and the portfolio total says how many it excluded.

Every query is scoped to current_user(), so the one thing this layer must
never do -- show one client another's book -- is a property of the SQL and
not of a caller remembering to filter."
```

---

## Verification

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/ -q
```

Expected: **276 passing** (234 existing + 42 new).

The plan is complete when all of the following also hold:

| | Check |
|:---:|:--|
| ☐ | `test_every_client_route_is_classified` passes — no `/api/app` route is unclassified |
| ☐ | `curl localhost:$PORT/api/app/record` returns JSON with `hit_rate: null`, not `0` |
| ☐ | A position with an unfetchable symbol reports `price_unavailable: true`, never a price of `0` |
| ☐ | `curl` as a signed-out user gets 200 on `/api/app/calls` and 401 on `/api/app/positions` |
| ☐ | No response body contains `v4`, `composite_scorer`, `sqlite`, or a filesystem path |
| ☐ | `git diff prototype/app.py` shows exactly four added lines and zero removed |

## Not in this plan

The five screens — Home, Calls, Call detail, Book, Track record — are the next
plan. They consume these eight endpoints and need the light/indigo palette and
the 900px responsive shell from the spec. Nothing in this plan renders HTML.

Project B (accounts) is still deferred. `current_user()` returning a fixed id
is the only thing standing in for it, and swapping that stub is the entire
integration.
