# v5-vs-v6 Experiment — Design Spec for 2026-04-29

> Origin: 04-28 EOD post-mortem identified that v5's `signal_engine` wrapper
> mechanically converts the bottom 10/20% of v4-scored stocks into SHORTs based
> on regime, even when those stocks aren't actually weak. This causes a
> structural underperformance vs v4 on green tapes — Rs 21,282 yesterday alone.

---

## Hypothesis

The v5 deficit comes from **two** sources:

1. **H1 (signal-layer bug)**: v5's wrapper forces SHORTs on stocks that v4's
   raw scorer wouldn't even classify as bearish. On a bullish tape these
   become a tax on v5.
2. **H2 (re-emission debounce)**: v5's wrapper de-prioritizes recently-traded
   symbols, breaking the WINNER_RE_ARM loop that gave v4 +Rs 9,460 from 29
   re-entered symbols on 04-28.

Tonight's experiment isolates H1 with two interventions:

| Intervention | Targets | Implementation |
|---|---|---|
| **Fix #1**: SHORT requires absolute weakness | H1 only (in v5) | `prototype/v5/signal_engine.py` lines 50-51, 195-208. Stocks ranked bottom-N must ALSO have `change_pct < -0.5%` AND `score < 35` to actually emit SHORT. Otherwise downgrade to HOLD. |
| **v6 engine**: skip wrapper entirely | H1 + H2 (full bypass) | `scripts/v6-paper-trade.py` calls v4's `composite_scorer.score_all_stocks()` directly. Absolute thresholds: BUY ≥ 60, SHORT ≤ 35 AND change_pct < -0.5%. Inherits all Track A from v5 base (cost modeling, RE-ARM, SHORT_BLOCK, FLAT_EXIT). |

---

## Engine roster (6) and what each tests

