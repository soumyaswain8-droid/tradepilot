"""
TradePilot v5 — FII/DII Data Feed
===================================
Fetches REAL daily FII/DII data with fallback chain:
  1. Primary:  nsepython.nse_fiidii()
  2. Fallback: NSE API direct (needs session cookies)
  3. Fallback: Cached data from prototype/data/cache/fii_dii/

Functions:
  get_fii_dii_today()   -> single day dict
  get_fii_dii_history() -> list of daily dicts
  compute_fii_signal()  -> direction + signal strength

CLI: python3 -m prototype.v5.fii_feed
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "cache" / "fii_dii"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ===================================================================
# Cache helpers
# ===================================================================

def _cache_path(date_str: str) -> Path:
    """Cache file path for a given YYYY-MM-DD date."""
    return _CACHE_DIR / f"{date_str}.json"


def _read_cache(date_str: str) -> Optional[dict]:
    p = _cache_path(date_str)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return None
    return None


def _write_cache(date_str: str, data: dict) -> None:
    try:
        _cache_path(date_str).write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning(f"Cache write failed for {date_str}: {e}")


# ===================================================================
# Source 1: nsepython
# ===================================================================

def _fetch_nsepython() -> Optional[dict]:
    """Fetch today's FII/DII via nsepython.nse_fiidii()."""
    try:
        from nsepython import nse_fiidii
        df = nse_fiidii()
        if df is None or df.empty:
            return None

        result = {}
        for _, row in df.iterrows():
            cat = str(row.get("category", "")).strip().upper()
            buy = float(row.get("buyValue", 0))
            sell = float(row.get("sellValue", 0))
            net = float(row.get("netValue", 0))
            date_str = str(row.get("date", ""))

            if "FII" in cat or "FPI" in cat:
                result["fii_buy"] = round(buy, 2)
                result["fii_sell"] = round(sell, 2)
                result["fii_net_crores"] = round(net, 2)
            elif "DII" in cat:
                result["dii_buy"] = round(buy, 2)
                result["dii_sell"] = round(sell, 2)
                result["dii_net_crores"] = round(net, 2)

            if date_str and "date" not in result:
                # Parse DD-Mon-YYYY or DD-Mmm-YYYY to YYYY-MM-DD
                result["date"] = _parse_nse_date(date_str)

        if "fii_net_crores" in result:
            return result
        return None
    except Exception as e:
        logger.debug(f"nsepython failed: {e}")
        return None


def _parse_nse_date(raw: str) -> str:
    """Parse NSE date formats to YYYY-MM-DD."""
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # Fallback: return today
    return datetime.now().strftime("%Y-%m-%d")


# ===================================================================
# Source 2: NSE API direct
# ===================================================================

