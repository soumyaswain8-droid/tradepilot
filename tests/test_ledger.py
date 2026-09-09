"""Ledger tests (WP-4). Skips cleanly when the DevPilot Postgres is unreachable.

Everything DB-side runs in a throwaway schema (TP_LEDGER_SCHEMA) that is dropped at the end,
so the real `tradepilot` schema is never touched by the test-suite.
"""
import datetime as dt
import hashlib
import json
import os
import uuid

import pytest

from ledger import db
from ledger.hashing import canonical_json, merkle_root, row_hash, sanitize

TEST_SCHEMA = "tradepilot_test_" + uuid.uuid4().hex[:8]


# ----------------------------------------------------------------------------- pure
def test_canonical_json_is_sorted_compact_and_repr_floats():
    assert canonical_json({"b": 1, "a": [1.5, 0.1, 2]}) == '{"a":[1.5,0.1,2],"b":1}'
    assert canonical_json({"x": 1e-05}) == '{"x":1e-05}'


def test_row_hash_stable_and_order_independent():
    a = {"symbol": "X", "qty": 3, "px": 10.25}
    b = {"px": 10.25, "qty": 3, "symbol": "X"}
    assert row_hash(a) == row_hash(b) == hashlib.sha256(canonical_json(a).encode()).hexdigest()
    assert row_hash({"symbol": "X", "qty": 4, "px": 10.25}) != row_hash(a)


def test_canonical_json_normalises_negative_zero_like_jsonb():
    assert canonical_json({"pnl": -0.0, "xs": [-0.0, -1.5]}) == '{"pnl":0.0,"xs":[0.0,-1.5]}'
    assert row_hash({"pnl": -0.0}) == row_hash({"pnl": 0.0})


def test_sanitize_drops_nan_and_inf():
    out = sanitize({"a": float("nan"), "b": [float("inf"), 1.0], "c": {"d": 2}})
    assert out == {"a": None, "b": [None, 1.0], "c": {"d": 2}}
    canonical_json(out)  # must not raise


def test_merkle_root_1_2_3_leaves_and_empty():
    h = lambda s: hashlib.sha256(s.encode()).hexdigest()  # noqa: E731
    a, b, c = h("a"), h("b"), h("c")
    assert merkle_root([]) == h("")
    assert merkle_root([a]) == a
    assert merkle_root([a, b]) == h(a + b)
    assert merkle_root([a, b, c]) == h(h(a + b) + h(c + c))  # odd leaf duplicated


# ----------------------------------------------------------------------------- db
@pytest.fixture(scope="module")
def conn():
    if not db.reachable():
        pytest.skip("ledger Postgres unreachable (TP_LEDGER_DSN)")
    os.environ["TP_LEDGER_SCHEMA"] = TEST_SCHEMA
    c = db.connect(autocommit=True)
    yield c
    with c.cursor() as cur:  # our own throwaway schema; the migration file itself never drops anything
        cur.execute(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE")
    c.close()
    os.environ.pop("TP_LEDGER_SCHEMA", None)


def _count(conn, table):
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {TEST_SCHEMA}.{table}")
        return cur.fetchone()[0]


def test_migration_is_idempotent(conn):
    db.apply_migration(conn, TEST_SCHEMA)
    db.apply_migration(conn, TEST_SCHEMA)
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s ORDER BY 1",
                    (TEST_SCHEMA,))
        names = [r[0] for r in cur.fetchall()]
    assert names == ["baselines", "calls", "disclosures", "ledger_roots", "outcomes", "panels", "verdicts"]
    assert "tradepilot." not in db.migration_sql(TEST_SCHEMA)  # fully re-pointed


def test_append_only_trigger_blocks_update_and_delete(conn):
    db.apply_migration(conn, TEST_SCHEMA)
    payload = {"kind": "call", "symbol": "TEST", "nonce": uuid.uuid4().hex}
    with conn.cursor() as cur:
        cur.execute(f"INSERT INTO {TEST_SCHEMA}.calls (payload, row_hash, symbol) VALUES (%s::jsonb, %s, %s) RETURNING id",
                    (canonical_json(payload), row_hash(payload), "TEST"))
        rid = cur.fetchone()[0]
    for stmt in (f"UPDATE {TEST_SCHEMA}.calls SET symbol = 'X' WHERE id = %s",
                 f"DELETE FROM {TEST_SCHEMA}.calls WHERE id = %s"):
        with pytest.raises(Exception) as ei, conn.cursor() as cur:
            cur.execute(stmt, (rid,))
        assert "append-only" in str(ei.value)
    with conn.cursor() as cur:
        cur.execute(f"SELECT symbol FROM {TEST_SCHEMA}.calls WHERE id = %s", (rid,))
        assert cur.fetchone()[0] == "TEST"


