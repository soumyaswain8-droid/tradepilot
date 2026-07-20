"""TrendScore sensor + mode ladder for v5_chop (spec 2026-07-17).

Pure functions only — no network, no file IO — so tests run without market
data. TrendScore measures trend STRENGTH (direction-neutral); direction is
the signal engine's job. Fail-closed: missing inputs score 0 (=> CHOP).

Calibration (2026-07-20, approved 2-tier design): Gate-1's joint normalization
+ threshold sweep (docs/research/2026-07-17_gate1-trend-sensor-backtest.md,
"Joint sweep (final)" section, 600 combos over td/bm/rd/chop_th/trend_th)
found NO combo clearing the 70/70 profit-capture/loss-capture gate — the
sensor cannot isolate TREND days from the June-July data. The best
CHOP-separating combo alone (td=1.0, bm=1.0, rd=6, chop_th=45, trend_th=55)
reached profit-capture 17% / loss-capture 85%: it reliably flags bleed days
as CHOP even though it can't cleanly flag green days as TREND. Given that,
the design was cut to 2 tiers: CHOP throttles entries, everything else
(NEUTRAL and TREND alike) trades vanilla v5 — see LADDER below.
"""

CHOP_TH = 45.0
TREND_TH = 55.0


def tape_efficiency(closes) -> float:
    """|net move| / sum(|bar moves|) * 100 over 5-min closes since open."""
    if closes is None or len(closes) < 2:
        return 0.0
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
    if path == 0:
        return 0.0
    return abs(closes[-1] - closes[0]) / path * 100.0


def breadth_strength(pct_20_today, pct_20_prev) -> float:
    """Directional breadth strength from %-above-20SMA level + day delta."""
    if pct_20_today is None or pct_20_prev is None:
        return 0.0
    return min(100.0, abs(pct_20_today - 50.0) * 2 + abs(pct_20_today - pct_20_prev) * 5)


def trend_score(tape: float, breadth: float, regime_score: int) -> float:
    # td=1.0, bm=1.0, rd=6 — the Gate-1 joint sweep's best CHOP-separating
    # combo (docs/research/2026-07-17_gate1-trend-sensor-backtest.md, "Joint
    # sweep (final)": profit-capture 17%, loss-capture 85%). No combo in the
    # 600-combo grid cleared the 70/70 gate outright, so this is *not* a
    # promoted TREND detector — it is kept only for its CHOP-flagging power,
    # which is all the 2-tier ladder (CHOP-only throttle) needs.
    s = (0.4 * min(100.0, (tape or 0) / 1.0)
         + 0.4 * min(100.0, (breadth or 0) * 1.0)
         + 0.2 * min(100.0, abs(regime_score or 0) / 6.0 * 100.0))
    return max(0.0, min(100.0, s))


def _raw_mode(score: float, chop_th: float, trend_th: float) -> str:
    if score < chop_th:
        return "CHOP"
    if score >= trend_th:
        return "TREND"
    return "NEUTRAL"


def mode_for(score: float, prev_pending, cur_mode: str,
             chop_th: float = CHOP_TH, trend_th: float = TREND_TH):
    """2-consecutive-scan hysteresis. Returns (mode, pending)."""
    raw = _raw_mode(score, chop_th, trend_th)
    if raw == cur_mode:
        return cur_mode, None
    if raw == prev_pending:
        return raw, None
    return cur_mode, raw


# mode -> (max_new_entries, size_mult, alloc_mult, floor_percentile)
# 2-tier design (approved 2026-07-20): Gate-1 could not clear the 70/70 gate
# for a TREND leg (see trend_score docstring above), so only CHOP throttles
# entries. NEUTRAL is treated identically to TREND — vanilla v5, unfiltered.
LADDER = {
    "CHOP":    (3,    0.40, 0.5, 75),
    "NEUTRAL": (None, 1.00, 1.0, 0),
    "TREND":   (None, 1.00, 1.0, 0),
}


def _percentile(sorted_vals, pct):
    """Linear-interpolation percentile (matches numpy default)."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def apply_ladder(signals, mode):
    """Filter+cap signals per mode. Returns (allowed, size_mult, alloc_mult)."""
    max_new, size_mult, alloc_mult, floor_pct = LADDER.get(mode, LADDER["CHOP"])
    ranked = sorted(signals, key=lambda s: -float(s.get("score", 0)))
    if floor_pct:
        scores = sorted(float(s.get("score", 0)) for s in signals)
        floor_val = _percentile(scores, floor_pct)
        ranked = [s for s in ranked if float(s.get("score", 0)) >= floor_val]
    if max_new is not None:
        ranked = ranked[:max_new]
    return ranked, size_mult, alloc_mult