| Engine | Signal layer | Track A bolt-on | Role |
|---|---|---|---|
| **v4** | v4 raw (composite_scorer) | NO | Control. Yesterday's winner (+Rs 26,179). |
| **v5** | v4 + wrapper + Fix #1 | YES | "Did Fix #1 alone close the gap?" |
| v5_classic | v4 + wrapper (no Fix #1) | NO | Baseline / sanity. |
| v5_6 | v5 + Darvas Box overlay | YES | Independent variant — informational. |
| v5_7 | v5 + Intraday Box overlay | YES | Independent variant — informational. |
| **v6** | v4 raw (no wrapper) + absolute thresholds | YES | "Track A on a v4-quality signal layer" — the cleanest test of Track A's marginal value. |

Bold = the three engines that answer tomorrow's experimental question.

---

## What we measure (primary)

| Metric | Source | What it tells us |
|---|---|---|
| Day P&L per engine | `docs/paper-trades/{engine}/2026-04-29.json` | Headline outcome |
| Win rate (closed trades) | same | Trade-quality proxy |
| Trade count | same | Did slot-cap or Fix #1 reduce participation? |
| Side mix (LONG vs SHORT) | same | Does v5 still emit too many SHORTs after Fix #1? |
| Re-emissions per symbol | derived from closed trades | v4 = ~29 yesterday. v5 = 2. v6 should approach v4. |
| Fix #1 filter count | `grep "Fix#1 filtered" logs/v5-paper-trade.log` | How often Fix #1 actually fires. >0 means it's doing work. |

## What we measure (secondary, by Track A diagnostics)

| Metric | Source | Interprets |
|---|---|---|
| `[SHORT_BLOCK]` fires per engine (v5, v6) | logs | Bullish-premarket guard active? |
| `[RE-ARM]` redeploys / re-armable marks | watchdog events JSON | v6 should mark + redeploy at v4-like rates if H2 was the bottleneck |
| `FLAT_FORCE_EXIT` count | logs | 13:30-14:00 flat-position cleanup |
| Cost per trade (gross vs net) | closed-trade rows | 12 bps applied uniformly |

---

## Decision matrix (Wednesday EOD reading)

Read across ALL three engines together — single-comparison readings can
mislead on a one-day sample.

| v6 vs v4 | v5(Fix#1) vs v6 | Read |
|---|---|---|
| v6 ≥ v4 + Rs 3K | v5 ≈ v6 | **Best case**. Track A is value-add. Fix #1 closes v5's gap. Both v5 and v6 viable; pick on simplicity. |
| v6 ≥ v4 + Rs 3K | v5 << v6 | Track A is value-add. Fix #1 wasn't enough — v5 still has bugs (likely H2). Consider retiring v5 wrapper, keeping v6. |
| v6 ≈ v4 (±Rs 2K) | v5 ≈ v6 | Track A is neutral on v4 signals. Yesterday's "Track A added Rs 7,132 to v5" was actually Track A *compensating for v5's bugs*. Drop Track A overhead, keep v4. |
| v6 ≈ v4 | v5 << v6 | v5 wrapper still actively harmful. Fix #1 incomplete. Investigate H2. |
| v6 < v4 by Rs 3K+ | any | Track A is hurting v4. SHORT_BLOCK or RE-ARM mis-firing on the new signal mix. Disable Track A on v6 next iteration. |

**One day is one sample.** Do not retire any engine on a single Wednesday
result. Feed all into the 4-week observation window ending 2026-05-25.

---

## Pre-flight verifications (already passing)

- `python3 tests/test_track_a.py` → 16/16 OK
- `compile()` on `signal_engine.py` and `v6-paper-trade.py` → clean
- `bash -n` on `launch-market.sh` and `crash-watchdog.sh` → clean
- Engine registries in launch-market.sh, crash-watchdog.sh, status-digest.py all list 6 engines including v6
- v6 thresholds: `V6_BUY_MIN_SCORE=60`, `V6_SHORT_MAX_SCORE=35`, `V6_SHORT_MIN_NEG_CHANGE=-0.5`
- Fix #1 thresholds: `SHORT_REQUIRE_NEGATIVE_CHANGE_PCT=-0.5`, `SHORT_REQUIRE_MAX_SCORE=35`
- (Both fixes use the same absolute thresholds — comparable across engines)

---

## Risk register

| Risk | Mitigation |
|---|---|
| Fix #1 filters out so many SHORTs that v5 takes near-zero SHORT trades on a bear day, missing a real signal | Track A SHORT_BLOCK is morning-only; afternoon SHORTs still emit when actually weak. Fix #1 only blocks bottom-rank-but-not-weak. Genuinely weak stocks (change<-0.5% AND score<35) still pass. |
| v6 pulls v4's score directly but v4's score updates aren't synchronised with v6's scan loop | v6 calls `score_all_stocks(self.qualifiers)` fresh each scan — same data path v4 uses. No staleness. |
| v6's Track A double-counts re-arm with v4's natural re-emission | v4 has no re-arm code. v6's Track A re-arm runs on TARGET hits only. The natural re-emission v4 enjoys is a separate scan-loop behavior. Both can coexist. |
| 6 engines = more API load, possible rate limits | v4 already runs alongside v5/v5_6/v5_7. Adding v6 adds one more scan loop. v6 reuses v4's score cache when called within the same minute. |
| v6 P&L file name collisions with v4 | Different `TRADE_DIR`: `docs/paper-trades/v6/`. No overlap. |

---

## Tonight's status before market open

| Item | State |
|---|---|
| Fix #1 in `signal_engine.py` | ✓ shipped (lines 50-51, 195-208) |
| `v6-paper-trade.py` | ✓ shipped |
| `launch-market.sh` ENGINES | ✓ 6 engines |
| `crash-watchdog.sh` ENGINES | ✓ 6 engines |
| `status-digest.py` ENGINES | ✓ 6 engines |
| TOMORROW_MORNING_CHECKLIST.md | ✓ updated for Wed 04-29 |
| Experiment design doc | ✓ this file |
| Unit tests | ✓ 16/16 passing |
| Compile checks | ✓ clean |
| Bash syntax | ✓ clean |
| Commit status | uncommitted (per observation rule) |

---

## Tomorrow EOD: how to write this up

Append to `docs/learning/2026-04-29-eod-summary.md` (mirror yesterday's
template):

1. Final scoreboard table (6 rows)
2. Did Fix #1 fire? How many times? Did it save losses?
3. v6 vs v4 head-to-head: trades, P&L, side mix, re-emission count
4. v5 (Fix #1) vs v6: did closing the gap require Track A's defensive layer or
   just the fixed wrapper?
5. Watchdog events for v5 + v6 separately (insights.md per engine if both ran)
6. One-line verdict: which hypothesis (H1, H2, both, neither) the data supports
7. Decision: which engines stay in observation through the 4-week gate

---

**One sample tomorrow. 30+ samples by 2026-05-25. Don't decide on one day.**
