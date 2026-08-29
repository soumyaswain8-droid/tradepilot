# HAC Audit — overlapping-window t-statistics across the codebase

**Five files compute a return t-statistic on overlapping windows. Two of them are already
corrected or already retired; the other three carry negative conclusions.**

**No stated conclusion flips. We checked, and the existing conclusions hold.**

*One correction to the record: the `mom_12_1` "5.72 → 1.49" line conflates two different
measurements. §1 sets it out. The number is real but it is not the momentum result on our books.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — quant research |
| **Version** | `v1.0.0` |
| **Status** | Complete — correctness sweep, no conclusions changed |
| **Created** | 2026-08-29 |
| **Updated** | 2026-08-29 |
| **Parent** | `breakout-hac.md` §7, closing note |
| **Scope** | 35 files triaged, 3 results re-derived |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## 1. The `mom_12_1` ambiguity — resolved, and the record needs correcting

**These are two different measurements of two different objects. They were conflated.**

::: {.gap-table}

| | (a) `quant/validate_mom121.py` | (b) the breakout lane's control |
|:--|:--|:--|
| **What is measured** | A *tradeable portfolio*: long top-N by 12-1 momentum, monthly rebalance, net of real delivery costs, excess over an equal-weight benchmark on the same universe | A *cross-sectional regression slope*: daily Fama-MacBeth of the raw `mom_12_1` signal on market-neutral h-day forward returns |
| **Return frequency** | Monthly. Month *t* → return of month *t+1*. Each month used **once** | Daily. A 21-day forward return computed at **every** session |
| **Window** | Full sample, 46 months | Holdout only, 323 sessions (Jan 2025 – Jun 2026) |
| **Overlap** | **None.** Disjoint by construction | h−1 = 20 days shared between neighbours |
| **t-statistic** | **Legitimate as computed** | **Inflated 3.8×** |
| **The number** | t = **+0.28** (N=10, rerun today); docs cite an on-book range of 0.91–1.82 | naive **+5.72** → NW **+1.49** |

:::

### What this means for the claim that was made

The statement *"mom_12_1, already on our books, goes 5.72 → 1.49"* **overstates it, and should be
corrected wherever it was recorded (including the commit message).** Three things are wrong with it:

1. **5.72 was never on our books.** It was created inside the breakout lane on 2026-08-28 as a
   control variable, and it is a regression slope, not a strategy return. The momentum result that
   is on our books is the monthly portfolio in (a).
2. **The on-books momentum number needs no correction at all.** It is non-overlapping. Rerunning
   `validate_mom121.py` today gives excess t = **+0.28** at N=10 and t = **−0.92** walk-forward.
   It was already dead, and it did not die of overlap — it died of having no excess over
   buy-and-hold-everything.
3. **The 1.49 is a window artefact, not a verdict on momentum.** Extended to the full sample the
   same slope is naive +10.97 → **NW +2.92** (§3.1). The holdout's 323 sessions are simply
   underpowered. Writing 1.49 as though it settled the momentum question is the mirror image of
   the error the audit was meant to catch.

**The honest sentence:** *the momentum factor slope survives HAC on the full sample at NW t ≈ 2.9;
the tradeable long-only monthly implementation has no excess over equal-weight (t = 0.28). Both
statements were already true before this audit and neither changes.*

`docs/research/overnight/breakout-hac.md` §4c and §7 should have the phrase *"consistent with the
factor's known on-book range of t = 0.91–1.82"* struck — it is comparing a slope to a portfolio.

---

## 2. Triage

35 files reached; 5 are OVERLAPPING. Only `swing-engine.py` had an overlapping t-stat gating
anything live, and it is currently negative (§3.3).

### 2a. AFFECTED — overlapping construction

::: {.spec-table}

| file | classification | reason |
|:--|:--|:--|
| `quant/_winner_anatomy.py` | **OVERLAPPING** | `fwd(k)` for k=5/10/21 evaluated at every stock-day; clustered by date only, no serial correction. The file that produced BREAKOUT t = 3.39 / raw 5.79. |
| `quant/_winner_anatomy2.py` | **OVERLAPPING (self-corrected)** | Same construction, but this *is* the remediation script — reports naive alongside NW at L=h/h−1/auto plus 36 disjoint subsamples. |
| `quant/orderbook_test.py` | **OVERLAPPING** | `fwd = ltp[i+h]/px − 1` at **every** snapshot for h ∈ {2,10,30,60}; a 60-snapshot horizon shares 59 of 60 with its neighbour. Ceiling ≈ √60 ≈ 7.7×. |
| `quant/hypothesis_search.py` | **OVERLAPPING** | `fwd[hbars] = c[i+1+hbars]/entry − 1` at every 5-minute bar, holds of 3–24 bars. Bonferroni applied, HAC not. Ceiling ≈ √24 ≈ 4.9×. |
| `scripts/swing-engine.py` | **OVERLAPPING** | `backtest()` scans every day, holds up to `MAX_HOLD_SESSIONS = 3`; neighbours share 2 of 3 days. Also pools 8 slots/day as iid. |

