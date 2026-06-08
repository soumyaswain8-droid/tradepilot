# Long / Short / Flip — Two-Layer Directional Spec for TradePilot

*Source: deep-research run 2026-06-08 (5 angles, 23 sources, 101 claims → 25 verified → 16 confirmed / 9 killed by 3-vote adversarial check). Cited but practical.*

## Why this exists
Today (BEAR, Nifty -0.94%) v4 (long-only) lost -Rs8.3k while v5 (short-tilted) made +Rs465. The audit traced the entire loss to one class — `LONG_IN_BEAR` (78 trades, -Rs18.8k). Root cause: the scorer emits **0 SELL** signals, so the engine has no sanctioned way to be short and no gate to stop longing a falling market. This spec is the fix: a **regime gate** that decides the *allowed side*, plus an **intraday state machine** that flips within it.

---

## Layer 1 — Daily allowed-side regime (the GATE)

Computed once per day per stock on **daily** bars. Output: `allowed_side ∈ {LONG_ONLY, SHORT_ONLY, BOTH, FLAT}`.

| Step | Rule | Data (have it?) |
|---|---|---|
| **Trend permission** | `ADX(14) > 25` → trend, directional trades allowed. `ADX < 20` → **FLAT** (stand aside). 20–25 = no-new-entry buffer. | ADX/DMI ✅ |
| **Direction** | `+DI > -DI` → bullish (long side); `-DI > +DI` → bearish (short side) | ADX/DMI ✅ |
| **Confirm** | SMA50 slope: `SMA50[today] - SMA50[5d ago] > 0` = up-regime, `< 0` = down-regime | OHLCV ✅ |
| **Volatility bucket** | `ATR%(14) = ATR/Close` vs its ~100-day average → Low / Mid / High (sizing input) | OHLCV ✅ |

**Decision:** `allowed_side = f(ADX gate, +DI vs -DI, SMA50 slope)`.
- Down-regime (-DI>+DI **and** SMA50 sloping down, ADX>25) → **SHORT_ONLY** — *longs disabled.* This is exactly what would have stopped today's bleed.
- Up-regime → LONG_ONLY. Mixed/weak → FLAT.

> **The ADX gate is non-negotiable.** The +DI/-DI direction rule only survived 2-1 in verification and is repeatedly called "a recipe for disaster in a ranging market" *without* the ADX filter. DI gives direction; **ADX gives permission.** Skipping the gate reproduces today's shorting-risers / longing-fallers failure.

*Sources: Fidelity/Wilder (ADX>25 trend, <20 no-trend; DI relationship), QuantMonitor (SMA50-slope + ATR% buckets).*

---

## Layer 2 — Intraday entry / flip state machine

Runs on intraday bars, **constrained by Layer 1's `allowed_side`**. States: `FLAT → LONG → SHORT → FLAT`.

- **Engine: Supertrend (ATR-based) as stop-and-reverse.** Two native states (long/short); flips when price *closes* on the opposite side of its active ATR band. The band is path-dependent — ratchets up in uptrends, down in downtrends — so it doubles as a **trailing stop** and resists premature flips. *(Source: FXEmpire + canonical TradingView formula.)*
- **Entry trigger:** `+DI crosses above -DI` (long), gated by `ADX>25`. For shorts, drive off the **-DI>+DI relationship**, *not* a mirror "-DI crosses below +DI" event — that mirror phrasing was **refuted 0-3**.
- **FLAT overlay (TradePilot's addition):** even if Supertrend signals a side, force FLAT when Layer 1 revokes permission (ADX<20, or the side isn't allowed).
- **Chop protection (the core anti-whipsaw):** stand aside when `ADX<20` **or** the Supertrend line stays flat >~5 candles while price keeps crisscrossing it. Supertrend whipsaws (4–6 flips, ~45-55% win) in range-bound tape — gating fixes it. *(Verified 3-0.)*

### Flip rule, plain language
> Be on the side Supertrend says, **only if** Layer 1 allows that side **and** ADX>25. The moment Supertrend closes across its band → reverse (if the new side is allowed) or go FLAT (if not). If ADX drops below 20 → FLAT regardless.

