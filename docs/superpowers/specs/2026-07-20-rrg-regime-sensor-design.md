# RRG Sector-Rotation Regime Sensor — Design

> **STATUS: APPROVED 2026-07-20** — user go-ahead to implement, starting with
> approach (b) as the Gate-1 probe per §7. Approaches (a)/(c) proceed only if
> (b)'s Gate-1 result justifies the added calibration surface.
> One no-lookahead constraint made explicit at approval time: the score for
> day t uses daily closes up to t-1 only (premarket tilt), unlike the
> intraday TrendScore backtest which consumed same-day bars.

---

## 1. Problem recap

The v5_chop intraday TrendScore sensor (`prototype/v5/trend_mode.py`: tape
efficiency 40% + market breadth 40% + premarket regime 20%) failed its Gate-1
backtest after three calibration passes — best joint result
`chop_th=45, trend_th=55` (td=0.5, bm=1.0, rd=6) reached **70% profit-capture
but only 54% loss-capture** against the required 70/70 bar (see
`docs/research/2026-07-17_gate1-trend-sensor-backtest.md` and commit
`ba25d80`). The sensor separates green days reasonably well but cannot
reliably flag the bleed days — i.e. it fails on exactly the side that
justifies throttling risk. A 2-tier CHOP-throttle shadow ships on this
sensor anyway (`docs/superpowers/specs/2026-07-17-v5chop-chop-filter-design.md`),
so a credible replacement candidate is worth designing now, independent of
whether/when it displaces the current sensor.

## 2. Prior research found

**Located**: `docs/research/regime-switching-daily/2026-07-13.md` — Topic
#11/30, "Sector rotation as regime signal — Indian sectors." This is a
filled edition (most of the 30-topic series are stubs; 07-13 and 04-30 are
the two completed ones), so it is a real, citable prior finding, not a gap.

Key conclusions from that research, in priority order:

1. **RRG-Sector-Rotation-India** (GitHub, AdroitAnandAI) implements the
   classic Julius de Kempenaer RRG methodology on NSE sector indices vs
   NIFTY — RS-Ratio + RS-Momentum, EMA and z-score (JdK-standard) variants.
   Low-activity repo (16 commits) but `rrg_calculator.py` is modular enough
   to extract the RS-Ratio/RS-Momentum math without its UI or its AngelOne
   data dependency — the research explicitly notes "we can feed it our own
   yfinance sector CSVs."
2. **RegimeFolio** (arxiv 2510.14986) — sectors as *both* allocation target
   and regime indicator via HMM; regime-aware rebalancing reduced
   transition drawdowns vs static allocation. Built for strategic
   (multi-day) allocation, not intraday — retraining cadence unclear.
3. **TSX 60 sector-rotation study** (MDPI JRFM 19(1):70, 2026) — 25y
   out-of-sample: median-performer sector selection beat momentum-chasing;
   ML regime classification hit 72.7% accuracy at **quarterly** rebalance
   cadence. Two transferable warnings: (a) don't just buy the
   most-extended/leading sector, (b) this is a low-frequency signal — daily
   application risks whipsaw the study didn't test for.
4. **"When Alpha Breaks"** (arxiv 2603.13252) — sector-leadership rotation
   is flagged as a cause of cross-sectional ranker failure, i.e. a
   sector-rotation monitor doubles as a scorer-health signal, not just a
   throttle input.
5. The research's own **concrete minimal design** (already sketched,
   07-13): daily JdK RS-Ratio/RS-Momentum over the 13 NSE sectoral indices
   vs NIFTY; regime input = count of defensive sectors (PHARMA, FMCG,
   HEALTHCARE) in the Leading quadrant minus cyclicals (BANK, AUTO, METAL,
   REALTY) in the Leading quadrant. It ties this directly to the 07-09
   breadth-bear miss postmortem (`docs/SESSION_2026-07-12_outage-review-and-
   data-guard.md` §B): index closed +0.34% while the book bled on breadth,
   and a defensive-leadership rotation was visible in sector RS days
   earlier. It also explicitly recommends **tilt input, not trading
   trigger**, consistent with the project's own 06-30 finding that tilting
   beats flipping.

This design adopts the 07-13 sketch as its starting point rather than
inventing a new approach from scratch — it is already grounded in this
project's own postmortem and its own India-specific market read.

## 3. Candidate approaches

### (a) Classic daily RRG — RS-Ratio + RS-Momentum quadrant concentration