def test_row_hash_survives_jsonb_round_trip(conn):
    payload = {"kind": "outcome", "pnl_net": -0.0, "pnl_pct": -1.15, "qty": 32, "px": 1045.7,
               "tiny": 1e-05, "rows": [{"gross": -0.0, "net": 7053.16}], "text": "ORB breakdown \u2014 below"}
    with conn.cursor() as cur:
        cur.execute("SELECT %s::jsonb", (canonical_json(payload),))
        back = cur.fetchone()[0]
    assert row_hash(back) == row_hash(payload)


def _fixture_tree(tmp_path):
    day = {
        "date": "2026-09-01", "engine": "v9", "pools": {
            "INTRADAY": {"positions": [], "pnl": 0, "closed": [
                {"symbol": "ABC", "entry_price": 100.0, "exit_price": 101.0, "qty": 10, "entry_time": "09:30:00",
                 "exit_time": "10:00:00", "pnl": 10.0, "pnl_net": 8.5, "cost": 1.5, "reason": "TARGET",
                 "position_type": "LONG", "pool": "INTRADAY", "score": 71.2}]},
            "SWING": {"positions": [], "pnl": 0, "closed": []}}}
    (tmp_path / "docs" / "paper-trades" / "v9").mkdir(parents=True)
    (tmp_path / "docs" / "paper-trades" / "v9" / "2026-09-01.json").write_text(json.dumps(day))
    (tmp_path / "docs" / "research" / "daygain" / "baseline").mkdir(parents=True)
    (tmp_path / "docs" / "research" / "daygain" / "baseline" / "2026-09-01.json").write_text(json.dumps(
        {"date": "2026-09-01", "rule": "x", "capital": 1, "eod": {"net": 5.0, "gross": 6.0, "cost": 1.0, "rows": []}}))
    return tmp_path


def test_migrate_json_dry_run_writes_nothing(conn, tmp_path):
    from ledger import migrate_json
    root = _fixture_tree(tmp_path)
    r = migrate_json.run(root, dry_run=True, conn=conn, schema=TEST_SCHEMA, today=dt.date(2026, 9, 10))
    assert r["parsed"] == {"calls": 1, "outcomes": 1, "baselines": 1, "verdicts": 0}
    assert r["tables"]["calls"]["inserted"] == 1 and r["tables"]["outcomes"]["inserted"] == 1
    assert r["tables"]["baselines"]["inserted"] == 1 and r["roots"] is None
    assert _count(conn, "outcomes") == 0 and _count(conn, "baselines") == 0


def test_migrate_json_twice_is_idempotent_and_chain_verifies(conn, tmp_path):
    from ledger import migrate_json, queries
    root = _fixture_tree(tmp_path)
    today = dt.date(2026, 9, 10)
    first = migrate_json.run(root, conn=conn, schema=TEST_SCHEMA, today=today)
    second = migrate_json.run(root, conn=conn, schema=TEST_SCHEMA, today=today)
    assert first["tables"]["outcomes"]["inserted"] == 1 and first["roots"]["inserted"] == 1
    assert all(second["tables"][t]["inserted"] == 0 for t in second["tables"])
    assert second["roots"] == {"inserted": 0, "unchanged": 1, "mismatch": []}
    assert _count(conn, "outcomes") == 1 and _count(conn, "ledger_roots") == 1
    for t in ("calls", "outcomes", "baselines", "ledger_roots"):
        v = queries.verify_chain(t, conn=conn)
        assert v["ok"], v
    net = queries.net_by_engine_day("2026-09-01", "2026-09-01", conn=conn)
    assert [(r["engine"], r["net"], r["trades"]) for r in net if r["engine"] == "v9"] == [("v9", 8.5, 1)]
    beat = [r for r in queries.baseline_beat_rate("2026-09-01", "2026-09-01", rule="top10_gainers_0935", conn=conn)
            if r["engine"] == "v9"]
    assert beat and beat[0]["days_beat"] == 1  # 8.5 > 5.0
    with conn.cursor() as cur:  # outcome is linked to its synthesised call
        cur.execute(f"SELECT c.symbol, c.pre_registered FROM {TEST_SCHEMA}.outcomes o "
                    f"JOIN {TEST_SCHEMA}.calls c ON c.id = o.call_id WHERE o.engine = 'v9'")
        assert cur.fetchall() == [("ABC", False)]
