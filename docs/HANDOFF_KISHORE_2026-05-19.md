# TradePilot — Project Snapshot & Research Handoff

**For:** Kishore
**From:** Soumya Swain
**Date:** 2026-05-19
**Status:** Active rebuild · Sprint 1 closed · Sprint 2 next week
**Repository:** local at `~/Documents/tinker/projects/tradepilot/`

---

## TL;DR — What This Is

TradePilot is an **Indian intraday equity paper-trading platform** with an ML-driven signal layer and a rule-based execution layer. We trade Nifty 500 stocks on simulated ₹10L capital per engine. The thesis: 93% of Indian retail F&O traders lose money (SEBI 2024) — we're building the institutional-grade machinery to land in the profitable 7%.

We are **mid-rebuild**. The platform was making money in April. A silent model regression on May 13 broke it. We diagnosed the cause, restored a working model, hardened the safety system to prevent recurrence, and laid out an 8-week rebuild path. We're at the start of week 2.

**What I need from you:** scan the internet and GitHub for existing tools, frameworks, papers, and case studies that overlap with what we're building. We may be reinventing wheels; we may be missing leverage. Bring back findings, not opinions.

---

## 1. The Problem We're Solving

**Indian equity intraday is one of the cruelest markets for retail.** SEBI's 2024 study (1.13 crore traders, FY22–FY24): 93% lose money, aggregate losses ₹1.8 lakh crore over 3 years. The top 1% (those who made > ₹1L profit) had win rates of 50–55% and net Sharpe of 0.8–1.3.

The bleed comes from four places:

1. **Slippage** — 5–15bps per round-trip on Nifty 200–500 names eats most edge before alpha shows up.
2. **Overfitting** — backtest Sharpe of 2+ collapses to 0.3–0.6 live.
3. **Signal decay** — popular strategies stop working as more people run them.
4. **Cost asymmetry** — STT 0.025% sell-side compounds across 50–100 trades/day.

A serious quant fund (Quantbox, Tower India, etc.) achieves Sharpe 2.5–4 net. The realistic retail-algo ceiling, without paid data, is around Sharpe 1.0–1.5 net.

**Our target: Sharpe 1.5 net of 10bps in 6 months.** That puts us in the top-1% retail cohort, not at quant-fund parity.

---

## 2. What We Built

### 2.1 The Engine Zoo (now consolidated to 3)

| Engine | Role | Status |
|---|---|---|
| **v4** | Pure-Python LightGBM signal scorer. Direct execution. Our control. | Active |
| **v5** | Multi-pool, regime-aware, multi-horizon. Calls v4 scorer under the hood. Adds Track A rules (re-arm, bullish gate). Uses Rust risk layer. | Active (rebuild target) |
| **v5_classic** | A frozen v5 baseline. No Track A rules. No Rust. Used as A/B reference. | Active |
| ~~v5_2, v5_3, v5_4, v5_5, v5_6, v5_7, v5_8, v6~~ | Experimental variants — Darvas box breakout, mean-reversion, slot-partition off, raw-v4-with-track-A. | **Retired 2026-05-15** (scripts preserved, can revive post-rebuild). |

The retired engines explored alternative strategies. None survived as standalone winners in the May-13 regression. The consolidation was a focus play, not a verdict on those strategies.

### 2.2 The ML Layer

**Model:** Single LightGBM regressor (gradient boosted decision trees).
- 22 features (RSI, VWAP, ATR, MACD, gap, prev-day range, sector RS, FII/DII, VIX, etc.)
- Target: raw intraday return `(close_15:00 − open_09:30) / open_09:30`
- Training: walk-forward, 1-year window, 1-month test, 5-day embargo, 16 folds
- Current measured walk-forward IC: **0.0054** (project spec demands ≥ 0.05)

**The IC problem is the whole rebuild story.** Microsoft Qlib's published benchmarks show the same LightGBM family on a properly-engineered feature set (Alpha158) hits IC ≈ 0.045 on Chinese equity. We're at 1/9th of that. The gap is **features and labels**, not the model.

### 2.3 The Rules Layer (Track A)

Three rules added 2026-04-28 that work like sanity gates around the model:

| Rule | What it does |
|---|---|
| `BULLISH_PREMARKET_SHORT_BLOCK` | If pre-market is bullish + gap-up > 0.5%, suppress all SHORT signals for first 60 min. Prevents the BEAR-regime SHORT cascade. |
| `WINNER_RE_ARM` | When a position exits on TARGET, mark stock re-armable (up to 3 re-entries/day same direction). This is the cluster-day amplifier — what made April-22 a +₹61k day. |
| `TIME_EXIT_TIGHTENING` | At 13:30 IST, force-exit any position with `|unrealized_pnl%| < 0.3%`. Frees capital. |

Track A is well-understood and works. It's NOT what the rebuild changes.

### 2.4 The Rust Execution Layer

A Rust service on `localhost:8080` providing:
- `/api/execute` — signal validation
- `/api/risk` — daily DD + kill-switch state
- `/api/positions` — open + closed positions
- `/sync_positions` — state coherence with engines

**Currently optional.** v4 doesn't call it. v5 family imports `rust_bridge` with try/except fallback. If Rust is down, engines lose risk-state coherence but keep trading. We may strip it in Sprint 5+ as cleanup; not load-bearing.

### 2.5 Safety + Audit (Sarathi)

A 5-rule-family verification system enforced at multiple gates:

| Family | Trigger | Veto |
|---|---|---|
| `SARATHI-LRN` | Every learning written to DevPilot DB | Rejects unverified claims |
| `SARATHI-SPR` | Sprint open / close / task transitions | Blocks sprint close without evidence |
| `SARATHI-ML` | Every model retrain candidate | **THE MAY-13 FIX** — blocks model promotion if OOS IC < champion or < spec floor |
| `SARATHI-CDE` | Engine code commits + launches | Blocks startup if pre-flight fails |
| `SARATHI-DAT` | Data feed pre-market, intraday, post-close | Refuses engine start on poisoned feed |

Every gate decision goes to an append-only JSONL audit log (`docs/team/audit/YYYY-MM-DD.jsonl`). Immutable. Searchable from the dashboard.

### 2.6 The Permanent Agent Team (10 roles)

We run a "quant desk" model — separation of duties, named roles with vetoes, daily/weekly cadences. Some are scripted (cron-like); some are LLM-driven (invoked when relevant).

| Role | Tier | Veto | Function |
|---|---|---|---|
| Soumya (CEO) | 1 | Absolute | Final approver |
| Sarathi (CRO) | 1 | Yes (5 rule families) | Verification authority |
| Architect (Head of Eng) | 1 | Yes (code merges) | Roadmap owner |
| Alpha Hunter (Research) | 2 | No | Weekly IC audit, feature recommendations |
| MLOps Sentinel | 2 | Yes (model promotion) | Runs IC gate, CPCV, champion-challenger |
| Execution Analyst | 2 | Sizing recos | Slippage, net-of-cost P&L |
| Drift Watcher | 3 | Pages Sarathi | Live IC + ADWIN |
| Data Quality Officer | 3 | Yes (data block) | Feed integrity 09:00/11:00/15:30 |
| Competitive Intel | 3 | No | Weekly research scans |
| Knowledge Archivist | 4 | No | Standup cards, PDFs, learnings to DB |

### 2.7 The Automation

The entire trading day runs without human touch:

| IST | Job | What |
|---|---|---|
| 08:45 | `pmset wake` | Mac wakes |
| 08:50 | `preflight` | 27-check self-test |
| 08:55 | `DAT pre-market` | Feed integrity |
| 09:10 | `engines-on` | DAT launch-gate → launch-market.sh (3 engines + Rust + Flask + watchdog + caffeinate) |
| 09:15 | NSE opens | Engines trade |
| 11:00 | `DAT mid-market` | Feed check |
| 15:31 | `exec-eod` | Slippage aggregate |
| 15:35 | `auto-stop-eod` | Engines killed cleanly |
| 15:50 | `standup` | Daily summary card written |
| 23:00 | `bk-daily` | Full backup → ~/tradepilot-backups/ |
| Sun 19:00 | `due-competitive-intel` | Marks LLM agent due for weekly research |
| Sun 19:05 | `due-architect` | Marks LLM agent due for sprint planning |

All via macOS native `launchd` (we tried cron first — hit TCC restrictions, migrated). Telegram alerts fire on any Sarathi BLOCK/REJECT.

### 2.8 The Dashboard

Lives at `localhost:5050/team` with two views:

