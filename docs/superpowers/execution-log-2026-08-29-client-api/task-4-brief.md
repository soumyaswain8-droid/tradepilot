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
