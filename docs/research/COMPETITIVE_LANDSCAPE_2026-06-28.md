# TradePilot — Competitive Landscape: Agentic Trading

*Who are our true competitors in fully-automated agentic trading — India & world, mid-2026*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot (autonomous agentic trading) |
| **Report** | Competitive landscape — true agentic peers |
| **Version** | `v1.0.0` |
| **Status** | Complete (Tier-2 / Tier-4 follow-ups in progress) |
| **Created** | 2026-06-28 |
| **Method** | Deep-research harness: 105 agents · 22 sources · 108 claims · 25 adversarially verified (20 confirmed, 5 killed) |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@sidewall.in |

:::

---

## 1. Verdict

TradePilot has genuine **architectural peers** but **no direct head-to-head competitor**. Fully-autonomous agentic trading (research → decide → trade → self-improve) demonstrably exists in 2026, but ~95% of it is **open-source research frameworks and academic prototypes**, not live-money products. The one clear commercial peer (Standard Signal) makes claims that failed verification. No verified peer targets **Indian NSE equities** — that lane is uncontested.

One-line: *We don't have a true competitor — we have a peer group; we're operationally more mature than the research-tier peers and uncontested in our market, but unproven on live capital like almost all of them.*

## 2. Tier 1 — True Agentic Peers

::: {.gap-table}

| System | What it is | Live money? | Verdict |
|:--|:--|:--|:--|
| Standard Signal (YC S26) | "Hedge fund where AI researches + executes every trade end-to-end," RL-trained, auditable | Claim refuted (1-2) | Closest commercial peer; live-trading + Sharpe>3 unaudited founder marketing; "first" is false (Aidyia/Sentient predate by a decade) |
| The Self-Driving Portfolio | ~50 agents, 20+ methods, critique/vote, meta-agent rewrites own code & prompts | No — proof of concept | Most advanced self-improvement found (beyond our learnings store); never deployed live |
| TradingAgents (Apache-2.0) | 4 analysts + bull/bear debate + trader + risk manager | No — simulated exchange | Leading open-source architecture; research-only |
| AI-Trader (HKUDS, MIT) | Agent-native: agents self-register, publish signals, copy-trade | Ambiguous | Active June 2026; real traction unproven |
| FinMem / TradingGroup | Autonomous LLM agents w/ layered memory + self-reflection | No — academic | Confirm our design category is real |
| FinWorld / FinRL | End-to-end financial-AI frameworks/platforms | No — frameworks | Tooling, not self-running products |

:::

Also named in the literature: NoFX, ValueCell, DeepFund, HedgeFundAgents, virattt/ai-hedge-fund (open source), Lumenai (planning an agentic fund), Altbridge.

## 3. The Reality Check (verified, 3-0)

These findings are the most important for gauging real capacity:

::: {.metrics-table}

| Finding | Evidence | Implication |
|:--|:--|:--|
| LLM trading alpha is largely lookahead bias / memorization | Alpha collapses post-training-cutoff (one case: +20.73% in-sample → −1.04% out-of-sample) | Validates our zeroing of ML (IC 0.006) |
| LLM features add little real edge | Removing the LLM dropped Sharpe only 1.40 → 1.14 | Our execution-discipline edge is more defensible |
| Agentic systems are fragile | TradeTrap: "highly vulnerable to perturbation, poor returns, weak risk management" | Robustness/discipline is a moat, not LLM cleverness |

:::

**Key insight:** the global research literature independently confirms the call we already made — most "peers" are chasing LLM alpha the academy says is partly illusory. Our edge living in *execution discipline* (long book, tight brackets, regime-awareness) rather than "AI magic" is the more defensible position.

## 4. Where TradePilot Stands

::: {.gap-table}

| Dimension | TradePilot | Peer field | Standing |
|:--|:--|:--|:--|
| Architecture | Multi-agent, regime-aware, self-improving, A/B engines | Same category | At parity |
| Operational maturity | Daily auto-launch, live watchdogs, 4 live A/B engines | Mostly on-demand sims/backtests | Ahead of research tier |
| Market focus | Indian NSE equities | No verified peer in India | Uncontested |
| Live capital | Paper only | Almost all paper/sim/unaudited | Shared gap |
| Self-modification | Passive (watchdogs + learnings store) | Self-Driving Portfolio rewrites own code | Behind (upgrade path) |
| Audited track record | None yet | Almost none | Shared gap |

