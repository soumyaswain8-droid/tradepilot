# TradePilot — Full Detailed Report (June 2026)

*The complete record: every finding, every debug, every feature, every validation — with the data, evidence, code locations, and reasoning behind each.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot (autonomous agentic trading, NSE intraday) |
| **Document** | Full detailed report — June 2026 work arc |
| **Version** | `v1.0.0` |
| **Period covered** | 2026-06-22 → 2026-06-30 |
| **Method** | 14+ research/forensic agents, ~7.5M tokens of deep-research, Sarathi-disciplined data validation |
| **Status** | Complete |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@sidewall.in |

:::

---

# 1. Executive Summary

This report documents an eight-day investigation that began with a single question — *"why are we losing money?"* — and ended with a data-grounded fix shipped into testing. The arc:

1. **Root cause** — The edge was never the AI/ML; it is **execution discipline**. Three months of reactive complexity (NIFTY-50→200, long+short, 4 pools, a 1,735-tree ML model, late-entry rescore loop) **diluted** a profitable engine. Win-rate fell **82% → ~48%** as trades/day rose **17 → 45**. The frozen original (`v5_classic`) quietly out-earns the live rebuild.
2. **Competitive & strategy** — TradePilot has **no direct competitor** (no Indian platform is agentic; global peers are mostly research prototypes), sits at autonomy level **T3** (the level credible real funds run at), and the academic literature **validates** its core thesis (LLM/ML alpha is largely lookahead-bias illusion). A 3-pillar strategy (profitability, UX, platform) showed all three converge on one artifact: a **simple, explainable, clean-execution decision pipeline**.
3. **Red-day regime work** — A live red day exposed that the engine **does not adapt its long/short mix to the tape**. Four successive data validations (each correcting a coarse assumption of mine) reshaped the fix from "flip the book short" into "**tilt the ratio, decide direction per-stock, with a risk cap**."
4. **Builds shipped** — Conviction logging across **all** engines (closing a "store-everything" gap), and a **`v5_flip`** fast-regime-flip shadow added to the A/B rotation. Plus three infra/diagnostic tools (red-day watchdog, daily compare, decision dashboard) and a data-stall root fix.

**Bottom line:** the engine is not broken — its *execution* degraded and it *doesn't read the tape*. Both are fixable and now instrumented. The path is sequenced: **prove profitability → go live cheaply (own capital) → productize into an agentic platform only if chosen.**

<div class="page-break"></div>

# 2. Root-Cause Investigation — Why We Were Losing

## 2.1 The edge is execution discipline, not ML/AI

The original profitable engine (April) ran NIFTY-50, top-5 long-only, a tight +1.5% / −0.75% bracket, flat at 15:15 — and hit an **82% win rate**. Decisive evidence the *models* were not the source of that edge:

- On the 82%-WR day, the average **winner's composite score (66.9) ≈ the average loser's score (69.2)**. The score was not separating winners from losers.
- The ML information coefficient was **0.006** — statistically indistinguishable from zero. ML was later weighted to 0 with no measured degradation.

The money came from the *disciplined bracket + concentration + end-of-day flat exit*, not the intelligence.

## 2.2 Complexity diluted the edge

::: {.gap-table}

| Dimension | Original (April) | Current (June) | Direction |
|:--|:--|:--|:--|
| Universe | NIFTY-50 | NIFTY-200 | 4× wider |
| Direction | Long-only | Long + short + flip | More exposure |
| Positions | 5 | 20 (4 pools) | 4× more |
| Trades/day | 17 | ~45–57 | 2.6–3.4× more |
| Bracket | +1.5% / −0.75% | +2.0% / −1.5% | Wider stops |
| **Win rate** | **82%** | **44–53%** | **Collapsed** |

:::

