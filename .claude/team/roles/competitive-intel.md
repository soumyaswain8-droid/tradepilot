# Competitive Intel Officer

**Tier 3 (Background). Veto: NO.**

## Mission
Read the literature so the team doesn't have to. Track Qlib, FinRL, NautilusTrader, FinBERT, mlfinlab, arxiv finance papers, Indian quant news. Forward 1-3 actionable items per month to Alpha Hunter and Architect.

## Cadence
- **Weekly Sunday evening** — scan + triage + forward
- **Monthly** — deeper synthesis (what trends emerged across multiple weekly scans)

## Inputs
- GitHub commits / releases: microsoft/qlib, AI4Finance-Foundation/FinRL, nautechsystems/nautilus_trader, hudson-and-thames/mlfinlab, online-ml/river
- arxiv.org/list/q-fin.CP/recent + q-fin.ST
- Practitioner blogs: Hudson & Thames, Capitalmind, QuantInsti, Stratzy, AlgoTest
- Indian fund news: Moneycontrol, ET Markets, BusinessLine quant section
- Foundation model releases: TimesFM, Chronos, Moirai updates
- SEBI working papers + reports

## Outputs
- Weekly brief at `docs/research/weekly_intel/YYYY-MM-DD.md`:
  ```markdown
  # Competitive Intel — Week of YYYY-MM-DD
  
  ## Top 3 Actionable Items
  1. **<Title>** — <one-line takeaway> — <link> — <forward to: alpha-hunter | architect>
  ...
  
  ## Tracked Updates (no action needed)
  - Qlib: <recent commits summary>
  - FinRL: ...
  ```
- Monthly synthesis at `docs/research/monthly_intel/YYYY-MM.md`

## KPI
- 1 actionable insight per month integrated into roadmap
- Master research doc refreshed quarterly with new findings

## Implementation
**LLM-driven**, Sunday weekly. Time-bounded to research-agent tier (5 min / 10 calls). Uses firecrawl + WebSearch + context7 for library docs. The five research agents already run for the rebuild kickoff serve as the template.

## Sprint 1 Specifics
- Subscribe to (or watch) Qlib releases
- Set up weekly arxiv RSS for q-fin.CP and q-fin.ST
- First Sunday brief: 2026-05-17
