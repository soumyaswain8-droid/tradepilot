# M0 — Truth First: implementation plan

Spec: `docs/superpowers/specs/2026-09-10-m0-truth-first-design.md`. Local sprint only (do not sync to DevPilot sprint tables). No agent restarts Flask or touches running engines. No commits by agents.

- [ ] **WP-1 Pool-aware cost model + swing re-cost** — `scripts/v5-paper-trade.py` (`cost_for_trade(qty, entry, exit, pool="INTRADAY")`, delivery schedule per spec §2, call site in `close_position` passes `pool_name`); new `scripts/recost-swing-ledgers.py` (adds `cost_delivery`, `pnl_net_delivery` to every multi-day closed trade in `docs/paper-trades/*/**.json` without altering existing fields; summary per engine); new `docs/research/swing/2026-09-10-swing-cost-correction.md` (before/after table, what the 0.62%/deployment claim becomes). Tests in `tests/test_cost_model.py`.
- [ ] **WP-2 Terminology guard** — `compliance/terminology.yaml`, `tests/test_terminology_guard.py`, allow-list mechanism, findings fixed in place where they are plain copy (templates, JS, Dart), documented exceptions otherwise. Report every hit.
- [ ] **WP-3 Rosters from disk** — `prototype/engines.py` + `scripts/retired/RETIRED.txt`; rewire the three reporters and the watchdog; `tests/test_engine_discovery.py`.
- [ ] **WP-4 Ledger schema + migration** — `ledger/__init__.py`, `ledger/migrations/001_ledger.sql`, `ledger/hashing.py`, `ledger/migrate_json.py`, `ledger/queries.py` (record-page queries: net per engine per day, baseline beat rate, kill count), `tests/test_ledger.py` (uses the DevPilot Postgres; skip if unreachable). Connection: `postgresql://devpilot:<pw>@localhost:5499/devpilot`, schema `tradepilot`.
- [ ] **Verification** — full pytest, migration run twice, guard run on the real tree, reporters regenerated for 2026-09-09 from disk rosters.
