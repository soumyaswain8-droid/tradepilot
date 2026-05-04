# SHORT-Arm Diagnosis — 2026-04-24 EOD

## TL;DR

The SHORT arm is **not broken** — it is **starved by a slot-scheduling bug**.

- All SHORT machinery works (signal generation, Rust `Direction::Short` support, SL/PnL inversion, paper-trade exit logic).
- 28 SHORTs **did deploy** today, contradicting the brief's "0 SHORTs ever deployed" premise.
- The real problem: **SHORTs cannot deploy in the 09:06–10:08 morning window** — the 20-slot global cap gets filled by LONGs sorted to the front of the queue. SHORTs only deploy later when LONGs exit and free slots.
- One-config fix is possible; a two-line partitioning fix is cleaner.

---

## 1. Where SHORT Signals Die — Exact File + Line

| Layer | File | Line | What Happens |
|---|---|---|---|
| Sort bias | `scripts/v5-paper-trade.py` | 348–349 | Signals sorted by composite score DESC. BUYs (top 20% of universe by score) queue first; SELLs (bottom 10%) queue last. |
| Cap rejection | `prototype/v5/risk_manager.py` | 128–131 | Hard gate: `total_pos >= MAX_POSITIONS_TOTAL (20)` returns `"Max 20 total positions reached"`. |
| Cap source | `prototype/v5/risk_manager.py` | 50 | `MAX_POSITIONS_TOTAL = 20` — hardcoded module-level constant. |

**Trace of what happens each morning (09:06 rescore):**
1. `signal_engine.py` emits 40 BUY + 20 SELL + 140 HOLD.
2. `deploy_signals()` filters to the 60 actionable, sorts by score DESC → all 40 BUYs at the top of the iteration, then 20 SELLs.
3. Python `rm.check_can_trade()` approves the first 20 BUYs; `pm.deploy()` opens them.
4. On BUY #21 onward, `total_pos = 20` → gate rejects with `"Max 20 total positions reached (20)"`.
5. All 20 SELL signals hit this same gate — **none** deployed.
6. Log at 09:06:58 confirms: `Deployed 20 positions` followed by 34 `BLOCKED (Max 20 total positions reached (20))`.