---

## Regime-type detection (trend vs mean-revert vs chop)

Use the **Hurst exponent (H)** as a *soft* per-horizon hint:
- `H > 0.5` → trending/persistent → use the Supertrend+DMI trend logic above.
- `H < 0.5` → mean-reverting → use mean-revert logic (e.g. fade extremes to VWAP).
- `H ≈ 0.5` → random walk → prefer FLAT.

**Caveats (verified):** Hurst is **timeframe-dependent** — compute it *separately* for daily and intraday windows. It needs **100–200+ bars**, is unstable near 0.5, overestimates on small samples (use the **DFA** estimator), and **describes the recent window, not the future** — it is a classifier, not a predictor. The claim that Hurst can *directly switch* the engine was **refuted 1-2**: use it only as a hint, **confirmed by ADX**, never as a standalone switch. *(Source: Macrosynergy + peer-reviewed scale-dependence literature.)*

---

## How this kills today's failure mode

| Today's mistake | What stops it here |
|---|---|
| `LONG_IN_BEAR` (78×) | Layer 1 sets SHORT_ONLY in a down-regime → longs disabled |
| `SHORTED_RISER` (22×) | ADX gate + only short when -DI>+DI; intraday rule: never short a stock green/above VWAP |
| Trading in chop | ADX<20 → FLAT; Supertrend flat-line stand-aside |
| No SELL signal exists | Layer 1 produces an explicit SHORT side — the missing tier |

---

## Validation / backtesting (strongest-sourced section — primary papers)

1. **Walk-Forward Optimization (minimum bar):** optimize on in-sample window → validate **only** on the next out-of-sample window → slide forward → aggregate **only OOS** results. A plain chronological split or plain walk-forward is **insufficient** (walk-forward ranked weakest for overfitting control).
2. **Report the Deflated Sharpe Ratio (DSR):** discounts the selection bias from testing many strategy variants (the more variants you try, the higher a Sharpe you'll hit by chance). *(Bailey & López de Prado, primary.)*
3. **Strict point-in-time data** — no look-ahead bias; only use info available at the historical bar.
4. **Tune ALL defaults via WFO** — the ADX thresholds, 5-day SMA lookback, 100-day ATR baseline, and Supertrend ATR-multiplier are arbitrary textbook defaults, **not** validated numbers. Do not ship them as-is.
5. *Optional upgrade:* Combinatorial Purged CV (CPCV) ranks best on overfitting in a 2024 Elsevier study, but the panel **declined to mandate it** (heavier to implement). WFO+DSR first.

---

## Do NOT hardwire (explicitly refuted this run)

- **FII/DII** directional-sign, magnitude thresholds (±₹1k/2-5k/5k Cr), and 3-week-selling-streak rules → all refuted (1-2 / 0-3). Keep FII/DII as *exploratory features only*, pending your own backtest. Do not gate the regime on them.
- Mirror "-DI crosses below +DI = short" crossover → refuted 0-3.
- "Backtest length scaled to holding period" (3-4yr intraday etc.) → refuted 0-3.
- Specific "0% long activation in down regime" number → refuted (use as a *design rule* to disable, not a cited stat).

## Open gaps (no verified claim covered these)
- **VWAP, RSI, MACD, India VIX, breadth** roles are unvalidated by this research. VWAP is a natural intraday flip/mean-revert anchor (and the audit already flagged "short only below VWAP"); India VIX is a natural volatility-regime input. Treat as design choices to validate, not evidence-backed.

## Suggested build order
1. Layer 1 gate (ADX/DMI + SMA50 slope) → emit `allowed_side` per stock. **Wire into the scorer so it finally produces a SHORT tier.**
2. Backtest Layer 1 alone (WFO + DSR) — does the regime gate alone turn bear days green? (Today says yes.)
3. Add Layer 2 Supertrend flip machine, constrained by Layer 1.
4. Add Hurst as a soft mode-hint; add VWAP intraday rule.
5. Paper-trade a new engine (`v7_regime`?) alongside v4/v5 for A/B.
