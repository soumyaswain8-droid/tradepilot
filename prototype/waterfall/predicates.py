#!/usr/bin/env python3
"""
predicates — the falsifiable building blocks of the agentic waterfall.

EVERY FUNCTION HERE OBEYS ONE RULE
    Nothing may read a bar that had not closed at `as_of`.

That rule is enforced by construction: callers slice with `before(df, as_of)` and the
predicate never sees the future. It is written this way because four findings collapsed
the week of 2026-08-03 for exactly this reason — a measurement that used information the
system would not have had at the time. Lookahead does not announce itself; it shows up
as an edge that evaporates live.

WHAT IS AND IS NOT MEASURABLE HERE
Family A (SMC/ICT) and Family B (evidenced baseline) are both implemented, so one
backtest grades them on identical terms. One Family B predicate is NOT here:
order-book imbalance. Depth collection began 2026-08-07, so there is no history to
test it against. Excluding it is honest; faking it with a volume proxy would not be.

Standing of the Family A predicates, recorded BEFORE any result is seen so the test
cannot grade its own homework:
    mtf_alignment      strong   — momentum/trend agreement under another name
    liquidity_sweep    moderate — stop-cascade-then-reversion is documented
    fvg                moderate — a gap by another name; gap-fill has real tendency
    smt_divergence     moderate — lead-lag between correlated instruments
    order_block        WEAK     — subjective, hardest to define without hindsight
    amd_phase          WEAK     — Wyckoff relabelled; thin formal evidence
If the two WEAK ones come out strongest, that is a red flag for hindsight fitting,
not a discovery.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# ─────────────────────────── time safety ───────────────────────────


def before(df: pd.DataFrame, as_of) -> pd.DataFrame:
    """Bars that had CLOSED at as_of. Strict inequality: a bar stamped 09:30 closes at
    09:30, so at as_of=09:30 it is not yet usable by a decision made at 09:30."""
    if df is None or df.empty:
        return df
    # Daily frames are tz-naive; intraday frames are tz-aware IST. Comparing across
    # the two raises a cryptic "Invalid comparison" deep in pandas. Say what is
    # actually wrong, because the caller passed the wrong clock, not bad data.
    idx_aware = getattr(df.index, "tz", None) is not None
    ts_aware = getattr(as_of, "tzinfo", None) is not None
    if idx_aware != ts_aware:
        raise TypeError(
            f"before(): timezone mismatch — index is "
            f"{'tz-aware' if idx_aware else 'tz-naive'} but as_of is "
            f"{'tz-aware' if ts_aware else 'tz-naive'}. Daily frames are naive, "
            f"intraday frames are IST-aware; pass the matching stamp.")
    return df[df.index < as_of]


def atr(df: pd.DataFrame, n: int = 14) -> float:
    """Average true range over the last n closed bars. Returns nan when short."""
    if df is None or len(df) < n + 1:
        return float("nan")
    h, l, c = df["High"], df["Low"], df["Close"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    return float(tr.tail(n).mean())


# ─────────────────────────── market structure ───────────────────────────


def swings(df: pd.DataFrame, k: int = 2):
    """Fractal swing points: a high with k lower highs on each side, and the converse.

    ONE definition of a swing is used by structure, SMT and liquidity alike. When two
    layers disagree about what a swing is, their verdicts cannot be compared, and the
    confluence score silently double-counts or cancels.
    """
    if df is None or len(df) < 2 * k + 1:
        return [], []
    h, l = df["High"].values, df["Low"].values
    hi, lo = [], []
    for i in range(k, len(df) - k):
        w_h, w_l = h[i - k:i + k + 1], l[i - k:i + k + 1]
        if h[i] == w_h.max() and (w_h.argmax() == k):
            hi.append((df.index[i], float(h[i])))
        if l[i] == w_l.min() and (w_l.argmin() == k):
            lo.append((df.index[i], float(l[i])))
    return hi, lo


def protected_levels(df: pd.DataFrame, k: int = 2):
    """The protected high/low: the swing that produced the most recent break of
    structure. Losing it means the structure that justified the trade is gone."""
    hi, lo = swings(df, k)
    if not hi or not lo or df is None or df.empty:
        return {"protected_high": None, "protected_low": None, "last_bos": None}
    close = float(df["Close"].iloc[-1])
    last_hi, last_lo = hi[-1][1], lo[-1][1]
    bos = None
    if close > last_hi:
        bos = "bullish"
    elif close < last_lo:
        bos = "bearish"
    return {"protected_high": last_hi, "protected_low": last_lo, "last_bos": bos}


def daily_bias(daily: pd.DataFrame, as_of) -> dict:
    """L3 — the highest-authority per-symbol veto, and the cheapest.

    long  : structure broke up and we hold above the prior day's high or the mid
    short : the converse
    neutral: inside the prior day's range with no break — permits both
    """
    d = before(daily, as_of)
    if d is None or len(d) < 25:
        return {"bias": "neutral", "basis": ["insufficient_history"]}
    pdh, pdl = float(d["High"].iloc[-1]), float(d["Low"].iloc[-1])
    close = float(d["Close"].iloc[-1])
    st = protected_levels(d.tail(60))
    basis, score = [], 0
    if st["last_bos"] == "bullish":
        score += 1; basis.append("bos_up")
    elif st["last_bos"] == "bearish":
        score -= 1; basis.append("bos_down")
    mid = (pdh + pdl) / 2
    if close > mid:
        score += 1; basis.append("above_pd_mid")
    else:
        score -= 1; basis.append("below_pd_mid")
    ma20 = float(d["Close"].tail(20).mean())
    if close > ma20:
        score += 1; basis.append("above_ma20")
    else:
        score -= 1; basis.append("below_ma20")
    bias = "long" if score >= 2 else "short" if score <= -2 else "neutral"
    return {"bias": bias, "basis": basis, "score": score,
            "pdh": pdh, "pdl": pdl, "protected_low": st["protected_low"],
            "protected_high": st["protected_high"]}


# ─────────────────────────── Family A — SMC / ICT ───────────────────────────


def find_fvg(df: pd.DataFrame, lookback: int = 40):
    """Fair Value Gap: a three-candle imbalance where candle 1 and candle 3 do not
    overlap. NOTE this is price structure, NOT valuation — see the spec's terminology
    section. Returns unmitigated gaps only (price has not traded back through)."""
    out = []
    if df is None or len(df) < 3:
        return out
    w = df.tail(lookback)
    h, l = w["High"].values, w["Low"].values
    for i in range(2, len(w)):
        if l[i] > h[i - 2]:
            out.append({"dir": "bullish", "lo": float(h[i - 2]), "hi": float(l[i]),
                        "at": w.index[i]})
        elif h[i] < l[i - 2]:
            out.append({"dir": "bearish", "lo": float(h[i]), "hi": float(l[i - 2]),
                        "at": w.index[i]})
    last = float(df["Close"].iloc[-1])
    alive = []
    for g in out:
        after = w[w.index > g["at"]]
        if after.empty:
            continue
        # mitigated once price trades back into the gap
        touched = ((after["Low"] <= g["hi"]) & (after["High"] >= g["lo"])).any()
        if not touched:
            g["distance_pct"] = (min(abs(last - g["lo"]), abs(last - g["hi"])) / last) * 100
            alive.append(g)
    return alive


def find_order_blocks(df: pd.DataFrame, lookback: int = 40):
    """Order block: the last opposing candle before a displacement leg that broke
    structure. This is the WEAKEST predicate in the set — 'displacement' and 'last
    opposing candle' are exactly the kind of definitions that absorb hindsight. It is
    pinned to explicit numbers (body > 1.2x ATR) so it can be falsified rather than
    argued about."""
    out = []
    if df is None or len(df) < 12:
        return out
    a = atr(df, 14)
    if not np.isfinite(a) or a <= 0:
        return out
    w = df.tail(lookback)
    o, c = w["Open"].values, w["Close"].values
    h, l = w["High"].values, w["Low"].values
    for i in range(1, len(w)):
        body = abs(c[i] - o[i])
        if body < 1.2 * a:
            continue
        if c[i] > o[i] and c[i - 1] < o[i - 1]:          # bullish displacement
            out.append({"dir": "bullish", "lo": float(min(o[i - 1], c[i - 1])),
                        "hi": float(max(o[i - 1], c[i - 1])), "at": w.index[i - 1]})
        elif c[i] < o[i] and c[i - 1] > o[i - 1]:        # bearish displacement
            out.append({"dir": "bearish", "lo": float(min(o[i - 1], c[i - 1])),
                        "hi": float(max(o[i - 1], c[i - 1])), "at": w.index[i - 1]})
    return out[-5:]


def liquidity_pools(df: pd.DataFrame, tol_pct: float = 0.10, k: int = 2):
    """Equal highs / equal lows — resting stops. Two or more swings within tol_pct."""
    hi, lo = swings(df, k)
    pools = []
    for name, pts in (("equal_highs", hi), ("equal_lows", lo)):
        vals = [p[1] for p in pts][-8:]
        for i in range(len(vals)):
            grp = [v for v in vals if abs(v - vals[i]) / vals[i] * 100 <= tol_pct]
            if len(grp) >= 2:
                pools.append({"kind": name, "level": float(np.mean(grp)), "n": len(grp)})
    # dedupe by level
    seen, out = set(), []
    for p in pools:
        key = (p["kind"], round(p["level"], 2))
        if key not in seen:
            seen.add(key); out.append(p)
    return out


def liquidity_sweep(df: pd.DataFrame, level: float, bars: int = 3) -> dict:
    """Swept then reclaimed: price trades through a level and closes back inside
    within `bars`. This is the stop-run-then-reversion effect, and it is the most
    defensible idea in Family A."""
    if df is None or len(df) < bars + 1 or level is None or not np.isfinite(level):
        return {"swept": False}
    w = df.tail(bars + 1)
    below = (w["Low"] < level).any()
    above = (w["High"] > level).any()
    close = float(w["Close"].iloc[-1])
    if below and close > level:
        return {"swept": True, "dir": "bullish", "level": float(level)}
    if above and close < level:
        return {"swept": True, "dir": "bearish", "level": float(level)}
    return {"swept": False}


def amd_phase(df: pd.DataFrame, pools: list) -> dict:
    """Accumulation / Manipulation / Distribution, pinned to measurable tests.

    Wyckoff relabelled, and the second-weakest predicate here. Definitions are numeric
    so the phase is falsifiable rather than a matter of opinion.
    """
    if df is None or len(df) < 20:
        return {"phase": "unknown"}
    a = atr(df, 14)
    if not np.isfinite(a) or a <= 0:
        return {"phase": "unknown"}
    w = df.tail(20)
    rng = float(w["High"].max() - w["Low"].min())
    body = abs(float(w["Close"].iloc[-1] - w["Open"].iloc[-1]))
    for p in pools:
        s = liquidity_sweep(df, p["level"])
        if s["swept"]:
            return {"phase": "manipulation_complete", "dir": s["dir"],
                    "level": s["level"]}
    if body > 1.5 * a:
        return {"phase": "distribution"}
    if rng < 0.6 * a * 5:
        return {"phase": "accumulation"}
    return {"phase": "unknown"}


def smt_divergence(sym: pd.DataFrame, ref: pd.DataFrame, lookback: int = 20) -> dict:
    """Smart-money-technique divergence: the symbol and a correlated reference
    disagree about a new extreme.

    The only predicate whose information comes from OUTSIDE the symbol's own price
    history, which is why it is worth measuring separately from the rest.
    """
    if sym is None or ref is None or len(sym) < lookback or len(ref) < lookback:
        return {"smt": False}
    s, r = sym.tail(lookback), ref.tail(lookback)
    s_ll = float(s["Low"].iloc[-1]) <= float(s["Low"].min())
    r_ll = float(r["Low"].iloc[-1]) <= float(r["Low"].min())
    s_hh = float(s["High"].iloc[-1]) >= float(s["High"].max())
    r_hh = float(r["High"].iloc[-1]) >= float(r["High"].max())
    if r_ll and not s_ll:
        return {"smt": True, "dir": "bullish"}
    if r_hh and not s_hh:
        return {"smt": True, "dir": "bearish"}
    return {"smt": False}


def mtf_alignment(frames: dict, bias: str) -> dict:
    """How many timeframes agree with the daily bias. D -> 1H -> 15m -> 5m.

    Strongest-evidenced predicate in Family A: this is trend/momentum agreement, which
    has substantial published support under that name.
    """
    if bias not in ("long", "short"):
        return {"aligned": 0, "of": 0}
    agree = 0
    total = 0
    for tf, df in frames.items():
        if df is None or len(df) < 25:
            continue
        total += 1
        ma = float(df["Close"].tail(20).mean())
        up = float(df["Close"].iloc[-1]) > ma
        if (bias == "long" and up) or (bias == "short" and not up):
            agree += 1
    return {"aligned": agree, "of": total}


# ─────────────────────────── Family B — evidenced baseline ───────────────────────────
# Deliberately boring. These exist so the thesis is not staked on one school, and
# because the data already exists so they cost almost nothing to test.


def short_term_reversal(daily: pd.DataFrame, as_of, days: int = 5) -> dict:
    """The 5-day loser bounce. One of the most consistently documented anomalies in
    the equities literature, and a fair benchmark for anything fancier."""
    d = before(daily, as_of)
    if d is None or len(d) < days + 1:
        return {"signal": None}
    r = (float(d["Close"].iloc[-1]) / float(d["Close"].iloc[-1 - days]) - 1) * 100
    return {"signal": "long" if r < -3 else "short" if r > 3 else None, "ret_5d": r}


def overnight_gap(daily: pd.DataFrame, intraday_today: pd.DataFrame, as_of) -> dict:
    """Does an opening gap continue or fade? One of the two OHLCV hypotheses left
    untested from the 2026-08-05 signal-rebuild plan."""
    d = before(daily, as_of)
    if d is None or len(d) < 2 or intraday_today is None or intraday_today.empty:
        return {"gap_pct": None}
    prev_close = float(d["Close"].iloc[-1])
    today_open = float(intraday_today["Open"].iloc[0])
    g = (today_open / prev_close - 1) * 100
    return {"gap_pct": g,
            "signal": "long" if g > 0.5 else "short" if g < -0.5 else None}


def index_lead(index_intra: pd.DataFrame, as_of, bars: int = 3) -> dict:
    """Does the index move before its constituents? The second untested OHLCV
    hypothesis. Uses the index's own recent return as a directional lead."""
    x = before(index_intra, as_of)
    if x is None or len(x) < bars + 1:
        return {"signal": None}
    r = (float(x["Close"].iloc[-1]) / float(x["Close"].iloc[-1 - bars]) - 1) * 100
    return {"signal": "long" if r > 0.15 else "short" if r < -0.15 else None,
            "index_ret": r}


def opening_range(intraday_today: pd.DataFrame, as_of, minutes: int = 30) -> dict:
    """Position relative to the first `minutes` of the session."""
    x = before(intraday_today, as_of)
    if x is None or len(x) < 2:
        return {"signal": None}
    start = x.index[0]
    orb = x[x.index < start + pd.Timedelta(minutes=minutes)]
    if orb.empty:
        return {"signal": None}
    hi, lo = float(orb["High"].max()), float(orb["Low"].min())
    last = float(x["Close"].iloc[-1])
    return {"signal": "long" if last > hi else "short" if last < lo else None,
            "orh": hi, "orl": lo}
