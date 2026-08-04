#!/usr/bin/env python3
"""
TradePilot v5.3 — Staged Entry Paper Trading Engine
=====================================================
3-stage entry system that WAITS for confirmation before committing capital.
Runs as a SEPARATE experiment alongside v4, v5, and v5.2.

Key difference from v5:
  - v5 deploys everything at 09:35 with potentially stale prices
  - v5.3 deploys in stages with LIVE confirmed prices
  - v5.3 cancels entries that don't confirm (v5 enters regardless)
  - v5.3 tracks conviction tiers and reports P&L by tier

Daily flow:
  08:30  Pre-market: regime + signals + conviction tiers
  09:35  Stage 1: deploy Tier 1 at 50% (live price, NOT stale quote)
  10:15  Stage 2: ORB confirmation → Tier 1 add 50%, Tier 2 enter 100%
  11:30  Stage 3: midday rescore → Tier 3 enter if signal strengthened
  Every 10m: position management (SL/target/trailing)
  15:15  Force close INTRADAY positions
  15:30  EOD report with tier breakdown

Capital: Rs 10,00,000 (same as v4/v5 for fair comparison)

Usage:
    python3 scripts/v5_3-paper-trade.py              # Auto-pilot
    python3 scripts/v5_3-paper-trade.py --status      # Current state
    python3 scripts/v5_3-paper-trade.py --summary     # Cumulative P&L
"""

from dp_creds import devpilot_db_password
import json
import sys
import time
import warnings
import importlib
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).parent.parent
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades" / "v5_3"
LOG_DIR = PROJECT_ROOT / "logs"
sys.path.insert(0, str(PROJECT_ROOT / "prototype"))
sys.path.insert(0, str(PROJECT_ROOT))
from prototype.utils.signal_guards import atomic_write_json
LOG_FILE = LOG_DIR / "v5_3-paper-trade.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

TOTAL_CAPITAL = 1_000_000  # Rs 10L — same as v4/v5 for fair comparison
TRAILING_TRIGGER_PCT = 1.0
TRAILING_STEP_PCT = 0.5
SCAN_INTERVAL_MIN = 10
FORCE_EXIT_HOUR, FORCE_EXIT_MIN = 15, 15

# Stage timing (IST)
STAGE1_HOUR, STAGE1_MIN = 9, 35
STAGE2_HOUR, STAGE2_MIN = 10, 15
STAGE3_HOUR, STAGE3_MIN = 11, 30
NO_NEW_ENTRIES_HOUR, NO_NEW_ENTRIES_MIN = 12, 0

CARRY_FORWARD_FILE = TRADE_DIR / "carry_forward_v5_3.json"


# ═══════════════════════════════ IMPORTS ═══════════════════════════════

_mods = {}
_mod_imports = {
    "regime": ("prototype.v5.regime_detector", "detect_regime"),
    "signals": ("prototype.v5.signal_engine", "generate_signals"),
    "staged": ("prototype.v5_3.staged_entry", "generate_staged_signals"),
    "classify": ("prototype.v5_3.staged_entry", "classify_conviction"),
    "confirm": ("prototype.v5_3.staged_entry", "check_confirmation"),
    "stage_size": ("prototype.v5_3.staged_entry", "calculate_staged_size"),
    "rescore_syms": ("prototype.v5_3.staged_entry", "rescore_symbols"),
}

for _key, (_mod_path, _attr) in _mod_imports.items():
    try:
        _m = importlib.import_module(_mod_path)
        _mods[_key] = getattr(_m, _attr)
    except (ImportError, AttributeError) as e:
        _mods[_key] = None
        print(f"[WARN] {_key}: {e}")


# ═══════════════════════════════ HELPERS ═══════════════════════════════

def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def _fmt(val):
    return f"Rs {val/1_00_000:,.2f}L" if abs(val) >= 1_00_000 else f"Rs {val:,.0f}"


# ═══════════════════════════════ PRICE FETCH ═══════════════════════════

def get_prices_batch(symbols):
    """Fetch LIVE prices via yfinance 1-minute candles. Always returns latest tick."""
    import yfinance as yf
    prices = {}
    if not symbols:
        return prices
    ns = [s if ".NS" in s else s + ".NS" for s in symbols]
    try:
        data = yf.download(ns, period="1d", interval="1m", progress=False, threads=True)
        if len(data) > 0:
            if len(ns) == 1:
                c = data["Close"]
                if len(c.dropna()) > 0:
                    prices[symbols[0].replace(".NS", "")] = float(c.dropna().iloc[-1])
            elif "Close" in data.columns.get_level_values(0):
                c = data["Close"]
                for s in ns:
                    if s in c.columns and len(c[s].dropna()) > 0:
                        prices[s.replace(".NS", "")] = float(c[s].dropna().iloc[-1])
    except Exception:
        pass
    # Fallback for missing symbols
    for s in symbols:
        clean = s.replace(".NS", "")
        if clean not in prices:
            try:
                h = yf.Ticker(s if ".NS" in s else s + ".NS").history(period="1d", interval="1m")
                if len(h) > 0:
                    prices[clean] = float(h["Close"].iloc[-1])
            except Exception:
                pass
    return prices


def get_intraday_candles(symbol, interval="5m"):
    """Fetch intraday candles for ORB/VWAP computation."""
    try:
        import yfinance as yf
        ns = symbol if ".NS" in symbol else symbol + ".NS"
        df = yf.download(ns, period="1d", interval=interval, progress=False)
        if hasattr(df.columns, 'droplevel') and isinstance(df.columns, __import__('pandas').MultiIndex):
            df.columns = df.columns.droplevel(1)
        return df if len(df) > 0 else None
    except Exception:
        return None


