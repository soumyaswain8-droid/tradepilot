"""The auth boundary, and the test that keeps it honest.

This app has roughly seventy routes and none of them are protected. The whole
argument for putting client endpoints under one prefix is that protection
becomes a property a test can enumerate, rather than a decorator someone has
to remember. That enumeration is the most important test in this file.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, app_store, client_api, client_auth


@pytest.fixture
def signed_in(client, tmp_path, monkeypatch):
    """A real session, cookie set on the test client. Returns the user id."""
    path = str(tmp_path / "auth.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_auth, "open_store", lambda: app_store.get_db(path))
    monkeypatch.setattr(client_api, "open_store", lambda: app_store.get_db(path))
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    token = accounts.create_session(conn, uid)
    client.set_cookie("localhost", client_auth.COOKIE_NAME, token)
    conn.close()
    return uid


def _app_endpoints(flask_app):
    """Every blueprint endpoint mounted under /api/app.

    Matched on a path boundary, not a substring: a future operator route
    called /api/apply must not be dragged into the client registry.
    """
    return {r.endpoint for r in flask_app.url_map.iter_rules()
            if str(r.rule) == "/api/app" or str(r.rule).startswith("/api/app/")}


def test_every_client_route_is_classified(flask_app):
    """A new endpoint in neither list fails the suite.

    This is the whole payoff of the shared prefix: "did we forget to protect
    something?" stops being a review question and becomes a test result.
    """
    classified = client_auth.PUBLIC_ENDPOINTS | client_auth.GATED_ENDPOINTS
    unclassified = _app_endpoints(flask_app) - classified
    assert unclassified == set(), (
        "these /api/app routes are in neither PUBLIC_ENDPOINTS nor "
        "GATED_ENDPOINTS: %s" % sorted(unclassified))


def test_no_endpoint_is_both_public_and_gated(flask_app):
    """An endpoint in both lists has an ambiguous policy."""
    assert client_auth.PUBLIC_ENDPOINTS & client_auth.GATED_ENDPOINTS == frozenset()


def test_registries_name_only_real_endpoints(flask_app):
    """A registry entry with no matching route is a stale name protecting nothing."""
    declared = client_auth.PUBLIC_ENDPOINTS | client_auth.GATED_ENDPOINTS
    assert declared - _app_endpoints(flask_app) == set()


def test_a_route_merely_starting_with_the_same_letters_is_not_swept_in(flask_app):
    """/api/apply is an operator route, not a client one.

    A substring match would drag it into the client registry and fail the
    enumeration against a route that has nothing to do with this API.
    """
    from flask import Flask
    probe = Flask("probe")

    @probe.route("/api/apply")
    def _apply():
        return ""

    @probe.route("/api/app/thing")
    def _thing():
        return ""

    found = _app_endpoints(probe)
    assert "_thing" in found
    assert "_apply" not in found


def test_gated_endpoint_401s_without_a_user(client, monkeypatch):
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/app/me").status_code == 401


def test_gated_endpoint_allows_a_user(client, signed_in):
    assert client.get("/api/app/me").status_code == 200


def test_me_returns_the_current_user(client, signed_in):
    body = client.get("/api/app/me").get_json()
    assert body["user_id"] == signed_in
    assert body["plan"] == "none"


def test_me_returns_the_signed_in_account_email(client, signed_in):
    body = client.get("/api/app/me").get_json()
    assert body["email"] == "priya@example.com"


def test_no_cookie_means_no_user(client):
    assert client.get("/api/app/me").status_code == 401


def test_a_forged_token_means_no_user(client, signed_in):
    client.set_cookie("localhost", client_auth.COOKIE_NAME, "forged-token")
    assert client.get("/api/app/me").status_code == 401


def test_an_unsafe_method_from_a_foreign_origin_is_refused(client, signed_in):
    r = client.post("/api/app/positions",
                    json={"symbol": "CIPLA", "qty": 1, "avg_price": 10.0},
                    headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403


def test_a_missing_origin_is_not_treated_as_foreign(client, signed_in):
    """CSRF requires a browser sending cookies, and browsers always send
    Origin on an unsafe cross-origin request. A request with no Origin at all
    is curl or a test -- not the threat model -- and rejecting it would break
    every non-browser caller for no security gain."""
    r = client.post("/api/app/positions", json={"symbol": "CIPLA", "qty": 1,
                                                "avg_price": 10.0})
    assert r.status_code == 201


def test_a_matching_host_with_a_different_scheme_is_accepted(client, signed_in):
    """Behind a TLS-terminating proxy the browser's Origin is https:// while
    Flask sees http:// internally. Comparing schemes would refuse every real
    write in production. request.host under the test client is "localhost",
    confirmed directly rather than assumed."""
    r = client.post("/api/app/positions",
                    json={"symbol": "CIPLA", "qty": 1, "avg_price": 10.0},
                    headers={"Origin": "https://" + "localhost"})
    assert r.status_code == 201


def test_the_operator_surface_is_untouched(client):
    """The guard must apply to /api/app only, never to the existing app."""
    assert client.get("/api/indices").status_code == 200


def test_the_operator_surface_stays_open_to_a_signed_out_caller(client, monkeypatch):
    """The guard must scope to /api/app, never to the whole app.

    Without patching current_user to None, the guard's `and` short-circuits
    and this check proves nothing -- it would pass even if every endpoint in
    the app were gated.
    """
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/indices").status_code == 200
    assert client.get("/api/app/me").status_code == 401
