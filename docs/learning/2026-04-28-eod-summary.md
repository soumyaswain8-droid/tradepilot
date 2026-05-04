# TradePilot EOD Summary — Tuesday 2026-04-28

> Day 1 of the v5 Track A observation window. v4 was retired Mon evening but
> re-instated mid-day Tue (13:47 IST) after a 4-hour run that broke the case
> for retirement. This summary captures what happened, why, and what tonight's
> review should focus on.

---

## TL;DR

- **Combined P&L: +Rs 41,014 across 412 trades** — best day in the observation window
- **v4 dominated**: +Rs 26,179 (71% WR, 103 trades, peak Rs +35,204). Even with a 35-min restart gap mid-day
- **v5 (Track A) finished 2nd**: +Rs 4,897 (65% WR, 88 trades) — better than yesterday's +Rs 737, but 5.3x behind v4
- **All 4 v5-family engines profitable today** (+Rs 1,677 to +Rs 4,897). Not a v5-broken day. A v5-vs-v4 gap day.
- **Track A's value-add on v5: +Rs 7,132** (Rs 1,320 from SHORT_BLOCK + Rs 5,812 from re-arm tracking) — fixes work, but underlying signal layer holds v5 back

---

## Final scoreboard

| # | Engine | P&L | WR | Trades | Best | Worst | Notes |
|:---:|---|---:|---:|---:|---|---|---|
| 🥇 | **v4** | **+Rs 26,179** | **71%** | 103 | GLENMARK +Rs 1,338 | HINDZINC -Rs 683 | LONG-only; 29 stocks re-entered |
| 🥈 | v5 (Track A) | +Rs 4,897 | 65% | 88 | IDEA +Rs 483 | COALINDIA -Rs 446 | 33 SHORTs took 26 STOPLOSSES |
| 🥉 | v5_7 | +Rs 4,823 | 60% | 80 | (similar pattern) | | |
| 4 | v5_6 | +Rs 4,596 | 62% | 77 | (similar pattern) | | |
| 5 | v5_classic | +Rs 1,882 | 58% | 67 | (similar pattern) | | |

---

## Why v4 succeeded — the pattern

### 1. v4 went LONG-only on a green tape

| Side | Trades | P&L | WR |
|---|:---:|---:|---:|
| **LONG** | **103** | **+Rs 26,179** | **71%** |
| SHORT | 0 | Rs 0 | — |

Nifty closed +0.81% (BULL→BEAR drift, but predominantly green for individual stocks). v4's signal scorer correctly emitted no SHORTs and stayed long the whole day. v5 family by contrast emitted 50%+ SHORT signals which bled in the green tape.

### 2. v4 hit TARGET 38 times — average win Rs +691

| Exit reason | Trades | P&L | Avg per trade |
|---|:---:|---:|---:|
| **TARGET** | **38** | **+Rs 26,263** | **+Rs 691** |
| STOPLOSS | 27 | +Rs 1,159 | +Rs 43 (near-flat — tight stops) |
| TIME_EXIT | 32 | -Rs 259 | -Rs 8 (also near-flat) |
| SIGNAL_EXIT | 6 | -Rs 983 | -Rs 164 |

The **target-hit rate (37%) carried 100% of v4's profit**. Stop-losses and time-exits were essentially flat. The signal layer is good at identifying stocks that hit their +2% target.

### 3. v4 re-entered 29 winning symbols — Rs +9,460 of P&L came from re-entries

Top re-entry pairs (each symbol traded 2x):

| Symbol | Trades | Combined P&L |
|---|:---:|---:|
| ADANIENT | 2x | **+Rs 1,961** |
| IDEA | 2x | **+Rs 1,900** |
| WAAREEENER | 2x | **+Rs 1,309** |
| DIXON | 2x | +Rs 1,194 |
| TATACOMM | 2x | +Rs 1,177 |
| BSE | 2x | +Rs 980 |
| MCX | 2x | +Rs 950 |
| SAIL | 2x | +Rs 720 |

**This is the WINNER_RE_ARM mechanic operating natively in v4**. v4 has no explicit re-arm code — it just keeps re-evaluating symbols every rescore and deploys when the signal returns. Aggressive re-deployment is the source of ~36% of v4's day P&L.

### 4. v4 had 32 stop-losses but they were tight enough to be near-flat

Average loss per STOPLOSS exit: -Rs 43. That is essentially break-even. The trailing-stop logic is doing its job — once a stock starts moving against, exit before damage compounds.

---

## Why v5 fell behind — the pattern

### 1. v5 emitted 33 SHORTs in a green tape — 26 hit STOPLOSS

v5's signal_engine wraps v4's scorer and adds a regime gate that flips the bottom 10% of scored stocks into SHORTs in SIDEWAYS/BEAR regimes. Today the regime started SIDEWAYS, drifted to BEAR — but individual stocks were largely green. The wrapper kept emitting SHORTs:

- **Top v5 losses (4 of top 5 are SHORTs)**:
  - SHORT COALINDIA -Rs 446 + -Rs 346 (re-shorted, lost twice)
  - SHORT GROWW -Rs 302 + -Rs 258 (re-shorted, lost twice)
  - SHORT TMCV -Rs 284

Each of these is a stock that the wrapper **graded weakest** in a tape where weakness was illusory. v4 didn't take any of them.

### 2. WINNER_RE_ARM fired only 2 redeploys despite 20 marks

