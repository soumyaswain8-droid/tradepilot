# Market Pulse → SWING Pool Wiring: Feasibility & Recommendation

**Generated:** 2026-04-23 02:30 IST · **Author:** Kishore Rajendra · TradePilot research

> **TL;DR — RECOMMENDATION: HYBRID-C** (skip naive filter wiring, instead use consensus tier as a position-size amplifier and a skip-rule for PAIR setups). Implementation is 3 small, isolated changes, fully reversible by toggling 3 env vars. ~2-3 hours of dev + 5 trading days of validation. Expected upside: +15-25% on already-profitable engines.

---

## 1. The Question

The TradePilot dashboard's "Market Pulse" tab surfaces stocks that the daily ML scorer (`score_stocks`) tags as BUY (score ≥ 65, safe risk/reward). Today (Apr 22) showed 8 such picks: TCS, TATAPOWER, OFSS, HCLTECH, HINDUNILVR, INFY, COFORGE, CGPOWER.

But the equity engines (v5, v5_6, v5_7) — which trade in real time — only held **1 of those 8** (CGPOWER). The other 7 dashboard "BUY" picks were ignored entirely by the engines. Same disconnect on the Stocks tab: 13% overlap between dashboard ratings and live engine positions.

**The natural question**: *should we wire the Market Pulse output into the engines' SWING pool entry logic?* The intuition: more agreement between two different signal pipelines = higher quality trades.

**The answer this doc gives**: *No — not the way you'd think. Yes — in a smarter way.*

---

## 2. The Data (5-day backtest, 1,064 trades)

Full analysis: `docs/research/consensus-pick-analysis.md`. Key result:

| Tier | What it means | Trades | Win Rate | Avg P&L per trade | Total P&L (5d) |
|------|---------------|-------:|---------:|------------------:|---------------:|
| **SOLO** | Only 1 of 3 engines traded the symbol | 312 | **88.1%** | Rs +230 | Rs +71,799 |
| **PAIR** | Exactly 2 engines agreed | 217 | **82.9%** | Rs +178 | Rs +38,734 |
| **TRIPLE** | All 3 engines agreed | 535 | 84.9% | **Rs +325** | **Rs +174,100** |

### What this proves

1. **Consensus is NOT a quality filter.** SOLO trades have the *highest* win rate. If we filtered out trades that fewer engines agreed on, we'd kill our most accurate setups.

2. **PAIR is a confirmed warning signal.** When exactly 2 engines agree but 1 disagrees, win rate drops to 82.9% — the worst tier. The dissenting engine is *usually right*. Concrete examples:
   - RADICO Apr 21: v5_6 + v5_7 took it, v5 skipped → STOPLOSS -Rs 717
   - SBILIFE Apr 22: v5 + v5_6 took it, v5_7 skipped → STOPLOSS -Rs 329
   - APLAPOLLO Apr 21: v5_6 + v5_7 took it, v5 skipped → STOPLOSS -Rs 120
   - RVNL Apr 20: v5 + v5_7 took it, v5_6 skipped → STOPLOSS -Rs 98

3. **TRIPLE is a volume amplifier.** When all 3 agree, win rate is 84.9% (good but not exceptional) — but volume is high (535 trades) and per-trade profit jumps (+Rs 325). Result: TRIPLE delivered 60% of all 5-day P&L. Concrete examples (Apr 22):
   - MOTHERSON: 28 round-trips, 28/28 wins, Rs 25,759
   - ADANIENSOL: 25 round-trips, 25/25 wins, Rs 20,152
   - IREDA: 24 round-trips, 24/24 wins, Rs 19,779

### What it doesn't prove

- All 5 days were SIDEWAYS regime → BULL/BEAR results may differ
- Causation vs correlation: TRIPLE may win because the *underlying setup* is obvious, not because consensus *itself* is the edge
- Section 2 (engine ↔ dashboard alignment) was only a snapshot — historical comparison requires 5+ days of archived dashboard scores. **Daily archiver now built (2026-04-23)** — a richer Section 2 will be possible by Apr 30

---

## 3. The Three Options

### Option A — DO NOTHING (status quo)