Compute JdK RS-Ratio (normalized relative strength of each sector index vs
NIFTY, smoothed) and RS-Momentum (rate of change of RS-Ratio) daily, for the
13 NSE sectoral indices already tracked in `MARKET_INDICES`
(`prototype/stock_universe.py:378-393`). Regime score = defensive count
(PHARMA, FMCG, Healthcare) in Leading quadrant (RS-Ratio>100, RS-Momentum>100)
minus cyclical count (Bank, Auto, Metal, Realty) in Leading quadrant, or
equivalently a continuous dispersion measure across the four RRG quadrants
(Leading/Weakening/Lagging/Improving).

- **Pros**: closest to the actual 07-13 research finding; captures
  *rotation*, which is structurally different information from tape
  efficiency/breadth (both intraday, single-index proxies). Directly
  explains the 07-09 miss the TrendScore sensor couldn't see. Reusable
  extracted math from a real reference implementation (RRG-Sector-Rotation-
  India), not built from a paper's pseudocode.
- **Cons**: needs a defensible smoothing/normalization scheme (JdK RS-Ratio
  is itself a two-stage EMA construction — more moving parts to calibrate
  than TrendScore's linear blend, which is exactly what burned three
  calibration passes on TrendScore). Quadrant-count regime mapping
  (defensive − cyclical) is a coarse discretization of a continuous
  RS-Ratio/RS-Momentum plane and needs its own threshold tuning. Daily-bar
  signal — cannot react intraday, so it complements rather than replaces the
  tape-efficiency term for same-day timing.

### (b) Simpler sector-breadth quadrant count (no RS-Momentum, RS-Ratio only)

Drop RS-Momentum; just rank sector indices' 1-day and 5-day relative
performance vs NIFTY (simple relative strength, no JdK EMA machinery).
Regime score = count of "outperforming" sectors − count of "underperforming"
sectors, or defensive-vs-cyclical relative-return spread directly (e.g.
avg(PHARMA, FMCG, Healthcare 5d return) − avg(Bank, Auto, Metal, Realty 5d
return)).

- **Pros**: far fewer free parameters than full RRG (no EMA windows, no
  RS-Ratio normalization constant) — lower risk of repeating TrendScore's
  three-pass recalibration cycle. Easy to compute from data already fetched
  for `MARKET_INDICES`. Directly interpretable (a spread in %).
