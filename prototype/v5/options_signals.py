"""
TradePilot v5 -- Options PCR & IV Skew Signal Module
=====================================================
Enhances v4 options OI signal (10% weight in composite scorer) with:
  - Nifty Put-Call Ratio (PCR OI + PCR volume)
  - Max pain strike + distance
  - IV skew (OTM put IV / OTM call IV)
  - Combined contrarian signal (EXTREME_FEAR / EXTREME_GREED)

Data source: nsepython nse_optionchain_scrapper("NIFTY")
Fallback: VIX-based PCR estimation when option chain unavailable.

Usage:
    from prototype.v5.options_signals import get_nifty_pcr, get_options_signal
    pcr_data = get_nifty_pcr()
    signal   = get_options_signal()
CLI:
    python3 -m prototype.v5.options_signals
"""

import logging
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("tradepilot.v5.options_signals")
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"
    ))
    logger.addHandler(_h)
    logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
NIFTY_STRIKE_GAP = 50

# PCR thresholds
PCR_BULLISH = 1.2      # PCR > 1.2 -> oversold -> contrarian BULLISH
PCR_BEARISH = 0.7      # PCR < 0.7 -> overbought -> contrarian BEARISH

# IV skew thresholds
IV_FEAR = 1.1           # OTM put IV / OTM call IV > 1.1 -> fear premium
IV_GREED = 0.9          # skew < 0.9 -> greed / complacency

# Extreme thresholds for combined signal
PCR_EXTREME_FEAR = 1.3
PCR_EXTREME_GREED = 0.5
IV_EXTREME_FEAR = 1.2
IV_EXTREME_GREED = 0.8

# OTM distance for IV skew (number of strikes away from ATM)
OTM_STRIKES = 4         # 4 * 50 = 200 pts OTM


# ---------------------------------------------------------------------------
# Option chain fetch
# ---------------------------------------------------------------------------

def _fetch_nse_option_chain() -> Optional[dict]:
    """Fetch raw Nifty option chain via nsepython. Returns None on failure."""
    try:
        from nsepython import nse_optionchain_scrapper
        raw = nse_optionchain_scrapper("NIFTY")
        if raw and isinstance(raw, dict) and "records" in raw:
            return raw
        logger.warning("nsepython returned empty/invalid data")
        return None
    except ImportError:
        logger.warning("nsepython not installed, using VIX fallback")
        return None
    except Exception as e:
        logger.warning("nsepython failed: %s, using VIX fallback", e)
        return None


def _get_vix() -> float:
    """Get India VIX. Try nsepython, then v4 data, then default."""
    try:
        from nsepython import nse_get_index_quote
        vix_data = nse_get_index_quote("INDIA VIX")
        if isinstance(vix_data, dict):
            return float(vix_data.get("last", 18.0))
        return float(vix_data) if vix_data else 18.0
    except Exception:
        pass
    # Fallback: try v4 data_nse
    try:
        _root = str(Path(__file__).resolve().parent.parent.parent)
        if _root not in sys.path:
            sys.path.insert(0, _root)
        from prototype.v4.data_nse import get_nifty_index_level
        nifty = get_nifty_index_level()
        vix = nifty.get("india_vix", 18.0)
        return vix if vix and not (isinstance(vix, float) and math.isnan(vix)) else 18.0
    except Exception:
        return 18.0


# ---------------------------------------------------------------------------
# PCR from VIX fallback
# ---------------------------------------------------------------------------

