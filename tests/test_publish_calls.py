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


def test_v2_shaped_pick_produces_the_same_levels_via_pct_suffixed_keys():
    """app.py falls back to the v2/v1 engines on ImportError from v4.

    Those engines emit stop_loss_pct/target_pct instead of v4's
    stopLoss/target. Reading only the v4 spelling silently captures every
    such call with no levels at all.
    """
    payload = {
        "category": "stocks",
        "picks": [
            {"symbol": "CIPLA.NS", "price": 1420.0, "score": 73,
             "direction": "BUY", "reasons": [],
             "stop_loss_pct": 1.5, "target_pct": 2.0},
        ],
    }
    rows = publish_calls.build_rows(payload, "2026-08-28T09:20:00")
    assert rows[0]["target"] == pytest.approx(1420.0 * 1.02)
    assert rows[0]["stop"] == pytest.approx(1420.0 * 0.985)


def test_both_spellings_present_prefers_the_v4_names():
    """If a pick somehow carries both, stopLoss/target (v4) wins."""
    payload = {
        "category": "stocks",
        "picks": [
            {"symbol": "CIPLA.NS", "price": 1420.0, "score": 73,
             "direction": "BUY", "reasons": [],
             "stopLoss": 1.5, "target": 2.0,
             "stop_loss_pct": 9.0, "target_pct": 9.0},
        ],
    }
    rows = publish_calls.build_rows(payload, "2026-08-28T09:20:00")
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
            # target/stopLoss are UNSIGNED magnitudes exactly as composite_scorer
            # produces them (a volatility multiplier with no reference to
            # direction) -- do not "helpfully" re-sign these to make a SELL
            # test pass. The sign that decides which side of the entry the
            # levels land on comes from build_rows reading `side`, not from
            # the input data.
            {"symbol": "XYZ.NS", "price": 500.0, "score": 70,
             "direction": "SELL",
             "reasons": [{"text": "Bearish RSI divergence", "type": "negative"}],
             "target": 2.0, "stopLoss": 1.5},
        ],
    }
    rows = publish_calls.build_rows(payload, "2026-08-28T09:20:00")
    assert rows[0]["side"] == "SELL"
    assert rows[0]["target"] < 500.0
    assert rows[0]["stop"] > 500.0


def test_same_magnitudes_produce_mirrored_levels_for_buy_and_sell():
    """The side decides which way the levels go -- not the sign of the input.

    composite_scorer emits unsigned magnitudes, so BUY and SELL picks with
    identical target/stopLoss values must produce mirrored levels around the
    entry. If this fails, a short's target sits above its entry and the
    resolver grades it a hit whenever the stock rises.
    """
    base = {"symbol": "X.NS", "price": 1000.0, "score": 70,
            "target": 3.0, "stopLoss": 1.0, "reasons": []}
    buy = publish_calls.build_rows(
        {"category": "stocks", "picks": [dict(base, direction="BUY")]},
        "2026-08-28T09:20:00")[0]
    sell = publish_calls.build_rows(
        {"category": "stocks", "picks": [dict(base, direction="SELL")]},
        "2026-08-28T09:20:00")[0]
    assert buy["stop"] < 1000.0 < buy["target"]
    assert sell["target"] < 1000.0 < sell["stop"]
    assert buy["target"] == pytest.approx(1030.0)
    assert sell["target"] == pytest.approx(970.0)


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


def test_fetch_picks_raises_when_payload_carries_an_error_key(monkeypatch):
    """app.py:2839-2840 returns HTTP 200 with {"picks": [], "error": str(e)}
    when scoring fails. A 200 status alone does not mean success -- treating
    it as one would silently publish an empty day and exit 0, defeating this
    pipeline's own loud-failure contract at its most likely failure point.
    """
    import json as _json

    class FakeResponse:
        status = 200

        def read(self):
            return _json.dumps(
                {"picks": [], "error": "scorer timed out"}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(publish_calls.urllib.request, "urlopen",
                         lambda url, timeout=30: FakeResponse())
    with pytest.raises(RuntimeError, match="scorer timed out"):
        publish_calls.fetch_picks("http://fake/api/picks")


def test_fetch_picks_does_not_raise_on_an_honest_empty_picks_list(monkeypatch):
    """A genuinely empty picks list with no error key is not a failure."""
    import json as _json

    class FakeResponse:
        status = 200

        def read(self):
            return _json.dumps({"category": "stocks", "picks": []}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(publish_calls.urllib.request, "urlopen",
                         lambda url, timeout=30: FakeResponse())
    payload = publish_calls.fetch_picks("http://fake/api/picks")
    assert payload["picks"] == []


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
