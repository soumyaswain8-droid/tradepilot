"""Invite and reset links.

A link is single-use, time-limited, and stored only as a digest. The
single-use property is claimed by the UPDATE that checks it -- a read
followed by a write can let two nearly simultaneous clicks both succeed,
and mail clients that prefetch links make that real rather than theoretical.
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
    c = app_store.get_db(str(tmp_path / "tokens.db"))
    app_store.init_db(c)
    yield c
    c.close()


def test_issuing_returns_a_token(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com",
                                 accounts.INVITE_HOURS)
    assert token
    assert len(token) > 20


def test_the_raw_token_is_never_stored(conn):
    import hashlib
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    stored = conn.execute("SELECT token_hash FROM auth_tokens").fetchone()[0]
    assert token not in stored
    assert stored == hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_peek_reports_the_purpose_without_consuming(conn):
    token = accounts.issue_token(conn, "reset", "priya@example.com", 1)
    assert accounts.peek_token(conn, token) == "reset"
    # Still usable afterwards -- peeking must not spend the link.
    assert accounts.consume_token(conn, token) == ("reset", "priya@example.com")


def test_consuming_returns_the_purpose_and_email(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    assert accounts.consume_token(conn, token) == ("invite", "priya@example.com")


def test_a_token_can_only_be_consumed_once(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    first = accounts.consume_token(conn, token)
    second = accounts.consume_token(conn, token)
    assert first == ("invite", "priya@example.com")
    assert second == (None, None)


def test_a_used_token_no_longer_peeks(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    accounts.consume_token(conn, token)
    assert accounts.peek_token(conn, token) is None


def test_an_expired_token_is_refused(conn):
    token = accounts.issue_token(conn, "reset", "priya@example.com", 1)
    conn.execute("UPDATE auth_tokens SET expires_at = '2020-01-01T00:00:00.000000+00:00'")
    conn.commit()
    assert accounts.peek_token(conn, token) is None
    assert accounts.consume_token(conn, token) == (None, None)


def test_an_unknown_token_is_refused(conn):
    accounts.issue_token(conn, "invite", "priya@example.com", 72)
    assert accounts.consume_token(conn, "not-a-real-token") == (None, None)
    assert accounts.peek_token(conn, "not-a-real-token") is None


def test_an_empty_token_is_refused(conn):
    assert accounts.consume_token(conn, "") == (None, None)
    assert accounts.consume_token(conn, None) == (None, None)
    assert accounts.peek_token(conn, "") is None


def test_two_tokens_for_one_address_are_independent(conn):
    a = accounts.issue_token(conn, "reset", "priya@example.com", 1)
    b = accounts.issue_token(conn, "reset", "priya@example.com", 1)
    accounts.consume_token(conn, a)
    assert accounts.consume_token(conn, b) == ("reset", "priya@example.com")


def test_the_expiry_honours_the_hours_given(conn):
    token = accounts.issue_token(conn, "invite", "priya@example.com", 72)
    row = conn.execute("SELECT created_at, expires_at FROM auth_tokens").fetchone()
    span = accounts._parse(row["expires_at"]) - accounts._parse(row["created_at"])
    assert timedelta(hours=71) < span < timedelta(hours=73)
