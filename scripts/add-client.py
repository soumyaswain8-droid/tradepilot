#!/usr/bin/env python3
"""Create a client account.

    $ python3 scripts/add-client.py priya@example.com
    Password: (not echoed)
    Confirm:  (not echoed)
    created user u-8f21c4

The password is prompted for, never passed as an argument: an argument
lands in shell history and in the process list.

This is the only account-creation path in B1. Self-serve signup is B2.
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prototype import accounts, app_store  # noqa: E402


def open_store():
    """Open the store. A named function so tests can point at a throwaway file."""
    conn = app_store.get_db()
    app_store.init_db(conn)
    return conn


def main(argv, prompt=getpass.getpass):
    if len(argv) != 1:
        print("usage: add-client.py <email>", file=sys.stderr)
        return 2
    email = argv[0]

    password = prompt("Password: ")
    if not password:
        print("password must not be empty", file=sys.stderr)
        return 2
    if prompt("Confirm:  ") != password:
        print("those did not match", file=sys.stderr)
        return 2

    conn = open_store()
    try:
        uid = accounts.create_user(conn, email, password)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1
    finally:
        conn.close()

    print("created user " + uid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
