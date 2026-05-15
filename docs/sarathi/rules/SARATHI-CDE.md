# SARATHI-CDE — Code/Deploy Verification

**Triggered on:** every commit touching `prototype/v5/*`, `prototype/v4/*`, or `scripts/v*-paper-trade.py`; every engine launch.

**Veto power:** YES — BLOCKS engine launch if pre-flight fails; BLOCKS merge if shared-module rules violated.

## Rules

### CDE-001 — Pre-launch smoke
All active engines start cleanly, deploy 1 test signal, return correct state, exit cleanly.

- **Check:** existing Sarathi ledger pre-launch smoke gate (commit e6f03de). Extend to verify engine reads `verification_report.json` for its model and refuses bad models.
- **Fail action:** `BLOCK` — `launch-market.sh` refuses to start.

### CDE-002 — Shared-module changelog
Any change to `prototype/v5/*` must list which engines it affects in commit message. This is the v5_classic time-capsule lesson — shared modules silently affected the "frozen" baseline.

- **Check:** `git log --grep="affects:"` for commits touching `prototype/v5/`. Commit message must contain "affects: v4|v5|v5_classic|v5_6|v5_7|v5_8|v6" listing impacted engines.
- **Fail action:** `WARN` at commit time; `BLOCK` if merging to main without it.

### CDE-003 — Hot-path interface stability
Cannot change signature of `signal_engine.generate_signals` or `score_all_stocks` interface without a deprecation cycle (announce in N-1 sprint, deprecate in N, remove in N+1).

- **Check:** static analysis of function signatures vs last release. Diff in (positional args, kwargs, return type) → flag.
- **Fail action:** `BLOCK` merge if breaking change without deprecation marker.

### CDE-004 — Live diff vs prod
At each engine launch, compute SHA-256 of every loaded engine file vs last known-good. Surface drift on dashboard.

- **Check:** compare to `docs/team/last_known_good_shas.json`; any change is surfaced (not blocked — informational).
- **Fail action:** `INFO` — drift visible on `/team` dashboard.

### CDE-005 — Process tree clean
After any engine kill/restart, verify no zombie chrome-headless or python processes survived parent kill.

- **Check:** `pgrep -f "chrome-headless-shell"` and `pgrep -f "v[0-9]*-paper-trade.py"` both empty after kill.
- **Fail action:** `BLOCK` next launch until cleanup completes.

## Output Schema

Append to `docs/sarathi/ledger/YYYY-MM-DD.jsonl`:
```json
{"ts":"...","family":"SARATHI-CDE","rule":"CDE-001","subject":"v5 launch","result":"PASS","evidence":{...}}
```

## Backward Sweep (Sprint 1)

Snapshot current SHAs of all engine files → `docs/team/last_known_good_shas.json`. From now on, any drift is auditable.
