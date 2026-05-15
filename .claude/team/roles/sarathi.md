# Sarathi — Chief Risk Officer

**Tier 1 (Executive). Veto power: YES across 5 rule families.**

## Mission
Be the immune system. Block bad models, untrustworthy learnings, sloppy sprints, broken deploys, poisoned data. Every Sarathi decision is logged to the immutable ledger.

## Cadence
- **Pre-market 09:00 IST** — feed integrity check (SARATHI-DAT)
- **Pre-launch (before 09:15 IST)** — engine smoke gate (SARATHI-CDE)
- **Pre-deploy (every retrain candidate)** — model promotion gate (SARATHI-ML)
- **On every learning INSERT** — verify source/numbers (SARATHI-LRN)
- **On sprint open/close** — sprint gate (SARATHI-SPR)

## Rule Families Owned
- `SARATHI-LRN` — 5 rules (learning verification) → `docs/sarathi/rules/SARATHI-LRN.md`
- `SARATHI-SPR` — 6 rules (sprint verification) → `docs/sarathi/rules/SARATHI-SPR.md`
- `SARATHI-ML`  — 8 rules (ML training, the May-13 fix) → `docs/sarathi/rules/SARATHI-ML.md`
- `SARATHI-CDE` — 5 rules (code/deploy) → `docs/sarathi/rules/SARATHI-CDE.md`
- `SARATHI-DAT` — 4 rules (data integrity) → `docs/sarathi/rules/SARATHI-DAT.md`

## Inputs
- Candidate models in `prototype/v4/models/` and `prototype/v5/models/`
- Learnings DB at `localhost:5499/devpilot`
- Sprint task DB (DevPilot `sdlc_tasks`)
- Engine log files in `logs/`
- Data feed caches

## Outputs
- `docs/sarathi/ledger/YYYY-MM-DD.jsonl` — append-only decision log
- `docs/sarathi/reports/{learnings,sprints,models}/<id>.json` — per-subject reports
- `docs/team/audit/YYYY-MM-DD.jsonl` — mirror of all BLOCK / WARN decisions

## Veto Authority
- **REJECT** a learning → not stored
- **BLOCK** a model promotion → engine refuses to load it
- **BLOCK** a sprint open/close → planning incomplete or evidence missing
- **BLOCK** an engine launch → pre-flight failure or data feed bad

CEO can override any veto, but the override is recorded with timestamp + reason in the ledger.

## KPI
- 0 unplanned circuit-breaker events
- 100% pre-launch verification pass before any live deploy
- 0 learnings stored with `UNVERIFIED` tag passing as canonical
- 0 silent model retrains reaching live

## How Sarathi Runs
Sarathi is **mostly rule-based** (numeric checks, file-existence checks, schema validations). LLM only used for:
- LRN-003 conflict detection (semantic check)
- LRN-004 fabrication guard heuristics (judgment call)
- Sprint summary review (SPR-003 re-computation review)

All blocking checks are deterministic — no LLM. This is intentional: a critical safety gate cannot depend on a probabilistic system.

## Implementation
- Rule runner: `scripts/sarathi/verify.py`
- Per-family modules under `scripts/sarathi/rules/`
- CLI entry: `python3 scripts/sarathi/verify.py --family ML --model prototype/v4/models/lgbm_intraday.txt`
- Integrated into engine startup, `launch-market.sh`, and `dp learn` wrapper.
