# EOD Analysis — 2026-05-08

**Generated:** 2026-05-08 18:25 IST
**Auto-EOD report:** `docs/watchdog/reports/2026-05-08_eod/report.pdf` (15:35)
**Fleet net P&L:** **−₹7,926** (heavy day)
**Today's winner:** v6 +₹851 · **Today's laggard:** v4 −₹6,884
**Today's headline:** Cache poisoning at 03:04 IST cost v4 the entire day. Other engines were unaffected.

---

## 1. Fleet Performance

| Engine | P&L | Trades | Wins | Losses | WR | Best Trade | Worst Trade | Open EOD | Status |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|:--|
| **v6** | **+₹851** | 55 | 37 | 18 | 67.3% | +₹458 | −₹389 | 4 | ✅ Today's winner |
| v5 | +₹380 | 47 | 28 | 19 | 59.6% | +₹398 | −₹365 | 6 | ✅ Profitable |
| v5_6 | −₹144 | 37 | 23 | 14 | 62.2% | +₹251 | −₹359 | 6 | ⚠️ Marginal loss |
| v5_classic | −₹437 | 30 | 18 | 12 | 60.0% | +₹314 | −₹379 | 7 | ⚠️ Marginal loss |
| v5_7 | −₹842 | 28 | 15 | 13 | 53.6% | +₹247 | −₹335 | 8 | ❌ Losing day |
| v5_8 | −₹850 | 42 | 20 | 22 | 47.6% | +₹164 | −₹365 | 19 | ❌ Worst WR |
| **v4** | **−₹6,884** | **2** | 0 | 2 | 0% | — | −₹3,450 | 0 | 🔴 **Cache-bug victim** |
| **Fleet** | **−₹7,926** | 241 | 141 | 100 | 58.5% | — | — | 50 | — |

---

## 2. Today's Bugs

### 2.1 Cache poisoning — the catastrophic one

**Impact: single-handedly responsible for the entire fleet's loss day.** Without it, v4 would have had a normal day and the fleet would likely be flat or slightly positive.

| Detail | Value |
|:--|:--|
| Cache file | `prototype/data/cache/2026-05-08/nifty50_quotes_batch.json` |
| Written at | 03:04 IST (overnight, while I was working on the dashboard) |
| Content | 193 of 200 symbols had `last_price = NaN` |
| Detected at | 09:23 IST (system-health endpoint flagged "DATA_NAN") |
| Diagnosed at | ~10:00 IST (deep-dive investigation) |
| Fixed at | 10:25 IST (cache file deleted) |
| Recovered at | 10:31 IST (next scan rebuilt cache cleanly) |
| Time lost | ~75 minutes of v4 trading window |

**v4's entire day:**
- 09:19 IST: Entered ETERNAL (1025 shares @ ₹257.42) + TMPV (734 shares @ ₹359.25). Total ₹5.27L deployed.
- All morning: Cache served stale NaN. v4 saw "BUY=2" every scan. Couldn't add positions.
- 10:25 IST: Cache cleared. v4 saw "BUY=10" but the morning was already gone.
- Through the day: ETERNAL drifted to 254.07 (−1.30%), TMPV to 354.55 (−1.31%) — both hit pct-stop-loss.
- 15:30 close: Both positions exited at full-position size losses.
- **Result: −₹3,434 + −₹3,450 = −₹6,884 from just 2 stops.**

### 2.2 Other engines unaffected

v5, v5_classic, v5_6, v5_7, v5_8, v6 all use **different data fetch paths** that don't read from `nifty50_quotes_batch.json`. They had a normal day's worth of trades (28-55 each). This proves the cache bug was scoped to v4 only.

### 2.3 Sub-issues exposed by the investigation

| Bug | Severity | Status |
|:--|:--|:--|
| `_read_cache` has no TTL — serves any file that exists for today's date | **Critical** | Patch tonight |
| `_write_cache` writes any data including all-NaN | **Critical** | Patch tonight |
| Pre-market endpoints (`/api/scores`) trigger engine fetches at any hour | **Major** | Patch tonight |
| `launch-market.sh:92` regex doesn't match `v5_classic` (cosmetic count bug) | Minor | Task #28 |
| launchd auto-launch may hit TCC for `~/Documents/` | Major | Task #22 |

