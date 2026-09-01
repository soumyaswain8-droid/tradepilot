"""Store for the client product's own data -- published calls and client positions.

Deliberately a SEPARATE database file from tradepilot_analytics.db. Analytics is
behavioural tracking: disposable and rebuildable. `calls` is the product record --
if it is lost, the track record is lost, and it cannot be reconstructed without
retroactively labelling engine history as calls, which the design rejects.

Connection settings mirror prototype/analytics.py, which has run in production
here for months: WAL for concurrent readers, a busy timeout so a writer does not
fail instantly under contention, and Row so callers get mappings not tuples.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "tradepilot_app.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id             TEXT PRIMARY KEY,
    symbol         TEXT NOT NULL,
    side           TEXT NOT NULL,
    published_at   TEXT NOT NULL,
    price_at_call  REAL NOT NULL,
    score          REAL,
    signal         TEXT,
    horizon        TEXT,
    target         REAL,
    stop           REAL,
    outcome_price  REAL,
    outcome_at     TEXT,
    outcome        TEXT NOT NULL DEFAULT 'open'
);

-- Idempotency is a constraint, not a convention: re-running the publish job
-- cannot double-count a day.
CREATE UNIQUE INDEX IF NOT EXISTS ux_calls_symbol_day
    ON calls (symbol, date(published_at));

CREATE INDEX IF NOT EXISTS ix_calls_outcome
    ON calls (outcome, published_at);

CREATE TABLE IF NOT EXISTS positions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    qty         REAL NOT NULL,
    avg_price   REAL NOT NULL,
    opened_at   TEXT NOT NULL,
    closed_at   TEXT,
    exit_price  REAL,
    source      TEXT NOT NULL DEFAULT 'manual',
    broker_ref  TEXT,
    call_id     TEXT REFERENCES calls(id)
);

CREATE INDEX IF NOT EXISTS ix_positions_user
    ON positions (user_id, closed_at);

CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    email          TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    disabled_at    TEXT,
    failed_count   INTEGER NOT NULL DEFAULT 0,
    locked_until   TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email
    ON users (lower(email));
"""


def get_db(path=None):
    """Open the store. Pass `path` to point at a throwaway file in tests."""
    conn = sqlite3.connect(path or DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn):
    """Create tables and indexes. Safe to run on every boot."""
    conn.executescript(SCHEMA)
    conn.commit()
