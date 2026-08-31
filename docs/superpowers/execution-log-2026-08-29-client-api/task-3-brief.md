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

