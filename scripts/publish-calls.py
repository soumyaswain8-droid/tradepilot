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
    """GET the picks payload. Raises on any non-200, unparseable, or error body."""
    with urllib.request.urlopen(url, timeout=30) as r:
        if r.status != 200:
            raise RuntimeError("picks endpoint returned HTTP %s" % r.status)
        payload = json.loads(r.read().decode("utf-8"))
        # The picks endpoint returns HTTP 200 with an "error" key when scoring
        # fails, so a 200 alone does not mean success. Treated as a failure here
        # because a silently empty day is indistinguishable from a real one.
        if payload.get("error"):
            raise RuntimeError("picks endpoint reported: %s" % payload["error"])
        return payload


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
        side = str(p.get("direction", "")).upper()
        if side not in ("BUY", "SELL"):
            # HOLD / AVOID are not actionable calls. Recording one so a
            # resolver can later grade it would manufacture a hit rate out
            # of non-advice.
            continue
        sl_raw = p.get("stopLoss")
        if sl_raw is None:
            sl_raw = p.get("stop_loss_pct")
        tgt_raw = p.get("target")
        if tgt_raw is None:
            tgt_raw = p.get("target_pct")
        # v4's composite_scorer emits stopLoss/target; the v2 and v1 engines emit
        # stop_loss_pct/target_pct. app.py falls back between them on ImportError,
        # so both spellings are live. Reading only one silently captures every
        # call with no levels at all.
        sl_pct = abs(float(sl_raw or 0))
        tgt_pct = abs(float(tgt_raw or 0))
        # target and stopLoss are unsigned magnitudes -- composite_scorer derives
        # them from a volatility multiplier with no reference to direction. Which
        # side of the entry they land on is decided HERE, by the trade's side.
        # Applying the BUY arithmetic to a SELL would put a short's target above
        # its entry, and the resolver would then grade that short a hit whenever
        # the stock rose.
        sign = -1.0 if side == "SELL" else 1.0
        reasons = p.get("reasons") or []
        # reasons entries are dicts like {"text": ..., "type": "positive"|
        # "negative"}; join their plain text, positives and negatives alike,
        # in order. Be defensive: a plain-string entry still works.
        parts = [r.get("text") if isinstance(r, dict) else str(r) for r in reasons]
        rows.append({
            # Deterministic: a re-run on the same day produces the same id, so
            # the unique index collides instead of inserting a near-duplicate.
            "id": "call-%s-%s" % (symbol, day),
            "symbol": symbol,
            "side": side,
            "published_at": published_at,
            "price_at_call": price,
            "score": float(p.get("score") or 0),
            "signal": "; ".join(part for part in parts if part) or None,
            "horizon": horizon,
            "target": round(price * (1 + sign * tgt_pct / 100.0), 2) if tgt_pct else None,
            "stop": round(price * (1 - sign * sl_pct / 100.0), 2) if sl_pct else None,
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