def compute_orb_from_candles(df):
    """Compute Opening Range Breakout from intraday candles (first 15 min: 9:15-9:30)."""
    if df is None or df.empty:
        return None, None
    cols = {c.lower(): c for c in df.columns}
    high_col = cols.get("high", "High")
    low_col = cols.get("low", "Low")

    idx = df.index
    if hasattr(idx, "hour"):
        mask = (idx.hour == 9) & (idx.minute >= 15) & (idx.minute < 30)
        if mask.any():
            orb_df = df.loc[mask]
            return float(orb_df[high_col].max()), float(orb_df[low_col].min())
    # Fallback: first 3 candles (15 min at 5m interval)
    first = df.iloc[:3]
    return float(first[high_col].max()), float(first[low_col].min())


def compute_vwap_from_candles(df):
    """Compute VWAP from intraday OHLCV candles."""
    if df is None or df.empty:
        return None
    cols = {c.lower(): c for c in df.columns}
    high_col = cols.get("high", "High")
    low_col = cols.get("low", "Low")
    close_col = cols.get("close", "Close")
    vol_col = cols.get("volume", "Volume")

    if vol_col not in df.columns:
        return None

    typical = (df[high_col] + df[low_col] + df[close_col]) / 3.0
    cum_tpv = (typical * df[vol_col]).cumsum()
    cum_vol = df[vol_col].cumsum()
    vwap_series = cum_tpv / cum_vol.replace(0, float('nan'))
    if len(vwap_series.dropna()) > 0:
        return float(vwap_series.dropna().iloc[-1])
    return None


def compute_volume_ratio(df):
    """Compute current session volume vs average (rough proxy)."""
    if df is None or df.empty:
        return 1.0
    cols = {c.lower(): c for c in df.columns}
    vol_col = cols.get("volume", "Volume")
    if vol_col not in df.columns:
        return 1.0
    vols = df[vol_col].dropna()
    if len(vols) < 2:
        return 1.0
    avg = vols.mean()
    if avg == 0:
        return 1.0
    return float(vols.iloc[-1] / avg)


def get_vix():
    try:
        import yfinance as yf
        d = yf.download("^INDIAVIX", period="2d", interval="1d", progress=False)
        if hasattr(d.columns, 'droplevel') and len(d.columns.names) > 1:
            d.columns = d.columns.droplevel(1)
        if len(d) > 0:
            return float(d["Close"].iloc[-1])
    except Exception:
        pass
    return 15.0


# ═══════════════════════════════ STATE ═══════════════════════════════

def _state_file():
    return TRADE_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"


def fresh_state(capital=None):
    cap = capital or TOTAL_CAPITAL
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "engine": "v5.3",
        "started_at": datetime.now().strftime("%H:%M:%S"),
        "total_capital": cap,
        "regime": "SIDEWAYS",
        "current_stage": 0,
        # Staged entry tracking
        "staged_signals": [],       # All classified signals for today
        "pending": [],              # Waiting for confirmation
        "stage1_deployed": [],      # Deployed at Stage 1 (partial, awaiting confirm)
        "stage2_deployed": [],      # Deployed at Stage 2 (ORB confirmed)
        "stage3_deployed": [],      # Deployed at Stage 3 (midday confirmed)
        "cancelled": [],            # Confirmation failed → skipped
        "positions": [],            # All open positions
        "closed": [],               # Closed trades
        # Summary
        "summary": {
            "total_pnl": 0, "trades": 0, "wins": 0, "losses": 0,
            "longs": 0, "shorts": 0, "scan_count": 0,
            "tier_pnl": {1: 0, 2: 0, 3: 0},
            "tier_trades": {1: 0, 2: 0, 3: 0},
            "tier_wins": {1: 0, 2: 0, 3: 0},
            "confirmed_count": 0, "cancelled_count": 0,
        },
        "orb_data": {},    # symbol -> {high, low}
        "vwap_data": {},   # symbol -> vwap
    }


def _get_carry_forward_balance():
    if CARRY_FORWARD_FILE.exists():
        try:
            cf = json.load(open(CARRY_FORWARD_FILE))
            bal = cf.get("closing_balance", TOTAL_CAPITAL)
            log(f"  CARRY FORWARD: Rs {bal:,.0f} from {cf.get('date', '?')}")
            return bal
        except Exception:
            pass
    return TOTAL_CAPITAL


def _save_carry_forward(state):
    pnl = state["summary"]["total_pnl"]
    closing = TOTAL_CAPITAL + pnl
    if CARRY_FORWARD_FILE.exists():
        try:
            prev = json.load(open(CARRY_FORWARD_FILE))
            closing = prev.get("closing_balance", TOTAL_CAPITAL) + pnl
        except Exception:
            pass
    cf = {
        "date": state["date"],
        "closing_balance": round(closing, 2),
        "todays_pnl": round(pnl, 2),
        "cumulative_pnl": round(closing - TOTAL_CAPITAL, 2),
        "starting_capital": TOTAL_CAPITAL,
    }
    with open(CARRY_FORWARD_FILE, "w") as f:
        json.dump(cf, f, indent=2)
    log(f"  Balance carried forward: Rs {closing:,.0f}")


def load_state():
    today = datetime.now().strftime("%Y-%m-%d")
    f = _state_file()
    if f.exists():
        s = json.loads(f.read_text())
        if s.get("date") == today:
            return s
    balance = _get_carry_forward_balance()
    return fresh_state(capital=balance)


def save_state(s):
    atomic_write_json(_state_file(), s)


# ═══════════════════════════════ PRE-MARKET ═══════════════════════════

