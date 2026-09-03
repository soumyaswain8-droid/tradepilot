"""Approving from the waitlist.

The mail goes out before the row is marked approved. The other order leaves a
row that says approved with no invite in existence and nothing signalling that
anything went wrong -- the operator sees a satisfied list, the client sees
silence.
"""
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import accounts, app_store

_spec = importlib.util.spec_from_file_location(
    "waitlist_cli", os.path.join(REPO_ROOT, "scripts", "waitlist.py"))
waitlist = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(waitlist)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "wl.db")
    monkeypatch.setattr(waitlist, "open_store", lambda: app_store.get_db(path))
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    yield conn
    conn.close()


def _wait(conn, email):
    conn.execute("INSERT INTO waitlist (id, email, requested_at) VALUES (?, ?, ?)",
                 ("w-" + email[:4], email, accounts._iso(accounts._now())))
    conn.commit()


def _sink():
    sent = []
    return sent, (lambda to, subject, body: sent.append((to, subject, body)))


def test_list_shows_pending_entries(db, capsys):
    _wait(db, "priya@example.com")
    assert waitlist.main(["list"]) == 0
    assert "priya@example.com" in capsys.readouterr().out


def test_list_hides_already_approved_entries(db, capsys):
    _wait(db, "priya@example.com")
    db.execute("UPDATE waitlist SET approved_at = '2026-09-01T00:00:00.000000+00:00'")
    db.commit()
    waitlist.main(["list"])
    assert "priya@example.com" not in capsys.readouterr().out


def test_approving_sends_an_invite(db):
    _wait(db, "priya@example.com")
    sent, send = _sink()
    assert waitlist.main(["approve", "priya@example.com"], send=send) == 0
    assert len(sent) == 1
    assert sent[0][0] == "priya@example.com"
    assert "/app/set-password?t=" in sent[0][2]


def test_approving_issues_an_invite_token(db):
    _wait(db, "priya@example.com")
    _, send = _sink()
    waitlist.main(["approve", "priya@example.com"], send=send)
    row = db.execute("SELECT purpose FROM auth_tokens").fetchone()
    assert row["purpose"] == "invite"


def test_approving_marks_the_row(db):
    _wait(db, "priya@example.com")
    _, send = _sink()
    waitlist.main(["approve", "priya@example.com"], send=send)
    row = db.execute("SELECT approved_at FROM waitlist").fetchone()
    assert row["approved_at"] is not None


def test_a_failed_send_leaves_the_row_pending(db):
    """Send first, mark second. A row marked approved with no invite in
    existence is invisible to the operator and silent to the client."""
    _wait(db, "priya@example.com")

    def explode(to, subject, body):
        raise RuntimeError("smtp down")

    assert waitlist.main(["approve", "priya@example.com"], send=explode) != 0
    row = db.execute("SELECT approved_at FROM waitlist").fetchone()
    assert row["approved_at"] is None


def test_approving_someone_not_on_the_list_is_refused(db):
    _, send = _sink()
    assert waitlist.main(["approve", "nobody@example.com"], send=send) != 0


def test_approving_an_address_that_already_has_an_account_is_refused(db):
    _wait(db, "priya@example.com")
    accounts.create_user(db, "priya@example.com", "pw")
    sent, send = _sink()
    assert waitlist.main(["approve", "priya@example.com"], send=send) != 0
    assert sent == []


def test_it_requires_a_known_subcommand(db):
    assert waitlist.main([]) != 0
    assert waitlist.main(["frobnicate"]) != 0
