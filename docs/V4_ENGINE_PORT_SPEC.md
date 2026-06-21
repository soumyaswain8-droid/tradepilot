# v4 Engine Port Spec — Old (winner) + Current's Safety Layer

**Date:** 2026-06-05  ·  **Basis:** A/B Day-1 result — old 5-tree engine +₹21,171 (72% WR) vs current 1,735-tree −₹4,049 (41% WR), clean apples-to-apples day. Delta +₹25,220 for OLD.

**Goal:** Make the OLD engine (commit `0b9ff84`, Apr-23) the new LIVE v4, porting ONLY the safety/data-quality fixes from the current engine — never the alpha-changing parts.

## DROP (the alpha regression — caused the collapse)
- Retrained **1,735-tree** `lgbm_intraday.txt` → revert to the **5-tree** model.
- `tiered_scorer.py` + `config/tiers.json` + tiered models (broad/elite/large_cap/mid_cap) — the overfit culprit (commit 1d174bc).

## PORT from current (safety/data-quality ONLY — does not touch stock selection)
1. **NaN-price guard (May-8, MANDATORY)** — `composite_scorer.score_all_stocks` downgrades NaN/non-positive priced stocks to HOLD; `position_sizer` explicit NaN check + logging. Old engine PREDATES this and is exposed to the "38 of 40 BUYs vanish silently" cache/NaN-poisoning bug. Must port first.
2. **Market-hours / 09:30 warm-up guard** — already prototyped in the A/B runner; fold in cleanly.
3. **3-tier kill switch** — ABS_DAILY_WARN_RS −2,500 / SOFT_HOLD −5,000 / HARD_KILL −10,000 (replaces old flat kill).
4. **MVP guards (May-4)** — corp_actions filter (skip stocks within ex-date ban window), ABS_POSITION_SL_RS −25,000 per-position floor, STOCK_LOSS_EXIT_PCT −10% outer floor, MAX_LOSSES_PER_STOCK_PER_DAY 2.
5. **preflight.py** — pre-launch config/boot checks (ops safety).

## Already in BOTH (no action)
Circuit-breaker (5 consecutive losses), VIX sizing (>18 → 0.5x), bear-mode sizing (0.5x), daily-loss kill switch (3%), max-reentry (1/stock/day).

## EVALUATE SEPARATELY (alpha-touching — own A/B, do NOT assume good)
- `candle_patterns.py` — old composite_scorer does not use it; current does. Test its individual contribution before adding.
- position_sizer cap **20% → 15%** per stock — affects returns; A/B it.

## Build order
1. Branch/snapshot current live v4 (preserve — never delete; archive as the A/B challenger).
2. Bring old 5-tree model + old composite_scorer as the live base.
3. Port items 1–5 above (safety layer), starting with the NaN guard.
4. Smoke-test (boot, model loads, NaN day simulated).
5. Re-A/B for 2-3 sessions (old+safety as "live-candidate" vs current) before final promotion.
6. Override expires 2026-07-15 — decide promotion well before.
