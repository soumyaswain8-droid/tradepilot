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
