# Design — Fast Regime Flip (avoid losses + profit on red days)

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Document** | Design spec (research/design — NOT yet implemented) |
| **Version** | `v0.1.0` (draft) |
| **Created** | 2026-06-30 |
| **Trigger** | Live red day: NIFTY −0.73%, engines long-heavy & bleeding while shorts were green |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@sidewall.in |

:::

---

## 1. Root cause (confirmed in code)

- **Gap 1 — regime frozen at launch.** `detect_regime()` runs once at premarket (`scripts/v5-paper-trade.py:379`); `rescore_and_redeploy` reuses `state["regime"]` (`:698`) and never re-detects. Intraday market moves never change the tag.
- **Gap 2 — slow inputs.** `prototype/v5/regime_detector.py` votes on 6 daily aggregates (50/200-DMA, 5-day momentum, daily VIX, FII/DII, advance/decline). A red open barely moves a 50-day average, so it reads SIDEWAYS/BULL after an uptrend and deploys the 15-long/5-short slot split.
- Result this morning: 09:00 "SIDEWAYS" → 15L/5S → 16–23 longs → NIFTY −0.73% → frozen long-heavy → bled. Shorts were green (+₹497) but too few.

## 2. The fix — Fast Regime Flip

### Piece 1 — fast intraday `tape_state` signal (the missing input)
Compute every scan from live data: NIFTY intraday % (open→now, vs prev close), NIFTY vs VWAP / opening-range, live breadth (% NIFTY-50 red), intraday VIX spike → `tape_state ∈ {RISK_ON, NEUTRAL, RISK_OFF}`.