Rising trade count with falling win rate is the mathematical signature of **over-diversification + over-trading** regressing a selective alpha toward a coin flip. The complexity cascade was *reactive* — each layer (regime detector, kill switches, shorts, pools, FLAT_FORCE_EXIT) was bolted on after a single bad day (notably v4's −₹30,816 loss on Apr-9, a bear day with no regime filter), not because the simple engine was failing.

## 2.3 Forensic trade-level findings

| Finding | Detail | Verdict |
|:--|:--|:--|
| **FLAT_FORCE_EXIT exonerated** | Trade-level audit of 06-17 & 06-22 (the two worst v5-specific days): on the symbols it flattened, it ended **+₹30 and +₹299 better** than the frozen original holding them | **Innocent — it helped** |
| **Late entry is the day-to-day bleed** | v5 entered the *same names, same direction* 30–60 min later than `v5_classic` on **16/35 (06-17)** and **21/38 (06-22)** shared positions → winners booked as STOPLOSS/TIME_EXIT not TARGET. Cost: **−₹1,969 (06-17), −₹1,092 (06-22)** | The real mechanism |
| **Over-trading = cost drag** | 8 days: gross **+₹4,691**, round-trip cost **−₹7,153** → net **−₹2,462**. Excess churn from 57/day vs original 17/day = **₹5,046 = 205% of net**. At 17/day cadence the same edge nets **+₹2,584** (winning) | Cost flips a winning book to a loss |
| **Under-deployed, fragmented** | Avg position **₹13,130** (~10× smaller than the 15%-of-pool rule implies); only ~₹260k working on a ₹10L book | Capital barely used |

## 2.4 The decisive finding — the SHORT book is the net bleed

Across 454 trades (06-16 → 06-25):

::: {.metrics-table}

| Direction | Trades | Net P&L | Win rate | TARGET hit |
|:--|--:|--:|--:|--:|
| **LONG** | 213 | **+₹1,149** | 41.8% | 8.5% |
| **SHORT** | 241 | **−₹3,611** | 34.4% | 4.1% |
| Total | 454 | −₹2,462 | 37.9% | 6.2% |

:::

If the short book were merely flat, v5 would be net positive. Shorts hit TARGET only **4.1%** of the time (longs 8.5%) and die on **STOPLOSS (−₹9,107, the single biggest loss bucket)** — classic shorting-into-an-up-drifting-tape. *(Note: this finding is refined later in §6.2 — shorts are not categorically bad; mis-timed shorts on the wrong tape are.)*

## 2.5 v5_classic ("the old tree") dominance

The frozen original v5 (git `236d6e4`, pre-Rust, pre-safeguards) has out-performed the live rebuild over 45 sessions (Apr 20 → Jun 29):

::: {.metrics-table}

| Metric | v5_classic | v5 (live) |
|:--|--:|--:|
| Cumulative (45 sessions) | +₹111,803 | +₹116,357 |
| Green / red days | 28G / 14R (62%) | fewer |
| Beat the other, day-by-day | won 29/43 (67%) | won 33% |
| Avg/day | +₹2,485 | — |

:::

**v5's apparent ₹4,554 lead is a mirage** — it comes entirely from **two April outlier days**: 04-22 (v5 +₹44,612 vs classic +₹10,291, a ₹34,321 gap) and 04-23 (+₹15,352 gap) = ₹49,673. Strip those and v5_classic wins the remaining 43 sessions decisively. This is the *identical* outlier-fragility that retired v4.

**The trend is decisive and accelerating:**

::: {.metrics-table}

| Month | v5_classic | v5 (live) | Winner |
|:--|--:|--:|:--|
| April (early A/B) | +₹39,245 (8G/1R) | +₹69,342 | v5 — *only via the 2 outlier days* |
| May | +₹59,667 (won 13/17) | +₹46,325 | classic |
| **June** | **+₹12,891 (11G/5R)** | **+₹690** | **classic, 18×** |

:::

Why it wins: clean early-entry execution + holds to TIME_EXIT, with **none** of the late-entry lag, FLAT_FORCE_EXIT, or 57-trade churn the rebuild carries. Same signals, same universe, same stops — the original *executes* them cleanly.

## 2.6 The OLD 5-tree A/B — a leverage mirage hiding a real gem

The dashboard card "v4 model — 5-tree challenger vs live 1,735-tree" (sibling project `tradepilot-oldengine-ab`) shows the OLD 5-tree model (`best_iteration: 5` vs the live model's **1,735**), long-only, printing **+₹122,003 over 14 sessions (71% green)** vs live v5's −₹6,023. Skeptic checks deflate the headline:

::: {.gap-table}

| Check | Finding | Effect |
|:--|:--|:--|
| Leverage | 06-29 deployed **₹3,130,953 = 313% of the ₹10L book** (139 positions) vs v5's ~35% | ~9× more capital — bigger rupees, not better alpha |
| Gross, not net | `realized_pnl` only, **no cost field** (v5's is net of 12bps) | Costs would erase a large chunk |
| Outlier-driven | Top **4 days = ₹88,303 = 72%** of total; the other 10 days net ~₹34k | Same fragility that retired v4 |

:::

**The real, leverage-independent gem:** a 5-boosting-round model **out-hits** the 1,735-round live model. This is hard internal evidence the **live ML model is overfit** (textbook: complex models memorize noise; simple models generalize) — and the fix it implies ("shrink the model drastically") is cheap and testable.

## 2.7 Watchdog validation — entry quality, not volume

Independent telemetry (06-16 → 06-25) cross-checked the claims:

- Only **6.2% of 454 exits hit TARGET**; the book held **3.6× more losers than winners** at any snapshot.
- **Win-rate drives P&L, not trade volume:** 06-25 did 67 trades for **+₹5,014 (61% WR)**; 06-24 did 62 trades for **−₹2,044 (31% WR)**. Near-identical volume, opposite result.
- **"What right looks like":** 06-19 (BEAR regime) — 45 trades, **zero** SIGNAL_FLIP/FLAT churn, **+₹1,602**.

<div class="page-break"></div>

# 3. Debugs & Data-Integrity Fixes

## 3.1 The 06-26 all-day data stall

**Symptom:** On 06-26 every engine made ~5 trades all day, ₹0 P&L, the missed-opps watchdog flatlined at 10:31, engines alive but starved.

**Root cause (✅ verified):** yfinance 1.2.0 keeps a shared SQLite cache (`~/Library/Caches/py-yfinance/tkr-tz.db`). All engine processes + dashboard + watchdogs hit the *same* file concurrently → `OperationalError: unable to open database file` → every download returns `None` → no prices → no signals → no trades. The `-wal`/`-shm` files present at the time are the smoking gun of concurrent SQLite access. *Not* a sleep (heartbeats ran) or crash (nothing restarted).

**Fix:** Per-process cache isolation — `yf.set_tz_cache_location()` keyed by `ENGINE_NAME`/PID — in `prototype/v4/data_nse._get_yfinance()` (covers all engines + dashboard) and `scripts/missed-opportunities-watchdog.py` (calls yfinance directly). Cleared the corrupt shared db. **Verified:** live `RELIANCE.NS` download works post-fix; held under real multi-engine load on 06-29 (all 4 engines normal volume, no repeat).

## 3.2 Conviction not stored on closed trades

**Symptom:** `score`/`reasons` could not be correlated to P&L from history → the dynamic-allocation question (§6.4) was unprovable.

**Root cause (✅ verified):** The entry conviction *is* captured (`score=33.0`, `direction`, `reasons` all live on the open position), but `close_position` rebuilt the closed record from a **hardcoded subset of fields** and dropped them. The data was never missing — it was *thrown away at the last step*. Against the standing "store everything" instruction.

**Fix:** Carry `score`, `direction`, `reasons`, `sl_price`, `target_price`, `entry_date`, `trailing_activated` into the closed record across **all** engines: the v5 family (`v5`, `v5_long`, `v5_cut`) via the shared `close_position`, plus the standalone `v5_classic` and `v7_regime` scripts. **Verified:** compile clean, smoke gate PASS (exit 0), fields present in the close path. Applies at next launch; running processes untouched. From the next session every closed trade is fully instrumented; ~5 sessions yields conviction→P&L data.

<div class="page-break"></div>

# 4. Engine Roster Consolidation

**6 → 4 lean roster (06-26 audit), then → 5 with the new shadows.** Retirements are *commented out* (state preserved), never deleted.

::: {.gap-table}

| Engine | Role | Status |
|:--|:--|:--|
| v5 | Live baseline (with shorts) — the thing to beat | Active |
| v5_classic | Frozen April original — the durable benchmark | Active |
| v5_long | RC-1: long-only NIFTY-200 (shorts disabled via `SHORT_REQ_MAX_SCORE=-1`) | Active |
| v5_cut | ML-removed + faster wrong-way cut + tighter short-gate + ~450 universe | Active |
| **v5_flip** | **Fast intraday regime-flip (new, §7.6)** | **Active (new)** |
| ~~v5_noml~~ | Redundant — `ml_score=0` already global, so it ran v5 twice | Retired |
| ~~v5_apr~~ | Tracked v5 within +₹78 over 9 days — no information value | Retired |
| ~~v7_regime~~ | Beat v5 by only +₹1,684/9d; daily-gate WFO showed no edge (DSR 0.12) | Retired |

:::

Consistency enforced across `launch-market.sh`, `crash-watchdog.sh`, and `engine-compare.py` (all show the same 5 active engines).

<div class="page-break"></div>

# 5. Competitive & Strategy Research

## 5.1 Competitive landscape (105-agent deep-research, adversarially verified)

**TradePilot has no direct head-to-head competitor.** Genuinely agentic trading exists but is ~95% open-source research frameworks / academic prototypes: TradingAgents (4 analysts + bull/bear debate), FinMem (layered memory), TradingGroup (5 agents + self-reflection), The Self-Driving Portfolio (~50 agents + a meta-agent that rewrites its own code), AI-Trader, FinWorld, FinRL. The one commercial Tier-1 peer, **Standard Signal (YC S26)**, makes live-trading + Sharpe>3 claims that **failed verification** (unaudited, solo founder; the "first" claim is false — Aidyia/Sentient predate it by a decade).

**Reality-check (3-0 verified):** LLM trading alpha is **largely lookahead-bias / memorization** — it collapses out-of-sample (one cited case: +20.73% in-sample → −1.04% post-cutoff). Removing LLM features dropped Sharpe only 1.40→1.14. This **independently validates** the decision to zero our ML (IC 0.006): the edge living in *execution discipline* is the more defensible position.

## 5.2 Autonomy benchmark — T3

No trading-specific L0–L5 standard exists; derived from the Knight Columbia agent-autonomy paper (arXiv 2506.12469): **TradePilot = T3 (Conditional Autonomy)** — AI runs the entire intraday loop (research → regime → score → signal → size → execute → EOD) with no human in the loop; humans retain veto only at the strategy layer. T4 would require self-modifying strategy params without sign-off. T3 is the level credible real funds actually operate at.

## 5.3 Tier-2 — Indian retail-algo market

**Zero Indian platforms are genuinely agentic.** Every major one — Streak, Tradetron, AlgoTest, QuantMan, Sensibull, AlgoBulls — is a rule-based strategy builder where the user defines all logic. The closest (AlgoBulls Phoenix Copilot) just translates "buy when RSI<30" into code. TradePilot's autonomy is a **category gap**, not a feature gap. Incumbents' moats are elsewhere: live execution (Tradetron 1.5M trades/mo, 60+ brokers), real users (Sensibull 1M+, AlgoTest ~25k), 2+ years of SEBI compliance work, polished UX, and ₹300–1,300/mo pricing the market is trained on.

## 5.4 Tier-4 — institutional AI funds

Every fund with real money keeps a human in the strategy loop: Renaissance & Two Sigma frame AI as a research/signal tool, not the decision-maker. The "fully autonomous" funds (Lumenai, Altbridge, Standard Signal) are pre-launch / proof-of-concept / self-reported. **Numerai** is the closest verified AI-native (JPMorgan committed up to $500M; ~25% net 2024) — but it's crowdsourced ensemble + systematic execution, not autonomous agents.

## 5.5 SEBI compliance (the answer to "are we doing anything wrong?": **No**)

SEBI's framework (Feb-2025 circular, fully in force **April 1, 2026**) regulates *orders on exchanges via broker APIs*. TradePilot places none.

::: {.gap-table}

| Tier | Trigger | Obligations | Burden |
|:--|:--|:--|:--|
| Paper (now) | Simulation only | None | **Zero** |
| Live, own capital | Kite order API | Static IP + whitelist · kill-switch · 5-yr order audit log · Kite algo-TOS check · OPS profiling (we run ~**0.0024 OPS** avg, peak <1 — far under the 10-OPS line) · family-account carve-out only | **Light** |
| Offer to others | Product | SEBI Research Analyst licence (black-box) · NSE/BSE empanelment · ISO 27001 · biannual CERT-In VAPT · per-strategy algo-ID · grievance redressal | **Heavy** (6–12 mo) |

:::

Running the algo for anyone outside the family (self/spouse/dependent parents/children) instantly triggers the heavy "algo provider" tier.

## 5.6 3-pillar strategy research — the convergence

All three pillars point at one artifact:

- **Profitability (5 ranked levers):** ① execute-at-open / kill the rescore loop (highest, free; Man Group: alpha decays in minutes) · ② collapse the ML to ≤20 trees + purged walk-forward (Bailey/Lopez-de-Prado: ~4.75 backtests = Sharpe 1.0 by chance) · ③ ATR-sizing at ≥60% deployment (fractional Kelly; underbetting destroys returns) · ④ binary regime gate on *direction* (SMA + VIX-rank, no grid-search) · ⑤ retrain on the correct label, P(target before stop).
- **UX:** the user is a **supervisor, not a pilot** — single status surface, plain-language decision log, progressive-delegation onboarding, Telegram check-not-operate, dual-mode UI.
- **Platform:** "**BYOB White-Box Agent**" — runs in the user's own broker account, zero platform capital (no PMS licence), white-box (no RA licence). 9-role agent DAG, train/eval-namespace separation (structural anti-overfit).

**The spine:** the explainable decision log is simultaneously the profitability validation, the UX trust surface, the SEBI compliance audit trail, *and* the platform's audit layer. One build, four payoffs. The agentic-DAG architecture is the *same* investment as the overfitting fix.

<div class="page-break"></div>

# 6. The Red-Day / Regime-Flip Arc (06-30) — Four Data Validations

This is the most rigorous sequence of the arc. The `/rules` (Sarathi) discipline was explicitly applied: **re-verify instead of defend; show evidence; confidence-label every claim.** The data corrected a coarse assumption of mine **four times**.

## 6.0 The live diagnosis

At 09:48 on a red day (NIFTY −0.73% intraday), per-engine attribution was unambiguous:

::: {.metrics-table}

| Engine | Net | LONGS | SHORTS |
|:--|--:|--:|--:|
| v5 | −1,214 | −1,671 (17t) | **+623 (10t)** |
| v5_classic | −1,753 | −2,376 (16t) | **+623 (10t)** |
| v5_long | −1,238 | −1,142 (23t) | 0 (no shorts) |
| v5_cut | −1,082 | −585 (17t) | −371 (10t) |

:::

**The longs were the entire bleed; the shorts were green.** The engines were long-heavy (16–23 longs vs 10 shorts) on a falling tape.

## 6.1 The two structural gaps (✅ confirmed in code)

- **Gap 1 — regime frozen at launch.** `detect_regime()` runs once at premarket (`v5-paper-trade.py:379`); `rescore_and_redeploy` reuses `state["regime"]` (`:698`) and never re-detects intraday.
- **Gap 2 — slow inputs.** `regime_detector.py` votes on 6 *daily* aggregates (50/200-DMA, 5-day momentum, daily VIX, FII/DII, advance-decline). A red open barely moves a 50-day average → it reads SIDEWAYS/BULL → deploys the 15-long/5-short split. The engine is **structurally blind to a red open**.

## 6.2 Validation 1 — "no flips after 13:30" is REFUTED

I had proposed going defensive after 13:30. The data (INTRADAY trades, all sessions since April), by **entry** time-of-day:

::: {.metrics-table}

| v5 (50 sessions) | Net P&L |
|:--|--:|
| Entered after 1:00pm | **+₹30,515** (486t) |
| Entered before 1:00pm | **−₹2,724** (723t) |
| Entered after 1:30pm | +₹20,209 (would have been thrown away) |

:::

Best entry hour = **13:00 (+₹16,882)**, then 14:00 (+₹9,926); the 10am hour *loses* −₹7,363. v5_classic milder but same direction (post-1pm +₹10,517, 55% green). **Conclusion: the 2nd half is where the profit is — the rule was removed; the flip is bidirectional and active all session.** *(Caveat: the "168% of net realized after 1pm" exit-time figure is TIME_EXIT-inflated; the entry-time numbers are the clean measure.)*

## 6.3 Validation 2 — "short=red, long=green" is REFUTED

P&L by direction × market-day-direction:

::: {.metrics-table}

| Cohort | LONG | SHORT |
|:--|--:|--:|
| v5 · UP-day | +₹122,689 (71% green) | +₹11,747 (30%) |
| v5 · DOWN-day | **+₹79,428 (56% green)** | +₹17,584 (48%) |
| classic · UP-day | +₹59,170 (69%) | −₹3,711 (36%) |
| classic · DOWN-day | +₹19,787 (52%) | **+₹33,457 (59%)** |

:::

**Two refutations:** (1) **shorts profit on their own** (v5 net-positive in both regimes); (2) **"the other way around" works** — longs make money on DOWN days (+₹79,428, 56% green): strong stocks rise in a falling market. **The edge is stock-selection (long strong / short weak); the regime should tilt the ratio, not flip the book.** Re-arm winners on both sides — repeated-entry evidence: **COALINDIA shorted ×6 on 2026-04-10 = +₹23,197**; multi-entry shorts +₹40,714 vs single +₹21,429; multi-entry longs +₹280,808.

## 6.4 Validation 3 — tilt magnitude & trigger

Per-trade P&L bucketed by how red the day actually was:

::: {.metrics-table}

| Severity (NIFTY o→c) | v5 LONG/trade | v5 SHORT/trade |
|:--|--:|--:|
| UP (>+0.15%) | +203 (74%) | +18 (31%) |
| MILD-DOWN (−0.15 to −0.6%) | **+123** (63%) | +11 (47%) |
| HARD-DOWN (< −0.6%) | +49 (45%) | **+82** (53%) |

:::

**Trigger correction:** the short-tilt fires only on **HARD-DOWN (< ~−0.6%)** — mild-down days still favour longs for v5. **Magnitude:** the engine's existing **BEAR 8L/12S** slot split is already in the data-supported zone (hard-down: v5 +₹1,378/day, classic +₹1,023/day). The linear ratio-sim shows more shorts (2L/18S) earns more on paper, but ⚠️ that overstates marginal shorts (best-scored-first), over-concentrates, ignores afternoon-reversal risk, and rests on only 7–8 hard-down days — **do not chase it**. Never zero longs (v5 longs earn +49/trade even hard-down). **So the fix is fast intraday *activation* of the existing 8/12, not a new ratio.**

## 6.5 Validation 4 — fixed ratio vs dynamic allocation

Does the engine adapt its mix to the tape? **No.** Short-share by day severity:

::: {.metrics-table}

| Day | Short share of book |
|:--|--:|
| UP (>+0.15%) | 46% |
| FLAT | 43% |
| MILD-DOWN | 45% |
| HARD-DOWN (< −0.6%) | 45% |

:::

**The mix is flat ~45% whether the day is +0.5% green or −1% red.** The BEAR split exists in code but rarely activates (slow daily regime) → a *de-facto* fixed ratio. **The principled design** (the user's point): direction decided **per-stock by its own trend**, the long/short count **floats** from the opportunity set, and a **net-exposure risk cap** replaces the fixed ratio. This is dynamic market-neutral-with-tilt — what v5 was validated as.

**Honest dependency:** this only beats a fixed mix if the per-stock signal is predictive — and conviction→P&L could not be validated because score wasn't stored on closed trades (§3.2, now fixed). The cross-sectional score is weakly predictive (winner≈loser; IC 0.006), so the driver should be **per-stock trend (VWAP/MA)**, not that score.

## 6.6 The 10% cap — clarification

The "10%" in code is `BASELINE_MAX_POSITION_PCT = 0.10` — **max 10% of pool capital per position (a size/concentration cap), not a loss cap** (loss is bounded tighter by the 1.5–2.25% stop; there's also a 10% *monthly* pool-drawdown breaker). It covers the "max single-name" half of the risk cap but does **not** bound *net directional exposure* — so the dynamic design still needs a net-exposure limit on top. Necessary but not sufficient.

<div class="page-break"></div>

# 7. Features & Tools Built

## 7.1 Red-day watchdog — `scripts/red-day-watchdog.py`
Real-time (5-min) loss attribution: NIFTY direction · per-engine long-vs-short P&L split · regime-mismatch flag · the "if we were short-heavy" counterfactual · one-shot Telegram alert. Read-only, exits at 15:35. Built live during the red day; confirmed the diagnosis and ran all session.

## 7.2 Daily engine compare — `scripts/engine-compare.py` + launchd
A reusable script + `com.tradepilot.engine-compare.plist` (weekdays 15:40 IST) that Telegrams the full engine scorecard (net P&L, WR, L/S split) + a trailing cumulative. Now covers all 5 active engines. Verified live against real data.

## 7.3 Decision dashboard — `docs/decision-dashboard.html` + Flask `/decisions` + pageswitch
A single-source-of-truth strategy/roadmap dashboard, integrated into the live Flask app at `localhost:5050/decisions` (HTTP 200 verified), with a "Decisions" entry added to the global `static/pageswitch.js` nav so it appears on **every** page.

## 7.4 yfinance per-process cache fix — `data_nse.py` + `missed-opportunities-watchdog.py`
The 06-26 data-stall root fix (§3.1). Verified live.

## 7.5 Conviction logging — all engines
The "store everything" fix (§3.2). Verified; applies next launch.

## 7.6 `v5_flip` fast-regime-flip shadow — `scripts/v5_flip-paper-trade.py` + wiring
Same v5 code + an env-gated (`FAST_FLIP=1`) hook in the scan loop. Every **5 min** it re-checks the live NIFTY tape; on a **confirmed hard-down (< −0.6%, 2 consecutive reads)** it sets `state["regime"]="BEAR"` intraday (activating the existing 8/12 slot split via `pm.set_regime` + `rm.regime`); **bidirectional** (reverts to SIDEWAYS on a confirmed green reversal, ≥2 reads); keeps both legs; anti-whipsaw via confirmation + hysteresis. Env-gated so **live v5 is unaffected**. Wired into `launch-market.sh`, `crash-watchdog.sh`, and `engine-compare.py` (roster=5). **Verified:** all scripts compile, `bash -n` clean, roster=5 consistent in both files, env-override functional (`SCAN_INTERVAL_MIN=5`, `_fast_flip` callable), smoke gate PASS exit 0.

**Honest scope:** `v5_flip` is the *stepping-stone* ("fast activation of the existing 8/12 tilt") — the data justified it. The *full* dynamic per-stock-trend allocation + net-exposure cap is deliberately **not** built; it's gated on the conviction→P&L data now being collected.

<div class="page-break"></div>

# 8. Roadmap (all tracks)

| Track | Focus | Status |
|:--|:--|:--|
| **A — Profitability** | RC-1 long-only · RC-2 short-gate · RC-3 entry timing · RC-4 concentrate · (data-stall fixed, roster lean) | In progress; `v5_flip` + `v5_long` testing |
| **B — Autonomy (T3→T4)** | Meta-agent that proposes/auto-applies strategy-param changes | Future, post live track record |
| **C — Competitive moat / product** | Lead with autonomy (uncontested in India); build live execution layer | Designed |
| **D — Compliance** | Paper (zero) → live own-capital (light) → product (heavy) | Phased; D-0 now |
| **E — Validation & risk** | Keep alpha in execution; paper→live trust gate; audited track record; robustness | Ongoing |
| **F — Research follow-ups** | Numerai deep-dive · SEBI RA process · Jarvis Invest analog · **Kite algo-TOS (before go-live)** · Standard Signal EDGAR | Queued |
| **G — Agentic platform** | **BYOB White-Box Agent**; G-0 personal-T4 (9-role DAG + meta-agent + train/eval-namespace) → G-1 invite-BYOB → G-2 beta (RA licence) → G-3 marketplace | Roadmapped; gated on Track A |

**Sequencing rule:** prove profitability → go live cheaply (own capital) → productize into the agentic platform *only if chosen*. The agentic-DAG architecture (G-0) and the overfitting fix (Track A) are the **same** engineering investment — platform and profit converge.

<div class="page-break"></div>

# 9. Learnings Index (DevPilot store)

~20 learnings persisted this arc (`dp lrc recall "tradepilot <topic>"`): edge-source · over-trading · short-book (decisive) · v5_classic dominance · OLD-5tree skeptic · data-stall bug · competitive landscape · SEBI compliance · strategic position (T3) · 3-pillar strategy · red-day live finding · fast-flip design · 2nd-half validation · direction-vs-regime · tilt-magnitude · dynamic-allocation · conviction-logging + v5_flip build · session wrap-up.

# 10. Open Questions & Next Steps

1. **Does the morning loss recover by EOD on down days?** Inferred from aggregates (longs net-positive on down days) — worth a direct intraday-P&L-path check.
2. **Conviction→P&L** — answerable in ~5 sessions now that score is logged; settles the dynamic-allocation design.
3. **Purged folds vs leaky K-fold** in `backtest-honest-fills.py` — determines whether the 5-tree "win" is real before shrinking the live model.
4. **`v5_flip`'s first red day** — does fast-activating the 8/12 tilt cut red-day losses *without* false-triggering on green days? (The decisive live test.)
5. **Reconcile the two long-only experiments** (`v5_long` vs the pre-existing `tradepilot-v5-longonly-ab`).
6. **Net-exposure cap** — the missing risk control for the dynamic phase.
7. **Kite Connect algo-TOS** — does own-account automation below 10 OPS need separate approval? (Gate before any go-live.)

---

*End of report. Companion docs: `ROOT_CAUSE_ANALYSIS_2026-06-24`, `_II_2026-06-26`, `COMPETITIVE_LANDSCAPE_2026-06-28`, `STRATEGY_RESEARCH_2026-06-30`, `DESIGN_fast-regime-flip_2026-06-30`, `ROADMAP_2026-06-28`, `SESSION_CHANGELOG_2026-06`.*
