"""Signing in.

The open-redirect test is not a formality. A login page that redirects
anywhere is a phishing primitive: the attacker sends a link to the real
site, the victim signs in for real, and the redirect lands them on a copy
that asks again.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, accounts_web, app_store, client_auth


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / "web.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    monkeypatch.setattr(client_auth, "open_store", lambda: app_store.get_db(path))
    monkeypatch.setattr(accounts_web, "open_store", lambda: app_store.get_db(path))
    accounts.create_user(conn, "priya@example.com", "correct horse")
    yield conn
    conn.close()


def test_the_login_page_renders(client, store):
    r = client.get("/app/login")
    assert r.status_code == 200
    assert b"password" in r.data.lower()


def test_the_login_page_contains_no_javascript(client, store):
    body = client.get("/app/login").get_data(as_text=True).lower()
    assert "<script" not in body


def test_signing_in_sets_a_session_cookie_and_redirects(client, store):
    r = client.post("/app/login",
                    data={"email": "priya@example.com", "password": "correct horse"})
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/app")
    assert client_auth.COOKIE_NAME in r.headers.get("Set-Cookie", "")


def test_the_cookie_is_httponly_and_samesite(client, store):
    r = client.post("/app/login",
                    data={"email": "priya@example.com", "password": "correct horse"})
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_a_wrong_password_does_not_sign_you_in(client, store):
    r = client.post("/app/login",
                    data={"email": "priya@example.com", "password": "wrong"})
    assert client_auth.COOKIE_NAME not in r.headers.get("Set-Cookie", "")


def test_the_refusal_is_identical_for_an_unknown_email(client, store):
    wrong = client.post("/app/login", data={"email": "priya@example.com",
                                            "password": "wrong"}).get_data(as_text=True)
    unknown = client.post("/app/login", data={"email": "nobody@example.com",
                                              "password": "wrong"}).get_data(as_text=True)
    assert wrong == unknown


def test_signing_in_then_reaching_the_book(client, store):
    client.post("/app/login",
                data={"email": "priya@example.com", "password": "correct horse"})
    assert client.get("/api/app/me").status_code == 200


def test_logging_out_clears_the_cookie(client, store):
    """The test client drops its cookie once logout expires it.

    That proves the browser-facing half (the client no longer holds a
    cookie) but nothing about the server -- see
    test_logout_revokes_server_side_not_just_the_cookie for the half that
    actually matters.
    """
    client.post("/app/login",
                data={"email": "priya@example.com", "password": "correct horse"})
    client.post("/app/logout")
    assert client.get("/api/app/me").status_code == 401


def test_logout_revokes_server_side_not_just_the_cookie(client, store):
    """Re-present the SAME token after logging out.

    The test client drops the cookie when logout expires it, so merely
    re-requesting proves nothing about the server. This proves the row is
    gone -- which is the entire reason this design uses server-side sessions
    rather than a signed cookie.
    """
    uid = accounts.check_login(store, "priya@example.com", "correct horse")
    token = accounts.create_session(store, uid)
    client.set_cookie("localhost", client_auth.COOKIE_NAME, token)
    assert client.get("/api/app/me").status_code == 200
    client.post("/app/logout")
    client.set_cookie("localhost", client_auth.COOKIE_NAME, token)
    assert client.get("/api/app/me").status_code == 401


@pytest.mark.parametrize("target", [
    "https://evil.example.com/phish",
    "//evil.example.com/phish",
    "http://evil.example.com",
    "\\\\evil.example.com",
    "/\t/evil.example.com",
    "/\n/evil.example.com",
    "/\r/evil.example.com",
    "/ev\til.example.com",
])
def test_next_cannot_send_you_off_site(target):
    assert accounts_web.safe_next(target) == "/app"


@pytest.mark.parametrize("target", ["/app", "/app#book", "/app/login"])
def test_a_local_next_is_kept(target):
    assert accounts_web.safe_next(target) == target


def test_next_is_honoured_after_signing_in(client, store):
    r = client.post("/app/login?next=/app%23book",
                    data={"email": "priya@example.com", "password": "correct horse"})
    assert r.headers["Location"].endswith("/app#book")
