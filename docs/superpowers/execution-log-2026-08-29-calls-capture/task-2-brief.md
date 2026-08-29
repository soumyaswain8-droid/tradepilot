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

