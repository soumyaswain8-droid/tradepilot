"""The public forms.

Both take an email address, and both must answer identically whether that
address is unknown, already waitlisted, or already has an account. Anything
else turns either form into an account enumerator.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, accounts_web, app_store, client_api, client_auth


@pytest.fixture
def store(tmp_path, monkeypatch):
    path = str(tmp_path / "web.db")
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    for mod in (client_auth, accounts_web, client_api):
        monkeypatch.setattr(mod, "open_store", lambda: app_store.get_db(path))
    yield conn
    conn.close()


@pytest.fixture
def sent(monkeypatch):
    box = []
    monkeypatch.setattr(accounts_web, "send_mail",
                        lambda to, subject, body: box.append((to, subject, body)))
    return box


def test_the_signup_page_renders(client, store):
    r = client.get("/app/signup")
    assert r.status_code == 200
    assert b"email" in r.data.lower()


def test_signing_up_records_a_waitlist_row(client, store, sent):
    client.post("/app/signup", data={"email": "priya@example.com"})
    rows = store.execute("SELECT email FROM waitlist").fetchall()
    assert [r["email"] for r in rows] == ["priya@example.com"]


def test_signing_up_sends_no_mail(client, store, sent):
    """Joining a list is not an event anyone needs to be emailed about."""
    client.post("/app/signup", data={"email": "priya@example.com"})
    assert sent == []


def test_signup_answers_the_same_for_an_address_that_already_has_an_account(
        client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    known = client.post("/app/signup", data={"email": "priya@example.com"})
    fresh = client.post("/app/signup", data={"email": "nobody@example.com"})
    assert known.get_data(as_text=True) == fresh.get_data(as_text=True)
    assert known.status_code == fresh.status_code


def test_signing_up_twice_is_accepted(client, store, sent):
    client.post("/app/signup", data={"email": "priya@example.com"})
    client.post("/app/signup", data={"email": "priya@example.com"})
    assert store.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 2


def test_signup_from_a_foreign_origin_is_refused(client, store, sent):
    r = client.post("/app/signup", data={"email": "priya@example.com"},
                    headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403
    assert store.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 0


def test_the_forgot_page_renders(client, store):
    assert client.get("/app/forgot").status_code == 200


def test_forgot_mails_a_reset_link_to_a_real_account(client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    client.post("/app/forgot", data={"email": "priya@example.com"})
    assert len(sent) == 1
    to, subject, body = sent[0]
    assert to == "priya@example.com"
    assert "/app/set-password?t=" in body


def test_forgot_issues_a_reset_token(client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    client.post("/app/forgot", data={"email": "priya@example.com"})
    row = store.execute("SELECT purpose FROM auth_tokens").fetchone()
    assert row["purpose"] == "reset"


def test_forgot_sends_nothing_for_an_unknown_address(client, store, sent):
    client.post("/app/forgot", data={"email": "nobody@example.com"})
    assert sent == []
    assert store.execute("SELECT COUNT(*) FROM auth_tokens").fetchone()[0] == 0


def test_forgot_answers_the_same_whether_or_not_the_account_exists(
        client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    known = client.post("/app/forgot", data={"email": "priya@example.com"})
    unknown = client.post("/app/forgot", data={"email": "nobody@example.com"})
    assert known.get_data(as_text=True) == unknown.get_data(as_text=True)
    assert known.status_code == unknown.status_code


def test_forgot_still_answers_normally_when_mail_fails(client, store, monkeypatch):
    """The visitor cannot be told, because telling them would reveal that the
    account exists. The failure is logged server-side instead."""
    accounts.create_user(store, "priya@example.com", "pw")

    def explode(to, subject, body):
        raise RuntimeError("smtp down")
    monkeypatch.setattr(accounts_web, "send_mail", explode)

    r = client.post("/app/forgot", data={"email": "priya@example.com"})
    assert r.status_code == 200
    assert accounts_web.FORGOT_ACK.encode() in r.data


def test_forgot_from_a_foreign_origin_is_refused(client, store, sent):
    accounts.create_user(store, "priya@example.com", "pw")
    r = client.post("/app/forgot", data={"email": "priya@example.com"},
                    headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403
    assert sent == []
    assert store.execute("SELECT COUNT(*) FROM auth_tokens").fetchone()[0] == 0


def _invite(store, email="priya@example.com"):
    return accounts.issue_token(store, "invite", email, accounts.INVITE_HOURS)


def test_a_live_invite_renders_the_form(client, store):
    token = _invite(store)
    r = client.get("/app/set-password?t=" + token)
    assert r.status_code == 200
    assert b'name="password"' in r.data
    assert b'name="t"' in r.data


def test_an_expired_link_says_so_without_revealing_anything(client, store):
    token = _invite(store)
    store.execute("UPDATE auth_tokens SET expires_at = '2020-01-01T00:00:00.000000+00:00'")
    store.commit()
    body = client.get("/app/set-password?t=" + token).get_data(as_text=True)
    unknown = client.get("/app/set-password?t=never-existed").get_data(as_text=True)
    assert body == unknown


def test_completing_an_invite_creates_the_account_and_signs_them_in(client, store):
    token = _invite(store)
    r = client.post("/app/set-password", data={"t": token, "password": "a good one"})
    assert r.status_code == 302
    assert accounts.check_login(store, "priya@example.com", "a good one")
    assert client.get("/api/app/me").status_code == 200


def test_an_invite_link_cannot_be_used_twice(client, store):
    token = _invite(store)
    client.post("/app/set-password", data={"t": token, "password": "a good one"})
    again = client.post("/app/set-password", data={"t": token, "password": "another"})
    assert again.status_code == 400
    assert store.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_a_reset_changes_the_password_and_the_old_one_stops_working(client, store):
    uid = accounts.create_user(store, "priya@example.com", "old password")
    token = accounts.issue_token(store, "reset", "priya@example.com",
                                 accounts.RESET_HOURS)
    client.post("/app/set-password", data={"t": token, "password": "new password"})
    assert accounts.check_login(store, "priya@example.com", "new password") == uid
    assert accounts.check_login(store, "priya@example.com", "old password") is None


def test_a_reset_ends_sessions_that_already_existed(client, store):
    """Re-present the OLD token explicitly. The client's cookie jar has moved
    on, so merely re-requesting would prove nothing about the server."""
    uid = accounts.create_user(store, "priya@example.com", "old password")
    stale = accounts.create_session(store, uid)
    token = accounts.issue_token(store, "reset", "priya@example.com",
                                 accounts.RESET_HOURS)
    client.post("/app/set-password", data={"t": token, "password": "new password"})
    assert accounts.lookup_session(store, stale) is None


def test_the_browser_completing_a_reset_is_left_signed_in(client, store):
    """Revocation must happen BEFORE the new session is issued, or the fresh
    one is deleted along with the old and the user lands back at login."""
    uid = accounts.create_user(store, "priya@example.com", "old password")
    accounts.create_session(store, uid)
    token = accounts.issue_token(store, "reset", "priya@example.com",
                                 accounts.RESET_HOURS)
    client.post("/app/set-password", data={"t": token, "password": "new password"})
    assert client.get("/api/app/me").status_code == 200


def test_set_password_from_a_foreign_origin_is_refused(client, store):
    token = _invite(store)
    r = client.post("/app/set-password",
                    data={"t": token, "password": "a good one"},
                    headers={"Origin": "https://evil.example.com"})
    assert r.status_code == 403
    assert store.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_an_empty_password_is_refused(client, store):
    token = _invite(store)
    r = client.post("/app/set-password", data={"t": token, "password": ""})
    assert r.status_code != 302
    assert store.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0



def test_an_invite_is_refused_once_the_account_exists(client, store):
    """Two approvals can issue two live invites. The second must not
    silently reset what the first created."""
    token_a = _invite(store)
    token_b = _invite(store)
    client.post("/app/set-password", data={"t": token_a, "password": "first one"})
    r = client.post("/app/set-password", data={"t": token_b, "password": "second one"})
    assert r.status_code == 400
    assert accounts.check_login(store, "priya@example.com", "first one")
    assert accounts.check_login(store, "priya@example.com", "second one") is None


def test_a_reset_is_refused_when_the_account_is_gone(client, store):
    uid = accounts.create_user(store, "priya@example.com", "old password")
    token = accounts.issue_token(store, "reset", "priya@example.com",
                                 accounts.RESET_HOURS)
    store.execute("DELETE FROM users WHERE id = ?", (uid,))
    store.commit()
    r = client.post("/app/set-password", data={"t": token, "password": "new one"})
    assert r.status_code == 400
    assert store.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
