# TradePilot Quant System — Roadmap & Decisions

*Synthesized from the curated research sweep (2026-06-16) + the first real backtest. Honest, cost/capacity-aware — per Sarathi rules.*

## The honest thesis
There is **no magic edge to buy or invent** — 64–85% of published equity anomalies don't replicate (Hou-Xue-Zhang; Harvey-Liu-Zhu demand t>3). Factors *do* generalize out-of-sample across 93 countries (Jensen-Kelly-Pedersen 2023), so disciplined factor edge is real but *commodity and decaying* (~58% post-publication). **The edge for us comes from engineering correctness and discipline, not the model** — the single most-cited result: a data-leakage/executability fix added **+0.44 Sharpe** vs only **+0.12** from a fancier model. So: get the plumbing honest first; fancy ML last.

## Frameworks to build on (decided)
| Layer | Pick | Why | India gap to close |
|---|---|---|---|
| Backtest + execution spine | **NautilusTrader** | Rust-native, event-driven, *identical code research↔live* | No official NSE adapter — backtest-first; route live via existing Zerodha/engine integration later |
| Research + factor + ML lab | **Microsoft qlib** (MIT) | Full pipeline, 24+ models, Alpha158/360 factor libs | No India dataset — build a custom NSE data loader (our `quant/data` cache is step 1) |
| Discipline layer | **AFML** (López de Prado) | triple-barrier, meta-labeling, **purged/embargoed CV**, feature-importance research | Methods, not a package — implement directly |

## First real finding (already built)
`quant/backtest_factor.py` on 5y / 200 NSE names, net 23bps: **cross-sectional momentum edge is at LONG horizons, not intraday.** Best: 252-day lookback / monthly hold → **Sharpe ~1.1, +9.3%/yr, IC 0.047, −9.2% maxDD.** Short-horizon (5-day) momentum is dead net of cost. *This locates a real, extendable positional book.*

**But it's an optimistic upper bound:** Indian survivorship bias runs **3.5–4.4%/yr**, so the real Sharpe is meaningfully lower (~0.7–0.9). Must be confirmed with survivorship correction + purged-CV before it's bankable.

## Prioritized plan (highest leverage first)
1. **Honest data layer** *(highest leverage — research's #1)*: extend `quant/data` toward point-in-time + survivorship-bias-free (NSE index-membership history; TickData for inactive names later) + executability flags (no trading on halted/limit days) + realistic per-name costs/ADV capacity.
2. **Purged/embargoed CV validation** of the momentum finding (AFML) — turn the upper-bound Sharpe into a defensible one.
3. **Multi-horizon book structure**: positional factor core (the momentum finding) + the validated intraday v5 sleeve as the "nimble" overlay (GSAM-style blend), with risk budgeting across horizons.
4. **ML last, disciplined**: only after 1–3, use qlib + AFML triple-barrier/meta-labeling, validated by feature-importance (NOT repeated backtesting — ~20 iterations finds a spurious strategy).
5. **Feed the live engines**: route only OOS-validated, capacity-checked signals into v5 and a new positional engine.

## What we are NOT doing (per rules)
Not claiming "unbeatable/best-in-world." Not trusting backtest Sharpe before survivorship + purged-CV. Not iterating model-on-backtest (false-discovery trap). Not deploying any signal without OOS + cost/capacity validation.

## Top learning resources (ranked)
1. AFML (López de Prado) + "10 Reasons" whitepaper — the discipline layer
2. Replication-crisis papers: Hou-Xue-Zhang, Harvey-Liu-Zhu, McLean-Pontiff, Jensen-Kelly-Pedersen 2023
3. WorldQuant University — free accredited MScFE
4. Grinold-Kahn *Active Portfolio Management*; Narang *Inside the Black Box*
5. qlib + NautilusTrader docs/codebases (learn by reading the engines)

## Open questions (need data/decisions)
- Real per-trade cost + ADV capacity for tradable NSE mid/large-caps → AUM ceiling per horizon.
- India survivorship-free EOD/fundamentals/corp-actions/FII-DII/OI source (TickData = paid intraday only, verified).
- Signal-combination math across horizons (risk parity vs HRP).
- NautilusTrader: backtest-only vs build NSE live adapter.

## Validation result (2026-06-16, TPQ-007)
Momentum 252d/21d: raw Sharpe 1.12 but **Deflated Sharpe 74% = FAIL** (multiple-testing), real Sharpe **~0.6** after survivorship haircut, positive 4/5 years. **Promising but NOT bankable as-is** — treat as a modest sleeve; needs survivorship-free data + pre-registered tests, not searched configs.

## DEFINITIVE momentum verdict (2026-06-16): MIRAGE
Survivorship-free + corp-action-adjusted: Sharpe **0.31, IC 0.000** = no edge. The biased 1.12 was ~all survivorship bias. **Do NOT build a positional momentum book.** Multi-horizon expansion needs a different edge source (v5 intraday rule-logic + engineering correctness, or validated India factors), NOT momentum.

## META-VERDICT (2026-06-16): standard factor route is dead on clean data
Tested all standard factors survivorship-free + adjusted: momentum IC 0.000, 3-mo mom -0.027, 1-mo reversal -0.018, 1-wk reversal -0.006, low-vol +0.022 — **all ~zero IC, no real edge.** Long-horizon factor alpha is NOT viable on honest Indian data (2021-26). **Real path:** harden v5 intraday rule-edge (live, net-of-cost) + microstructure — not a factor book. Awaiting founder decision on direction.
