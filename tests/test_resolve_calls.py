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


def test_classify_raises_when_target_is_none():
    """A call published without a target cannot be graded against one.

    Grading it by a softer rule (e.g. against the call price) would pool two
    different standards into a single published hit rate. main() handles the
    None-target case itself by marking the call 'ungraded' and excluding it,
    rather than calling classify() at all.
    """
    with pytest.raises(ValueError, match="target"):
        resolve_calls.classify("BUY", 1000.0, 1030.0, None)
    with pytest.raises(ValueError, match="target"):
        resolve_calls.classify("SELL", 1000.0, 970.0, None)


def test_due_call_with_no_target_is_marked_ungraded(conn, tmp_path, monkeypatch):
    """main() must exclude a target-less call, not grade it by a softer rule.

    main() closes its connection on the way out, so reopen the same on-disk
    db afterward to read back what it wrote.
    """
    conn.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call,"
        " horizon, target, stop) VALUES (?,?,?,?,?,?,?,?)",
        ("c1", "NOTARGET", "BUY", "2026-08-28T09:20:00", 1000.0, "intraday",
         None, None))
    conn.commit()

    db_path = str(tmp_path / "test_app.db")
    orig_get_db = app_store.get_db
    monkeypatch.setattr(resolve_calls, "fetch_price", lambda symbol: 1030.0)
    monkeypatch.setattr(resolve_calls.app_store, "get_db",
                         lambda path=None: orig_get_db(db_path))
    monkeypatch.setattr(resolve_calls.app_store, "init_db", lambda c: None)

    rc = resolve_calls.main()
    assert rc == 0

    check = orig_get_db(db_path)
    row = check.execute(
        "SELECT outcome, outcome_price FROM calls WHERE id='c1'").fetchone()
    check.close()
    assert row["outcome"] == "ungraded"
    assert row["outcome_price"] == 1030.0


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


def test_unknown_horizon_falls_back_to_the_longest_window():
    """An unrecognised horizon must resolve LATE, never early.

    publish-calls writes whatever horizon the payload carries. If a new
    horizon type is added to the scorer and not mirrored into HORIZON_DAYS,
    falling back to intraday would grade a 30-day call after one day and
    report success. Erring long leaves it open and visible instead.
    """
    # Two days on: intraday would already be due. The fallback must not be.
    assert resolve_calls.is_elapsed("2026-08-28T09:20:00", "nonsense",
                                    "2026-08-30T09:20:00") is False
    # Thirty-one days on: past even the longest window, so now it is due.
    assert resolve_calls.is_elapsed("2026-08-28T09:20:00", "nonsense",
                                    "2026-09-28T09:20:00") is True


def test_one_failing_quote_does_not_abandon_the_rest(conn, tmp_path, monkeypatch, capsys):
    """A flaky quote for one symbol must not cost the others their cycle.

    main() closes its connection on the way out (by design, for the real CLI
    path), so `conn` from the fixture is unusable for assertions afterward.
    Reopen the same on-disk db to read back what main() actually wrote.
    """
    for i, sym in enumerate(("AAA", "BBB", "CCC")):
        _add(conn, "c%d" % i, sym, "2026-08-28T09:20:00", "intraday", 1000.0)

    def flaky(symbol):
        if symbol == "BBB":
            raise RuntimeError("quote endpoint down")
        return 1030.0

    db_path = str(tmp_path / "test_app.db")
    orig_get_db = app_store.get_db
    monkeypatch.setattr(resolve_calls, "fetch_price", flaky)
    monkeypatch.setattr(resolve_calls.app_store, "get_db",
                         lambda path=None: orig_get_db(db_path))
    monkeypatch.setattr(resolve_calls.app_store, "init_db", lambda c: None)

    rc = resolve_calls.main()

    check = orig_get_db(db_path)
    outcomes = {r["symbol"]: r["outcome"]
                for r in check.execute("SELECT symbol, outcome FROM calls")}
    check.close()
    assert outcomes["AAA"] == "hit"
    assert outcomes["CCC"] == "hit"
    assert outcomes["BBB"] == "open"   # left for tomorrow, not graded a miss
    assert rc == 1                      # still loud about the failure
