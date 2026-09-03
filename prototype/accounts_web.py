"""Sign in and sign out.

Server-rendered on purpose. A real form POST means browser password managers
work, and credentials never pass through the fetch layer -- api.js does not
know this page exists.
"""
import secrets

from flask import (Blueprint, current_app, jsonify, make_response, redirect,
                   render_template, request, url_for)

from prototype import accounts, app_store, client_auth, mailer

bp = Blueprint("accounts_web", __name__)

REFUSAL = "That email and password did not match."


def open_store():
    """Open the store. A named function so tests can point at a throwaway file."""
    return app_store.get_db()


def safe_next(target):
    """A local path to redirect to after signing in, or /app.

    Anything that could leave this site is discarded. Two shapes are easy to
    miss: "//evil.example.com" is a URL rather than a path, so a leading-slash
    check alone is not enough; and browsers strip ASCII tab, LF and CR from
    ANYWHERE in a URL before parsing it, so "/\tevil" arrives at the browser
    as "//evil" -- an off-site redirect that every prefix check below would
    otherwise wave through.
    """
    if not target:
        return "/app"
    if any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in target):
        return "/app"
    if not target.startswith("/"):
        return "/app"
    if target.startswith("//") or target.startswith("/\\"):
        return "/app"
    if "\\" in target or ":" in target:
        return "/app"
    # Quotes shouldn't matter -- the template renders this through
    # |urlencode -- but a value that never contains one costs nothing and
    # stops that filter being the only thing standing between this value and
    # an attribute break-out.
    if '"' in target or "'" in target:
        return "/app"
    return target


@bp.route("/app/login", methods=["GET", "POST"])
def login():
    nxt = safe_next(request.args.get("next"))
    if request.method == "GET":
        return render_template("login.html", error=None, next=nxt)

    # Login sits outside GATED_ENDPOINTS -- correctly, since a login page
    # that required a session to reach would be a locked door with the key
    # inside -- so the client_auth guard never runs here. SameSite=Lax can't
    # cover it either: signing in requires no cookie, so there is nothing for
    # SameSite to withhold. Without this check a hostile page can cross-site
    # POST the attacker's own credentials and sign the victim into the
    # attacker's account, where every position the victim then logs lands in
    # a book the attacker can read.
    if client_auth.foreign_origin():
        return jsonify({"error": "bad origin"}), 403

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
    # The cookie is transport, the row is the authority: accounts.lookup_session
    # already slides expires_at on every request and enforces the 90-day cap
    # server-side, so the cookie only needs to outlive that cap, not track the
    # 30-day sliding window itself. Setting max_age to SESSION_SLIDING_DAYS
    # instead would sign a daily-active user out at day 30 regardless of
    # activity -- the browser would discard a cookie the server still
    # considers valid. Re-issuing Set-Cookie on every gated response would
    # also work, but that adds a header to every API call to track a
    # lifetime the server already tracks in the sessions table.
    resp.set_cookie(client_auth.COOKIE_NAME, token,
                    httponly=True, samesite="Lax", path="/",
                    secure=request.is_secure,
                    max_age=accounts.SESSION_MAX_DAYS * 24 * 3600)
    return resp


@bp.route("/app/logout", methods=["POST"])
def logout():
    if client_auth.foreign_origin():
        return jsonify({"error": "bad origin"}), 403

    token = request.cookies.get(client_auth.COOKIE_NAME)
    conn = open_store()
    try:
        accounts.revoke_session(conn, token)
    finally:
        conn.close()
    resp = make_response(redirect(url_for("client_app")))
    resp.delete_cookie(client_auth.COOKIE_NAME, path="/")
    return resp


WAITLIST_ACK = "Thanks -- we will be in touch."
FORGOT_ACK = "If that address has an account, a reset link is on its way."


def send_mail(to, subject, body):
    """Indirection so tests replace one function instead of the mailer."""
    mailer.send(to, subject, body)


def reset_body(token):
    return ("Someone asked to reset the password on your TradePilot account.\n\n"
            "If that was you, set a new one here -- the link is good for an hour:\n"
            "%s/app/set-password?t=%s\n\n"
            "If it was not you, ignore this. Nothing has changed.\n"
            % (request.host_url.rstrip("/"), token))


@bp.route("/app/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html", done=False, ack=WAITLIST_ACK)
    if client_auth.foreign_origin():
        return jsonify({"error": "bad origin"}), 403

    email = (request.form.get("email") or "").strip()
    if email:
        conn = open_store()
        try:
            conn.execute(
                "INSERT INTO waitlist (id, email, requested_at) VALUES (?, ?, ?)",
                ("w-" + secrets.token_hex(4), email, accounts._iso(accounts._now())))
            conn.commit()
        finally:
            conn.close()
    # The same page whether the address is new, repeated, or already an
    # account. Anything else makes this form an account enumerator.
    return render_template("signup.html", done=True, ack=WAITLIST_ACK)


@bp.route("/app/forgot", methods=["GET", "POST"])
def forgot():
    if request.method == "GET":
        return render_template("forgot.html", done=False, ack=FORGOT_ACK)
    if client_auth.foreign_origin():
        return jsonify({"error": "bad origin"}), 403

    email = (request.form.get("email") or "").strip()
    if email:
        conn = open_store()
        try:
            row = conn.execute(
                "SELECT id FROM users WHERE lower(email) = lower(?)",
                (email,)).fetchone()
            if row is not None:
                token = accounts.issue_token(conn, "reset", email,
                                             accounts.RESET_HOURS)
                try:
                    send_mail(email, "Reset your TradePilot password",
                              reset_body(token))
                except Exception:
                    # Cannot be surfaced: saying "we could not send it" would
                    # confirm the account exists. Log it and answer normally.
                    current_app.logger.exception("reset mail failed")
        finally:
            conn.close()
    return render_template("forgot.html", done=True, ack=FORGOT_ACK)
