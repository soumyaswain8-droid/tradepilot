#!/usr/bin/env python3
"""The waitlist.

    $ python3 scripts/waitlist.py list
    $ python3 scripts/waitlist.py approve priya@example.com

Approving emails a one-time link that both proves the person controls the
address and is where they choose a password. Nothing exists as an account
until that link is used.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prototype import accounts, app_store, mailer  # noqa: E402

BASE_URL = os.environ.get("TRADEPILOT_URL", "https://tradepilot.onrender.com")


def open_store():
    conn = app_store.get_db()
    app_store.init_db(conn)
    return conn


def _default_send(to, subject, body):
    mailer.send(to, subject, body)


def _invite_body(token):
    return ("You have been approved for TradePilot.\n\n"
            "Set your password here -- the link is good for 72 hours:\n"
            "%s/app/set-password?t=%s\n" % (BASE_URL.rstrip("/"), token))


def cmd_list(conn):
    rows = conn.execute(
        "SELECT email, requested_at FROM waitlist "
        "WHERE approved_at IS NULL ORDER BY requested_at").fetchall()
    print("%d waiting" % len(rows))
    for r in rows:
        print("  %-32s %s" % (r["email"], r["requested_at"][:10]))
    return 0


def cmd_approve(conn, email, send):
    # Deliberately not restricted to approved_at IS NULL: an invite that
    # expired without anyone completing it is not a terminal state -- the
    # operator can re-approve, per the 72-hour-then-back-to-pending spec.
    # What actually blocks a re-approval is checked below: an account that
    # already exists, or an invite that is still live.
    row = conn.execute(
        "SELECT id, user_id FROM waitlist WHERE lower(email) = lower(?)",
        (email,)).fetchone()
    if row is None:
        print("%s is not waiting" % email, file=sys.stderr)
        return 1

    if row["user_id"] is not None:
        print("%s already has an account" % email, file=sys.stderr)
        return 1

    existing = conn.execute("SELECT id FROM users WHERE lower(email) = lower(?)",
                            (email,)).fetchone()
    if existing is not None:
        print("%s already has an account" % email, file=sys.stderr)
        return 1

    live = conn.execute(
        "SELECT 1 FROM auth_tokens WHERE lower(email) = lower(?) "
        "AND purpose = 'invite' AND used_at IS NULL AND expires_at > ?",
        (email, accounts._iso(accounts._now()))).fetchone()
    if live is not None:
        print("%s already has a live invite" % email, file=sys.stderr)
        return 1

    token = accounts.issue_token(conn, "invite", email, accounts.INVITE_HOURS)
    try:
        send(email, "Your TradePilot invite", _invite_body(token))
    except Exception as e:
        # A token nobody received must not outlive the failed send -- the
        # command promises to change nothing when it fails, and marking
        # approved now would leave a satisfied-looking list and a client
        # who never hears anything.
        conn.execute("DELETE FROM auth_tokens WHERE token_hash = ?",
                     (accounts._hash_token(token),))
        conn.commit()
        print("could not send: %s" % e, file=sys.stderr)
        return 2

    conn.execute("UPDATE waitlist SET approved_at = ? WHERE id = ?",
                 (accounts._iso(accounts._now()), row["id"]))
    conn.commit()
    print("invite sent, expires in %dh" % accounts.INVITE_HOURS)
    return 0


def main(argv, send=_default_send, out=sys.stdout):
    if not argv:
        print("usage: waitlist.py list | approve <email>", file=sys.stderr)
        return 2

    conn = open_store()
    try:
        if argv[0] == "list":
            return cmd_list(conn)
        if argv[0] == "approve":
            if len(argv) != 2:
                print("usage: waitlist.py approve <email>", file=sys.stderr)
                return 2
            return cmd_approve(conn, argv[1], send)
        print("unknown command: %s" % argv[0], file=sys.stderr)
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