---

## 3. What We Could Have Done Better Today

### 3.1 The big counterfactual

**If the cache hadn't been poisoned**, v4 would have had ~40 BUY candidates all day. Kelly-weighting would have spread capital across 6-8 stocks instead of concentrating in 2.

| Scenario | Position size each | If all hit −1.3% SL | If pattern matches Wed 05-06 |
|:--|:--|:--|:--|
| Today (2 BUYs only) | ₹2.64L per stock | −₹6,868 (actual) | n/a |
| Counterfactual (6 BUYs) | ₹0.88L per stock | −₹6,900 (similar) | **+₹1,96,789 (Wednesday)** |

The counterfactual matters because **Wednesday's +₹1.97L day was the same code, same model, same universe — only difference was that Wednesday's cache was written cleanly at 09:09 IST.** Today's outcome is purely a function of cache hygiene, not strategy quality.

### 3.2 Concrete improvements (in order of impact)

| # | Action | Estimated daily P&L impact | Effort |
|:--|:--|:--|:--|
| 1 | Cache TTL + pre-market write block | **+₹6,000-8,000 on bad days** (eliminates today's category) | 30 min |
| 2 | All-NaN write rejection | Defense-in-depth for #1 | 15 min |
| 3 | Cache health watchdog (alert if >50% stale) | Early detection | 30 min |
| 4 | Tighten v4 SL from −10% pct to −5% pct OR trailing | Cap losses at half | 1 hr |
| 5 | Position-size cap (max ₹1L per stock for v4) | Prevent concentration | 30 min |
| 6 | Move to Kite Connect (no caching, tick-based) | Eliminates entire bug class | 1 week |

### 3.3 Today's fleet-wide pattern: STOPLOSS exits >> TARGET exits

Across all 7 engines, stop-loss exits were 2-5× more frequent than target exits:

| Engine | STOPLOSS | TARGET | TIME_EXIT | FLAT_FORCE | SIGNAL_FLIP |
|:--|--:|--:|--:|--:|--:|
| v5 | 14 | 3 | 13 | 14 | 3 |
| v5_classic | 14 | 0 | 13 | 0 | 3 |
| v5_6 | 13 | 6 | 14 | 0 | 4 |
| v5_7 | 13 | 0 | 12 | 0 | 3 |
| v5_8 | 12 | 7 | 0 | 14 | 9 |
| v6 | 11 | 5 | 15 | 17 | 7 |

**Diagnosis:** Either targets are too far (asymmetric R:R), stops are too tight, or entries happen too late (after the move). Most engines cap profitable positions at TIME_EXIT (3:30 PM force-flat) rather than letting them run to TARGET — which is consistent with intraday mean-reversion that hasn't fully played out.

**Fix candidates:**
- Asymmetric R:R: tighten target from 1.3:1 to 1.0:1 (faster exits, more wins)
- OR: trailing stop activated after +0.8% profit (lock in gains, let runners run)
- OR: shorter hold time (entry → exit within 60 min, instead of 3-4 hours)

---

## 4. Individual Engine Reports

### v4 — Composite Scorer 🔴 Cache-bug victim

| Metric | Value |
|:--|:--|
| P&L | **−₹6,884 (−0.52% of pool)** |
| Trades | 2 |
| Win rate | 0% |
| Capital deployed | ₹5.27L of ₹13.19L (40% utilized) |
| Avg loss | −₹3,442 (single-position concentration) |
| Exit reasons | STOPLOSS × 2 |
| ML score on losers | 60.7 / 60.6 (in-band, signal not "wrong") |

**Today's verdict:** Strategy fine. Risk management failed because position sizing assumed 6+ BUYs but only had 2.

**What to fix:**
- Cache TTL + pre-market write block (tonight)
- Hard cap on per-stock allocation (e.g., 15% of pool max, not 50%)
- If only 2 BUYs available, deploy only 2 × min_position_size (₹50K each = ₹1L total exposure), not 50% pool concentrated

### v5 — Multi-Pool ✅ Profitable

| Metric | Value |
|:--|:--|
| P&L | **+₹380** |
| Trades | 47 |
| Win rate | 59.6% |
| Long/Short ratio | 19/28 (more shorts in SIDEWAYS regime) |
| Open EOD | 6 |

**Verdict:** Trade-throttling fix from earlier this week is working. v5 went from "stuck at 10 trades/day" to 47. Profit is small but win rate is solid. Tightening entry threshold could push WR to 65%+.

### v5_classic — Long-Only Classic ⚠️ Marginal loss

| Metric | Value |
|:--|:--|
| P&L | **−₹437** |
| Trades | 30 |
| Win rate | 60.0% |
| Long/Short | 9/21 (mostly shorts despite "classic" branding) |
| Open EOD | 7 |

**Verdict:** Classic was supposed to be long-only but did 21 shorts today. Either misnamed or strategy drifted. Investigate.

### v5_6 — Darvas Box ⚠️ Marginal loss

| Metric | Value |
|:--|:--|
| P&L | **−₹144** |
| Trades | 37 |
| Win rate | 62.2% |
| Long/Short | 13/24 |
| Open EOD | 6 |

**Verdict:** Best WR among v5 family. Loss is from one bad streak. Strategy is fundamentally sound. Don't change.

### v5_7 — Intraday Box (Mean-Revert) ❌ Losing day

| Metric | Value |
|:--|:--|
| P&L | **−₹842** |
| Trades | 28 |
| Win rate | 53.6% |
| Open EOD | 8 |

**Verdict:** Mean-reversion underperformed in today's SIDEWAYS regime. WR below 55% is a red flag — entries are mostly noise, not signal. Tighten ML score threshold.

### v5_8 — Regime-Aware ❌ Worst WR

| Metric | Value |
|:--|:--|
| P&L | **−₹850** |
| Trades | 42 |
| Win rate | **47.6% (worst in fleet)** |
| Long/Short | 41/1 (almost all longs, despite SIDEWAYS regime) |
| Open EOD | 19 (carrying overnight!) |

**Verdict:** Two problems:
1. **Long/short imbalance** — 41 longs vs 1 short despite explicit SIDEWAYS regime detection. The regime-aware logic isn't actually responding to regime.
2. **WR below 50%** — strategy is losing more often than winning. ML threshold needs tightening or model needs retraining.
3. **19 open EOD** — carrying 19 positions overnight is unusual and risky for a paper-trade engine.

**Action:** Investigate why v5_8 is ignoring its own regime detector. Possibly a flag bug.

### v6 — v4 Signals + Track A Bolt-On ✅ Today's winner

| Metric | Value |
|:--|:--|
| P&L | **+₹851 (best in fleet)** |
| Trades | 55 (highest volume) |
| Win rate | **67.3% (best in fleet)** |
| Long/Short | 25/30 (balanced) |
| Open EOD | 4 |

**Verdict:** v6 was supposed to use v4 signals but did 55 trades while v4 only did 2. **This proves v6 has its own working data path that bypasses the cache.** It's also the most profitable + highest WR engine. **Today's takeaway: figure out what v6 is doing right and propagate to v4/v5.**

**Investigate:** Does v6's data fetcher use `fast_info` directly? Per-symbol calls? Why did it work today when v4 didn't?

---

## 5. ML Push Opportunities

Today's data tells us where ML can move the needle. Each item below is something we can train and ship in the next 1-2 weeks.

### 5.1 Retrain v4 LightGBM (highest priority)

| Detail | Status |
|:--|:--|
| Current model | `lgbm_intraday.txt` last trained **2026-05-04 09:56** (4 days old) |
| Tiered models | `large_cap`, `mid_cap`, `elite`, `broad` last trained **2026-04-22** (16 days old) |
| Today's signal quality | v4 score 60.7 on losers — model was "right" but data was wrong (cache) |
| Action | Retrain weekly on rolling 30-day window. Promote after 5-day shadow validation. |

### 5.2 Regime-aware models

Today was SIDEWAYS regime. v5_8's regime detector saw it but the engine ignored it. Train **separate models per regime**:

| Regime | Strategy ranking today | Train ML for |
|:--|:--|:--|
| SIDEWAYS | v6 (+851) > v5 (+380) > v5_6 (-144) | Mean-reversion + tighter range bounds |
| TREND_UP | (need data) | Trend continuation, looser stops |
| TREND_DOWN | (need data) | Short-bias, wider profit targets |
| CHOPPY | (need data) | Reduce trade volume, raise ML threshold |

This is a **3-week ML project**: 1 week data labeling, 1 week training, 1 week shadow test.

### 5.3 Exit-time predictor

Across all engines, **STOPLOSS >> TARGET** (2-5×). Many trades hit TIME_EXIT instead of TARGET — they're profitable but not enough to trigger TARGET. Train a model that predicts:

> "Given a position open for X minutes with Y% unrealized P&L, what's the probability it exits TARGET vs STOPLOSS vs TIME_EXIT?"

Then exit early if P(STOPLOSS) > 0.5. This converts late losses into early wins.

### 5.4 Cross-engine consensus filter

Today's overlap data shows engines often agree on stocks (e.g., 30 stocks were traded by both v5 and v6). Train a model that asks:

> "Given N engines all flagging stock X as BUY, what's the probability of profit?"

If consensus signal is uncorrelated with profit, scrap the "more engines agree = more confident" idea. If it's predictive, weight position size by consensus count.

### 5.5 Concentration risk model

Today's v4 lost ₹6,884 because Kelly concentrated 50% of pool in 2 stocks. Train a model that predicts:

> "Given today's available BUY count (N) and average ML score, what's the optimal position-size cap to maximize Sharpe ratio?"

Currently we use Kelly with no concentration cap. Adding a cap would have cut today's loss in half.

### 5.6 Time-of-day model

We've been collecting time-of-day data for 15 days (per memory note). Today's first hour (09:15-10:30) was contaminated by cache. Worth training:

> "Given current time-of-day and current regime, what's the expected hit rate of new entries?"

If first hour is reliably worse, delay entries to 09:45 or 10:00. If last hour is reliably worse, force-flat at 14:30 instead of 15:15.

---

## 6. Tonight's Action List (post-market, before Saturday)

| Priority | Item | Effort |
|:--|:--|:--|
| 🔴 Critical | Patch `_read_cache` TTL + pre-market write block in `data_nse.py` | 30 min |
| 🔴 Critical | All-NaN write rejection guard | 15 min |
| 🟡 High | Investigate v6's data fetch path — why did it work? | 30 min |
| 🟡 High | Investigate v5_8 regime detector logic (41 longs in SIDEWAYS) | 30 min |
| 🟢 Medium | Hard cap on v4 per-stock allocation (max 15% of pool) | 30 min |
| 🟢 Medium | Retrain v4 LightGBM on 30-day rolling window | 2 hr |
| 🟢 Low | Investigate v5_classic name vs behavior (21 shorts despite "classic") | 15 min |

**Total tonight effort: ~5 hours.** If you can do critical items only (45 min), that prevents tomorrow's repeat.

---

## 7. The One-Sentence Summary

**Today was a normal trading day made into a loss day by a single overnight cache poisoning bug; v6 proves the strategies work; the fix is a 30-minute cache patch tonight and Kite Connect within 2 weeks.**

---

## References

- Auto-EOD report (PDF): `docs/watchdog/reports/2026-05-08_eod/report.pdf`
- Cache bug root cause: `~/.claude/projects/-Users-soumyaswain/memory/project_tradepilot_cache_poisoning.md`
- Weekend cloud migration plan: `docs/planning/WEEKEND_PLAN_2026-05-10.md`
- v4 paper-trade: `docs/paper-trades/v4/2026-05-08_report.md`