### Piece 2 — re-evaluate every scan, not at launch
Slow daily regime sets the baseline; the fast `tape_state` can override it intraday. **Scan every 5 min** (REVISED from 10 — aligns with the 5-min candle so we don't miss the trend signal). Detection is every 5 min; position flips require 2–3 confirming reads (anti-whipsaw).

### Piece 3 — TILT the ratio, do NOT flip the book (REVISED after data validation 2026-06-30)

Data (all sessions since April) shows the edge is **stock-selection, not market-direction**: longs net positive even on DOWN days (v5 +Rs79,428, 56% green) and shorts net positive on both (v5 up +Rs11,747 / down +Rs17,584). So a hard flip to all-short would dump the longs right before they earn. Instead, keep **both legs always on** and tilt the long/short *ratio* by regime.

::: {.gap-table}

| Tape | Action | Goal |
|:--|:--|:--|
| RISK_OFF (red, confirmed) | Tilt slot ratio toward shorts (e.g. SIDEWAYS 15/5 → 11/9, not 0/20); KEEP longs (they recover/profit on down days); re-arm winning shorts (COALINDIA x6 = +Rs23,197 pattern) | Add short profit without forfeiting long recovery |
| RISK_ON (green, confirmed) | Tilt toward longs; shorts still allowed on clearly-weak names (dispersion) | Capture the up-trend, keep short optionality |

:::

**Direction is per-STOCK (long strong / short weak), regime only sets the tilt.** Re-arm winners on BOTH sides (multi-entry shorts made +Rs40,714 vs +Rs21,429 single; multi-entry longs +Rs280,808).

### Piece 3b — TILT MAGNITUDE (✅ data back-tested 2026-06-30, per-trade by day severity)

Per-trade P&L bucketed by NIFTY open->close shows the short-tilt should fire only on a GENUINELY hard-down day, and the existing BEAR split is already right:

::: {.metrics-table}

| Severity (NIFTY o->c) | v5 LONG/trade | v5 SHORT/trade |
|:--|--:|--:|
| UP (>+0.15%) | +203 | +18 |
| MILD-DOWN (-0.15 to -0.6%) | **+123** | +11 |
| HARD-DOWN (< -0.6%) | +49 | **+82** |

:::

- **Trigger correction:** short-tilt fires only on **HARD-DOWN (NIFTY < ~-0.6%)**, NOT -0.5% (mild-down days still favor longs for v5: +123 vs +11/trade).
- **Magnitude = the existing BEAR slot split 8L/12S** — it's in the data-supported zone (v5 +1,378/day, classic +1,023/day on hard-down). Going more aggressive (5L/15S, 2L/18S) shows higher modelled P&L but it's a LINEAR model that overstates marginal shorts + ignores concentration/2nd-half-reversal risk + tiny sample (7-8 days) — do NOT chase it.
- **Never zero longs:** v5 longs still earn +49/trade even on hard-down days.
- **So the fix is ACTIVATION, not ratio:** the engine already has BEAR 8/12; the gap is applying it fast intraday (the Fast-Flip detection), gated by the slow daily regime today.

## 2b. VALIDATION (✅ data-checked 2026-06-30, all sessions since April)

INTRADAY trade P&L by ENTRY time-of-day refutes a time cutoff and confirms the 2nd half is where profit is made:

::: {.metrics-table}

| Engine | Entered after 1pm | Entered before 1pm |
|:--|--:|--:|
| v5 (50 sess) | **+₹30,515** (486t) | −₹2,724 (723t) |
| v5_classic (46 sess) | +₹10,517 (55% green) | +₹19,558 |

:::

v5's best entry hour = 13:00 (+₹16,882); mornings lose. **Conclusion: do NOT disable new entries/flips in the 2nd half — both engines are net-positive on post-1pm entries.** (Caveat: exit-time "168% of net" figure is inflated by TIME_EXIT mechanics; entry-time numbers above are the clean measure.)

## 3. Guardrails (so it doesn't backfire / curve-fit)

- Flip to RISK_OFF only if NIFTY < −0.5% **AND** breadth < 35% green **AND** below VWAP, **confirmed over ≥2–3 consecutive 5-min reads** (not one wiggle).
- **Bidirectional & active all session** (REVISED — the 13:30 cutoff is REMOVED per validation above): the flip must catch a 2nd-half reversal too — if we're short from a red morning and the afternoon turns green (NIFTY back > VWAP + breadth > 50%), flip back to long to capture the post-1pm up-trend. This is where the profit is.
- Hysteresis + cooldown between flips to prevent churn (fast to *detect*, deliberate to *act*).
- 2–3 robust signals, NO parameter grid-search (Lever-4 discipline).

## 4. Code map

- New `prototype/v5/tape_regime.py` — `tape_state()` from live NIFTY/breadth/VWAP (reuse red-day-watchdog fetch).
- `scripts/v5-paper-trade.py` scan loop — call `tape_state()` each scan; RISK_OFF → override into `deploy_signals` (Tier 1 gate longs) + `pm.set_regime("BEAR")` (Tier 2 short-heavy).
- `risk_manager.py` `REGIME_SLOT_SPLIT` — BEAR 8/12 already exists; flip activates it intraday.

## 4b. Fixed ratio vs DYNAMIC allocation (✅ validated 2026-06-30)

The engine does NOT adapt its mix to the tape today: short-share is flat ~43–46% across UP / FLAT / MILD-DOWN / HARD-DOWN days (the BEAR split exists but rarely activates because the slow daily regime rarely flips → de-facto fixed ratio). So a fixed `8/12` is not "intelligence," it's a crude risk proxy.

**Principled design (the destination):**
- Direction decided **per-stock by its own trend** (long up-trending, short down-trending), not a market ratio.
- The long/short **count floats** from the opportunity set (red day → more weak stocks → more shorts naturally).
- Replace the fixed ratio with a **risk cap** (net directional exposure ≤ X%, max single-name ≤ Y%) — bounds reversal risk without freezing the mix. = dynamic market-neutral-with-tilt (what v5 was validated as).

**Honest dependency / can't-yet-validate:**
- `score`/conviction is NOT stored on closed trades → cannot correlate conviction→P&L from history. Needs the engine instrumented to log entry-conviction, then a few weeks of data.
- Cross-sectional composite score is weakly predictive (winner≈loser; ML IC 0.006) → weight by per-stock TREND (VWAP/MA), not that score.

**Layering:** Fast-Flip activation of the existing 8/12 = quick win (low risk, uses what exists). Dynamic trend-driven allocation + risk cap = the right architecture, but gated on the conviction/trend validation above.

## 5. Rollout plan (deliberate, not mid-session)

1. Build as a **shadow engine first** (`v5_flip`) — same v5 code + fast-flip, A/B vs live v5. Prove it on red days before touching live.
2. Validate: on red days does it cut losses (Tier 1) and turn profit (Tier 2)? On normal days does it avoid false flips (whipsaw cost)?
3. Promote to live only after ~5–10 sessions incl. ≥2 red days.

## 6. Status
Design only. Not implemented. Do NOT change live engines mid-session — build the `v5_flip` shadow and validate deliberately.
