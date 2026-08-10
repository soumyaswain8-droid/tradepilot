# v10 — "Replay the April strategy" feasibility check

**STATUS: DRAFT — for Soumya's verification. Nothing implemented. No code changed.**

**Author:** Soumya Swain <soumya@suryaai.co.in>
**Date:** 2026-07-29
**Request:** build engine `v10` reusing the April strategy as it stood up to 2026-05-06.

---

## 1. Bottom line

**This experiment has already been run, and it failed.** `v8` is the April-recipe replica,
built 2026-07-06 from `docs/eod-reports/DEGRADATION_ANALYSIS_Apr-Jul_2026.md`. It has run
17 live sessions:

| | April engine target | `v8` actual |
|---|---|---|
| Return | +1%/day (Rs 10,000 on Rs 10L) | **−2,827 total** |
| Win rate | 65%+ | **28%** |
| Trades | — | 39 in 17 sessions; **zero trades on 5 days** |

`v8`'s own docstring states the intent verbatim: *"a clean-room revert to the proven April
engine — NIFTY-50, top-5, long-only, +1.5/−0.75 FIXED bracket, early entry, flat by EOD…
Target: recover +1%/day, 65%+ WR on Rs10L."*

Building `v10` to the same recipe would repeat a completed, falsified experiment. **Unless
v10 differs from v8 in some specific, stated way, it will reproduce v8's result.** Section 6
sets out what would make it a genuinely new test.

## 2. What the April recipe actually was

From `scripts/v8-paper-trade.py` (all params env-gated onto the shared v5 engine):

| Param | April value | Meaning |
|---|---|---|
| `UNIVERSE_FILE` | `universe_nifty50.txt` | NIFTY-50 only (not the current 200) |
| `MAX_POSITIONS_TOTAL` | `5` | top-5 concentration |
| `TARGET_PCT` | `1.5` | fixed target |
| `STOP_PCT` | `0.75` | fixed stop |
| `STOP_MODE` | `fixed` | no trailing |
| `SHORT_REQ_MAX_SCORE` | `-1` | long-only |
| `RESCORE_INTERVAL_MIN` | `999` | enter early on first scan, hold to bracket |
| `ML_SCORE_WEIGHT` | `0` | no ML |

## 3. "Up to May 6" is NOT the same as the April recipe

You asked for the state up to 2026-05-06. The last engine commit on or before that date is
`1d174bc` (2026-05-04, *"v5_8 + v6 + v5_classic + tiered scorer + retrained models"*).

That May-6 engine is **889 lines**; today's is **1,421** (+60%). Notably, at May-6 the
engine had **no `SCAN_INTERVAL_MIN`, no `RESCORE_INTERVAL_MIN`, and no `STOP_MODE`** — those
were all added later (today `STOP_MODE` defaults to `trailing`).

But May 6 sits *after* the April window. By May the win rate had already fallen 77% → 53%.
**So "up to May 6" captures the engine at roughly half its April edge.** If the goal is to
reproduce April, the target date should be ~2026-04-30, not 2026-05-06. **Needs your call —
see Q1.**

## 4. The degradation analysis's causal story is not supported by the evidence

`DEGRADATION_ANALYSIS_Apr-Jul_2026.md` attributes the 77% → 46% win-rate collapse to a
"complexity cascade": short book added, universe 50 → 200, late entry, longer holds, overfit
1,735-tree ML, churn.

**`v8` removed every one of those, and scored 28% — worse than the "degraded" v5 at 46%.**

That does not prove the cascade was harmless, but it does mean removing it is not sufficient
to recover April, and the stated cause is at best incomplete.

Two further checks that weaken the story:

- **Regime is not the explanation.** The engine's own daily classification shows April was
  11 SIDEWAYS / 3 BEAR and July is 15 SIDEWAYS / 4 BEAR / 1 BULL. Nearly the same mix,
  wildly different outcomes. April was *not* a bull market that flattered a long-only book.