:::

### 2b. NON-OVERLAPPING — correct as computed

::: {.spec-table}

| file | reason |
|:--|:--|
| `quant/validate_mom121.py` | Monthly panel, `FWD = Mv[1:]` — month *t* → month *t+1*. Each month once. |
| `quant/validate_factor.py` | `rebal = index[lookback+1::horizon]` — steps *by* the horizon, so 21-day holds are strictly disjoint. `t = SR·√(n/ppy)` is the right construction. |
| `quant/backtest_factor.py`, `factor_zoo.py`, `factor_zoo_clean.py`, `regime_alloc.py`, `validate_sf_adjusted.py`, `validate_survivorship_free.py` | All share the same disjoint `index[252+1::H]` rebalance pattern. |
| `quant/_precursors_analyse.py` | Return t-stats are on `dr = top.groupby('date')['r'].mean()` with `r` = same-day return (h=1). One obs per date. |
| `quant/_precursors_final.py` | Same h=1 daily basket; turnover-floor sweep and short-side check on the one-day series. |
| `quant/_precursors_diag.py` | Same h=1 daily basket; vol/momentum attribution and split-half. |
| `quant/fo_vrp_analysis.py` | One record per weekly NIFTY expiry, held to expiry. Disjoint. |
| `quant/dh_straddle.py` | One delta-hedged straddle per weekly expiry, `t = μ/σ·√n` over per-expiry returns. Disjoint. |
| `quant/validate_hi52_sf.py` | Trade-level: entry on a 52-week-high cross, exit on a trailing stop; a symbol's positions cannot overlap themselves. |
| `scripts/test-mean-reversion.py` | Realized intraday P&L — one decision per stock-day, same-day exit. Each return period used once. |
| `scripts/falsify-predicates.py` | Trade-level P&L per predicate per stock-day, intraday exits, with a random control. |
| `scripts/test-classic-swing.py` | Trade-level entry/exit per symbol plus a month-end rotation holding one month. |
| `scripts/shadow-settle.py` | Realized shadow trades settled on real minute bars; each trade's window used once. |
| `scripts/weekly-stats-tracker.py` | Daily engine P&L from a daily engine; builds a 95% CI, not a t-stat. |

:::

### 2c. NOT-A-RETURN-TSTAT / NO-TSTAT — out of scope

::: {.spec-table}

| file | reason |
|:--|:--|
| `quant/winners_scan.py` | Welch two-sample test on *prior-day features* between winners and non-winners. The dependent variable is a feature, not a return. Already self-flags its cross-sectional inflation. |
| `quant/_precursors_build.py` | Panel builder; no test statistic. |
| `scripts/v5-backtest.py`, `scripts/opt1k.py`, `scripts/real1k.py`, `prototype/backtest/runner.py`, `prototype/app.py` | No t-statistic. Grep hits were `pilot_state.json`, `api_rust_status`, and Sharpe annualization. |
| `prototype/v10/risk_manager.py`, `prototype/v5/{pool_manager,regime_detector,risk_manager}.py` | Grep hits were `get_status()` / `current_state` (an HMM state id). No t-stat. |
| `scripts/paper-trade-engine.py`, `paper-trade-aggressive.py`, `v5-paper-trade.py` and the v4–v10 engine family | Live engines; `print_status` only. |
| `scripts/backtest-rrg-sensor.py` | Profit-capture % against a threshold grid; no t-statistic. |

:::

---

## 3. Re-derivations

Lag = holding period throughout (Bartlett kernel, L = h). This is the *known* dependence length
implied by an h-day overlap, not an estimated one — the Newey-West automatic bandwidth is the wrong
tool here, for the reason set out in `breakout-hac.md` §2.

### 3.1 `mom_12_1` Fama-MacBeth slope — the one worth re-deriving

Daily cross-sectional OLS of market-neutral h-day forward returns on `mom_12_1` (with the BREAKOUT
dummy, matching the parent spec). Panel rebuilt in memory from `sf_ret` + `sf_turn`, 1,935,973
stock-days over 980 sessions, tradeable filter ≥ Rs 1 crore 20-day median turnover.

::: {.changes-table}

