### Task 1: The store and its schema

**Files:**
- Create: `prototype/app_store.py`
- Create: `tests/test_app_store.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `app_store.DB_PATH` → absolute path to `prototype/tradepilot_app.db`
  - `app_store.get_db(path=None)` → `sqlite3.Connection` with WAL, `busy_timeout=5000`, `row_factory=sqlite3.Row`, and `PRAGMA foreign_keys=ON`. The optional `path` argument exists so tests can use a temporary file.
  - `app_store.init_db(conn)` → creates both tables and indexes. Idempotent.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_store.py`:

```python
"""Schema tests for the calls/positions store.

`calls` is the product record -- if it is lost the track record cannot be
rebuilt. These tests pin the two properties that protect it: the schema is
idempotent, and the publish job physically cannot write the same call twice.
"""
import os
import sqlite3
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


@pytest.fixture
def conn(tmp_path):
    """A store backed by a throwaway file, never the real database."""
    c = app_store.get_db(str(tmp_path / "test_app.db"))
    app_store.init_db(c)
    yield c
    c.close()


def test_both_tables_exist(conn):
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "calls" in names
    assert "positions" in names


def test_init_db_is_idempotent(conn):
    """Running it twice must not raise -- migrations re-run on every boot."""
    app_store.init_db(conn)
    app_store.init_db(conn)


def test_foreign_keys_are_enforced(conn):
    """SQLite ignores foreign keys unless the pragma is set per connection."""
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO positions (id, user_id, symbol, qty, avg_price, "
            "opened_at, call_id) VALUES (?,?,?,?,?,?,?)",
            ("p1", "u1", "CIPLA", 10, 1420.0, "2026-08-28T09:30:00", "no-such-call"))
        conn.commit()


def test_duplicate_call_same_symbol_same_day_is_rejected(conn):
    """The idempotency guarantee is a database constraint, not a convention."""
    row = ("c1", "CIPLA", "BUY", "2026-08-28T09:20:00", 1420.0, 73.0,
           "VWAP reclaim", "intraday", 1448.0, 1399.0)
    cols = ("INSERT INTO calls (id, symbol, side, published_at, price_at_call, "
            "score, signal, horizon, target, stop) VALUES (?,?,?,?,?,?,?,?,?,?)")
    conn.execute(cols, row)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(cols, ("c2", "CIPLA", "BUY", "2026-08-28T15:10:00", 1431.0,
                            71.0, "VWAP reclaim", "intraday", 1460.0, 1410.0))
        conn.commit()


def test_same_symbol_next_day_is_allowed(conn):
    """A stock called on consecutive days is two calls, not a duplicate."""
    cols = ("INSERT INTO calls (id, symbol, side, published_at, price_at_call) "
            "VALUES (?,?,?,?,?)")
    conn.execute(cols, ("c1", "CIPLA", "BUY", "2026-08-28T09:20:00", 1420.0))
    conn.execute(cols, ("c2", "CIPLA", "BUY", "2026-08-29T09:20:00", 1431.0))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 2


def test_outcome_defaults_to_open(conn):
    """An unresolved call must never look resolved."""
    conn.execute("INSERT INTO calls (id, symbol, side, published_at, price_at_call) "
                 "VALUES (?,?,?,?,?)",
                 ("c1", "CIPLA", "BUY", "2026-08-28T09:20:00", 1420.0))
    conn.commit()
    assert conn.execute("SELECT outcome FROM calls WHERE id='c1'").fetchone()[0] == "open"


def test_real_db_path_is_not_the_analytics_db():
    """The product record must not share a file with disposable analytics."""
    assert app_store.DB_PATH.endswith("tradepilot_app.db")
    assert "analytics" not in app_store.DB_PATH
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/test_app_store.py -q
```

Expected: collection error — `ModuleNotFoundError: No module named 'prototype.app_store'`.

- [ ] **Step 3: Write the store**

Create `prototype/app_store.py`:

```python
"""Store for the client product's own data -- published calls and client positions.

Deliberately a SEPARATE database file from tradepilot_analytics.db. Analytics is
behavioural tracking: disposable and rebuildable. `calls` is the product record --
if it is lost, the track record is lost, and it cannot be reconstructed without
retroactively labelling engine history as calls, which the design rejects.

Connection settings mirror prototype/analytics.py, which has run in production
here for months: WAL for concurrent readers, a busy timeout so a writer does not
fail instantly under contention, and Row so callers get mappings not tuples.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "tradepilot_app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id             TEXT PRIMARY KEY,
    symbol         TEXT NOT NULL,
    side           TEXT NOT NULL,
    published_at   TEXT NOT NULL,
    price_at_call  REAL NOT NULL,
    score          REAL,
    signal         TEXT,
    horizon        TEXT,
    target         REAL,
    stop           REAL,
    outcome_price  REAL,
    outcome_at     TEXT,
    outcome        TEXT NOT NULL DEFAULT 'open'
);

-- Idempotency is a constraint, not a convention: re-running the publish job
-- cannot double-count a day.
CREATE UNIQUE INDEX IF NOT EXISTS ux_calls_symbol_day
    ON calls (symbol, date(published_at));

CREATE INDEX IF NOT EXISTS ix_calls_outcome
    ON calls (outcome, published_at);

CREATE TABLE IF NOT EXISTS positions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    qty         REAL NOT NULL,
    avg_price   REAL NOT NULL,
    opened_at   TEXT NOT NULL,
    closed_at   TEXT,
    exit_price  REAL,
    source      TEXT NOT NULL DEFAULT 'manual',
    broker_ref  TEXT,
    call_id     TEXT REFERENCES calls(id)
);

CREATE INDEX IF NOT EXISTS ix_positions_user
    ON positions (user_id, closed_at);
"""


def get_db(path=None):
    """Open the store. Pass `path` to point at a throwaway file in tests."""
    conn = sqlite3.connect(path or DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    """Create tables and indexes. Safe to run on every boot."""
    conn.executescript(SCHEMA)
    conn.commit()
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 -m pytest tests/test_app_store.py -q
```

Expected: 7 passed.

- [ ] **Step 5: Confirm the whole suite still passes**

```bash
python3 -m pytest tests/ -q
```

Expected: 191 passed (184 existing + 7 new).

- [ ] **Step 6: Commit**

```bash
git add prototype/app_store.py tests/test_app_store.py
git commit -m "feat(store): the calls and positions store

A separate database file from the analytics DB, deliberately. Analytics is
behavioural tracking and is rebuildable; calls is the product record, and
losing it means losing the track record with no honest way to reconstruct it.

Idempotency is a unique index on (symbol, date(published_at)) rather than a
convention the publish job is trusted to honour."
```

---

