#!/usr/bin/env python3
"""Capture today's published calls into the `calls` table.

This job is the ONLY writer of `calls`. Everything the track record later
claims rests on it: if calls could be written from anywhere, "we called this"
stops being falsifiable.

It reads the SAME HTTP endpoint the product serves rather than calling the
scorer directly, so what is recorded is by construction what was published --
not a recomputation that might differ.

STOCKS ONLY. /api/picks?category=etfs and ?category=mf return hardcoded literal
arrays with invented recommendation strings; they are not model output and must
never enter the record.

Exit code 0 on success, 1 on any failure. Failure must be loud: a missing day
in the record is worse than a visible gap.
"""
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store

PICKS_URL = os.environ.get(
    "TP_PICKS_URL", "http://127.0.0.1:5050/api/picks?category=stocks&count=10")


def fetch_picks(url):
    """GET the picks payload. Raises on any non-200 or unparseable body."""
    with urllib.request.urlopen(url, timeout=30) as r:
        if r.status != 200:
            raise RuntimeError("picks endpoint returned HTTP %s" % r.status)
        return json.loads(r.read().decode("utf-8"))


def build_rows(payload, published_at):
    """Map a picks payload to `calls` rows. Pure -- no I/O, no clock."""
    category = payload.get("category", "stocks")
    if category != "stocks":
        raise ValueError(
            "refusing category %r: only 'stocks' is model output. etfs and mf "
            "are hardcoded literals and must never become calls." % category)

    day = published_at[:10]
    horizon = payload.get("horizon", "intraday")
    rows = []
    for p in payload.get("picks", []):
        symbol = str(p.get("symbol", "")).replace(".NS", "").replace(".BO", "")
        if not symbol:
            continue
        price = float(p.get("price") or 0)
        if price <= 0:
            continue
        sl_pct = float(p.get("stop_loss_pct") or 0)
        tgt_pct = float(p.get("target_pct") or 0)
        reasons = p.get("reasons") or []
        rows.append({
            # Deterministic: a re-run on the same day produces the same id, so
            # the unique index collides instead of inserting a near-duplicate.
            "id": "call-%s-%s" % (symbol, day),
            "symbol": symbol,
            "side": "BUY" if str(p.get("direction", "UP")).upper() == "UP" else "SELL",
            "published_at": published_at,
            "price_at_call": price,
            "score": float(p.get("score") or 0),
            "signal": "; ".join(str(r) for r in reasons) or None,
            "horizon": horizon,
            "target": round(price * (1 + tgt_pct / 100.0), 2) if tgt_pct else None,
            "stop": round(price * (1 - sl_pct / 100.0), 2) if sl_pct else None,
        })
    return rows


def insert_rows(conn, rows):
    """Insert rows, skipping any that already exist. Returns the insert count."""
    inserted = 0
    for r in rows:
        try:
            conn.execute(
                "INSERT INTO calls (id, symbol, side, published_at, price_at_call,"
                " score, signal, horizon, target, stop)"
                " VALUES (:id, :symbol, :side, :published_at, :price_at_call,"
                " :score, :signal, :horizon, :target, :stop)", r)
            inserted += 1
        except sqlite3.IntegrityError:
            # Already recorded today. Expected on a re-run; not an error.
            pass
    conn.commit()
    return inserted


def main():
    published_at = datetime.now().isoformat(timespec="seconds")
    try:
        payload = fetch_picks(PICKS_URL)
        rows = build_rows(payload, published_at)
        conn = app_store.get_db()
        app_store.init_db(conn)
        n = insert_rows(conn, rows)
        conn.close()
    except Exception as e:
        print("PUBLISH FAILED %s: %s: %s" % (published_at, type(e).__name__, e),
              file=sys.stderr)
        return 1
    print("published %d call(s) of %d pick(s) at %s" % (n, len(rows), published_at))
    return 0


if __name__ == "__main__":
    sys.exit(main())
