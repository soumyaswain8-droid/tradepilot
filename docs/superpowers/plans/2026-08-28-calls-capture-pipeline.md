# Calls Capture Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist every call TradePilot publishes, and resolve what happened to it, so a defensible track record accrues from today.

**Architecture:** A SQLite store (`prototype/app_store.py`) holds `calls` and `positions` in their own database file, separate from the analytics DB. A publish job fetches `/api/picks?category=stocks` over HTTP and writes one row per pick, made idempotent by a unique index rather than by convention. A resolver fills the outcome once a call's horizon has elapsed. Neither job depends on any UI.

**Tech Stack:** Python 3, standard-library `sqlite3` (no ORM, no new dependency), `urllib.request` for the HTTP fetch, pytest 7.4.0. macOS `launchd` for scheduling, following the pattern already used by `auto-sync`.

**Spec:** `docs/superpowers/specs/2026-08-28-client-dashboard-design.md` (Phase 0)

## Global Constraints

- **No new runtime dependencies.** No pip install, no `requirements.txt` change. `sqlite3` and `urllib` are standard library.
- **The publish job is the ONLY writer of `calls`.** Nothing else inserts into that table. A single writer is what makes "we called this" falsifiable.
- **Capture `category=stocks` ONLY.** `/api/picks?category=etfs` and `?category=mf` return hardcoded literal arrays with fabricated recommendation strings (`app.py` ~line 2843-2868). Those must never enter `calls`.
- **A call inside its horizon has `outcome = 'open'`** and must never be counted in a hit rate.
- **Failures are logged loudly and exit non-zero.** A missing day in the record is worse than a visible gap. Never swallow an exception.
- **`PRAGMA foreign_keys = ON` per connection.** SQLite does not enforce foreign keys by default.
- Python style in this repo: 4-space indent, double-quoted strings, docstrings on functions.
- Run tests as `python3 -m pytest tests/ -q` — always scope to `tests/`. A repo-wide run fails collection on a pre-existing unrelated file (`scripts/test_baseline_protection.py` raises SystemExit).

## File Structure

| File | Responsibility |
|:--|:--|
| `prototype/app_store.py` | **new** — SQLite connection + schema for `calls` and `positions`. Mirrors the proven pattern in `prototype/analytics.py` (WAL, busy_timeout, `row_factory=Row`). Owns schema only; no business logic. |
| `scripts/publish-calls.py` | **new** — fetches `/api/picks?category=stocks`, maps picks to `calls` rows, inserts idempotently. |
| `scripts/resolve-calls.py` | **new** — fills `outcome_price` / `outcome_at` / `outcome` for calls whose horizon has elapsed. |
| `scripts/calls-status.py` | **new** — prints the state of the record. This is how you know the pipeline is alive. |
| `tests/test_app_store.py` | **new** — schema, idempotency index, foreign keys. |
| `tests/test_publish_calls.py` | **new** — mapping, idempotency, stocks-only. |
| `tests/test_resolve_calls.py` | **new** — horizon logic, hit/miss classification. |

**Why a separate database file.** `prototype/tradepilot_analytics.db` holds behavioural tracking — page views, device strings — which is disposable and rebuildable. `calls` is the product record: if it is lost, the track record is lost and cannot be reconstructed without the retroactive labelling the spec rejects. Different durability requirements deserve different files.

---

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

### Task 2: The publish job

**Files:**
- Create: `scripts/publish-calls.py`
- Create: `tests/test_publish_calls.py`

**Interfaces:**
- Consumes: `app_store.get_db(path)`, `app_store.init_db(conn)` from Task 1.
- Produces:
  - `publish_calls.build_rows(payload, published_at)` → `list[dict]`, one per pick, keys exactly: `id`, `symbol`, `side`, `published_at`, `price_at_call`, `score`, `signal`, `horizon`, `target`, `stop`. Pure function, no I/O — this is what the tests drive.
  - `publish_calls.insert_rows(conn, rows)` → `int` count actually inserted (duplicates skipped, not raised).
  - `publish_calls.fetch_picks(url)` → parsed JSON dict.
  - `publish_calls.main()` → exit code 0 on success, 1 on any failure.

