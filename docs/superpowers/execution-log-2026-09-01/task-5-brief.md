### Task 5: Creating an account from the terminal

**Files:**
- Create: `scripts/add-client.py`
- Test: `tests/test_add_client.py`

**Interfaces:**
- Consumes: `accounts.create_user(conn, email, password) -> str`, `app_store.get_db`, `app_store.init_db`
- Produces: `add_client.main(argv, prompt) -> int` (a process exit code; `prompt` is injected so tests never touch a terminal)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_add_client.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest tests/test_add_client.py -q`
Expected: FAIL — the script file does not exist.

- [ ] **Step 3: Write the script**

Create `scripts/add-client.py`:

```python
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
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_add_client.py -q`
Expected: PASS, 6 tests.

- [ ] **Step 5: Commit**

```bash
git add scripts/add-client.py tests/test_add_client.py
git commit -m "feat(accounts): add-client.py creates an account

Password via getpass, never an argument. Refuses a duplicate rather
than silently resetting a live account's password."
```

---

