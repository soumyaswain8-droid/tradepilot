# v10 — frozen April-2026 engine

**Author:** Soumya Swain <soumya@suryaai.co.in>
**Date:** 2026-07-30
**Status:** Built, not yet run live. Launches with the fleet at 08:50 on the next trading day.
**Supersedes:** v8 (retired 2026-07-30)

---

## 1. Purpose

Reproduce the April 2026 engine exactly, to establish whether April's +1.35%/day at 77%
win rate was real strategy or measurement artifact. This is a **diagnostic experiment**,
not a candidate for promotion.

## 2. Why v8 did not already answer this

v8 called itself "the April-recipe replica" but its last three lines are
`runpy.run_path()` into **today's** 1,421-line `v5-paper-trade.py` with April parameters
set as env vars. It tested today's code wearing April's settings — the ~689 lines added
since April are still in its execution path, and only the env-gated ones are neutralised.

Its parameters were not a faithful April match either: v8 set `RESCORE_INTERVAL_MIN=999`,
`MAX_POSITIONS_TOTAL=5` and long-only, whereas the real April engine ran `SCAN=10,
RESCORE=30`, four pools, and its `signal_engine` emitted SHORT signals.

v8's result — **−2,827 at 28% WR over 17 sessions** against a +1%/day, 65%-WR target —
therefore says nothing about the April engine.

## 3. The frozen/current boundary

The governing principle: **freeze what decides, keep current what fetches or writes.**

### Frozen at April (git `9d7db34`, 2026-04-16)

| Path | Lines | Role |
|---|---:|---|
| `scripts/v10-paper-trade.py` | 732 | orchestrator |
| `prototype/v10/composite_scorer.py` | 580 | stock ranking |
| `prototype/v10/signal_engine.py` | 259 | BUY/SELL/HOLD selection |
| `prototype/v10/risk_manager.py` | 595 | position sizing |
| `prototype/v10/config.py` | 225 | **April COMPOSITE_WEIGHTS** |
| `prototype/v10/ml_engine.py` | 803 | April ML scorer (no retirement check) |
| `prototype/v10/models/lgbm_intraday.txt` | — | April-21 model, 1,726 trees, 22 features |

### Deliberately current

| Module | Why not frozen |
|---|---|
| `prototype/v4/data_nse.py` | **Fleet safety.** Writes `prototype/data/cache/YYYY-MM-DD/`, the shared cache all 9 live engines read. April's version predates the staleness and NaN guards added 2026-05-08 "after cache poisoning incident" — running it could poison the live fleet's prices. Non-negotiable. |
| `prototype/v4/features_intraday.py` | Byte-identical to April (405 lines). No duplication needed. |
| `prototype/v4/features_institutional.py` | Byte-identical to April (191 lines). |
| `prototype/v5/regime_detector.py` | Byte-identical (417). |
| `prototype/v5/premarket_intel.py` | Byte-identical (374). |
| `prototype/v5/pool_manager.py` | Byte-identical (337). |
| `prototype/v5/comparator.py` | Byte-identical (189). |
| `prototype/v5/alpha_hunter.py` | Byte-identical (672). |

Verified by sha1 on 2026-07-29.

## 4. Divergences from git `9d7db34` — exhaustive

`scripts/v10-paper-trade.py` differs from the April original by **exactly 4 lines**
(verified by diff), plus a prepended docstring:

1. `TRADE_DIR` → `docs/paper-trades/v10` (original hardcodes `v5` and would **overwrite
   live v5 state**)
2. `LOG_FILE` → `logs/v10-paper-trade.log` (same reason)
3. `_mod_imports["signals"]` → `prototype.v10.signal_engine`
4. `_mod_imports["risk"]` → `prototype.v10.risk_manager`

Import repoints inside the vendored modules (mechanical, no behaviour change):
`composite_scorer` → `prototype.v10.config`, `prototype.v10.ml_engine`, and
`prototype.v4.{data_nse, features_intraday, features_institutional}`;
`signal_engine` → `prototype.v10.composite_scorer`.

**No strategy logic was edited.**

## 5. The ML finding — the likely explanation for April

April's `COMPOSITE_WEIGHTS` gave **25% of the ranking to the ML model**:

| Weight | April | Today |
|---|---:|---:|
| `ml_score` | **0.25** | **0.00** |
| `rs_score` | 0.20 | 0.2667 |
| `orb_score` | 0.15 | 0.20 |
| `vwap` / `fii` / `oi` / `vol` | 0.10 each | ~0.1333 each |

That model was later measured at **IC 0.006** — no out-of-sample signal — zeroed
fleet-wide, and retired 2026-07-23.

Two details from `archive/2026-04-21/trained_at.txt` sharpen this:

- **`hit_rate: 0.5223`** — the model's own validation hit rate was 52%, while the engine
  it fed posted 77%.
- **`fixes: random_val_split`** — a *random* validation split on time-series data leaks
  future bars into validation. Textbook lookahead.

**Working hypothesis:** April's 77% was substantially the ML model scoring its own
training window — in-sample memorisation that collapsed the moment it went out-of-sample.
The April → May → June → July curve (77 → 53 → 48 → 47) fits.

v10 tests this directly. It runs the April-21 model at April's 0.25 weight.

**If v10 reproduces ~77%, April was memorisation and the question is closed.** A model
with IC 0.006 cannot produce 77% on genuinely unseen data; reproducing it on *today's*
data would instead indicate the leak is still live and reachable, which is itself a
finding worth having.

## 6. Fleet isolation

v10's ML is scoped to itself. Verified:

- live fleet → `prototype/v4/models/lgbm_intraday.txt` (May-9, sha `304ddf1072c7`), with
  the `retired` marker intact, so `predict_ml_score` still returns neutral for v5..v5_gate
- v10 → `prototype/v10/models/lgbm_intraday.txt` (April-21, sha `ad6171bc1925`), in its own
  directory with **no** `verification_report.json`, so no marker to honour
- separate module objects; April's `ml_engine` contains zero occurrences of `retired`

No bypass or override of the live retirement gate was needed or performed. **ML-001
remains in force for every other engine.**

## 7. Measurement

- **Capital:** Rs 10,00,000 — same as the fleet.
- **Costs:** v10 does **not** book costs, matching April. Net P&L is computed post-hoc in
  the analysis layer at v5's measured rate (Rs 14.32/trade, from Rs 42,344 over 2,957
  trades). The engine stays byte-faithful; the comparison stays fair.
- **Success bar:** beat live v5 **net**, on identical sessions. Immune to April's
  cost-accounting gaps and to regime. Needs ~20+ sessions before it means anything.
- **Secondary read:** win rate. If v10 lands near 77%, see §5. If it lands near the
  fleet's 46–48%, April's edge was not in the code.

## 8. Roster change

v8 retired and commented out of both `scripts/launch-market.sh` and
`scripts/crash-watchdog.sh`; v10 added to both. Fleet stays at 9 engines. v8's state files
and script are preserved, unchanged, per the data-safety rule.

Also corrected while in there: `crash-watchdog.sh` said `# Active engines (5)` and alerted
"will monitor 7 engines" while the array held 9. That stale comment misdirected a live
outage diagnosis on 2026-07-28.

## 9. Verification performed

- `v10-paper-trade.py` diff vs `9d7db34` = exactly 4 lines
- all three initially-vendored files sha-identical to April before repointing
- full frozen chain imports cleanly under anaconda python3
- `TRADE_DIR`/`LOG_FILE`/`CARRY_FORWARD`/`ACTIVE_POS` all resolve under `v10/`
- v5's `positions_active.json` md5 unchanged across a full v10 module import
- v10 resolves the frozen 259-line picker, not today's 310-line one
- April model loads: 1,726 trees, 22 features, matches `TRAINING_FEATURES`, predicts
- `bash -n` clean on both modified shell scripts; both rosters list the same 9 engines

## 10. Not yet done

- **No live session.** v10 has never generated a signal against live market data. First
  run is the next trading day at 08:50.
- **Post-hoc cost calculation is not yet implemented** — needs adding to the analysis
  layer before the first comparison is drawn.
- **v10 is absent from `eod-comparison-daily.py`'s engine roster**, which currently reports
  only v5 and v5_classic. That roster needs widening or v10 will not appear in the EOD
  summary.