def run_premarket(state):
    log(f"\n{'='*65}")
    log(f"  v5.3 STAGED ENTRY | PRE-MARKET PHASE")
    log(f"{'='*65}")
    detect_regime = _mods.get("regime")
    regime = "SIDEWAYS"
    if detect_regime:
        try:
            rd = detect_regime()
            regime = rd.get("regime", "SIDEWAYS")
            log(f"  Regime: {regime} (score={rd.get('score',0)}, alloc={rd.get('allocation',0.75):.0%})")
        except Exception as e:
            log(f"  Regime failed: {e}")
    state["regime"] = regime

    vix = get_vix()
    log(f"  VIX: {vix:.1f}")

    # Generate staged signals
    gen_staged = _mods.get("staged")
    if gen_staged:
        try:
            signals = gen_staged(regime)
            state["staged_signals"] = signals
            t1 = [s for s in signals if s.get("tier") == 1]
            t2 = [s for s in signals if s.get("tier") == 2]
            t3 = [s for s in signals if s.get("tier") == 3]
            log(f"  Signals: {len(signals)} actionable")
            log(f"    Tier 1 (enter at open):     {len(t1)} stocks")
            log(f"    Tier 2 (wait for ORB):      {len(t2)} stocks")
            log(f"    Tier 3 (wait for midday):   {len(t3)} stocks")
            # List Tier 1 stocks
            for s in t1:
                log(f"      T1 {s['direction']:4s} {s['symbol']:>12s} score={s.get('score',0):.0f}")
            # Mark all Tier 2/3 as pending
            for s in t2 + t3:
                state["pending"].append({
                    "symbol": s["symbol"],
                    "direction": s["direction"],
                    "score": s.get("score", 0),
                    "tier": s["tier"],
                    "conviction": s.get("conviction", {}),
                    "signal": s,
                })
        except Exception as e:
            log(f"  Staged signal gen failed: {e}")
    else:
        log("  [WARN] staged_entry module not available")

    return regime, vix


# ═══════════════════════════════ DEPLOY HELPERS ═══════════════════════

def _deploy_position(state, symbol, direction, price, qty, tier, stage, conviction):
    """Create and record a new position."""
    is_short = direction == "SELL"
    sl_pct = 0.015 if tier <= 2 else 0.02
    tgt_pct = 0.02 if tier <= 2 else 0.025

    if is_short:
        sl = round(price * (1 + sl_pct), 2)
        tgt = round(price * (1 - tgt_pct), 2)
    else:
        sl = round(price * (1 - sl_pct), 2)
        tgt = round(price * (1 + tgt_pct), 2)

    pos = {
        "symbol": symbol,
        "direction": direction,
        "position_type": "SHORT" if is_short else "LONG",
        "entry_price": round(price, 2),
        "qty": qty,
        "cost": round(qty * price, 2),
        "entry_time": datetime.now().strftime("%H:%M:%S"),
        "entry_date": datetime.now().strftime("%Y-%m-%d"),
        "sl_price": sl,
        "target_price": tgt,
        "tier": tier,
        "stage_entered": stage,
        "partial": (tier == 1 and stage == 1),  # Tier 1 Stage 1 = partial position
        "trailing_activated": False,
        "peak_price": round(price, 2),
        "trough_price": round(price, 2),
        "score": conviction.get("original_score", 0),
    }
    state["positions"].append(pos)

    stage_key = f"stage{stage}_deployed"
    if stage_key in state:
        state[stage_key].append(symbol)

    tag = "SHORT" if is_short else "LONG "
    partial_tag = " (50%)" if pos["partial"] else " (100%)"
    log(f"  {tag} {symbol:>12} x{qty:<4d} @{price:.2f} SL:{sl:.2f} TGT:{tgt:.2f} "
        f"TIER {tier}{partial_tag}")
    return pos


# ═══════════════════════════════ STAGE 1 ═══════════════════════════════

def run_stage1(state):
    """
    Stage 1 (09:35): Deploy ONLY Tier 1 stocks at 50% position size.
    Use LIVE price, not stale quote. Shorts: DO NOT enter yet.
    """
    state["current_stage"] = 1
    signals = state.get("staged_signals", [])
    t1_longs = [s for s in signals if s.get("tier") == 1 and s.get("direction") == "BUY"]

    if not t1_longs:
        log("  Stage 1: No Tier 1 longs to deploy")
        return

    log(f"\n{'='*65}")
    log(f"  STAGE 1 DEPLOYMENT | {len(t1_longs)} Tier 1 longs at 50%")
    log(f"{'='*65}")

    # Fetch LIVE prices — CRITICAL: never use stale signal price
    syms = [s["symbol"] for s in t1_longs]
    prices = get_prices_batch(syms)

    held = {p["symbol"] for p in state["positions"]}
    cap = state.get("total_capital", TOTAL_CAPITAL)
    calc_size = _mods.get("stage_size")

    for sig in t1_longs:
        sym = sig["symbol"]
        if sym in held:
            continue

        live_price = prices.get(sym)
        if live_price is None:
            log(f"  {sym}: SKIPPED (no live price)")
            continue

        conv = sig.get("conviction", {})
        if calc_size:
            budget = calc_size(conv, cap, stage=1)
        else:
            budget = cap * 0.15 * 0.5  # 15% max per stock, 50% initial

        if budget < 5000:
            log(f"  {sym}: SKIPPED (budget too small: {budget:.0f})")
            continue

        qty = max(1, int(budget / live_price))
        _deploy_position(state, sym, "BUY", live_price, qty, tier=1, stage=1, conviction=conv)
        held.add(sym)

    save_state(state)


# ═══════════════════════════════ STAGE 2 ═══════════════════════════════

