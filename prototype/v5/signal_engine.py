"""
TradePilot v5 -- Signal Engine (BUY + SELL + HOLD)
====================================================
Extends v4 composite scorer with SHORT signals so the system profits on bear
days. Built after v4 lost Rs 30,816 on 2026-04-09 (long-only in -0.93% market).

Usage:
    from prototype.v5.signal_engine import generate_signals
    signals = generate_signals()
CLI:
    python3 -m prototype.v5.signal_engine
"""
import logging, os, sys, time
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger("tradepilot.v5.signal_engine")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# --- Import v4 scorer + v5 regime detector ---
try:
    from ..v4.composite_scorer import score_all_stocks
    from ..v4.data_nse import get_nifty_index_level
except ImportError:
    _root = str(Path(__file__).resolve().parent.parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from prototype.v4.composite_scorer import score_all_stocks
    from prototype.v4.data_nse import get_nifty_index_level

try:
    from .regime_detector import detect_regime
except ImportError:
    detect_regime = None

# Percentile cuts
_BUY_TOP_PCT = 0.20       # top 20% = BUY
_SELL_BOT_PCT = 0.20      # bottom 20% = SELL
_BEAR_BUY_PCT = 0.10      # BEAR: shrink BUY to top 10%
_SIDEWAYS_SELL_PCT = 0.10  # SIDEWAYS: shrink SELL to bottom 10%

# Fix #1 (2026-04-28): SHORT emission requires actual weakness, not just bottom-rank.
# RCA showed mechanical bottom-percentile flipped good stocks into SHORT in BEAR regime
# (e.g. 04-28: stock score=55 with change_pct=+0.3% became SHORT — guaranteed loss).
# Now bottom-ranked stocks must ALSO satisfy these absolute conditions to be SHORTed.
# Env-tunable (v5_cut tightens these so we don't short names that aren't clearly weak —
# the watchdog's wrong-way-shorts-on-rising-names problem, e.g. Adani complex/BIOCON).
SHORT_REQUIRE_NEGATIVE_CHANGE_PCT = float(os.environ.get("SHORT_REQ_CHG_PCT", "-0.5"))  # must be down ≥ this
SHORT_REQUIRE_MAX_SCORE = float(os.environ.get("SHORT_REQ_MAX_SCORE", "35"))            # composite must be below this

# Variant C AND-gate (2026-07-24 backtest, 1cr-roadmap/research/2026-07-24_short-confirm-backtest.md
# §6, base commit 4f129bd): a SHORT candidate that clears Fix #1 (red + weak-scored) must
# ALSO be below VWAP at entry before it's allowed to fire. VWAP-only backtested net-negative
# (Variant B: -Rs742/12d, blocks more good shorts than bad); the red-day+below-VWAP AND-gate
# backtested net-positive (Variant C: +Rs1,859/10d, catches 46/230 SHORTED_RISER). Fleet-wide
# kill-switch so all variants sharing this module change together and the four-way comparison
# stays internally consistent. SHORT_VWAP_GATE=0 restores exact pre-gate behavior.
SHORT_VWAP_GATE = os.environ.get("SHORT_VWAP_GATE", "1") != "0"


def score_for_short(stock: dict, nifty_change: float) -> dict:
    """Compute weakness score for a SELL (short) candidate."""
    composite = stock.get("score", 50.0)
    change_pct = stock.get("change_pct", 0.0)
    above_vwap = stock.get("above_vwap", True)
    orb_breakout = stock.get("orb_breakout", True)
    breakdown = stock.get("composite_breakdown", {})
    rs_today = stock.get("rs_today", 0.0)

    weakness = round(100.0 - composite, 1)
    rel_weakness = round(change_pct - nifty_change, 2)
    vol_confirm = breakdown.get("vol_score", 0.5) > 0.55 and change_pct < -0.3
    below_vwap = not above_vwap
    orb_breakdown = not orb_breakout
    rs_weak = rs_today < -0.5

    short_score = (weakness * 0.40
                   + min(abs(rel_weakness) * 10, 20)
                   + (15.0 if vol_confirm else 0)
                   + (10.0 if below_vwap else 0)
                   + (10.0 if orb_breakdown else 0)
                   + (5.0 if rs_weak else 0))

    return {
        "short_score": round(min(short_score, 100.0), 1),
        "weakness": weakness,
        "rel_weakness_vs_nifty": rel_weakness,
        "vol_confirm_selling": vol_confirm,
        "below_vwap": below_vwap,
        "orb_breakdown": orb_breakdown,
        "rs_weak": rs_weak,
    }


def _compute_short_levels(stock: dict) -> dict:
    """Short entry/SL/target from ORB logic (inverted)."""
    price = stock.get("price", 0.0)
    high = stock.get("high") or price
    low = stock.get("low") or price
    orb_range = max(high - low, price * 0.01)

    entry = round(low, 2)                        # below ORB low
    sl = round(high * 1.005, 2)                   # ORB high + 0.5%
    target = round(entry - 2.0 * orb_range, 2)   # 2x range below

    if target <= 0 or target >= entry:
        target = round(entry * 0.98, 2)
    risk = max(sl - entry, price * 0.015)
    reward = max(entry - target, price * 0.02)
    return {"entry_price": entry, "sl_price": sl,
            "target_price": target, "riskReward": round(reward / risk, 1) if risk > 0 else 0.0}


def _compute_long_levels(stock: dict) -> dict:
    """Long entry/SL/target from v4 scorer output."""
    price = stock.get("price", 0.0)
    sl_pct = stock.get("stopLoss", 1.5)
    tgt_pct = stock.get("target", 2.0)
    return {"entry_price": round(price, 2),
            "sl_price": round(price * (1 - sl_pct / 100), 2),
            "target_price": round(price * (1 + tgt_pct / 100), 2),
            "riskReward": stock.get("riskReward", 0.0)}


def _assign_pool(direction: str, score: float, regime: str) -> str:
    """Assign recommended trading pool."""
    if direction == "SELL":
        return "INTRADAY"
    if direction == "HOLD":
        return "NONE"
    # BUY
    if regime == "BULL" and score >= 70:
        return "INTRADAY"
    return "SWING" if score >= 60 else "INVESTMENT"


def generate_signals(regime: str = None) -> List[dict]:
    """Generate BUY / SELL / HOLD signals for all Nifty 50 stocks.

    Args:
        regime: Override ("BULL"/"BEAR"/"SIDEWAYS"). Auto-detected if None.
    Returns:
        List of signal dicts sorted by score desc.
    """
    t0 = time.time()

    # #4 FIX: resolve regime FIRST (from v5.regime_detector), then pass it into v4 composite scorer.
    # Previously: v4 computed its own regime internally (from nifty change% only) which could disagree
    # with v5's multi-indicator regime — leading to long-biased scoring in BEAR tapes.
    if regime is None and detect_regime is not None:
        try:
            ri = detect_regime()
            regime = ri.get("regime", "SIDEWAYS")
            logger.info(f"v5 regime: {regime} (score={ri.get('score')}, conf={ri.get('confidence')})")
        except Exception as e:
            logger.warning(f"Regime detection failed: {e}")
            regime = "SIDEWAYS"
    if regime:
        regime = regime.upper().replace("NEUTRAL", "SIDEWAYS")

    logger.info("Running v4 composite scorer...")
    v4_results = score_all_stocks(regime_override=regime)
    if not v4_results:
        logger.error("v4 scorer returned empty results")
        return []

    # Final regime normalization (in case regime was never set)
    if not regime:
        regime = v4_results[0].get("market_regime", "SIDEWAYS")
        regime = regime.upper().replace("NEUTRAL", "SIDEWAYS")

    # Nifty change for short scoring
    nifty_change = 0.0
    try:
        nifty_change = get_nifty_index_level().get("change_pct", 0.0)
    except Exception:
        pass

    # Classify by regime-aware percentile cuts (v4 results sorted score DESC)
    n = len(v4_results)
    if regime == "BEAR":
        buy_count, sell_count = max(1, int(n * _BEAR_BUY_PCT)), max(1, int(n * _SELL_BOT_PCT))
    elif regime == "SIDEWAYS":
        buy_count, sell_count = max(1, int(n * _BUY_TOP_PCT)), max(1, int(n * _SIDEWAYS_SELL_PCT))
    else:  # BULL
        buy_count, sell_count = max(1, int(n * _BUY_TOP_PCT)), 0

    signals = []
    n_short_filtered = 0
    for i, stock in enumerate(v4_results):
        rank = i + 1
        if rank <= buy_count:
            direction, pos = "BUY", "LONG"
            levels, short_data = _compute_long_levels(stock), {}
        elif sell_count > 0 and rank > n - sell_count:
            # Fix #1: bottom-ranked is necessary but not sufficient. Stock must
            # ALSO show actual weakness (real negative change AND low absolute score).
            # Without this gate, a green-tape day causes 20-40 SHORTs to fire on
            # stocks that just happen to be the relatively-lowest-scored — and
            # they all hit STOPLOSS as the tape rises. RCA: 2026-04-28 v5 EOD.
            stock_change = stock.get("change_pct", 0)
            stock_score = stock.get("score", 100)
            actually_weak = (stock_change < SHORT_REQUIRE_NEGATIVE_CHANGE_PCT and
                             stock_score < SHORT_REQUIRE_MAX_SCORE)
            # Variant C AND-gate: red-day (above) AND below-VWAP must BOTH hold. Only
            # evaluated once Fix #1 already passed, so this can only narrow, never widen,
            # the set of shorts that fire. Unknown VWAP state (above_vwap missing/None,
            # i.e. it couldn't be computed at entry) is treated as NOT below-VWAP — the
            # conservative reading of a confirmation gate: an unconfirmed signal shouldn't
            # be allowed to pass a gate whose whole job is to confirm it.
            if SHORT_VWAP_GATE and actually_weak:
                below_vwap_confirmed = stock.get("above_vwap") is False
                if not below_vwap_confirmed:
                    logger.info(f"{stock.get('symbol', '?')} above VWAP — short blocked (SHORT_VWAP_GATE)")
                    actually_weak = False
            if actually_weak:
                direction, pos = "SELL", "SHORT"
                short_data = score_for_short(stock, nifty_change)
                levels = _compute_short_levels(stock)
            else:
                # Bottom-ranked but not actually weak — skip rather than force-SHORT.
                direction, pos = "HOLD", "NONE"
                levels, short_data = _compute_long_levels(stock), {}
                n_short_filtered += 1
        else:
            direction, pos = "HOLD", "NONE"
            levels, short_data = _compute_long_levels(stock), {}

        signal = {
            "symbol": stock["symbol"], "direction": direction,
            "score": stock["score"], "pool": _assign_pool(direction, stock["score"], regime),
            "entry_price": levels["entry_price"], "sl_price": levels["sl_price"],
            "target_price": levels["target_price"], "riskReward": levels["riskReward"],
            "position_type": pos, "regime": regime,
            "reasons": stock.get("reasons", []),
            # composite_breakdown stripped for IP protection (SECURITY-005)
            "price": stock.get("price", 0.0), "change_pct": stock.get("change_pct", 0.0),
            "trend": stock.get("trend", ""), "volatility": stock.get("volatility", ""),
            "engine": "v5", "rank": rank,
        }
        if short_data:
            signal["short_metrics"] = short_data
        signals.append(signal)

    elapsed = time.time() - t0
    counts = {d: sum(1 for s in signals if s["direction"] == d) for d in ("BUY", "SELL", "HOLD")}
    fix_note = f" (Fix#1 filtered {n_short_filtered} bottom-ranked-but-not-weak SHORTs)" if n_short_filtered else ""
    logger.info(f"v5 signals: BUY={counts['BUY']} SELL={counts['SELL']} HOLD={counts['HOLD']} "
                f"| regime={regime} | {elapsed:.1f}s{fix_note}")
    return signals


def get_long_signals(regime: str = None) -> List[dict]:
    """Return only BUY signals."""
    return [s for s in generate_signals(regime) if s["direction"] == "BUY"]


def get_short_signals(regime: str = None) -> List[dict]:
    """Return only SELL (short) signals."""
    return [s for s in generate_signals(regime) if s["direction"] == "SELL"]


# --- CLI ---
_C = {"BUY": "\033[92m", "SELL": "\033[91m", "HOLD": "\033[90m",
      "BULL": "\033[92m", "BEAR": "\033[91m", "SIDEWAYS": "\033[93m"}
_R = "\033[0m"
_HDR = f"  {'Symbol':>12}  {'Score':>6}  {'Price':>10}  {'Chg%':>7}  {'Pool':<10}  {'Entry':>10}  {'SL':>10}  {'Tgt':>10}  {'R:R':>5}"

def _row(s):
    return (f"  {s['symbol']:>12}  {s['score']:6.1f}  {s['price']:10.2f}  "
            f"{s['change_pct']:+6.2f}%  {s['pool']:<10}  {s['entry_price']:10.2f}  "
            f"{s['sl_price']:10.2f}  {s['target_price']:10.2f}  {s['riskReward']:5.1f}")

def _cli():
    signals = generate_signals()
    if not signals:
        print("No signals generated."); return

    regime = signals[0]["regime"]
    by_dir = {d: [s for s in signals if s["direction"] == d] for d in ("BUY", "SELL", "HOLD")}

    print(f"\n{'='*72}")
    print(f"  TradePilot v5 Signal Engine")
    print(f"  Regime: {_C.get(regime,'')}{regime}{_R}  |  "
          f"BUY: {len(by_dir['BUY'])}  SELL: {len(by_dir['SELL'])}  HOLD: {len(by_dir['HOLD'])}")
    print(f"{'='*72}")

    for label in ("BUY", "SELL"):
        if by_dir[label]:
            tag = "LONG" if label == "BUY" else "SHORT"
            print(f"\n  {_C[label]}--- {label} ({tag}) ---{_R}")
            print(_HDR)
            for s in by_dir[label]:
                print(_row(s))

    if by_dir["HOLD"]:
        print(f"\n  {_C['HOLD']}--- HOLD (top 5) ---{_R}")
        for s in by_dir["HOLD"][:5]:
            print(f"  {s['symbol']:>12}  {s['score']:6.1f}  {s['price']:10.2f}  {s['change_pct']:+6.2f}%")

    print(f"\n{'='*72}")
    print(f"  Shorts close by EOD. Longs follow pool rules.")
    print(f"{'='*72}\n")

if __name__ == "__main__":
    _cli()
