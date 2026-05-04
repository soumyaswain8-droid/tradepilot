# Research Agent Brief — 2026-05-04 (Mon)

**Purpose**: SEBI April 2026 algo trading rules + v6.1 paper-trading feasibility check.

**Triggered by**: User request 2026-04-29 evening, scheduled cron + this fallback brief.

**If the cron doesn't fire on Monday morning**: paste the prompt below into a fresh
Claude session in this project to manually trigger the agent.

---

## Background context

Soumya is building TradePilot, currently in 6-engine paper trading observation
window through 2026-05-25. The roadmap doc at
`docs/reports/2026-04-29/PRODUCTION_ROADMAP_v6.1.md` describes the path from
today's laptop paper trading to a SEBI-compliant multi-broker production system
over 36-40 weeks.

This research agent's job is to fill in two gaps in the roadmap that need fresh
investigation: SEBI's April 2026 algo trading rule changes and the practical
mechanics of paper-trading the full v6.1 multi-agent architecture before live
money flows.

---

## Agent prompt (paste into Claude)

```
Research agent task. Working directory: /Users/soumyaswain/Documents/tinker/projects/tradepilot.

Two deliverables, both due as MD + PDF in docs/reports/2026-05-04/.

=== DELIVERABLE 1: SEBI Compliance Roadmap ===

Pull SEBI's April 2026 algo trading rules. Use WebSearch + WebFetch as needed.
Cover:
- What changed in April 2026 vs the previous algo trading regime
- Categories of algo registration (broker-mediated vs self-registration vs
  proprietary vs third-party advisory)
- Capital / net-worth requirements per category
- Broker registration vs SEBI Registered Investment Adviser (RIA) — when each
  is needed for our path: personal -> public advisory
- NISM XA + XB exam requirements + costs + timeline
- Process to register an algo with Zerodha Kite specifically (their dev portal
  + SEBI side)
- Relationship to Phase 3 of v6.1 roadmap (live trading with Kite, 1 lot then
  scale)
- Decision matrix: when do we apply for what, in what order, with what
  prerequisites
- Cost summary in INR (registration fees, exam fees, ongoing costs)
- Timeline summary (week-by-week from application to clearance)

Write to: docs/reports/2026-05-04/COMPLIANCE_ROADMAP.md

Render PDF using Pyppeteer pattern from docs/reports/2026-04-29/render_pdf.py
(NEVER WeasyPrint per memory). Copy that file as a starting point, change
input/output paths and cover content. Keep the green theme since this is a
v6.1 follow-on doc.

=== DELIVERABLE 2: v6.1 Paper Trading Feasibility ===

Question: can the full v6.1 production architecture (multi-agent: Orchestrator
+ 4 signal agents + Risk + Execution + Portfolio, hosted on AWS Mumbai,
connected to Kite API) be operated in PAPER mode end-to-end, before Phase 3
commits real money?

Investigate:
- Does Zerodha Kite Connect provide a sandbox / paper-trading API endpoint?
  (Check kite.trade docs, GitHub issues, kiteconnect Python library)
- If not, what's the standard pattern: build a "paper trading mode" flag in
  the execution agent that intercepts orders before submission and books
  synthetic fills against the live tick stream? Document the architecture.
- Are there existing open-source frameworks that paper-trade against live tick
  data at production scale? Specifically check: zipline, vectorbt, lean
  (QuantConnect), backtrader, freqtrade. Note which support Indian markets +
  Kite integration.
- What's the right test pattern for the multi-agent fusion layer (which is
  novel) — can we replay historical days through it without committing fills?
- Identify if "shadow mode" (the 4-week step in Phase 3 of v6.1) maps to an
  existing pattern or is something we need to build from scratch.
- Recommendation: how should v6.1 Phase 2 (Intelligence) and Phase 3 prep
  (shadow mode) be structured to maximise paper-trading coverage of the full
  system before any real money flows?

Write to: docs/reports/2026-05-04/V6.1_PAPER_TRADE_FEASIBILITY.md

Render PDF using same Pyppeteer pattern.

=== CONSTRAINTS ===

- Maximum runtime: 20 minutes for the whole job. Use Bash timeout: 1200000 on
  long commands.
- Do NOT use sleep-poll loops.
- WebSearch / WebFetch limit: 12 calls total across both deliverables.
- For DELIVERABLE 1 prefer official SEBI source (sebi.gov.in / nseindia.com /
  bseindia.com) for the rule text; cross-check with livemint, economictimes,
  moneycontrol, capitalmind.in.
- For DELIVERABLE 2 prefer broker docs (kite.trade developer portal, GitHub
  for OSS frameworks).
- Each deliverable: one MD + one PDF. PDFs must be rendered via Pyppeteer.

=== AFTER COMPLETION ===

1. Append a brief summary to docs/observation_journal.md with both file paths
   and the headline finding from each deliverable (one-line each).
2. Send a Telegram message via the .env TELEGRAM_BOT_TOKEN +
   TELEGRAM_CHAT_ID:
   "Research agent done. Compliance: <one line>. Paper-feasibility:
   <one line>. Files: docs/reports/2026-05-04/*.pdf"
3. Open both PDFs in Finder for Soumya's review.
```

---

## Files this agent should produce

| File | Format |
|---|---|
| `docs/reports/2026-05-04/COMPLIANCE_ROADMAP.md` | Markdown |
| `docs/reports/2026-05-04/COMPLIANCE_ROADMAP.html` | Rendered HTML |
| `docs/reports/2026-05-04/COMPLIANCE_ROADMAP.pdf` | Pyppeteer PDF |
| `docs/reports/2026-05-04/V6.1_PAPER_TRADE_FEASIBILITY.md` | Markdown |
| `docs/reports/2026-05-04/V6.1_PAPER_TRADE_FEASIBILITY.html` | Rendered HTML |
| `docs/reports/2026-05-04/V6.1_PAPER_TRADE_FEASIBILITY.pdf` | Pyppeteer PDF |

---

## Why these two specifically

The v6.1 production roadmap (`docs/reports/2026-04-29/PRODUCTION_ROADMAP_v6.1.md`)
flagged these two as "OPEN" / needing fresh research:

1. **Compliance gate** — Section 7 of the roadmap. SEBI's April 2026 rule
   changes are referenced in the competitive analysis but not yet read in
   detail. This is the gate that decides whether v6.1 can ever be public-facing.

2. **Paper-trading the multi-agent system** — Phases 1 and 2 of v6.1 are
   paper-only by design, but the *mechanics* (how do you paper-trade a
   multi-agent system that uses live Kite ticks?) aren't specified. Soumya
   asked specifically whether this is feasible.

Both are blockers for Phase 3 planning. Both are research-only (no code
changes). Both should be solvable by a single agent in one session.
