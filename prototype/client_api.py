"""The client dashboard's API. Eight endpoints, one prefix, one guard.

Everything here is client-facing, which sets rules the operator surface does
not have: no engine names, no strategy internals, no agent vocabulary, and no
internal detail in any error message. A client sees what was called and what
happened -- never which engine said so.
"""
from flask import Blueprint, jsonify

from prototype import client_auth

bp = Blueprint("client_api", __name__, url_prefix="/api/app")


@bp.route("/me")
def me():
    """The signed-in user and their plan. Project B owns this shape later."""
    return jsonify({"user_id": client_auth.current_user(), "plan": "none"})
