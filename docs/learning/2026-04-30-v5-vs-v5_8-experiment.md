# v5 vs v5.8 Experiment — Design Spec for 2026-04-30

> Origin: 2026-04-29 EOD found v5 blocked **175 LONG signals** because the
> regime-aware slot partition (BEAR → 8 LONG / 12 SHORT) starved LONGs on a
> green-tape day labelled BEAR. v4 took the same signals and made +Rs 47,354
> while v5 made +Rs 18,044 — a Rs 29K gap directly attributable to the
> partition. The slot partition was tune-up #1 of the 10 v5 fixes applied
> 2026-04-24 EOD. We need to test whether removing it closes the gap.

---

## Hypothesis

**H3 (slot-partition starvation)**: v5's regime-aware slot partition mechanically
caps LONG capacity in BEAR regime to 8 slots, even when individual stocks are
bullish. On green-tape days the regime detector lags and labels BEAR while the
tape is rising; the partition then blocks ~50% of the LONG signals that v4
takes freely. The partition was designed to defend on bear days but backfires
on mislabeled bear days.

If H3 is true, removing the partition should close most of the v5-vs-v4 gap.

---

## Intervention

| Engine | Signal layer | Slot partition | Track A | Fix #1 |
|---|---|---|---|---|
| v4 | v4 raw | none | no | no |
| v5 | v4 + wrapper | **BULL 18/2 · SIDEWAYS 15/5 · BEAR 8/12** | yes | yes |
| **v5.8 NEW** | v4 + wrapper | **disabled (20/20 in all regimes)** | yes | yes |
| v6 | v4 raw | none | yes | n/a |

v5.8 = v5 with one line changed. Implementation: monkey-patches
`prototype.v5.risk_manager.REGIME_SLOT_SPLIT` in v5.8's import block. Original
v5 untouched — both run side by side using the same risk_manager class.

---

## What we measure

### Primary

| Metric | Compare across | What it tells us |
|---|---|---|
| Day P&L | v4 / v5 / v5.8 / v6 | Headline outcome |
| Trade count | same | Did v5.8 actually take more LONGs than v5? |
| `LONG slot cap reached` log lines | v5 logs | Should still fire on v5; should be ZERO on v5.8 |
| Side mix (LONG vs SHORT) | each engine | v5.8 should look closer to v4's mix |
| Re-emissions per symbol | each engine | If v5.8 still trails v4, points to H2 (re-emission debounce) |

### Decision matrix (read tomorrow EOD)

| v5.8 vs v5 | v5.8 vs v4 | Read |
|---|---|---|
| v5.8 >> v5 (gap > Rs 10K) | v5.8 ≈ v4 | **H3 confirmed**. Partition was the bottleneck. Disable in v5 permanently after 4 more samples. |
| v5.8 >> v5 | v5.8 < v4 by Rs 5K+ | **Partition was a partial bottleneck.** Other H2/H1 issues remain. Keep investigating. |
| v5.8 ≈ v5 | v5.8 < v4 | **Partition was NOT the bottleneck.** Look elsewhere — re-emission debounce, sector concentration cap, some other gate. |
| v5.8 < v5 | both < v4 | Partition was **helping** v5 today. Likely a SHORT-friendly tape, partition reserved space for legit SHORTs. Need a bear-day sample. |

---

## Risk register

| Risk | Mitigation |
|---|---|
| v5.8 over-trades and hits the global 20-position cap fast, leaving no capacity for late-day signals | The 20-total cap still applies. If this becomes a problem, raise MAX_POSITIONS_TOTAL. But keep it constant during this experiment. |
| v5.8 takes too many SHORTs on a bull day (since SHORTs aren't capped at 12 anymore) | Fix #1 still requires absolute weakness for SHORT emission — should self-limit. |
| v5.8 introduces correlation risk by holding 20 LONGs in similar sectors | MAX_SAME_SECTOR=3 still enforced by RiskManager. |
| Slot partition was protecting against gap-down disaster days | True — the partition was designed for that. v5.8 would be exposed on a real bear day. **Do not retire v5 yet.** Run v5 and v5.8 in parallel for at least 4 weeks. |

---

## What to look for in v5.8 logs tomorrow

| Pattern | Meaning |
|---|---|
| `Deployed N positions (N Rust-validated)` where N is consistently high | Slot partition no longer constraining |
| Zero `LONG slot cap reached` lines | Confirmation patch applied |
| `Max 20 total positions reached` lines later in the day | Hit the global cap — that's expected and OK |
| Symbol overlap with v4's closed_trades growing | Closing the wrapper-vs-raw gap |

---

## Tonight's status

| Item | State |
|---|---|
| `scripts/v5_8-paper-trade.py` | ✓ shipped (copy of v5 + monkey-patch) |
| Output dir `docs/paper-trades/v5_8/` | ✓ created |
| `launch-market.sh` ENGINES (7 entries) | ✓ |
| `crash-watchdog.sh` ENGINES (7 entries) | ✓ |
| `status-digest.py` ENGINES (7 entries) | ✓ |
| Compile checks | ✓ clean |
| Bash syntax | ✓ clean |
| Monkey-patch verified to override REGIME_SLOT_SPLIT | ✓ |
| Commit status | uncommitted (per observation rule) |

---

## Tomorrow's full roster (7)

| # | Engine | Role |
|---|---|---|
| 1 | v4 | Control. Raw scorer, no caps, no Track A. |
| 2 | v5 | Wrapper + Track A + Fix #1 + slot partition. |
| 3 | v5_classic | Wrapper, no Track A. Baseline. |
| 4 | v5_6 | v5 + Darvas Box overlay. |
| 5 | v5_7 | v5 + Intraday Box overlay. |
| 6 | v6 | v4 raw + Track A bolt-on. |
| 7 | **v5.8** | **v5 with slot partition disabled.** |

---

**One day is one sample. We have 25+ trading days to May 25 gate.**
