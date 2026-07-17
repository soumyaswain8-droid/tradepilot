# v5_chop — Chop-Filter Shadow Engine (Design)

**Date:** 2026-07-17 · **Author:** Soumya Swain · **Status:** Approved design, pre-implementation

## Problem

June-16 → July-16 (21 clean sessions): the roster realized +₹21,587 while the audits identify ₹3,59,201 left on the table (~₹17.1k/day). v5's win rate collapsed from April's 75% to 48% at the same ~55 trades/day, and cost drag rose 8× (₹2,956 → ₹23,831). The decomposition is symmetric whipsaw, not a bad book: WRONG_DIRECTION ₹106k + SHORTED_RISER ₹105k + EXIT_TOO_EARLY ₹53k.

Root cause: **the engine has only ever made money on trending days.** By declared regime, v5 lost ₹766/day across the 19 SIDEWAYS sessions and made +₹2,240 on the single BULL day. April was a trending month; the last month was chop. The regime detector's SIDEWAYS band (score −3..+3 of ±6) captures 86% of days, so "regime" carries almost no sizing information. Meanwhile four of the month's best days (+₹6–7.5k) also occurred on SIDEWAYS labels — days that trended intraday. A hard sit-out is therefore wrong; the engine must **trade less and smaller in chop, and detect intraday trend and re-engage.**

Decision (2026-07-17, Soumya): build v5_chop = mode ladder at the entry choke-point (A) **plus** allocation-multiplier plumbing through pool budgets (B), ML-free, validated by sensor backtest then 2-week shadow. The ML rebuild proceeds as a **parallel workstream** with its own spec (§8).

## 1. Sensor — TrendScore (0–100), recomputed each scan

| Input | Weight | Source | Definition |
|---|---:|---|---|
| Tape efficiency | 40% | NIFTY 5-min bars since open (same fetch as fast-flip) | \|net move since open\| ÷ Σ\|bar-to-bar moves\|, scaled 0–100. Trending day ≈ high even if net % small; whipsaw ≈ 0. |
| Breadth direction | 40% | `prototype/v5/market_breadth.py` (exists, currently unused for sizing) | Blend of % NIFTY-200 advancers (distance from 50%) and Δ(% above 20-SMA) vs yesterday, scaled 0–100. |
| Premarket regime score | 20% | existing 6-indicator detector | \|score\| / 6 × 100, so declared BULL/BEAR days start closer to TREND. |

