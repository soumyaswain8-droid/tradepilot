# Soumya Swain — Founder / CEO

**Tier 1 (Executive). Veto: ABSOLUTE.**

## Mission
Set direction. Approve direction-of-the-week. Override any agent veto when needed (overrides are recorded in the audit log). Own the P&L outcome.

## Cadence
- **Weekly Sunday** — sprint review with Architect, Alpha Hunter, Execution Analyst
- **Daily** — review 15:50 IST standup card (5 min)
- **Ad-hoc** — paged on Drift Watcher escalations, Sarathi blocks needing override

## Inputs
- Daily standup card from Knowledge Archivist
- Weekly sprint progress from Architect
- Cost-corrected Sharpe trajectory from Execution Analyst
- IC trajectory from Alpha Hunter

## Outputs
- Sprint-level go/no-go decisions
- Risk-budget allocation
- Capital allocation decisions
- Architecture decisions for major direction changes

## Authority
Final approval on:
- Sprint roadmap
- Sharpe target adjustment (currently 1.5 net 10bps in 6 months — option 1B)
- Engine consolidation decisions (currently v4 + v5 + v5_classic — option 3B)
- Live deployment of any model
- Override any agent veto with logged reason

## Constraints Set
```
Sharpe target (6mo):     1.5 net of 10bps slippage
Cost assumption:         10bps round-trip baseline; 15bps stress
Engine scope:            v4, v5, v5_classic (3 engines, post-consolidation)
Capital ceiling:         Rs 10L paper per engine
Fact-check priority:     Slippage realism (option 2C)
Sprint cadence:          1 week, with Sarathi gate at each close
```

## Communication
Daily check-in via standup card. Sunday sync via weekly review. Paged via dashboard alerts only on:
- Drift Watcher CHANGE event
- Sarathi BLOCK awaiting override
- DQO data-block on engine start
