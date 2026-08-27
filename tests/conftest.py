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
