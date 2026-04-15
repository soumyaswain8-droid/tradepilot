"""
TradePilot v5.2 — F&O Options Strategy Engine
===============================================
Core engine implementing 4 options strategies keyed to v5 regime detection.

Strategies:
    1. PROTECTIVE_PUT     — BEAR regime insurance (buy ATM/OTM puts)
    2. STRADDLE_SELL      — SIDEWAYS regime premium selling (sell ATM straddle)
    3. DIRECTIONAL_CALL   — high-confidence BULL (buy OTM calls)
    4. DIRECTIONAL_PUT    — high-confidence BEAR (buy OTM puts)
    5. COVERED_CALL       — sell OTM calls on v5 SWING holdings

Usage:
    from prototype.v5_2.options_engine import generate_fo_signals
    signals = generate_fo_signals(regime_result, vix, nifty_price)
"""

import math
import warnings
from datetime import datetime, date, timedelta
from typing import Optional

import numpy as np

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NIFTY_LOT_SIZE = 75
BANKNIFTY_LOT_SIZE = 30
NIFTY_STRIKE_GAP = 50
BANKNIFTY_STRIKE_GAP = 100

# Capital allocation per strategy (% of total F&O capital)
ALLOC_PROTECTIVE_PUT = 0.05    # 5% — small insurance bet
ALLOC_STRADDLE_SELL = 0.10     # 10% — premium selling
ALLOC_DIRECTIONAL = 0.03       # 3% — small leveraged bet
ALLOC_COVERED_CALL = 0.05      # 5% — passive income on holdings

# Risk limits
MAX_LOSS_PER_TRADE_PCT = 0.02  # 2% max loss per trade
STRADDLE_SL_PCT = 0.02         # 2% straddle SL
DIRECTIONAL_SL_PCT = 0.50      # 50% premium SL
DIRECTIONAL_TARGET_PCT = 1.00  # 100% premium target
PROTECTIVE_TARGET_PCT = 0.50   # 50% premium target on puts


# ===================================================================
# Option chain fetching
# ===================================================================

def get_nifty_option_chain() -> dict:
    """Fetch Nifty option chain from nsepython.

    Returns:
        dict with keys: atm_strike, strikes, calls, puts, expiry, raw
        Each call/put entry: {strike, premium, oi, iv, delta_approx}
    """
    try:
        from nsepython import nse_optionchain_scrapper
        raw = nse_optionchain_scrapper("NIFTY")

        if not raw or "records" not in raw:
            return _empty_chain("nsepython returned empty data")

        records = raw["records"]
        expiry_dates = records.get("expiryDates", [])
        data = records.get("data", [])
        underlying = records.get("underlyingValue", 0)

        if not data or not underlying:
            return _empty_chain("No data or underlying value")

        # Use nearest expiry (weekly Tuesday)
        nearest_expiry = expiry_dates[0] if expiry_dates else None

        # ATM strike: nearest to underlying
        atm_strike = round(underlying / NIFTY_STRIKE_GAP) * NIFTY_STRIKE_GAP

        calls = {}
        puts = {}

        for row in data:
            if row.get("expiryDate") != nearest_expiry:
                continue
            strike = row.get("strikePrice", 0)
            if not strike:
                continue

            # CE data
            ce = row.get("CE", {})
            if ce:
                calls[strike] = {
                    "strike": strike,
                    "premium": ce.get("lastPrice", 0),
                    "oi": ce.get("openInterest", 0),
                    "iv": ce.get("impliedVolatility", 0),
                    "change": ce.get("change", 0),
                    "volume": ce.get("totalTradedVolume", 0),
                }

            # PE data
            pe = row.get("PE", {})
            if pe:
                puts[strike] = {
                    "strike": strike,
                    "premium": pe.get("lastPrice", 0),
                    "oi": pe.get("openInterest", 0),
                    "iv": pe.get("impliedVolatility", 0),
                    "change": pe.get("change", 0),
                    "volume": pe.get("totalTradedVolume", 0),
                }

        return {
            "source": "nsepython",
            "underlying": underlying,
            "atm_strike": atm_strike,
            "expiry": nearest_expiry,
            "calls": calls,
            "puts": puts,
            "strike_count": len(calls),
        }

    except Exception as e:
        return _empty_chain(f"nsepython failed: {e}")


