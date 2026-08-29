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
    """An empty table summarises cleanly rather than raising."""
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
    """Open calls do not dilute or inflate the hit rate."""
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
    """The market is shut on Saturday and Sunday -- that is not a missed run."""
    _add(conn, "c1", "CIPLA", "2026-08-28")   # Friday
    _add(conn, "c2", "TITAN", "2026-08-31")   # Monday
    s = calls_status.summarise(conn, "2026-08-31T18:00:00")
    assert "2026-08-29" not in s["gaps"]      # Saturday
    assert "2026-08-30" not in s["gaps"]      # Sunday


def test_main_on_empty_store_is_loud_and_exits_nonzero(conn, monkeypatch, capsys):
    """A pipeline that never ran must not look like one running perfectly.

    This is the only failure mode with no time bound -- there is no future
    date at which an empty store starts reporting gaps on its own.
    """
    monkeypatch.setattr(calls_status.app_store, "get_db", lambda path=None: conn)
    monkeypatch.setattr(calls_status.app_store, "init_db", lambda c: None)
    rc = calls_status.main()
    out = capsys.readouterr().out
    assert rc == 1
    assert "NO CALLS EVER RECORDED" in out


def test_main_with_a_missing_weekday_exits_nonzero(conn, monkeypatch, capsys):
    """The non-zero exit IS the alerting mechanism -- assert it, not just gaps."""
    _add(conn, "c1", "CIPLA", "2026-08-26")   # Wednesday
    _add(conn, "c2", "TITAN", "2026-08-28")   # Friday -- Thursday is missing
    monkeypatch.setattr(calls_status.app_store, "get_db", lambda path=None: conn)
    monkeypatch.setattr(calls_status.app_store, "init_db", lambda c: None)
    rc = calls_status.main()
    assert rc == 1
    assert "MISSING DAYS" in capsys.readouterr().out
