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


@pytest.fixture(scope="session", autouse=True)
def _never_touch_the_real_database(tmp_path_factory):
    """Repoint the default database path at a throwaway file for the run.

    Four modules hold their own open_store seam over one database, and
    patching them individually has now failed four times -- a fixture that
    misses one reads the real product record, whose loss cannot be
    recovered. DB_PATH is the single choke point every unpatched seam flows
    through, so redirecting it turns a recurring defect into an impossible
    one.
    """
    from prototype import app_store
    real = app_store.DB_PATH
    app_store.DB_PATH = str(tmp_path_factory.mktemp("db") / "safety-net.db")
    yield
    app_store.DB_PATH = real


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