**Mode mapping:** CHOP < 35 ≤ NEUTRAL < 65 ≤ TREND. Thresholds are priors — Gate 1 calibrates them.
**Hysteresis:** mode changes require 2 consecutive scans (anti-whipsaw, same pattern as fast-flip's confirmation).
**Failure posture:** if breadth or tape inputs are unavailable (data outage), TrendScore degrades to CHOP — consistent with DATA-GUARD's fail-closed philosophy for entries.

## 2. Intervention A — entry ladder in `deploy_signals`

| Mode | Max new entries/scan | Size multiplier | Conviction floor |
|---|---|---|---|
| CHOP | 3 | 0.40× | top quartile of the scan's signal scores |
| NEUTRAL | 8 | 0.70× | ≥ median |
| TREND | v5 current behavior | 1.00× | v5 current |

Implemented as a single gate + parameter lookup at the top of `deploy_signals` (the same choke-point as DATA-GUARD), env-flagged `CHOP_FILTER=1` so live v5 is untouched.

## 3. Intervention B — capital plumbing

The mode drives the regime detector's existing **allocation multiplier** into `pool_manager` budgets: CHOP 0.5×, NEUTRAL 0.8×, TREND 1.0× of deployable capital. Freed budget restores automatically when TREND confirms. **Exits are never gated** (same principle as DATA-GUARD: only new risk is throttled).

Note: A and B stack deliberately — in CHOP a position is 0.40× size inside a 0.5× budget (~0.2× effective exposure vs v5). This double brake is intentional for the first shadow run; Gate 2 data decides whether to relax one dial.

## 4. Packaging

- `scripts/v5_chop-paper-trade.py` wrapper (runpy pattern, like v5_cut) setting `ENGINE_NAME=v5_chop`, `CHOP_FILTER=1`, `ML_SCORE_WEIGHT=0` (ML-free — ML is selection-neutral, IC 0.006, TP-CLN-008).
- Own state dir `docs/paper-trades/v5_chop/`, own dated logs.
- Wired into `launch-market.sh` ENGINES, `crash-watchdog.sh`, `engine-compare.py` (roster 6 → 7).
- New module `prototype/v5/trend_mode.py` (pure functions: `tape_efficiency(df)`, `breadth_score(...)`, `trend_score(...)`, `mode_for(score, prev_modes)`) — unit-testable without network, TDD like `tests/test_data_guard.py`.

## 5. Validation gates

**Gate 1 — sensor backtest (~1 day, no engine code):** replay TrendScore across 2026-06-16 → 2026-07-16 using stored daily CSVs/breadth data and each day's realized P&L.
*Pass:* days flagged TREND (at any point intraday) contain ≥70% of the month's gross positive P&L, AND days flagged CHOP all day contain ≥70% of the gross losses. Threshold calibration (35/65) happens here.
*Fail:* kill or re-spec the sensor. No engine work begins until Gate 1 passes.

**Gate 2 — shadow (2 weeks):** v5_chop runs alongside v5.
*Promote to live only if:* better net P&L AND lower cost drag AND max drawdown no worse than v5. Early-kill if v5_chop trails v5 by >₹5k after week 1 with no offsetting drawdown advantage.

## 6. Testing

- Unit: `tests/test_trend_mode.py` — tape-efficiency extremes (pure trend=100, pure whipsaw≈0), breadth blend bounds, mode hysteresis (no flip on single scan), fail-closed on missing data.
- Ladder: `deploy_signals` respects per-mode caps/size/floor (extend the importlib test pattern).
- Gate 1 backtest script doubles as the regression harness for future threshold changes.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Sensor lags real trend starts (late re-engage) | Hysteresis is 2 scans (~20 min max); Gate 1 measures capture of green-day P&L explicitly |
| Extra yf fetch per scan | Reuses fast-flip's fetch; breadth from cached daily CSVs |
| Mode flapping around thresholds | Hysteresis + Gate-1-calibrated bands |
| Shadow verdict polluted by a trending fortnight (filter never engages) | Gate 2 also reports mode-distribution; extend shadow if <5 CHOP days observed |
| Roster bloat (7 engines) | v8 and v5_chop both have kill/promote criteria and dates |

## 8. Parallel workstream — ML rebuild (separate spec to follow)

Milestones only (owns its own design doc):
1. **Meta-labeling dataset** from logged trade outcomes (conviction logging live since 06-30); salvage lessons from failed v8_ml 5-tree attempt.
2. **CPCV/purged cross-validation** producing the PBO report Sarathi **ML-001** requires (PBO < ceiling).
3. **Ship-gate wiring**: `scripts/sarathi/verify.py` passes legitimately; retire the CEO-override chain. (Gotcha: verify.py rewrites `verification_report.json` with `override: None` — re-adding the override after any verify run is required until this ships.)
4. **Retrain cadence + freshness automation** so the 3-day freshness guard passes without human intervention.

Deadline context: CEO override extended to **2026-07-22**; extend again if milestone 3 hasn't shipped — do not let engines die at open again.

## Success criteria (the point of all this)

Capture trend months (April profile: ₹+11.5k/day at 75% WR) while cutting chop-month bleed toward zero. Concretely for the shadow: on CHOP-flagged days v5_chop's gross loss < 40% of v5's; on TREND-flagged days ≥ 90% of v5's gross profit; overall lower cost drag from the reduced churn.