def run_stage2(state):
    """
    Stage 2 (10:15): ORB confirmation.
    - Tier 1 longs: if price > ORB high → add remaining 50%
    - Tier 2: if ORB confirmed → enter 100%
    - Shorts: if price < ORB low → enter full short
    - If NOT confirmed → cancel pending entry
    """
    state["current_stage"] = 2
    log(f"\n{'='*65}")
    log(f"  STAGE 2 | ORB CONFIRMATION")
    log(f"{'='*65}")

    # Compute ORB for all relevant symbols
    all_syms = set()
    for p in state["positions"]:
        all_syms.add(p["symbol"])
    for pend in state.get("pending", []):
        if pend.get("tier") == 2:
            all_syms.add(pend["symbol"])

    # Fetch intraday data and compute ORB/VWAP
    for sym in all_syms:
        df = get_intraday_candles(sym)
        if df is not None:
            h, l = compute_orb_from_candles(df)
            if h is not None and l is not None:
                state["orb_data"][sym] = {"high": h, "low": l}
            vwap = compute_vwap_from_candles(df)
            if vwap is not None:
                state["vwap_data"][sym] = vwap

    # Fetch live prices
    prices = get_prices_batch(list(all_syms))
    check_fn = _mods.get("confirm")
    calc_size = _mods.get("stage_size")
    cap = state.get("total_capital", TOTAL_CAPITAL)

    # --- Tier 1: check ORB confirmation for existing partial positions ---
    for pos in list(state["positions"]):
        if not pos.get("partial"):
            continue
        sym = pos["symbol"]
        live_price = prices.get(sym)
        if live_price is None:
            continue

        orb = state["orb_data"].get(sym, {})
        vwap = state["vwap_data"].get(sym, live_price)
        conv = {"confirm_condition": "price_above_orb_high", "tier": 1,
                "original_score": pos.get("score", 0)}

        if check_fn:
            result = check_fn(sym, conv, live_price,
                              orb.get("high", live_price * 1.01),
                              orb.get("low", live_price * 0.99),
                              vwap)
        else:
            result = {"confirmed": live_price > orb.get("high", live_price * 1.01),
                      "reason": "manual check", "entry_price": live_price}

        if result["confirmed"]:
            # Add remaining 50%
            already = pos["cost"]
            if calc_size:
                budget = calc_size(conv, cap, stage=2, already_deployed=already)
            else:
                budget = cap * 0.15 * 0.5
            add_qty = max(1, int(budget / live_price))
            pos["qty"] += add_qty
            pos["cost"] = round(pos["qty"] * pos["entry_price"], 2)
            pos["partial"] = False
            state["summary"]["confirmed_count"] += 1
            log(f"  CONFIRMED {sym}: +{add_qty} shares @{live_price:.2f} "
                f"({result['reason']}) → total x{pos['qty']}")
        else:
            log(f"  {sym}: ORB not confirmed ({result['reason']}) — keeping partial position")

    # --- Tier 2: check pending signals ---
    held = {p["symbol"] for p in state["positions"]}
    remaining_pending = []

    for pend in state.get("pending", []):
        if pend.get("tier") != 2:
            remaining_pending.append(pend)
            continue

        sym = pend["symbol"]
        if sym in held:
            continue

        live_price = prices.get(sym)
        if live_price is None:
            log(f"  {sym}: SKIPPED (no live price)")
            state["cancelled"].append({"symbol": sym, "tier": 2, "reason": "no live price"})
            state["summary"]["cancelled_count"] += 1
            continue

        orb = state["orb_data"].get(sym, {})
        vwap = state["vwap_data"].get(sym, live_price)
        conv = pend.get("conviction", {})
        direction = pend.get("direction", "BUY")

        if check_fn:
            vol_ratio = 1.0
            df = get_intraday_candles(sym)
            if df is not None:
                vol_ratio = compute_volume_ratio(df)
            result = check_fn(sym, conv, live_price,
                              orb.get("high", live_price * 1.01),
                              orb.get("low", live_price * 0.99),
                              vwap, volume_ratio=vol_ratio)
        else:
            if direction == "SELL":
                result = {"confirmed": live_price < orb.get("low", live_price * 0.99),
                          "reason": "manual", "entry_price": live_price}
            else:
                result = {"confirmed": live_price > vwap,
                          "reason": "manual", "entry_price": live_price}

        if result["confirmed"]:
            if calc_size:
                budget = calc_size(conv, cap, stage=2)
            else:
                budget = cap * 0.15

            qty = max(1, int(budget / live_price))
            _deploy_position(state, sym, direction, live_price, qty, tier=2, stage=2, conviction=conv)
            held.add(sym)
            state["summary"]["confirmed_count"] += 1
        else:
            log(f"  CANCELLED {sym} T2 {direction}: {result['reason']}")
            state["cancelled"].append({"symbol": sym, "tier": 2, "reason": result["reason"]})
            state["summary"]["cancelled_count"] += 1

    state["pending"] = remaining_pending
    save_state(state)


# ═══════════════════════════════ STAGE 3 ═══════════════════════════════

