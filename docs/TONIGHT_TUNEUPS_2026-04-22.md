# Tonight's Tune-Ups — 2026-04-22 (post-market)

Scheduled for: after market close (15:35 IST) once EOD comparison report is reviewed.
Owner: Soumya.
Status: queued · local-only · do not push to DevPilot DB until user confirms.

---

## Unified Build Queue (combines dashboard tune-ups + deep-dive findings)

Two independent investigation streams converged into one queue:
- **Dashboard tune-ups** (Parts B/C/D/E) — surfaced from mid-market dashboard observations at 12:26 and 13:41 IST
- **Deep-dive findings** (Items P1–P4) — surfaced from the EOD deep-dive battle report at 19:14 IST (`docs/watchdog/reports/2026-04-22_deep_dive/report.pdf`)

Note: deep-dive item P5 (Live Engine Picks widget) is the same as dashboard Part B — counted once below.

### Build order (defensive → UX → research → engine-surgery)

| # | Item | Code | Type | Priority | Time est. | Touches engine? |
|---|------|------|------|----------|-----------|-----------------|
| 1 | Cap v5_2 options + daily loss kill-switch | P1 | Defensive | **CRITICAL** | 30 min | yes (v5_2 only) |
| 2 | Build Live Engine Picks widget + `/api/live-engine-picks` | B / P5 | UX/data | High | 60 min | no |
| 3 | Stocks tab per-card holding indicator | E | UX | High | 30 min | no — reuses #2 |
| 4 | Diagnose v4 — retire OR retrain | P2 | Cleanup | High | 45 min | yes (v4 only) |
| 5 | Consensus-pick analysis (5-day backtest) | D | Research | Med | 60 min | no |
| 6 | Market Pulse → SWING feasibility write-up | C | Research | Med | 45 min | no |
| 7 | Test pool cap raise 20 → 30 in paper mode | P4 | Engine | Low | 30 min | yes (config) |

**DEFERRED** — pulled from tonight, queued for weekend Task #2:
| ~~Was #4~~ | ~~Diagnose v4 — retire OR retrain~~ | ~~P2~~ | ~~Cleanup~~ | **DEFERRED to weekend** | — | — |
| ~~Was #7~~ | ~~Port v5_6 box-theory exits onto v5~~ | ~~P3~~ | ~~Engine~~ | **DEFERRED to 2026-04-24 EOD gate** | — | — |
| ~~New~~  | ~~Tune v5_3 staged entry — fix-or-retire~~ | — | ~~Cleanup~~ | **DEFERRED to weekend** | — | — |
| ~~Was #7→config~~ | ~~Pool cap test 20→30~~ | ~~P4~~ | ~~Engine~~ | **DEFERRED to weekend** | — | — |

**Why v4 + v5_3 deferred together (decision 2026-04-23 00:30):**
- v4 (51% WR coin-flip) and v5_3 (0 confirmed / 59 cancelled today) both need decisions, both not bleeding the fleet, both deserve consistent treatment
- Single weekend session evaluates both with consistent retire/tune decision rules
- See Task #2 spec for the rules

**Final tonight queue: 4 items (~75 min)** — Items #2, #3, #5, #6 only. Item #1 already done.

**Reason for deferral**: 1 day of data is not enough to confirm v5's exit-precision is the real gap. Hold v5's existing exit logic unchanged for Thursday Apr 23 and Friday Apr 24. Compare 3-day P&L gap (v5 vs v5_6/v5_7) on Friday EOD. Only if the gap stays consistent at ~Rs 15-20K/day will we port box-exits. This follows the "don't rush findings" rule — patterns must persist across 3+ trading days before triggering engine surgery.

**Total estimate:** ~5 hours of work (deferred item removes 90 min). Items 1-6 (~4 hours) are the high-value, low-risk batch — strongly recommended for tonight. Item 7 is config-only.

### Why this order

- **#1 first**: a single bad day on v5_2 wipes out the rest of the fleet. Defensive cap = sleep peacefully tonight.
- **#2 before #3**: Part E reuses Part B's data source, so build the API once.
- **#4 after UX work**: v4 cleanup is mechanical, fits well as a "between bigger tasks" slot.
- **#5 after #2 & #3**: consensus analysis depends on the holding-indicator data structures we'll have built.
- **#6 last among research**: fewest dependencies; can also run in parallel with #5.
- **#7 (was #8)**: lowest priority; requires careful regime backtesting; can wait for a quiet weekend.

