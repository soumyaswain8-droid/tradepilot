# ledger/ — TradePilot evidence ledger

Spec: `docs/superpowers/specs/2026-09-10-m0-truth-first-design.md` §5. Lives in the DevPilot
Postgres (`localhost:5499`, db `devpilot`) under schema **`tradepilot`**. Every table is
append-only (trigger raises on UPDATE/DELETE), every row is hashed, every table is a hash chain,
and every closed business date gets a Merkle root.

| file | role |
|---|---|
| `migrations/001_ledger.sql` | idempotent schema (`IF NOT EXISTS`, `OR REPLACE`, `DROP TRIGGER IF EXISTS`; never `DROP TABLE`) |
| `hashing.py` | `canonical_json`, `row_hash`, `merkle_root`, `sanitize` |
| `db.py` | `connect()`, `apply_migration()`, DSN/schema from env |
| `migrate_json.py` | `python3 -m ledger.migrate_json [--since D] [--dry-run] [--root DIR]` |
| `queries.py` | `net_by_engine_day`, `baseline_beat_rate`, `kill_count`, `verify_chain` |

## Connection
`TP_LEDGER_DSN` (default: local DevPilot), `TP_LEDGER_SCHEMA` (default `tradepilot`; the tests
use a throwaway schema and drop it). Driver: `psycopg` if importable, else `psycopg2`. Nothing
ever prints the DSN.

## Row model
Common columns: `id uuid`, `seq` (strict insertion order), `tenant`, `jurisdiction`,
`licence_scope`, `payload jsonb`, `row_hash`, `prev_hash`, `created_at`, plus a few typed,
indexed columns per table that are *derived from* the payload:

- `calls(symbol, market, side, engine, published_at, pre_registered, pre_registration_hash)`
- `verdicts(test_id, hypothesis, result ∈ PASS|KILL|PENDING, author)`
- `outcomes(call_id → calls.id, engine, trade_date, realized_net, cost)`
- `baselines(period_date, rule, net)`, `panels`, `disclosures`
- `ledger_roots(root_date, merkle_root, row_count)` unique per `(tenant, root_date)`

`row_hash = sha256(canonical_json(payload))` — the payload carries no ids or hashes of its own
row, so a re-run produces the same hash and is skipped. `canonical_json` normalises `-0.0` to
`0.0` because jsonb (numeric) has no negative zero; without that, `verify_chain` flags every row
that held a `-0.0` (103 outcomes + 5 shadow verdicts on the first real load). `prev_hash` is the previous row's hash in
the same table (`seq` order). Every payload carries `ledger_date` (the business date the row
belongs to); the Merkle root for a date is `merkle_root(sorted(row_hashes of all tables))`, so it
does not depend on insertion order. Roots are only written for dates **before today** (the day
must be closed). A stored root that no longer matches is reported as `ROOT MISMATCH` and left
alone — investigate; never "fix" it.

## What migrate_json loads
| source | rows |
|---|---|
| `docs/paper-trades/<engine>/<date>.json` closed trades (v5 pools shape, v4 flat `closed_trades`, older `closed`/`closed_positions`) | one `call` (synthesised from entry fields, `pre_registered=false`, `published_at` = entry date + time in exchange zone) + one `outcome` (fills, cost, `pnl_net` or `pnl`, reason, exit time, pool, linked by `call_hash`) |
| `docs/research/daygain/baseline/*.json` with an `eod` block | `baselines`, rule `top10_gainers_0935` |
| `docs/research/shadows/{armband,regime}/*.json` | `verdicts` PENDING, test_id `armband-shadow` / `regime-shadow` |
| `docs/research/daygain/phase0-holdout-*.md` | `verdicts` KILL, test_id `daygain-phase0` (full text + sha256 in payload) |

`us_v1` files repeat closed trades across days; `trade_date` comes from `exit_ts` so the repeat
hashes identically and is skipped. `--dry-run` parses, counts against the live tables, and rolls
back. Exit code 1 on a root mismatch, 2 if the DB is unreachable.

## Verify
```bash
python3 -c "from ledger import queries; print(queries.verify_chain('outcomes'))"
python3 -m pytest tests/test_ledger.py -q
```
