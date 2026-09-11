"""Phase 1 cheap wins: pure functions against tmp_path fixtures, routes via client."""
import json
from datetime import date
from pathlib import Path

import pytest


def test_operator_blueprint_is_registered(client):
    r = client.get("/api/operator/ping")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}


POS = {
    "symbol": "MAXHEALTH", "entry_price": 1036.8, "qty": 16, "cost": 16588.8,
    "entry_time": "14:10:48", "entry_date": "2026-09-09",
    "sl_price": 1023.32, "target_price": 1069.98,
    "position_type": "LONG", "pool": "SWING",
    "trailing_activated": False, "peak_price": 1038.5, "trough_price": 1036.8,
    "score": 78.9, "direction": "BUY", "reasons": [], "days_held": 1,
}


def test_position_row_carries_stop_and_target():
    from prototype.operator_api import position_row
    row = position_row("v5", "SWING", POS)
    assert row["engine"] == "v5"
    assert row["side"] == "LONG"
    assert row["entry"] == 1036.8 and row["qty"] == 16
    assert row["value"] == 16589
    assert row["sl_price"] == 1023.32
    assert row["target_price"] == 1069.98
    assert row["peak_price"] == 1038.5 and row["trough_price"] == 1036.8
    assert row["trailing_activated"] is False
    assert row["score"] == 78.9


def test_position_row_missing_stop_is_none_not_zero():
    from prototype.operator_api import position_row
    bare = {"symbol": "X", "entry_price": 10.0, "qty": 1, "position_type": "SHORT"}
    row = position_row("v5", "INTRADAY", bare)
    assert row["side"] == "SHORT"
    assert row["sl_price"] is None and row["target_price"] is None
    assert row["value"] == 10


def _fresh_desk(client, monkeypatch):
    """api_desk caches for 30 s; reset so each test sees its own patching."""
    import prototype.app as app_module
    app_module._desk_cache["time"] = 0
    app_module._desk_cache["data"] = None
    return client.get("/api/desk").get_json()


def test_desk_open_positions_carry_stop_fields(client, monkeypatch):
    data = _fresh_desk(client, monkeypatch)
    for row in data["open_positions"]:
        for k in ("sl_price", "target_price", "peak_price", "trough_price",
                  "trailing_activated", "score"):
            assert k in row, f"{k} missing from open_positions row"


def test_unrealized_signs():
    from prototype.operator_api import unrealized
    assert unrealized("LONG", 100.0, 10, 105.0) == 50.0
    assert unrealized("SHORT", 100.0, 10, 105.0) == -50.0
    assert unrealized("SHORT", 1757.4, 8, 1740.0) == pytest.approx(139.2)


def test_enrich_with_marks_computes_pnl_and_stop_distance():
    from prototype.operator_api import enrich_with_marks, position_row
    long_row = position_row("v5", "SWING", POS)                     # LONG 1036.8, sl 1023.32
    short_row = position_row("v5", "INTRADAY", {
        "symbol": "ADANIPORTS", "entry_price": 1757.4, "qty": 8,
        "sl_price": 1768.1, "position_type": "SHORT"})
    rows = enrich_with_marks([long_row, short_row],
                             {"MAXHEALTH": 1040.0, "ADANIPORTS": 1760.0})
    assert rows[0]["mark"] == 1040.0
    assert rows[0]["unrealized_pnl"] == pytest.approx(51.2)
    assert rows[0]["to_stop_pct"] == pytest.approx((1040.0 - 1023.32) / 1040.0 * 100)
    assert rows[0]["risk_at_stop"] == pytest.approx((1023.32 - 1036.8) * 16)
    assert rows[1]["unrealized_pnl"] == pytest.approx(-20.8)
    assert rows[1]["to_stop_pct"] == pytest.approx((1768.1 - 1760.0) / 1760.0 * 100)
    assert rows[1]["risk_at_stop"] == pytest.approx((1757.4 - 1768.1) * 8)


def test_enrich_with_marks_missing_mark_is_null_not_zero():
    from prototype.operator_api import enrich_with_marks, position_row
    row = position_row("v5", "SWING", POS)
    rows = enrich_with_marks([row], {})
    assert rows[0]["mark"] is None
    assert rows[0]["unrealized_pnl"] is None
    assert rows[0]["to_stop_pct"] is None
    assert rows[0]["risk_at_stop"] == pytest.approx((1023.32 - 1036.8) * 16)  # needs no mark


def test_marks_for_swallows_feed_failure(monkeypatch):
    from prototype import operator_api
    import prototype.v4.kite_data as kd

    def boom(symbols):
        raise RuntimeError("kite down")
    monkeypatch.setattr(kd, "get_quotes", boom)
    assert operator_api.marks_for(["INFY"]) == {}


def test_marks_for_maps_last_price(monkeypatch):
    from prototype import operator_api
    import prototype.v4.kite_data as kd
    monkeypatch.setattr(kd, "get_quotes",
                        lambda symbols: {"INFY": {"last_price": 1489.5}, "TCS": {"last_price": None}})
    assert operator_api.marks_for(["INFY", "TCS"]) == {"INFY": 1489.5}


def test_desk_fleet_has_unrealized_and_risk(client, monkeypatch):
    from prototype import operator_api
    monkeypatch.setattr(operator_api, "marks_for", lambda symbols: {})
    data = _fresh_desk(client, monkeypatch)
    f = data["fleet"]
    assert "unrealized" in f and "risk_at_stop" in f and "deployed" in f and "unpriced" in f
    assert f["unpriced"] == len(data["open_positions"])       # no marks => all unpriced
    for row in data["open_positions"]:
        assert row["mark"] is None and row["unrealized_pnl"] is None


def test_live_trades_open_rows_do_not_fake_pnl(client, monkeypatch):
    from prototype import operator_api
    monkeypatch.setattr(operator_api, "marks_for", lambda symbols: {})
    r = client.get("/api/live-trades")
    assert r.status_code == 200
    for eng in r.get_json().get("engines", {}).values():
        for t in eng.get("trades", []):
            if t.get("status") == "open":
                assert t["pnl"] is None