def _empty_chain(reason: str) -> dict:
    """Return empty chain with error reason."""
    return {
        "source": "none",
        "error": reason,
        "underlying": 0,
        "atm_strike": 0,
        "expiry": None,
        "calls": {},
        "puts": {},
        "strike_count": 0,
    }


# ===================================================================
# Premium estimation (fallback when live chain unavailable)
# ===================================================================

def estimate_premium(
    nifty_price: float,
    strike: float,
    option_type: str,
    vix: float,
    days_to_expiry: float,
) -> float:
    """Simple Black-Scholes-like premium estimate for simulation.

    Args:
        nifty_price: Current Nifty spot price
        strike: Option strike price
        option_type: "CE" (call) or "PE" (put)
        vix: India VIX (annualized volatility %)
        days_to_expiry: Calendar days to expiry

    Returns:
        Estimated premium per share (Rs)
    """
    if days_to_expiry <= 0:
        # At expiry — intrinsic only
        if option_type == "CE":
            return max(nifty_price - strike, 0)
        else:
            return max(strike - nifty_price, 0)

    moneyness = (nifty_price - strike) / nifty_price

    # Intrinsic value
    if option_type == "CE":
        intrinsic = max(nifty_price - strike, 0)
    else:
        intrinsic = max(strike - nifty_price, 0)

    # Time value approximation (simplified BS)
    sigma = vix / 100
    t = days_to_expiry / 365
    time_value = nifty_price * sigma * math.sqrt(t) * 0.4

    # OTM discount: deeper OTM = less time value
    otm_discount = max(1 - abs(moneyness) * 10, 0.1)

    premium = intrinsic + time_value * otm_discount
    return round(max(premium, 0.5), 2)  # Min Rs 0.50


def estimate_premium_change(
    old_nifty: float,
    new_nifty: float,
    strike: float,
    option_type: str,
    vix: float,
    old_dte: float,
    new_dte: float,
) -> tuple:
    """Estimate new premium after Nifty price change + time decay.

    Returns:
        (new_premium, pct_change)
    """
    old_p = estimate_premium(old_nifty, strike, option_type, vix, old_dte)
    new_p = estimate_premium(new_nifty, strike, option_type, vix, new_dte)
    if old_p > 0:
        pct = (new_p - old_p) / old_p * 100
    else:
        pct = 0.0
    return (new_p, round(pct, 2))


# ===================================================================
# Strike selection
# ===================================================================

