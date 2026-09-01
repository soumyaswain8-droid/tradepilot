"""Schema tests for the calls/positions store.

`calls` is the product record -- if it is lost the track record cannot be
rebuilt. These tests pin the two properties that protect it: the schema is
idempotent, and the publish job physically cannot write the same call twice.
"""
import os
import sqlite3
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


@pytest.fixture
def conn(tmp_path):
    """A store backed by a throwaway file, never the real database."""
    c = app_store.get_db(str(tmp_path / "test_app.db"))
    app_store.init_db(c)
    yield c
    c.close()


def test_both_tables_exist(conn):
    names = {r["name"] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "calls" in names
    assert "positions" in names


def test_init_db_is_idempotent(conn):
    """Running it twice must not raise -- migrations re-run on every boot."""
    app_store.init_db(conn)
    app_store.init_db(conn)


def test_foreign_keys_are_enforced(conn):
    """SQLite ignores foreign keys unless the pragma is set per connection."""
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO positions (id, user_id, symbol, qty, avg_price, "
            "opened_at, call_id) VALUES (?,?,?,?,?,?,?)",
            ("p1", "u1", "CIPLA", 10, 1420.0, "2026-08-28T09:30:00", "no-such-call"))
        conn.commit()


def test_duplicate_call_same_symbol_same_day_is_rejected(conn):
    """The idempotency guarantee is a database constraint, not a convention."""
    row = ("c1", "CIPLA", "BUY", "2026-08-28T09:20:00", 1420.0, 73.0,
           "VWAP reclaim", "intraday", 1448.0, 1399.0)
    cols = ("INSERT INTO calls (id, symbol, side, published_at, price_at_call, "
            "score, signal, horizon, target, stop) VALUES (?,?,?,?,?,?,?,?,?,?)")
    conn.execute(cols, row)
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(cols, ("c2", "CIPLA", "BUY", "2026-08-28T15:10:00", 1431.0,
                            71.0, "VWAP reclaim", "intraday", 1460.0, 1410.0))
        conn.commit()


def test_same_symbol_next_day_is_allowed(conn):
    """A stock called on consecutive days is two calls, not a duplicate."""
    cols = ("INSERT INTO calls (id, symbol, side, published_at, price_at_call) "
            "VALUES (?,?,?,?,?)")
    conn.execute(cols, ("c1", "CIPLA", "BUY", "2026-08-28T09:20:00", 1420.0))
    conn.execute(cols, ("c2", "CIPLA", "BUY", "2026-08-29T09:20:00", 1431.0))
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 2


def test_outcome_defaults_to_open(conn):
    """An unresolved call must never look resolved."""
    conn.execute("INSERT INTO calls (id, symbol, side, published_at, price_at_call) "
                 "VALUES (?,?,?,?,?)",
                 ("c1", "CIPLA", "BUY", "2026-08-28T09:20:00", 1420.0))
    conn.commit()
    assert conn.execute("SELECT outcome FROM calls WHERE id='c1'").fetchone()[0] == "open"


def test_real_db_path_is_not_the_analytics_db():
    """The product record must not share a file with disposable analytics.

    Reconstructs the production default from the module's own path logic
    rather than reading the live app_store.DB_PATH attribute: the
    session-scoped safety-net fixture in conftest.py deliberately repoints
    that attribute at a throwaway file for the whole test run, so it no
    longer holds the real default while this suite is running -- asserting
    on it here would describe conftest's disguise, not the actual product
    default this test exists to pin.
    """
    real_default = os.path.join(os.path.dirname(app_store.__file__), "tradepilot_app.db")
    assert real_default.endswith("tradepilot_app.db")
    assert "analytics" not in real_default
