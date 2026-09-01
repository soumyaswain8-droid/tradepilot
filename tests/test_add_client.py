"""Creating an account from the terminal.

The password is read with getpass, never taken as an argument -- a password
on the command line lands in shell history and in the process list, where
any other user on the machine can read it.
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
    "add_client", os.path.join(REPO_ROOT, "scripts", "add-client.py"))
add_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(add_client)


@pytest.fixture
def db(tmp_path, monkeypatch):
    path = str(tmp_path / "add.db")
    monkeypatch.setattr(add_client, "open_store", lambda: app_store.get_db(path))
    conn = app_store.get_db(path)
    app_store.init_db(conn)
    yield conn
    conn.close()


def test_it_creates_an_account(db, capsys):
    code = add_client.main(["priya@example.com"], prompt=lambda _: "correct horse")
    assert code == 0
    assert accounts.check_login(db, "priya@example.com", "correct horse")


def test_it_refuses_a_duplicate_rather_than_resetting_a_live_password(db, capsys):
    add_client.main(["priya@example.com"], prompt=lambda _: "correct horse")
    code = add_client.main(["priya@example.com"], prompt=lambda _: "new password")
    assert code != 0
    # The original password still works -- the second run changed nothing.
    assert accounts.check_login(db, "priya@example.com", "correct horse")


def test_it_refuses_when_the_two_entries_differ(db):
    answers = iter(["correct horse", "different"])
    code = add_client.main(["priya@example.com"], prompt=lambda _: next(answers))
    assert code != 0
    assert accounts.check_login(db, "priya@example.com", "correct horse") is None


def test_it_refuses_an_empty_password(db):
    code = add_client.main(["priya@example.com"], prompt=lambda _: "")
    assert code != 0


def test_it_requires_an_email(db):
    assert add_client.main([], prompt=lambda _: "correct horse") != 0


def test_the_password_never_appears_in_the_output(db, capsys):
    add_client.main(["priya@example.com"], prompt=lambda _: "correct horse")
    out = capsys.readouterr()
    assert "correct horse" not in out.out
    assert "correct horse" not in out.err
