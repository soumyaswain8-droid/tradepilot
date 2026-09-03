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