- **`/team`** — Agent grid (status dots, DUE badges, last action) + activity feed + audit log + KPI strip (today's PASS/WARN/BLOCK counts).
- **`/team/sarathi`** — Sarathi verification ledger drill-down. Filterable by rule family + decision.

Built on the existing Flask app (additive). Reads from append-only logs and per-agent JSON status files. Refreshes every 5 seconds.

---

## 3. The Research We Did (2026-05-14)

Before committing to the rebuild path, we ran 5 parallel research agents covering five independent dimensions:

### Agent A — ML Model Benchmarks

| Model | Reported IC | Reported IR/Sharpe | Source |
|---|---:|---:|---|
| LightGBM (Qlib Alpha158, CSI300) | 0.0448 | IR 1.02 | Microsoft Qlib leaderboard |
| XGBoost (same) | 0.0498 | IR 0.91 | Qlib |
| CatBoost (same) | 0.0481 | IR 0.80 | Qlib |
| **HIST (Alpha360)** | **0.0522** | **IR 1.37** | Qlib (best single model) |
| **DoubleEnsemble** | **0.0521** | **IR 1.34** | Qlib (best on Alpha158) |
| TFT (Alpha158) | 0.0358 | IR 0.81 | Qlib (worse than LightGBM) |
| TimesFM zero-shot (US) | R² −2.80% | Ann.Ret **−1.47%** | arXiv 2511.18578 (Nov 2025) |
| Chronos zero-shot | R² −1.37% | — | Same arXiv |

**Verdict:** Our LightGBM is the right model class. The problem isn't the algorithm. Foundation models for finance are not ready. The best published single model (HIST/DoubleEnsemble) is a **graph-aware ensemble built on top of GBM features** — same algorithm family, just better features + ensembling.

### Agent B — Open-Source Quant Frameworks

We audited Microsoft Qlib, FinRL, NautilusTrader, mlfinlab, OpenBB, QuantConnect Lean, Jesse, Backtrader, Zipline.

**Recommendations:**
1. **Adopt Qlib's Alpha158 feature set.** Same LightGBM family we already use. Drop-in feature uplift.
2. **Layer mlfinlab's triple-barrier + meta-labeling.** López de Prado's central thesis: fixed-horizon labels destroy IC; triple-barrier (TP/SL/timeout categorical labels) lifts IC 2–5× in published intraday literature.
3. **Skip FinRL, NautilusTrader, Lean for now.** They solve adjacent problems (RL allocation, execution fidelity, cloud infra). We don't have those problems yet.

### Agent C — Feature Engineering

The top alpha features we're NOT capturing today:

| Rank | Feature | Why |
|--:|---|---|
| 1 | **Order Flow Imbalance (OFI) 5m / 15m** | Kolm/Turiel/Westray 2023 — significant alpha at 1-min to 30-min horizon |
| 2 | **Kyle's Lambda** (price impact per ₹ traded) | Berkeley Haas — forecasts intraday volatility + next-bar returns |
| 3 | **Sector-relative return** | De-markets the feature space; addresses our "everything moves with Nifty" problem |
| 4 | **Delivery % z-score** | Institutional accumulation proxy; daily NSE bhavcopy (free) |
| 5 | **Stock-level ΔPCR intraday** | F&O sentiment per stock (F&O-listed names only) |
| 6 | **Micro-price** (Stoikov 2017) | Queue-imbalance encoding; beats mid-price as 1-tick-ahead predictor |
| 7 | **VPIN bucket** | Flow toxicity; predicts volatility expansion windows |
| 8 | **IV-skew (25Δ put − 25Δ call) + change** | Hedging demand → directional alpha |
| 9 | **Peer-cluster z-score** | k-NN-based cross-sectional de-marketing |
| 10 | F&O ban list + days-to-expiry × beta | Regime feature, near-free |

**Critical insight:** features 1–3 alone are projected to lift IC from 0.005 to 0.02–0.04 (4–8× lift). They are all derivable from **free Zerodha Kite L1 tick feed**. No paid L2 data needed.

### Agent D — Validation Methodology

What we should be using but aren't:

| Method | Why | Reported lift |
|---|---|---|
| **Combinatorial Purged Cross-Validation (CPCV)** | Replace single-path walk-forward; produces a distribution of Sharpe paths + PBO (Probability of Backtest Overfitting) score | Detects fake positives walk-forward hides |
| **Triple-Barrier Labels** | Replace raw return target with {TP, SL, timeout} | Korean intraday: drawdown ~halved |
| **Meta-Labeling** | Binary classifier on top of primary; filters low-confidence trades | **Sharpe +37%, Sortino ~2×, flat drawdown** |
| **ADWIN / Page-Hinkley** | Online drift detection | Catches regime shifts days before scheduled retrain |
| **IC promotion gate** | Block worse-IC models from going live | Prevents the May-13 regression class |

**Conceptual reframe:** *"IC is the wrong KPI to obsess over. Meta-labeling is designed to leave IC unchanged while doubling Sharpe."* We can ship a profitable system at IC 0.02 (not 0.05) if the meta-label filter is selective enough.

### Agent E — India-Specific Realistic Benchmarks

| Cohort | Win Rate | Sharpe (net) | Monthly | Annual |
|---|:---:|:---:|:---:|:---:|
| Retail F&O average | ~7% profitable | < 0 | −1.5 to −3% | −15 to −30% |
| Retail F&O top 1% | 50–55% | 0.8–1.3 | 1.5–3% | 18–30% |
| Retail algo (Streak/Tradetron) | 40–50% | 0.3–0.8 | flat | flat to −10% |
| **Retail algo top tier** | **48–55%** | **1.0–1.5** | **2–4%** | **25–40%** |
| Quant prop (Quantbox, Tower IN) | not disclosed | inferred 2.5–4+ | — | — |

**Fact-check of Apr-8 master research claims (3 found suspect):**
1. "Insider buying cluster → 11.2% outperformance over 6 months" → **not corroborated**. Closest public figure: 5–7% over 1 week (NSE 2010–19 study).
2. "FII net sell > ₹2000cr → bearish 1–3d" → **weak in 2026** (DII counter-flow neutralizes).
3. "GIFT Nifty 0.3% → 75% gap-up" → directionally 75–85% accurate, but **magnitude error 15–40 points** and fails on Fed/RBI/Budget days.

Tagged as `UNVERIFIED` / `NEEDS_INDIA_VALIDATION` / `PARTIAL` in our learnings DB.

---

## 4. The Honest Numbers

### 4.1 Where we sit today (Apr 21 → May 19 window)

| Engine | Gross P&L | Net @ 10bps | Net @ 15bps | Win-day p-value |
|---|---:|---:|---:|:---:|
| v4 | +₹258k | +₹98k | +₹18k | 0.50 (random) |
| v5 | +₹130k | −₹20k | −₹95k | 0.0064 |
| v5_6 | +₹159k | −₹4k | −₹86k | 0.17 |
| v5_7 | +₹158k | +₹2k | −₹76k | 0.0245 |
| v5_classic | +₹94k | −₹48k | −₹119k | 0.0245 |

**Three hard truths:**

1. **At realistic 10bps slippage, 4 of 5 engines are net negative.** v4 only survives because of one outlier day (May-6 +₹196,789 = 76% of v4's total).
2. **v4's win-day frequency is statistically random** (p = 0.50). Without the May-6 monster, v4 is a coin flip.
3. **v5 family has statistically significant win-frequency** but the magnitude is concentrated on cluster days. Non-cluster days bleed.

### 4.2 The cluster vs whipsaw signature

| Engine | Cluster day net/day @ 10bps | Non-cluster day net/day @ 10bps |
|---|---:|---:|
| v4 | +₹32,592 | −₹10,795 |
| v5 | +₹7,049 | −₹6,902 |
| v5_6 | +₹9,717 | −₹7,212 |
| v5_7 | +₹11,233 | −₹7,667 |
| v5_classic | +₹3,955 | −₹7,600 |

**TradePilot is currently a momentum-cluster harvester that bleeds on whipsaw days.** The asymmetry barely survives 10bps cost. The rebuild's whole purpose is to halve the non-cluster bleed without losing the cluster gains.

---

## 5. The Rebuild Plan (8 weeks)

| Sprint | Theme | Gate | Status |
|---|---|---|---|
| **1** (May 15–18) | Stop bleed + dashboard + Sarathi rules + automation | All gates live | ✓ done |
| 2 (May 25–31) | Triple-barrier labels + 6 postmortem hardening tasks | Label quality vs known TARGETs | next |
| 3 (Jun 1–7) | Sector-RS + OFI + Kyle's λ features | CPCV IC ≥ 0.02 | |
| 4 (Jun 8–14) | Meta-label classifier | Backtest Sharpe ≥ 1.0 net 10bps | |
| 5 (Jun 15–21) | Live 5-day A/B (meta-filtered vs unfiltered) | Live WR ≥ 55% | |
| 6 (Jun 22–28) | Microstructure v2 (micro-price, VPIN, ΔPCR) | CPCV IC ≥ 0.03 | |
| 7 (Jun 29–Jul 5) | Drift detector + champion-challenger automation | Synthetic drift catch | |
| 8 (Jul 6–12) (stretch) | FinBERT sentiment | OOS IC stable | |
| **Override expires** | **2026-07-15** — rebuilt model MUST be live by this date or engines hard-block at boot |

### 5.1 The conceptual core

Two parallel optimization targets:

1. **Primary IC ≥ 0.04** (matches Qlib LightGBM/Alpha158 baseline) — via features + Alpha158-inspired engineering + microstructure adds
2. **Post-meta-label Sharpe ≥ 1.0 net of 10bps** — via triple-barrier labels + meta-label classifier

You can hit profitable trading with a "weak" IC 0.02 primary if the meta-label filter is selective.

### 5.2 Projected outcome on the same window (back-test prediction)

| Engine | Current net @ 10bps | Projected net @ 10bps post-rebuild | Mechanism |
|---|---:|---:|---|
| v5 | −₹19,676 | +₹35–55k | whipsaw bleed cut in half, cluster days preserved |
| v5_6 | −₹4,098 | +₹50–70k | same dynamics, more trades |
| v5_7 | +₹1,958 | +₹55–75k | meta-label is pure upside |
| v5_classic | −₹48,308 | +₹15–30k | smaller magnitude, no Track A |

**These are projections from literature reported lifts. Actual proof requires Sprint 5 live A/B.**

---

## 6. What Kishore Should Research

This is the explicit ask. Below are research questions ranked by impact.

### 6.1 Highest priority — existing implementations to investigate

1. **Microsoft Qlib + Alpha158 feature set on Indian (NSE) data.**
   - Q: Has anyone done a public NSE adapter for Qlib?
   - Q: What's the IC of Alpha158 on NSE specifically? (Should be similar to CSI300 if features are universal.)
   - Q: Does Qlib's WorkflowR pipeline support NSE bhavcopy + jugaad-data ingestion?
   - GitHub starters: `microsoft/qlib`, look for community forks tagged "nse" or "india".

2. **mlfinlab triple-barrier + meta-labeling — is the OSS version usable?**
   - Q: Hudson & Thames gated the original repo in 2021. Are there active forks?
   - Q: How many LOC to reimplement the 3 core functions? (We estimated ~300.)
   - Q: Any published Indian-market case studies using triple-barrier?
   - GitHub: `hudson-and-thames/mlfinlab` (gated), search for "triple-barrier" + "Indian equity".

3. **Order Flow Imbalance (OFI) on free L1 data — what's the floor for accuracy?**
   - Q: Kolm/Turiel/Westray 2023 used NASDAQ L2. Does OFI work as well on Zerodha Kite L1 ticks?
   - Q: Are there Python implementations of OFI we can borrow?
   - Q: Has anyone published OFI alpha on NSE specifically?

4. **HIST and DoubleEnsemble — are these reproducible on smaller equity universes?**
   - Q: Qlib reports IC 0.052 with HIST on CSI300 (~300 stocks). We have ~200 Nifty stocks. Is HIST viable?
   - Q: Compute requirements?
   - GitHub: `microsoft/qlib/examples/benchmarks/HIST`.

### 6.2 India-specific edges to fact-check / explore

5. **Insider buying signals on NSE.** Our Apr-8 master claims "11.2% over 6mo" but it doesn't reproduce. Find the actual published number from SEBI SAST data.
6. **GIFT Nifty premium / cash-open relationship in 2026.** Has the relationship strength changed since Tuesday-weekly expiry shift (Sep 2025)?
7. **NSE delivery % as institutional signal.** Find at least one back-tested study on this.
8. **F&O ban-list intraday volatility regime.** Does an unusual volatility regime form when a stock crosses 95% MWPL? How to model it?
9. **AlgoTest, Stratzy, Streak case studies.** What do their profitable users actually run? Public material only.

### 6.3 Infrastructure / tooling questions

10. **Cloud migration.** We have `docs/research/2026-05-08_cloud_migration_master.md` exploring AWS / GCP / hetzner for moving off the M1 Mac. Worth comparing fresh.
11. **River library** (online ML, Python). Used for drift detection. Are there better alternatives in 2026?
12. **Telegram bot UX for trading alerts.** What patterns work? What's the Indian retail standard?
13. **NSE data sources.** We use jugaad-data + Zerodha Kite. Are there cheaper / more reliable alternatives that emerged since the 2026-04-08 master research?
14. **Sentiment data.** FinBERT/FinGPT on Indian news. Is there an Indian-market-fine-tuned variant?

### 6.4 Conceptual / strategic

15. **Walk-forward IC vs CPCV.** Find a clean explainer + Python implementation we can lift. Likely in `skfolio`.
16. **The "two safety guards disagree" pattern.** Search literature on quant ops for unified safety frameworks. We just hit one of these (May-18 incident); there are likely more in our codebase.
17. **Smallcase / Wright Research / Quantonet** — are any of these doing what we're trying to do, but cheaper/better? Public material only.
18. **Indian quant founders interviewed publicly.** Krishnan Velayudhan (Quantbox), Roopalee Dave (Tower India). Public talks, interviews — any insight on what they do or don't do?

---

## 7. What I Need Back From Kishore

For each research question:

1. **Existing implementation** — link to GitHub repo, paper, blog post, or product page
2. **Active or stale?** — last commit / update date
3. **Indian-market relevance** — does it work on NSE, or US-centric?
4. **Compute requirements** — runs on M1 Mac or needs GPU?
5. **Honest assessment** — would adopting it 10× our current work, save us 10× the effort, or be lateral?
6. **One paragraph: should we use it, fork it, ignore it, or reimplement?**

Format: a markdown doc back to me with one section per question. Don't fabricate findings. "Couldn't find anything authoritative" is a valid result.

---

## 8. Repository Map (where to find things)

```
~/Documents/tinker/projects/tradepilot/
├── .claude/team/
│   ├── README.md                       Team charter, org chart, sprint cadence
│   ├── roles/                          10 agent role definitions
│   └── cadence/                        Daily standup + auto-stop scripts
│
├── docs/
│   ├── HANDOFF_KISHORE_2026-05-19.md   ← This file
│   ├── research/
│   │   ├── 2026-04-08_v5_master_research.md  Original master research (480 lines)
│   │   ├── weekly_intel/2026-05-17.md  Latest Competitive Intel brief
│   │   └── weekly/2026-05-17_ic_audit.md  Latest Alpha Hunter audit
│   ├── sarathi/rules/                  5 rule catalogs (LRN, SPR, ML, CDE, DAT)
│   ├── team/
│   │   ├── backlog/sprint2.md          Sprint 2 plan
│   │   ├── audit/                      Append-only daily audit log
│   │   ├── activity/                   Activity feed
│   │   └── standup/                    Daily summary cards
│   ├── paper-trades/{v4,v5,v5_classic}/ Per-engine per-day trade JSONs
│   ├── work-log/                       EOD insight markdowns
│   ├── slippage/                       New: per-trade-leg slippage records
│   └── exec/                           Daily cost-corrected summaries
│
├── prototype/
│   ├── app.py                          Flask app — UI + dashboard backend (NOT detail focus)
│   ├── v4/
│   │   ├── ml_engine.py                LightGBM scorer, model loader, SARATHI-ML gate
│   │   ├── composite_scorer.py         The 22-feature scorer
│   │   ├── tiered_scorer.py            VIX-tiered model variant (May-4)
│   │   └── models/
│   │       ├── lgbm_intraday.txt       Live model (May-9 archive, restored)
│   │       ├── verification_report.json  Sarathi-signed; CEO override until 2026-07-15
│   │       └── archive/                Dated model snapshots, never deleted
│   ├── v5/
│   │   ├── signal_engine.py            Percentile gates + SHORT weakness gate (May-4)
│   │   ├── regime_detector.py          3-state market regime (BULL/SIDEWAYS/BEAR)
│   │   ├── premarket_intel.py          GIFT Nifty + gap prediction
│   │   ├── pool_manager.py             4-pool capital manager
│   │   ├── risk_manager.py             Circuit breakers + Kelly sizing
│   │   ├── rust_bridge.py              HTTP client for Rust execution layer
│   │   └── enhanced_features.py        Beyond-baseline indicators
│   └── utils/signal_guards.py          Defensive: safe_qty, freshness, reentry block
│
├── scripts/
│   ├── v4-paper-trade.py               v4 engine (~1000 lines)
│   ├── v5-paper-trade.py               v5 engine (~1100 lines, multi-pool)
│   ├── v5_classic-paper-trade.py       Frozen baseline
│   ├── launch-market.sh                Full battle launch (Rust + Flask + engines + watchdogs)
│   ├── sarathi/verify.py               5-family rule runner
│   ├── team/
│   │   ├── log.py                      Shared audit + activity logger
│   │   ├── slippage.py                 Execution Analyst helper
│   │   ├── cadence/                    Automation scripts
│   │   └── gates/mlops_ic_gate.py      Engine-side model gate
│
└── engine/                             Rust execution + risk layer (Cargo)
    └── src/                            ~3k lines Rust
```

---

## 9. Key Numerical Targets

| Metric | Today | 6-month target | Quant-fund floor |
|---|---:|---:|---:|
| Walk-forward IC | 0.0054 | ≥ 0.04 | ~0.06–0.10 |
| Live Sharpe (net 10bps) | likely < 0 | **1.0–1.5** | 2.5–4+ |
| Win rate | 32–43% (today's bleed) | 50–55% | not disclosed |
| Max drawdown per engine | tracked daily | < 8% | < 5% |
| Annual return target | TBD | 25–40% net | 30–60% |
| Slippage realized | being measured (Sprint 1) | ≤ 10bps avg | ≤ 5bps |
| CPCV PBO (overfit risk) | not yet computed | < 0.5 | < 0.3 |

---

## 10. The Discipline We've Adopted

1. **Every learning has a source.** Numerical claims without citations get tagged UNVERIFIED. Three claims from our own master research were retroactively flagged.
2. **Every model promotion goes through a gate.** The May-13 incident is structurally impossible to reproduce silently.
3. **Every decision is audited.** Append-only JSONL. Searchable from the dashboard. We can replay any moment.
4. **Three independent vetoes block bad work.** Architect (code) + MLOps Sentinel (IC) + Sarathi (risk) must all approve a model promotion. DQO can independently block on data integrity. CEO can override but it's recorded.
5. **No claim of profitability without 10bps slippage cost applied.** Gross P&L is no longer the headline number.

---

## 11. Open Strategic Questions

These are the calls I haven't fully answered:

1. **Do we keep Rust?** v4 already runs pure-Python. v5 family imports rust_bridge with try/except fallback. Rust holds risk-state coherence but Python could too. Removing Rust is Sprint 5+ cleanup. Verdict: keep for now.
2. **Do we expand the universe?** Currently Nifty 200 + selected Nifty 500. Top-100 only would reduce slippage materially but lose breadth. Counter: where's the alpha — top-100 or 200–500?
3. **Live broker integration timing?** Plan says Phase 4 (week 10–12). I think live brokerage should not happen before 30 consecutive days of positive net-of-cost paper P&L.
4. **One engine or three?** v5_classic adds noise but proves the rules layer. v4 is the control. Worth maintaining all three through Sprint 8 or consolidate to one after Sprint 5?
5. **Telegram pager or dashboard-first?** Telegram fires on BLOCK now. Some routine WARNs add noise. What's the right signal-to-noise ratio?

---

## 12. What I Learned That I Didn't Expect

1. **IC is the wrong KPI to obsess over.** Meta-labeling lets a low-IC primary become a high-Sharpe filtered output. Stop chasing IC alone.
2. **The first deep-research session refuted the model-class hypothesis.** Our LightGBM is the right algorithm; the features and labels are the lever. This saved us from a wasted Sprint 4 of trying TFT/Mamba/foundation models.
3. **macOS TCC has per-file-path memory of denials.** A log file path can become "tainted" such that subsequent launchd writes to it return EX_CONFIG with zero log output. Took us a 90-minute debug to find. Documented in commit notes.
4. **Two safety guards independently added will eventually disagree.** Our `check_model_freshness` and SARATHI-ML override were both added with good intent; they disagreed on the legacy model and caused an outage. Sprint 2 audits the rest of the codebase for this pattern.
5. **The most profitable mechanism we have is rules, not ML.** Track A (re-arm + bullish gate + time exit) is what made April-22 a +₹61k day. The ML's job is to stop the *other* days from bleeding — not to generate cluster-day alpha.

---

## 13. How to Pick This Up

**If Kishore is doing research only:** start at Section 6 ("What Kishore Should Research") and Section 1–4 for context. Skip 7–13.

**If Kishore wants to clone and run locally:**
```bash
git clone <repo>
cd tradepilot
# Read .claude/team/README.md first — describes the team + cadence
bash scripts/team/cadence/monday-check.sh   # 27-check sanity test
# Dashboard:
cd prototype && python3 app.py              # serves localhost:5050/team
```

**If Kishore wants to run engines locally:** don't. The engines paper-trade with real-time NSE data fetches and write to actual state files. Better to read trade JSONs in `docs/paper-trades/` to understand outputs.

---

## 14. Contact

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@sidewall.in |
| **Project repo** | local (not yet public) |
| **DevPilot DB** | localhost:5499 (sprint + task + learnings store) |
| **Dashboard** | localhost:5050/team (when Flask is running) |
| **Override expiry** | 2026-07-15 (the rebuild's hard deadline) |

---

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| IC (Information Coefficient) | Rank correlation between predicted return and actual return. A measure of model alpha. Above 0.05 is "tradeable" per most quant lit. |
| CPCV | Combinatorial Purged Cross-Validation. López de Prado's anti-overfit validation method. |
| PBO | Probability of Backtest Overfitting. CPCV outputs this; < 0.5 is the floor for trustworthy backtests. |
| Meta-labeling | Adding a secondary binary classifier on top of a primary regressor's predictions, to filter low-confidence trades. |
| Triple-barrier method | Replace fixed-horizon return labels with categorical {TP_hit, SL_hit, vertical_timeout} labels. |
| OFI | Order Flow Imbalance. Microstructure feature from L1 bid/ask order book. |
| VPIN | Volume-synchronized Probability of Informed Trading. Flow-toxicity proxy. |
| Sarathi | (Sanskrit: charioteer/guide) Our verification authority — a 5-rule-family safety system. In the Mahabharata, Krishna was Arjuna's sarathi. |
| DAT/CDE/ML/LRN/SPR | The five Sarathi rule families (data, code/deploy, ML training, learnings, sprints). |
| Track A | The three Apr-27 rule changes: BULLISH_PREMARKET_SHORT_BLOCK, WINNER_RE_ARM, TIME_EXIT_TIGHTENING. |
| Track B | The 4-week ML rebuild plan from Apr-27 (target, dataset, features, integration). Now subsumed into Sprints 2–4. |
| TCC | macOS Transparency, Consent, Control. The permission system that blocks launchd from arbitrary file writes. |
| `launchd` | macOS-native scheduler. We migrated from cron. |
| `pmset` | macOS power management CLI. We use it to wake the Mac at 08:45 IST weekdays. |
| `dp` | DevPilot CLI — companion tool for sprint/learning/task management. |

---

## Appendix B — Key Sprint 1 Commits

| Commit | Title |
|---|---|
| 84c8ffe | feat(team): permanent agent team charter + 5 Sarathi rule families |
| 8e18d1c | feat(team): shared audit log + activity feed + slippage helpers |
| 0174c6c | feat(sarathi): SARATHI-ML gate + ml_engine integration (May-13 prevention) |
| 93dcf62 | fix(model): revert May-13 retrain to May-9 pre-retrain + CEO override |
| dff5b99 | feat(dashboard): /team agent dashboard + Sarathi ledger drill-down |
| 12b26af | chore(engines): consolidate to v4 + v5 + v5_classic |
| 5d150dc | feat(automation): cron-driven cadence — no manual work |
| 9715b47 | chore(automation): pmset wake at 08:45 IST Mon-Fri |
| 6976823 | refactor(automation): migrate cron → launchd; v2 namespace + TCC fixes |
| 93c34e1 | feat(monday-prep): launchd PATH fix + AbandonProcessGroup + slippage + dashboard |
| e9c6489 | feat(automation): weekday 08:50 IST automated preflight check |
| 5593c77 | fix(v5-startup): freshness guard respects CEO override on stale model |
| 4130b5d | docs(sprint2): backlog with postmortem hardening + main work items |

---

*End of handoff doc. ~12 KB / 600 lines.*
