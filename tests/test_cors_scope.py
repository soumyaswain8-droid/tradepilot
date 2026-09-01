"""CORS must not cover the client's private endpoints.

/app and /api/app/* are served from one origin, and a same-origin request
never consults CORS. Leaving those paths outside the rule removes the
supports_credentials decision entirely, rather than requiring someone to
get it right later.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, app_store, client_api, client_auth

ORIGIN = {"Origin": "http://localhost:3000"}


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


def test_the_legacy_api_still_answers_cross_origin(client):
    r = client.get("/api/indices", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" in r.headers


def test_the_client_api_carries_no_cors_headers(client):
    r = client.get("/api/app/calls", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" not in r.headers


def test_the_gated_client_api_carries_no_cors_headers(client):
    r = client.get("/api/app/positions", headers=ORIGIN)
    assert "Access-Control-Allow-Origin" not in r.headers


def test_the_gated_client_api_carries_no_cors_headers_when_signed_in(client, signed_in):
    """The rejected-request case above proves nothing about a real response --
    a 401 short-circuits before any handler runs. This pins the same absence
    on the 200 path, where a handler actually executes."""
    r = client.get("/api/app/positions", headers=ORIGIN)
    assert r.status_code == 200
    assert "Access-Control-Allow-Origin" not in r.headers
