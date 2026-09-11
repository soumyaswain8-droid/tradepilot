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

SHADOW_START = date(2026, 9, 8)   # pre-registration: docs/research/shadows/2026-09-08-preregistration.md
SHADOW_DAYS = 10

bp = Blueprint("operator_api", __name__, url_prefix="/api")


@bp.get("/operator/ping")
def ping():
    return jsonify({"ok": True})


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
        # Not rounded: rounding to 2dp here loses enough precision that a
        # near-touch stop distance (e.g. 1.60 vs the true 1.604%) can read as
        # further away than it is. The desk can format for display.
        r["to_stop_pct"] = ((mark - sl) / mark * 100 * sign
                            if mark and sl else None)
        r["risk_at_stop"] = (round((sl - entry) * int(qty) * sign, 2)
                             if sl and entry is not None and qty else None)
    return rows


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
    engines = [e.strip() for e in (request.args.get("engine") or "").split(",") if e.strip()] or None
    only = request.args.get("only") or None
    syms = {s.strip().upper() for s in (request.args.get("symbols") or "").split(",") if s.strip()} or None
    return jsonify(load_verdicts(TRADES_ROOT, date_str, engines=engines, only=only, symbols=syms))


def datalink_rows(kite_health: dict, kite_alive: tuple, indices: dict) -> list:
    """One row per data link. Kite first, then every distinct index source."""
    rows = []
    kh = kite_health or {}
    if not kh.get("enabled"):
        rows.append({"name": "Kite", "state": "off", "detail": "paper mode, feed disabled"})
    else:
        ok, alive_detail = (kite_alive or (False, "unknown"))
        if ok:
            # alive_detail carries the Kite account identity ("<name> (<id>)")
            # -- this route is unauthenticated, so never pass it through.
            state, detail = "ok", "token ok"
            if kh.get("fallbacks"):
                state, detail = "stale", f"token ok · {kh['fallbacks']} fallbacks"
        else:
            state = "down"
            detail = str(kh.get("last_error") or alive_detail)
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
        resp = resp[0] if isinstance(resp, tuple) else resp
        indices = resp.get_json() if hasattr(resp, "get_json") else {}
    except Exception:
        indices = {}
    return jsonify({"generated_at": datetime.now().strftime("%H:%M:%S"),
                    "links": datalink_rows(kh, alive, indices)})


def shadow_day_index(day: date, start: date = SHADOW_START, total: int = SHADOW_DAYS) -> dict:
    """Count weekdays from start to day inclusive, clamped to [0, total]."""
    n = 0
    d = start
    while d <= day:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return {"day": max(0, min(n, total)), "total": total}


def _read_json(p: Path):
    """Read JSON from path, return None if missing or invalid."""
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def load_shadows(root: Path, date_str: str) -> dict:
    """Load armband and regime shadow data for a date."""
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
    """Serve armband and regime shadow deltas, plus lab experiments, for a date."""
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


def _hms(s):
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            t = datetime.strptime(str(s), fmt)
            return t.hour * 60 + t.minute
        except (TypeError, ValueError):
            continue
    return None


def duration_min(entry_time, exit_time, entry_date=None, exit_date=None):
    """Minutes held, clock-time only unless dates disagree.
    A multi-day SWING hold (entry_date != exit_date) has no honest clock-time
    duration -- returning the same-day delta silently understates it by a day
    or more, so callers get None instead of a wrong number."""
    if entry_date and exit_date and entry_date != exit_date:
        return None
    a, b = _hms(entry_time), _hms(exit_time)
    if a is None or b is None or b < a:
        return None
    return b - a


def model_trained_at(models_dir: Path = MODELS_DIR):
    """(timestamp, source). Meta files carry the real training timestamp;
    .pkl mtime is only checkout time once the file is git-tracked, so it is
    the fallback, not the primary source."""
    models_dir = Path(models_dir)
    for name in ("model_meta_v3.json", "model_meta_v2.json", "model_meta.json"):
        meta = _read_json(models_dir / name)
        trained_at = (meta or {}).get("trained_at")
        if trained_at:
            return trained_at, "meta"
    try:
        pkls = list(models_dir.glob("*.pkl"))
    except Exception:
        return None, None
    if not pkls:
        return None, None
    ts = max(p.stat().st_mtime for p in pkls)
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds"), "file-mtime"
