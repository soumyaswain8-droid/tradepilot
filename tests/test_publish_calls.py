"""Tests for the publish job.

The job is the ONLY writer of `calls`. Everything the track record later claims
rests on it recording exactly what was published, once per symbol per day.
"""
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


def _load(name, relpath):
    """Import a hyphenated script file as a module."""
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(REPO_ROOT, relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


publish_calls = _load("publish_calls", "scripts/publish-calls.py")


PAYLOAD = {
    "category": "stocks",
    "horizon": "intraday",
    "engine": "v4",
    "picks": [
        {"symbol": "CIPLA.NS", "name": "CIPLA", "price": 1420.0, "score": 73,
         "direction": "UP", "recommendation": "Strong Buy",
         "reasons": ["Reclaimed VWAP", "Volume 2.1x average"],
         "stop_loss_pct": 1.5, "target_pct": 2.0},
        {"symbol": "ADANIPORTS.NS", "name": "ADANIPORTS", "price": 1714.0,
         "score": 66, "direction": "UP", "recommendation": "Buy",
         "reasons": ["Broke previous-day high"],
         "stop_loss_pct": 2.0, "target_pct": 3.0},
    ],
}


@pytest.fixture
def conn(tmp_path):
    c = app_store.get_db(str(tmp_path / "test_app.db"))
    app_store.init_db(c)
    yield c
    c.close()


def test_builds_one_row_per_pick():
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert len(rows) == 2


def test_symbol_is_stripped_of_exchange_suffix():
    """Clients see CIPLA, never CIPLA.NS."""
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["symbol"] == "CIPLA"


def test_target_and_stop_are_absolute_prices_not_percentages():
    """The scorer gives percentages; a call must record the actual levels."""
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["target"] == pytest.approx(1420.0 * 1.02)
    assert rows[0]["stop"] == pytest.approx(1420.0 * 0.985)


def test_signal_is_plain_english_joined_reasons():
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["signal"] == "Reclaimed VWAP; Volume 2.1x average"


def test_id_is_stable_for_symbol_and_day():
    """Same symbol, same day, same id -- so a re-run collides deterministically."""
    a = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")[0]["id"]
    b = publish_calls.build_rows(PAYLOAD, "2026-08-28T15:10:00")[0]["id"]
    assert a == b


def test_side_comes_from_direction():
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["side"] == "BUY"


def test_rejects_non_stock_categories():
    """/api/picks?category=etfs returns hardcoded literal arrays with invented
    recommendation strings. Those must never become calls shown to a client."""
    with pytest.raises(ValueError, match="stocks"):
        publish_calls.build_rows({"category": "etfs", "picks": []},
                                 "2026-08-28T09:20:00")


def test_insert_is_idempotent(conn):
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert publish_calls.insert_rows(conn, rows) == 2
    assert publish_calls.insert_rows(conn, rows) == 0
    assert conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0] == 2


def test_inserted_calls_start_open(conn):
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    publish_calls.insert_rows(conn, rows)
    outcomes = {r["outcome"] for r in conn.execute("SELECT outcome FROM calls")}
    assert outcomes == {"open"}


def test_empty_picks_inserts_nothing_and_does_not_raise(conn):
    rows = publish_calls.build_rows({"category": "stocks", "picks": []},
                                    "2026-08-28T09:20:00")
    assert publish_calls.insert_rows(conn, rows) == 0