def run_stage3(state):
    """
    Stage 3 (11:30): Midday rescore.
    - Tier 3: if new score > original score → enter
    - Tier 1/2 not confirmed: final chance
    - After this, no new entries.
    """
    state["current_stage"] = 3
    log(f"\n{'='*65}")
    log(f"  STAGE 3 | MIDDAY RESCORE")
    log(f"{'='*65}")

    pending = state.get("pending", [])
    if not pending:
        log("  No pending signals for Stage 3")
        return

    # Rescore all pending symbols
    syms = [p["symbol"] for p in pending]
    rescore_fn = _mods.get("rescore_syms")
    new_scores = {}
    if rescore_fn:
        try:
            new_scores = rescore_fn(syms)
            log(f"  Rescored {len(new_scores)} symbols")
        except Exception as e:
            log(f"  Rescore failed: {e}")

    prices = get_prices_batch(syms)
    check_fn = _mods.get("confirm")
    calc_size = _mods.get("stage_size")
    cap = state.get("total_capital", TOTAL_CAPITAL)
    held = {p["symbol"] for p in state["positions"]}

    for pend in pending:
        sym = pend["symbol"]
        if sym in held:
            continue

        live_price = prices.get(sym)
        if live_price is None:
            log(f"  {sym}: SKIPPED (no live price)")
            state["cancelled"].append({"symbol": sym, "tier": pend.get("tier", 3),
                                       "reason": "no live price at midday"})
            state["summary"]["cancelled_count"] += 1
            continue

        conv = pend.get("conviction", {})
        direction = pend.get("direction", "BUY")
        new_score = new_scores.get(sym)

        orb = state["orb_data"].get(sym, {})
        vwap = state["vwap_data"].get(sym, live_price)

        if check_fn:
            result = check_fn(sym, conv, live_price,
                              orb.get("high", live_price * 1.01),
                              orb.get("low", live_price * 0.99),
                              vwap, new_score=new_score)
        else:
            orig = conv.get("original_score", 0)
            result = {"confirmed": new_score is not None and new_score > orig + 5,
                      "reason": f"score {new_score} vs {orig}",
                      "entry_price": live_price}

        if result["confirmed"]:
            tier = pend.get("tier", 3)
            if calc_size:
                budget = calc_size(conv, cap, stage=3)
            else:
                budget = cap * 0.15

            qty = max(1, int(budget / live_price))
            _deploy_position(state, sym, direction, live_price, qty, tier=tier, stage=3,
                             conviction=conv)
            held.add(sym)
            state["summary"]["confirmed_count"] += 1
        else:
            log(f"  CANCELLED {sym} T{pend.get('tier',3)} {direction}: {result['reason']}")
            state["cancelled"].append({"symbol": sym, "tier": pend.get("tier", 3),
                                       "reason": result["reason"]})
            state["summary"]["cancelled_count"] += 1

    state["pending"] = []  # No more pending after Stage 3
    save_state(state)


# ═══════════════════════════════ POSITION SCAN ═══════════════════════════

def scan_positions(state):
    """Check SL/target/trailing for all open positions."""
    state["summary"]["scan_count"] += 1
    positions = state.get("positions", [])
    if not positions:
        log("  No open positions")
        return

    prices = get_prices_batch([p["symbol"] for p in positions])
    unrealized = 0
    to_close = []

    log(f"\n{'='*65}")
    log(f"  SCAN #{state['summary']['scan_count']} | {len(positions)} positions")
    log(f"{'='*65}")

    for pos in positions:
        sym = pos["symbol"]
        entry = pos["entry_price"]
        if sym not in prices:
            log(f"  {sym}: no price")
            continue

        px = prices[sym]
        is_short = pos.get("position_type") == "SHORT"

        if is_short:
            pnl_rs = (entry - px) * pos["qty"]
            pnl_pct = (entry - px) / entry * 100
            if px < pos.get("trough_price", entry):
                pos["trough_price"] = round(px, 2)
        else:
            pnl_rs = (px - entry) * pos["qty"]
            pnl_pct = (px - entry) / entry * 100
            if px > pos.get("peak_price", entry):
                pos["peak_price"] = round(px, 2)

        unrealized += pnl_rs
        reason = None

        if is_short:
            if px >= pos["sl_price"]:
                reason = "STOPLOSS"
            elif px <= pos["target_price"]:
                reason = "TARGET"
            elif pnl_pct >= TRAILING_TRIGGER_PCT:
                if not pos.get("trailing_activated"):
                    pos["trailing_activated"] = True
                    pos["sl_price"] = entry
                    log(f"  {sym}: SHORT TRAILING -> SL@{entry:.2f}")
                else:
                    trail = round(pos["trough_price"] * (1 + TRAILING_STEP_PCT / 100), 2)
                    if trail < pos["sl_price"]:
                        pos["sl_price"] = trail
        else:
            if px <= pos["sl_price"]:
                reason = "STOPLOSS"
            elif px >= pos["target_price"]:
                reason = "TARGET"
            elif pnl_pct >= TRAILING_TRIGGER_PCT:
                if not pos.get("trailing_activated"):
                    pos["trailing_activated"] = True
                    pos["sl_price"] = entry
                    log(f"  {sym}: LONG TRAILING -> SL@{entry:.2f}")
                else:
                    trail = round(pos["peak_price"] * (1 - TRAILING_STEP_PCT / 100), 2)
                    if trail > pos["sl_price"]:
                        pos["sl_price"] = trail

        if reason:
            to_close.append((pos, px, reason))
        else:
            t = " [T]" if pos.get("trailing_activated") else ""
            partial = " [PARTIAL]" if pos.get("partial") else ""
            tag = "S" if is_short else "L"
            log(f"  {tag} {sym:>12} {px:>8.2f} {pnl_pct:+5.2f}% {pnl_rs:+8,.0f} "
                f"SL:{pos['sl_price']:.2f} TGT:{pos['target_price']:.2f} T{pos.get('tier','?')}{t}{partial}")

    for pos, px, reason in to_close:
        close_position(state, pos, px, reason)

    log(f"\n  Realized: {_fmt(state['summary']['total_pnl'])} | Unrealized: {_fmt(unrealized)}")


