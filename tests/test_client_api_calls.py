"""Client-facing call data.

These endpoints read the `calls` table and nothing else. /api/picks computes
live and stores nothing, so serving it would show a client a call that was
never published and never recorded -- the distinction the whole track record
rests on.
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
    """A throwaway database wired into the API, never the real record."""
    path = str(tmp_path / "api.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_api, "open_store", lambda: app_store.get_db(path))
    yield conn
    conn.close()


def _add_call(conn, cid, symbol, published_at, outcome="open", **kw):
    conn.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call,"
        " score, signal, horizon, target, stop, outcome, outcome_price)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (cid, symbol, kw.get("side", "BUY"), published_at,
         kw.get("price_at_call", 1000.0), kw.get("score", 73.0),
         kw.get("signal", "Reclaimed VWAP; volume 2.1x"),
         kw.get("horizon", "intraday"), kw.get("target", 1020.0),
         kw.get("stop", 985.0), outcome, kw.get("outcome_price")))
    conn.commit()


def test_empty_table_returns_an_empty_list_not_an_error(client, store):
    r = client.get("/api/app/calls")
    assert r.status_code == 200
    assert r.get_json()["calls"] == []


def test_calls_are_returned_newest_first(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-26T09:20:00")
    _add_call(store, "c2", "TITAN", "2026-08-28T09:20:00")
    symbols = [c["symbol"] for c in client.get("/api/app/calls").get_json()["calls"]]
    assert symbols == ["TITAN", "CIPLA"]


def test_a_call_carries_its_plain_english_reason(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00")
    call = client.get("/api/app/calls").get_json()["calls"][0]
    assert call["signal"] == "Reclaimed VWAP; volume 2.1x"


def test_no_engine_vocabulary_leaks_to_a_client(client, store):
    """A client sees what was called, never which engine said so."""
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00")
    body = client.get("/api/app/calls").get_data(as_text=True).lower()
    for word in ("v4", "v5_size", "composite_scorer", "alpha-hunter", "engine"):
        assert word not in body


def test_call_detail_returns_one_call(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00")
    body = client.get("/api/app/calls/c1").get_json()
    assert body["id"] == "c1"
    assert body["target"] == 1020.0


def test_unknown_call_id_404s_without_leaking(client, store):
    r = client.get("/api/app/calls/nope")
    assert r.status_code == 404
    body = r.get_data(as_text=True).lower()
    for leak in ("sqlite", "select ", "traceback", "prototype/"):
        assert leak not in body


def test_an_open_call_reports_no_outcome(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00", outcome="open")
    call = client.get("/api/app/calls/c1").get_json()
    assert call["outcome"] == "open"
    assert call["outcome_price"] is None


def test_a_resolved_call_reports_its_outcome(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-26T09:20:00",
              outcome="hit", outcome_price=1030.0)
    call = client.get("/api/app/calls/c1").get_json()
    assert call["outcome"] == "hit"
    assert call["outcome_price"] == 1030.0


def test_calls_response_is_bounded_by_default(client, store):
    """The record grows every trading day; the response must not grow with it."""
    for i in range(60):
        _add_call(store, "c%02d" % i, "S%02d" % i, "2026-08-28T09:20:00")
    body = client.get("/api/app/calls").get_json()
    assert body["limit"] == 50
    assert len(body["calls"]) == 50


def test_a_client_cannot_request_the_whole_table(client, store):
    _add_call(store, "c1", "CIPLA", "2026-08-28T09:20:00")
    assert client.get("/api/app/calls?limit=999999").get_json()["limit"] == 500


def test_calls_endpoint_is_public(client, store, monkeypatch):
    """Proof, not policy -- the acquisition surface must work signed out."""
    from prototype import client_auth
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/app/calls").status_code == 200
