"""Record-page queries. Plain SQL; every function returns a list of dicts.

Dates are ISO strings or datetime.date. Pass an open connection to reuse one; otherwise a
connection is opened per call.
"""
from __future__ import annotations

from contextlib import contextmanager

from . import TABLES, db
from .hashing import row_hash


@contextmanager
def _conn(conn=None):
    if conn is not None:
        yield conn
        return
    c = db.connect(autocommit=True)
    try:
        yield c
    finally:
        c.close()


def _q(conn, sql: str, params=()) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return db.rows_as_dicts(cur)


def net_by_engine_day(date_from, date_to, conn=None, tenant: str = "tradepilot") -> list[dict]:
    """Realised net, cost and trade count per (engine, trade_date) from outcomes."""
    s = db.schema()
    with _conn(conn) as c:
        return _q(c, f"""
            SELECT engine, trade_date::text AS trade_date,
                   COUNT(*)::int AS trades,
                   ROUND(SUM(realized_net)::numeric, 2) AS net,
                   ROUND(SUM(COALESCE(cost, 0))::numeric, 2) AS cost
            FROM {s}.outcomes
            WHERE tenant = %s AND trade_date BETWEEN %s AND %s
            GROUP BY engine, trade_date
            ORDER BY trade_date, engine""", (tenant, str(date_from), str(date_to)))


def baseline_beat_rate(date_from, date_to, rule: str = "top10_gainers_0935", conn=None,
                       tenant: str = "tradepilot") -> list[dict]:
    """Per engine: days (with a baseline) where engine net > baseline net."""
    s = db.schema()
    with _conn(conn) as c:
        return _q(c, f"""
            WITH eng AS (
                SELECT engine, trade_date, SUM(realized_net) AS net
                FROM {s}.outcomes
                WHERE tenant = %s AND trade_date BETWEEN %s AND %s
                GROUP BY engine, trade_date),
            base AS (
                SELECT period_date, MAX(net) AS net
                FROM {s}.baselines
                WHERE tenant = %s AND rule = %s AND period_date BETWEEN %s AND %s
                GROUP BY period_date)
            SELECT eng.engine,
                   COUNT(*)::int AS days_compared,
                   SUM(CASE WHEN eng.net > base.net THEN 1 ELSE 0 END)::int AS days_beat,
                   ROUND(AVG(CASE WHEN eng.net > base.net THEN 1.0 ELSE 0.0 END), 4) AS beat_rate
            FROM eng JOIN base ON base.period_date = eng.trade_date
            GROUP BY eng.engine
            ORDER BY beat_rate DESC, eng.engine""",
                  (tenant, str(date_from), str(date_to), tenant, rule, str(date_from), str(date_to)))


def kill_count(conn=None, tenant: str = "tradepilot") -> list[dict]:
    """KILL verdicts per test_id (sum `kills` for the headline number)."""
    s = db.schema()
    with _conn(conn) as c:
        return _q(c, f"""
            SELECT test_id, COUNT(*)::int AS kills
            FROM {s}.verdicts
            WHERE tenant = %s AND result = 'KILL'
            GROUP BY test_id ORDER BY test_id""", (tenant,))


def verify_chain(table: str, conn=None) -> dict:
    """Recompute every row_hash from payload and check prev_hash links in seq order.
    Returns {"table", "ok", "rows", "bad": [ {seq, reason} ... ]}."""
    if table not in TABLES:
        raise ValueError(f"unknown ledger table {table!r}")
    s = db.schema()
    bad: list[dict] = []
    n = 0
    prev = None
    with _conn(conn) as c, c.cursor() as cur:
        cur.execute(f"SELECT seq, payload, row_hash, prev_hash FROM {s}.{table} ORDER BY seq")
        for seq, payload, h, ph in cur:
            n += 1
            if row_hash(payload) != h:
                bad.append({"seq": seq, "reason": "row_hash does not match payload"})
            if ph != prev:
                bad.append({"seq": seq, "reason": f"prev_hash {str(ph)[:12]} != previous row {str(prev)[:12]}"})
            prev = h
    return {"table": table, "ok": not bad, "rows": n, "bad": bad}
