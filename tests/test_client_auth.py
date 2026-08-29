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

from prototype import client_auth


def _app_endpoints(flask_app):
    """Every blueprint endpoint mounted under /api/app."""
    return {r.endpoint for r in flask_app.url_map.iter_rules()
            if str(r.rule).startswith("/api/app")}


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


def test_gated_endpoint_401s_without_a_user(client, monkeypatch):
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    assert client.get("/api/app/me").status_code == 401


def test_gated_endpoint_allows_a_user(client):
    assert client.get("/api/app/me").status_code == 200


def test_me_returns_the_current_user(client):
    body = client.get("/api/app/me").get_json()
    assert body["user_id"] == "demo-user"
    assert body["plan"] == "none"


def test_401_body_leaks_nothing_internal(client, monkeypatch):
    monkeypatch.setattr(client_auth, "current_user", lambda: None)
    body = client.get("/api/app/me").get_data(as_text=True).lower()
    for leak in ("sqlite", "traceback", "prototype/", "select ", "/users/"):
        assert leak not in body


def test_the_operator_surface_is_untouched(client):
    """The guard must apply to /api/app only, never to the existing app."""
    assert client.get("/api/indices").status_code == 200
