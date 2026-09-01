"""Users and sessions.

One rule dominates the login path: a failure must not say WHICH failure.
An unknown email and a wrong password are the same answer, or the form
becomes an account enumerator.
"""
import os
import sys
from datetime import timedelta

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, app_store


@pytest.fixture
def conn(tmp_path):
    c = app_store.get_db(str(tmp_path / "accounts.db"))
    app_store.init_db(c)
    yield c
    c.close()


def test_creating_a_user_returns_an_id(conn):
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    assert uid
    assert isinstance(uid, str)


def test_the_password_is_not_stored_in_the_clear(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    assert "correct horse" not in stored


def test_a_duplicate_email_is_refused(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    with pytest.raises(ValueError):
        accounts.create_user(conn, "priya@example.com", "another one")


def test_email_uniqueness_ignores_case(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    with pytest.raises(ValueError):
        accounts.create_user(conn, "Priya@Example.com", "another one")


def test_the_right_password_returns_the_user_id(conn):
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    assert accounts.check_login(conn, "priya@example.com", "correct horse") == uid


def test_signing_in_is_case_insensitive_on_the_email(conn):
    uid = accounts.create_user(conn, "priya@example.com", "correct horse")
    assert accounts.check_login(conn, "PRIYA@example.com", "correct horse") == uid


def test_the_wrong_password_returns_none(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    assert accounts.check_login(conn, "priya@example.com", "wrong") is None


def test_an_unknown_email_returns_none_exactly_like_a_wrong_password(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    assert accounts.check_login(conn, "nobody@example.com", "anything") is None


def test_a_disabled_account_cannot_sign_in(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    conn.execute("UPDATE users SET disabled_at = '2026-01-01T00:00:00+00:00'")
    conn.commit()
    assert accounts.check_login(conn, "priya@example.com", "correct horse") is None


def test_repeated_failures_lock_the_account(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    for _ in range(accounts.LOCKOUT_THRESHOLD):
        accounts.check_login(conn, "priya@example.com", "wrong")
    # The correct password is now refused, because the account is locked.
    assert accounts.check_login(conn, "priya@example.com", "correct horse") is None


def test_a_lock_expires(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    for _ in range(accounts.LOCKOUT_THRESHOLD):
        accounts.check_login(conn, "priya@example.com", "wrong")
    conn.execute("UPDATE users SET locked_until = '2020-01-01T00:00:00+00:00'")
    conn.commit()
    assert accounts.check_login(conn, "priya@example.com", "correct horse")


def test_a_successful_login_clears_the_failure_count(conn):
    accounts.create_user(conn, "priya@example.com", "correct horse")
    for _ in range(3):
        accounts.check_login(conn, "priya@example.com", "wrong")
    accounts.check_login(conn, "priya@example.com", "correct horse")
    row = conn.execute("SELECT failed_count, locked_until FROM users").fetchone()
    assert row["failed_count"] == 0
    assert row["locked_until"] is None


def test_an_expired_lock_restores_the_full_attempt_budget(conn):
    """A lock that has run its course must reset the counter with it.

    Otherwise failed_count stays at the threshold and the very next failure
    re-locks -- which lets an attacker hold the account shut for one request
    every LOCKOUT_MINUTES, and leaves the real user a single-attempt window.
    """
    accounts.create_user(conn, "priya@example.com", "correct horse")
    for _ in range(accounts.LOCKOUT_THRESHOLD):
        accounts.check_login(conn, "priya@example.com", "wrong")
    conn.execute("UPDATE users SET locked_until = '2020-01-01T00:00:00+00:00'")
    conn.commit()
    accounts.check_login(conn, "priya@example.com", "wrong")   # one failure, post-expiry
    assert accounts.check_login(conn, "priya@example.com", "correct horse")


def _user(conn):
    return accounts.create_user(conn, "priya@example.com", "correct horse")


def test_a_session_resolves_to_its_user(conn):
    uid = _user(conn)
    token = accounts.create_session(conn, uid)
    assert accounts.lookup_session(conn, token) == uid


def test_the_raw_token_is_never_stored(conn):
    token = accounts.create_session(conn, _user(conn))
    stored = conn.execute("SELECT token_hash FROM sessions").fetchone()[0]
    assert stored != token
    assert token not in stored


def test_an_unknown_token_resolves_to_nothing(conn):
    accounts.create_session(conn, _user(conn))
    assert accounts.lookup_session(conn, "not-a-real-token") is None


def test_an_empty_token_resolves_to_nothing(conn):
    accounts.create_session(conn, _user(conn))
    assert accounts.lookup_session(conn, "") is None
    assert accounts.lookup_session(conn, None) is None


def test_an_expired_session_resolves_to_nothing(conn):
    token = accounts.create_session(conn, _user(conn))
    conn.execute("UPDATE sessions SET expires_at = '2020-01-01T00:00:00+00:00'")
    conn.commit()
    assert accounts.lookup_session(conn, token) is None


def test_using_a_session_slides_its_expiry_forward(conn):
    token = accounts.create_session(conn, _user(conn))
    conn.execute("UPDATE sessions SET expires_at = ?",
                 (accounts._iso(accounts._now() + timedelta(days=1)),))
    conn.commit()
    accounts.lookup_session(conn, token)
    fresh = conn.execute("SELECT expires_at FROM sessions").fetchone()[0]
    assert accounts._parse(fresh) > accounts._now() + timedelta(days=29)


def test_sliding_cannot_push_past_the_absolute_cap(conn):
    token = accounts.create_session(conn, _user(conn))
    old = accounts._now() - timedelta(days=89)
    conn.execute("UPDATE sessions SET created_at = ?", (accounts._iso(old),))
    conn.commit()
    accounts.lookup_session(conn, token)
    fresh = conn.execute("SELECT expires_at FROM sessions").fetchone()[0]
    # 89 days old, so the 90-day cap leaves at most one day, not thirty.
    assert accounts._parse(fresh) < accounts._now() + timedelta(days=2)


def test_a_session_past_the_cap_resolves_to_nothing(conn):
    token = accounts.create_session(conn, _user(conn))
    old = accounts._now() - timedelta(days=91)
    conn.execute("UPDATE sessions SET created_at = ?, expires_at = ?",
                 (accounts._iso(old), accounts._iso(accounts._now() + timedelta(days=30))))
    conn.commit()
    assert accounts.lookup_session(conn, token) is None


def test_revoking_a_session_kills_it_immediately(conn):
    token = accounts.create_session(conn, _user(conn))
    accounts.revoke_session(conn, token)
    assert accounts.lookup_session(conn, token) is None


def test_two_sessions_for_one_user_are_independent(conn):
    uid = _user(conn)
    a = accounts.create_session(conn, uid)
    b = accounts.create_session(conn, uid)
    accounts.revoke_session(conn, a)
    assert accounts.lookup_session(conn, a) is None
    assert accounts.lookup_session(conn, b) == uid