| window | h | scan days | coef | naive t | **NW t (L=h)** | inflation |
|:--|--:|--:|--:|--:|--:|--:|
| train | 1 | 636 | +0.0507% | +2.47 | **+2.37** | 1.04× |
| train | 5 | 636 | +0.2603% | +5.47 | **+2.89** | 1.89× |
| train | 21 | 636 | +0.9221% | +9.47 | **+2.59** | 3.65× |
| holdout | 1 | 343 | +0.0291% | +0.95 | **+0.93** | 1.03× |
| holdout | 5 | 339 | +0.1739% | +2.45 | **+1.26** | 1.94× |
| holdout | 21 | 323 | +0.8787% | **+5.72** | **+1.49** | **3.83×** |
| **FULL** | 1 | 979 | +0.0431% | +2.52 | **+2.44** | 1.04× |
| **FULL** | 5 | 975 | +0.2302% | +5.80 | **+3.02** | 1.92× |
| **FULL** | 10 | 970 | +0.4441% | +7.79 | **+2.96** | 2.63× |
| **FULL** | 21 | 959 | +0.9075% | +10.97 | **+2.92** | 3.76× |

:::

The holdout row reproduces `breakout-hac.md` §4c to the digit (5.72 → 1.49). **The h=1 control
barely moves (1.03–1.04×), as it must — h=1 windows do not overlap.** The implementation is behaving.

**The finding the holdout-only view hid.** Extended to the full sample the slope is NW **+2.92** at
h=21 and **+3.02** at h=5. Kernel-free confirmation on the full-sample h=21 series: 21 disjoint
subsamples (every 21st day, n≈45 each) give mean t = **+2.43**, range [+2.21, +2.82], and **21 of 21
exceed 1.96**. So the momentum slope is a real feature of this panel that survives HAC — the 1.49
is what 323 sessions can resolve, not a verdict on momentum.

**Does the stated conclusion survive?** Yes, both of them. BREAKOUT's residual after controlling for
momentum is still NW t ≤ 1.46 and BREAKOUT is still dead. And momentum is still not *tradeable* —
see §3.2. What does not survive is the sentence claiming the 1.49 matches our on-book momentum range.

### 3.2 Monthly `mom_12_1` — the non-overlapping control

Rerun of `validate_mom121.py`'s construction, with NW applied at several lags **to demonstrate it
does nothing**. Excess over equal-weight, net of delivery costs at Rs 1,00,000.

::: {.metrics-table}

| N | n months | excess pp/yr | naive t | NW t (L=1) | NW t (L=3) | NW t (L=6) |
|:--|--:|--:|--:|--:|--:|--:|
| 5 | 46 | −3.40 | −0.21 | −0.22 | −0.24 | −0.25 |
| 10 | 46 | +3.14 | **+0.28** | +0.31 | +0.31 | +0.34 |
| 20 | 46 | +0.86 | +0.11 | +0.11 | +0.12 | +0.12 |
| 50 | 46 | +3.94 | +0.58 | +0.55 | +0.55 | +0.51 |

:::

**HAC moves nothing beyond the third decimal.** This is the control that proves the machinery is
discriminating: it corrects overlapping series hard and leaves disjoint ones alone. Walk-forward on
the same construction is **−11.54 pp/yr, t = −0.92**. Conclusion unchanged and unaffected.

### 3.3 `scripts/swing-engine.py` — the only overlapping t-stat gating a live lane

`backtest()` prints a pooled t over every setup as though independent. It carries **two** errors:
up to 8 setups share one market day, and 3-session holds mean consecutive scan-days share 2 of 3
days. The in-file gate is `m > 0 and t > 2 → "RULE HAS HISTORICAL SUPPORT"`.

::: {.metrics-table}

| stage | value |
|:--|--:|
| Reproduction — pooled, as the file prints it | net **−0.3526%/trade**, t = **−1.68** (n=93 setups, 31 scan days, 8% hit rate) |
| Correction 1 — collapse to one obs per scan day | −0.6152%/day, t = **−2.55** |
| Correction 2 — + Newey-West, L = `MAX_HOLD_SESSIONS` = 3 | **t = −1.94** |
| Kernel-free — 3 disjoint subsamples (every 3rd scan day) | t = −1.23 / −1.80 / −1.28, mean **−1.44**, none past \|t\| = 2 |
| In-file gate `m > 0 and t > 2` | **FAILS** — as it already did |

:::

**The stated conclusion survives, because the rule is currently negative.** The gate reads
`m > 0`; the mean is −0.35%/trade, so `swing-engine.py` already prints *"NO significant edge
in-sample — deploy as EXPERIMENT ONLY"*. The `v5_swing` lane is correctly labelled. Nothing to
revoke.

Two things worth recording anyway:

- **The correction goes the other way here (0.87×, not >1×).** Collapsing to daily means removed
  within-day dispersion that had been *inflating the denominator*; the cross-sectional error and
  the serial error pointed in opposite directions and roughly cancelled. Do not assume the
  correction always shrinks a t — assume only that the uncorrected number is uninterpretable.
