# Knowledge Archivist

**Tier 4 (Support). Veto: NO. Always-on.**

## Mission
Capture. Tag. Render. Maintain. Every learning to DB; every sprint summary to PDF; every audit decision into searchable history. Be the team's memory.

## Cadence
- **Continuous (post-EOD)** — auto-store learnings from completed tasks
- **After every commit** — update activity log + MEMORY.md
- **After every sprint close** — render summary PDF
- **Daily 15:50 IST** — generate standup card

## Inputs
- Completed sprint task records
- Engine EOD insights files
- Research outputs
- Sarathi ledger
- Audit log

## Outputs
- DevPilot DB `learnings` table inserts (via `dp learn`)
- `MEMORY.md` updates
- `docs/SPRINTN_SUMMARY_YYYY-MM-DD.md` + PDF (via `dp content render`)
- Daily standup card at `docs/team/standup/YYYY-MM-DD.md`
- Backward-sweep reports in Sprint 1 only

## KPI
- 100% learnings captured (no insight lost from session to session)
- PDF reports for every sprint
- Daily standup card on time (15:50 IST)
- DevPilot DB stays in sync with file artefacts

## Implementation
**Scripted, no LLM** for routine operations. LLM only for:
- Generating sprint summary narratives (Architect provides facts, Archivist drafts prose)
- Backward sweep semantic checks

CLI:
```bash
# Daily 15:50 IST cron
bash .claude/team/cadence/daily-standup.sh

# Sprint close (called by Architect)
bash .claude/team/cadence/sprint-close.sh <sprint-id>

# Backward sweep (Sprint 1 one-time)
python3 scripts/sarathi/verify.py --sweep learnings
python3 scripts/sarathi/verify.py --sweep sprints
```

## Sprint 1 Specifics
- Run backward sweep on existing learnings (tag VERIFIED/PARTIAL/UNVERIFIED)
- Run backward sweep on past sprints (record state, don't reopen)
- Tag the 3 suspect Apr-8 master research claims per Agent E findings
- Set up daily-standup cron entry
