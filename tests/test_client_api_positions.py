"""The client's own book.

One rule dominates: never zero-fill a missing price. kite_data.get_quotes
omits symbols it cannot fetch, deliberately -- "a silent 0.0 price is how bad
fills happen". A position whose quote is missing must say so, not report a
portfolio worth nothing.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, app_store, client_api, client_auth


@pytest.fixture
def store(client, tmp_path, monkeypatch):
    path = str(tmp_path / "api.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_api, "open_store", lambda: app_store.get_db(path))
    monkeypatch.setattr(client_auth, "open_store", lambda: app_store.get_db(path))
    monkeypatch.setattr(client_api, "fetch_quotes",
                        lambda syms: {s: {"last_price": 1100.0, "change_pct": 1.0}
                                      for s in syms})
    # A real signed-in user, so every _post(client) call below authenticates
    # exactly as a browser would -- these positions endpoints are gated.
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    token = accounts.create_session(conn, uid)
    client.set_cookie("localhost", client_auth.COOKIE_NAME, token)
    yield conn
    conn.close()


def _post(client, **kw):
    payload = {"symbol": "CIPLA", "qty": 10, "avg_price": 1000.0}
    payload.update(kw)
    return client.post("/api/app/positions", json=payload)


def test_empty_book_returns_an_empty_list(client, store):
    body = client.get("/api/app/positions").get_json()
    assert body["positions"] == []
    assert body["totals"]["value"] == 0


def test_logging_a_trade_returns_201_and_the_position(client, store):
    r = _post(client)
    assert r.status_code == 201
    assert r.get_json()["symbol"] == "CIPLA"


def test_a_logged_position_appears_in_the_book(client, store):
    _post(client)
    assert len(client.get("/api/app/positions").get_json()["positions"]) == 1


def test_positions_are_marked_to_market(client, store):
    _post(client)                       # 10 @ 1000, quote 1100
    pos = client.get("/api/app/positions").get_json()["positions"][0]
    assert pos["last_price"] == 1100.0
    assert pos["value"] == 11000.0
    assert pos["pnl"] == 1000.0
    assert pos["pnl_pct"] == 10.0


def test_a_missing_quote_is_reported_not_zero_filled(client, store, monkeypatch):
    """A silent 0.0 would show a real holding as worthless."""
    monkeypatch.setattr(client_api, "fetch_quotes", lambda syms: {})
    _post(client)
    pos = client.get("/api/app/positions").get_json()["positions"][0]
    assert pos["price_unavailable"] is True
    assert pos["last_price"] is None
    assert pos["value"] is None
    assert pos["pnl"] is None


def test_totals_exclude_positions_with_no_price(client, store, monkeypatch):
    """A portfolio total must never silently omit a holding's cost basis."""
    monkeypatch.setattr(client_api, "fetch_quotes",
                        lambda syms: {"CIPLA": {"last_price": 1100.0, "change_pct": 1.0}})
    _post(client, symbol="CIPLA")
    _post(client, symbol="TITAN")
    totals = client.get("/api/app/positions").get_json()["totals"]
    assert totals["value"] == 11000.0
    assert totals["priced"] == 1
    assert totals["unpriced"] == 1


def test_provenance_defaults_to_the_clients_own_idea(client, store):
    pos = _post(client).get_json()
    assert pos["call_id"] is None
    assert pos["source"] == "manual"


def test_a_position_can_cite_the_call_that_triggered_it(client, store):
    store.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call)"
        " VALUES ('c1','CIPLA','BUY','2026-08-28T09:20:00',1000.0)")
    store.commit()
    pos = _post(client, call_id="c1").get_json()
    assert pos["call_id"] == "c1"


def test_a_position_citing_an_unknown_call_is_rejected(client, store):
    r = _post(client, call_id="nope")
    assert r.status_code == 400


def test_missing_required_fields_are_rejected(client, store):
    assert client.post("/api/app/positions", json={"symbol": "CIPLA"}).status_code == 400


def test_a_non_positive_quantity_is_rejected(client, store):
    assert _post(client, qty=0).status_code == 400
    assert _post(client, qty=-5).status_code == 400


def test_create_rejects_a_non_string_opened_at(client, store):
    """A dict here raises ProgrammingError, which the IntegrityError handler misses."""
    for bad in ({"a": 1}, [1, 2], 12345):
        r = client.post("/api/app/positions",
                        json={"symbol": "CIPLA", "qty": 10, "avg_price": 1000,
                              "opened_at": bad})
        assert r.status_code == 400, bad
    assert client.get("/api/app/positions").status_code == 200


