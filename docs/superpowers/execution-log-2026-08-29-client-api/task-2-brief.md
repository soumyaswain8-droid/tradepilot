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