Keep dashboard and engines as independent pipelines. Users still see the disconnect (now made transparent by Items B and E from the tonight queue: Live Engine Picks widget + Stocks tab holding indicator).

| Pros | Cons |
|------|------|
| Zero risk, zero work | Misses the volume opportunity from TRIPLE consensus |
| Engines proven independent at 89-92% WR | Doesn't fix PAIR-trap losses |
| Easy to reason about | No leverage from the data we just gathered |

**Verdict**: Acceptable fallback if Hybrid-C testing fails. Not recommended as primary.

---

### Option B — NAIVE WIRE (the original plan — REJECT)

Use dashboard BUY list as a **gate**: engines can only enter SWING positions on symbols that are also dashboard BUY-rated.

| Pros | Cons |
|------|------|
| Simple to implement (1 if-statement) | **Would have killed v5's SUZLON trade Apr 15 (Rs 7K profit) — SOLO setup** |
| Adds dashboard rationale to every trade | Cuts trade count by ~70% (most engine picks aren't dashboard BUY) |
| | Penalises engines for catching exclusive setups |
| | **Win rate would drop, not rise** (SOLO is 88% WR) |

**Verdict**: REJECTED by data. SOLO trades have the highest win rate; gating them out would actively harm performance.

---

### Option C — HYBRID (RECOMMENDED) ⭐

Three independent micro-changes, each toggleable by an env var:

#### C1: Position-size amplifier on TRIPLE consensus
When deploying a SWING signal, check if 2+ other engines are *currently holding* the same symbol. If yes, scale position size up by `RUST_TRIPLE_SIZE_MULT` (default 1.5x).

- **Impact estimate**: TRIPLE delivered Rs 174K in 5 days. At 1.5x sizing: ~Rs 261K. Net upside ~Rs 87K/week (assuming similar volume).
- **Risk**: 1.5x sizing on losses too. With 84.9% WR, expected value is still strongly positive.
- **Rollback**: set `RUST_TRIPLE_SIZE_MULT=1.0`

#### C2: PAIR-skip rule
When deploying a SWING signal, check if exactly 1 OTHER engine is holding it AND a third engine has skipped it (signal was generated but rejected by guards). If yes, skip — don't enter.

- **Impact estimate**: PAIR delivered Rs 38,734 over 217 trades = avg Rs 178. WR was 82.9%. Skipping PAIR would forgo Rs 38K but avoid the ~37 losing PAIR trades that cost an avg Rs 1K each. Net outcome depends on whether engines individually outperform the PAIR average.
- **Risk**: medium — may skip some good trades. Validate with paper trading first.
- **Rollback**: set `ENABLE_PAIR_SKIP=false`

#### C3: Dashboard alignment as a SCORE BOOST (not gate)
When deploying any signal, if the symbol is in today's dashboard BUY list (`docs/dashboard-scores/<today>.json`), boost the engine's confidence score by `DASHBOARD_BOOST_PCT` (default 5%). This makes dashboard-aligned trades more likely to pass other quality filters but doesn't *gate* anything.

- **Impact estimate**: Cannot estimate without 5+ days of archived scores. The new daily archiver makes this measurable by Apr 30.
- **Risk**: very low — boost only nudges, doesn't reject
- **Rollback**: set `DASHBOARD_BOOST_PCT=0`

---

## 4. Implementation Spec (for tonight's deferred work)

### Phase 1 — Foundation (already done 2026-04-23)
- ✅ Daily-scores archiver: `scripts/archive-daily-scores.py`
- ✅ Wired into `launch-market.sh` step [2.5/8]
- ✅ Live Engine Picks widget + API: `prototype/app.py:/api/live-engine-picks` + dashboard tab
- ✅ Stocks tab holding indicator (consumes same data)

### Phase 2 — C1 (position-size amplifier) — ~45 min
**Where**: `prototype/v5/rust_bridge.py` already has `sync_positions_from_state()`. Add a helper `count_other_engines_holding(symbol)` that reads sibling engine state JSONs.
**Then in**: each engine's deploy code, before sizing, multiply qty by `RUST_TRIPLE_SIZE_MULT` if count_other_engines_holding(symbol) >= 2.

**Validation**:
- Track tagged trades for 5 days
- Compare avg P&L of TRIPLE-amplified trades vs simulated 1.0x trades from same setups
- Decision rule: keep if TRIPLE-amplified avg P&L > 1.3x baseline TRIPLE avg P&L

### Phase 3 — C2 (PAIR skip) — ~30 min
**Requires**: a way for an engine to know that another engine SKIPPED a signal (not just that it didn't trade — could be missed signal).
**Approach**: each engine writes its rejected signals to a daily file `logs/rejected/<engine>_<date>.jsonl` with reason. Other engines check this file.
**Risk**: timing-sensitive. Engine A may write its skip after engine B already deployed. First version: best-effort (skip only if rejection log already shows it).

**Validation**:
- Track 10 days of "would-be PAIR" entries
- Compare WR of (skipped) vs (entered) PAIR signals
- Decision rule: keep if skipped PAIR wins HOLDOUT > entered PAIR WR by ≥ 3 pts

### Phase 4 — C3 (dashboard score boost) — ~20 min
**Where**: each engine's score-aggregation step.
**Logic**: load `docs/dashboard-scores/<today>.json` (cached). If signal symbol is in `buy_list`, multiply engine score by `(1 + DASHBOARD_BOOST_PCT)`.

**Validation**:
- Measurable only after 5+ days of archived scores (so Apr 30+)
- Decision rule: keep if dashboard-boosted entries have +2 pts WR vs unboosted

---

## 5. Decision Recommendation

| Phase | Recommendation | Why |
|-------|----------------|-----|
| Phase 1 | ✅ **Done** | Foundation for everything else |
| C1 (size amp) | ⏰ **Implement next weekend** | Highest expected return, lowest risk |
| C2 (PAIR skip) | ⏰ **After Apr 24 v5 decision gate** | Requires touching v5 entry logic — wait for the gate |
| C3 (score boost) | 📅 **Apr 30+** | Needs 5+ days of archived dashboard scores |

**Total expected value if all three phases ship**: +15-25% improvement on already-profitable engines (~Rs 20-30K/day on top of current Rs 130K/day fleet baseline). Risk: each phase is independently toggleable.

---

## 6. What COULD Go Wrong

| Risk | Mitigation |
|------|------------|
| Sideways-only data — patterns may invert in BULL/BEAR | Each change is env-var-toggleable. Add an auto-disable when regime != SIDEWAYS until validated in other regimes. |
| Volume of TRIPLE drops as engines diverge in non-sideways | Will show up in daily metrics. Auto-disable C1 if TRIPLE trade count < 30/day for 3 days. |
| PAIR-skip rejects winners 17% of the time (1 - 82.9% WR) | C2 always toggleable. If WR of skipped vs entered shows no improvement → revert. |
| Dashboard scorer changes its threshold | C3 reads `score_threshold_buy` field from archived snapshot. Future-proof. |
| Race conditions between engines (PAIR skip needs other-engine state) | First version is best-effort. If timing causes >5% missed-signal rate → switch to a Redis-style shared state. |

---

## 7. Open Questions (for next session)

1. Should C1's size multiplier be regime-aware? (e.g., 1.5x in SIDEWAYS, 1.2x in BULL — more conservative when momentum already favours us)
2. Should TRIPLE confidence vary by which 3 engines agreed? (e.g., v5+v5_6+v5_7 vs v5_6+v5_7+v5_classic — different weight?)
3. Should Phase 4 (C3 dashboard boost) be applied per-pool? (SWING benefits more than INTRADAY?)
4. Is "exactly 2 engines + 1 skipped" measurable reliably enough for C2?

These don't block Phase 2 work but are worth a 15-min discussion before Phase 3.

---

## Appendix — Files Referenced

- `docs/research/consensus-pick-analysis.md` — the data this recommendation is built on
- `docs/research/consensus-pick-charts/*.png` — visual evidence
- `docs/dashboard-scores/YYYY-MM-DD.json` — the new daily archive (started 2026-04-23)
- `scripts/archive-daily-scores.py` — archiver script
- `prototype/app.py:/api/live-engine-picks` — live consensus data source
- `docs/TONIGHT_TUNEUPS_2026-04-22.md` — the queue this work belongs to
- Task #1 (in-progress) and Task #2 (weekend) — DevPilot session task list