- **The backtest is near-powerless regardless.** The cache holds 74 sessions
  (2026-05-04 → 2026-08-17) yielding 93 setups across 31 scan days. Neither a pass nor a fail from
  this window should move anyone. **If this rule ever prints a positive t > 2, it must be
  re-derived with the daily-collapse + NW(L=3) treatment above before it licenses anything.**

### 3.4 Noted, not re-derived — negative results that only get more negative

Per the brief: a negative result that a correction makes more negative changes nothing.

- **`quant/orderbook_test.py`** — overlapping intraday forward returns at every snapshot. Stated
  conclusion is *"NOTHING beats the 0.106% toll."* Correction can only widen the shortfall.
- **`quant/hypothesis_search.py`** — overlapping 5-minute-bar forward returns. Best in-sample
  t = 0.90 against a ~4.0 Bonferroni bar, all top-5 flip negative out of sample. Already dead by
  two margins.
- **`quant/_winner_anatomy.py`** — the source of the inflated BREAKOUT numbers, already fully
  corrected and retracted in `breakout-hac.md`. Nothing left to re-derive.
- **`quant/validate_factor.py`** — *not* affected (disjoint rebalances), and reported here only
  because it is the project's other momentum measurement: Sharpe 1.12, **t = 2.19 on n = 46
  disjoint 21-day rebalances**, which already **FAILS** its own deflated-Sharpe gate at 74.1%.
  Legitimately constructed, legitimately negative.
- **`quant/dh_straddle.py`** — non-overlapping weekly expiries, t = 1.13 against a pre-registered
  bar of 2.0. Already failed, no correction owed.

---

## 4. Rule for future work

**The construction to avoid.** Do not compute an h-day forward return at every date and then
t-test the pool. Consecutive observations share h−1 days of the same price path; the denominator
assumes they are independent when they are mechanically correlated. The inflation ceiling is √h —
measured here at **1.9× / 2.6× / 3.8×** for h = 5 / 10 / 21, matching the theoretical 2.2 / 3.2 / 4.6
closely enough that you should budget for the full √h.

**What to do instead**, in order of preference:

1. **Sample disjointly.** Rebalance *by* the horizon — `index[start::h]`, the pattern
   `validate_factor.py` and the whole `factor_zoo` family already use. This is the cleanest fix and
   it needs no kernel, no bandwidth choice, and no defending. Prefer it.
2. **If you must sample daily, apply Newey-West with L = h.** The overlap induces a *known*
   MA(h−1) structure. Set the bandwidth from the holding period. Do **not** use the Newey-West (1994)
   automatic rule — it is built for unknown persistence and returns L ≈ 5 regardless of horizon,
   which understates the correction badly at h = 21.
3. **Always cross-check kernel-free.** Split the series into h disjoint subsamples (every h-th
   observation) and t-test each. If the NW number and the disjoint numbers disagree, trust neither
   until you know why.
4. **Always report an h=1 row as a control.** h=1 does not overlap, so its t must barely move. If
   your correction shifts the h=1 cell materially, the implementation is wrong, not the data. Every
   correction in this document carries one; all four came in at 0.97–1.04×.
5. **Collapse cross-sectional clustering first, then correct serially.** These are two distinct
   errors and they do not always point the same way (§3.3). Reduce to one observation per date,
   *then* apply the kernel.

**Report both numbers, always.** Print naive and corrected side by side with the inflation
multiplier, the way `_winner_anatomy2.py` does. A lone corrected t hides whether the correction
was doing any work; a lone naive t is not interpretable at all.

**And the scoping rule that this audit turned on:** state which object a t-statistic belongs to
before comparing it to another one. A cross-sectional regression slope and a net-of-cost tradeable
portfolio are different claims with different bars, and a number from one does not update the
other. That conflation, not the overlap, was the only actual error found in the record.

---

## 5. Reproduction

```bash
/Users/soumyaswain/anaconda3/bin/python3 quant/validate_mom121.py     # §3.2 monthly, non-overlapping
/Users/soumyaswain/anaconda3/bin/python3 quant/validate_factor.py     # §3.4 disjoint rebalances
/Users/soumyaswain/anaconda3/bin/python3 quant/_winner_anatomy2.py    # holdout FM slope, 5.72 -> 1.49
```

The full-sample extension in §3.1 and the swing-engine correction in §3.3 were run from scratchpad
scripts that rebuild the panel in memory from `quant/data/sf_ret.parquet` + `sf_turn.parquet` using
the verbatim logic of `_precursors_build.py`; no intermediates were kept.
`sf_turn` is in **Rs lakh**; `sf_ret` is **winsorised at ±50%**.