def close_position(state, pos, exit_price, reason):
    """Close a position and record P&L."""
    sym = pos["symbol"]
    is_short = pos.get("position_type") == "SHORT"
    tier = pos.get("tier", 0)

    if is_short:
        pnl = (pos["entry_price"] - exit_price) * pos["qty"]
        pnl_pct = (pos["entry_price"] - exit_price) / pos["entry_price"] * 100
    else:
        pnl = (exit_price - pos["entry_price"]) * pos["qty"]
        pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100

    state["closed"].append({
        "symbol": sym,
        "entry_price": pos["entry_price"],
        "exit_price": round(exit_price, 2),
        "qty": pos["qty"],
        "entry_time": pos.get("entry_time", ""),
        "exit_time": datetime.now().strftime("%H:%M:%S"),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "reason": reason,
        "position_type": pos.get("position_type", "LONG"),
        "tier": tier,
        "stage_entered": pos.get("stage_entered", 0),
    })

    # Remove from positions
    state["positions"] = [p for p in state["positions"] if p["symbol"] != sym]

    # Update summary
    s = state["summary"]
    s["total_pnl"] += pnl
    s["trades"] += 1
    if pnl > 0:
        s["wins"] += 1
    else:
        s["losses"] += 1
    if is_short:
        s["shorts"] = s.get("shorts", 0) + 1
    else:
        s["longs"] = s.get("longs", 0) + 1

    # Tier-level tracking
    t_key = str(tier)
    tier_pnl = s.get("tier_pnl", {})
    tier_trades = s.get("tier_trades", {})
    tier_wins = s.get("tier_wins", {})
    tier_pnl[t_key] = tier_pnl.get(t_key, 0) + pnl
    tier_trades[t_key] = tier_trades.get(t_key, 0) + 1
    if pnl > 0:
        tier_wins[t_key] = tier_wins.get(t_key, 0) + 1
    s["tier_pnl"] = tier_pnl
    s["tier_trades"] = tier_trades
    s["tier_wins"] = tier_wins

    tag = ("WIN" if pnl > 0 else "LOSS") + f" {'SHORT' if is_short else 'LONG'}"
    log(f"  >> {tag} {sym} x{pos['qty']} @{exit_price:.2f} ({reason}) "
        f"P&L: Rs {pnl:+,.0f} ({pnl_pct:+.2f}%) [T{tier}]")


# ═══════════════════════════════ FORCE CLOSE ═══════════════════════════

def force_close_intraday(state):
    """Force close all positions at 15:15 (intraday only)."""
    positions = state.get("positions", [])
    if not positions:
        log("  No positions to close")
        return

    log(f"\n  FORCE CLOSING {len(positions)} positions")
    prices = get_prices_batch([p["symbol"] for p in positions])

    for pos in list(positions):
        exit_px = prices.get(pos["symbol"], pos["entry_price"])
        close_position(state, pos, exit_px, "TIME_EXIT")


# ═══════════════════════════════ STATUS DISPLAY ═══════════════════════

def print_status(state):
    regime = state.get("regime", "?")
    stage = state.get("current_stage", 0)
    s = state.get("summary", {})

    stage_names = {0: "Pre-market", 1: "Stage 1 (Initial)", 2: "Stage 2 (ORB Confirmation)",
                   3: "Stage 3 (Midday Rescore)"}

    C = {"BULL": "\033[92m", "BEAR": "\033[91m", "SIDEWAYS": "\033[93m"}
    R = "\033[0m"

    print(f"\n{'='*65}")
    print(f"  v5.3 STAGED ENTRY  |  {state.get('date','today')}  |  Capital: {_fmt(TOTAL_CAPITAL)}")
    print(f"  Regime: {C.get(regime,'')}{regime}{R}  |  Stage: {stage_names.get(stage, f'Stage {stage}')}")
    print(f"{'='*65}")

    # Stage 1 deployed
    s1_positions = [p for p in state.get("positions", []) if p.get("stage_entered") == 1]
    if s1_positions:
        print(f"\n  STAGE 1 (deployed at {STAGE1_HOUR}:{STAGE1_MIN:02d}):")
        for p in s1_positions:
            partial = "[WAITING for ORB confirm]" if p.get("partial") else "[CONFIRMED]"
            tag = "SHORT" if p.get("position_type") == "SHORT" else "LONG "
            print(f"    {tag} {p['symbol']:>12} x{p['qty']:<4d} @{p['entry_price']:.2f} "
                  f"{'50% size' if p.get('partial') else '100% size':>10s}  TIER {p.get('tier','?')}  {partial}")

    # Stage 2 deployed
    s2_positions = [p for p in state.get("positions", []) if p.get("stage_entered") == 2]
    if s2_positions:
        print(f"\n  STAGE 2 (deployed at {STAGE2_HOUR}:{STAGE2_MIN:02d}):")
        for p in s2_positions:
            ptype = p.get("position_type", "LONG")
            tag = "SHORT" if ptype == "SHORT" else "LONG "
            confirm = "[ORB BREAKDOWN CONFIRMED]" if ptype == "SHORT" else "[ORB CONFIRMED]"
            print(f"    {tag} {p['symbol']:>12} x{p['qty']:<4d} @{p['entry_price']:.2f} "
                  f"{'100% size':>10s}  TIER {p.get('tier','?')}  {confirm}")

    # Stage 3 deployed
    s3_positions = [p for p in state.get("positions", []) if p.get("stage_entered") == 3]
    if s3_positions:
        print(f"\n  STAGE 3 (deployed at {STAGE3_HOUR}:{STAGE3_MIN:02d}):")
        for p in s3_positions:
            tag = "SHORT" if p.get("position_type") == "SHORT" else "LONG "
            print(f"    {tag} {p['symbol']:>12} x{p['qty']:<4d} @{p['entry_price']:.2f} "
                  f"{'100% size':>10s}  TIER {p.get('tier','?')}  [MIDDAY CONFIRMED]")

    # Cancelled
    cancelled = state.get("cancelled", [])
    if cancelled:
        print(f"\n  CANCELLED (confirmation failed):")
        for c in cancelled:
            print(f"    {c['symbol']:>12}  -- Tier {c.get('tier','?')}, {c.get('reason','unknown')}")

    # Closed trades
    closed = state.get("closed", [])
    if closed:
        wins = sum(1 for t in closed if t["pnl"] > 0)
        print(f"\n  CLOSED: {len(closed)} trades ({wins}W/{len(closed)-wins}L) | {_fmt(s.get('total_pnl', 0))}")

    # Tier performance
    tier_pnl = s.get("tier_pnl", {})
    tier_trades = s.get("tier_trades", {})
    tier_wins = s.get("tier_wins", {})
    has_tier_data = any(tier_trades.get(str(t), 0) > 0 for t in [1, 2, 3])
    if has_tier_data:
        print(f"\n  Tier Performance:")
        for t in [1, 2, 3]:
            tk = str(t)
            tr = tier_trades.get(tk, 0)
            w = tier_wins.get(tk, 0)
            pnl = tier_pnl.get(tk, 0)
            if tr > 0:
                print(f"    Tier {t}: {tr} trades, {_fmt(pnl)}, {w/tr*100:.0f}% win")
            else:
                print(f"    Tier {t}: 0 trades (none confirmed)")
        cancelled_count = s.get("cancelled_count", len(cancelled))
        if cancelled_count:
            print(f"    Cancelled: {cancelled_count} signals (saved from bad entries)")

    print(f"{'='*65}")


