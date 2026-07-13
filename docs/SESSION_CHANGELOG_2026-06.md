# TradePilot — Session Changelog (June 2026 arc)

*Complete record: every finding, debug, fix, feature, validation, research output, and design — with the doc + learning where each lives.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot (autonomous agentic trading) |
| **Document** | Master session changelog / index |
| **Version** | `v1.0.0` |
| **Period** | 2026-06-22 → 2026-06-30 |
| **Status** | Living index — append new work here |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@sidewall.in |

:::

---

## A. Root-cause investigation — why we were losing

| Finding | Verdict |
|:--|:--|
| The edge is **execution discipline, not ML/AI** | On the 82%-WR original, winner score ≈ loser score; ML IC 0.006 |
| Complexity **diluted** the edge | Win-rate 82% → ~48% as trades/day 17 → 45 (NIFTY-50→200, +shorts, 4 pools) |
| `FLAT_FORCE_EXIT` — **exonerated** | Trade-level audit: it *helped* (+₹30, +₹299) on the days it was blamed |
| **Late entry** is the day-to-day bleed | v5 enters winning names 30–60 min late (rescore loop) → booked as STOPLOSS not TARGET |
| **Over-trading = cost drag** | Gross +₹4,691 but cost −₹7,153 = net −₹2,462 over 8 days; excess churn = 205% of net |
| **The SHORT book is the net bleed** | Longs +₹1,149 vs shorts −₹3,611 (06-16..25); shorts hit TARGET only 4.1% (longs 8.5%) |
| **v5_classic (frozen original) beats live v5** | +₹111,803 vs +₹116,357 over 45 sess, but v5's lead is a 2-outlier-day mirage; June: classic +₹12,891 vs v5 +₹690 (18×) |
| **OLD 5-tree model** (sibling A/B) | +₹122k headline is a leverage(313%)+gross+72%-from-4-days mirage — BUT the 5-tree beating the 1,735-tree is real overfitting evidence |

**Docs:** `ROOT_CAUSE_ANALYSIS_2026-06-24.{md,pdf}`, `ROOT_CAUSE_ANALYSIS_II_2026-06-26.{md,pdf}`.

## B. Debugs / data-integrity fixes

| Bug | Root cause | Fix |
|:--|:--|:--|
| **06-26 all-day data stall** (engines alive, 0 trades) | yfinance shared SQLite tz-cache contention under concurrent multi-process load → `OperationalError: unable to open database file` → downloads return None | Per-process cache isolation (`yf.set_tz_cache_location` keyed by ENGINE_NAME/PID) in `data_nse._get_yfinance()` + `missed-opportunities-watchdog.py`; cleared corrupt shared db. ✅ verified live download works |
| **Conviction not stored on closed trades** | `close_position` rebuilt the record from a hardcoded subset, dropping `score`/`reasons` that *were* on the open position | Carry score/direction/reasons/sl_price/target_price/entry_date/trailing_activated into closed record across **all** engines (v5 family + v5_classic + v7_regime) |

## C. Engine roster consolidation

- **6 → 4 lean roster** (06-26 audit): retired `v5_noml` (redundant — ran v5 twice), `v5_apr` (tracked v5 +₹78/9d), `v7_regime` (flat + WFO-negative). State preserved (commented, not deleted).
- **+ v5_long** (RC-1 long-only) and **+ v5_flip** (fast regime-flip) → **roster now 5**: v5 · v5_classic · v5_long · v5_cut · v5_flip. Consistent across `launch-market.sh`, `crash-watchdog.sh`, `engine-compare.py`.

## D. Competitive & strategy research

| Output | Verdict |
|:--|:--|
| Competitive landscape (105-agent deep-research) | **No direct competitor.** Peers are ~95% research prototypes; only commercial one (Standard Signal) unverified |
| Autonomy benchmark | TradePilot = **T3 (Conditional Autonomy)** — same level credible real funds run at |
| Tier-2 India | **Zero Indian platforms are agentic** (all rule-based builders) — category gap |
| Tier-4 funds | Every real-money fund keeps a human in the strategy loop; Numerai closest verified AI-native |
| SEBI compliance | Paper = **zero** obligations; live own-capital = **light**; product = **heavy** (RA licence, empanelment, ISO 27001) |
| 3-pillar strategy | Profitability + UX + platform all share one spine: a **simple, explainable, clean-execution decision pipeline** |

**Docs:** `COMPETITIVE_LANDSCAPE_2026-06-28.{md,pdf}`, `STRATEGY_RESEARCH_2026-06-30.{md,pdf}`, `ROADMAP_2026-06-28.{md,pdf}`.

## E. Red-day / regime-flip work (06-30) — Sarathi-disciplined validations

Live red day (NIFTY −0.73%) → longs bled, shorts green → built diagnosis + design. **The data corrected coarse framings four times:**

| Claim tested | Result |
|:--|:--|
| "No flips after 13:30" | **REFUTED** — v5 post-1pm entries +₹30,515 vs morning −₹2,724. Rule removed; flip is bidirectional + all-session |
| "short=red, long=green" (flip the book) | **REFUTED** — edge is stock-selection; longs profit on DOWN days (+₹79,428, 56% green); shorts profit on their own; COALINDIA shorted ×6 = +₹23,197. → **tilt the ratio, don't flip** |
| Tilt magnitude / trigger | Existing **BEAR 8/12 is right**; trigger is **hard-down < −0.6%** (mild-down still favours longs), NOT −0.5%; don't chase all-in (linear-model + reversal + small-sample risk) |
| Fixed ratio vs dynamic | Engine **does not adapt** (short-share flat ~45% across up/down days). Principled design = **per-stock trend direction + net-exposure risk cap**, not a fixed ratio — but needs conviction data (now logging) |

**Docs:** `DESIGN_fast-regime-flip_2026-06-30.md`.

## F. Features / tools built

| Feature | What |
|:--|:--|
| `scripts/red-day-watchdog.py` | Real-time loss attribution (long vs short) + red-day counterfactual + Telegram alert |
| `scripts/engine-compare.py` + launchd | Daily 15:40 Telegram four/five-way engine scorecard (auto) |
| `docs/decision-dashboard.html` + `/decisions` route + pageswitch nav | Decision dashboard integrated into the live Flask dashboard (every page) |
| yfinance per-process cache fix | Data-stall root fix in `data_nse` + watchdog |
| Conviction logging | score/reasons/etc. on closed trades, all engines |
| `scripts/v5_flip-paper-trade.py` + wiring | Fast intraday regime-flip shadow (5-min tape → BEAR 8/12 tilt on confirmed hard-down, bidirectional) |

## G. Learnings persisted (DevPilot store)

~20 learnings stored this arc (search `dp lrc recall "tradepilot"`): root-cause, edge-source, over-trading, short-book, v5_classic, OLD-5tree, SEBI, competitive, autonomy-T3, 3-pillar, red-day, fast-flip design, 2nd-half validation, direction-vs-regime, tilt-magnitude, dynamic-allocation, conviction-logging + v5_flip build.

## H. Project memory

`tradepilot-root-cause`, `tradepilot-competitive-roadmap` (+ MEMORY.md index).
