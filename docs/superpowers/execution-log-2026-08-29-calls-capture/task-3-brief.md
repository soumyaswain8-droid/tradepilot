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