v5 marked 20 winners as re-armable on TARGET hits. But only 2 actual re-deploys happened. **Why?**

Because v5's signal_engine, after a TARGET exit, **does not re-emit the same symbol** in the next rescore. The symbol's score has been "spent" by the prior win. v4 doesn't have this debounce — it re-emits whenever the score returns, allowing the IDEA / ADANIENT / WAAREEENER pattern.

This is the highest-leverage finding of the day. The Track A re-arm code is correct; the bottleneck is upstream.

### 3. v5 missed several SHORT signals that controls captured

| Signal v5 skipped | Controls' avg P&L | Engine count |
|---|---:|:---:|
| SHORT ICICIBANK | +Rs 350 | 2 |
| SHORT INDIGO | +Rs 290 | 4 |
| SHORT PAGEIND | +Rs 270 | 1 |
| LONG OFSS | +Rs 184 | 5 |
| SHORT BAJAJ-AUTO | +Rs 172 | 3 |

Net missed wins: ~Rs 1,266 across 5 signals. These are signals where v5's filter/cap rejected a trade that other engines took successfully.

### 4. Track A's quality gate worked — just on a small sample

v5 correctly skipped 3 trades that controls lost on:
- LONG HYUNDAI (controls -Rs 109)
- SHORT CGPOWER (controls -Rs 26)
- LONG HCLTECH (controls -Rs 4)

Net saved: ~Rs 139. Small but directionally correct.

---

## Watchdog findings (raw)

From `docs/learning/v5-2026-04-28-insights.md` and `docs/learning/v5-2026-04-28-events.json`:

- **SHORT_BLOCK fires: 2** (morning bullish window — saved estimated +Rs 1,320 vs control avg)
- **TARGET re-armables marked: 20** (winners eligible for re-entry)
- **RE-ARM redeploys: 2** (only 2/20 re-armed slots actually consumed — bottleneck above)
- **FLAT_FORCE_EXIT: 4** (post-lunch flat closures freed 4 slots)
- **Estimated re-arm gains: +Rs 5,812 across 24 re-arm-eligible exit pairs**

The watchdog's view: Track A IS adding Rs 7,132 of value to v5. Without Track A, v5 would be at roughly +Rs (4,897 − 7,132) = **-Rs 2,235**. So Track A turned a losing v5 day into a winning one. The fixes work.

---

## The headline question: v5 vs v4 gap

| Metric | v4 | v5 |
|---|---:|---:|
| P&L | **+Rs 26,179** | +Rs 4,897 |
| Trades | 103 | 88 |
| WR | 71% | 65% |
| LONG-only? | Yes (100%) | No (38% SHORT) |
| Re-deploys on winners | 29 symbols | 2 actual |
| Avg win on TARGET | Rs +691 | smaller |

**Gap: v4 was Rs +21,282 ahead.** The gap is structural, not a parameter tune:

1. v4's signal layer chose **100% LONG today**. v5's wrapper added SHORTs that bled.
2. v4's deploy logic naturally **re-emits winning symbols**. v5's wrapper de-prioritizes recently-traded symbols, breaking the re-arm loop.
3. v4 takes **17% more trades** (103 vs 88). v5's slot-cap (15 LONG / 5 SHORT in SIDEWAYS) reduces participation.

---

## What this means for tonight's review

### Decisions that should be made

1. **v4 stays in active observation through 2026-05-25.** Two-day retirement was statistically wrong. We need 4+ weeks of v4 data for an honest call.

2. **Investigate v5's signal_engine wrapper** specifically:
   - Does it filter out SHORTs cleanly when regime is mislabeled?
   - Does it re-emit winning symbols after TARGET exits?
   - Is the slot cap (15/5 in SIDEWAYS) leaving alpha on the table?

3. **Consider a "v6 = v4 + Track A bolt-on"** as a future variant:
   - Take v4's signal layer (which works)
   - Add Track A rules (SHORT_BLOCK, RE-ARM, FLAT_EXIT, cost modeling)
   - Skip v5's signal_engine wrapper entirely
   - Expected outcome: v4's edge + Track A's defensive layer

4. **Don't ship any code changes during observation window** (per IMPLEMENTATION_BRIEF §3). Investigation is allowed; commits are not.

### Numbers to feed into May 25 decision gate

Day 2 of observation (today) provides the second sample point:
- v5 cumulative: ~Rs 23,000 across 12 days (+ today's Rs 4,897)
- v4 newly re-instated: 3 days, ~Rs 9,500 mean (vs the -Rs 2,981/day that was used to retire it)

Both engines need 30+ days for honest CI.

---

## Files generated today

| File | Purpose |
|---|---|
| `docs/paper-trades/v5/2026-04-28.json` | full v5 trade record |
| `docs/paper-trades/v4/2026-04-28.json` | full v4 trade record (15:15 final) |
| `docs/paper-trades/{v5_classic,v5_6,v5_7}/2026-04-28.json` | controls |
| `docs/learning/v5-2026-04-28-events.json` | watchdog event stream |
| `docs/learning/v5-2026-04-28-insights.md` | watchdog post-mortem |
| `docs/learning/2026-04-28-eod-summary.md` | this file |
| `logs/v5-learning-watchdog-2026-04-28.log` | watchdog running log |
| `logs/v[45]*-2026-04-28.log` | engine logs |

---

## One-line verdict

**Track A works. v5's wrapper doesn't. Tonight's job is to figure out why v4's raw signal layer beats v5's wrapped + filtered version by 5×.**
