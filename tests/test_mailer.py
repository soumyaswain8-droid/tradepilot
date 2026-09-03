"""Sending mail.

The transport is injected so tests never open a socket. Testing by mocking
smtplib's internals would couple these tests to the standard library's shape
rather than to the message we send.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import mailer


@pytest.fixture
def creds(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "soumya@sidewall.in")
    monkeypatch.setenv("SMTP_PASS", "an-app-password")


def recorder():
    sent = []

    def transport(host, port, user, password, msg):
        sent.append({"host": host, "port": port, "user": user,
                     "password": password, "msg": msg})
    return sent, transport


def test_it_sends_to_the_right_recipient(creds):
    sent, transport = recorder()
    mailer.send("priya@example.com", "Your invite", "Body here",
                transport=transport)
    assert len(sent) == 1
    assert sent[0]["msg"]["To"] == "priya@example.com"


def test_the_message_carries_the_subject_and_body(creds):
    sent, transport = recorder()
    mailer.send("priya@example.com", "Your invite", "Click this link",
                transport=transport)
    msg = sent[0]["msg"]
    assert msg["Subject"] == "Your invite"
    assert "Click this link" in msg.get_content()


def test_it_sends_from_the_configured_address(creds):
    sent, transport = recorder()
    mailer.send("priya@example.com", "s", "b", transport=transport)
    assert sent[0]["msg"]["From"] == "soumya@sidewall.in"


def test_it_uses_the_workspace_smtp_endpoint(creds):
    sent, transport = recorder()
    mailer.send("priya@example.com", "s", "b", transport=transport)
    assert sent[0]["host"] == "smtp.gmail.com"
    assert sent[0]["port"] == 587


def test_sending_without_credentials_raises(monkeypatch):
    """A mailer that silently does nothing when unconfigured is how a
    deployment discovers weeks later that no invite ever arrived."""
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    _, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)


def test_a_missing_password_alone_also_raises(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "soumya@sidewall.in")
    monkeypatch.delenv("SMTP_PASS", raising=False)
    _, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)


def test_nothing_is_sent_when_credentials_are_missing(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASS", raising=False)
    sent, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)
    assert sent == []


def test_a_missing_user_alone_raises(monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.setenv("SMTP_PASS", "an-app-password")
    _, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)


def test_an_empty_password_raises(monkeypatch):
    """The realistic deployment failure: the variable is present and blank,
    not absent. `not ""` is what the guard exists to catch."""
    monkeypatch.setenv("SMTP_USER", "soumya@sidewall.in")
    monkeypatch.setenv("SMTP_PASS", "")
    _, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)


def test_an_empty_user_raises(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASS", "an-app-password")
    _, transport = recorder()
    with pytest.raises(RuntimeError):
        mailer.send("priya@example.com", "s", "b", transport=transport)
