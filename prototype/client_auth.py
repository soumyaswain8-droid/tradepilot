"""The auth seam for the client API.

Project B (accounts) does not exist yet. Everything the client API assumes
about identity is in this file, and it is three things: current_user() returns
an id or None, gated endpoints are protected, and positions.user_id is stable.
Swapping the stub for real sessions is a one-function change.

The registries are the point. This app has roughly seventy unprotected routes;
scattering client endpoints among them would make auth a per-route audit where
one missed decorator is a data leak. One prefix plus two explicit lists makes
"is everything classified?" a question the test suite answers by enumeration.

Each task adds its own endpoints here as it adds them. That is deliberate:
it keeps both enumeration tests green at every commit, and it makes
classification an active step rather than a list written once and trusted.
"""
from flask import jsonify, request

# Blueprint endpoint names, not URL paths -- Flask dispatches on endpoints, and
# a path string would silently stop matching if a route were reworded.
PUBLIC_ENDPOINTS = frozenset({
    "client_api.calls_list",
    "client_api.call_detail",
    "client_api.record",
})

GATED_ENDPOINTS = frozenset({
    "client_api.me",
})


def current_user():
    """The signed-in user's id, or None.

    STUB. Returns a fixed id until project B lands. Every gated endpoint reads
    identity through this one function, so replacing it with a real session
    lookup is the entire integration.
    """
    return "demo-user"


def install_guard(app):
    """Refuse gated client endpoints when nobody is signed in."""

    @app.before_request
    def _guard_client_api():
        """Refuse a gated client endpoint when nobody is signed in."""
        endpoint = request.endpoint
        if endpoint in GATED_ENDPOINTS and current_user() is None:
            return jsonify({"error": "sign in to see this"}), 401
        return None
