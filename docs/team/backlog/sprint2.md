# Sprint 2 Backlog — TP-S2-001

**Sprint:** TP-S2-001 · Triple-Barrier Labels + Postmortem Hardening
**Planned window:** week of 2026-05-25 (after Sprint 1 wrap)
**Source of truth:** DevPilot DB `sdlc_tasks` table (this file is a mirror for git visibility)

---

## Why this sprint has 6 postmortem items

Monday 2026-05-18 09:10 IST: the automated launch fired correctly, but **v5 silently died at startup** due to an interaction between two independent safety systems (`check_model_freshness` guard vs SARATHI-ML CEO override) that didn't know about each other. v5 was down for 10 minutes. Caught at 09:20 via manual `pgrep`; would have been invisible until 15:30 P&L review without a status check.

Root-cause incident: `signal_guards.py:check_model_freshness()` had `max_age_days=3`; the restored May-9 model is 9 days old. Fixed live at 09:20 in commit `5593c77` by making the guard respect the CEO override in `verification_report.json`.

Sprint 2 adds 6 tasks to prevent the **class of bug** (not just this instance) from recurring, plus the 2 main work items already on the 8-week plan.

---

## Postmortem Hardening (6 tasks)

### S2-PM-001 · Preflight: add `--smoke-engine` dry-boot mode  ·  **high**
**Why:** preflight at 08:50 IST passed 27/27 today, but didn't try to actually *boot* engines. Static config can be perfect while engine startup still SystemExits.
**Fix:** add `--smoke-engine` mode that runs each engine with a short timeout, captures stderr + exit code, fails preflight if any engine errors.
**Pass criteria:** the 2026-05-18 incident is reproducible — re-introduce a tight staleness check and `preflight --smoke-engine` MUST detect it.

### S2-PM-002 · `market_go.py`: assert engine count after launch  ·  **high**
**Why:** launch-market.sh's internal verify reported "Engines: 2/7" today. The discrepancy was visible in logs but didn't propagate to Sarathi BLOCK because market_go.py only checked subprocess exit code.
**Fix:** after launch returns, `pgrep` actual engines, compare to expected count, log SARATHI-CDE BLOCK if short → Telegram pages.
**Pass criteria:** force-kill v5 right after launch → market_go.py exits non-zero with BLOCK in audit log.

### S2-PM-003 · Audit codebase for "two safety guards disagree" pattern  ·  **medium**
**Why:** check_model_freshness and SARATHI-ML override were added independently and disagreed. This pattern likely exists elsewhere.
**Scope:** sweep `*_guard`, `check_*`, `verify_*` in `prototype/utils/`, `prototype/v4/`, `prototype/v5/` and all SARATHI-* rules. Map which check the same predicate.
**Pass criteria:** audit report committed at `docs/research/safety-guards-audit-2026-MM.md`; any conflicts unified via shared source of truth; new SARATHI-SPR rule: "no two guards may check the same predicate with different thresholds without explicit linkage."

### S2-PM-004 · Fix launch-market.sh stale engine counter  ·  **low**
**Why:** prints "Engines: 2/7" but we only run 3. The "/7" is hardcoded from pre-Sprint-1 zoo.
**Fix:** derive from `${#ENGINES[@]}` (length of the array).
**Pass criteria:** log shows "Engines: 3/3" when all alive, "2/3" when one died.

### S2-PM-005 · Decide v4 staleness-guard policy  ·  **medium**
**Why:** Today v5 broke from check_model_freshness; v4 and v5_classic kept running on the same "stale" model because they don't call the guard. Inconsistent.
**Choice:** (a) add guard to v4 + v5_classic (uniform safety, override already bypasses), or (b) explicitly document v4 as exempt.
**Recommendation:** Option A — guard now respects override so behavior is unchanged while override is active.

### S2-PM-006 · Map `launch-market.sh` exit codes; treat non-zero as Sarathi BLOCK  ·  **high**
**Why:** launch-market.sh returned exit 6 today. market_go.py logged it but didn't propagate. Silent failure.
**Fix:** document exit codes in launch-market.sh header; market_go.py turns any non-zero into Sarathi BLOCK audit + Telegram page.
**Pass criteria:** force a non-zero exit from launch-market.sh → BLOCK appears on `/team/sarathi`.

---

## Main Sprint 2 Work (from 8-week plan)

### S2-MAIN-001 · Triple-barrier label generator  ·  **high**
**Why:** López de Prado AFML Ch.3 — fixed-horizon return labels destroy IC in retail setups. Triple-barrier {TP_hit, SL_hit, vertical_timeout} categorical labels reportedly halve drawdown on intraday equity (arXiv 2504.02249).
**Output:** `prototype/v4/labels/triple_barrier.py` + `prototype/v4/data/labels_triple_barrier.parquet` covering Apr-21 → today.
**Pass criteria:** 80%+ label match against existing `exit_reason` field in trade JSONs; SARATHI-LRN entry citing source.

### S2-MAIN-002 · Wire `record_slippage()` into v4 exit paths  ·  **medium**
**Why:** Deferred from Sprint 1 because v4 has a different exit structure than v5/v5_classic (which we did wire).
**Pass criteria:** v4 exits show up in `docs/slippage/YYYY-MM-DD.jsonl`; daily exec-eod aggregate now includes v4 alongside v5/v5_classic.

---

## Sprint 2 Acceptance Gates (per SARATHI-SPR-006)

Cannot close Sprint 2 until ALL:
- [ ] All 8 tasks final-state (`done` or `cancelled` with rationale)
- [ ] S2-PM-001 verified by reproducing the 2026-05-18 incident
- [ ] Audit report from S2-PM-003 committed
- [ ] Sprint 2 summary PDF rendered via `dp content render`
- [ ] Learnings (postmortem + triple-barrier method) stored to DevPilot DB
- [ ] `/team/sarathi` audit log has zero unresolved BLOCKs

---

_Mirror of DevPilot DB `sdlc_tasks` where `sprint_id='TP-S2-001'`. Authoritative state is in the DB; this file is for code-review visibility._
