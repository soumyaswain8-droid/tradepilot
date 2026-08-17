# Full strategy search — 3.5 months, 36 combos, train/holdout

**The ask**: simulate entries + exits + direction together over all available data
until a profitable configuration appears, then verify it is real.

**The run**: Kite 5m bars 2026-05-01 → 08-14 (201 symbols, licensed feed, fetched
fresh), 6 entry families × 3 exits × 2 direction filters = 36 pre-registered combos,
107,301 combo-trades. Train = pre-07-15 (free search), holdout = 07-15 onward (top 3
run once). Gate: holdout net > 0 at 0.0787% fees, t > 2, n ≥ 200.

## Verdict: NO configuration in this space is real-profitable

| Best on train | n | train net | holdout net | holdout t |
|:--|--:|--:|--:|--:|
| conf7/trail03/long | **4** | +0.399% | — | excluded, n<200 |
| conf6/fixed/both | 224 | +0.017% (t=0.37) | **−0.062%** | −1.02 |
| conf6/trail05/both | 224 | +0.001% | −0.076% | −1.37 |

- The train "winner" had **four trades** — the n≥200 floor existed precisely for this.
- Everything with real sample size was statistically zero on train and negative on
  holdout. The 12-symbol smoke had already shown the pattern (its leader went
  −0.242%, t=−3.15 out-of-sample).

## What this does and does not say

- **Does**: systematic entries built from OHLCV-derived predicates cannot clear
  0.0787% fees on this market at intraday horizon — fifth independent measurement
  landing at the same wall (v5 scorer, SMC, baseline, mean reversion, and now the
  composed search).
- **Does NOT**: contradict yesterday's exit result. That tested the ENGINE'S OWN
  entries (which carry +0.069% gross selection edge the synthetic rules lack) with a
  better exit → +0.0146% net at size, paired t=3.85, replicated. The validated stack
  is still: engine entries + arm0.3/0.25 trail + at-size fees.
- Note: per-bar simultaneous confluence (this search) is far stricter than the
  falsification run's per-day family agreement — hence conf7 n=4 vs 1,317 there.
  Same concepts, different operationalisation, same conclusion.

## Where profit actually is, on current evidence

1. **v5_trail shadow** (engine entries + surviving exit) — the one combination every
   test points at and none has killed. Build next.
2. **Order-book depth** — 6 sessions banked, ~1 week from testable; the only input
   not derived from the OHLCV every dead thesis mined.
3. More OHLCV entry mining: **stop.** Five measurements, one wall.