def select_strike(
    chain: dict,
    strategy: str,
    nifty_price: float,
    vix: float = 18.0,
    days_to_expiry: float = 5.0,
) -> dict:
    """Pick optimal strike for a strategy.

    Args:
        chain: Option chain dict from get_nifty_option_chain()
        strategy: PROTECTIVE_PUT, STRADDLE_SELL, DIRECTIONAL_CALL, DIRECTIONAL_PUT
        nifty_price: Current Nifty price
        vix: India VIX for fallback premium estimation
        days_to_expiry: Days to expiry for fallback

    Returns:
        dict with: strike, premium, lot_size, option_type, source
    """
    atm = round(nifty_price / NIFTY_STRIKE_GAP) * NIFTY_STRIKE_GAP
    has_chain = chain.get("strike_count", 0) > 0

    if strategy == "PROTECTIVE_PUT":
        # ATM or 1 strike OTM put
        strike = atm - NIFTY_STRIKE_GAP
        if has_chain and strike in chain.get("puts", {}):
            premium = chain["puts"][strike]["premium"]
            source = "live"
        else:
            premium = estimate_premium(nifty_price, strike, "PE", vix, days_to_expiry)
            source = "estimated"
        return {
            "strike": strike, "premium": premium, "lot_size": NIFTY_LOT_SIZE,
            "option_type": "PE", "source": source,
        }

    elif strategy == "STRADDLE_SELL":
        # ATM call + ATM put (return both)
        if has_chain:
            ce_prem = chain.get("calls", {}).get(atm, {}).get("premium", 0)
            pe_prem = chain.get("puts", {}).get(atm, {}).get("premium", 0)
            source = "live" if ce_prem > 0 and pe_prem > 0 else "estimated"
        else:
            source = "estimated"

        if source == "estimated":
            ce_prem = estimate_premium(nifty_price, atm, "CE", vix, days_to_expiry)
            pe_prem = estimate_premium(nifty_price, atm, "PE", vix, days_to_expiry)

        return {
            "strike": atm,
            "ce_premium": ce_prem,
            "pe_premium": pe_prem,
            "total_premium": round(ce_prem + pe_prem, 2),
            "lot_size": NIFTY_LOT_SIZE,
            "option_type": "STRADDLE",
            "source": source,
        }

    elif strategy == "DIRECTIONAL_CALL":
        # 2 strikes OTM call (cheap, leveraged)
        strike = atm + 2 * NIFTY_STRIKE_GAP
        if has_chain and strike in chain.get("calls", {}):
            premium = chain["calls"][strike]["premium"]
            source = "live"
        else:
            premium = estimate_premium(nifty_price, strike, "CE", vix, days_to_expiry)
            source = "estimated"
        return {
            "strike": strike, "premium": premium, "lot_size": NIFTY_LOT_SIZE,
            "option_type": "CE", "source": source,
        }

    elif strategy == "DIRECTIONAL_PUT":
        # 2 strikes OTM put (cheap, leveraged)
        strike = atm - 2 * NIFTY_STRIKE_GAP
        if has_chain and strike in chain.get("puts", {}):
            premium = chain["puts"][strike]["premium"]
            source = "live"
        else:
            premium = estimate_premium(nifty_price, strike, "PE", vix, days_to_expiry)
            source = "estimated"
        return {
            "strike": strike, "premium": premium, "lot_size": NIFTY_LOT_SIZE,
            "option_type": "PE", "source": source,
        }

    else:
        return {"strike": atm, "premium": 0, "lot_size": NIFTY_LOT_SIZE,
                "option_type": "CE", "source": "unknown_strategy"}


# ===================================================================
# P&L calculation
# ===================================================================

def calculate_option_pnl(
    entry_premium: float,
    exit_premium: float,
    qty: int,
    action: str,
) -> float:
    """Calculate P&L for an option trade.

    Args:
        entry_premium: Premium at entry (per share)
        exit_premium: Premium at exit (per share)
        qty: Total quantity (lot_size * lots)
        action: "BUY" or "SELL"

    Returns:
        P&L in Rs (positive = profit)
    """
    if action == "BUY":
        return round((exit_premium - entry_premium) * qty, 2)
    else:  # SELL
        return round((entry_premium - exit_premium) * qty, 2)


# ===================================================================
# Opportunity analysis
# ===================================================================

