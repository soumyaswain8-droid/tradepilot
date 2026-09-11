# Operator Terminal Phase 1: Cheap Wins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose five pieces of data that already exist on disk or in functions but no route serves: stops on open positions, per-engine verdicts, data-link health, shadow experiment deltas, and a real unrealised P&L. Plus two small honesty fixes: exit durations and a true model trained-at time.

**Architecture:** One new module `prototype/operator_api.py` holds pure functions (path in, dict out) and a Flask blueprint with three new routes. `app.py` gains one blueprint registration and four small edits inside existing routes that call those pure functions. Pure functions are tested against fixture files in `tmp_path`; routes get one smoke test each through the existing `client` fixture. No engine code changes.

**Tech Stack:** Python 3, Flask blueprints, pytest (`tests/conftest.py` provides `flask_app` and `client`), Kite batch quotes via `prototype/v4/kite_data.py`.

**Spec:** `docs/superpowers/specs/2026-09-11-operator-terminal-redesign-design.md` (Data, Phase 1). Field map: `docs/design/2026-09-11-operator-redesign/existing-page-map.md`.

## Global Constraints

- No engine code changes. Only `prototype/operator_api.py` (new), `prototype/app.py`, and tests are touched.
- A missing live price renders `null` in JSON and "price unavailable" on screens, never `0`.
- Run tests from the repo root as `python3 -m pytest tests/... -q` (conftest puts the repo root on `sys.path`; the `-m` form matters).
- Do not restart the running Flask server during market hours (09:15 to 15:30 IST). Tests use the test client and need no restart.
- Git runs under Rosetta in this shell. Use `arch -arm64 git ...` for every git command.
- Commit messages end with the attribution trailer used in this session:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FVyFt7SkQR8LnFHHN6twrP
  ```
- Data locations, verified 2026-09-11: positions in `docs/paper-trades/<engine>/positions_active.json` → `positions.<POOL>[]`; verdicts in `docs/paper-trades/<engine>/<date>_verdicts.json`; shadows in `docs/research/shadows/armband/<date>.json` and `docs/research/shadows/regime/<date>.json`; models in `prototype/models/*.pkl`.

---

### Task 1: Module scaffold, blueprint registration, smoke test

**Files:**
- Create: `prototype/operator_api.py`
- Modify: `prototype/app.py:66-68` (blueprint registration block)
- Test: `tests/test_operator_api.py`

**Interfaces:**
- Produces: `prototype.operator_api.bp` (Flask `Blueprint`, `url_prefix="/api"`), constants `REPO_ROOT`, `TRADES_ROOT`, `SHADOWS_ROOT`, `MODELS_DIR`.
- Produces: `GET /api/operator/ping` → `{"ok": true}` (kept as the blueprint's liveness check).

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_operator_api.py
"""Phase 1 cheap wins: pure functions against tmp_path fixtures, routes via client."""
import json
from datetime import date
from pathlib import Path

import pytest


def test_operator_blueprint_is_registered(client):
    r = client.get("/api/operator/ping")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True}
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 -m pytest tests/test_operator_api.py::test_operator_blueprint_is_registered -q`
Expected: FAIL, status 404.

- [ ] **Step 3: Create the module**

```python
# prototype/operator_api.py
"""Operator-tier API: the Phase 1 cheap wins from the 2026-09-11 redesign spec.

Pure functions take paths and dicts and return dicts, so tests run against
tmp_path fixtures. The blueprint wraps them. Nothing here touches engine code.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

REPO_ROOT = Path(__file__).resolve().parent.parent
TRADES_ROOT = REPO_ROOT / "docs" / "paper-trades"
SHADOWS_ROOT = REPO_ROOT / "docs" / "research" / "shadows"
MODELS_DIR = Path(__file__).resolve().parent / "models"

bp = Blueprint("operator_api", __name__, url_prefix="/api")


@bp.get("/operator/ping")
def ping():
    return jsonify({"ok": True})
```

- [ ] **Step 4: Register the blueprint in app.py**

In `prototype/app.py`, directly after line 68 (`app.register_blueprint(_accounts_web_bp)`), add:

```python
from prototype.operator_api import bp as _operator_api_bp  # noqa: E402
app.register_blueprint(_operator_api_bp)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_operator_api.py -q`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
arch -arm64 git add prototype/operator_api.py prototype/app.py tests/test_operator_api.py
arch -arm64 git commit -m "feat(operator-api): blueprint scaffold for Phase 1 cheap wins"
```

---

### Task 2: Stops and targets on open positions

**Files:**
- Modify: `prototype/operator_api.py`
- Modify: `prototype/app.py:3956-3966` (the `open_positions.append({...})` block inside `api_desk`)
- Test: `tests/test_operator_api.py`

**Interfaces:**
- Produces: `position_row(engine: str, pool: str, pos: dict) -> dict` with keys `engine, symbol, side, qty, entry, pool, value, entry_date, entry_time, sl_price, target_price, peak_price, trough_price, trailing_activated, score`. `side` is `"LONG"` or `"SHORT"` from `pos["position_type"]`. Missing stop fields are `None`.
- Consumes: the `pos` dict shape of `positions_active.json` → `positions.<POOL>[]` (keys `symbol, entry_price, qty, entry_time, entry_date, sl_price, target_price, position_type, pool, trailing_activated, peak_price, trough_price, score, direction, reasons`).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_operator_api.py -q -k position_row`
Expected: FAIL, `ImportError: cannot import name 'position_row'`.

- [ ] **Step 3: Implement position_row**

Append to `prototype/operator_api.py`:

```python
def _f(v):
    """float or None. Never coerce a missing price to 0."""
    try:
        return None if v is None else float(v)
    except (TypeError, ValueError):
        return None


def position_row(engine: str, pool: str, pos: dict) -> dict:
    """One open position as the desk shows it, plus the stop/target fields the
    engine already stores and the old desk dropped."""
    ep, q = _f(pos.get("entry_price")), pos.get("qty")
    try:
        value = round(ep * int(q), 0) if ep and q else 0
    except (TypeError, ValueError):
        value = 0
    return {
        "engine": engine, "symbol": pos.get("symbol"),
        "side": (pos.get("position_type") or "LONG").upper(),
        "qty": q, "entry": ep, "pool": pool, "value": value,
        "entry_date": pos.get("entry_date"), "entry_time": pos.get("entry_time"),
        "sl_price": _f(pos.get("sl_price")),
        "target_price": _f(pos.get("target_price")),
        "peak_price": _f(pos.get("peak_price")),
        "trough_price": _f(pos.get("trough_price")),
        "trailing_activated": bool(pos.get("trailing_activated", False)),
        "score": _f(pos.get("score")),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_operator_api.py -q -k position_row`
Expected: 2 passed.

- [ ] **Step 5: Use it in api_desk**

In `prototype/app.py`, inside `api_desk`, replace lines 3956-3966:

```python
                        ep, q = pos.get("entry_price"), pos.get("qty")
                        open_positions.append({
                            "engine": d.name, "symbol": pos.get("symbol"),
                            "side": (pos.get("position_type") or "LONG").upper(),
                            "qty": q, "entry": ep, "pool": pool,
                            "value": round(float(ep) * int(q), 0) if ep and q else 0,
                            "entry_date": pos.get("entry_date"),
                            "entry_time": pos.get("entry_time")})
```

with:

```python
                        open_positions.append(_opapi.position_row(d.name, pool, pos))
```

and add, at the top of `api_desk` (first line of the function body, before the cache check):

```python
    from prototype import operator_api as _opapi
```

- [ ] **Step 6: Write the route test**

Append to `tests/test_operator_api.py`:

```python
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
```

- [ ] **Step 7: Run all module tests**

Run: `python3 -m pytest tests/test_operator_api.py tests/test_web_routes.py -q`
Expected: all passed. (If the real `docs/paper-trades` has no open positions the loop asserts nothing; that is fine, the key contract is still enforced by Task 2 Step 1.)

- [ ] **Step 8: Commit**

```bash
arch -arm64 git add prototype/operator_api.py prototype/app.py tests/test_operator_api.py
arch -arm64 git commit -m "feat(desk): pass stop, target and peak prices through on open positions"
```

---

### Task 3: Live marks and a real unrealised P&L

**Files:**
- Modify: `prototype/operator_api.py`
- Modify: `prototype/app.py` `api_desk` (positions block and `fleet` init at line 3915, response at 4014-4025) and `api_live_trades` line 542
- Test: `tests/test_operator_api.py`

**Interfaces:**
- Produces: `marks_for(symbols: list[str]) -> dict[str, float]` wrapping `prototype.v4.kite_data.get_quotes`; symbols Kite does not return are absent; any failure returns `{}`.
- Produces: `enrich_with_marks(rows: list[dict], marks: dict[str, float]) -> list[dict]` adding to each row: `mark` (float or None), `unrealized_pnl` (float or None), `to_stop_pct` (float or None, positive while the stop is on the safe side), `risk_at_stop` (float or None, negative rupees lost if the stop fills from entry). Modifies rows in place and returns them.
- Produces: `unrealized(side: str, entry: float, qty: int, mark: float) -> float`.
- Consumes: `position_row` rows from Task 2.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_operator_api.py -q -k "unrealized or enrich or marks_for"`
Expected: FAIL with ImportError on `unrealized`.

- [ ] **Step 3: Implement**

Append to `prototype/operator_api.py`:

```python
def unrealized(side: str, entry: float, qty: int, mark: float) -> float:
    sign = -1.0 if (side or "LONG").upper() == "SHORT" else 1.0
    return round((mark - entry) * int(qty) * sign, 2)


def marks_for(symbols) -> dict:
    """{SYMBOL: last_price} from the licensed feed. Absent means unknown.
    A silent 0.0 is how bad fills happen, so failures return {} not zeros."""
    syms = sorted({str(s).upper() for s in symbols if s})
    if not syms:
        return {}
    try:
        from prototype.v4 import kite_data as kd
        quotes = kd.get_quotes(syms) or {}
    except Exception:
        return {}
    out = {}
    for sym, q in quotes.items():
        lp = _f((q or {}).get("last_price"))
        if lp:
            out[str(sym).upper()] = lp
    return out


def enrich_with_marks(rows: list, marks: dict) -> list:
    """Add mark, unrealized_pnl, to_stop_pct and risk_at_stop to position rows.
    Anything that needs a mark is None when the mark is missing."""
    for r in rows:
        side = (r.get("side") or "LONG").upper()
        sign = -1.0 if side == "SHORT" else 1.0
        entry, qty, sl = _f(r.get("entry")), r.get("qty"), _f(r.get("sl_price"))
        mark = marks.get(str(r.get("symbol") or "").upper())
        r["mark"] = mark
        r["unrealized_pnl"] = (unrealized(side, entry, qty, mark)
                               if mark and entry is not None and qty else None)
        r["to_stop_pct"] = (round((mark - sl) / mark * 100 * sign, 2)
                            if mark and sl else None)
        r["risk_at_stop"] = (round((sl - entry) * int(qty) * sign, 2)
                             if sl and entry is not None and qty else None)
    return rows
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_operator_api.py -q -k "unrealized or enrich or marks_for"`
Expected: 5 passed.

- [ ] **Step 5: Wire into api_desk**

In `prototype/app.py`, `api_desk`:

a) The `fleet = {...}` init spans lines 3914-3915 and ends with
```python
                          "wins": 0, "turnover": 0.0}
```
Change that closing line to
```python
                          "wins": 0, "turnover": 0.0,
                          "unrealized": None, "risk_at_stop": 0.0, "deployed": 0.0, "unpriced": 0}
```

b) Directly before the `data = {"session": session,` line (4014), add:

```python
    marks = _opapi.marks_for([p["symbol"] for p in open_positions]) if open_positions else {}
    _opapi.enrich_with_marks(open_positions, marks)
    priced = [p["unrealized_pnl"] for p in open_positions if p["unrealized_pnl"] is not None]
    fleet["unrealized"] = round(sum(priced), 0) if priced else None
    fleet["risk_at_stop"] = round(sum(p["risk_at_stop"] or 0.0 for p in open_positions), 0)
    fleet["deployed"] = round(sum(p["value"] or 0.0 for p in open_positions), 0)
    fleet["unpriced"] = sum(1 for p in open_positions if p["mark"] is None)
```

The `fleet` dict comprehension in the response already rounds floats and passes `None` through.

- [ ] **Step 6: Wire into api_live_trades**

In `prototype/app.py`, `api_live_trades`, the loop at lines 538-544 reads `p.get("unrealized_pnl")`, a key the engine never writes. Replace the loop body:

```python
            for p in pdata.get("positions", []):
                openn += 1
                trades.append(_trade(
                    p.get("symbol"), p.get("position_type") or p.get("direction"),
                    p.get("qty"), p.get("entry_price"), p.get("entry_time"),
                    None, None, p.get("unrealized_pnl"), None, "open",
                    p.get("reason"), pool))
```

with:

```python
            for p in pdata.get("positions", []):
                openn += 1
                sym = p.get("symbol")
                mark = _marks.get(str(sym or "").upper())
                upnl = (_opapi.unrealized(p.get("position_type") or "LONG",
                                          float(p["entry_price"]), int(p["qty"]), mark)
                        if mark and p.get("entry_price") and p.get("qty") else None)
                trades.append(_trade(
                    sym, p.get("position_type") or p.get("direction"),
                    p.get("qty"), p.get("entry_price"), p.get("entry_time"),
                    None, None, upnl, None, "open",
                    p.get("reason"), pool))
```

and, before the `for eng in ENGINES:` loop (line 502), collect the marks once for all engines:

```python
    from prototype import operator_api as _opapi
    _open_syms = []
    for _eng in ENGINES:
        _f = BASE / _eng / f"{TODAY}.json"
        if _f.exists():
            try:
                _d = json.loads(_f.read_text())
                for _pool in (_d.get("pools") or {}).values():
                    _open_syms += [p.get("symbol") for p in (_pool.get("positions") or [])]
            except Exception:
                pass
    _marks = _opapi.marks_for(_open_syms)
```

- [ ] **Step 7: Route tests**

Append to `tests/test_operator_api.py`:

```python
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
```

- [ ] **Step 8: Run all module tests**

Run: `python3 -m pytest tests/test_operator_api.py tests/test_web_routes.py -q`
Expected: all passed.

- [ ] **Step 9: Commit**

```bash
arch -arm64 git add prototype/operator_api.py prototype/app.py tests/test_operator_api.py
arch -arm64 git commit -m "fix(desk,live-trades): compute unrealised P&L from live marks instead of a key the engine never writes"
```

---

### Task 4: Verdicts route ("why we skipped it")

**Files:**
- Modify: `prototype/operator_api.py`
- Test: `tests/test_operator_api.py`

**Interfaces:**
- Produces: `load_verdicts(root: Path, date_str: str, engines: list[str] | None = None, only: str | None = None, symbols: set[str] | None = None) -> dict` returning
  `{"date", "engines": [names that had a file], "count", "verdicts": [...], "by_symbol": {SYM: [{"engine", "verdict", "failed", "score", "side", "pool", "checked_at"}]}}`.
  Each item in `verdicts` is the file's item plus `failed` (reasons that are not `": OK"` and not `": clear"`) and minus `plan.rationale` (long prose, not needed on the Market page).
- Produces: `GET /api/verdicts/<date>?engine=v5&only=rejected&symbols=INFY,TCS`.
- Consumes: `docs/paper-trades/<engine>/<date>_verdicts.json` with top-level `date, engine, verdicts[], updated_at` and items `symbol, plan{side,entry,target,stop,invalidation,size_rs,pool,score,rationale}, verdict, reasons[], checked_at, inline_outcome, engine, regime`.

- [ ] **Step 1: Write the failing tests**

```python
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


def test_verdicts_route(client):
    r = client.get("/api/verdicts/2026-09-10?only=rejected")
    assert r.status_code == 200
    body = r.get_json()
    assert set(body) >= {"date", "engines", "count", "verdicts", "by_symbol"}
    assert all(v["verdict"] == "rejected" for v in body["verdicts"])


def test_verdicts_route_rejects_bad_date(client):
    assert client.get("/api/verdicts/not-a-date").status_code == 400
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_operator_api.py -q -k verdicts`
Expected: FAIL (ImportError, then 404).

- [ ] **Step 3: Implement**

Append to `prototype/operator_api.py`:

```python
def _is_date(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except (TypeError, ValueError):
        return False


def _failed_reasons(reasons) -> list:
    out = []
    for r in reasons or []:
        s = str(r)
        if s.endswith(": OK") or ": clear" in s:
            continue
        out.append(s)
    return out


def load_verdicts(root: Path, date_str: str, engines=None, only=None, symbols=None) -> dict:
    """Every pick each engine judged on `date_str`, with the reasons that failed.
    This is the 'why we skipped it' column. File per engine per day; engines
    without a file are simply absent."""
    found, items = [], []
    for d in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        if engines and d.name not in engines:
            continue
        f = d / f"{date_str}_verdicts.json"
        if not f.exists():
            continue
        try:
            doc = json.loads(f.read_text())
        except Exception:
            continue
        found.append(d.name)
        for v in doc.get("verdicts") or []:
            sym = str(v.get("symbol") or "").upper()
            if only and v.get("verdict") != only:
                continue
            if symbols and sym not in symbols:
                continue
            plan = dict(v.get("plan") or {})
            plan.pop("rationale", None)
            item = dict(v)
            item["engine"] = item.get("engine") or d.name
            item["plan"] = plan
            item["failed"] = _failed_reasons(v.get("reasons"))
            items.append(item)
    by_symbol = {}
    for v in items:
        by_symbol.setdefault(v["symbol"], []).append({
            "engine": v["engine"], "verdict": v.get("verdict"), "failed": v["failed"],
            "score": _f(v["plan"].get("score")), "side": v["plan"].get("side"),
            "pool": v["plan"].get("pool"), "checked_at": v.get("checked_at")})
    return {"date": date_str, "engines": found, "count": len(items),
            "verdicts": items, "by_symbol": by_symbol}


@bp.get("/verdicts/<date_str>")
def api_verdicts(date_str):
    if not _is_date(date_str):
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    engines = [e for e in (request.args.get("engine") or "").split(",") if e] or None
    only = request.args.get("only") or None
    syms = {s.strip().upper() for s in (request.args.get("symbols") or "").split(",") if s.strip()} or None
    return jsonify(load_verdicts(TRADES_ROOT, date_str, engines=engines, only=only, symbols=syms))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_operator_api.py -q -k verdicts`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
arch -arm64 git add prototype/operator_api.py tests/test_operator_api.py
arch -arm64 git commit -m "feat(api): /api/verdicts/<date> serves each engine's rejected picks and the failed reasons"
```

---

### Task 5: Data-link health route

**Files:**
- Modify: `prototype/operator_api.py`
- Test: `tests/test_operator_api.py`

**Interfaces:**
- Produces: `datalink_rows(kite_health: dict, kite_alive: tuple, indices: dict) -> list[dict]`, pure. Each row: `{"name", "state": "ok"|"stale"|"down"|"off", "detail"}`.
- Produces: `GET /api/health/datalinks` → `{"generated_at", "links": [rows]}`.
- Consumes: `prototype.v4.kite_data.health()` → `{enabled, kite_calls, kite_ok, fallbacks, token_failures, last_error, last_fallback_at}`; `kite_data.token_alive()` → `(ok: bool, detail: str)`; the `/api/indices` JSON (keys `nifty, sensex, banknifty, niftyit, vix`, each with `price, change, changePct, source, stale`).

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_operator_api.py -q -k datalink`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `prototype/operator_api.py`:

```python
def datalink_rows(kite_health: dict, kite_alive: tuple, indices: dict) -> list:
    """One row per data link. Kite first, then every distinct index source."""
    rows = []
    kh = kite_health or {}
    if not kh.get("enabled"):
        rows.append({"name": "Kite", "state": "off", "detail": "paper mode, feed disabled"})
    else:
        ok, detail = (kite_alive or (False, "unknown"))
        if ok:
            state = "ok"
            if kh.get("fallbacks"):
                state, detail = "stale", f"{detail} · {kh['fallbacks']} fallbacks"
        else:
            state = "down"
            detail = str(kh.get("last_error") or detail)
        rows.append({"name": "Kite", "state": state, "detail": detail})
    seen = {}
    for key, idx in (indices or {}).items():
        src = str((idx or {}).get("source") or "unknown")
        stale = bool((idx or {}).get("stale"))
        cur = seen.setdefault(src, {"name": src, "state": "ok", "detail": []})
        cur["detail"].append(key.upper())
        if stale:
            cur["state"] = "stale"
    for src, cur in seen.items():
        cur["detail"] = "serves " + ", ".join(cur["detail"])
        rows.append(cur)
    return rows


@bp.get("/health/datalinks")
def api_datalinks():
    try:
        from prototype.v4 import kite_data as kd
        kh = kd.health()
        alive = kd.token_alive() if kh.get("enabled") else (False, "disabled")
    except Exception as e:  # the feed module itself failing is a 'down' row, not a 500
        kh, alive = {"enabled": True, "last_error": str(e)}, (False, str(e))
    try:
        resp = current_app.view_functions["api_indices"]()
        indices = resp.get_json() if hasattr(resp, "get_json") else {}
    except Exception:
        indices = {}
    return jsonify({"generated_at": datetime.now().strftime("%H:%M:%S"),
                    "links": datalink_rows(kh, alive, indices)})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_operator_api.py -q -k datalink`
Expected: 3 passed. If `api_indices` returns a tuple `(Response, status)` in some branch, unwrap with `resp = resp[0] if isinstance(resp, tuple) else resp` before `get_json()`.

- [ ] **Step 5: Commit**

```bash
arch -arm64 git add prototype/operator_api.py tests/test_operator_api.py
arch -arm64 git commit -m "feat(api): /api/health/datalinks exposes Kite and index-source health"
```

---

### Task 6: Shadows route

**Files:**
- Modify: `prototype/operator_api.py`
- Test: `tests/test_operator_api.py`

**Interfaces:**
- Produces: `shadow_day_index(day: date, start: date = SHADOW_START, total: int = SHADOW_DAYS) -> dict` → `{"day": n, "total": total}` counting weekdays from start to day inclusive, clamped to `[0, total]`.
- Produces: `load_shadows(root: Path, date_str: str) -> dict` → `{"date", "day", "total", "armband": [{engine, band, net, live_net, delta, n, stops, targets, worst_trade}], "regime": [{engine, live_regime, alt_regime, live_net, alt_net, delta, common_trades}]}`.
- Produces: `GET /api/shadows?date=YYYY-MM-DD` (default today) → `load_shadows(...)` plus `"lab": [{id, title, delta, cum_delta}]` from `/api/lab` for the same date.
- Consumes: `docs/research/shadows/armband/<date>.json` → `{date, bands, engines: {eng: {live_actual_gross, live_actual_net, bands: {band: {gross, net, n, stops, targets, worst_trade}}, trades}}}`; `docs/research/shadows/regime/<date>.json` → `{date, engine, live_regime, alt_regime, live_book_net, alt_book_net, common_trades, alt_minus_live, ...}`; `/api/lab` → `{date, experiments: [{id, title, ..., delta, cum_delta?}]}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_shadow_day_index_counts_weekdays_inclusive():
    from prototype.operator_api import shadow_day_index
    assert shadow_day_index(date(2026, 9, 8)) == {"day": 1, "total": 10}    # Tue, start
    assert shadow_day_index(date(2026, 9, 11)) == {"day": 4, "total": 10}   # Fri
    assert shadow_day_index(date(2026, 9, 14)) == {"day": 5, "total": 10}   # Mon, weekend skipped
    assert shadow_day_index(date(2026, 9, 7)) == {"day": 0, "total": 10}    # before start
    assert shadow_day_index(date(2026, 10, 30)) == {"day": 10, "total": 10} # clamped


def test_load_shadows_reads_armband_and_regime(tmp_path):
    from prototype.operator_api import load_shadows
    (tmp_path / "armband").mkdir(); (tmp_path / "regime").mkdir()
    (tmp_path / "armband" / "2026-09-10.json").write_text(json.dumps({
        "date": "2026-09-10", "bands": ["live", "arm0.5"],
        "engines": {"v5": {"live_actual_gross": -1328.0, "live_actual_net": -2122.98,
                           "bands": {"live": {"gross": -1328.0, "net": -2122.98, "n": 38, "stops": 20, "targets": 0, "worst_trade": -347.8},
                                     "arm0.5": {"gross": -1001.1, "net": -1503.5, "n": 38, "stops": 20, "targets": 0, "worst_trade": -347.8}},
                           "trades": []}}}))
    (tmp_path / "regime" / "2026-09-10.json").write_text(json.dumps({
        "date": "2026-09-10", "engine": "v5", "live_regime": "BEAR", "alt_regime": "SIDEWAYS",
        "live_book_net": -2743.4, "alt_book_net": -3601.1, "common_trades": 40, "alt_minus_live": -857.7}))
    out = load_shadows(tmp_path, "2026-09-10")
    assert out["day"] == 3 and out["total"] == 10
    arm = {(a["engine"], a["band"]): a for a in out["armband"]}
    assert arm[("v5", "arm0.5")]["delta"] == pytest.approx(-1503.5 - (-2122.98))
    assert arm[("v5", "live")]["delta"] == 0
    assert out["regime"][0]["delta"] == pytest.approx(-857.7)
    assert out["regime"][0]["alt_regime"] == "SIDEWAYS"


def test_load_shadows_missing_day_is_empty_not_error(tmp_path):
    from prototype.operator_api import load_shadows
    out = load_shadows(tmp_path, "2026-09-11")
    assert out["armband"] == [] and out["regime"] == []


def test_shadows_route(client):
    r = client.get("/api/shadows?date=2026-09-10")
    assert r.status_code == 200
    body = r.get_json()
    assert set(body) >= {"date", "day", "total", "armband", "regime", "lab"}
    assert client.get("/api/shadows?date=bad").status_code == 400
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_operator_api.py -q -k shadow`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement**

Append to `prototype/operator_api.py`:

```python
SHADOW_START = date(2026, 9, 8)   # pre-registration: docs/research/shadows/2026-09-08-preregistration.md
SHADOW_DAYS = 10


def shadow_day_index(day: date, start: date = SHADOW_START, total: int = SHADOW_DAYS) -> dict:
    n = 0
    d = start
    while d <= day:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return {"day": max(0, min(n, total)), "total": total}


def _read_json(p: Path):
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def load_shadows(root: Path, date_str: str) -> dict:
    root = Path(root)
    out = {"date": date_str, **shadow_day_index(date.fromisoformat(date_str)),
           "armband": [], "regime": []}
    arm = _read_json(root / "armband" / f"{date_str}.json") or {}
    for eng, e in (arm.get("engines") or {}).items():
        live_net = _f(e.get("live_actual_net"))
        for band, b in (e.get("bands") or {}).items():
            net = _f(b.get("net"))
            out["armband"].append({
                "engine": eng, "band": band, "net": net, "live_net": live_net,
                "delta": (round(net - live_net, 2) if net is not None and live_net is not None else None),
                "n": b.get("n"), "stops": b.get("stops"), "targets": b.get("targets"),
                "worst_trade": _f(b.get("worst_trade"))})
    reg = _read_json(root / "regime" / f"{date_str}.json")
    if reg:
        out["regime"].append({
            "engine": reg.get("engine"), "live_regime": reg.get("live_regime"),
            "alt_regime": reg.get("alt_regime"), "live_net": _f(reg.get("live_book_net")),
            "alt_net": _f(reg.get("alt_book_net")), "delta": _f(reg.get("alt_minus_live")),
            "common_trades": reg.get("common_trades")})
    return out


@bp.get("/shadows")
def api_shadows():
    date_str = request.args.get("date") or date.today().isoformat()
    if not _is_date(date_str):
        return jsonify({"error": "date must be YYYY-MM-DD"}), 400
    out = load_shadows(SHADOWS_ROOT, date_str)
    lab = []
    try:
        with current_app.test_request_context(f"/api/lab?date={date_str}"):
            resp = current_app.view_functions["api_lab"]()
        resp = resp[0] if isinstance(resp, tuple) else resp
        for x in (resp.get_json() or {}).get("experiments") or []:
            lab.append({"id": x.get("id"), "title": x.get("title"),
                        "delta": x.get("delta"), "cum_delta": x.get("cum_delta")})
    except Exception:
        pass
    out["lab"] = lab
    return jsonify(out)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_operator_api.py -q -k shadow`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
arch -arm64 git add prototype/operator_api.py tests/test_operator_api.py
arch -arm64 git commit -m "feat(api): /api/shadows serves arm-band and regime shadow deltas with the day counter"
```

---

### Task 7: Exit durations and a true model trained-at

**Files:**
- Modify: `prototype/operator_api.py`
- Modify: `prototype/app.py:3943-3947` (`recent_exits.append` in `api_desk`) and `prototype/app.py:1070-1125` (`api_model`, the `"lastTrained"` key at line 1116 and the v3 branch)
- Test: `tests/test_operator_api.py`

**Interfaces:**
- Produces: `duration_min(entry_time: str | None, exit_time: str | None) -> int | None` for `"HH:MM:SS"` or `"HH:MM"` strings on the same day; `None` if either is missing or unparsable; negative spans (overnight) return `None`.
- Produces: `model_trained_at(models_dir: Path = MODELS_DIR) -> str | None`, ISO timestamp of the newest `*.pkl`.
- Produces: `recent_exits[].duration_min` on `/api/desk`; `trained_at` on `/api/model` (and `lastTrained` becomes the date part of it instead of today's date).

- [ ] **Step 1: Write the failing tests**

```python
def test_duration_min():
    from prototype.operator_api import duration_min
    assert duration_min("09:40:13", "09:50:14") == 10
    assert duration_min("09:40", "10:45") == 65
    assert duration_min(None, "09:50:14") is None
    assert duration_min("garbage", "09:50:14") is None
    assert duration_min("15:20:00", "09:10:00") is None


def test_model_trained_at_uses_newest_pkl(tmp_path):
    import os, time
    from prototype.operator_api import model_trained_at
    assert model_trained_at(tmp_path) is None
    old, new = tmp_path / "a.pkl", tmp_path / "b.pkl"
    old.write_bytes(b"x"); new.write_bytes(b"y")
    os.utime(old, (1_700_000_000, 1_700_000_000))
    os.utime(new, (1_750_000_000, 1_750_000_000))
    assert model_trained_at(tmp_path) == datetime.fromtimestamp(1_750_000_000).isoformat(timespec="seconds")


def test_desk_exits_have_duration(client, monkeypatch):
    from prototype import operator_api
    monkeypatch.setattr(operator_api, "marks_for", lambda symbols: {})
    data = _fresh_desk(client, monkeypatch)
    for x in data["recent_exits"]:
        assert "duration_min" in x


def test_model_route_reports_trained_at_not_today(client):
    body = client.get("/api/model").get_json()
    assert "trained_at" in body
    if body["trained_at"]:
        assert body["lastTrained"] == body["trained_at"][:10]
```

Add `from datetime import datetime` to the test file's imports.

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -m pytest tests/test_operator_api.py -q -k "duration or trained_at"`
Expected: FAIL with ImportError.

- [ ] **Step 3: Implement the helpers**

Append to `prototype/operator_api.py`:

```python
def _hms(s):
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(str(s), fmt)
            return t.hour * 60 + t.minute
        except (TypeError, ValueError):
            continue
    return None


def duration_min(entry_time, exit_time):
    a, b = _hms(entry_time), _hms(exit_time)
    if a is None or b is None or b < a:
        return None
    return b - a


def model_trained_at(models_dir: Path = MODELS_DIR):
    try:
        pkls = list(Path(models_dir).glob("*.pkl"))
    except Exception:
        return None
    if not pkls:
        return None
    ts = max(p.stat().st_mtime for p in pkls)
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")
```

- [ ] **Step 4: Wire into api_desk exits**

In `prototype/app.py` `api_desk`, replace lines 3943-3947:

```python
                        recent_exits.append({
                            "engine": d.name, "symbol": c.get("symbol"),
                            "pnl": round(pnl, 0), "pnl_pct": c.get("pnl_pct"),
                            "reason": c.get("reason"), "exit_time": c.get("exit_time"),
                            "side": (c.get("position_type") or "LONG").upper()})
```

with:

```python
                        recent_exits.append({
                            "engine": d.name, "symbol": c.get("symbol"),
                            "pnl": round(pnl, 0), "pnl_pct": c.get("pnl_pct"),
                            "reason": c.get("reason"), "exit_time": c.get("exit_time"),
                            "entry_time": c.get("entry_time"),
                            "duration_min": _opapi.duration_min(c.get("entry_time"), c.get("exit_time")),
                            "side": (c.get("position_type") or "LONG").upper()})
```

(`_opapi` is already imported at the top of `api_desk` from Task 2.)

- [ ] **Step 5: Wire into api_model**

In `prototype/app.py` `api_model` (lines 1070-1125): add at the top of the function body

```python
    from prototype.operator_api import model_trained_at
    _trained = model_trained_at()
```

then in every `jsonify({...})` dict the function returns (the v3 branch and the v2/v4 branch that currently has `"lastTrained": datetime.now().strftime("%Y-%m-%d")` at line 1116), replace the `lastTrained` value with `(_trained or "")[:10] or "unknown"` and add the key `"trained_at": _trained`. The error branch at the bottom stays unchanged.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_operator_api.py -q -k "duration or trained_at or model_route or exits_have"`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
arch -arm64 git add prototype/operator_api.py prototype/app.py tests/test_operator_api.py
arch -arm64 git commit -m "feat(desk,model): exit durations on the feed; model trained_at from file mtime instead of today's date"
```

---

### Task 8: Full test run, map update, wrap

**Files:**
- Modify: `docs/design/2026-09-11-operator-redesign/existing-page-map.md` (flip the five Phase 1 rows from Wire to Reuse, naming the route)
- Test: whole suite

- [ ] **Step 1: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: everything that passed before this plan still passes, plus the new `tests/test_operator_api.py`. If a pre-existing test fails, check `arch -arm64 git stash && python3 -m pytest tests/ -q && arch -arm64 git stash pop` to confirm whether it failed before this plan; report it either way, do not silence it.

- [ ] **Step 2: Manual check against real data (read-only, allowed during market hours)**

```bash
cd /Users/soumyaswain/Documents/tinker/projects/tradepilot
python3 - <<'EOF'
from prototype.app import app
app.config["TESTING"] = True
c = app.test_client()
for u in ("/api/desk", "/api/verdicts/2026-09-10?only=rejected", "/api/health/datalinks",
          "/api/shadows?date=2026-09-10", "/api/model"):
    r = c.get(u); b = r.get_json() or {}
    print(u, r.status_code, {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in list(b.items())[:8]})
EOF
```

Expected: five 200s. `/api/desk` fleet shows `unrealized`, `risk_at_stop`, `deployed`, `unpriced`. `/api/verdicts` count is greater than zero for v5 and v5_wide. `/api/shadows` day is 3 for 2026-09-10.

- [ ] **Step 3: Update the page map**

In `docs/design/2026-09-11-operator-redesign/existing-page-map.md`, change these rows' status from `Wire` to `Reuse` and put the route in the Source column:
- Ready: "Data link NSE / yfinance / Kite" → `/api/health/datalinks`; "Shadow experiment deltas" → `/api/shadows`; "ML model last trained" → `/api/model` `trained_at`.
- Market: "Reason we skipped a stock" → `/api/verdicts/<date>`.
- Book: "Live price and unrealised P&L", "Distance to stop", "Time in trade, exit duration", "Loss if every stop hits" → `/api/desk` (`open_positions[].mark/unrealized_pnl/to_stop_pct/risk_at_stop`, `recent_exits[].duration_min`, `fleet.risk_at_stop`).

- [ ] **Step 4: Commit**

```bash
arch -arm64 git add docs/design/2026-09-11-operator-redesign/existing-page-map.md
arch -arm64 git commit -m "docs(design): page map reflects Phase 1 routes"
```

- [ ] **Step 5: Store the learning**

```bash
dp learn "TRADEPILOT: /api/live-trades and /api/positions-live read unrealized_pnl, a key the engine never writes, so open P&L was blank for months. Phase 1 computes it from Kite marks; positions_active.json already carried sl_price/target_price which /api/desk dropped." --project tradepilot --tags dashboard,api,bug-pattern
```

If `dp` is unavailable, skip and note it in the wrap-up message.