def _fetch_nse_api() -> Optional[dict]:
    """Fetch FII/DII from NSE API with session cookies."""
    try:
        import requests
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })
        # Hit main page first for cookies
        session.get("https://www.nseindia.com", timeout=10)
        resp = session.get(
            "https://www.nseindia.com/api/fiidiiTradeReact",
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        data = resp.json()
        if not data:
            return None

        result = {"date": datetime.now().strftime("%Y-%m-%d")}
        for entry in data:
            cat = str(entry.get("category", "")).upper()
            buy = float(entry.get("buyValue", 0))
            sell = float(entry.get("sellValue", 0))
            net = float(entry.get("netValue", 0))
            if "FII" in cat or "FPI" in cat:
                result["fii_buy"] = round(buy, 2)
                result["fii_sell"] = round(sell, 2)
                result["fii_net_crores"] = round(net, 2)
            elif "DII" in cat:
                result["dii_buy"] = round(buy, 2)
                result["dii_sell"] = round(sell, 2)
                result["dii_net_crores"] = round(net, 2)
            if "date" in entry:
                result["date"] = _parse_nse_date(str(entry["date"]))

        return result if "fii_net_crores" in result else None
    except Exception as e:
        logger.debug(f"NSE API failed: {e}")
        return None


# ===================================================================
# Public API
# ===================================================================

def get_fii_dii_today() -> dict:
    """Get today's FII/DII data. Tries nsepython -> NSE API -> cache.

    Returns:
        dict with: fii_net_crores, dii_net_crores, fii_buy, fii_sell,
                   dii_buy, dii_sell, date, source
    """
    today = datetime.now().strftime("%Y-%m-%d")

    # Check cache first (avoid repeated API calls)
    cached = _read_cache(today)
    if cached and "fii_net_crores" in cached:
        cached["source"] = "cache"
        return cached

    # Source 1: nsepython
    data = _fetch_nsepython()
    if data:
        data["source"] = "nsepython"
        _write_cache(data.get("date", today), data)
        return data

    # Source 2: NSE API
    data = _fetch_nse_api()
    if data:
        data["source"] = "nse_api"
        _write_cache(data.get("date", today), data)
        return data

    # Source 3: most recent cache
    for days_back in range(1, 5):
        prev = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
        cached = _read_cache(prev)
        if cached and "fii_net_crores" in cached:
            cached["source"] = f"cache ({prev})"
            return cached

    return {
        "fii_net_crores": 0, "dii_net_crores": 0,
        "fii_buy": 0, "fii_sell": 0, "dii_buy": 0, "dii_sell": 0,
        "date": today, "source": "unavailable",
    }


def get_fii_dii_history(days: int = 10) -> list[dict]:
    """Get FII/DII data for the last N calendar days from cache.

    Fetches today fresh, then reads cache for previous days.
    Returns list of daily dicts sorted oldest-first.
    """
    history = []

    # Ensure today is cached
    today_data = get_fii_dii_today()
    if today_data.get("source") != "unavailable":
        history.append(today_data)

    # Read from cache for previous days
    for i in range(1, days + 5):  # extra buffer for weekends/holidays
        if len(history) >= days:
            break
        date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        cached = _read_cache(date_str)
        if cached and "fii_net_crores" in cached:
            cached.setdefault("date", date_str)
            history.append(cached)

    # Deduplicate by date, keep first (freshest) per date
    seen = set()
    deduped = []
    for h in history:
        d = h.get("date", "")
        if d not in seen:
            seen.add(d)
            deduped.append(h)
    deduped.sort(key=lambda x: x.get("date", ""))
    return deduped[-days:]


def compute_fii_signal() -> dict:
    """Compute FII flow signal for regime detection.

    Returns:
        dict with: direction (BULLISH/BEARISH/NEUTRAL),
                   fii_3d_net, fii_5d_net,
                   consecutive_sell_days, consecutive_buy_days,
                   signal_strength (-1.0 to +1.0)
    """
    history = get_fii_dii_history(days=10)

    if not history:
        return {
            "direction": "NEUTRAL", "fii_3d_net": 0, "fii_5d_net": 0,
            "consecutive_sell_days": 0, "consecutive_buy_days": 0,
            "signal_strength": 0.0,
        }

    nets = [d.get("fii_net_crores", 0) for d in history]

    # Rolling sums
    fii_3d_net = sum(nets[-3:]) if len(nets) >= 3 else sum(nets)
    fii_5d_net = sum(nets[-5:]) if len(nets) >= 5 else sum(nets)

    # Consecutive sell/buy days (from most recent)
    consec_sell = 0
    consec_buy = 0
    for n in reversed(nets):
        if n < 0:
            consec_sell += 1
        else:
            break
    for n in reversed(nets):
        if n > 0:
            consec_buy += 1
        else:
            break

    # Signal logic
    direction = "NEUTRAL"
    strength = 0.0

    # BEARISH: FII net sell > 2000cr for 3+ days
    if fii_3d_net < -2000 and consec_sell >= 3:
        direction = "BEARISH"
        strength = max(-1.0, fii_5d_net / 10000)  # scale: -10000cr = -1.0

    # BULLISH: FII net buy > 1000cr for 3+ days
    elif fii_3d_net > 1000 and consec_buy >= 3:
        direction = "BULLISH"
        strength = min(1.0, fii_5d_net / 10000)

    # STRONG BULLISH: buy reversal after 10+ sell days
    elif consec_buy >= 1 and len(nets) >= 11:
        # Check if there were 10+ sell days before this buy
        prior_sell_streak = 0
        for n in reversed(nets[:-consec_buy]):
            if n < 0:
                prior_sell_streak += 1
            else:
                break
        if prior_sell_streak >= 10:
            direction = "BULLISH"
            strength = 0.8  # Strong reversal signal

    # Moderate signals (looser thresholds)
    elif fii_5d_net < -3000:
        direction = "BEARISH"
        strength = max(-1.0, fii_5d_net / 15000)
    elif fii_5d_net > 2000:
        direction = "BULLISH"
        strength = min(1.0, fii_5d_net / 15000)

    return {
        "direction": direction,
        "fii_3d_net": round(fii_3d_net, 2),
        "fii_5d_net": round(fii_5d_net, 2),
        "consecutive_sell_days": consec_sell,
        "consecutive_buy_days": consec_buy,
        "signal_strength": round(strength, 3),
    }


# ===================================================================
# CLI
# ===================================================================

def _cli():
    """Print today's FII/DII data and signal."""
    print("\n" + "=" * 55)
    print("  TradePilot v5 — FII/DII Data Feed")
    print("=" * 55)

    # Today's data
    today = get_fii_dii_today()
    print(f"\n  Date:          {today.get('date', 'N/A')}")
    print(f"  Source:        {today.get('source', 'N/A')}")
    print(f"  FII Net:       {today.get('fii_net_crores', 0):>10.2f} Cr")
    print(f"  FII Buy:       {today.get('fii_buy', 0):>10.2f} Cr")
    print(f"  FII Sell:      {today.get('fii_sell', 0):>10.2f} Cr")
    print(f"  DII Net:       {today.get('dii_net_crores', 0):>10.2f} Cr")
    print(f"  DII Buy:       {today.get('dii_buy', 0):>10.2f} Cr")
    print(f"  DII Sell:      {today.get('dii_sell', 0):>10.2f} Cr")

    # History
    history = get_fii_dii_history(days=5)
    if history:
        print(f"\n  {'Date':<14} {'FII Net':>10} {'DII Net':>10}")
        print(f"  {'-'*36}")
        for d in history:
            print(f"  {d.get('date','?'):<14} {d.get('fii_net_crores',0):>10.2f} {d.get('dii_net_crores',0):>10.2f}")

    # Signal
    sig = compute_fii_signal()
    color = {"BULLISH": "\033[92m", "BEARISH": "\033[91m", "NEUTRAL": "\033[93m"}
    reset = "\033[0m"
    c = color.get(sig["direction"], "")
    print(f"\n  Signal:        {c}{sig['direction']}{reset} (strength: {sig['signal_strength']:.2f})")
    print(f"  FII 3d Net:    {sig['fii_3d_net']:.2f} Cr")
    print(f"  FII 5d Net:    {sig['fii_5d_net']:.2f} Cr")
    print(f"  Consec Sell:   {sig['consecutive_sell_days']}d")
    print(f"  Consec Buy:    {sig['consecutive_buy_days']}d")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    _cli()
