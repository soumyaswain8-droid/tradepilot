"""RRG rotation-count regime sensor (Gate-1 PASSED 2026-07-20, commit d23726e).

Pure functions only — no network, no file IO — mirrors trend_mode.py's
style and fail-closed conventions. This encodes EXACTLY the Gate-1 winning
config from scripts/backtest-rrg-sensor.py (source of truth for the
semantics below — copied verbatim, not re-derived or "improved"):

    form=count, set=extended, N=1, threshold=-0.2143
    -> profit-capture 85%, loss-capture 73% (PASS vs 70/70 gate)

per the data-repair re-run (docs/research/2026-07-20_gate1-rrg-sensor-
backtest.md, "Data-repair re-run" section, commit d23726e).

Sensor: daily close-to-close relative return of each sector index vs
^NSEI, N=1-day lookback. `count` form = frac(defensive rel>0) -
frac(cyclical rel>0), where "rel" is a sector's own N-day return minus
^NSEI's N-day return over the same window, and the fraction is normalized
by the number of *present* members in each set that day (fail-closed, per
spec §4 / backtest _day_signal_inputs): a sector with a missing/insufficient
close is excluded from its set; if either set then has <2 present members,
the day is NO-DATA (signal = None). Day t is CHOP (risk-off/throttle) when
signal >= threshold, else TREND — a single-threshold binary classifier (no
momentum term, hence no NEUTRAL band at this layer — the NEUTRAL band, if
any, comes from mode_for()'s chop_th/trend_th hysteresis in trend_mode.py,
which this sensor's binary 0/100 score also feeds).

NIFTY_HEALTHCARE.NS (defensive) is UNREPAIRABLE per the 2026-07-20 data-
repair pass (12 candidate symbols tried — ^CNXHEALTH, NIFTYHEALTHCARE.NS,
NIFTY-HEALTHCARE.NS, NIFTY_HEALTHCARE.BO, NIFTY100HEALTHCARE.NS,
NIFTYHEALTHCARE25.NS, NIFTY_HEALTH.NS, ^NSEIHEALTHCARE,
NIFTY_HEALTHCARE25.NS, ^NIFTYHEALTHCARE, ^NSEHEALTHCARE, NIFTY_HEALTHCARE —
all returned no data). It stays in the defensive list and is handled by
the same fail-closed present-member exclusion as any other missing sector
— if yfinance coverage for it ever returns, this self-heals with no code
change, per house convention (no substitute index used, per spec
instruction).
"""

BENCHMARK = "^NSEI"
# NIFTY_HEALTHCARE.NS: UNREPAIRABLE (2026-07-20 probe), stays dead in the
# list, fail-closed skip — self-heals if yfinance coverage ever returns.
DEFENSIVE = ["^CNXPHARMA", "^CNXFMCG", "NIFTY_HEALTHCARE.NS"]
CYCLICAL_BASE = ["^NSEBANK", "^CNXAUTO", "^CNXMETAL", "^CNXREALTY"]
# repaired 2026-07-20: NIFTY_PVT_BANK.NS replaces the dead NIFTYPVTBANK.NS.
CYCLICAL_EXT_ADD = ["^CNXPSUBANK", "NIFTY_PVT_BANK.NS", "NIFTY_FIN_SERVICE.NS"]
CYCLICAL_EXTENDED = CYCLICAL_BASE + CYCLICAL_EXT_ADD  # Gate-1 winning set variant ("extended")

ALL_TICKERS = sorted(set([BENCHMARK] + DEFENSIVE + CYCLICAL_EXTENDED))

N = 1  # Gate-1 winning lookback (trading days)
THRESHOLD = -0.2143  # Gate-1 winning count-form threshold (data-repair re-run, PASS pc85/lc73)


def _n_day_return(closes):
    """N=1-day close-to-close return from the two most recent closes in a
    chronologically-ascending list. None if fewer than N+1 closes are
    present (mirrors backtest-rrg-sensor.py's _rel(): both endpoints must
    exist, or the ticker is excluded from its set that day)."""
    if closes is None or len(closes) < N + 1:
        return None
    c1, c0 = closes[-1], closes[-1 - N]
    if c0 is None or c1 is None or c0 == 0:
        return None
    return c1 / c0 - 1


def rotation_signal(closes_by_ticker) -> float | None:
    """Gate-1 count-form signal: frac(defensive rel>0) - frac(cyclical
    rel>0), set=extended, N=1.

    `closes_by_ticker` maps ticker -> list of closes in ascending
    chronological order. This function is pure and trusts its input for
    no-lookahead — the CALLER must ensure only closes strictly before the
    session date being scored are passed in (see
    scripts/v5-paper-trade.py `_update_trend_mode`'s REGIME_SENSOR=rrg
    path, which drops any bar dated today before calling this).

    Fail-closed, verbatim from backtest-rrg-sensor.py's
    _day_signal_inputs(): a ticker with <N+1 closes is excluded from its
    set; if either the defensive or cyclical set then has <2 present
    members, returns None (NO-DATA). Missing/short benchmark data also
    returns None (nothing is computable without it).
    """
    closes_by_ticker = closes_by_ticker or {}
    b = _n_day_return(closes_by_ticker.get(BENCHMARK))
    if b is None:
        return None
    def_rels = []
    for t in DEFENSIVE:
        r = _n_day_return(closes_by_ticker.get(t))
        if r is not None:
            def_rels.append(r - b)
    cyc_rels = []
    for t in CYCLICAL_EXTENDED:
        r = _n_day_return(closes_by_ticker.get(t))
        if r is not None:
            cyc_rels.append(r - b)
    if len(def_rels) < 2 or len(cyc_rels) < 2:
        return None
    pos_def = sum(1 for r in def_rels if r > 0) / len(def_rels)
    pos_cyc = sum(1 for r in cyc_rels if r > 0) / len(cyc_rels)
    return pos_def - pos_cyc


def rrg_score(signal) -> float:
    """Binary daily classifier -> 0-100 score for mode_for() (trend_mode.py).

    CHOP-classified (signal >= THRESHOLD, i.e. defensive leadership
    dominant per the backtest's `cls = "CHOP" if sig >= threshold else
    "TREND"`) -> 0.0; else (TREND) -> 100.0. None (NO-DATA) -> 0.0,
    fail-closed to CHOP per house convention ("missing inputs score 0 =>
    CHOP", same as trend_mode.py).

    Documented mapping into the shared hysteresis: with CHOP_TH=45 /
    TREND_TH=55 in mode_for(), a 0.0 score always resolves raw mode =
    CHOP (0 < 45) and a 100.0 score always resolves raw mode = TREND
    (100 >= 55) — this binary sensor never lands in the NEUTRAL band,
    which is expected: approach (b) has no momentum term to justify one
    (spec §3b).
    """
    if signal is None:
        return 0.0
    return 0.0 if signal >= THRESHOLD else 100.0
