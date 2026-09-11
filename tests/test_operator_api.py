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
