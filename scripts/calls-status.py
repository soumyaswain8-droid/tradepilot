#!/usr/bin/env python3
"""Print the state of the calls record.

A capture pipeline nobody can see is a pipeline that stops without anyone
noticing -- and every day it is stopped is a day of proof that cannot be
recovered. Run this whenever you want to know the record is alive.
"""
import os
import sys
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


def summarise(conn, now):
    """Aggregate the record. `now` is supplied so this stays testable."""
    rows = conn.execute("SELECT published_at, outcome FROM calls").fetchall()
    total = len(rows)
    hit = sum(1 for r in rows if r["outcome"] == "hit")
    miss = sum(1 for r in rows if r["outcome"] == "miss")
    open_ = sum(1 for r in rows if r["outcome"] == "open")
    resolved = hit + miss

    days = sorted({r["published_at"][:10] for r in rows})
    gaps = []
    if days:
        cur = datetime.fromisoformat(days[0]).date()
        end = datetime.fromisoformat(now[:10]).date()
        have = set(days)
        while cur <= end:
            # Monday is 0, Saturday 5, Sunday 6. A closed market is not a gap.
            if cur.weekday() < 5 and cur.isoformat() not in have:
                gaps.append(cur.isoformat())
            cur += timedelta(days=1)

    return {
        "total": total, "open": open_, "resolved": resolved,
        "hit": hit, "miss": miss,
        # None, never 0.0 -- an unresolved record is not a record of failure.
        "hit_rate": round(100.0 * hit / resolved, 1) if resolved else None,
        "first_call": days[0] if days else None,
        "last_call": days[-1] if days else None,
        "days_covered": len(days),
        "gaps": gaps,
    }


def main():
    """Print the record's state to stdout and return the process exit code."""
    conn = app_store.get_db()
    app_store.init_db(conn)
    s = summarise(conn, datetime.now().isoformat(timespec="seconds"))
    conn.close()

    if s["total"] == 0:
        # A dead pipeline that once ran self-corrects: first_call is fixed, the
        # gap loop marches forward from it, and the next weekday shows up as a
        # gap. A pipeline that has NEVER run has no such anchor -- days is
        # empty, the loop is skipped, and "gaps none" would be reported forever.
        # A fresh install and a year of flawless running must not look alike.
        print("NO CALLS EVER RECORDED -- the publish job has not run "
              "successfully even once.")
        print("Check that prototype/app.py is running, then run "
              "scripts/publish-calls.py by hand.")
        return 1

    print("calls recorded    %d  (%d open, %d resolved)"
          % (s["total"], s["open"], s["resolved"]))
    print("hit rate          %s"
          % ("%.1f%% of %d resolved" % (s["hit_rate"], s["resolved"])
             if s["hit_rate"] is not None else "-- (nothing resolved yet)"))
    print("covering          %s to %s  (%d day%s with calls)"
          % (s["first_call"] or "--", s["last_call"] or "--",
             s["days_covered"], "" if s["days_covered"] == 1 else "s"))
    if s["gaps"]:
        print("MISSING DAYS      %d: %s" % (len(s["gaps"]), ", ".join(s["gaps"][:10])))
        return 1
    print("gaps              none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