def analyze_options_opportunity(
    regime: dict,
    vix: float,
    nifty_price: float,
    capital: float = 1_000_000,
    is_expiry_week: bool = False,
) -> dict:
    """Analyze which F&O strategy to deploy based on regime + market conditions.

    Args:
        regime: dict from v5 detect_regime() — must have 'regime', 'score', 'confidence'
        vix: India VIX value
        nifty_price: Current Nifty spot price
        capital: Available F&O capital (Rs)
        is_expiry_week: True if today is in the weekly expiry week (deploy straddle)

    Returns:
        dict with: strategies (list), reason, risk_level, capital_at_risk
    """
    regime_label = regime.get("regime", "SIDEWAYS")
    score = regime.get("score", 0)
    confidence = regime.get("confidence", 0)

    strategies = []
    reasons = []
    total_risk = 0

    # Strategy 1: Protective Puts (BEAR regime)
    if regime_label == "BEAR" or score <= -2:
        alloc = capital * ALLOC_PROTECTIVE_PUT
        strategies.append({
            "strategy": "PROTECTIVE_PUT",
            "allocation": alloc,
            "reason": f"BEAR regime (score={score}), buying put insurance",
            "expected_win_rate": 0.25,
            "expected_payoff": "Lose 0.3-0.5% normal days, gain 5-15% on crash days",
        })
        total_risk += alloc
        reasons.append("BEAR -> protective puts")

    # Strategy 2: Straddle Selling (SIDEWAYS + expiry week)
    if regime_label == "SIDEWAYS" and is_expiry_week:
        alloc = capital * ALLOC_STRADDLE_SELL
        strategies.append({
            "strategy": "STRADDLE_SELL",
            "allocation": alloc,
            "reason": f"SIDEWAYS regime + expiry week, selling time decay",
            "expected_win_rate": 0.75,
            "expected_payoff": "70-80% win rate, avg +0.5-1% per week",
        })
        total_risk += alloc
        reasons.append("SIDEWAYS + expiry week -> straddle sell")

    # Strategy 3: Directional Options (high confidence)
    if abs(score) >= 3 and confidence >= 0.5:
        alloc = capital * ALLOC_DIRECTIONAL
        if regime_label == "BULL" or score >= 3:
            strat_name = "DIRECTIONAL_CALL"
            direction = "BULL"
        else:
            strat_name = "DIRECTIONAL_PUT"
            direction = "BEAR"
        strategies.append({
            "strategy": strat_name,
            "allocation": alloc,
            "reason": f"High confidence {direction} (score={score}, conf={confidence})",
            "expected_win_rate": 0.40,
            "expected_payoff": "Target +100%, SL -50%, small leveraged bet",
        })
        total_risk += alloc
        reasons.append(f"High confidence {direction} -> directional option")

    # VIX-based adjustments
    vix_note = ""
    if vix > 25:
        vix_note = "HIGH VIX (>25): options expensive, reduce size"
    elif vix < 13:
        vix_note = "LOW VIX (<13): options cheap, good for buying"

    # No strategies? Sit out.
    if not strategies:
        reasons.append("No clear edge — sitting out F&O today")

    return {
        "strategies": strategies,
        "regime": regime_label,
        "score": score,
        "confidence": confidence,
        "vix": vix,
        "vix_note": vix_note,
        "nifty_price": nifty_price,
        "capital": capital,
        "total_risk": total_risk,
        "risk_pct": round(total_risk / capital * 100, 2) if capital > 0 else 0,
        "is_expiry_week": is_expiry_week,
        "reasons": reasons,
        "timestamp": datetime.now().isoformat(),
    }


# ===================================================================
# Signal generation
# ===================================================================

def _next_tuesday(from_date: Optional[date] = None) -> date:
    """Get next Tuesday (weekly Nifty expiry)."""
    d = from_date or date.today()
    days_ahead = (1 - d.weekday()) % 7  # Tuesday = 1
    if days_ahead == 0:
        days_ahead = 7
    return d + timedelta(days=days_ahead)


def _is_expiry_week(from_date: Optional[date] = None) -> bool:
    """True if today is Monday or Tuesday of expiry week (deploy straddle on Tuesday AM)."""
    d = from_date or date.today()
    # Tuesday = 1. Monday before expiry or expiry day itself.
    return d.weekday() in (0, 1)  # Monday=0, Tuesday=1


def _days_to_expiry(from_date: Optional[date] = None) -> float:
    """Calendar days until next Tuesday expiry."""
    d = from_date or date.today()
    if d.weekday() == 1:  # Today is Tuesday (expiry day)
        return 0.2  # ~5 hours of trading left
    nxt = _next_tuesday(d)
    return max((nxt - d).days, 0.2)