### Decision-gate for v5 box-exit port (revisit Friday Apr 24 EOD)

Track these 3 metrics for v5 across Apr 22 (today, baseline), Apr 23, Apr 24:

| Metric | Apr 22 | Apr 23 | Apr 24 | Decision rule |
|--------|--------|--------|--------|---------------|
| v5 daily P&L | Rs 44,612 | (TBD) | (TBD) | — |
| v5 win rate | 89% | (TBD) | (TBD) | — |
| v5 P&L gap to v5_6/v5_7 leader | Rs 16,940 | (TBD) | (TBD) | If avg gap ≥ Rs 12K AND avg WR gap ≥ 2.5pts → port box-exits |

If gap shrinks to under Rs 8K/day or v5's WR catches up → no porting needed; v5 just had a "broad universe day" today.
If the gap inverts (v5 beats v5_6/v5_7) on any day → DO NOT port; v5's broader symbol coverage is its strength.

---

## Task: Reconcile dashboard Market Pulse vs engine reality

### Context (surfaced mid-market 2026-04-22 at 12:26 IST)

While watching the live dashboard, Soumya noticed the **Market Pulse** tab showed 8 bullish picks (TCS, TATAPOWER, OFSS, HCLTECH, HINDUNILVR, INFY, COFORGE, CGPOWER). Cross-checking against the live engine state showed **only 1 of those 8 (CGPOWER) was actually held by any engine**. The dashboard suggests "these are our picks" but the engines trade a completely different universe (NATIONALUM, NTPC, LODHA, BANKINDIA, VOLTAS, UNIONBANK, FORTIS, SWIGGY, IREDA, GAIL, AUBANK, etc.).

Root cause — two independent pipelines:
- `/api/bots/market-pulse` → calls `score_stocks_v2()` → daily ML score ≥ 65 + safe-risk filter. Horizon: multi-day swing.
- v5 / v5_6 / v5_7 paper-trade engines → Rust bridge + 5-minute intraday momentum + tiered models. Horizon: intraday / short swing.

They disagree because they *should* disagree — different features, different horizons. But the UX says "Market Pulse = our picks", which is misleading.

### Plan (two parts)

#### Part B (build tonight) — "Live Engine Picks" widget

Add a new widget/tab beside "Market Pulse" that shows what the engines are **actually** holding right now. Read from the engine state JSONs, not from the daily scorer.

- **Source**: `docs/paper-trades/<engine>/<today>.json` → `.pools[*].positions[]`
- **Engines shown**: v5, v5_6, v5_7 (the three that are performing). v5_classic optional.
- **Columns**: Symbol · Engine · Pool · Entry price · Current price · P&L · Entry time
- **API route**: new `/api/live-engine-picks` endpoint in `prototype/app.py`
- **Placement**: next to "Market Pulse" tab in the Market Intelligence card (same tab group: Global Events · India News · Market Pulse · **Live Engine Picks**)
- **Refresh**: same cadence as Market Pulse (every 60 sec or on click)
- **Visual**: green chip if in profit, red if in loss, small chart sparkline optional

Reference files:
- API: `prototype/app.py` around line 821 (`api_bots_market_pulse`)
- Template: `prototype/templates/index.html` (search `Market Pulse` for tab group)
- Data: `docs/paper-trades/v5_6/<date>.json` → `.pools.SWING.positions[]`

#### Part C (explore tonight — do not wire yet) — Can Market Pulse feed the SWING pool?

Investigate whether `score_stocks_v2()` output could become an input signal to the engine's SWING pool. Key questions to answer:

1. **Historical alignment**: for the last 5 trading days, how many times did Market Pulse picks align with engine wins? Build a small backtest script that reads past `daily-scores*.json` (if they exist — check) and past closed trades.
2. **Score threshold**: is score ≥ 65 + SL ≤ 10% + target > SL the right bar? Too strict would starve the feed, too loose would dilute.
3. **Pool routing**: would these go into the INTRADAY pool (probably no — daily scores), SWING pool (likely), or POSITIONAL pool (if target_pct > 15)?
4. **Duplicate avoidance**: if engine's own signal already flagged the same symbol, which one wins?
5. **Risk**: Market Pulse picks are large-cap, slow-moving (TCS, INFY). They won't trigger intraday momentum — engines might still ignore even with the subscription.

