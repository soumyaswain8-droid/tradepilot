# TradePilot Foundation Review — 2026-06-11

**Trigger:** "Why can't any engine make money?" — a panel-of-5 adversarial audit + 2-month
data analysis + three independent statistical validation tests.

**Headline:** Most engines have no edge. **One engine (v5) is a genuinely validated,
market-neutral, cost-robust strategy.** Tomorrow we run a clean rotation: only validated
engines.

---

## How the verdict evolved (each step overturned the last comfort)

| Evidence | What it said |
|---|---|
| 2 days (Jun 9–10) | "Everything loses / whipsawed" — noise |
| 2 months (~40 days) | "Everything is up" — false comfort |
| Outlier-concentration test | "v4's profit is fake; v5 looks real" |
| NIFTY alpha-beta regression | "v5 has real market-neutral alpha (t=3.0)" |
| Honest-fills backtest (5m replay) | "and it's not an accounting artifact (t=2.73)" |
| Cost-realism stress ladder | "and it's robust to realistic costs (t=2.52 @ 23bps)" |

---

## Engine scorecard (2 months, authoritative)

| Engine | 2-mo P&L | Median day | Top-3 days % of total | Alpha t-stat | Verdict |
|---|--:|--:|--:|--:|:--|
| **v5** | +250,883 | +840 | 54% | **2.7–3.0** ✅ | **VALIDATED — keep** |
| **v5_classic** | +100,819 | +724 | 61% | **2.39** ✅ | Real alpha — keep (secondary) |
| v7_regime | +1,996 (4 days) | — | — | n/a (too new) | Keep as regime experiment |
| **v4** | +272,882 | **₹0** | **103%** | 1.51 (n.s.) ❌ | **RETIRE — no edge, beta + 1 lucky day** |
| v6 / v5_8 / v5_6 / v5_7 / v5_2 / v5_3 | mixed | — | >100% (v6, v5_8) | — | Stay retired |

**v4 detail:** +196,789 on 2026-05-06 = 72% of its 2 months. That day it deployed
**₹6.8M** (vs normal ₹0–1.1M) across 243 trades into a rising market — the day its
regime/size gate was disabled. Brakes off + beta + luck. Median day ₹0; negative without
top-3 days. Not a strategy.

---

## The 5-critic root causes (panel verdict)

1. **Entry gate is relative, not absolute** (`composite_scorer.py:540` `buy_cutoff = n*0.80`)
   — top 20% are *always* bought; the system cannot decline to trade. (3 critics found this independently.)
2. **No validated edge baseline** — WFO OOS Sharpe −0.10, DSR 0.12 (`v7_regime…py:244`);
   ML walk-forward hit-rate 51.6% (coin flip); features dominated by india_vix + nifty → predicts the *market*, not the *stock*.
3. **Regime detector blind to single-day trends** (`regime_detector.py:293`, ±3 votes on slow daily indicators; A/D random-noise fallback `:161`); v4's gate neutered (`v4-paper-trade.py:355`, "always 1.0"). No net-directional cap.
4. **Fill accounting** — stops fill at last 10-min close not stop level (`v5…py:597,635`); 404'd symbols silently dropped from risk (`:182,774`); no staleness guard. **(Empirically only 0.7% impact on v5 — see below.)**
5. **ML label↔exit mismatch** — model predicts open→close return but trades exit on SL/TGT brackets (`ml_engine.py:305`); 80% win-rate target is a fantasy that *causes* the SL>>TGT bleed (sane target 52–55%).

---

## The three validation tests v5 PASSED

### 1. Beta-neutralization (alpha vs NIFTY, intraday open→close, 35 days)
- v5: **α = ₹7,226/day, t = 3.00, p = 0.005**; β not significant (t=0.94); R² = 2.6%.
- v5_classic: α t=2.39 (sig), β n.s. — corroborates.
- v4: α t=1.51 (NOT sig), β t=2.01 (sig) → pure beta. Minus its outlier day: α t=1.24 (zero).

### 2. Honest-fills backtest (`scripts/backtest-honest-fills.py`, 5-min intraday replay)
- Books stops the live engine missed between 10-min scans, at the stop level.
- Impact over ~1,800 trades: **₹1,635 (0.7%)** — 20 trades re-priced.
- Critic-4's 20–40% inflation hypothesis **refuted for v5** (liquid names + 1.5% stop + 10-min scan rarely round-trip).
- Re-run regression on honest series: **α = ₹6,370/day, t = 2.73, p = 0.01.** Survives.

### 3. Cost-realism stress ladder (re-price at 12→35bps, re-run regression each level)
- v5: 1,950 trades, ₹24.0M turnover, avg notional only ₹12,304/trade.

| Cost | Net | Alpha/day | t(α) | Sig? |
|--:|--:|--:|--:|:--:|
| 12 bps (engine) | 221,456 | 6,418 | 2.76 | ✅ |
| 23 bps (realistic) | 195,608 | 5,677 | 2.52 | ✅ |
| 35 bps (pessimistic) | 167,411 | 4,868 | 2.24 | ✅ |

- **Break-even cost ≈ 105 bps (9× current).** Alpha loses significance only above ~45 bps.

---

## Open question (the next study): CAPACITY

All of v5's robustness holds **at ₹12k/trade.** Scale toward real capital and slippage
grows non-linearly (large orders move the market). v5 is validated **to deploy at small
size**; how much capital it can absorb before slippage erodes the edge requires a
slippage-vs-order-size/ADV model — not flat bps. **This is the gating question before real money.**

---

## Decision for tomorrow

Run a clean rotation: **v5 (primary), v5_classic (secondary), v7_regime (regime experiment).**
**Drop v4** from `launch-market.sh`. Stop spending compute validating losers.

*All findings also persisted to DevPilot `learnings` (category: validation/architecture/bug-pattern, project: tradepilot, 2026-06-11).*
