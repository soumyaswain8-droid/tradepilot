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