def generate_fo_signals(
    regime: dict,
    vix: float,
    nifty_price: float,
    capital: float = 1_000_000,
    today: Optional[date] = None,
) -> list:
    """Generate F&O trade signals for today.

    Args:
        regime: dict from v5 detect_regime()
        vix: India VIX
        nifty_price: Current Nifty spot
        capital: Available F&O capital
        today: Override date for backtesting

    Returns:
        List of signal dicts ready for execution
    """
    today = today or date.today()
    expiry_week = _is_expiry_week(today)
    dte = _days_to_expiry(today)
    expiry_date = _next_tuesday(today)

    # Analyze opportunity
    analysis = analyze_options_opportunity(regime, vix, nifty_price, capital, expiry_week)

    if not analysis["strategies"]:
        return []

    # Fetch option chain (try live, fallback to estimation)
    chain = get_nifty_option_chain()

    signals = []

    for strat_info in analysis["strategies"]:
        strat_name = strat_info["strategy"]
        alloc = strat_info["allocation"]

        if strat_name == "STRADDLE_SELL":
            strike_info = select_strike(chain, strat_name, nifty_price, vix, dte)
            total_prem = strike_info["total_premium"]
            lots = max(1, int(alloc / (total_prem * NIFTY_LOT_SIZE * 2)))  # margin ~2x
            lots = min(lots, 3)  # Cap at 3 lots for safety

            # Signal for CE leg
            signals.append(_make_signal(
                strategy="STRADDLE_SELL",
                instrument="NIFTY",
                option_type="CE",
                strike=strike_info["strike"],
                action="SELL",
                lot_size=NIFTY_LOT_SIZE,
                lots=lots,
                premium=strike_info["ce_premium"],
                expiry=expiry_date.isoformat(),
                regime=regime,
                vix=vix,
                reason=strat_info["reason"],
                sl_pct=STRADDLE_SL_PCT,
            ))
            # Signal for PE leg
            signals.append(_make_signal(
                strategy="STRADDLE_SELL",
                instrument="NIFTY",
                option_type="PE",
                strike=strike_info["strike"],
                action="SELL",
                lot_size=NIFTY_LOT_SIZE,
                lots=lots,
                premium=strike_info["pe_premium"],
                expiry=expiry_date.isoformat(),
                regime=regime,
                vix=vix,
                reason=strat_info["reason"],
                sl_pct=STRADDLE_SL_PCT,
            ))

        elif strat_name in ("PROTECTIVE_PUT", "DIRECTIONAL_CALL", "DIRECTIONAL_PUT"):
            strike_info = select_strike(chain, strat_name, nifty_price, vix, dte)
            premium = strike_info["premium"]

            if premium <= 0:
                continue

            lots = max(1, int(alloc / (premium * NIFTY_LOT_SIZE)))
            lots = min(lots, 5)  # Cap for safety

            # SL and target
            if strat_name == "PROTECTIVE_PUT":
                sl_premium = round(premium * (1 - DIRECTIONAL_SL_PCT), 2)
                target_premium = round(premium * (1 + PROTECTIVE_TARGET_PCT), 2)
            else:
                sl_premium = round(premium * (1 - DIRECTIONAL_SL_PCT), 2)
                target_premium = round(premium * (1 + DIRECTIONAL_TARGET_PCT), 2)

            signals.append(_make_signal(
                strategy=strat_name,
                instrument="NIFTY",
                option_type=strike_info["option_type"],
                strike=strike_info["strike"],
                action="BUY",
                lot_size=NIFTY_LOT_SIZE,
                lots=lots,
                premium=premium,
                expiry=expiry_date.isoformat(),
                regime=regime,
                vix=vix,
                reason=strat_info["reason"],
                sl_premium=sl_premium,
                target_premium=target_premium,
            ))

    return signals