def print_summary(state):
    s = state.get("summary", {})
    pnl = s.get("total_pnl", 0)
    tr = s.get("trades", 0)
    w = s.get("wins", 0)

    print(f"\nv5.3 STAGED ENTRY | {state.get('date','today')} | {_fmt(TOTAL_CAPITAL)} | Regime: {state.get('regime','?')}")
    print(f"P&L: {_fmt(pnl)} ({pnl/TOTAL_CAPITAL*100:+.2f}%)")
    if tr:
        print(f"Trades: {tr} | Wins: {w} ({w/tr*100:.0f}%) | L:{s.get('longs',0)} S:{s.get('shorts',0)}")
    print(f"Confirmed: {s.get('confirmed_count',0)} | Cancelled: {s.get('cancelled_count',0)}")

    tier_pnl = s.get("tier_pnl", {})
    tier_trades = s.get("tier_trades", {})
    tier_wins = s.get("tier_wins", {})
    for t in [1, 2, 3]:
        tk = str(t)
        tr_t = tier_trades.get(tk, 0)
        pnl_t = tier_pnl.get(tk, 0)
        w_t = tier_wins.get(tk, 0)
        if tr_t:
            print(f"  T{t}: {tr_t} trades, {_fmt(pnl_t)}, {w_t/tr_t*100:.0f}%w")


# ═══════════════════════════════ EOD REPORT ═══════════════════════════

def generate_report(state):
    today = datetime.now().strftime("%Y-%m-%d")
    path = TRADE_DIR / f"{today}_report.md"
    s = state.get("summary", {})
    pnl = s.get("total_pnl", 0)
    pp = pnl / TOTAL_CAPITAL * 100
    closed = state.get("closed", [])
    wins = [t for t in closed if t["pnl"] > 0]
    wr = len(wins) / len(closed) * 100 if closed else 0

    lines = [
        f"# v5.3 Staged Entry Report -- {today}\n",
        "## Summary\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Engine | v5.3 staged entry |",
        f"| Capital | {_fmt(TOTAL_CAPITAL)} |",
        f"| Regime | {state.get('regime', '?')} |",
        f"| **Net P&L** | **{_fmt(pnl)} ({pp:+.2f}%)** |",
        f"| Trades | {s.get('trades', 0)} (L:{s.get('longs', 0)} S:{s.get('shorts', 0)}) |",
        f"| Win Rate | {wr:.0f}% |",
        f"| Confirmed | {s.get('confirmed_count', 0)} |",
        f"| Cancelled | {s.get('cancelled_count', 0)} |",
        "",
        "## Tier Breakdown\n",
        "| Tier | Trades | P&L | Win Rate |",
        "|------|--------|-----|----------|",
    ]

    tier_pnl = s.get("tier_pnl", {})
    tier_trades = s.get("tier_trades", {})
    tier_wins = s.get("tier_wins", {})
    for t in [1, 2, 3]:
        tk = str(t)
        tr = tier_trades.get(tk, 0)
        p = tier_pnl.get(tk, 0)
        w = tier_wins.get(tk, 0)
        wr_t = f"{w/tr*100:.0f}%" if tr else "N/A"
        lines.append(f"| Tier {t} | {tr} | {_fmt(p)} | {wr_t} |")

    lines += [
        "",
        "## Trades\n",
        "| # | Type | Tier | Stock | Entry | Exit | P&L | Reason |",
        "|---|------|------|-------|-------|------|-----|--------|",
    ]
    for i, t in enumerate(closed, 1):
        lines.append(
            f"| {i} | {t.get('position_type', 'LONG')} | T{t.get('tier', '?')} | "
            f"{t['symbol']} | {t['entry_price']:.2f} | {t['exit_price']:.2f} | "
            f"Rs {t['pnl']:+,.0f} | {t['reason']} |"
        )

    cancelled = state.get("cancelled", [])
    if cancelled:
        lines += [
            "",
            "## Cancelled Entries\n",
            "| Stock | Tier | Reason |",
            "|-------|------|--------|",
        ]
        for c in cancelled:
            lines.append(f"| {c['symbol']} | T{c.get('tier', '?')} | {c.get('reason', '')} |")

    path.write_text("\n".join(lines))
    log(f"  Report: {path}")