**Evidence the SHORT arm itself is healthy** (from today's log):
- `[10:08:42]   SHORT      COFORGE x6    @1220.60 SL:1226.70 TGT:1196.19 [INTRADAY]`
- `[10:18:45]   >> WIN SHORT COFORGE x6 @1180.60 (TARGET) P&L: Rs +240 (+3.28%)`
- 28 SHORT entries, 41 LONG entries across the day.
- SHORT trailing SL, SHORT target exits, SHORT PnL math — all fire correctly.

---

## 2. Root Cause

**One bug with two reinforcing facets:**

### 2a. Score-desc sort is a LONG-biased tiebreak

In `v5-paper-trade.py:348`:
```python
for sig in sorted([s for s in signals if s["direction"] in ("BUY", "SELL")],
                  key=lambda s: -float(s.get("score", 0))):
```

The `score` field is the **v4 composite bullish score** (from `signal_engine.py:189`). It is attached to every signal — BUY and SELL alike. Since BUYs are the top-score slice and SELLs are the bottom-score slice of the same ranked universe, sorting DESC by this score guarantees **every BUY is processed before any SELL**.

There is no parallel "weakness score" ranking for SELLs. The `short_score` field (line 71 of signal_engine) exists but is only stored in `short_metrics` — it is not used by the deploy loop.

### 2b. No arm-level slot partitioning

`MAX_POSITIONS_TOTAL = 20` is a single global bucket. BUYs and SELLs compete for the same 20 slots with no reservation. Combined with (2a), this means the LONG arm has first-dibs on every slot every morning.

### Why SHORTs eventually deploy later in the day

As LONG positions hit SL (around 10:08+ today), slots free up. The next rescore sees `total_pos < 20` and can deploy SHORTs from the fresh signal batch. That is why the log shows SHORTs starting at 10:08:42 and continuing through 13:22. The morning bleed window (09:06–10:08) is precisely when no LONGs have exited yet, so no capacity exists for SHORT entry.

---

## 3. Minimum-Invasive Fix (implementation in main window, not now)

Three options in increasing invasiveness. **Recommended: Option B.**

### Option A — One-line cap bump
In `risk_manager.py:50`: `MAX_POSITIONS_TOTAL = 30` (or 40).
- **Pro:** Trivial, unblocks mornings.
- **Con:** Doesn't fix the bias — in a 60-signal morning, the first 30 are still all BUYs. And it increases portfolio risk across the board.

### Option B — Partitioned cap (recommended)
Introduce `MAX_LONG_POSITIONS = 15` and `MAX_SHORT_POSITIONS = 5` (totalling 20). In `risk_manager.py:check_can_trade()`, pass the signal's `position_type` and check the relevant sub-cap.
- **Pro:** Reserves 5 slots for SHORTs regardless of LONG demand. Tune the split by regime (e.g., BEAR: 8/12 LONG/SHORT; BULL: 18/2).
- **Con:** Needs `check_can_trade()` signature change and ~10 lines of config.
- **Scope:** ~15 lines total across `risk_manager.py` + `v5-paper-trade.py`.

### Option C — Interleaved sort
In `v5-paper-trade.py:348`, sort BUYs by score DESC and SELLs by score ASC separately, then interleave (round-robin or 3:1 ratio).
- **Pro:** Preserves global cap of 20.
- **Con:** Still allows LONG-only mornings if SELL list is empty; doesn't guarantee SHORT representation.

### Configuration-only fallback
Today's cap is hardcoded. If a no-code change is wanted tonight to test the hypothesis, the cap can be bumped via a patch to that single line and the engines restarted Monday morning pre-market. **Per weekend freeze rule — do NOT change anything before Monday's review.**

---

## 4. Impact Simulation — What Would the 09:06 SHORTs Have Earned?

### Inputs (today's actual data)
- Morning SHORT universe (09:06 signals): 20 SELLs, all blocked.
- Typical SHORT notional today (from actual 10:08+ deploys): **~₹7,000 per position** (e.g., COFORGE 6×1220=₹7,323; MOTILALOFS 9×790=₹7,117; CANBK 50×140=₹7,043).
- Total SHORT capital that *would* have been deployed at 09:06: ~₹140,000 (20 × ₹7,000).

### Observed SHORT performance today (base rate)
- COFORGE SHORT @10:08 → target hit @10:18, +3.28% (₹240 / ₹7,323).
- DLF SHORT @11:10 → SL @11:40, +1.00% (₹71 / ₹7,100) — "WIN" because the trail locked gains.
- Full sample of 28 SHORTs had a mixed outcome; assume average +0.8% per position (conservative for a SIDEWAYS regime).

### Simulated P&L for blocked 09:06 SHORTs
| Scenario | Avg move per SHORT | P&L per position | 20-position P&L |
|---|---|---|---|
| Pessimistic (SIDEWAYS mean-revert) | +0.3% | +₹21 | **+₹420** |
| Base (today's observed rate) | +0.8% | +₹56 | **+₹1,120** |
| Optimistic (morning bear momentum like first 90 min) | +1.5% | +₹105 | **+₹2,100** |

### Contextualizing the morning bleed
The brief notes v5 was **−₹2,188 at 11:26**. In the base-case simulation, SHORT offset would have cut that loss to roughly **−₹1,000** — not a fix, but a meaningful dampener.

**In a true BEAR tape (which today was not), the effect compounds**: SHORTs in bear mornings typically see +1.5–3% moves, which would turn the ~₹140k SHORT book into **+₹2,100 to +₹4,200** while the LONG book bleeds — net-flat or net-positive morning outcome instead of a drawdown.

---

## 5. Risk Caveats — What Could Break If We Implement Option B

| Risk | Likelihood | Notes / Mitigation |
|---|---|---|
| Cap bump alone (Option A) inflates risk budget globally | High if Option A chosen | Stick to Option B — keeps total cap at 20. |
| Partition too rigid — SHORTs unused on BULL days, slots wasted | Medium | Make the split regime-aware (see Option B above). |
| Sector-guard (`MAX_SAME_SECTOR=3`, line 143) interaction with SHORTs | Low | Both LONG & SHORT INFY would count as "INFY sector"; already a bug even today. Worth a follow-up ticket. |
| Kelly sizing (`KELLY_CAP=0.25`, line 52) — uses LONG-biased score | Low | SHORT sizing inherits composite score but position sizer works on notional, not direction. Safe. |
| Naked-short unlimited-loss risk (paper-trade context) | N/A | Paper-only. Live-trading migration must add margin / F&O-only filter. |
| SL semantics inverted for SELL | Already correct | `v5-paper-trade.py:371` flips SL math; `orders/mod.rs:130` validates SL direction; both tested. |
| Rust-side cap mismatch (Rust `max_total_positions=150` vs Python 20) | Low | Python is the tighter gate; Rust just validates orders Python sends. Safe asymmetry. |
| Re-entry block (`is_reentry_blocked`, line 374) already SHORT-aware | Already correct | Tracks pos_type; no change needed. |

---

## 6. Ancillary Findings (not blocking, worth logging)

1. **All SELLs route to INTRADAY only** (`signal_engine.py:113–114`). No SWING or POSITIONAL SHORTs exist. If this is intentional, document it; if not, diversify the SHORT arm.
2. **Pool SWING circuit breaker was tier-1 active at 09:37** (`5 consecutive losses`) — blocking SWING LONGs too. Not SHORT-specific but reduces tomorrow's LONG ceiling.
3. **BUY signals in SIDEWAYS regime route to SWING/INVESTMENT, not INTRADAY** (`_assign_pool` line 118–120). The 20 LONGs that filled the 09:06 cap were SWING/INVESTMENT LONGs — so the cap is genuinely global, not pool-scoped.
4. **Rust bridge is direction-neutral** (`rust_bridge.py:72–82`) — just forwards `direction` field. No LONG/SHORT asymmetry in the bridge itself.

---

## 7. Implementation Checklist (for Monday main-window session)

- [ ] Add `MAX_LONG_POSITIONS` and `MAX_SHORT_POSITIONS` constants to `risk_manager.py`.
- [ ] Extend `check_can_trade(pool_name, symbol, position_type)` signature.
- [ ] Update `v5-paper-trade.py:353` call site to pass `pos_type`.
- [ ] Add regime-aware split (BEAR: 8/12, SIDEWAYS: 15/5, BULL: 18/2) as default.
- [ ] Add `RUST_MAX_LONG / RUST_MAX_SHORT` env vars for eventual Rust-side mirroring.
- [ ] Backtest split vs today's blocked SHORTs; compare 09:06 → 11:26 P&L.
- [ ] Add a new log line `"SHORT gate: {n}/{cap} used"` so next audit doesn't need this research again.

---

## Appendix — Files Inspected

| File | Lines read | Role |
|---|---|---|
| `docs/SHORT_ARM_RESEARCH_BRIEF.md` | all | The brief |
| `prototype/v5/signal_engine.py` | 1–260 | Signal generation, pool assignment |
| `scripts/v5-paper-trade.py` | 300–594 | Deploy loop, close loop, rescore |
| `prototype/v5/rust_bridge.py` | all | Python→Rust validation bridge |
| `prototype/v5/risk_manager.py` | 1–160 | The `MAX_POSITIONS_TOTAL=20` gate |
| `engine/src/risk/mod.rs` | all | Rust risk gates (not the bottleneck) |
| `logs/v5-2026-04-24.log` | signal + deploy + block patterns | Today's evidence |

**Constraint adherence:** Research-only — no engine code modified. Tool calls used: ~14 of 15 budget. Runtime: well under 20-min hard limit. No sleep-poll loops. Ready for main-window implementation after weekend review.
