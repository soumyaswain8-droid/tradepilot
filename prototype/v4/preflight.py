"""
TradePilot v4 — Late-Start Preflight
=====================================
If the engine boots after 09:30 IST, the morning's intraday signals are stale —
trends already played out, entries near intraday highs/lows are bad value.

This module implements the spec from:
  docs/research/late-start-preflight-spec.md (specced 2026-04-27, coded 2026-05-09)

The preflight runs ONCE on the first scan after a late boot, then disables itself.
Normal scans resume from scan #2 onward. This is a one-shot safety cushion.

Behavior summary:
  - Boot before 09:30 IST: no-op, normal scan
  - Boot 09:30-14:00 IST:  build morning context, apply late-mode filters,
                            reduce Kelly to 50-60%, deploy with caution
  - Boot after 14:00 IST:  skip first deploy entirely, manage existing only
"""

from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Window thresholds (IST)
WARMUP_END = time(9, 30)
LATE_THRESHOLD = time(9, 30)
SKIP_DEPLOY_THRESHOLD = time(14, 0)

# Late-mode filter thresholds
LATE_MODE_LONG_MAX_PCT_FROM_OPEN = 1.5    # don't buy stocks already up >+1.5%
LATE_MODE_SHORT_MIN_PCT_FROM_OPEN = -1.5  # don't short stocks already down >-1.5%
LATE_MODE_EXTENDED_PCT = 2.5              # skip stocks moved >+/-2.5% (overextended)

# Position sizing reduction in late mode (50-60% of normal Kelly)
LATE_MODE_KELLY_FRACTION = 0.55


def is_late_start(now: Optional[datetime] = None) -> bool:
    """Returns True if engine started after 09:30 IST."""
    now = now or datetime.now()
    return now.time() > LATE_THRESHOLD


def should_skip_first_deploy(now: Optional[datetime] = None) -> bool:
    """Returns True if engine started after 14:00 — skip first deploy entirely."""
    now = now or datetime.now()
    return now.time() > SKIP_DEPLOY_THRESHOLD


def build_morning_context(symbols: List[str]) -> Dict[str, Dict]:
    """
    Pull intraday 5-min bars from 09:15 → now for each symbol.
    One Yahoo batch call. Returns per-symbol context for late-mode filtering.

    Returns:
        {
            "RELIANCE": {
                "open": 1429.0,
                "current": 1432.5,
                "pct_from_open": 0.24,
                "high": 1438.0,
                "low": 1425.0,
                "volume": 1234567,
                "trend_30m": "UP" | "FLAT" | "DOWN",
            },
            ...
        }
    """
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        logger.error("yfinance/pandas not available for late-start preflight")
        return {}

    if not symbols:
        return {}

    # yfinance expects ticker symbols joined by space
    yf_symbols = " ".join(f"{s}.NS" for s in symbols)
    try:
        df = yf.download(
            yf_symbols,
            period="1d",
            interval="5m",
            group_by="ticker",
            progress=False,
            timeout=30,
            threads=True,
        )
    except Exception as e:
        logger.warning(f"Late-start preflight intraday fetch failed: {e}")
        return {}

    if df is None or df.empty:
        logger.warning("Late-start preflight: no intraday data returned")
        return {}

    context = {}
    for symbol in symbols:
        yf_sym = f"{symbol}.NS"
        try:
            if isinstance(df.columns, pd.MultiIndex) and yf_sym in df.columns.get_level_values(0):
                bars = df[yf_sym].dropna(how="all")
            else:
                bars = df.dropna(how="all")
            if bars.empty or len(bars) < 2:
                continue

            open_price = float(bars.iloc[0]["Open"])
            current_price = float(bars.iloc[-1]["Close"])
            high = float(bars["High"].max())
            low = float(bars["Low"].min())
            volume = int(bars["Volume"].sum())
            pct_from_open = round((current_price - open_price) / open_price * 100, 2) if open_price else 0.0

            # Trend in last 30 min (last 6 bars of 5-min interval)
            recent = bars.iloc[-6:] if len(bars) >= 6 else bars
            recent_open = float(recent.iloc[0]["Close"])
            recent_close = float(recent.iloc[-1]["Close"])
            recent_pct = (recent_close - recent_open) / recent_open * 100 if recent_open else 0
            if recent_pct > 0.3:
                trend = "UP"
            elif recent_pct < -0.3:
                trend = "DOWN"
            else:
                trend = "FLAT"

            context[symbol] = {
                "open": open_price,
                "current": current_price,
                "pct_from_open": pct_from_open,
                "high": high,
                "low": low,
                "volume": volume,
                "trend_30m": trend,
            }
        except Exception as e:
            logger.debug(f"Late-start context build failed for {symbol}: {e}")
            continue

    logger.info(f"Late-start preflight: built context for {len(context)}/{len(symbols)} symbols")
    return context


