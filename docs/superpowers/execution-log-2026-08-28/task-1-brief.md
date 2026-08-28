### Task 1: Web-layer test harness

The `tests/` directory holds 14 files, all engine and strategy logic. There is no Flask test client anywhere in the repo, so nothing that follows can be test-driven until this exists. This task builds the harness and proves it against routes that already work.

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_web_routes.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a pytest fixture `client` — a `flask.testing.FlaskClient` for `prototype.app.app`. Every later task's tests take `client` as their first argument.

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
"""Shared fixtures for the web-layer tests.

The Flask app lives in prototype/app.py and inserts its own directory onto
sys.path at import time, so importing it requires the repo root on sys.path.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture(scope="session")
def flask_app():
    """The prototype Flask application, configured for testing."""
    from prototype.app import app
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(flask_app):
    """A test client. Use client.get(path) -- no network, no live server."""
    return flask_app.test_client()
```

Create `tests/test_web_routes.py`:

```python
"""Web-layer coverage.

Before this file the entire Flask surface -- roughly 70 routes -- was
untested. The terminal already shipped one blank tab on 2026-08-03 because a
script was silently discarded; these tests exist so that class of bug fails
in CI rather than in the browser.
"""


def test_terminal_renders(client):
    """GET / returns the terminal shell."""
    r = client.get("/")
    assert r.status_code == 200
    assert b"TRADEPILOT" in r.data


def test_floor_renders(client):
    """GET /floor returns the Agent Floor console."""
    r = client.get("/floor")
    assert r.status_code == 200
    assert b"Market Scan" in r.data


def test_team_renders(client):
    """GET /team returns the Quant Desk."""
    r = client.get("/team")
    assert r.status_code == 200
    assert b"<h1>TradePilot Quant Desk</h1>" in r.data
```

- [ ] **Step 2: Run the tests to verify the harness reports honestly**

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/test_web_routes.py -v
```

Expected: all three PASS. These assert existing behaviour, so a failure here means the harness is broken (import error, wrong sentinel), not the app. Fix the harness before continuing.

If the import fails with `ModuleNotFoundError: No module named 'prototype'`, confirm `prototype/__init__.py` exists; if it does not, create an empty one and re-run.

- [ ] **Step 3: Verify the harness catches a real failure**

Temporarily change the sentinel in `test_terminal_renders` from `b"TRADEPILOT"` to `b"THIS_STRING_IS_NOT_IN_THE_PAGE"` and re-run:

```bash
python3 -m pytest tests/test_web_routes.py::test_terminal_renders -v
```

Expected: FAIL with an assertion error. This confirms the test is actually reading the response body rather than passing vacuously. Revert the sentinel to `b"TRADEPILOT"` and re-run to confirm PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_web_routes.py
git commit -m "test(web): first coverage for the Flask surface

Seventy routes, zero tests. The terminal shipped a blank tab on 2026-08-03
because a script tag was silently discarded and nothing caught it. This is
the harness that makes that class of bug fail before the browser does."
```

---