- **Cons**: loses the momentum/rotation-*direction* information that is the
  actual point of RRG (a sector can be leading but decelerating, which RRG
  distinguishes and this doesn't). Weaker theoretical grounding — none of
  the cited sources evaluate this reduced form directly, so its Gate-1
  performance is a genuine unknown rather than literature-informed.

### (c) Hybrid: daily RRG regime term + existing intraday tape term

Keep `tape_efficiency()` (intraday, direction-neutral, reacts same-day) as
one input; replace `breadth_strength()` and the premarket `regime_score`
term with a daily RRG-derived defensive/cyclical rotation score (from
approach a or b), carried forward from the prior close since RRG's inputs
are daily bars. Recompute the trend_score blend weights via the same
normalization-then-threshold sweep methodology already built in
`scripts/backtest-trend-sensor.py` (task-3 recalibration pattern).

- **Pros**: doesn't throw away the one piece of TrendScore that measures
  something RRG structurally cannot (same-day price-path efficiency).
  Reuses the existing sweep harness with only the daily component swapped.
  Most consistent with the "tilt input, not trading trigger" caution from
  the 07-13 research — RRG sets the day's stance, tape efficiency still
  modulates within it.
- **Cons**: most complex of the three to implement and calibrate (two
  independent daily/intraday feature families instead of one); if RRG alone
  turns out to Gate-1 PASS on its own, the added tape term is unneeded
  complexity carried over from a sensor that already failed.

## 4. Data requirements

**Tickers** — already defined in `prototype/stock_universe.py:378-393`
(`MARKET_INDICES` dict), no new symbol research needed:

| Sector | Ticker | Class |
|---|---|---|
| NIFTY 50 (benchmark) | `^NSEI` | benchmark |
| NIFTY Bank | `^NSEBANK` | cyclical |
| NIFTY IT | `^CNXIT` | — |
| NIFTY Pharma | `^CNXPHARMA` | defensive |
| NIFTY Auto | `^CNXAUTO` | cyclical |
| NIFTY Metal | `^CNXMETAL` | cyclical |
| NIFTY FMCG | `^CNXFMCG` | defensive |
| NIFTY Energy | `^CNXENERGY` | — |
| NIFTY Realty | `^CNXREALTY` | cyclical |
| NIFTY Infra | `^CNXINFRA` | — |
| NIFTY PSU Bank | `^CNXPSUBANK` | cyclical (bank) |
| NIFTY Fin Service | `NIFTY_FIN_SERVICE.NS` | cyclical |
| NIFTY Pvt Bank | `NIFTYPVTBANK.NS` | cyclical (bank) |
| NIFTY Healthcare | `NIFTY_HEALTHCARE.NS` | defensive |
| NIFTY Consumer | `NIFTY_CONSUMPTION.NS` | defensive-ish |
| NIFTY Media | `^CNXMEDIA` | — |

The 07-13 research's "13 NSE sectoral indices" framing maps onto this
existing dict reasonably well; the defensive set (PHARMA, FMCG, Healthcare)
and cyclical set (Bank, Auto, Metal, Realty ± PSU Bank/Pvt Bank/Fin Service)
it names are all already present. No unverified/invented tickers are needed
— this is a reuse-existing-data design.

**History depth**: JdK RRG conventionally uses a ~52-week RS-Ratio
lookback with a shorter (~10-13 week) RS-Momentum smoothing on top; a
lighter EMA variant (per the reference repo's "faster" mode) can run on
much less. For Gate-1 purposes only the same 21-trading-day window used by
`scripts/backtest-trend-sensor.py` (`START="2026-06-16"`,
`END="2026-07-16"`) is being *scored*, but the RS-Ratio/RS-Momentum
calculation needs data from before that window to warm up — at minimum the
smoothing window's length of prior daily bars (e.g. 60-90 calendar days) is
needed before 2026-06-16 for the reduced/EMA variant; the full JdK-standard
variant would need close to a year.

**Failure modes** (yfinance-specific, informed by this project's own
recent history): `docs/research/2026-07-17_gate1-trend-sensor-backtest.md`
already documented a stale-cache clamp bug in the TrendScore backtest
(`_pct20()` silently reused a bar dated before the actual window). The same
class of bug is a live risk here — sector index tickers (especially the
`.NS`-suffixed ones like `NIFTY_FIN_SERVICE.NS`, `NIFTYPVTBANK.NS`,
`NIFTY_HEALTHCARE.NS`, `NIFTY_CONSUMPTION.NS`) are lower-liquidity/lower-
coverage symbols than large-cap stocks and are more prone to yfinance gaps,
stale closes, or silent zero-fill than `^NSEI`/`^NSEBANK`. Any
implementation must fail closed (missing sector bar ⇒ exclude that sector
from the day's quadrant count, don't zero-fill it into a spurious
defensive/cyclical reading) — same principle `trend_mode.py` already uses
("missing inputs score 0 (=> CHOP)").

## 5. Integration with existing CHOP-throttle machinery

No change to the engine wrapper is implied by any of the three approaches.
The existing design already isolates the sensor behind a pure-function
interface:

- `trend_score(...) -> float` (0-100) is the only thing that needs a
  replacement/parallel implementation — e.g. a new
  `prototype/v5/rrg_regime.py` exposing an equivalent
  `rotation_score(sector_closes_by_ticker, benchmark_closes) -> float`
  (0-100, same fail-closed-to-CHOP convention).
- `mode_for(score, prev_pending, cur_mode, chop_th, trend_th)` — 2-scan
  hysteresis — is sensor-agnostic; it just needs a score. No change.
- `apply_ladder(signals, mode)` — the `LADDER` dict (CHOP 0.5×/NEUTRAL
  0.8×/TREND 1.0× allocation multiplier, per
  `docs/superpowers/specs/2026-07-17-v5chop-chop-filter-design.md` §"mode
  drives... allocation multiplier") — is sensor-agnostic. No change.
- The `CHOP_FILTER=1` env-gate at the `deploy_signals` choke-point (same
  pattern as DATA-GUARD) and the `scripts/v5_chop-paper-trade.py` runpy
  wrapper (`ENGINE_NAME=v5_chop`) also require no change — they call
  whatever produces the mode, not the specific sensor math.

In other words: **swap the score producer, not the consumer.** The
cleanest integration point is a drop-in replacement (or, for approach (c),
a second input alongside) for the `trend_score()` call inside whatever
per-scan loop currently calls it — that call site was not located in this
research pass (grep found no `import trend_mode` usage outside
`tests/test_trend_mode.py` and `scripts/backtest-trend-sensor.py`, i.e. the
CHOP-throttle shadow's live wiring into `deploy_signals` was not directly
verified in this pass and should be confirmed before implementation).
One structural mismatch to design around: RRG regime data is daily
(computed once per session, most naturally pre-market or at prior EOD),
whereas `trend_score()` is currently called per intraday scan with
freshly-fetched 5-min closes. A daily-computed RRG score would be held
constant across the session (recomputed once at the open, or even at prior
EOD) rather than refreshed per scan — this is a feature, not a bug, per the
07-13 research's "tilt input, not trading trigger" framing, but it does mean
`mode_for`'s 2-consecutive-scan hysteresis becomes close to a no-op for a
score that doesn't change intraday (only relevant for hybrid approach (c),
where the tape term still varies per scan).

## 6. Gate-1 test plan

Reuse `scripts/backtest-trend-sensor.py`'s pattern directly:

1. **Same window and truth data**: `_sessions()` already reads
   `docs/paper-trades/v5/2026-0[67]-*.json` for `START="2026-06-16"` /
   `END="2026-07-16"` (with `EXCLUDE={"2026-07-08","2026-07-10"}` for the
   outage days) and extracts `net` P&L and `regime` per day. No change
   needed — this is the ground truth (green day vs bleed day) both sensors
   are being scored against.
2. **New closes-fetch layer**: replace `_fetch_closes()` (5-min intraday
   closes for tape efficiency) and `_pct20()` (breadth) with a sector-index
   daily-closes fetcher pulling the tickers in §4, going back far enough
   pre-window for RS-Ratio/RS-Momentum warm-up. Cache per session exactly
   like the existing `closes_cache` pattern (`series_cache` in
   `evaluate_grid`) to keep the sweep itself pure arithmetic with no
   re-fetch — this was the design that made the existing joint sweep cheap
   to run repeatedly.
3. **Same evaluation function shape**: `evaluate()` / `evaluate_grid()`
   already compute profit-capture (% of gross positive P&L on
   TREND-flagged days) and loss-capture (% of gross losses on all-day-CHOP
   days) generically over `(chop_th, trend_th, day, mode)` tuples — this is
   sensor-agnostic and can be reused unchanged once the new score-per-day
   series exists.
4. **Sweep**: same joint-sweep pattern (`TREND_GRID`, threshold grid over
   `chop_th`/`trend_th`, plus whatever RRG-specific normalization constants
   replace `td`/`bm`/`rd`) to avoid hand-picking thresholds, per the
   existing task-3 methodology.
5. **Same bar: 70/70.** Recommend keeping the 70% profit-capture / 70%
   loss-capture bar rather than relaxing it. TrendScore's own failure was on
   loss-capture (54% vs 70%), and the entire reason to look at RRG is that
   it targets the *risk-off/defensive-rotation* signal the postmortem says
   TrendScore couldn't see (07-09) — i.e. the specific weakness. If RRG
   can't clear 70% loss-capture either, that is real information (sector
   rotation isn't sufficient at the daily granularity available), not a
   reason to lower the bar.
6. New report artifact: `docs/research/2026-07-2x_gate1-rrg-sensor-
   backtest.md`, mirroring the existing report structure (best-combo
   verdict line first, per-threshold table, joint-sweep top-10 table, CHOP
   vs non-CHOP P&L sum table) so the two Gate-1 reports are directly
   comparable side by side.

## 7. Recommendation

Start with **approach (b)** (simple defensive-vs-cyclical relative-return
spread, no JdK EMA machinery) as the fastest, lowest-parameter-count way to
get a real Gate-1 number for "does sector rotation alone clear 70/70,"
before investing in the full RS-Ratio/RS-Momentum EMA construction of
approach (a). Rationale: TrendScore burned three calibration passes tuning
a *linear blend of well-defined inputs* and still only reached 70/54 —
adding RRG's own multi-stage smoothing/normalization on top is a similar or
larger calibration surface, and the 07-13 research's own concrete minimal
design (defensive-count minus cyclical-count) is already close to approach
(b)'s reduced form. If (b) clears or nearly clears 70/70 loss-capture on
its own, that is a strong, cheap signal to invest further in the full JdK
RRG (approach a) or the hybrid (approach c) for production quality. If (b)
fails outright on loss-capture the same way TrendScore did, that argues the
daily granularity itself (not the specific math) is the limiting factor,
which is exactly the risk the TSX 60 study flags ("quarterly, not daily,
rebalance survives costs") — worth knowing before sinking more time into
approach (a)'s extra complexity.

Regardless of which variant is chosen, do **not** treat this as a
same-day replacement for the tape-efficiency term — the 07-13 research and
the TSX study both point at a *tilt*, not an intraday trigger. If it ships
at all, the natural target is the daily/premarket regime component of the
sensor, not a full replacement for the intraday tape signal — i.e. approach
(c)'s framing, even if approach (b) or (a) is what actually gets
calibrated and Gate-1 tested first in isolation.

---

*Author: Soumya Swain <soumya@suryaai.co.in> — draft, 2026-07-20. Sources
for the RRG research are cited in
`docs/research/regime-switching-daily/2026-07-13.md`.*