The script name has a hyphen, so tests import it via `importlib`. The test file shows exactly how.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_publish_calls.py`:

```python
"""Tests for the publish job.

The job is the ONLY writer of `calls`. Everything the track record later claims
rests on it recording exactly what was published, once per symbol per day.
"""
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


def _load(name, relpath):
    """Import a hyphenated script file as a module."""
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(REPO_ROOT, relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


publish_calls = _load("publish_calls", "scripts/publish-calls.py")


PAYLOAD = {
    "category": "stocks",
    "horizon": "intraday",
    "engine": "v4",
    "picks": [
        {"symbol": "CIPLA.NS", "name": "CIPLA", "price": 1420.0, "score": 73,
         "direction": "UP", "recommendation": "Strong Buy",
         "reasons": ["Reclaimed VWAP", "Volume 2.1x average"],
         "stop_loss_pct": 1.5, "target_pct": 2.0},
        {"symbol": "ADANIPORTS.NS", "name": "ADANIPORTS", "price": 1714.0,
         "score": 66, "direction": "UP", "recommendation": "Buy",
         "reasons": ["Broke previous-day high"],
         "stop_loss_pct": 2.0, "target_pct": 3.0},
    ],
}


@pytest.fixture
def conn(tmp_path):
    c = app_store.get_db(str(tmp_path / "test_app.db"))
    app_store.init_db(c)
    yield c
    c.close()


def test_builds_one_row_per_pick():
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert len(rows) == 2


def test_symbol_is_stripped_of_exchange_suffix():
    """Clients see CIPLA, never CIPLA.NS."""
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["symbol"] == "CIPLA"


def test_target_and_stop_are_absolute_prices_not_percentages():
    """The scorer gives percentages; a call must record the actual levels."""
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["target"] == pytest.approx(1420.0 * 1.02)
    assert rows[0]["stop"] == pytest.approx(1420.0 * 0.985)


def test_signal_is_plain_english_joined_reasons():
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["signal"] == "Reclaimed VWAP; Volume 2.1x average"


def test_id_is_stable_for_symbol_and_day():
    """Same symbol, same day, same id -- so a re-run collides deterministically."""
    a = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")[0]["id"]
    b = publish_calls.build_rows(PAYLOAD, "2026-08-28T15:10:00")[0]["id"]
    assert a == b


def test_side_comes_from_direction():
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["side"] == "BUY"


def test_rejects_non_stock_categories():
    """/api/picks?category=etfs returns hardcoded literal arrays with invented
    recommendation strings. Those must never become calls shown to a client."""
    with pytest.raises(ValueError, match="stocks"):
        publish_calls.build_rows({"category": "etfs", "picks": []},
                                 "2026-08-28T09:20:00")


def test_insert_is_idempotent(conn):
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert publish_calls.insert_rows(conn, rows) == 2
    assert publish_calls.insert_rows(conn, rows) == 0
    assert conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 2


def test_inserted_calls_start_open(conn):
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    publish_calls.insert_rows(conn, rows)
    outcomes = {r["outcome"] for r in conn.execute("SELECT outcome FROM calls")}
    assert outcomes == {"open"}


def test_empty_picks_inserts_nothing_and_does_not_raise(conn):
    rows = publish_calls.build_rows({"category": "stocks", "picks": []},
                                    "2026-08-28T09:20:00")
    assert publish_calls.insert_rows(conn, rows) == 0
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_publish_calls.py -q
```

Expected: collection error — `scripts/publish-calls.py` does not exist.

- [ ] **Step 3: Write the job**

Create `scripts/publish-calls.py`:

```python
#!/usr/bin/env python3
"""Capture today's published calls into the `calls` table.

This job is the ONLY writer of `calls`. Everything the track record later
claims rests on it: if calls could be written from anywhere, "we called this"
stops being falsifiable.

It reads the SAME HTTP endpoint the product serves rather than calling the
scorer directly, so what is recorded is by construction what was published --
not a recomputation that might differ.

STOCKS ONLY. /api/picks?category=etfs and ?category=mf return hardcoded literal
arrays with invented recommendation strings; they are not model output and must
never enter the record.

Exit code 0 on success, 1 on any failure. Failure must be loud: a missing day
in the record is worse than a visible gap.
"""
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store

PICKS_URL = os.environ.get(
    "TP_PICKS_URL", "http://127.0.0.1:5050/api/picks?category=stocks&count=10")


def fetch_picks(url):
    """GET the picks payload. Raises on any non-200 or unparseable body."""
    with urllib.request.urlopen(url, timeout=30) as r:
        if r.status != 200:
            raise RuntimeError("picks endpoint returned HTTP %s" % r.status)
        return json.loads(r.read().decode("utf-8"))


def build_rows(payload, published_at):
    """Map a picks payload to `calls` rows. Pure -- no I/O, no clock."""
    category = payload.get("category", "stocks")
    if category != "stocks":
        raise ValueError(
            "refusing category %r: only 'stocks' is model output. etfs and mf "
            "are hardcoded literals and must never become calls." % category)

    day = published_at[:10]
    horizon = payload.get("horizon", "intraday")
    rows = []
    for p in payload.get("picks", []):
        symbol = str(p.get("symbol", "")).replace(".NS", "").replace(".BO", "")
        if not symbol:
            continue
        price = float(p.get("price") or 0)
        if price <= 0:
            continue
        sl_pct = float(p.get("stop_loss_pct") or 0)
        tgt_pct = float(p.get("target_pct") or 0)
        reasons = p.get("reasons") or []
        rows.append({
            # Deterministic: a re-run on the same day produces the same id, so
            # the unique index collides instead of inserting a near-duplicate.
            "id": "call-%s-%s" % (symbol, day),
            "symbol": symbol,
            "side": "BUY" if str(p.get("direction", "UP")).upper() == "UP" else "SELL",
            "published_at": published_at,
            "price_at_call": price,
            "score": float(p.get("score") or 0),
            "signal": "; ".join(str(r) for r in reasons) or None,
            "horizon": horizon,
            "target": round(price * (1 + tgt_pct / 100.0), 2) if tgt_pct else None,
            "stop": round(price * (1 - sl_pct / 100.0), 2) if sl_pct else None,
        })
    return rows


def insert_rows(conn, rows):
    """Insert rows, skipping any that already exist. Returns the insert count."""
    inserted = 0
    for r in rows:
        try:
            conn.execute(
                "INSERT INTO calls (id, symbol, side, published_at, price_at_call,"
                " score, signal, horizon, target, stop)"
                " VALUES (:id, :symbol, :side, :published_at, :price_at_call,"
                " :score, :signal, :horizon, :target, :stop)", r)
            inserted += 1
        except sqlite3.IntegrityError:
            # Already recorded today. Expected on a re-run; not an error.
            pass
    conn.commit()
    return inserted


def main():
    published_at = datetime.now().isoformat(timespec="seconds")
    try:
        payload = fetch_picks(PICKS_URL)
        rows = build_rows(payload, published_at)
        conn = app_store.get_db()
        app_store.init_db(conn)
        n = insert_rows(conn, rows)
        conn.close()
    except Exception as e:
        print("PUBLISH FAILED %s: %s: %s" % (published_at, type(e).__name__, e),
              file=sys.stderr)
        return 1
    print("published %d call(s) of %d pick(s) at %s" % (n, len(rows), published_at))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 -m pytest tests/test_publish_calls.py -q
```

Expected: 10 passed.

- [ ] **Step 5: Run it for real against the live app**

Start the app on a port that is not 5050 if 5050 is occupied by someone else's server, then:

```bash
python3 prototype/app.py &
sleep 5
python3 scripts/publish-calls.py
```

Expected: `published N call(s) of N pick(s) at ...`. Run it a SECOND time immediately — expected `published 0 call(s) of N pick(s)`, proving idempotency against the real database. Then kill the server you started.

- [ ] **Step 6: Confirm the whole suite still passes, then commit**

```bash
python3 -m pytest tests/ -q
git add scripts/publish-calls.py tests/test_publish_calls.py
git commit -m "feat(calls): capture what was published, once per symbol per day

Reads the same HTTP endpoint the product serves rather than recomputing from
the scorer, so the record is by construction what was published.

Stocks only. /api/picks?category=etfs and ?category=mf return hardcoded arrays
with invented recommendation strings -- harmless on an operator screen, not
something to record as a call and later publish a hit rate for."
```

---

### Task 3: The resolver

**Files:**
- Create: `scripts/resolve-calls.py`
- Create: `tests/test_resolve_calls.py`

**Interfaces:**
- Consumes: `app_store.get_db(path)`, `app_store.init_db(conn)`.
- Produces:
  - `resolve_calls.HORIZON_DAYS` → `dict` mapping horizon name to days: `{"intraday": 1, "swing": 7, "investment": 30}`
  - `resolve_calls.is_elapsed(published_at, horizon, now)` → `bool`. Pure.
  - `resolve_calls.classify(side, price_at_call, outcome_price, target)` → `"hit"` or `"miss"`. Pure. Note there is no `stop` parameter — a stop is not what grades a call.
  - `resolve_calls.due_calls(conn, now)` → list of `sqlite3.Row` whose horizon has elapsed and `outcome = 'open'`.
  - `resolve_calls.apply_outcome(conn, call_id, outcome_price, outcome, now)` → `None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resolve_calls.py`:

```python
"""Tests for the resolver.

The single rule that protects the track record from overstating itself: a call
still inside its horizon stays `open` and is never counted.
"""
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(REPO_ROOT, relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


resolve_calls = _load("resolve_calls", "scripts/resolve-calls.py")


@pytest.fixture
def conn(tmp_path):
    c = app_store.get_db(str(tmp_path / "test_app.db"))
    app_store.init_db(c)
    yield c
    c.close()


def _add(conn, cid, symbol, published_at, horizon="intraday", price=1000.0):
    conn.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call,"
        " horizon, target, stop) VALUES (?,?,?,?,?,?,?,?)",
        (cid, symbol, "BUY", published_at, price, horizon, price * 1.02, price * 0.985))
    conn.commit()


def test_call_inside_its_horizon_is_not_due(conn):
    """The property that stops the record overstating itself."""
    _add(conn, "c1", "CIPLA", "2026-08-28T09:20:00", "intraday")
    assert resolve_calls.due_calls(conn, "2026-08-28T15:00:00") == []


def test_call_past_its_horizon_is_due(conn):
    _add(conn, "c1", "CIPLA", "2026-08-28T09:20:00", "intraday")
    due = resolve_calls.due_calls(conn, "2026-08-30T09:20:00")
    assert [r["id"] for r in due] == ["c1"]


def test_swing_horizon_is_longer_than_intraday(conn):
    _add(conn, "c1", "CIPLA", "2026-08-28T09:20:00", "swing")
    assert resolve_calls.due_calls(conn, "2026-08-30T09:20:00") == []
    assert len(resolve_calls.due_calls(conn, "2026-09-05T09:20:00")) == 1


def test_already_resolved_call_is_not_due_again(conn):
    _add(conn, "c1", "CIPLA", "2026-08-28T09:20:00", "intraday")
    resolve_calls.apply_outcome(conn, "c1", 1050.0, "hit", "2026-08-30T18:00:00")
    assert resolve_calls.due_calls(conn, "2026-09-30T09:20:00") == []


def test_buy_above_target_is_a_hit():
    assert resolve_calls.classify("BUY", 1000.0, 1025.0, 1020.0) == "hit"


def test_buy_below_entry_is_a_miss():
    assert resolve_calls.classify("BUY", 1000.0, 980.0, 1020.0) == "miss"


def test_buy_up_but_short_of_target_is_a_miss():
    """Only reaching the published target counts. Partial moves are not wins."""
    assert resolve_calls.classify("BUY", 1000.0, 1010.0, 1020.0) == "miss"


def test_sell_below_target_is_a_hit():
    assert resolve_calls.classify("SELL", 1000.0, 975.0, 980.0) == "hit"


def test_call_with_no_target_grades_against_the_call_price():
    """build_rows sets target=None when the scorer returns target_pct = 0.

    Without a fallback every such call scores a miss, biasing the whole record
    downward for a reason that has nothing to do with the calls being wrong.
    """
    assert resolve_calls.classify("BUY", 1000.0, 1030.0, None) == "hit"
    assert resolve_calls.classify("BUY", 1000.0, 970.0, None) == "miss"
    assert resolve_calls.classify("SELL", 1000.0, 970.0, None) == "hit"


def test_flat_is_never_a_hit_when_there_was_no_target():
    """Going nowhere is not a win."""
    assert resolve_calls.classify("BUY", 1000.0, 1000.0, None) == "miss"


def test_apply_outcome_writes_all_three_fields(conn):
    _add(conn, "c1", "CIPLA", "2026-08-28T09:20:00", "intraday")
    resolve_calls.apply_outcome(conn, "c1", 1050.0, "hit", "2026-08-30T18:00:00")
    r = conn.execute("SELECT outcome, outcome_price, outcome_at FROM calls"
                     " WHERE id='c1'").fetchone()
    assert r["outcome"] == "hit"
    assert r["outcome_price"] == 1050.0
    assert r["outcome_at"] == "2026-08-30T18:00:00"


def test_is_elapsed_is_pure_and_boundary_inclusive():
    assert resolve_calls.is_elapsed("2026-08-28T09:20:00", "intraday",
                                    "2026-08-29T09:20:00") is True
    assert resolve_calls.is_elapsed("2026-08-28T09:20:00", "intraday",
                                    "2026-08-28T23:59:00") is False


def test_unknown_horizon_falls_back_to_intraday():
    assert resolve_calls.is_elapsed("2026-08-28T09:20:00", "nonsense",
                                    "2026-08-30T09:20:00") is True
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_resolve_calls.py -q
```

Expected: collection error — `scripts/resolve-calls.py` does not exist.

- [ ] **Step 3: Write the resolver**

Create `scripts/resolve-calls.py`:

```python
#!/usr/bin/env python3
"""Fill in what actually happened to each published call.

One rule matters above the others: a call still inside its horizon stays
`open` and is never counted in a hit rate. Resolving early is how a track
record quietly starts overstating itself.

A call is a `hit` only if it reached the target that was published with it.
A favourable-but-short move is a miss. Grading on anything softer would make
the published target decorative.

Exit code 0 on success, 1 on any failure.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store

HORIZON_DAYS = {"intraday": 1, "swing": 7, "investment": 30}

QUOTE_URL = os.environ.get("TP_QUOTE_URL", "http://127.0.0.1:5050/api/stock/%s")


def is_elapsed(published_at, horizon, now):
    """Has this call's horizon passed? Pure -- `now` is supplied, never read."""
    days = HORIZON_DAYS.get(horizon or "intraday", HORIZON_DAYS["intraday"])
    due = datetime.fromisoformat(published_at) + timedelta(days=days)
    return datetime.fromisoformat(now) >= due


def classify(side, price_at_call, outcome_price, target):
    """hit only if the published target was reached. Everything else is a miss.

    When no target was published -- the scorer can return target_pct = 0, and
    build_rows stores None -- the bar falls back to the call price and requires
    a strict move, so flat is not a win. Without that fallback every
    target-less call would score a miss and bias the record downward for a
    reason that has nothing to do with the calls being wrong.

    There is deliberately no `stop` parameter. A stop bounds a loss; it does
    not grade whether the call was right.
    """
    if target is not None:
        return "hit" if (outcome_price <= target if side == "SELL"
                         else outcome_price >= target) else "miss"
    return "hit" if (outcome_price < price_at_call if side == "SELL"
                     else outcome_price > price_at_call) else "miss"


def due_calls(conn, now):
    """Open calls whose horizon has elapsed."""
    rows = conn.execute(
        "SELECT * FROM calls WHERE outcome = 'open' ORDER BY published_at").fetchall()
    return [r for r in rows if is_elapsed(r["published_at"], r["horizon"], now)]


def apply_outcome(conn, call_id, outcome_price, outcome, now):
    """Record the result. Writes all three outcome fields together."""
    conn.execute(
        "UPDATE calls SET outcome_price = ?, outcome = ?, outcome_at = ?"
        " WHERE id = ?", (outcome_price, outcome, now, call_id))
    conn.commit()


def fetch_price(symbol):
    """Current price for a symbol, or None if unavailable."""
    with urllib.request.urlopen(QUOTE_URL % symbol, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    price = data.get("price") or data.get("current_price")
    return float(price) if price else None


def main():
    now = datetime.now().isoformat(timespec="seconds")
    resolved, skipped = 0, 0
    try:
        conn = app_store.get_db()
        app_store.init_db(conn)
        for row in due_calls(conn, now):
            price = fetch_price(row["symbol"])
            if price is None:
                # No price is not a miss. Leave it open and try again tomorrow.
                skipped += 1
                continue
            outcome = classify(row["side"], row["price_at_call"], price,
                               row["target"])
            apply_outcome(conn, row["id"], price, outcome, now)
            resolved += 1
        conn.close()
    except Exception as e:
        print("RESOLVE FAILED %s: %s: %s" % (now, type(e).__name__, e),
              file=sys.stderr)
        return 1
    print("resolved %d call(s), %d left open for want of a price" % (resolved, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 -m pytest tests/test_resolve_calls.py -q
```

Expected: 13 passed.

- [ ] **Step 5: Confirm the whole suite still passes, then commit**

```bash
python3 -m pytest tests/ -q
git add scripts/resolve-calls.py tests/test_resolve_calls.py
git commit -m "feat(calls): resolve outcomes, and only when the horizon has passed

A call inside its horizon stays open and is never counted -- resolving early
is how a track record quietly starts overstating itself.

A hit requires reaching the target published with the call. A favourable but
short move is a miss, because grading on anything softer would make the
published target decorative. A missing price leaves the call open rather than
recording a miss it did not earn."
```

---

### Task 4: Scheduling and visibility

A pipeline nobody can see the state of is a pipeline that stops without anyone noticing. This task makes it observable, then schedules it.

**Files:**
- Create: `scripts/calls-status.py`
- Create: `docs/CALLS_PIPELINE.md`
- Create: `tests/test_calls_status.py`

**Interfaces:**
- Consumes: `app_store.get_db(path)`, `app_store.init_db(conn)`.
- Produces: `calls_status.summarise(conn, now)` → `dict` with keys `total`, `open`, `resolved`, `hit`, `miss`, `hit_rate`, `first_call`, `last_call`, `days_covered`, `gaps`. `hit_rate` is `None` when `resolved` is 0 — never `0.0`, which would read as "we get everything wrong".

- [ ] **Step 1: Write the failing tests**

Create `tests/test_calls_status.py`:

```python
"""Tests for the pipeline status summary."""
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(REPO_ROOT, relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


calls_status = _load("calls_status", "scripts/calls-status.py")


@pytest.fixture
def conn(tmp_path):
    c = app_store.get_db(str(tmp_path / "test_app.db"))
    app_store.init_db(c)
    yield c
    c.close()


def _add(conn, cid, symbol, day, outcome="open"):
    conn.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call, outcome)"
        " VALUES (?,?,?,?,?,?)",
        (cid, symbol, "BUY", day + "T09:20:00", 1000.0, outcome))
    conn.commit()


def test_empty_store_reports_zero_not_an_error(conn):
    s = calls_status.summarise(conn, "2026-08-28T18:00:00")
    assert s["total"] == 0
    assert s["hit_rate"] is None


def test_hit_rate_is_none_when_nothing_resolved(conn):
    """None, never 0.0 -- zero would read as 'we get everything wrong'."""
    _add(conn, "c1", "CIPLA", "2026-08-28")
    s = calls_status.summarise(conn, "2026-08-28T18:00:00")
    assert s["open"] == 1
    assert s["resolved"] == 0
    assert s["hit_rate"] is None


def test_hit_rate_counts_only_resolved_calls(conn):
    _add(conn, "c1", "CIPLA", "2026-08-26", "hit")
    _add(conn, "c2", "TITAN", "2026-08-26", "miss")
    _add(conn, "c3", "SUNTV", "2026-08-28", "open")
    s = calls_status.summarise(conn, "2026-08-28T18:00:00")
    assert s["resolved"] == 2
    assert s["hit_rate"] == 50.0


def test_gaps_lists_weekdays_with_no_calls(conn):
    """A day the job did not run is the failure this whole script exists to show."""
    _add(conn, "c1", "CIPLA", "2026-08-26")   # Wednesday
    _add(conn, "c2", "TITAN", "2026-08-28")   # Friday
    s = calls_status.summarise(conn, "2026-08-28T18:00:00")
    assert "2026-08-27" in s["gaps"]


def test_weekends_are_not_gaps(conn):
    _add(conn, "c1", "CIPLA", "2026-08-28")   # Friday
    _add(conn, "c2", "TITAN", "2026-08-31")   # Monday
    s = calls_status.summarise(conn, "2026-08-31T18:00:00")
    assert "2026-08-29" not in s["gaps"]      # Saturday
    assert "2026-08-30" not in s["gaps"]      # Sunday
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_calls_status.py -q
```

Expected: collection error — `scripts/calls-status.py` does not exist.

- [ ] **Step 3: Write the status script**

Create `scripts/calls-status.py`:

```python
#!/usr/bin/env python3
"""Print the state of the calls record.

A capture pipeline nobody can see is a pipeline that stops without anyone
noticing -- and every day it is stopped is a day of proof that cannot be
recovered. Run this whenever you want to know the record is alive.
"""
import os
import sys
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


def summarise(conn, now):
    """Aggregate the record. `now` is supplied so this stays testable."""
    rows = conn.execute("SELECT published_at, outcome FROM calls").fetchall()
    total = len(rows)
    hit = sum(1 for r in rows if r["outcome"] == "hit")
    miss = sum(1 for r in rows if r["outcome"] == "miss")
    open_ = sum(1 for r in rows if r["outcome"] == "open")
    resolved = hit + miss

    days = sorted({r["published_at"][:10] for r in rows})
    gaps = []
    if days:
        cur = datetime.fromisoformat(days[0]).date()
        end = datetime.fromisoformat(now[:10]).date()
        have = set(days)
        while cur <= end:
            # Monday is 0, Saturday 5, Sunday 6. A closed market is not a gap.
            if cur.weekday() < 5 and cur.isoformat() not in have:
                gaps.append(cur.isoformat())
            cur += timedelta(days=1)

    return {
        "total": total, "open": open_, "resolved": resolved,
        "hit": hit, "miss": miss,
        # None, never 0.0 -- an unresolved record is not a record of failure.
        "hit_rate": round(100.0 * hit / resolved, 1) if resolved else None,
        "first_call": days[0] if days else None,
        "last_call": days[-1] if days else None,
        "days_covered": len(days),
        "gaps": gaps,
    }


def main():
    conn = app_store.get_db()
    app_store.init_db(conn)
    s = summarise(conn, datetime.now().isoformat(timespec="seconds"))
    conn.close()

    print("calls recorded    %d  (%d open, %d resolved)"
          % (s["total"], s["open"], s["resolved"]))
    print("hit rate          %s"
          % ("%.1f%% of %d resolved" % (s["hit_rate"], s["resolved"])
             if s["hit_rate"] is not None else "-- (nothing resolved yet)"))
    print("covering          %s to %s  (%d trading days)"
          % (s["first_call"] or "--", s["last_call"] or "--", s["days_covered"]))
    if s["gaps"]:
        print("MISSING DAYS      %d: %s" % (len(s["gaps"]), ", ".join(s["gaps"][:10])))
        return 1
    print("gaps              none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 -m pytest tests/test_calls_status.py -q
```

Expected: 5 passed.

- [ ] **Step 5: Write the operator documentation**

Create `docs/CALLS_PIPELINE.md`:

```markdown
# Calls capture pipeline

Records what TradePilot published, and what happened to it. The track record
shown to clients is a query over this and nothing else.

**This is time-sensitive.** Every day the publish job does not run is a day of
proof that cannot be recovered — the record cannot be backfilled without
retroactively labelling engine history as calls, which the design rejects.

## The jobs

| Job | When | What it does |
|:--|:--|:--|
| `scripts/publish-calls.py` | 09:20 IST, weekdays | Fetches `/api/picks?category=stocks` and writes one row per pick |
| `scripts/resolve-calls.py` | 18:30 IST, weekdays | Fills the outcome for calls whose horizon has elapsed |
| `scripts/calls-status.py` | on demand | Prints the state of the record; exits 1 if there are missing weekdays |

Both jobs require `prototype/app.py` to be running — they read the same HTTP
endpoints the product serves, so the record is by construction what was
published rather than a recomputation that might differ.

## Checking it is alive

```bash
python3 scripts/calls-status.py
```

Non-zero exit means missing weekdays. Investigate before they accumulate.

## Rules that must not be relaxed

- The publish job is the **only** writer of `calls`.
- **Stocks only.** `/api/picks?category=etfs` and `?category=mf` return
  hardcoded literal arrays with invented recommendation strings. They are not
  model output and must never be recorded as calls.
- A call inside its horizon stays `open` and is never counted in a hit rate.
- A hit requires reaching the target published with the call.
- A missing price leaves a call open rather than recording a miss it did not earn.
```

- [ ] **Step 6: Schedule both jobs**

Create the two launchd agents. Replace `YOURNAME` with the output of `whoami`:

```bash
cat > ~/Library/LaunchAgents/co.tradepilot.publish-calls.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>co.tradepilot.publish-calls</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>/Users/YOURNAME/Documents/tinker/projects/tradepilot/scripts/publish-calls.py</string>
  </array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>1</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>2</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>3</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>4</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>5</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/tmp/tradepilot-publish-calls.log</string>
  <key>StandardErrorPath</key><string>/tmp/tradepilot-publish-calls.log</string>
</dict></plist>
EOF

cat > ~/Library/LaunchAgents/co.tradepilot.resolve-calls.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>co.tradepilot.resolve-calls</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>/Users/YOURNAME/Documents/tinker/projects/tradepilot/scripts/resolve-calls.py</string>
  </array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>1</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>2</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>3</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>4</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>5</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/tmp/tradepilot-resolve-calls.log</string>
  <key>StandardErrorPath</key><string>/tmp/tradepilot-resolve-calls.log</string>
</dict></plist>
EOF

launchctl load ~/Library/LaunchAgents/co.tradepilot.publish-calls.plist
launchctl load ~/Library/LaunchAgents/co.tradepilot.resolve-calls.plist
launchctl list | grep tradepilot
```

Expected: both labels listed. Both plists are written out in full rather than
derived from one another — a `sed` that rewrites `<integer>` values would also
match the `Weekday` entries.

- [ ] **Step 7: Confirm the whole suite passes, then commit**

```bash
python3 -m pytest tests/ -q
git add scripts/calls-status.py tests/test_calls_status.py docs/CALLS_PIPELINE.md
git commit -m "feat(calls): make the pipeline observable, and schedule it

A capture pipeline nobody can see is one that stops without anyone noticing,
and every stopped day is proof that cannot be recovered. calls-status prints
the record and exits non-zero on missing weekdays, so a silence becomes a
signal.

Weekends are not gaps. An unresolved record reports a hit rate of None rather
than 0.0, which would read as getting everything wrong."
```

---

## Verification

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/ -q
```

Expected: **219 passing** (184 existing + 7 + 10 + 13 + 5).

The plan is complete when all of the following also hold:

| | Check |
|:---:|:--|
| ☐ | `python3 scripts/publish-calls.py` twice in a row inserts N then 0 |
| ☐ | `python3 scripts/calls-status.py` prints a record and exits 0 |
| ☐ | `prototype/tradepilot_app.db` exists and is separate from `tradepilot_analytics.db` |
| ☐ | `launchctl list \| grep tradepilot` shows both agents |
| ☐ | No `.NS` suffix appears in any recorded symbol |
| ☐ | No ETF or mutual-fund symbol appears in `calls` |

## Not in this plan

The `/app` client dashboard — five screens and eight endpoints — is the second
plan against this spec. It consumes the `calls` and `positions` tables this plan
creates, and can be built against a stubbed `current_user()` without waiting for
project B. Nothing in the dashboard is a prerequisite for this pipeline; the
reverse is not true, which is why this one ships first.