def _make_signal(
    strategy: str,
    instrument: str,
    option_type: str,
    strike: float,
    action: str,
    lot_size: int,
    lots: int,
    premium: float,
    expiry: str,
    regime: dict,
    vix: float,
    reason: str,
    sl_pct: float = 0,
    sl_premium: float = 0,
    target_premium: float = 0,
) -> dict:
    """Construct a standardized F&O signal dict."""
    qty = lot_size * lots

    if action == "BUY":
        cost = round(premium * qty, 2)
        credit = 0
    else:
        cost = 0
        credit = round(premium * qty, 2)

    # For SELL signals, SL is premium going UP
    if action == "SELL" and sl_pct > 0:
        sl_premium = round(premium * (1 + sl_pct / premium * 100), 2) if sl_pct else 0

    return {
        "strategy": strategy,
        "instrument": instrument,
        "option_type": option_type,
        "strike": strike,
        "action": action,
        "lot_size": lot_size,
        "lots": lots,
        "qty": qty,
        "premium": premium,
        "cost": cost,
        "credit": credit,
        "sl_premium": sl_premium,
        "target_premium": target_premium,
        "expiry": expiry,
        "regime": regime.get("regime", "UNKNOWN"),
        "regime_score": regime.get("score", 0),
        "vix": vix,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
    }


# ===================================================================
# CLI
# ===================================================================

def _print_signals(signals: list, analysis: dict) -> None:
    """Pretty-print generated signals."""
    regime = analysis.get("regime", "?")
    color = {"BULL": "\033[92m", "BEAR": "\033[91m", "SIDEWAYS": "\033[93m"}
    reset = "\033[0m"
    c = color.get(regime, "")

    print(f"\n{'='*64}")
    print(f"  TradePilot v5.2 — F&O Options Signal Generator")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*64}")
    print(f"  Regime:    {c}{regime}{reset} (score: {analysis.get('score', '?')})")
    print(f"  VIX:       {analysis.get('vix', '?')}")
    print(f"  Nifty:     {analysis.get('nifty_price', '?')}")
    print(f"  Expiry:    {'This week' if analysis.get('is_expiry_week') else 'Next week'}")
    print(f"  Risk:      {analysis.get('risk_pct', 0):.1f}% of capital")
    if analysis.get("vix_note"):
        print(f"  Note:      {analysis['vix_note']}")
    print(f"{'-'*64}")

    if not signals:
        print(f"  No F&O signals today — {', '.join(analysis.get('reasons', ['sitting out']))}")
    else:
        for i, sig in enumerate(signals, 1):
            act = sig["action"]
            act_color = "\033[92m" if act == "BUY" else "\033[91m"
            print(f"  [{i}] {act_color}{act}{reset}  NIFTY {sig['strike']}{sig['option_type']}"
                  f"  x{sig['qty']}  @Rs {sig['premium']:.1f}"
                  f"  [{sig['strategy']}]")
            if sig["cost"] > 0:
                print(f"      Cost: Rs {sig['cost']:,.0f}  |  SL: Rs {sig['sl_premium']:.1f}"
                      f"  |  Target: Rs {sig['target_premium']:.1f}")
            elif sig["credit"] > 0:
                print(f"      Credit: Rs {sig['credit']:,.0f}  |  Expiry: {sig['expiry']}")
            print(f"      Reason: {sig['reason']}")

    print(f"{'='*64}\n")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent))

    # Get regime from v5
    try:
        from prototype.v5.regime_detector import detect_regime
        regime = detect_regime()
    except Exception as e:
        print(f"[WARN] Could not detect regime: {e}")
        regime = {"regime": "SIDEWAYS", "score": 0, "confidence": 0.5}

    # Get VIX
    vix = regime.get("indicators", {}).get("india_vix", {}).get("value", 18.0)
    if vix is None or (isinstance(vix, float) and np.isnan(vix)):
        vix = 18.0

    nifty_price = regime.get("nifty_close", 23500)

    analysis = analyze_options_opportunity(
        regime, vix, nifty_price,
        capital=1_000_000,
        is_expiry_week=_is_expiry_week(),
    )
    signals = generate_fo_signals(regime, vix, nifty_price, capital=1_000_000)
    _print_signals(signals, analysis)
