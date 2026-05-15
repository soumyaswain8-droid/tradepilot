# SARATHI-SPR — Sprint Verification

**Triggered on:** sprint open, every task status transition, sprint close.

**Veto power:** YES — can BLOCK sprint open if planning incomplete; BLOCK sprint close if evidence missing.

## Rules

### SPR-001 — Pre-defined acceptance
Every task in a sprint must have explicit acceptance criteria *before* sprint opens (not retrofit mid-sprint).

- **Check:** at sprint open, every task has `acceptance` field with at least one verifiable condition (numeric threshold, file existence, test result, etc.).
- **Fail action:** `BLOCK` — sprint cannot open. Architect must define acceptance for every task.

### SPR-002 — Evidence on completion
Task marked `done` requires evidence: commit SHA, test result JSON, file output path, or screenshot link.

- **Check:** task transition `* → done` validates that `evidence` field is non-empty and references real artifacts (file exists OR commit SHA resolves OR URL responds 200).
- **Fail action:** `BLOCK` — status reverts to `in_progress` until evidence supplied.

### SPR-003 — Re-computable numbers
Any sprint summary number (P&L, IC, WR, Sharpe) must be re-derivable from raw data. The derivation script must be committed.

- **Check:** sprint summary doc contains a "Reproducibility" section pointing to script paths. Run-once verification: Sarathi executes the script and compares output to summary.
- **Fail action:** `BLOCK` — sprint cannot close.

### SPR-004 — No moving goalposts
Acceptance criteria frozen at sprint open. Mid-sprint scope changes require new task IDs, not edits to existing ones.

- **Check:** diff acceptance fields between sprint-open snapshot and current state. Any change to existing tasks' acceptance → flagged.
- **Fail action:** `BLOCK` if change to existing task's acceptance; `PASS` if change creates a new task ID.

### SPR-005 — Failure documented
Any task marked `blocked` requires a `blocker` field explaining why and what's needed to unblock.

- **Check:** task status = `blocked` AND `blocker` field non-empty.
- **Fail action:** `WARN` — task can stay blocked but blocker rationale must exist.

### SPR-006 — Sprint close gate
Cannot mark sprint `done` until:
- All tasks in final state (`done` / `blocked` / `cancelled`)
- All `done` tasks have evidence (SPR-002 passes)
- Summary numbers re-computable (SPR-003 passes)
- Summary PDF rendered via `dp content render`
- Learnings stored to DB (Knowledge Archivist confirms)
- Audit log has zero unresolved BLOCKs

- **Fail action:** `BLOCK` — sprint stays `active`. Each failed sub-check listed in the audit record.

## Output Schema

Per-sprint verification ledger at `docs/sarathi/reports/sprints/<sprint-id>.json`:
```json
{
  "sprint_id": "...",
  "opened_at": "...",
  "open_gate": {"result":"PASS|BLOCK","failed_rules":[],"acceptance_snapshot":{...}},
  "transitions": [
    {"ts":"...","task":"...","from":"todo","to":"done","gate":"PASS","evidence":"..."},
    ...
  ],
  "close_gate": null  // populated at close
}
```

## Backward Sweep (Sprint 1)

Knowledge Archivist runs SPR rules retrospectively against past sprints in DevPilot DB. Don't re-open completed sprints; just record verification state for posterity:
- How many tasks had pre-defined acceptance? (likely <50%)
- How many done-tasks have evidence on file? (likely sparse)
- How many sprint summaries are re-computable today?

Produces `docs/sarathi/reports/sprints/_sweep_2026-05-15.md` — establishes the baseline.