def push_to_devpilot(state):
    try:
        import psycopg2
        conn = psycopg2.connect(host="localhost", port=5499, user="devpilot",
                                password=devpilot_db_password(), dbname="devpilot")
        s = state.get("summary", {})
        today = datetime.now().strftime("%Y-%m-%d")
        pnl = s.get("total_pnl", 0)
        pp = pnl / TOTAL_CAPITAL * 100
        wr = s.get("wins", 0) / max(s.get("trades", 1), 1) * 100
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO learnings (project,category,title,content,source,tags,active,created_at,updated_at) "
            "VALUES (%s,%s,%s,%s,'v5.3-paper-trade',%s,true,NOW(),NOW())",
            ("tradepilot", "paper-trade",
             f"v5.3 {today}: {_fmt(pnl)} ({pp:+.2f}%) | {s.get('trades',0)}t | {wr:.0f}%w | "
             f"C:{s.get('confirmed_count',0)} X:{s.get('cancelled_count',0)}",
             json.dumps({
                 "engine": "v5.3", "capital": TOTAL_CAPITAL,
                 "regime": state.get("regime", "?"),
                 "pnl": pnl, "trades": s.get("trades", 0),
                 "wins": s.get("wins", 0), "longs": s.get("longs", 0),
                 "shorts": s.get("shorts", 0),
                 "confirmed": s.get("confirmed_count", 0),
                 "cancelled": s.get("cancelled_count", 0),
                 "tier_pnl": s.get("tier_pnl", {}),
                 "tier_trades": s.get("tier_trades", {}),
             }),
             ["paper-trade", "v5.3", "staged-entry", today, state.get("regime", "").lower()]))
        conn.commit()
        cur.close()
        conn.close()
        log("  Saved to DevPilot DB")
    except Exception as e:
        log(f"  DevPilot push failed: {e}")


# ═══════════════════════════════ MAIN LOOP ═══════════════════════════

def _wait_until(hour, minute, label):
    """Wait until a specific time (IST). Returns False if already past."""
    target = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    now = datetime.now()
    if now >= target:
        return False  # Already past this time
    wait_sec = (target - now).total_seconds()
    log(f"\n  Waiting {wait_sec/60:.0f}m for {label} ({hour}:{minute:02d})...")
    time.sleep(wait_sec)
    return True


def run():
    log(f"{'='*65}")
    log(f"  v5.3 STAGED ENTRY ENGINE | {_fmt(TOTAL_CAPITAL)}")
    log(f"  Stage 1: {STAGE1_HOUR}:{STAGE1_MIN:02d} (Tier 1 @ 50%)")
    log(f"  Stage 2: {STAGE2_HOUR}:{STAGE2_MIN:02d} (ORB confirmation)")
    log(f"  Stage 3: {STAGE3_HOUR}:{STAGE3_MIN:02d} (midday rescore)")
    log(f"  Exit:    {FORCE_EXIT_HOUR}:{FORCE_EXIT_MIN:02d}")
    log(f"{'='*65}")

    state = load_state()

    # === Pre-market ===
    regime, vix = run_premarket(state)
    save_state(state)

    # === Stage 1: Initial deployment (09:35) ===
    _wait_until(STAGE1_HOUR, STAGE1_MIN, "Stage 1")
    if datetime.now().hour < FORCE_EXIT_HOUR:
        run_stage1(state)
        save_state(state)

    # === Stage 2: ORB confirmation (10:15) ===
    _wait_until(STAGE2_HOUR, STAGE2_MIN, "Stage 2")
    if datetime.now().hour < FORCE_EXIT_HOUR:
        run_stage2(state)
        save_state(state)

    # === Stage 3: Midday rescore (11:30) ===
    _wait_until(STAGE3_HOUR, STAGE3_MIN, "Stage 3")
    if datetime.now().hour < FORCE_EXIT_HOUR:
        run_stage3(state)
        save_state(state)

    # === Position management loop ===
    while True:
        now = datetime.now()
        fe = now.replace(hour=FORCE_EXIT_HOUR, minute=FORCE_EXIT_MIN, second=0)

        if now >= fe:
            force_close_intraday(state)
            save_state(state)
            break

        if now >= now.replace(hour=15, minute=30):
            break

        wait = min(SCAN_INTERVAL_MIN * 60, (fe - now).total_seconds())
        if wait > 0:
            log(f"\n  Next scan in {wait/60:.0f}m...")
            time.sleep(wait)

        scan_positions(state)
        save_state(state)

    # === EOD ===
    log(f"\n{'='*65}")
    log(f"  END OF DAY")
    log(f"{'='*65}")
    print_status(state)
    generate_report(state)
    push_to_devpilot(state)
    _save_carry_forward(state)
    save_state(state)

    s = state.get("summary", {})
    if s.get("trades"):
        log(f"\n  FINAL: {_fmt(s['total_pnl'])} ({s['total_pnl']/TOTAL_CAPITAL*100:+.2f}%) | "
            f"{s['trades']}t (L:{s.get('longs',0)} S:{s.get('shorts',0)}) | "
            f"{s['wins']}W/{s['losses']}L | "
            f"Confirmed:{s.get('confirmed_count',0)} Cancelled:{s.get('cancelled_count',0)}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        print_status(load_state())
    elif "--summary" in sys.argv:
        print_summary(load_state())
    else:
        run()
