"""The client dashboard's API. Eight endpoints, one prefix, one guard.

Everything here is client-facing, which sets rules the operator surface does
not have: no engine names, no strategy internals, no agent vocabulary, and no
internal detail in any error message. A client sees what was called and what
happened -- never which engine said so.
"""
from datetime import datetime

from flask import Blueprint, jsonify, request

from prototype import app_store, client_auth

bp = Blueprint("client_api", __name__, url_prefix="/api/app")


@bp.route("/me")
def me():
    """The signed-in user and their plan. Project B owns this shape later."""
    return jsonify({"user_id": client_auth.current_user(), "plan": "none"})


def open_store():
    """Open the calls/positions database.

    A named function rather than an inline call so tests can point the API at
    a throwaway file without touching the real record.
    """
    conn = app_store.get_db()
    app_store.init_db(conn)
    return conn


CALL_FIELDS = ("id", "symbol", "side", "published_at", "price_at_call",
               "score", "signal", "horizon", "target", "stop",
               "outcome", "outcome_price", "outcome_at")


def shape_call(row):
    """One `calls` row as the client sees it.

    An explicit field list rather than dict(row): it keeps internal columns
    from leaking into a client payload by accident when the schema grows.
    """
    return {k: row[k] for k in CALL_FIELDS}


# The record grows by roughly ten rows every trading day, so an unbounded
# response would be thousands of calls within a year while the Home screen
# shows a handful. Bounded by default, raisable by the caller, hard-capped so
# a client cannot ask for the whole table.
DEFAULT_CALL_LIMIT = 50
MAX_CALL_LIMIT = 500


@bp.route("/calls")
def calls_list():
    """Published calls, newest first. Reads the record -- never /api/picks."""
    try:
        limit = int(request.args.get("limit", DEFAULT_CALL_LIMIT))
    except (TypeError, ValueError):
        limit = DEFAULT_CALL_LIMIT
    limit = max(1, min(limit, MAX_CALL_LIMIT))

    conn = open_store()
    try:
        rows = conn.execute(
            "SELECT * FROM calls ORDER BY published_at DESC, symbol ASC"
            " LIMIT ?", (limit,)).fetchall()
        return jsonify({"calls": [shape_call(r) for r in rows],
                        "limit": limit,
                        "as_of": datetime.now().isoformat(timespec="seconds")})
    finally:
        conn.close()


@bp.route("/calls/<call_id>")
def call_detail(call_id):
    """One call, with the reasoning that was published alongside it."""
    conn = open_store()
    try:
        row = conn.execute("SELECT * FROM calls WHERE id = ?", (call_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        return jsonify({"error": "no such call"}), 404
    return jsonify(shape_call(row))
