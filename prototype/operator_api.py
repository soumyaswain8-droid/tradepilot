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