**Do not change engine code tonight.** Just produce a write-up (`docs/research/market-pulse-to-swing-feasibility.md`) with:
- 5-day alignment data
- Recommendation (wire / skip / modify)
- If wire: specific integration point, flag name, fallback behaviour

#### Part D (new — 13:41 IST observation) — Consensus-pick tracker

While viewing the dashboard "Stocks" tab mid-market, only 2 of 15 BUY/HOLD-rated stocks (13%) were being traded by engines. But one of them — **DRREDDY** — was held by all three top engines (v5 + v5_6 + v5_7) AND had a dashboard score of 69 (BUY). That's the "holy grail" signal: large-cap daily scorer agrees with intraday momentum from multiple engines.

Build a small analysis that tags every engine position with a **consensus score**:
- `solo` — only 1 engine + no dashboard BUY
- `engine-only` — 2+ engines agree, dashboard silent / score < 65
- `dashboard-only` — dashboard BUY (score ≥ 65), 0 engines acted
- `consensus` — dashboard BUY AND 2+ engines trading

Then look at closed trades over the last 5 days and compare win-rate + avg P&L by consensus score. Hypothesis: **consensus picks win more often**. If it holds:
- Surface "Consensus picks today" as a special widget on the dashboard
- Weight position sizing up for consensus-tagged signals
- Use as entry filter for the SWING pool (Part C)

Deliverable: `docs/research/consensus-pick-analysis.md` with the comparison tables. No engine code changes tonight.

#### Part E (new — 13:41 IST observation) — "Stocks" tab has the same misleading framing as Market Pulse

Same problem as Market Pulse: the Stocks tab shows BUY/HOLD ratings on 15 large-caps but the engines ignore 13 of them (87%). Users assume "TradePilot says BUY → we're buying" — but we're not.

Options for tonight:
- Add a badge/indicator on each stock card showing whether any engine is currently holding it ("LIVE" / "IGNORED")
- Or add a tooltip: "Score ≥ 65 does NOT mean the engine is trading this. It's a daily outlook. See Live Engine Picks for real positions."
- Or simpler: a small card footer with "Held by: v5, v5_6, v5_7" when any engine has a position on it

This reuses the Part B widget's data source — just surfaces it inline on each stock card.

### Acceptance criteria for tonight

- [ ] Part B: new widget visible in dashboard, shows live positions from v5 / v5_6 / v5_7, refreshes correctly, doesn't break existing Market Pulse
- [ ] Part B: tested locally in browser before handoff (per `feedback_test_before_handoff`)
- [ ] Part C: feasibility write-up produced, no engine code changed
- [ ] Part D: consensus-pick analysis over last 5 days produced at `docs/research/consensus-pick-analysis.md`
- [ ] Part E: Stocks tab cards show holding status (LIVE/IGNORED or "Held by: ..." footer). Tested in browser.
- [ ] Nothing committed until Soumya reviews tomorrow morning

### References

- Discovery screenshot #1 (Market Pulse): user sent at ~12:26 IST on 2026-04-22
- Discovery screenshot #2 (Stocks tab): user sent at ~13:41 IST on 2026-04-22 — 15 large-caps rated BUY/HOLD, engines only holding 2 of them (NTPC via v5_6, DRREDDY via v5+v5_6+v5_7). 13% overlap.
- Engine state snapshot at time of discovery:
  - v5: 78 trades, 83.3% win, +Rs 15,879 (active positions: mid-cap/PSU only)
  - v5_6: 85 trades, 89.4% win, +Rs 18,738
  - v5_7: 78 trades, 89.7% win, +Rs 20,488
  - Dashboard picks: TCS(80), TATAPOWER(77), OFSS(73), HCLTECH(73), HINDUNILVR(72), INFY(69), COFORGE(69), CGPOWER(67)
  - Overlap: CGPOWER only (v5_7, 1 open position)
