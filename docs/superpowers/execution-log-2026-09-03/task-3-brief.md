### Task 3: The mailer

**Files:**
- Create: `prototype/mailer.py`
- Test: `tests/test_mailer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `mailer.send(to, subject, body, transport=None) -> None`
  - `mailer.FROM_ADDRESS = "soumya@sidewall.in"`
  - `mailer.SMTP_HOST = "smtp.gmail.com"`, `mailer.SMTP_PORT = 587`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mailer.py`:

```python
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
    assert sent[0]["msg"]["From"] == mailer.FROM_ADDRESS


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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_mailer.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'prototype.mailer'`

- [ ] **Step 3: Write the module**

Create `prototype/mailer.py`:

```python
"""Outbound mail.

No Flask import: this takes values and a transport, so it is testable without
a request context and the tests never open a socket.

sidewall.in publishes SPF and a DKIM key at selector `google`. If either stops
resolving, mail still sends and silently lands in spam, because the domain's
DMARC policy is p=quarantine. Run scripts/check-mail-dns.sh sidewall.in to
check that from outside the app -- nothing in here can detect it.
"""
import os
import smtplib
from email.message import EmailMessage

FROM_ADDRESS = "soumya@sidewall.in"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


def _smtp_transport(host, port, user, password, msg):
    with smtplib.SMTP(host, port, timeout=20) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)


def send(to, subject, body, transport=None):
    """Send one plain-text message. Raises if SMTP is not configured."""
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if not user or not password:
        raise RuntimeError(
            "SMTP_USER and SMTP_PASS must be set to send mail")

    msg = EmailMessage()
    msg["From"] = FROM_ADDRESS
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    (transport or _smtp_transport)(SMTP_HOST, SMTP_PORT, user, password, msg)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_mailer.py -q`
Expected: PASS, 7 tests.

- [ ] **Step 5: Confirm the sending domain still authenticates**

Run: `./scripts/check-mail-dns.sh sidewall.in`
Expected: exit 0, with SPF, DKIM and MX all OK.

The spec makes this B2's gate for a reason. `sidewall.in` publishes DMARC
`p=quarantine`, so if SPF or the DKIM key ever stops resolving, mail still
sends successfully and silently lands in spam. Nothing inside the application
can detect that — the SMTP call returns success either way. If this exits
non-zero, stop and report it: the mailer is correct but undeliverable, and
building the rest of B2 on top would produce a signup flow that appears to
work and reaches nobody.

- [ ] **Step 6: Confirm nothing opens a socket**

Run the whole suite with networking unavailable to prove the seam holds:

```bash
python3 -m pytest tests/ -q
```

Then read `tests/test_mailer.py` and confirm every test passes a `transport=` argument. Report whether any test path could reach `_smtp_transport`. A test that accidentally used the real transport would hang on connect rather than fail cleanly, so this is worth checking by eye rather than inferring from a green run.

- [ ] **Step 7: Commit**

```bash
git add prototype/mailer.py tests/test_mailer.py
git commit -m "feat(mail): stdlib SMTP with an injectable transport

Raises when SMTP_USER or SMTP_PASS is unset. A mailer that no-ops when
unconfigured is how you find out weeks later that no invite ever arrived."
```

---

