# M0 — Truth First (platform redesign, milestone 0)

Date: 2026-09-10. Status: approved by Soumya (in chat, 02:45 IST). Blueprint: "TradePilot Platform Redesign Blueprint" (9 Sep) — this spec covers its §10 items 1, 2, 5 and the roster fix; items 3, 4, 6 are running experiments or human tasks.

## Why
An acquirer buys the evidence ledger. Today the evidence is JSON-per-day files with one verified accounting bug (swing pool costed at intraday 12 bps; delivery is ~24 bps) and reporters that hard-code engine rosters from June. Before any surface is rebuilt, the numbers must be right and queryable.

## Decisions
1. **Modular monolith, not services.** `prototype/` stays one deployable. New code lives in two packages: `ledger/` (schema, migration, hashing, queries) and later `research_core/`. No new runtime for M0.
2. **Cost model is pool-aware.** `cost_for_trade` gains a `pool` argument. INTRADAY keeps the existing model (unchanged numbers, comparability). Multi-day pools (SWING, POSITIONAL, INVESTMENT) use the Zerodha delivery schedule: brokerage 0; STT 0.1% on buy AND sell value; NSE exchange txn 0.00297% of turnover; SEBI 0.0001% of turnover; stamp 0.015% of buy value; GST 18% on (brokerage + exchange + SEBI); DP charge Rs 15.34 + GST per sell scrip. Historical swing ledgers are re-costed by a script that writes `pnl_net_delivery`/`cost_delivery` fields ALONGSIDE the old fields (never overwrites), and a corrected swing verdict document is written.
3. **Terminology guard** is a pytest (`tests/test_terminology_guard.py`) scanning `prototype/templates/*.html`, `prototype/static/**/*.js`, `app/lib/**/*.dart` and `docs/product/**` for a versioned banned list in `compliance/terminology.yaml`: predict, prediction, guarantee(d), assured, expected profit, will earn, sure-shot, risk-free. Allow-list by file+line for documented exceptions (e.g. the word inside a disclaimer). Fails the build.
4. **Rosters from disk.** A single `prototype/engines.py` exposes `discover_engines(date)` = engines with a `docs/paper-trades/<engine>/<date>.json`, minus `scripts/retired/`-listed names. `eod-comparison-report.py`, `missed-trades-report.py`, `eod-insights.py` and `missed-opportunities-watchdog.py` use it. No hard-coded rosters remain.
5. **Ledger schema** in the DevPilot Postgres (localhost:5499, db devpilot) under schema `tradepilot`, migration file `ledger/migrations/001_ledger.sql` (idempotent, IF NOT EXISTS everywhere, no DROP). Tables: `calls`, `verdicts`, `outcomes`, `baselines`, `panels`, `disclosures`, `ledger_roots`. Every table: `id uuid`, `tenant text default 'tradepilot'`, `jurisdiction text default 'IN'`, `licence_scope text`, `row_hash text` (sha256 of canonical JSON of the row minus hash/ids), `prev_hash text`, `created_at timestamptz`. Append-only enforced by a trigger that raises on UPDATE/DELETE. `ledger_roots` holds one Merkle root per (tenant, date). `ledger/migrate_json.py` loads every `docs/paper-trades/*/<date>.json` closed trade as an `outcome` (with `call` rows synthesised from the trade's entry fields, `pre_registration_hash` null and flagged `pre_registered=false`), every `docs/research/**/phase0*.md` + shadow ledgers as `verdicts`, and `docs/research/daygain/baseline/*.json` as `baselines`. Re-runnable; skips rows whose hash exists.
6. **No surface changes in M0.** No route, template or Flutter screen changes except the guard's findings.

## Out of scope
Services split, Quant Lab UI, RA filing, data-vendor agreement (flagged as M1 gate), Kite live orders, changing INTRADAY costs, touching v5's stop/trailing/regime (experiment window to 09-19).

## Testing
`python3 -m pytest tests/ -q` stays green plus new tests: cost model (delivery vs intraday numbers on a fixed trade), discovery (fixture dirs), terminology guard (self-test with a planted word), migration (load a fixture day twice → identical row count, hashes stable), append-only trigger (UPDATE raises).
