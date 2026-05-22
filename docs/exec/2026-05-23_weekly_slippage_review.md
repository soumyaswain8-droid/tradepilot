# Execution Analyst · Weekly Slippage Review · Week of 2026-05-18

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — Execution Realism |
| **Version** | `v0.1.0` |
| **Status** | Sprint 1 instrumentation complete |
| **Created** | 2026-05-23 |
| **Updated** | 2026-05-23 |
| **Scope** | Exit-leg slippage only (entry hook deferred to Sprint 2) |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya — Execution Analyst, TradePilot |
| **Email** | soumya@sidewall.in |
| **LinkedIn** | [linkedin.com/in/kishorer747](https://www.linkedin.com/in/kishorer747) |

:::

## TL;DR

- **Realized exit slippage is ~210 bps adverse, ~20x our 10 bps modeled assumption.** Across 419 exit legs, v5 mean = 215 bps, v5_classic mean = 208 bps. Tails are nasty (P95 ~388 bps).
- **Both engines are essentially break-even (v5: -₹1,047) or flat (v5_classic: ₹0) after real slippage.** The headline "₹40k weekly P&L" disappears entirely when the 12 bps model is replaced with measured fills — the model was hiding ~₹42k/week of execution cost per engine.
- **Slippage is reason-driven, not size-driven.** STOPLOSS legs leak ~283 bps adverse; TARGET legs gain ~58 bps favorable. Trade size has near-zero effect (all legs are <₹50k). The problem is exit logic, not order size.

## Aggregate Stats Per Engine

| Engine | Legs | Mean bps | Median bps | P95 bps | P5 bps | Weighted Mean bps | Implied ₹ Cost |
|:--|---:|---:|---:|---:|---:|---:|---:|
| v5 | 228 | +215.08 | +210.18 | +387.51 | -11.03 | +210.58 | ₹44,674 |
| v5_classic | 191 | +207.77 | +210.00 | +390.54 | -23.48 | +205.02 | ₹42,203 |
| **Total** | **419** | **+211.75** | **+210.06** | **~389** | **~-17** | **+207.84** | **₹86,877** |

Total weekly traded value: ₹41.8L across both engines. Implied weekly execution drag: **₹86.9k vs ₹4.2k** if our 10 bps assumption held — a **20x miss**.

## Slippage vs 10 bps Assumption

Our backtest assumed 10 bps adverse exit slippage; the realized number is **~210 bps adverse** — twenty times worse. Even the P5 (best 5% of fills) only reaches -11 to -23 bps, meaning fewer than 1-in-20 exits beat the modeled cost. The distribution is right-skewed but not bimodal — the bulk of fills cluster around 200-250 bps, indicating this is structural (driven by exit type and likely market-order behavior on illiquid mid-caps at thin moments), not a few outlier fat fingers. **The 10 bps model is invalidated.**

## By Exit Reason

| Reason | n | Mean bps | Median bps | Implied ₹ Cost | Verdict |
|:--|---:|---:|---:|---:|:--|
| TARGET | 39 | **-58.54** | -26.18 | -₹2,759 | Favorable — hypothesis confirmed |
| STOPLOSS | 168 | **+282.66** | +269.19 | ₹49,501 | Severely adverse — hypothesis confirmed |
| SIGNAL_FLIP | 51 | +237.74 | +246.16 | ₹14,747 | Adverse — flip lag is costly |
| TIME_EXIT | 119 | +186.45 | +203.98 | ₹18,881 | Adverse — end-of-day liquidity drain |
| FLAT_FORCE_EXIT | 42 | +219.17 | +206.14 | ₹6,507 | Adverse — square-off urgency tax |

Hypothesis fully verified. **TARGETs gain ~58 bps** (we sit on the bid/ask and get filled at a favorable level). **STOPLOSSes lose ~283 bps** (we chase a moving price). STOPLOSS alone accounts for ₹49.5k (57%) of the weekly drag despite being 40% of legs.

## By Trade Size

| Bucket | n | Mean bps | Weighted Mean bps |
|:--|---:|---:|---:|
| <₹10k | 219 | +211.91 | +202.99 |
| ₹10k-25k | 191 | +212.13 | +210.64 |
| ₹25k-50k | 9 | +199.59 | +200.13 |

All legs fall under ₹50k, so the classic "big-order pays more" effect is not observable in this sample. Within the observable range, **size is essentially neutral** — slippage is uniform across small/medium tickets. The cost driver is exit reason, not size.

## Cost-Corrected Weekly P&L

| Engine | Modeled P&L (12 bps) | Realized P&L (actual fills) | Cost Delta | Realized / Modeled |
|:--|---:|---:|---:|---:|
| v5 | +₹41,081 | **-₹1,047** | -₹42,128 | -2.5% |
| v5_classic | +₹39,733 | **+₹0** | -₹39,733 | 0.0% |
| **Combined** | **+₹80,814** | **-₹1,047** | **-₹81,861** | **-1.3%** |

**Both engines are not profitable after realistic exit costs.** The entire modeled edge was being eaten by un-modeled execution cost. This invalidates promotion of either engine to live capital until exit costs are reduced or modeled correctly.

## Sprint 2 Recommendation

**Replace market-on-touch STOPLOSS with a 2-tick limit + 3-second TIF, then market.** STOPLOSS is the single largest cost source (₹49.5k/week, 283 bps mean). The current implementation appears to be issuing market orders the instant the stop is breached — which guarantees we pay full spread plus impact at the worst moment. A bounded-aggression replacement (limit at stop-trigger + 2 ticks, time-in-force 3 seconds, then market sweep if unfilled) should compress STOPLOSS slippage by 100-150 bps based on standard execution-algo lit. Even halving STOPLOSS adverse to ~140 bps recovers ~₹25k/week, which is the difference between break-even and a viable strategy.

Secondary: instrument the entry leg (Sprint 1 deferred) so we can compute round-trip cost and stop reasoning about exits in isolation.
