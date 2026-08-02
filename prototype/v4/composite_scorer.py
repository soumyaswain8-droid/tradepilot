"""
TradePilot v4 — Composite Scorer (The Brain)
=============================================
Combines all v4 signals into ranked stock picks for the Nifty 50 universe.

Pipeline:
    1. Batch-fetch market-wide data (Nifty index, FII/DII) — once
    2. Batch-fetch all 50 stock quotes — once
    3. Per-stock: compute sub-scores (ORB, VWAP, RS, vol, OI, FII, ML)
    4. Weighted composite → 0-100 score
    5. Percentile-rank → BUY / HOLD / AVOID classification
    6. Generate human-readable reasons list per stock

Output format is v3-dashboard-compatible (dict per stock).
"""

import logging
import time
from datetime import date
from typing import List, Optional

import numpy as np
import pandas as pd

from .config import (
    COMPOSITE_WEIGHTS,
    CLASSIFICATION_THRESHOLDS,
    NIFTY_50_SYMBOLS,
    ACTIVE_SYMBOLS,
)
from .data_nse import (
    get_fii_dii_daily,
    get_intraday_candles,
    get_all_nifty50_quotes,
    get_nifty_index_level,
    get_options_chain,
)
from .features_intraday import (
    compute_orb,
    compute_vwap_position,
    compute_intraday_momentum,
    compute_relative_strength,
)
from .features_institutional import (
    compute_fii_dii_score,
    compute_oi_buildup,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger("tradepilot.v4.composite_scorer")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _norm_neg1_pos1(val: float) -> float:
    """Map a value in [-1, +1] to [0, 1]."""
    return float(np.clip((val + 1.0) / 2.0, 0.0, 1.0))


def _norm_breakout(direction: int, strength: float) -> float:
    """ORB breakout → 0-1 score. +1 breakout=1.0, -1=0.0, inside=0.5 + strength bonus."""
    if direction == 1:
        return min(1.0, 0.75 + 0.25 * min(strength, 1.0))
    elif direction == -1:
        return max(0.0, 0.25 - 0.25 * min(strength, 1.0))
    else:
        return 0.5


def _norm_volume(volume: int, avg_volume: float) -> float:
    """Volume ratio → 0-1 score. ratio=1.0 → 0.5, ratio=2.0 → 0.75, ratio=3+ → ~1.0."""
    if avg_volume <= 0:
        return 0.5
    ratio = volume / avg_volume
    # Sigmoid-like: tanh maps ratio to 0-1 range centered at ratio=1
    score = float(np.tanh((ratio - 1.0) / 2.0))  # -1..+1 range
    return float(np.clip((score + 1.0) / 2.0, 0.0, 1.0))


def _detect_market_regime(nifty_change_pct: float) -> str:
    """Simple regime detection from Nifty change%."""
    if nifty_change_pct > 0.5:
        return "BULL"
    elif nifty_change_pct < -0.5:
        return "BEAR"
    else:
        return "NEUTRAL"


def _estimate_trend(change_pct: float, above_vwap: bool, orb_dir: int) -> str:
    """Estimate trend label from available signals."""
    bullish_signals = sum([
        change_pct > 0.3,
        above_vwap,
        orb_dir == 1,
    ])
    if bullish_signals >= 2:
        return "Uptrend"
    elif bullish_signals == 0:
        return "Downtrend"
    return "Sideways"


def _estimate_volatility(intraday_range_pct: float) -> str:
    """Estimate volatility from intraday range."""
    if intraday_range_pct > 3.0:
        return "High"
    elif intraday_range_pct > 1.5:
        return "Medium"
    return "Low"


def _estimate_macd(change_pct: float, momentum: float) -> str:
    """Rough MACD proxy from price momentum."""
    if change_pct > 0.2 and momentum > 0:
        return "Bullish"
    elif change_pct < -0.2 and momentum < 0:
        return "Bearish"
    return "Neutral"


def _compute_sl_target(score: float, volatility: str) -> tuple:
    """Compute stop-loss% and target% based on score and volatility."""
    vol_mult = {"Low": 0.8, "Medium": 1.0, "High": 1.3}.get(volatility, 1.0)
    # Higher score = tighter SL, wider target
    if score >= 70:
        sl = 1.0 * vol_mult
        target = 2.5 * vol_mult
    elif score >= 50:
        sl = 1.5 * vol_mult
        target = 2.0 * vol_mult
    else:
        sl = 2.0 * vol_mult
        target = 1.5 * vol_mult
    return round(sl, 1), round(target, 1)


# ---------------------------------------------------------------------------
# Reason generation
# ---------------------------------------------------------------------------

def _build_reasons(
    symbol: str,
    orb: dict,
    vwap: dict,
    rs: dict,
    fii_data: dict,
    oi: dict,
    momentum: dict,
    vol_ratio: float,
    change_pct: float,
) -> list:
    """Generate human-readable reasons list (positive / negative / neutral)."""
    reasons = []

    # ORB
    if orb.get("breakout_direction") == 1:
        reasons.append({
            "text": f"ORB breakout above {orb.get('orb_high', 0):.0f}",
            "type": "positive",
        })
    elif orb.get("breakout_direction") == -1:
        reasons.append({
            "text": f"ORB breakdown below {orb.get('orb_low', 0):.0f}",
            "type": "negative",
        })

    # VWAP
    dev = vwap.get("price_vs_vwap_pct", 0)
    if vwap.get("above_vwap"):
        reasons.append({
            "text": f"Price +{abs(dev):.2f}% above VWAP ({vwap.get('vwap', 0):.0f})",
            "type": "positive",
        })
    elif dev < -0.2:
        reasons.append({
            "text": f"Price {dev:.2f}% below VWAP ({vwap.get('vwap', 0):.0f})",
            "type": "negative",
        })

    # Relative strength
    rs_today = rs.get("rs_today", 0)
    if rs_today > 1.0:
        reasons.append({
            "text": f"Relative strength +{rs_today:.2f}% vs Nifty",
            "type": "positive",
        })
    elif rs_today < -1.0:
        reasons.append({
            "text": f"Relative weakness {rs_today:.2f}% vs Nifty",
            "type": "negative",
        })

    # FII/DII
    fii_net = fii_data.get("fii_net", 0)
    dii_net = fii_data.get("dii_net", 0)
    if fii_net > 0:
        reasons.append({
            "text": f"FII buying (+{fii_net:.0f} Cr)",
            "type": "positive",
        })
    elif fii_net < 0:
        reasons.append({
            "text": f"FII selling ({fii_net:.0f} Cr)",
            "type": "negative",
        })
    if dii_net > 0:
        reasons.append({
            "text": f"DII buying (+{dii_net:.0f} Cr)",
            "type": "positive",
        })

    # OI buildup
    oi_sent = oi.get("oi_sentiment", "neutral")
    if oi_sent == "long_buildup":
        reasons.append({"text": "Long buildup in options", "type": "positive"})
    elif oi_sent == "short_buildup":
        reasons.append({"text": "Short buildup in options", "type": "negative"})
    elif oi_sent == "short_covering":
        reasons.append({"text": "Short covering rally", "type": "positive"})

    # Volume
    if vol_ratio > 1.5:
        reasons.append({
            "text": f"Volume surge ({vol_ratio:.1f}x average)",
            "type": "positive",
        })
    elif vol_ratio < 0.5:
        reasons.append({
            "text": f"Low volume ({vol_ratio:.1f}x average)",
            "type": "negative",
        })

    # Momentum
    mom = momentum.get("price_momentum", 0)
    if mom > 0.05:
        reasons.append({"text": "Positive intraday momentum", "type": "positive"})
    elif mom < -0.05:
        reasons.append({"text": "Negative intraday momentum", "type": "negative"})

    # Price change
    if change_pct > 2.0:
        reasons.append({"text": f"Strong rally +{change_pct:.1f}%", "type": "positive"})
    elif change_pct < -2.0:
        reasons.append({"text": f"Sharp fall {change_pct:.1f}%", "type": "negative"})

    return reasons


# ---------------------------------------------------------------------------
# Per-stock scoring
# ---------------------------------------------------------------------------

def compute_stock_scores(
    symbol: str,
    quote: dict,
    intraday_df: pd.DataFrame,
    nifty_data: dict,
    fii_data: dict,
    all_changes: dict,
    options_data: Optional[dict] = None,
) -> dict:
    """
    Compute all sub-scores for a single stock.

    Args:
        symbol:         NSE symbol (e.g. "RELIANCE")
        quote:          Quote dict from get_all_nifty50_quotes() or get_equity_quote()
        intraday_df:    Intraday OHLCV DataFrame (may be empty)
        nifty_data:     Nifty 50 index dict from get_nifty_index_level()
        fii_data:       FII/DII dict from get_fii_dii_daily()
        all_changes:    Dict of {symbol: change_pct} for all 50 stocks (for RS ranking)
        options_data:   Options chain dict (optional)

    Returns:
        Dict with all sub-scores, composite score, classification, and reasons.
    """
    price = quote.get("last_price", 0.0)
    change_pct = quote.get("change_pct", 0.0)
    prev_close = quote.get("prev_close", 0.0)
    volume = quote.get("volume", 0)
    nifty_change = nifty_data.get("change_pct", 0.0)

    # ---- Sub-score 1: ML score (LightGBM regression) ----
    try:
        from .ml_engine import predict_ml_score, TRAINING_FEATURES
        # Build features dict from available data (all lagged by design)
        ml_features = {
            "stock_change_pct": change_pct,
            "gap_pct": ((price - prev_close) / prev_close * 100) if prev_close else 0.0,
            "return_5d": quote.get("return_5d", 0.0),
            "return_20d": quote.get("return_20d", 0.0),
            "prev_day_range_pct": quote.get("day_range_pct", 0.0),
            "atr_norm": quote.get("atr_norm", 1.5),
            "stock_volume_ratio": quote.get("volume_ratio", 1.0),
            "rsi_14": quote.get("rsi_14", 50.0),
            "macd_hist": quote.get("macd_hist", 0.0),
            "bollinger_pctb": quote.get("bollinger_pctb", 0.5),
            "adx_14": quote.get("adx_14", 25.0),
            "sma20_rel": quote.get("sma20_rel", 0.0),
            "sma50_rel": quote.get("sma50_rel", 0.0),
            "nifty_change_pct": nifty_change,
            "india_vix": nifty_data.get("india_vix", 15.0),
            "rs_vs_nifty_5d": quote.get("rs_vs_nifty_5d", 0.0),
            "rs_vs_nifty_20d": quote.get("rs_vs_nifty_20d", 0.0),
        }
        ml_score = predict_ml_score(symbol, ml_features)
    except Exception as e:
        logger.debug(f"ML score fallback for {symbol}: {e}")
        ml_score = 0.5

    # ---- Sub-score 2: Relative Strength ----
    rs = compute_relative_strength(
        stock_change_pct=change_pct,
        nifty_change_pct=nifty_change,
        stock_5d_return=0.0,   # not available in real-time batch
        nifty_5d_return=0.0,
    )
    # Percentile rank among all 50 stocks
    rs_today = rs["rs_today"]
    if all_changes:
        changes_list = sorted(all_changes.values())
        n = len(changes_list)
        # Count how many stocks have lower RS
        rs_values = {s: (all_changes[s] - nifty_change) for s in all_changes}
        sorted_rs = sorted(rs_values.values())
        rank = np.searchsorted(sorted_rs, rs_today, side="right")
        rs_score = rank / max(len(sorted_rs), 1)
    else:
        rs_score = 0.5

    # ---- Sub-score 3: ORB ----
    orb = compute_orb(intraday_df)
    orb_score = _norm_breakout(orb["breakout_direction"], orb["breakout_strength"])

    # ---- Sub-score 4: VWAP ----
    vwap = compute_vwap_position(intraday_df)
    vwap_score = _norm_neg1_pos1(vwap["vwap_score"])

    # ---- Sub-score 5: FII/DII (market-wide, same for all stocks) ----
    fii_raw = compute_fii_dii_score(fii_data)
    fii_score = _norm_neg1_pos1(fii_raw)

    # ---- Sub-score 6: OI buildup ----
    oi = compute_oi_buildup(options_data, change_pct)
    oi_score = _norm_neg1_pos1(oi["oi_score"])

    # ---- Sub-score 7: Volume confirmation ----
    # Estimate avg volume: use 20-day average if available, else use volume itself
    # For batch mode we don't have historical avg, so use a heuristic:
    # Volume ratio from momentum features if intraday data is available
    momentum = compute_intraday_momentum(intraday_df)
    vol_accel = momentum.get("volume_acceleration", 1.0)
    vol_score = _norm_volume(int(vol_accel * 100), 100)  # normalize acceleration as ratio

    # ---- Composite ----
    breakdown = {
        "ml_score": round(ml_score, 4),
        "rs_score": round(rs_score, 4),
        "orb_score": round(orb_score, 4),
        "vwap_score": round(vwap_score, 4),
        "fii_score": round(fii_score, 4),
        "oi_score": round(oi_score, 4),
        "vol_score": round(vol_score, 4),
    }

    composite = sum(
        COMPOSITE_WEIGHTS[k] * breakdown[k]
        for k in COMPOSITE_WEIGHTS
    )
    # Scale to 0-100
    score_100 = round(composite * 100, 1)

    # ---- Derived fields for v3 compatibility ----
    intraday_range = momentum.get("intraday_range_pct", 0.0)
    trend = _estimate_trend(change_pct, vwap.get("above_vwap", False), orb["breakout_direction"])
    volatility = _estimate_volatility(intraday_range)
    macd_label = _estimate_macd(change_pct, momentum.get("price_momentum", 0))
    sl, target = _compute_sl_target(score_100, volatility)
    rr = round(target / sl, 1) if sl > 0 else 0.0

    # ---- Reasons ----
    reasons = _build_reasons(
        symbol, orb, vwap, rs, fii_data, oi, momentum, vol_accel, change_pct,
    )

    change_abs = round(price - prev_close, 2) if prev_close > 0 else 0.0

    return {
        # v3-compatible core fields
        "symbol": symbol,
        "name": symbol,
        "price": price,
        "change": change_abs,
        "change_pct": change_pct,
        "score": score_100,
        "direction": "",  # filled after ranking
        "rsi": 50.0,      # placeholder — no intraday RSI in v4 yet
        "trend": trend,
        "volatility": volatility,
        "macd": macd_label,
        "stopLoss": sl,
        "target": target,
        "riskReward": rr,
        "reasons": reasons,
        # v4 extras
        "engine": "v4",
        # composite_breakdown stripped for IP protection (SECURITY-005)
        "rs_today": rs_today,
        "orb_breakout": orb["breakout_direction"] == 1,
        "above_vwap": vwap.get("above_vwap", False),
        "market_regime": "",  # filled at ranking stage
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def score_all_stocks(symbols: Optional[List[str]] = None,
                     regime_override: Optional[str] = None) -> List[dict]:
    """
    Score and rank all stocks in the universe.

    Args:
        symbols: Optional list of NSE symbols. Defaults to ACTIVE_SYMBOLS.
        regime_override: #4 FIX — when set (e.g., v5.regime_detector result), use this as
            the market regime instead of recomputing from nifty change%. Unifies the regime
            source so v5 signal engine and v4 composite scorer never disagree.

    Returns:
        List of scored stock dicts, sorted by composite score descending.
        Top 20% marked BUY, next 30% HOLD, bottom 50% AVOID.
    """
    t0 = time.time()

    if symbols is None:
        symbols = list(ACTIVE_SYMBOLS)
    else:
        # Strip .NS suffix if present (app.py passes "RELIANCE.NS" style)
        symbols = [s.replace(".NS", "").replace(".BO", "") for s in symbols]

    logger.info(f"Scoring {len(symbols)} stocks...")

    # ------------------------------------------------------------------
    # Step 1: Fetch market-wide data (once)
    # ------------------------------------------------------------------
    logger.info("Fetching market-wide data (Nifty index, FII/DII)...")
    nifty_data = get_nifty_index_level()
    fii_data = get_fii_dii_daily()
    # #4 FIX: respect caller-supplied regime; fall back to nifty-change detection only if not provided
    if regime_override:
        market_regime = regime_override.upper().replace("SIDEWAYS", "NEUTRAL")
        logger.info(f"Using caller-supplied regime: {regime_override} -> {market_regime}")
    else:
        market_regime = _detect_market_regime(nifty_data.get("change_pct", 0.0))
    logger.info(
        f"Nifty: {nifty_data.get('level', 0):.0f} ({nifty_data.get('change_pct', 0):+.2f}%) "
        f"| Regime: {market_regime} "
        f"| FII: {fii_data.get('fii_net', 0):+.0f}Cr DII: {fii_data.get('dii_net', 0):+.0f}Cr"
    )

    # ------------------------------------------------------------------
    # Step 2: Batch-fetch all stock quotes
    # ------------------------------------------------------------------
    logger.info("Fetching batch quotes for all stocks...")
    all_quotes = get_all_nifty50_quotes()
    logger.info(f"Got quotes for {len(all_quotes)} stocks")

    # Build change% map for RS percentile ranking
    all_changes = {
        sym: all_quotes[sym].get("change_pct", 0.0)
        for sym in all_quotes
    }

    # ------------------------------------------------------------------
    # Step 2b: Batch-prefetch intraday candles  (perf fix 2026-08-02)
    # ------------------------------------------------------------------
    # The Step-3 loop below calls get_intraday_candles() per symbol. That was fine
    # at the original 50-symbol universe but the universe is now 201, and measured
    # cost was 1.82s/symbol => 363s per full scan, which made /api/scores look hung.
    # One batched call covers all 201 in ~9.5s (~38x faster). get_intraday_candles()
    # transparently serves from this cache; if the prefetch fails it returns 0 and
    # every call simply falls back to its own fetch — slower, still correct.
    try:
        from .data_nse import prefetch_intraday_batch
        _n = prefetch_intraday_batch(symbols, interval="15m")
        logger.info(f"Intraday batch prefetch: {_n}/{len(symbols)} symbols cached")
    except Exception as _e:
        logger.warning(f"Intraday batch prefetch unavailable ({_e}) — per-symbol fallback")

    # ------------------------------------------------------------------
    # Step 3: Score each stock
    # ------------------------------------------------------------------
    results = []
    scored = 0
    failed = 0

    for symbol in symbols:
        try:
            quote = all_quotes.get(symbol)
            if not quote or quote.get("last_price", 0) <= 0:
                logger.debug(f"Skipping {symbol}: no valid quote")
                failed += 1
                continue

            # Fetch intraday candles (per-stock, yfinance is fast)
            intraday_df = get_intraday_candles(symbol, interval="15m")

            # Options data (try, but don't block on failure)
            options_data = None
            try:
                options_data = get_options_chain(symbol)
            except Exception:
                pass

            stock_result = compute_stock_scores(
                symbol=symbol,
                quote=quote,
                intraday_df=intraday_df,
                nifty_data=nifty_data,
                fii_data=fii_data,
                all_changes=all_changes,
                options_data=options_data,
            )
            stock_result["market_regime"] = market_regime
            results.append(stock_result)
            scored += 1

        except Exception as e:
            logger.warning(f"Error scoring {symbol}: {e}")
            failed += 1
            continue

    if not results:
        logger.error("No stocks scored successfully. Check data sources.")
        return []

    # ------------------------------------------------------------------
    # Step 4: Rank and classify
    # ------------------------------------------------------------------
    results.sort(key=lambda x: x["score"], reverse=True)
    n = len(results)

    buy_cutoff = int(n * CLASSIFICATION_THRESHOLDS.get("BUY", 0.80))
    hold_cutoff = int(n * CLASSIFICATION_THRESHOLDS.get("HOLD", 0.50))

    # BUY = top 20% (indices 0 to buy_count-1)
    # HOLD = next 30% (indices buy_count to hold_count-1)
    # AVOID = bottom 50%
    buy_count = n - buy_cutoff   # stocks above 80th percentile
    hold_count = n - hold_cutoff  # stocks above 50th percentile

    # 2026-05-08 NaN guard: yfinance returns NaN price during rate-limit / stale-quote
    # periods. NaN propagates into the BUY record and silently fails downstream
    # filters (notably position_sizer.py:77 `price > 0` which evaluates False for
    # NaN). Symptom: 38 of 40 BUYs vanish from sizer with no log line.
    # Root cause documented in memory project_tradepilot_v4_sizer_bug.md
    # (was incorrectly marked FIXED 2026-05-06 — wrapper was reverted).
    # Fix: any stock with non-positive or NaN price is downgraded to HOLD before
    # ranking is finalized. The downstream sizer never sees these rows as BUYs
    # so it cannot deploy them — but the scorer also cannot mistakenly count them.
    nan_dropped = 0
    for i, stock in enumerate(results):
        price = stock.get("price", 0)
        if not isinstance(price, (int, float)) or price != price or price <= 0:
            stock["direction"] = "HOLD"
            stock["_nan_price"] = True  # for diagnostics
            nan_dropped += 1
            continue
        if i < buy_count:
            stock["direction"] = "BUY"
        elif i < hold_count:
            stock["direction"] = "HOLD"
        else:
            stock["direction"] = "AVOID"

    elapsed = time.time() - t0
    buy_n = sum(1 for r in results if r["direction"] == "BUY")
    hold_n = sum(1 for r in results if r["direction"] == "HOLD")
    avoid_n = sum(1 for r in results if r["direction"] == "AVOID")

    logger.info(
        f"Scoring complete: {scored} scored, {failed} failed "
        f"| BUY={buy_n} HOLD={hold_n} AVOID={avoid_n} "
        f"| NaN-priced (downgraded to HOLD): {nan_dropped} "
        f"| {elapsed:.1f}s elapsed"
    )

    return results


# ---------------------------------------------------------------------------
# Quick test entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    results = score_all_stocks()
    print(f"\n{'='*70}")
    print(f"{'Symbol':>12}  {'Score':>6}  {'Dir':<6}  {'Price':>10}  {'Chg%':>7}  Reasons")
    print(f"{'='*70}")
    for r in results[:15]:
        print(
            f"{r['symbol']:>12}  {r['score']:6.1f}  {r['direction']:<6}  "
            f"{r['price']:10.2f}  {r['change_pct']:+6.2f}%  "
            f"{len(r['reasons'])} signals"
        )
    print(f"{'='*70}")
    print(f"Total: {len(results)} stocks | "
          f"BUY: {sum(1 for r in results if r['direction']=='BUY')} | "
          f"HOLD: {sum(1 for r in results if r['direction']=='HOLD')} | "
          f"AVOID: {sum(1 for r in results if r['direction']=='AVOID')}")
