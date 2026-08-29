"""Tests for the publish job.

The job is the ONLY writer of `calls`. Everything the track record later claims
rests on it recording exactly what was published, once per symbol per day.

The PAYLOAD fixture mirrors the SHAPE actually served by /api/picks (verified
against the live endpoint), not the internal scorer record it is built from:
direction is BUY/HOLD/AVOID (not UP/DOWN), target and stopLoss are percentage
keys (not target_pct/stop_loss_pct), and reasons is a list of {"text", "type"}
dicts (not plain strings).
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
         "direction": "BUY", "recommendation": "Strong Buy",
         "reasons": [
             {"text": "Reclaimed VWAP", "type": "positive"},
             {"text": "Volume 2.1x average", "type": "positive"},
             {"text": "FII selling (-5040 Cr)", "type": "negative"},
         ],
         "stopLoss": 1.5, "target": 2.0},
        {"symbol": "ADANIPORTS.NS", "name": "ADANIPORTS", "price": 1714.0,
         "score": 66, "direction": "BUY", "recommendation": "Buy",
         "reasons": [{"text": "Broke previous-day high", "type": "positive"}],
         "stopLoss": 2.0, "target": 3.0},
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
    assert rows[0]["signal"] == (
        "Reclaimed VWAP; Volume 2.1x average; FII selling (-5040 Cr)")


def test_signal_contains_negative_reason_text_no_dict_reprs():
    """Negative reasons are part of why the call looks the way it does and
    must survive the mapping as plain text, not a stringified dict."""
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert "FII selling (-5040 Cr)" in rows[0]["signal"]
    assert "{" not in rows[0]["signal"]


def test_id_is_stable_for_symbol_and_day():
    """Same symbol, same day, same id -- so a re-run collides deterministically."""
    a = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")[0]["id"]
    b = publish_calls.build_rows(PAYLOAD, "2026-08-28T15:10:00")[0]["id"]
    assert a == b


def test_side_comes_from_direction():
    rows = publish_calls.build_rows(PAYLOAD, "2026-08-28T09:20:00")
    assert rows[0]["side"] == "BUY"


def test_sell_direction_has_target_below_and_stop_above_price():
    payload = {
        "category": "stocks",
        "picks": [
            {"symbol": "XYZ.NS", "price": 500.0, "score": 70,
             "direction": "SELL",
             "reasons": [{"text": "Bearish RSI divergence", "type": "negative"}],
             "target": -2.0, "stopLoss": -1.5},
        ],
    }
    rows = publish_calls.build_rows(payload, "2026-08-28T09:20:00")
    assert rows[0]["side"] == "SELL"
    assert rows[0]["target"] < 500.0
    assert rows[0]["stop"] > 500.0


def test_hold_direction_is_skipped():
    """HOLD is not an actionable call -- recording one so a resolver can later
    grade it would manufacture a hit rate out of non-advice."""
    payload = {
        "category": "stocks",
        "picks": [
            {"symbol": "PARKED.NS", "price": 100.0, "score": 40,
             "direction": "HOLD", "reasons": [], "target": 1.0, "stopLoss": 1.0},
        ],
    }
    rows = publish_calls.build_rows(payload, "2026-08-28T09:20:00")
    assert rows == []


def test_avoid_direction_is_skipped():
    payload = {
        "category": "stocks",
        "picks": [
            {"symbol": "AVOIDED.NS", "price": 100.0, "score": 20,
             "direction": "AVOID", "reasons": [], "target": 1.0, "stopLoss": 1.0},
        ],
    }
    rows = publish_calls.build_rows(payload, "2026-08-28T09:20:00")
    assert rows == []


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