def _pcr_from_vix(vix: float) -> dict:
    """Estimate PCR when option chain is unavailable, based on VIX level."""
    if vix > 22:
        pcr = 1.3
    elif vix >= 15:
        pcr = 1.0
    else:
        pcr = 0.7

    if pcr > PCR_BULLISH:
        pcr_signal = "BULLISH"
    elif pcr < PCR_BEARISH:
        pcr_signal = "BEARISH"
    else:
        pcr_signal = "NEUTRAL"

    return {
        "source": "vix_estimate",
        "pcr_oi": pcr,
        "pcr_volume": pcr,
        "pcr_signal": pcr_signal,
        "max_pain": 0,
        "max_pain_distance_pct": 0.0,
        "iv_skew": 1.0,
        "iv_signal": "NEUTRAL",
        "vix_used": vix,
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Core: get_nifty_pcr
# ---------------------------------------------------------------------------

def get_nifty_pcr() -> dict:
    """
    Fetch Nifty Put-Call Ratio from NSE option chain.
    Uses nsepython: nse_optionchain_scrapper("NIFTY")

    Returns:
    {
        "pcr_oi": 1.25,           # Put OI / Call OI
        "pcr_volume": 0.95,       # Put volume / Call volume
        "pcr_signal": "BULLISH",  # PCR > 1.2 = oversold -> BULLISH bounce expected
                                  # PCR < 0.7 = overbought -> BEARISH correction expected
                                  # 0.7-1.2 = NEUTRAL
        "max_pain": 23900,        # Strike with maximum OI pain
        "max_pain_distance_pct": -0.3,  # (Nifty - MaxPain) / MaxPain * 100
        "iv_skew": 1.15,          # OTM Put IV / OTM Call IV (>1 = fear premium)
        "iv_signal": "FEAR",      # FEAR (skew > 1.1), GREED (skew < 0.9), NEUTRAL
    }
    """
    raw = _fetch_nse_option_chain()
    if raw is None:
        vix = _get_vix()
        return _pcr_from_vix(vix)

    records = raw["records"]
    data_rows = records.get("data", [])
    underlying = records.get("underlyingValue", 0)
    expiry_dates = records.get("expiryDates", [])
    nearest_expiry = expiry_dates[0] if expiry_dates else None

    if not data_rows or not underlying:
        return _pcr_from_vix(_get_vix())

    atm_strike = round(underlying / NIFTY_STRIKE_GAP) * NIFTY_STRIKE_GAP

    # Accumulators
    total_ce_oi = 0
    total_pe_oi = 0
    total_ce_vol = 0
    total_pe_vol = 0
    strike_pain = {}    # strike -> total pain for max pain calc

    # IV by strike for skew
    otm_call_ivs = []   # OTM calls: strike > ATM
    otm_put_ivs = []    # OTM puts:  strike < ATM

    for row in data_rows:
        if row.get("expiryDate") != nearest_expiry:
            continue

        strike = row.get("strikePrice", 0)
        if not strike:
            continue

        ce = row.get("CE", {})
        pe = row.get("PE", {})

        ce_oi = ce.get("openInterest", 0) or 0
        pe_oi = pe.get("openInterest", 0) or 0
        ce_vol = ce.get("totalTradedVolume", 0) or 0
        pe_vol = pe.get("totalTradedVolume", 0) or 0
        ce_iv = ce.get("impliedVolatility", 0) or 0
        pe_iv = pe.get("impliedVolatility", 0) or 0

        total_ce_oi += ce_oi
        total_pe_oi += pe_oi
        total_ce_vol += ce_vol
        total_pe_vol += pe_vol

        # Max pain: total loss writers face at this strike
        # For each existing position, compute intrinsic value payout
        strike_pain[strike] = 0
        for r2 in data_rows:
            if r2.get("expiryDate") != nearest_expiry:
                continue
            s2 = r2.get("strikePrice", 0)
            c2_oi = (r2.get("CE", {}).get("openInterest", 0) or 0)
            p2_oi = (r2.get("PE", {}).get("openInterest", 0) or 0)
            # Call writer pain at expiry = max(0, strike_expiry - s2) * c2_oi
            strike_pain[strike] += max(0, strike - s2) * c2_oi
            # Put writer pain at expiry = max(0, s2 - strike_expiry) * p2_oi
            strike_pain[strike] += max(0, s2 - strike) * p2_oi

        # IV skew: collect OTM strikes within OTM_STRIKES range
        otm_distance = abs(strike - atm_strike) / NIFTY_STRIKE_GAP
        if 1 <= otm_distance <= OTM_STRIKES:
            if strike > atm_strike and ce_iv > 0:
                otm_call_ivs.append(ce_iv)
            elif strike < atm_strike and pe_iv > 0:
                otm_put_ivs.append(pe_iv)

    # --- Compute PCR ---
    pcr_oi = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else 1.0
    pcr_volume = round(total_pe_vol / total_ce_vol, 3) if total_ce_vol > 0 else 1.0

    if pcr_oi > PCR_BULLISH:
        pcr_signal = "BULLISH"
    elif pcr_oi < PCR_BEARISH:
        pcr_signal = "BEARISH"
    else:
        pcr_signal = "NEUTRAL"

    # --- Max pain ---
    max_pain = min(strike_pain, key=strike_pain.get) if strike_pain else 0
    if max_pain and underlying:
        max_pain_dist = round((underlying - max_pain) / max_pain * 100, 2)
    else:
        max_pain_dist = 0.0

    # --- IV skew ---
    avg_put_iv = sum(otm_put_ivs) / len(otm_put_ivs) if otm_put_ivs else 0
    avg_call_iv = sum(otm_call_ivs) / len(otm_call_ivs) if otm_call_ivs else 0
    iv_skew = round(avg_put_iv / avg_call_iv, 3) if avg_call_iv > 0 else 1.0

    if iv_skew > IV_FEAR:
        iv_signal = "FEAR"
    elif iv_skew < IV_GREED:
        iv_signal = "GREED"
    else:
        iv_signal = "NEUTRAL"

    return {
        "source": "nsepython",
        "pcr_oi": pcr_oi,
        "pcr_volume": pcr_volume,
        "pcr_signal": pcr_signal,
        "max_pain": max_pain,
        "max_pain_distance_pct": max_pain_dist,
        "iv_skew": iv_skew,
        "iv_signal": iv_signal,
        "underlying": underlying,
        "atm_strike": atm_strike,
        "expiry": nearest_expiry,
        "total_ce_oi": total_ce_oi,
        "total_pe_oi": total_pe_oi,
        "timestamp": datetime.now().isoformat(),
    }


# ---------------------------------------------------------------------------
# Core: get_options_signal (combined contrarian signal)
# ---------------------------------------------------------------------------

def get_options_signal() -> dict:
    """
    Combined options signal for market direction.

    PCR > 1.3 AND IV skew > 1.2 -> EXTREME_FEAR -> contrarian BUY
    PCR < 0.5 AND IV skew < 0.8 -> EXTREME_GREED -> contrarian SELL
    Otherwise blend PCR + IV skew into directional confidence.

    Returns:
        {
            "direction": "BULLISH" | "BEARISH" | "NEUTRAL",
            "confidence": 0.0 - 1.0,
            "pcr": float,
            "iv_skew": float,
            "reason": str,
        }
    """
    pcr_data = get_nifty_pcr()
    pcr = pcr_data["pcr_oi"]
    skew = pcr_data["iv_skew"]

    # --- Extreme zones (contrarian) ---
    if pcr >= PCR_EXTREME_FEAR and skew >= IV_EXTREME_FEAR:
        return {
            "direction": "BULLISH",
            "confidence": min(0.9, 0.5 + (pcr - 1.0) * 0.3 + (skew - 1.0) * 0.2),
            "pcr": pcr,
            "iv_skew": skew,
            "extreme": "EXTREME_FEAR",
            "reason": f"Contrarian BUY: PCR={pcr:.2f} (>1.3) + IV skew={skew:.2f} (>1.2) = panic oversold",
            "pcr_data": pcr_data,
        }

    if pcr <= PCR_EXTREME_GREED and skew <= IV_EXTREME_GREED:
        return {
            "direction": "BEARISH",
            "confidence": min(0.9, 0.5 + (1.0 - pcr) * 0.3 + (1.0 - skew) * 0.2),
            "pcr": pcr,
            "iv_skew": skew,
            "extreme": "EXTREME_GREED",
            "reason": f"Contrarian SELL: PCR={pcr:.2f} (<0.5) + IV skew={skew:.2f} (<0.8) = euphoria overbought",
            "pcr_data": pcr_data,
        }

    # --- Normal zone: blend PCR + IV skew ---
    # PCR score: >1.2 bullish (+1), <0.7 bearish (-1), else linear
    if pcr > PCR_BULLISH:
        pcr_score = min(1.0, (pcr - 1.0) / 0.5)
    elif pcr < PCR_BEARISH:
        pcr_score = max(-1.0, (pcr - 1.0) / 0.5)
    else:
        pcr_score = (pcr - 0.95) / 0.25  # center around 0.95

    # IV skew score: >1.1 fear -> bullish contrarian, <0.9 greed -> bearish
    if skew > IV_FEAR:
        iv_score = min(1.0, (skew - 1.0) / 0.3)
    elif skew < IV_GREED:
        iv_score = max(-1.0, (skew - 1.0) / 0.3)
    else:
        iv_score = 0.0

    # Weighted blend: PCR 60%, IV skew 40%
    combined = pcr_score * 0.6 + iv_score * 0.4

    if combined > 0.2:
        direction = "BULLISH"
    elif combined < -0.2:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"

    confidence = round(min(abs(combined), 1.0), 2)

    pcr_label = pcr_data["pcr_signal"]
    iv_label = pcr_data["iv_signal"]
    reason = f"PCR={pcr:.2f} ({pcr_label}) + IV skew={skew:.2f} ({iv_label}) -> {direction}"

    return {
        "direction": direction,
        "confidence": confidence,
        "pcr": pcr,
        "iv_skew": skew,
        "extreme": None,
        "reason": reason,
        "pcr_data": pcr_data,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli():
    """Pretty-print current PCR + IV skew + combined signal."""
    print(f"\n{'='*64}")
    print(f"  TradePilot v5 -- Options PCR & IV Skew Signal")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*64}")

    pcr_data = get_nifty_pcr()
    signal = get_options_signal()

    # Color codes
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    RESET = "\033[0m"

    src = pcr_data.get("source", "unknown")
    print(f"  Source:     {src}")
    if "underlying" in pcr_data:
        print(f"  Nifty:     {pcr_data['underlying']}")
        print(f"  ATM:       {pcr_data['atm_strike']}")
        print(f"  Expiry:    {pcr_data.get('expiry', 'N/A')}")
    print(f"{'-'*64}")

    # PCR
    pcr = pcr_data["pcr_oi"]
    pcr_color = GREEN if pcr > PCR_BULLISH else RED if pcr < PCR_BEARISH else YELLOW
    print(f"  PCR (OI):      {pcr_color}{pcr:.3f}{RESET}  [{pcr_data['pcr_signal']}]")
    print(f"  PCR (Volume):  {pcr_data['pcr_volume']:.3f}")

    # Max pain
    mp = pcr_data.get("max_pain", 0)
    if mp:
        dist = pcr_data["max_pain_distance_pct"]
        dist_color = GREEN if dist > 0 else RED if dist < 0 else YELLOW
        print(f"  Max Pain:      {mp}  ({dist_color}{dist:+.2f}%{RESET} from spot)")

    # IV skew
    skew = pcr_data["iv_skew"]
    skew_color = RED if skew > IV_FEAR else GREEN if skew < IV_GREED else YELLOW
    print(f"  IV Skew:       {skew_color}{skew:.3f}{RESET}  [{pcr_data['iv_signal']}]")

    print(f"{'-'*64}")

    # Combined signal
    d = signal["direction"]
    conf = signal["confidence"]
    extreme = signal.get("extreme")
    d_color = GREEN if d == "BULLISH" else RED if d == "BEARISH" else YELLOW

    if extreme:
        print(f"  {CYAN}*** {extreme} ***{RESET}")
    print(f"  Direction:     {d_color}{d}{RESET}  (confidence: {conf:.0%})")
    print(f"  Reason:        {signal['reason']}")
    print(f"{'='*64}\n")


if __name__ == "__main__":
    _root = str(Path(__file__).resolve().parent.parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    _cli()
