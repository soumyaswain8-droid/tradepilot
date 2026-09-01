"""Users and sessions.

One rule dominates the login path: a failure must not say WHICH failure.
An unknown email and a wrong password are the same answer, or the form
becomes an account enumerator.
"""
import os
import sys

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
