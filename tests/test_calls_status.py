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