def late_entry_allowed(signal: Dict, context: Dict[str, Dict]) -> Tuple[bool, str]:
    """
    Per-signal filter for late-start mode.

    Args:
        signal: dict with at least {"symbol", "direction"} ("BUY"/"SELL")
        context: morning context dict from build_morning_context()

    Returns:
        (allowed: bool, reason: str)
    """
    sym = signal.get("symbol")
    direction = signal.get("direction", "BUY").upper()
    ctx = context.get(sym)
    if not ctx:
        return True, "no late-mode context (allow with caution)"

    pct = ctx.get("pct_from_open", 0.0)
    trend = ctx.get("trend_30m", "FLAT")

    # Skip overextended stocks regardless of direction
    if abs(pct) >= LATE_MODE_EXTENDED_PCT:
        return False, f"overextended ({pct:+.2f}% from open, threshold +/-{LATE_MODE_EXTENDED_PCT}%)"

    if direction == "BUY":
        if pct >= LATE_MODE_LONG_MAX_PCT_FROM_OPEN:
            return False, f"already up {pct:+.2f}% (limit +{LATE_MODE_LONG_MAX_PCT_FROM_OPEN}%)"
        if trend == "DOWN":
            return False, f"30-min trend is DOWN — bad entry for LONG"
    elif direction == "SELL":
        if pct <= LATE_MODE_SHORT_MIN_PCT_FROM_OPEN:
            return False, f"already down {pct:+.2f}% (limit {LATE_MODE_SHORT_MIN_PCT_FROM_OPEN}%)"
        if trend == "UP":
            return False, f"30-min trend is UP — bad entry for SHORT"

    return True, f"OK (pct={pct:+.2f}%, trend={trend})"


def apply_late_start_filter(
    buy_signals: List[Dict],
    symbols: List[str],
    now: Optional[datetime] = None,
) -> Tuple[List[Dict], Dict, str]:
    """
    Top-level entry point. Called from v4-paper-trade.py before the first deploy.

    Args:
        buy_signals: list of BUY signal dicts from composite_scorer
        symbols: list of all universe symbols (for context build)
        now: current time (defaults to datetime.now())

    Returns:
        (filtered_signals: list, context: dict, mode_label: str)

    mode_label:
        "NORMAL"           — boot before 09:30, no filtering applied
        "LATE_ENTRY"       — boot 09:30-14:00, filters + half-Kelly
        "MANAGE_ONLY"      — boot after 14:00, no first deploy
    """
    now = now or datetime.now()

    if not is_late_start(now):
        return buy_signals, {}, "NORMAL"

    if should_skip_first_deploy(now):
        logger.warning(f"Boot time {now.strftime('%H:%M:%S')} > 14:00 — skipping first deploy. Will manage existing positions only.")
        return [], {}, "MANAGE_ONLY"

    logger.info(f"Late-start mode active: boot at {now.strftime('%H:%M:%S')} (after 09:30). Building morning context...")
    context = build_morning_context(symbols)

    if not context:
        logger.warning("Late-start preflight could not build context — falling back to NORMAL mode")
        return buy_signals, {}, "NORMAL"

    filtered = []
    rejected = 0
    rejection_reasons = []
    for sig in buy_signals:
        allowed, reason = late_entry_allowed(sig, context)
        if allowed:
            filtered.append(sig)
        else:
            rejected += 1
            rejection_reasons.append(f"  {sig.get('symbol', '?')}: {reason}")

    logger.info(
        f"Late-start filter: {len(filtered)}/{len(buy_signals)} signals passed, "
        f"{rejected} rejected"
    )
    if rejection_reasons:
        for r in rejection_reasons[:10]:
            logger.info(r)

    return filtered, context, "LATE_ENTRY"


def kelly_scale_for_mode(mode_label: str) -> float:
    """Return Kelly multiplier based on preflight mode."""
    if mode_label == "LATE_ENTRY":
        return LATE_MODE_KELLY_FRACTION  # 0.55 of normal Kelly
    return 1.0


# ---------------------------------------------------------------------------
# Quick test entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Test with a small universe
    test_symbols = ["RELIANCE", "TCS", "INFY"]
    print(f"Boot time: {datetime.now().strftime('%H:%M:%S')}")
    print(f"is_late_start: {is_late_start()}")
    print(f"should_skip_first_deploy: {should_skip_first_deploy()}")
    if is_late_start():
        print("Building morning context...")
        ctx = build_morning_context(test_symbols)
        for sym, c in ctx.items():
            print(f"  {sym}: open={c['open']:.2f} current={c['current']:.2f} pct_from_open={c['pct_from_open']:+.2f}% trend={c['trend_30m']}")
