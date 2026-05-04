# Naming clarification

Two things are called "v6" right now. This doc fixes that.

| Name | What it is | Lifecycle |
|---|---|---|
| **v6** (the engine) | Paper-trading experiment shipped 2026-04-28 EOD. "v4 raw signals + Track A bolt-on." Lives in `scripts/v6-paper-trade.py`. One of 6 engines running on the laptop. | Experiment. Will be retired or promoted at the May-25 statistical gate. |
| **v6.1** (this roadmap) | The full production system from the April 12 master plan, refreshed with everything we've learned and shipped since then. The cloud-hosted, multi-broker, optionally autonomous TradePilot. | Roadmap. 9-12 months from today to public launch. |

**From here on:** "v6" always means the paper-trading engine. "v6.1" always means the production system.

---

# Where we actually are tonight

A clean snapshot before we plan forward.

## Engines in observation (6 active)

| Engine | Role | Edge being tested |
|---|---|---|
| v4 | Control. Raw v4 composite scorer, LONG-only. | Baseline. 04-28 made +Rs 26,179 (71% WR). |
| v5 (Fix #1) | v5 wrapper + tonight's Fix #1. | Does Fix #1 close the gap to v4? |
| v5_classic | Baseline v5 with no Track A. | Confirms Track A's contribution. |
| v5_6 | v5 + Darvas Box overlay. | Independent variant. |
| v5_7 | v5 + Intraday Box overlay. | Independent variant. |
| v6 | v4 raw + Track A bolt-on. | Cleanest test of Track A's marginal value. |

## What's already shipped

| Layer | Status |
|---|---|
| Multi-engine paper trading framework | Live, 6 engines, daily reports |
| Track A defensive layer (cost modeling, RE-ARM, SHORT_BLOCK, FLAT_EXIT) | Shipped 2026-04-27 |
| Fix #1 (SHORT requires absolute weakness) | Shipped 2026-04-28 |
| ML staging + 4-gate promotion system | Shipped — no model auto-promotes to production |
| Crash watchdog | Shipped — auto-restart, market-hours-aware |
| Telegram digest (2-hour cadence) | Shipped |
| Laptop heartbeat (15-min) | Shipped |
| Auto-stop-EOD (15:35) | Shipped |
| Daily watchdog learning insights | Shipped |
| LaunchAgent for Monday weekly tracker | Shipped |
| LaunchAgent for tomorrow's EOD comparison | Shipped tonight |
| Statistical gate doc (deflated Sharpe + 95% CI) | Live in `docs/IMPLEMENTATION_BRIEF_2026-04-27.md` |
| Threat surface analysis (1,597 lines) | Live in `docs/security/TRADEPILOT_V6_LIVE_TRADING_THREAT_ANALYSIS.md` |
| Competitive analysis (Zerodha, Groww, Streak, Sensibull, etc.) | Live in `docs/research/competitive-analysis.md` |

## Where the original April 12 plan put us

> "Phase 1: Foundation, Weeks 1-4. Make it work."

Reality: We are at session ~14 of 20-session paper validation. Track A (which wasn't in the original plan) ate the last 4 weeks and was correct to do so. **Phase 1 is ~80% complete.** Phases 2, 3, 4 are unchanged from the original plan.

---

# The four-phase staircase (v6.1, refreshed)

Original plan had 20 weeks. Reality says 36-40 weeks across 4 phases. Here's the honest version:

## Phase 1 — Foundation ("make it work")

Goal: prove on paper that at least one engine produces statistically significant alpha.

| Item | Original (Apr 12) | Refreshed (Apr 29) | Status |
|---|---|---|---|
| Paper trading framework | Build | Built (multi-engine) | Done |
| 20-session validation | 4 weeks | 4-week observation window through 2026-05-25 | In progress |
| ML model with proper training | Foundation | Done (LightGBM, best_iter ≥ 100 guardrail, atomic promote) | Done |
| Track A defensive layer | Not in plan | Shipped — 4 fixes | Done (added April 27) |
| Statistical gate (Sharpe + CI) | Not in plan | Lopez de Prado deflated Sharpe + 95% CI methodology | Methodology defined, awaiting data |
| Cross-asset signals (bonds, crude, USD/INR) | Foundation | Deferred to Phase 2 | Not started |
| Shoonya account for historical data | Foundation | Deferred — not needed for current observation | Optional |

**Exit criteria for Phase 1 → Phase 2:** At the May 25 gate, at least ONE engine must show a deflated Sharpe ≥ 1.0 with 95% CI lower bound > 0 over the 20-session window. If yes, that becomes our base engine. If no, we extend observation by 4 more weeks and revisit.

**Time remaining in Phase 1:** ~4 weeks (through May 25, 2026).

## Phase 2 — Intelligence ("make it smart")

Goal: layer additional alpha sources on top of the winning Phase 1 engine.

| Item | Original (Apr 12) | Refreshed (Apr 29) |
|---|---|---|
| LLM sentiment layer (Claude API for news) | Yes | Yes — but only if Phase 1 base engine alone falls below Sharpe 1.5 |
| FII/DII institutional flow signals | Yes | Yes — public data, Rs 0 cost |
| Insider buying clusters from SEBI filings | Yes | Yes — public data |
| Pairs trading (cointegrated Nifty 200 pairs) | Yes | Yes — separate strategy pool |
| Options strategies (premium harvesting) | Yes | Defer to Phase 3 — too risky to layer with equity in early Phase 2 |
| Multi-agent orchestrator | Yes | Soft-yes — only if monolithic loop becomes the bottleneck |

**Time:** 8 weeks (May 26 → July 21, 2026).

**Exit criteria for Phase 2 → Phase 3:** Combined system (base engine + 2-3 alpha layers) shows Sharpe > 1.5, max drawdown < 12%, win rate > 60% on a fresh 30-session paper window.

## Phase 3 — Execution ("make it real")

Goal: connect to a real broker, execute real orders with real money — but tiny size and hard kill switches.

| Item | Original (Apr 12) | Refreshed (Apr 29) |
|---|---|---|
| Open Zerodha Kite Connect dev account | Yes | Yes — Rs 2,000/month, apply during Phase 2 |
| Build Kite execution agent | Yes | Yes — separate microservice with audit log |
| Smart order routing (limit vs market) | Yes | Yes |
| **Shadow mode (log orders, do not execute)** | Yes — 2 weeks | **Yes — extended to 4 weeks.** This is the most important step in the entire plan. |
| SEBI algo registration via Kite | Yes — 2-4 weeks | **OPEN — needs fresh SEBI April 2026 rules research.** Different from RIA. |
| Kill switch + audit trail | Yes | Yes — daily, weekly, monthly loss caps with hard auto-halt |
| Move from laptop to AWS Mumbai | Yes (ap-south-1) | Yes — same VPC as Kite servers for sub-50ms latency |
| Live with 1 lot | Yes — 2 weeks | **Yes — extended to 4 weeks. No exceptions.** |

**Time:** 12 weeks (July 22 → October 13, 2026).

**Exit criteria for Phase 3 → Phase 4:** 4 weeks live with 1 lot, no catastrophic incidents, real-money Sharpe within 1 standard deviation of paper Sharpe (this proves paper-to-live transfer worked).

## Phase 4 — Scale ("make it bigger")

Goal: scale capital, add second-order features, prepare for public-facing offering.

| Item | Original (Apr 12) | Refreshed (Apr 29) |
|---|---|---|
| Scale 1 lot → full personal capital | Yes | Yes — over 4-6 weeks, 25/50/75/100% ladder |
| Grafana real-time P&L dashboard | Yes | Yes — separate from paper-trading dashboard |
| Commodities (gold, crude) | Yes | Soft-yes — only if equity engine plateaus |
| Currency hedging (USD/INR) | Yes | Defer — adds complexity without clear edge |
| Tax optimization (STCG/LTCG awareness) | Yes | Yes — automated booking |
| **Public API for subscribers** | Yes | **OPEN — depends on SEBI RIA license decision (separate workstream)** |

**Time:** 16 weeks (October 14, 2026 → February 2, 2027).

---

# Decision gates (statistical, not vibes)

The gates are what stop us from "feeling like" the system is ready and shipping it anyway.

| Gate | Date | What we measure | What passes |
|---|---|---|---|
| **G1** | 2026-05-25 | Phase 1 → Phase 2 | At least one engine: deflated Sharpe ≥ 1.0, 95% CI lower bound > 0, 20+ trading days |
| **G2** | 2026-07-21 | Phase 2 → Phase 3 | Combined system: Sharpe > 1.5, max drawdown < 12%, win rate > 60%, 30+ trading days fresh post-Phase-1 |
| **G3** | 2026-08-31 | Shadow mode → Live with 1 lot | 4 weeks of shadow mode with zero divergence between predicted and would-have-been-actual fills |
| **G4** | 2026-10-13 | 1 lot → Full personal capital | 4 weeks live: real-money Sharpe within 1 SD of paper Sharpe; zero unauthorised orders; zero kill-switch overrides |
| **G5** | 2027-Q1 | Personal → Public | Determined separately by SEBI license + 6+ months of audited live track record |

If any gate fails, we extend that phase. We do not skip gates.

---

# Production architecture (v6.1)

Refreshed from the April 12 master plan. The core idea is unchanged: separate **signal generation** from **risk management** from **execution** from **portfolio construction**. Each is its own service, each is independently testable.

## Service map

```
                    ORCHESTRATOR (master agent)
                          |
     +----------+---------+---------+-----------+
     |          |         |         |           |
  SIGNAL    SIGNAL    SIGNAL    RISK       EXECUTION
  Technical Sentiment Flow      AGENT      AGENT
  Agent     Agent     Agent     |          |
     |          |         |         |           |
     +----------+---------+         |           |
                |                   |           |
            FUSION                  |           |
            LAYER                   |           |
                |                   |           |
                +-------------------+-----------+
                                    |
                              PORTFOLIO
                              AGENT
                                    |
                              KITE API
                              (live broker)
                                    |
                              NSE / BSE
```

## What each service does

| Service | Job | What goes wrong if it fails |
|---|---|---|
| **Orchestrator** | Coordinate all agents, manage state, hold the global kill switch | Whole system halts safely (correct behaviour) |
| **Technical signal agent** | LightGBM composite scorer + Track A rules (this is v5/v6 today) | Lose primary alpha source — fall back to no-trade |
| **Sentiment signal agent** | Claude API news scoring (Phase 2) | Lose secondary alpha — degrade to technical-only |
| **Flow signal agent** | FII/DII + insider + delivery % (Phase 2) | Lose tertiary alpha — degrade gracefully |
| **Fusion layer** | Combine signals into a single decision per stock | Single point of failure — needs heavy testing |
| **Risk agent** | Regime detect, VIX size, kill switches, correlation guard | Hard halt on breach — never override |
| **Execution agent** | Submit orders to Kite, smart routing, retry, audit | Order failures logged, alerted, manual recovery |
| **Portfolio agent** | Multi-strategy allocation, Kelly sizing, rebalance | Holds the actual book of record — never deletes positions |

## Hosting

| Layer | Choice | Why |
|---|---|---|
| Compute | AWS Mumbai (ap-south-1) | Same region as Kite servers — sub-50ms latency, SEBI data residency |
| Hot DB (ticks) | QuestDB | Fastest tick ingestion, ASOF JOIN, time-series native |
| Analytics DB | DuckDB + Parquet | Zero infra cost, columnar, plenty fast for our scale |
| Object store | S3 (Mumbai region) | Backups, model artifacts, historical Parquet |
| Secrets | AWS Secrets Manager | Kite tokens, API keys, never on disk in plaintext |
| Monitoring | Grafana + CloudWatch + Telegram | 3 layers: deep dive, native, instant alert |
| CI/CD | GitHub Actions → AWS | Auto-deploy from `main`, manual gate for production |

---

# Tech stack (locked-in)

| Concern | Tool | Cost (monthly, INR) |
|---|---|---|
| Live execution broker | Zerodha Kite Connect | Rs 2,000 |
| Tick data | Kite WebSocket (3,000 instruments) | Included |
| Historical data download | Shoonya (Finvasia) free API | Rs 0 |
| ML training | LightGBM + neuralforecast (TFT/LSTM) | Rs 0 |
| LLM sentiment | Claude API (Anthropic) | ~Rs 4,000 |
| Backup local LLM | Llama 3.1 via Ollama | Rs 0 |
| Hot DB | QuestDB (self-hosted on EC2) | included in compute |
| Analytics | DuckDB + Parquet | Rs 0 |
| Cloud compute | AWS EC2 t4g.large + EBS gp3 | ~Rs 6,000 |
| Storage | S3 + lifecycle to Glacier | ~Rs 500 |
| Monitoring | Grafana Cloud (free tier) → paid | Rs 0 → Rs 2,000 |
| Telegram bot | Free | Rs 0 |
| Domain + SSL | Cloudflare | Rs 100 |

**Phase-by-phase monthly cost (INR):**

| Phase | Items | Monthly |
|---|---|---|
| Phase 1 (now) | Laptop + Telegram | ~Rs 0 |
| Phase 2 | Cloud paper + Claude API + Shoonya | ~Rs 8,000 |
| Phase 3 | Above + Kite API + AWS Mumbai + Grafana paid | ~Rs 18,000 |
| Phase 4 | Above + scaled compute + monitoring | ~Rs 30,000 |

These are pre-revenue costs. Revenue model in section 9.

---

# Risk rules (non-negotiable)

These come from the April 12 plan and are unchanged. They are the load-bearing safety layer.

| Rule | Limit | Why |
|---|---|---|
| Daily max loss | 2% of capital | Survive any single bad day |
| Weekly max loss | 5% of capital | Survive any bad week |
| Monthly max loss | 10% of capital | Kill switch trigger — pause all trading |
| Single position max | 10% of capital | Concentration risk |
| Max F&O leverage | 3x | Survive a 30% gap-down |
| Max correlated positions | 3 from same sector | Survive a sector blowup |
| Kill switch | Auto-fire at -2% daily | Hard stop. No override. |
| Recovery ladder after kill switch | 25 / 50 / 75 / 100% over 15 days | Don't revenge-trade |
| Order size validation | Reject if > 2% of capital OR > 5x average position | Catch fat-fingers + bugs |
| Pre-trade sanity check | Reject if price > 3 SD from VWAP in last 5 min | Catch quote-stuffing / market-manip windows |

**The kill switch is the single most important piece of code in the system.** It is tested in every CI run. It cannot be silenced by any other agent. If it fires, only manual intervention with a 24-hour cooldown can restart trading.

---

# Compliance — the gate before we open to others

This is the section that changes everything else. Three regulatory regimes, three different obligations.

| Regime | Who needs it | What it lets us do | What it costs |
|---|---|---|---|
| **Personal trading** | Anyone | Trade your own money via your own broker, automated or manual. No license needed. | Rs 0 |
| **SEBI algo trading registration (broker-side)** | Anyone running automated orders through a broker | Register the algo strategy with the broker, who registers with the exchange. **April 2026 SEBI rules tightened this.** Needs fresh research. | TBD — likely Rs 0 to Rs 50K |
| **SEBI Registered Investment Adviser (RIA)** | Anyone giving paid investment advice to non-related third parties | Charge subscribers for signals, recommendations, or advisory services | Rs 5 lakh net worth + NISM XA + XB exams + ~3 month process. ~Rs 50K total fees |

## What this means for v6.1's roadmap

| Phase | Compliance posture | Allowed |
|---|---|---|
| Phase 1, 2 (paper) | None needed | Paper trade, write blog posts, share own results in journal form |
| Phase 3 (shadow + live with 1 lot, personal) | SEBI algo registration via Kite | Trade your own money automated |
| Phase 4 personal scale | Same | Trade more of your own money |
| **Phase 4+ public** | **RIA license required** | Take subscribers, send paid signals, charge for access |

**Decision needed by July 2026:** Do we apply for the RIA license or stay personal-only? If RIA, application starts in parallel with Phase 2 work because it takes ~3 months and blocks public launch. A separate compliance doc is the next deliverable after this one.

---

# Threat surface (already documented in detail)

A 1,597-line analysis already exists at `docs/security/TRADEPILOT_V6_LIVE_TRADING_THREAT_ANALYSIS.md`. The categories:

| Category | What's covered |
|---|---|
| Kite API security | Token theft, session hijack, rate limit abuse, key vs secret vs access token danger ranking |
| Financial threats | Rogue orders, flash crash, double ordering, market manipulation rules, slippage |
| Network | MITM, DNS hijack, SSL pinning, VPN, internet drop mid-trade |
| Infrastructure | SSH compromise, DDoS, DB corruption, power failure, clock sync |
| Quantum | Harvest-now-decrypt-later (long-term) |

For v6.1 production launch, every Phase 3 item must reference its corresponding threat category and demonstrate a control. **No code goes live without a paired threat-mitigation entry.**

---

# Revenue model (Phase 4+, contingent on RIA)

From the April 12 plan, refreshed.

| Tier | Price (INR/month) | What they get | Volume target Y1 |
|---|---|---|---|
| Free | Rs 0 | Market data, basic signals, paper trading sandbox | 10,000 |
| Pro | Rs 999 | Full signals, regime alerts, Telegram bot | 500 |
| Algo | Rs 4,999 | API access, auto-execution via their own Kite, all strategies | 50 |
| Enterprise | Custom (>Rs 25K) | White-label, dedicated support, custom strategies | 5 |

**Revenue projection (Year 1 post-RIA launch):**

| Tier | Users | MRR | Annual |
|---|---|---|---|
| Free | 10,000 | Rs 0 | Rs 0 |
| Pro | 500 | Rs 5,00,000 | Rs 60 lakh |
| Algo | 50 | Rs 2,50,000 | Rs 30 lakh |
| Enterprise | 5 | Rs 1,25,000 | Rs 15 lakh |
| **Total** | **10,555** | **Rs 8.75 lakh MRR** | **Rs 1.05 Cr ARR** |

This is a conservative re-scoping. The April 12 plan said Rs 20L MRR; that assumed faster ramp. Year 1 we hit Rs 8.75L MRR. Year 2 target is Rs 25L MRR.

---

# Risk register (SWOT-style)

| Risk | Category | Mitigation |
|---|---|---|
| Insufficient sample at May 25 gate (no engine crosses Sharpe 1.0) | Statistical | Extend observation window 4 weeks. Do not lower the bar. |
| SEBI April 2026 rules disqualify our algo registration | Regulatory | Compliance doc due first week of May with full rule reading + workaround paths |
| Kite API outage during a signal-fire window | Technical | Smart order router with automatic retry + halt-on-stale-quote; documented incident at competitive-analysis.md:125 |
| Streak / Sensibull copy our edge once visible | Competitive | Multi-layer alpha (Phase 2) + execution moat (sub-50ms) — they can't easily replicate |
| Solo founder bandwidth (Soumya also runs DevPilot + Sidewall) | Personal | Strict no-engine-changes-mid-day rule, MindPilot framework cadence, automation everywhere |
| ML model degrades silently (alpha decay) | ML | 4-gate promotion + rolling 5-day IC tracking + auto-alert if IC turns negative |
| Real-money Sharpe diverges from paper Sharpe (transaction cost surprise) | Live transition | 4-week shadow mode + 4-week 1-lot live before scaling |
| Kill switch bug | Catastrophic | Daily CI test + manual quarterly drill |

---

# Today's actionable checklist (next 4 weeks)

Concrete items between now and the May 25 gate.

| Item | Owner | When | Status |
|---|---|---|---|
| Continue 6-engine observation window | Engines (auto) | Daily through 2026-05-25 | Active |
| Watch for Fix #1 firing pattern in v5 logs | Soumya | Daily | Pending |
| Watch v6 vs v4 head-to-head | Soumya | Daily via auto EOD report | Pending |
| Read SEBI April 2026 algo trading rules | Soumya / Claude (research agent) | First week of May | Not started |
| Write compliance roadmap doc (the "B" option) | Claude | Week of May 5 | Pending |
| Apply for Zerodha Kite Connect dev account | Soumya | After May 25 gate passes | Blocked on G1 |
| Start drafting Kite execution agent code | Claude | After May 25 gate passes | Blocked on G1 |
| Open Shoonya account (for historical data download) | Soumya | Phase 2 entry | Optional |
| Set up AWS Mumbai account + IAM | Soumya | Phase 3 prep | Not started |
| RIA license decision | Soumya | By July 2026 | Open |

**Today's gate before doing any of this: does the May 25 statistical test pass?** Everything downstream depends on at least one engine crossing the Sharpe-1.0 / CI-positive bar.

---

# Reference docs index

The supporting material for this roadmap, in priority order.

| Doc | Use it for |
|---|---|
| `docs/IMPLEMENTATION_BRIEF_2026-04-27.md` | Statistical gate methodology, Track A spec, ML promotion gates |
| `docs/security/TRADEPILOT_V6_LIVE_TRADING_THREAT_ANALYSIS.md` | Every Phase 3 security control |
| `docs/research/2026-04-12_v6_master_plan.md` | The original v6 master plan (this doc supersedes it) |
| `docs/research/competitive-analysis.md` | Competitor moats, Kite outage history, SEBI rule context |
| `docs/learning/2026-04-28-eod-summary.md` | The v4 vs v5 RCA that motivated Fix #1 and v6 |
| `docs/learning/2026-04-29-v5-vs-v6-experiment.md` | Tomorrow's experiment design + decision matrix |
| `docs/observation_journal.md` | Daily observation log through May 25 |
| `docs/RETIRED_ENGINES.md` | Why engines were retired (and why some came back) |

---

# One-line summary

**v6.1 is a 36-40 week journey from today's 6-engine paper trading laptop setup to a public-facing, SEBI-compliant, multi-broker production system. We are 80% through Phase 1. The May 25 statistical gate is the next decision point. Nothing ships to live trading until at least one engine crosses Sharpe 1.0 with a positive 95% CI lower bound.**
