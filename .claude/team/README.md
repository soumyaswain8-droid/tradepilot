# TradePilot Quant Desk — Team Charter

**Status:** Sprint 1 — Foundation
**Created:** 2026-05-15
**Owner:** Soumya Swain (CEO)

## Operating Principle

This isn't a sprint; it's a desk. Separation of duties (research never deploys to live; ops never approves their own work), explicit veto rights for risk, daily/weekly cadences, one CEO with final call.

Every agent has: **cadence, inputs, outputs, veto authority, KPI, fallback.**

## Org Chart

```
                   ┌──────────────────────────┐
                   │  SOUMYA  — Founder/CEO    │
                   │  Final approver, vision   │
                   └────────────┬──────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
 ┌──────▼───────┐       ┌───────▼───────┐       ┌──────▼──────┐
 │ SARATHI      │       │ ARCHITECT     │       │ ALPHA HUNTER│
 │ Chief Risk   │       │ Head of Eng   │       │ Research    │
 │ 5 rule fam.  │       │ Owns roadmap  │       │ (T2 weekly) │
 └──────┬───────┘       └───────┬───────┘       └─────────────┘
        │                       │
        │     ┌─────────────────┼──────────────────┐
        │  ┌──▼───────────┐  ┌──▼──────────────┐   │
        │  │ MLOPS        │  │ EXECUTION       │   │
        │  │ SENTINEL     │  │ ANALYST         │   │
        │  │ Promo gate   │  │ Slippage/cost   │   │
        │  └──┬───────────┘  └─────────────────┘   │
        │     │                                    │
        │     ▼                                    │
        │   ┌─────────────────────┐                │
        └──►│ DRIFT WATCHER       │ ───────────────┘
            │ Live IC + ADWIN     │
            └─────────────────────┘

 ┌────────────────────┐    ┌────────────────────┐
 │ DATA QUALITY OFFR  │    │ COMPETITIVE INTEL  │
 │ Feed health (T3)   │    │ Weekly scans (T3)  │
 └────────────────────┘    └────────────────────┘

 ┌────────────────────┐
 │ KNOWLEDGE ARCHIVIST│ (T4, always-on)
 └────────────────────┘
```

## The Nine Agents

| # | Agent | Tier | Cadence | Veto |
|--:|---|:--:|---|:--:|
| 1 | Soumya (CEO) | T1 | Weekly + ad-hoc | Absolute |
| 2 | Sarathi (CRO) | T1 | Pre-deploy / pre-09:15 IST | YES |
| 3 | Architect (Head of Eng) | T1 | Daily code review + weekly roadmap | YES |
| 4 | Alpha Hunter (Quant Research) | T2 | Weekly Fri + monthly deep dive | No |
| 5 | MLOps Sentinel | T2 | Every retrain + daily post-close | YES |
| 6 | Execution Analyst | T2 | Daily post-close | Recommends sizing |
| 7 | Drift Watcher | T3 | Continuous during market hours | Pages Sarathi |
| 8 | Data Quality Officer | T3 | 09:00 / 11:00 / 15:30 IST | YES (data block) |
| 9 | Competitive Intel Officer | T3 | Sunday weekly | No |
| — | Knowledge Archivist | T4 | Post-EOD always | No |

## Authority Map

Three independent veto holders must approve any model promotion to live:

```
Architect (code OK)  +  MLOps Sentinel (IC OK)  +  Sarathi (risk OK)
                                │
                                ▼
                         Deploy allowed
```

DQO has independent data-block authority. CEO override possible but always recorded in audit log.

## Sarathi Rule Catalog (Five Families)

| Family | Prefix | Triggers on |
|---|---|---|
| Learning Verification | `SARATHI-LRN` | Every learning written |
| Sprint Verification | `SARATHI-SPR` | Every sprint open / close / task transition |
| ML Training Verification | `SARATHI-ML` | Every retrain candidate (the May-13 fix) |
| Code/Deploy Verification | `SARATHI-CDE` | Every engine-touching commit, every launch |
| Data Verification | `SARATHI-DAT` | Feed integrity pre-market, intraday, post-close |

Full rule definitions in `docs/sarathi/rules/SARATHI-*.md`.

## File Layout

```
.claude/team/
  README.md                  this charter
  roles/                     9 role prompts (one .md per agent)
  cadence/                   daily / weekly automation
  gates/                     gate definitions (LLM-readable)

scripts/team/
  log.py                     audit + activity logger (shared)
  gates/
    mlops-ic-gate.py         SARATHI-ML implementation
    data-quality-gate.py     SARATHI-DAT implementation
  slippage.py                slippage logging helper

scripts/sarathi/
  verify.py                  rule runner for all 5 families

docs/team/
  status/                    per-agent live status (overwritten)
  activity/YYYY-MM-DD.jsonl  append-only activity feed
  audit/YYYY-MM-DD.jsonl     append-only audit log (gate decisions)
  standup/YYYY-MM-DD.md      daily 15:45 IST card

docs/sarathi/
  rules/SARATHI-*.md         5 rule catalogs
  ledger/YYYY-MM-DD.jsonl    Sarathi decision ledger
  reports/
    learnings/               per-learning verification records
    sprints/                 per-sprint verification ledgers
    models/                  per-model verification reports
```

## Sprint Cadence — The 8-Week Rebuild

| Wk | Theme | Lead | Sarathi gate |
|--:|---|---|---|
| 1 | Stop bleed + dashboard + Sarathi 5-family rules | Architect | SARATHI-ML, CDE live |
| 2 | Triple-barrier labels | Alpha Hunter | SARATHI-ML on new labels |
| 3 | Sector-RS + OFI + Kyle's λ | Alpha Hunter | CPCV IC ≥ 0.02 |
| 4 | Meta-label classifier | MLOps Sentinel | Backtest Sharpe ≥ 1.0 net 10bps |
| 5 | Live 5-day A/B | Exec Analyst + Sarathi | Live WR ≥ 55% |
| 6 | Microstructure v2 | Alpha Hunter | CPCV IC ≥ 0.03 |
| 7 | Drift + champion-challenger | MLOps Sentinel | Synthetic drift catch |
| 8 | (Stretch) FinBERT sentiment | Alpha Hunter | OOS IC stable |

After week 8 → maintenance mode (1 sprint = 1 research item, indefinite).

## Communication Protocol

- **Daily standup:** 15:45 IST automated (post-close). Card at `docs/team/standup/YYYY-MM-DD.md`.
- **Weekly sprint review:** Sunday. Architect presents roadmap progress; Alpha Hunter presents IC trajectory; Exec Analyst presents net-of-cost P&L.
- **Escalation chain:** Drift Watcher → Sarathi → CEO; MLOps Sentinel → Architect → CEO; DQO can self-block engines without approval.

## Sarathi Constants (canonical numbers — anyone reading these must match)

```
SPEC_IC_FLOOR      = 0.05   # Apr-8 master research § 5.5
SPEC_IC_POS_PCT    = 0.60   # ≥60% folds with positive IC
SPEC_PBO_CEILING   = 0.50   # CPCV PBO must be below this
COST_BPS_DEFAULT   = 10     # standard slippage assumption
COST_BPS_STRESS    = 15     # stress test slippage
SHARPE_TARGET_6MO  = 1.5    # CEO-set target (option 1B from synthesis)
```
