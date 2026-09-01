"""The auth seam for the client API.

Everything the client API assumes about identity is in this file, and it is
three things: current_user() returns an id or None, gated endpoints are
protected, and positions.user_id is stable. current_user() now resolves a
real session -- the tp_session cookie through accounts.lookup_session() --
but every gated endpoint still reads identity through this one function, so
that remains the entire integration surface.

The registries are the point. This app has roughly seventy unprotected routes;
scattering client endpoints among them would make auth a per-route audit where
one missed decorator is a data leak. One prefix plus two explicit lists makes
"is everything classified?" a question the test suite answers by enumeration.

Each task adds its own endpoints here as it adds them. That is deliberate:
it keeps both enumeration tests green at every commit, and it makes
classification an active step rather than a list written once and trusted.
"""
from flask import jsonify, request

from prototype import accounts, app_store

COOKIE_NAME = "tp_session"

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Blueprint endpoint names, not URL paths -- Flask dispatches on endpoints, and
# a path string would silently stop matching if a route were reworded.
PUBLIC_ENDPOINTS = frozenset({
    "client_api.calls_list",
    "client_api.call_detail",
    "client_api.record",
})

GATED_ENDPOINTS = frozenset({
    "client_api.me",
    "client_api.positions_list",
    "client_api.position_create",
    "client_api.position_update",
    "client_api.position_delete",
})


def open_store():
    """Open the store. A named function so tests can point at a throwaway file."""
    return app_store.get_db()


def current_user():
    """The signed-in user's id, or None.

    One indexed read per gated request. The cookie carries an opaque random
    token and nothing else, so there is no signature to verify and no
    SECRET_KEY to manage -- and logout can actually revoke, because the row
    is the authority rather than the cookie.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    conn = open_store()
    try:
        return accounts.lookup_session(conn, token)
    finally:
        conn.close()


def install_guard(app):
    """Refuse gated client endpoints when nobody is signed in."""

    @app.before_request
    def _guard_client_api():
        endpoint = request.endpoint
        if endpoint not in GATED_ENDPOINTS:
            return None
        if current_user() is None:
            return jsonify({"error": "sign in to see this"}), 401
        if request.method in UNSAFE_METHODS:
            origin = request.headers.get("Origin")
            # Only a PRESENT and mismatched Origin is refused. Browsers always
            # send it on an unsafe cross-origin request, so the attack is
            # caught; a request with none is not a browser and therefore not
            # the CSRF threat model.
            if origin is not None and origin != request.host_url.rstrip("/"):
                return jsonify({"error": "bad origin"}), 403
        return None