:::

## 5. Tier 2 — Indian Retail-Algo Market (resolved)

**Verdict: zero Indian platforms are genuinely agentic.** Every major one is a rule-based strategy builder where the user defines all the logic.

::: {.gap-table}

| Platform | Type | Agentic? | Note |
|:--|:--|:--|:--|
| Zerodha Streak | No-code visual builder | No | Free for Zerodha users since Feb 2024 (commoditized entry tier) |
| Tradetron | Builder + cloud exec + marketplace | No | 11k algos, 1.5M trades/mo, 10+ brokers |
| AlgoTest | Options backtester + deploy | No | ~25k users; "Signals AI" = config assistant |
| QuantMan | Drag-drop indicator builder | No | Rule-based |
| Sensibull | Options analytics + builder | No | 1M+ users; structured picker |
| AlgoBulls Phoenix | Builder + NLP "Copilot" | No (closest) | Copilot translates user intent to code; user still decides |

:::

Closest to agentic: AlgoBulls Copilot (NLP→code) — still the user is researcher + decider. Jarvis Invest (SEBI RA, ₹500cr+ AI portfolio advisory) is a discretionary advisory service, different category. **TradePilot's autonomy-first approach has no direct Indian competitor — a structural, category-level gap.**

## 6. Tier 4 — Live Institutional AI Funds (resolved)

**Every fund with real money keeps a human in the strategy loop — exactly like TradePilot.** "Fully autonomous" language comes only from pre-launch/unverified startups.

::: {.gap-table}

| Fund | Autonomous AI decides? | Live capital? | Verified |
|:--|:--|:--|:--|
| Renaissance, Two Sigma | No — AI is a research/signal tool | Yes | Legit operators; no autonomy claim |
| Numerai | Partial (crowdsourced signals + systematic) | Yes | JPMorgan up to $500M; ~25% net 2024 — closest verified AI-native |
| Altbridge | "Claimed" but FAQ admits human PM verifies | Unconfirmed | Unverified marketing |
| Lumenai | Claimed; humans retain oversight | No — pre-launch (~Jun 2026) | No track record |
| Standard Signal | Claimed end-to-end | Self-reported only | No third-party / SEC verification of live + Sharpe>3 |

:::

## 7. Autonomy Benchmark — TradePilot = T3 (Conditional Autonomy)

No trading-specific L0–L5 standard exists; derived from the Knight Columbia agent-autonomy paper (arXiv 2506.12469). On a T0–T5 scale: **TradePilot = T3** — AI runs the entire intraday loop (research → regime → score → signal → size → execute → EOD) with no human in the loop; humans retain veto only at the *strategy layer*. T4 would require self-modifying strategy params without sign-off (the Self-Driving Portfolio's meta-agent). T3 is the level credible real funds actually operate at.

## 8. SEBI Compliance Summary

Paper trading = **outside the framework entirely** (it regulates exchange orders; we place none). Going live for own capital = **light** (static IP, kill-switch, audit log, ~0.0024 OPS << 10-OPS line, family-account carve-out). Offering to others = **heavy** (SEBI RA license for black-box, exchange empanelment, ISO 27001, biannual VAPT, 6–12 mo). Full detail + checklist in the master roadmap (`docs/ROADMAP_2026-06-28.md`).

## 6. Sources (selected, verified)

- Standard Signal — ycombinator.com/companies/standard-signal (primary)
- The Self-Driving Portfolio — arXiv 2604.02279 (primary)
- TradingAgents — github.com/TauricResearch/TradingAgents; arXiv 2412.20138 (primary)
- AI-Trader — github.com/HKUDS/AI-Trader (primary)
- FinMem — arXiv 2311.13743 (primary); TradingGroup — arXiv 2508.17565 (primary)
- FinWorld — arXiv 2508.02292; FinRL — github.com/AI4Finance-Foundation/FinRL (primary)
- Lookahead bias — arXiv 2512.23847 (NBER); "Blindfolded LLMs" — arXiv 2603.17692 (primary)
- TradeTrap (fragility) — arXiv 2512.02261 (primary)
