#!/usr/bin/env python3
"""Fill in what actually happened to each published call.

One rule matters above the others: a call still inside its horizon stays
`open` and is never counted in a hit rate. Resolving early is how a track
record quietly starts overstating itself.

A call is a `hit` only if it reached the target that was published with it.
A favourable-but-short move is a miss. Grading on anything softer would make
the published target decorative.

Exit code 0 on success, 1 on any failure.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store

HORIZON_DAYS = {"intraday": 1, "swing": 7, "investment": 30}

QUOTE_URL = os.environ.get("TP_QUOTE_URL", "http://127.0.0.1:5050/api/stock/%s")


def is_elapsed(published_at, horizon, now):
    """Has this call's horizon passed? Pure -- `now` is supplied, never read."""
    days = HORIZON_DAYS.get(horizon or "intraday", HORIZON_DAYS["intraday"])
    due = datetime.fromisoformat(published_at) + timedelta(days=days)
    return datetime.fromisoformat(now) >= due


def classify(side, price_at_call, outcome_price, target):
    """hit only if the published target was reached. Everything else is a miss.

    When no target was published -- the scorer can return target_pct = 0, and
    build_rows stores None -- the bar falls back to the call price and requires
    a strict move, so flat is not a win. Without that fallback every
    target-less call would score a miss and bias the record downward for a
    reason that has nothing to do with the calls being wrong.

    There is deliberately no `stop` parameter. A stop bounds a loss; it does
    not grade whether the call was right.
    """
    if target is not None:
        return "hit" if (outcome_price <= target if side == "SELL"
                         else outcome_price >= target) else "miss"
    return "hit" if (outcome_price < price_at_call if side == "SELL"
                     else outcome_price > price_at_call) else "miss"


def due_calls(conn, now):
    """Open calls whose horizon has elapsed."""
    rows = conn.execute(
        "SELECT * FROM calls WHERE outcome = 'open' ORDER BY published_at").fetchall()
    return [r for r in rows if is_elapsed(r["published_at"], r["horizon"], now)]


def apply_outcome(conn, call_id, outcome_price, outcome, now):
    """Record the result. Writes all three outcome fields together."""
    conn.execute(
        "UPDATE calls SET outcome_price = ?, outcome = ?, outcome_at = ?"
        " WHERE id = ?", (outcome_price, outcome, now, call_id))
    conn.commit()


def fetch_price(symbol):
    """Current price for a symbol, or None if unavailable."""
    with urllib.request.urlopen(QUOTE_URL % symbol, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    price = data.get("price") or data.get("current_price")
    return float(price) if price else None


def main():
    now = datetime.now().isoformat(timespec="seconds")
    resolved, skipped = 0, 0
    try:
        conn = app_store.get_db()
        app_store.init_db(conn)
        for row in due_calls(conn, now):
            price = fetch_price(row["symbol"])
            if price is None:
                # No price is not a miss. Leave it open and try again tomorrow.
                skipped += 1
                continue
            outcome = classify(row["side"], row["price_at_call"], price,
                               row["target"])
            apply_outcome(conn, row["id"], price, outcome, now)
            resolved += 1
        conn.close()
    except Exception as e:
        print("RESOLVE FAILED %s: %s: %s" % (now, type(e).__name__, e),
              file=sys.stderr)
        return 1
    print("resolved %d call(s), %d left open for want of a price" % (resolved, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
