"""The client dashboard's API. Eight endpoints, one prefix, one guard.

Everything here is client-facing, which sets rules the operator surface does
not have: no engine names, no strategy internals, no agent vocabulary, and no
internal detail in any error message. A client sees what was called and what
happened -- never which engine said so.
"""
import logging
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from flask import Blueprint, jsonify, request

from prototype import app_store, client_auth

log = logging.getLogger(__name__)

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
    try:
        app_store.init_db(conn)
    except Exception:
        # The caller's try/finally has not been entered yet, so nothing else
        # will close this handle. init_db runs on every request; a recurring
        # leak here would exhaust descriptors far from the cause.
        conn.close()
        raise
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


# A hit rate over a handful of calls is the easiest way to mislead a customer
# without lying to them. The response always carries the sample size and says
# plainly whether it is meaningful yet.
MEANINGFUL_FROM = 100


def _rate(hit, resolved):
    """Hit rate to one decimal, rounded half-UP so it matches a calculator.

    None when nothing is resolved -- 0.0 would render as "0%" and read as
    "we get everything wrong" rather than "nothing has resolved yet".
    """
    if not resolved:
        return None
    exact = Decimal(100 * hit) / Decimal(resolved)
    return float(exact.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


@bp.route("/record")
def record():
    """Aggregate outcomes. Ungraded calls are excluded, never counted softly."""
    conn = open_store()
    try:
        rows = conn.execute("SELECT published_at, outcome FROM calls").fetchall()
    finally:
        conn.close()

    hit = sum(1 for r in rows if r["outcome"] == "hit")
    miss = sum(1 for r in rows if r["outcome"] == "miss")
    ungraded = sum(1 for r in rows if r["outcome"] == "ungraded")
    open_ = sum(1 for r in rows if r["outcome"] == "open")
    resolved = hit + miss
    days = sorted({r["published_at"][:10] for r in rows})

    return jsonify({
        "total": len(rows),
        "resolved": resolved,
        "hit": hit,
        "miss": miss,
        "ungraded": ungraded,
        "open": open_,
        # Explicit half-up, NOT round(). Python's round() is round-half-to-even,
        # so round(6.25, 1) gives 6.2 while a customer's calculator gives 6.3 --
        # and 1 hit of 16 resolved is exactly that case. The early record lives
        # at these denominators, which is when a sceptic is most likely to check
        # the arithmetic by hand on the number the product is sold on.
        "hit_rate": _rate(hit, resolved),
        "since": days[0] if days else None,
        "meaningful_from": MEANINGFUL_FROM,
        "is_meaningful": resolved >= MEANINGFUL_FROM,
    })


def fetch_quotes(symbols):
    """Live prices for a set of symbols.

    Wraps kite_data.get_quotes, which OMITS symbols it cannot fetch rather
    than zero-filling them -- a silent 0.0 would render a real holding as
    worthless. That omission is preserved here on purpose: callers must handle
    a missing symbol, not receive a fake price for it.

    Returns {} rather than raising if the quote feed is unavailable, so a book
    still renders with its cost basis when prices are down.
    """
    if not symbols:
        return {}
    try:
        from prototype.v4 import kite_data
        return kite_data.get_quotes(sorted(set(symbols))) or {}
    except Exception as e:
        # Returning {} is deliberate -- a book still renders its cost basis when
        # prices are down. But a permanently broken feed would otherwise be
        # invisible: every position reads price_unavailable with nothing to grep.
        log.warning("quote feed unavailable (%s: %s); positions will render "
                    "without prices", type(e).__name__, e)
        return {}


POSITION_FIELDS = ("id", "user_id", "symbol", "qty", "avg_price", "opened_at",
                   "closed_at", "exit_price", "source", "broker_ref", "call_id")


def shape_position(row, quote):
    """One position, marked to market where a price is available."""
    out = {k: row[k] for k in POSITION_FIELDS}
    last = (quote or {}).get("last_price")
    if last is None:
        out.update({"last_price": None, "value": None, "pnl": None,
                    "pnl_pct": None, "price_unavailable": True})
        return out
    value = round(float(last) * float(row["qty"]), 2)
    cost = float(row["avg_price"]) * float(row["qty"])
    out.update({
        "last_price": float(last),
        "value": value,
        "pnl": round(value - cost, 2),
        "pnl_pct": round(100.0 * (value - cost) / cost, 2) if cost else None,
        "price_unavailable": False,
    })
    return out


@bp.route("/positions")
def positions_list():
    """The signed-in user's open book, marked to market."""
    user = client_auth.current_user()
    conn = open_store()
    try:
        rows = conn.execute(
            "SELECT * FROM positions WHERE user_id = ? AND closed_at IS NULL"
            " ORDER BY opened_at DESC", (user,)).fetchall()
    finally:
        conn.close()

    quotes = fetch_quotes([r["symbol"] for r in rows])
    shaped = [shape_position(r, quotes.get(r["symbol"])) for r in rows]
    priced = [p for p in shaped if not p["price_unavailable"]]
    return jsonify({
        "positions": shaped,
        "totals": {
            "value": round(sum(p["value"] for p in priced), 2) if priced else 0,
            "pnl": round(sum(p["pnl"] for p in priced), 2) if priced else 0,
            "priced": len(priced),
            # Surfaced, never silently dropped: a total that omits a holding
            # without saying so understates the book.
            "unpriced": len(shaped) - len(priced),
        },
    })


def _bad_number(value):
    """NaN and infinity both slip past a `<= 0` check.

    float("nan") <= 0 and float("inf") <= 0 are both False, so neither is
    caught by the positivity guard -- and either one propagates into value,
    pnl and the portfolio totals. PATCH rejects both; POST must agree.
    """
    return value != value or value in (float("inf"), float("-inf"))


@bp.route("/positions", methods=["POST"])
def position_create():
    """Log a trade the client placed at their own broker."""
    body = request.get_json(silent=True) or {}
    symbol = str(body.get("symbol", "")).upper().replace(".NS", "").strip()
    try:
        qty = float(body.get("qty"))
        avg_price = float(body.get("avg_price"))
    except (TypeError, ValueError):
        return jsonify({"error": "qty and avg_price must be numbers"}), 400
    # NaN and infinity both pass `<= 0` as False, so either would otherwise
    # slip past the positivity check and poison every later P&L figure
    # computed from this row. PATCH rejects the same values -- see
    # _bad_number -- so this must match it exactly.
    if _bad_number(qty) or _bad_number(avg_price):
        return jsonify({"error": "qty and avg_price must be real numbers"}), 400
    if not symbol or qty <= 0 or avg_price <= 0:
        return jsonify({"error": "symbol, a positive qty and a positive "
                                 "avg_price are required"}), 400

    call_id = body.get("call_id") or None
    conn = open_store()
    try:
        if call_id is not None:
            exists = conn.execute("SELECT 1 FROM calls WHERE id = ?",
                                  (call_id,)).fetchone()
            if exists is None:
                return jsonify({"error": "no such call"}), 400
        pid = "pos-" + uuid.uuid4().hex[:12]
        try:
            conn.execute(
                "INSERT INTO positions (id, user_id, symbol, qty, avg_price,"
                " opened_at, source, call_id) VALUES (?,?,?,?,?,?,?,?)",
                (pid, client_auth.current_user(), symbol, qty, avg_price,
                 body.get("opened_at") or datetime.now().isoformat(timespec="seconds"),
                 "manual", call_id))
        except sqlite3.IntegrityError:
            # The call existed when we checked and does not now. A clean 400
            # beats an unhandled 500 for a condition the client can act on.
            return jsonify({"error": "no such call"}), 400
        conn.commit()
        row = conn.execute("SELECT * FROM positions WHERE id = ?", (pid,)).fetchone()
        return jsonify(shape_position(row, None)), 201
    finally:
        conn.close()


@bp.route("/positions/<pid>", methods=["PATCH"])
def position_update(pid):
    """Edit or close a position. Only the owner's rows are reachable."""
    body = request.get_json(silent=True) or {}
    allowed = ("qty", "avg_price", "closed_at", "exit_price")
    numeric = ("qty", "avg_price", "exit_price")

    sets = []
    for key in allowed:
        if key not in body:
            continue
        value = body[key]
        if key in numeric:
            # POST already rejects a non-positive qty or price. PATCH writes to
            # the same columns, so it must reject the same values -- otherwise a
            # client can put their book into a state the API refuses to create.
            # A string here is worse than wrong: it stores fine, then raises in
            # shape_position on every later list request, so the client's whole
            # book 500s until someone edits the database by hand.
            try:
                value = float(value)
            except (TypeError, ValueError):
                return jsonify({"error": "%s must be a number" % key}), 400
            if _bad_number(value):
                return jsonify({"error": "%s must be a real number" % key}), 400
            if key in ("qty", "avg_price") and value <= 0:
                return jsonify({"error": "%s must be positive" % key}), 400
            if key == "exit_price" and value <= 0:
                return jsonify({"error": "exit_price must be positive"}), 400
        elif value is not None and not isinstance(value, str):
            return jsonify({"error": "%s must be a string" % key}), 400
        sets.append((key, value))

    if not sets:
        return jsonify({"error": "nothing to update"}), 400

    conn = open_store()
    try:
        clause = ", ".join("%s = ?" % k for k, _ in sets)
        params = [v for _, v in sets] + [pid, client_auth.current_user()]
        cur = conn.execute(
            "UPDATE positions SET " + clause + " WHERE id = ? AND user_id = ?",
            params)
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "no such position"}), 404
        row = conn.execute("SELECT * FROM positions WHERE id = ?", (pid,)).fetchone()
        return jsonify(shape_position(row, None))
    finally:
        conn.close()


@bp.route("/positions/<pid>", methods=["DELETE"])
def position_delete(pid):
    """Remove a mistaken entry. Scoped to the owner."""
    conn = open_store()
    try:
        cur = conn.execute("DELETE FROM positions WHERE id = ? AND user_id = ?",
                           (pid, client_auth.current_user()))
        conn.commit()
    finally:
        conn.close()
    if cur.rowcount == 0:
        return jsonify({"error": "no such position"}), 404
    return "", 204
