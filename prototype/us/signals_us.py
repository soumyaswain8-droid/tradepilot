#!/usr/bin/env python3
"""
signals_us — factor-based signal generation for US equities.

DESIGN, and why it is not another ML scorer
-------------------------------------------
TradePilot's own April-2026 engine posted a 77% win rate that collapsed to 46%. The
v10 investigation traced the likely cause to a LightGBM model carrying 25% of the
composite score, measured at IC 0.006, trained with a *random* validation split on
time-series data. Classic in-sample memorisation.

So this module deliberately uses NAMED, TESTABLE FACTORS with 30+ years of
out-of-sample replication, not an opaque score:
  - momentum   (Jegadeesh-Titman; 12-1 month)
  - trend      (price vs long moving average)
  - low-vol    (realised volatility, inverted)
  - quality-proxy (return consistency — a price-based stand-in until SEC EDGAR
                   fundamentals land; see LIMITATIONS)

THE REGIME RULE — the single most actionable research finding
-------------------------------------------------------------
Momentum is regime-conditional, and the effect has been strengthening:

    period      after a volatility spike     in calm periods
    1994-2024        -0.73%/month               +0.54%/month
    2014-2024        -0.96%/month               +0.65%/month

Momentum also has the worst tail risk of any factor (documented crashes to -88%).
A momentum sleeve that ignores volatility regime has NEGATIVE expectancy after a
vol spike. So momentum weight here is *cut* when realised vol is elevated, rather
than applied blindly. See 1cr-roadmap/us-market/03-anvitra-and-what-actually-works.md

REGULATORY CONSTRAINT — enforced in code, not documentation
-----------------------------------------------------------
RBI bars LRS remittance for forex trading and for margin/margin calls (VERIFIED,
rbi.org.in). The only clearly-safe lane for an Indian resident is LONG-ONLY, CASH,
UNLEVERAGED. This module therefore emits BUY and EXIT only. It has no code path
that can produce a short. See 1cr-roadmap/us-market/04-regulatory-lrs-tax.md

LIMITATIONS (state them, do not hide them)
------------------------------------------
- Quality and value are the best-replicated factors after momentum, and both need
  FUNDAMENTALS. This module currently uses a price-based consistency proxy for
  quality and has NO value factor. SEC EDGAR (free, 10 req/sec, no key) is the
  intended source. Until then, treat this as a momentum/trend/vol engine.
- Universe is a current-membership snapshot => SURVIVORSHIP BIAS in any backtest.
- No transaction costs are modelled here; the engine applies them.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from typing import Optional

logger = logging.getLogger(__name__)

# ── factor weights ──────────────────────────────────────────────────────────
# Deliberately flat-ish and few. Every weight names a factor with published
# out-of-sample evidence. No weight exists that cannot be attributed after a trade.
W_MOMENTUM = 0.40
W_TREND    = 0.25
W_LOWVOL   = 0.20
W_QUALITY  = 0.15

# ── regime thresholds ───────────────────────────────────────────────────────
# Realised 20d annualised volatility above VOL_SPIKE_PCT (percentile of the
# universe's own recent vol) marks the "after a vol spike" state where momentum's
# historical expectancy turns negative.
VOL_LOOKBACK_D      = 20
VOL_SPIKE_PCTL      = 0.80     # top quintile of universe vol = elevated
MOM_CUT_IN_SPIKE    = 0.35     # keep only 35% of momentum weight when vol is elevated

BUY_SCORE_MIN       = 62.0     # score floor to open
EXIT_SCORE_MAX      = 42.0     # score below which an open position is exited


@dataclass
class Signal:
    symbol: str
    action: str            # "BUY" | "HOLD" | "EXIT"
    score: float
    momentum: float
    trend: float
    lowvol: float
    quality: float
    vol_regime: str        # "CALM" | "ELEVATED"
    price: float
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def _pct_rank(values: dict, higher_is_better: bool = True) -> dict:
    """Cross-sectional percentile rank, 0-100. Factor scores are only meaningful
    relative to the universe on the same day, never in absolute terms."""
    clean = {k: v for k, v in values.items() if v is not None and v == v}
    if not clean:
        return {}
    ordered = sorted(clean.items(), key=lambda kv: kv[1], reverse=not higher_is_better)
    n = len(ordered)
    return {k: (i / (n - 1) * 100 if n > 1 else 50.0) for i, (k, _) in enumerate(ordered)}


def compute_factors(history) -> dict:
    """Compute raw per-symbol factors from a wide Close DataFrame (index=date,
    columns=symbols). Returns {symbol: {...}}. Symbols with insufficient history
    are omitted rather than defaulted — a fabricated factor is worse than none."""
    import numpy as np

    out: dict = {}
    if history is None or len(history) < 260:
        logger.warning("insufficient history for factors (need ~260 rows)")
        return out

    rets = history.pct_change()

    for sym in history.columns:
        s = history[sym].dropna()
        if len(s) < 260:
            continue
        try:
            px = float(s.iloc[-1])
            if px <= 0:
                continue
            # momentum: 12-month return skipping the most recent month
            # (the skip is standard — it removes short-term reversal)
            mom = float(s.iloc[-21] / s.iloc[-252] - 1.0)
            # trend: price vs 200d mean
            trend = float(px / s.tail(200).mean() - 1.0)
            # realised vol, annualised
            r = rets[sym].dropna().tail(VOL_LOOKBACK_D)
            vol = float(r.std() * np.sqrt(252)) if len(r) > 5 else None
            # quality proxy: consistency = share of positive months over 12m
            monthly = s.resample("ME").last().pct_change().dropna().tail(12) if hasattr(s.index, "freq") or True else []
            qual = float((monthly > 0).mean()) if len(monthly) >= 6 else None
            out[sym] = {"price": px, "momentum": mom, "trend": trend,
                        "vol": vol, "quality": qual}
        except Exception as e:
            logger.debug(f"factor calc failed for {sym}: {e}")
            continue
    return out


def generate_signals(history, held: Optional[set] = None) -> list:
    """Produce long-only signals for the universe.

    `history`: wide DataFrame of adjusted closes (index=date, columns=symbols)
    `held`   : symbols currently held, so EXIT can be emitted for them

    Returns a list of Signal, sorted best-first. NEVER emits a SHORT.
    """
    import numpy as np

    held = held or set()
    facts = compute_factors(history)
    if not facts:
        return []

    # ── volatility regime, measured on the universe itself ──
    vols = {k: v["vol"] for k, v in facts.items() if v.get("vol") is not None}
    if vols:
        cutoff = float(np.quantile(list(vols.values()), VOL_SPIKE_PCTL))
    else:
        cutoff = None

    r_mom   = _pct_rank({k: v["momentum"] for k, v in facts.items() if v["momentum"] is not None})
    r_trend = _pct_rank({k: v["trend"]    for k, v in facts.items() if v["trend"] is not None})
    r_vol   = _pct_rank({k: v["vol"]      for k, v in facts.items() if v["vol"] is not None},
                        higher_is_better=False)          # LOW vol scores high
    r_qual  = _pct_rank({k: v["quality"]  for k, v in facts.items() if v["quality"] is not None})

    signals = []
    for sym, f in facts.items():
        mom = r_mom.get(sym); tr = r_trend.get(sym)
        lv = r_vol.get(sym);  ql = r_qual.get(sym)
        if mom is None or tr is None:
            continue
        lv = 50.0 if lv is None else lv
        ql = 50.0 if ql is None else ql

        # ── THE REGIME RULE ──
        # In an elevated-vol state momentum's historical expectancy is NEGATIVE
        # (-0.73%/mo 1994-2024, -0.96%/mo 2014-2024). Cut its weight rather than
        # trusting it, and redistribute to trend/low-vol which hold up better.
        elevated = cutoff is not None and f.get("vol") is not None and f["vol"] >= cutoff
        regime = "ELEVATED" if elevated else "CALM"
        w_mom = W_MOMENTUM * (MOM_CUT_IN_SPIKE if elevated else 1.0)
        spare = W_MOMENTUM - w_mom
        w_trend = W_TREND + spare * 0.5
        w_lowvol = W_LOWVOL + spare * 0.5

        score = (mom * w_mom + tr * w_trend + lv * w_lowvol + ql * W_QUALITY)
        score = score / (w_mom + w_trend + w_lowvol + W_QUALITY) if (w_mom + w_trend + w_lowvol + W_QUALITY) else 0.0

        if sym in held:
            action = "EXIT" if score < EXIT_SCORE_MAX else "HOLD"
        else:
            action = "BUY" if score >= BUY_SCORE_MIN else "HOLD"

        bits = [f"mom {mom:.0f}", f"trend {tr:.0f}", f"lowvol {lv:.0f}", f"qual {ql:.0f}"]
        if elevated:
            bits.append(f"VOL-ELEVATED: momentum weight cut to {MOM_CUT_IN_SPIKE:.0%}")

        signals.append(Signal(symbol=sym, action=action, score=round(score, 2),
                              momentum=round(mom, 1), trend=round(tr, 1),
                              lowvol=round(lv, 1), quality=round(ql, 1),
                              vol_regime=regime, price=round(f["price"], 2),
                              reason=" | ".join(bits)))

    signals.sort(key=lambda s: s.score, reverse=True)
    return signals
