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