def test_closing_a_position_records_the_exit(client, store):
    pid = _post(client).get_json()["id"]
    r = client.patch("/api/app/positions/" + pid,
                     json={"closed_at": "2026-08-29T15:30:00", "exit_price": 1120.0})
    assert r.status_code == 200
    assert r.get_json()["exit_price"] == 1120.0


def test_deleting_a_position_removes_it(client, store):
    pid = _post(client).get_json()["id"]
    assert client.delete("/api/app/positions/" + pid).status_code == 204
    assert client.get("/api/app/positions").get_json()["positions"] == []


def test_deleting_an_unknown_position_404s(client, store):
    assert client.delete("/api/app/positions/nope").status_code == 404


def test_one_user_never_sees_anothers_book(client, store, monkeypatch):
    """The single most important property in this file."""
    from prototype import client_auth
    _post(client)
    monkeypatch.setattr(client_auth, "current_user", lambda: "someone-else")
    assert client.get("/api/app/positions").get_json()["positions"] == []


def test_another_user_cannot_patch_your_position(client, store, monkeypatch):
    """Scoping is a property of the SQL, and it must stay one."""
    from prototype import client_auth
    pid = _post(client).get_json()["id"]
    monkeypatch.setattr(client_auth, "current_user", lambda: "someone-else")
    r = client.patch("/api/app/positions/" + pid, json={"qty": 999})
    assert r.status_code == 404


def test_another_user_cannot_delete_your_position(client, store, monkeypatch):
    """A real id belonging to someone else, not a made-up one."""
    pid = _post(client).get_json()["id"]
    owner = store.execute("SELECT id FROM users").fetchone()["id"]
    monkeypatch.setattr(client_auth, "current_user", lambda: "someone-else")
    assert client.delete("/api/app/positions/" + pid).status_code == 404
    monkeypatch.setattr(client_auth, "current_user", lambda: owner)
    assert len(client.get("/api/app/positions").get_json()["positions"]) == 1


def test_positions_are_gated(client, store, monkeypatch):
    from prototype import client_auth
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/app/positions").status_code == 401


def test_patch_rejects_a_non_numeric_quantity(client, store):
    """The delayed-failure case: this used to store, then 500 the whole book.

    A string in qty passes SQLite's REAL affinity untouched, and then
    shape_position raises ValueError on every later list request -- so the
    client bricks their own portfolio page with no way to undo it.
    """
    pid = _post(client).get_json()["id"]
    assert client.patch("/api/app/positions/" + pid, json={"qty": "abc"}).status_code == 400
    assert client.get("/api/app/positions").status_code == 200


def test_patch_rejects_null_in_a_not_null_column(client, store):
    pid = _post(client).get_json()["id"]
    assert client.patch("/api/app/positions/" + pid, json={"qty": None}).status_code == 400


def test_patch_rejects_values_post_would_refuse(client, store):
    """One door into the table must not accept what the other rejects."""
    pid = _post(client).get_json()["id"]
    for bad in ({"qty": 0}, {"qty": -5}, {"avg_price": 0}, {"avg_price": -50}):
        assert client.patch("/api/app/positions/" + pid, json=bad).status_code == 400, bad


def test_patch_still_accepts_a_legitimate_close(client, store):
    """The validation must not break the normal path."""
    pid = _post(client).get_json()["id"]
    r = client.patch("/api/app/positions/" + pid,
                     json={"closed_at": "2026-08-29T15:30:00", "exit_price": 1120.0})
    assert r.status_code == 200
    assert r.get_json()["exit_price"] == 1120.0


def test_both_write_paths_reject_the_same_unreal_numbers(client, store):
    """One door into the table must not accept what the other rejects.

    float("inf") <= 0 is False, so infinity slips past the positivity check
    exactly as NaN does -- and either one propagates into value, pnl and the
    portfolio totals.
    """
    for bad in (float("inf"), float("-inf"), float("nan")):
        assert _post(client, qty=bad).status_code == 400, ("POST qty", bad)
        assert _post(client, avg_price=bad).status_code == 400, ("POST avg_price", bad)

    pid = _post(client).get_json()["id"]
    for bad in (float("inf"), float("-inf"), float("nan")):
        assert client.patch("/api/app/positions/" + pid,
                            json={"qty": bad}).status_code == 400, ("PATCH qty", bad)


def test_positions_do_not_leak_the_internal_user_id(client, store):
    """A client has no use for their own internal identifier.

    Harmless while it is a stub; once accounts land it is the app's internal
    key for that person, handed to the browser for no reason any screen needs.
    """
    _post(client)
    pos = client.get("/api/app/positions").get_json()["positions"][0]
    assert "user_id" not in pos
