#!/usr/bin/env python3
"""Fill in what actually happened to each published call.

One rule matters above the others: a call still inside its horizon stays
`open` and is never counted in a hit rate. Resolving early is how a track
record quietly starts overstating itself.

A call is a `hit` if the price AT RESOLUTION TIME is at or beyond the published
target. This is a spot-price comparison, not an intraday high/low check: a
stock that touched the target and gave it back before resolution grades a
miss. That is deliberately conservative -- it can understate the hit rate but
never overstate it.

A call published with no target cannot be graded against one. Such calls are
marked `ungraded` and excluded from the hit rate, rather than graded by a
softer rule that would pool two different standards into one published
number.

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

# An unrecognised horizon falls back to the LONGEST known window, not the
# shortest. publish-calls writes whatever horizon the payload carries, with no
# whitelist, so a horizon added to the scorer and not mirrored here would
# otherwise be graded after one day instead of thirty -- resolving a call 29
# days early while reporting success. Erring long makes an unknown horizon
# resolve late or never, which surfaces as calls stuck 'open' in calls-status.
# Erring short corrupts the hit rate silently. Only one of those is recoverable.
_FALLBACK_DAYS = max(HORIZON_DAYS.values())

QUOTE_URL = os.environ.get("TP_QUOTE_URL", "http://127.0.0.1:5050/api/stock/%s")


def is_elapsed(published_at, horizon, now):
    """Has this call's horizon passed? Pure -- `now` is supplied, never read.

    `now` and `published_at` must both be naive local ISO-8601, exactly as
    datetime.now().isoformat(timespec="seconds") produces. Passing an
    offset-aware string for one and not the other raises TypeError.
    """
    days = HORIZON_DAYS.get(horizon or "intraday", _FALLBACK_DAYS)
    due = datetime.fromisoformat(published_at) + timedelta(days=days)
    return datetime.fromisoformat(now) >= due


def classify(side, price_at_call, outcome_price, target):
    """hit only if the published target was reached. Everything else is a miss.

    A target is required. A call published without one cannot be graded
    against one, and grading it by a softer rule would pool two different
    standards into a single published percentage. Such calls are marked
    'ungraded' by main() and excluded from the hit rate instead.

    There is deliberately no `stop` parameter. A stop bounds a loss; it does
    not grade whether the call was right.
    """
    if target is None:
        raise ValueError("classify requires a target; ungraded calls are "
                         "handled by main()")
    if side == "SELL":
        return "hit" if outcome_price <= target else "miss"
    return "hit" if outcome_price >= target else "miss"


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
    resolved, skipped, failed, ungraded = 0, 0, 0, 0
    try:
        conn = app_store.get_db()
        app_store.init_db(conn)
        for row in due_calls(conn, now):
            try:
                price = fetch_price(row["symbol"])
            except Exception as e:
                # One bad quote must not cost the other due calls their cycle.
                # The call stays open and is retried tomorrow -- an unresolved
                # call is never counted, so nothing downstream is wrong.
                print("  %s: price fetch failed (%s: %s)"
                      % (row["symbol"], type(e).__name__, e), file=sys.stderr)
                failed += 1
                continue
            if price is None:
                # No price is not a miss. Leave it open and try again tomorrow.
                skipped += 1
                continue
            if row["target"] is None:
                # No published target means no standard to grade against. Record
                # what happened and exclude it, rather than grading it by a
                # softer rule that would inflate the hit rate.
                apply_outcome(conn, row["id"], price, "ungraded", now)
                ungraded += 1
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
    print("resolved %d call(s), %d ungraded (no target), %d left open for want"
          " of a price, %d failed" % (resolved, ungraded, skipped, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
