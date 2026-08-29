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
