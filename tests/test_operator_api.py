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


def _write_verdicts(root: Path, engine: str, day: str, items: list):
    d = root / engine
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{day}_verdicts.json").write_text(json.dumps(
        {"date": day, "engine": engine, "verdicts": items, "updated_at": f"{day} 15:08:11"}))


V_OK = {"symbol": "ADANIPOWER", "verdict": "approved", "checked_at": "2026-09-10T09:06:07",
        "plan": {"side": "SHORT", "entry": 100.0, "target": 97.0, "stop": 102.0, "pool": "INTRADAY",
                 "score": 31.2, "rationale": "long prose"},
        "reasons": ["check_can_trade: OK", "pool_cash: OK", "soft:score_near_threshold: clear (31.2)"]}
V_REJ = {"symbol": "HINDALCO", "verdict": "rejected", "checked_at": "2026-09-10T09:36:00",
         "plan": {"side": "SHORT", "entry": 612.4, "target": 600.0, "stop": 618.0, "pool": "INTRADAY",
                  "score": 21.0, "rationale": "x"},
         "reasons": ["check_can_trade: OK", "check_position_size: FAIL size 0", "pool_cash: OK"]}


def test_load_verdicts_marks_failed_reasons_and_drops_rationale(tmp_path):
    from prototype.operator_api import load_verdicts
    _write_verdicts(tmp_path, "v5", "2026-09-10", [V_OK, V_REJ])
    out = load_verdicts(tmp_path, "2026-09-10")
    assert out["engines"] == ["v5"] and out["count"] == 2
    rej = next(v for v in out["verdicts"] if v["symbol"] == "HINDALCO")
    assert rej["failed"] == ["check_position_size: FAIL size 0"]
    assert "rationale" not in rej["plan"]
    ok = next(v for v in out["verdicts"] if v["symbol"] == "ADANIPOWER")
    assert ok["failed"] == []
    assert out["by_symbol"]["HINDALCO"][0]["engine"] == "v5"
    assert out["by_symbol"]["HINDALCO"][0]["score"] == 21.0


def test_load_verdicts_filters(tmp_path):
    from prototype.operator_api import load_verdicts
    _write_verdicts(tmp_path, "v5", "2026-09-10", [V_OK, V_REJ])
    _write_verdicts(tmp_path, "v5_wide", "2026-09-10", [V_OK])
    assert load_verdicts(tmp_path, "2026-09-10", only="rejected")["count"] == 1
    assert load_verdicts(tmp_path, "2026-09-10", engines=["v5_wide"])["count"] == 1
    assert load_verdicts(tmp_path, "2026-09-10", symbols={"HINDALCO"})["count"] == 1
    assert load_verdicts(tmp_path, "2026-09-11")["engines"] == []


def test_verdicts_route(client, tmp_path, monkeypatch):
    from prototype import operator_api
    _write_verdicts(tmp_path, "v5", "2026-09-10", [V_OK, V_REJ])
    monkeypatch.setattr(operator_api, "TRADES_ROOT", tmp_path)
    r = client.get("/api/verdicts/2026-09-10?only=rejected")
    assert r.status_code == 200
    body = r.get_json()
    assert set(body) >= {"date", "engines", "count", "verdicts", "by_symbol"}
    assert body["engines"] == ["v5"]
    assert body["count"] == 1
    assert body["verdicts"][0]["symbol"] == "HINDALCO"


def test_verdicts_route_rejects_bad_date(client):
    assert client.get("/api/verdicts/not-a-date").status_code == 400


def test_datalink_rows_kite_ok_and_index_sources():
    from prototype.operator_api import datalink_rows
    rows = datalink_rows(
        {"enabled": True, "kite_calls": 40, "kite_ok": 40, "fallbacks": 0,
         "token_failures": 0, "last_error": None, "last_fallback_at": None},
        (True, "Soumya (AB1234)"),
        {"nifty": {"price": 24861.15, "source": "nse", "stale": False},
         "sensex": {"price": 81205.3, "source": "bse", "stale": False},
         "vix": {"price": 13.9, "source": "csv", "stale": True}})
    byname = {r["name"]: r for r in rows}
    assert byname["Kite"]["state"] == "ok" and "AB1234" in byname["Kite"]["detail"]
    assert byname["nse"]["state"] == "ok"
    assert byname["bse"]["state"] == "ok"
    assert byname["csv"]["state"] == "stale"


def test_datalink_rows_kite_disabled_and_dead_token():
    from prototype.operator_api import datalink_rows
    rows = datalink_rows({"enabled": False}, (False, "no token"), {})
    assert rows[0] == {"name": "Kite", "state": "off", "detail": "paper mode, feed disabled"}
    rows = datalink_rows({"enabled": True, "kite_ok": 0, "kite_calls": 3,
                          "last_error": "TokenException"}, (False, "TokenException"), {})
    assert rows[0]["state"] == "down" and "TokenException" in rows[0]["detail"]


def test_datalinks_route(client, monkeypatch):
    import prototype.v4.kite_data as kd
    monkeypatch.setattr(kd, "health", lambda: {"enabled": False})
    monkeypatch.setattr(kd, "token_alive", lambda: (False, "no token"))
    r = client.get("/api/health/datalinks")
    assert r.status_code == 200
    body = r.get_json()
    assert body["links"][0]["name"] == "Kite" and body["links"][0]["state"] == "off"
    assert "generated_at" in body
