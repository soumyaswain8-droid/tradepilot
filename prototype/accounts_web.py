"""Sign in and sign out.

Server-rendered on purpose. A real form POST means browser password managers
work, and credentials never pass through the fetch layer -- api.js does not
know this page exists.
"""
from flask import (Blueprint, make_response, redirect, render_template,
                   request, url_for)

from prototype import accounts, app_store, client_auth

bp = Blueprint("accounts_web", __name__)

REFUSAL = "That email and password did not match."


def open_store():
    """Open the store. A named function so tests can point at a throwaway file."""
    return app_store.get_db()


def safe_next(target):
    """A local path to redirect to after signing in, or /app.

    Anything that could leave this site is discarded. A protocol-relative
    "//evil.example.com" is a URL, not a path, which is why checking only for
    a leading slash is not enough.
    """
    if not target:
        return "/app"
    if not target.startswith("/"):
        return "/app"
    if target.startswith("//") or target.startswith("/\\"):
        return "/app"
    if "\\" in target or ":" in target:
        return "/app"
    return target


@bp.route("/app/login", methods=["GET", "POST"])
def login():
    nxt = safe_next(request.args.get("next"))
    if request.method == "GET":
        return render_template("login.html", error=None, next=nxt)

    conn = open_store()
    try:
        uid = accounts.check_login(conn, request.form.get("email", ""),
                                   request.form.get("password", ""))
        if uid is None:
            # One message for every failure. See accounts.check_login.
            return render_template("login.html", error=REFUSAL, next=nxt), 401
        token = accounts.create_session(conn, uid)
    finally:
        conn.close()

    resp = make_response(redirect(nxt))
    resp.set_cookie(client_auth.COOKIE_NAME, token,
                    httponly=True, samesite="Lax", path="/",
                    secure=request.is_secure,
                    max_age=accounts.SESSION_SLIDING_DAYS * 24 * 3600)
    return resp


@bp.route("/app/logout", methods=["POST"])
def logout():
    token = request.cookies.get(client_auth.COOKIE_NAME)
    conn = open_store()
    try:
        accounts.revoke_session(conn, token)
    finally:
        conn.close()
    resp = make_response(redirect(url_for("client_app")))
    resp.delete_cookie(client_auth.COOKIE_NAME, path="/")
    return resp