- **The degradation is monotonic across engines**, including `v5_classic`, which carries
  none of the rebuild's additions (66% → 43%). Something affected *everything*, not just
  the engine that grew complex.

## 5. Measurement-integrity caveat on the April numbers — READ THIS FIRST

April's figures may be partly an artifact. Two concrete findings:

1. **Costs were barely booked in April.** Sessions where `total_cost > 0`, for v5:
   **April 3/14**, May 17/17, June 19/19, July 18/20. So most April days recorded P&L with
   no trading costs at all, while every later month did. April's *return* is inflated by an
   unknown amount on that basis alone.

2. **`v5_classic` has never booked costs — not once**, in any month (0/9, 0/19, 0/18, 0/20),
   and has no `total_pnl_net` field. Every "v5_classic beats v5" comparison you have seen
   compares v5 **net** against v5_classic **gross**. Correcting at v5's own measured rate
   (Rs 14.32/trade over 2,957 trades), across the 60 common sessions:

   | | |
   |---|---:|
   | v5 net | +100,697 |
   | v5_classic gross | +120,400 |
   | *apparent* v5_classic edge | **+19,703** |
   | v5_classic adjusted for costs (2,973 trades) | +77,827 |
   | **real edge vs v5** | **−22,869** |

   The frozen benchmark is behind live v5, not ahead of it.

**Costs do not change a win rate**, so they cannot explain 77% → 46% on their own. But they
do mean April's *headline return* (+1.35%/day, Rs 13,547) is not comparable to today's
numbers, and any v10 target derived from it is unsafe.

**The 77% April win rate is still unexplained.** I could not identify a mechanism. Until it
is explained, we do not know what we would be rebuilding.

## 6. What would make v10 worth running

If v10 is just "April recipe again", the answer is already known. To be a new test it must
differ deliberately. Options, cheapest first:

- **(a) v10 = v8 + costs verified + a fair target.** Re-run the April recipe but with
  correct cost booking and a target derived from *cost-adjusted* April, not raw April.
  Cheapest, but likely reconfirms v8.
- **(b) v10 = the May-6 engine verbatim** (`1d174bc`), not the April recipe. This is
  literally what you asked for and has *not* been tested — v8 is the April recipe, which is
  a different thing. It includes the tiered scorer and retrained models that the April
  recipe strips out.
- **(c) Explain April first, then rebuild.** Establish what produced a 77% win rate before
  spending a shadow slot. If it was an accounting artifact, there is nothing to rebuild; if
  it was real, we would know what to target.

**My recommendation is (c) then (b).** (b) is the honest reading of your request and is
genuinely untested; (c) protects against rebuilding an artifact. But this is your call —
the request as stated is (a), and I will build it if that is what you want.

## 7. Questions for you to verify

1. **Target date** — April recipe (~04-30) or the May-6 engine (`1d174bc`)? They are
   materially different, and only the second is untested. §3.
2. **Given v8 already failed at 28%**, what should v10 do *differently*? If nothing, we
   should expect v8's result. §1, §6.
3. **Do you accept the cost finding?** If yes, `v5_classic` is no longer the benchmark that
   beats v5, and the April baseline needs restating before any target is set. §5.
4. **Shadow slot** — v10 runs alongside 9 existing engines. Retire one first (v8 is the
   obvious candidate, being the failed predecessor), or run 10?
5. **Do you want April explained first?** I can attempt it, but I have no working
   hypothesis; regime and the complexity cascade are both ruled out.

## 8. What I verified vs what is uncertain

**Verified:** v8's config and provenance; v8's 17-session result; the cost-booking counts;
the v5_classic cost adjustment; the May-6 commit and line counts; regime mix by month.

**Uncertain:** why April's win rate was 77%; whether April's artifacts were produced by a
different accounting path; whether v5_classic's missing costs also affect its April figures
(likely, but the correction above uses v5's rate as a proxy, not v5_classic's own).
