#!/usr/bin/env python3
"""
TradePilot v7_regime Paper Trading Engine
=========================================
This is v5's engine (multi-pool, regime-aware, long+short, same sizing / pools /
SL-target / cost model / risk guards) with ONE thing swapped: the per-stock
DIRECTION decision. Instead of trusting v5's signal-engine BUY/SELL labels, each
candidate's side is decided by the two-layer long/short/flip logic:

  Layer 1 (gate):  prototype.v7.regime_gate.allowed_side(daily_df)
                   -> LONG_ONLY / SHORT_ONLY / BOTH / FLAT  (per-symbol, daily bars)
  Layer 2 (flip):  prototype.v7.supertrend_flip.supertrend(...) + flip_states(...)
                   -> LONG / SHORT / FLAT  (Supertrend state collapsed by the gate)

A side the regime forbids collapses to FLAT (no entry; existing position closed).
An intraday guard also refuses to SHORT a stock that is green on the day, or LONG
a stock that is red on the day. Everything else is v5 verbatim.

Spec:  docs/research/2026-06-08_long-short-flip-spec.md
Plan:  docs/superpowers/plans/2026-06-08-v7-regime-engine.md

Usage:
    python3 scripts/v7_regime-paper-trade.py              # Full auto-pilot
    python3 scripts/v7_regime-paper-trade.py --status      # All pools + positions
    python3 scripts/v7_regime-paper-trade.py --summary     # P&L summary
    python3 scripts/v7_regime-paper-trade.py --compare     # Run v4 vs v5 comparator
    python3 scripts/v7_regime-paper-trade.py --premarket   # Show pre-market analysis only
"""
import json, os, sys, time, warnings, importlib
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
PROJECT_ROOT = Path(__file__).parent.parent
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades" / "v7_regime"
LOG_DIR = PROJECT_ROOT / "logs"
sys.path.insert(0, str(PROJECT_ROOT / "prototype"))
sys.path.insert(0, str(PROJECT_ROOT))
from prototype.utils.signal_guards import safe_qty, atomic_write_json, check_model_freshness, is_reentry_blocked, record_reentry_sl
LOG_FILE = LOG_DIR / "v7_regime-paper-trade.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

TOTAL_CAPITAL = 1_000_000  # Same Rs 10L as v4 for fair comparison
TRAILING_TRIGGER_PCT, TRAILING_STEP_PCT = 1.0, 0.5
SCAN_INTERVAL_MIN, RESCORE_INTERVAL_MIN = 10, 30
FORCE_EXIT_HOUR, FORCE_EXIT_MIN = 15, 15
POOL_NAMES = ["INTRADAY", "SWING", "POSITIONAL", "INVESTMENT"]

# ═════════ TRACK A — Phase 1 tactical fixes (per IMPLEMENTATION_BRIEF_2026-04-27.md) ═════════
# All four constants below are tunable via env vars so we can dial without code edits.

# Task 1.1 — BULLISH_PREMARKET_SHORT_BLOCK
SHORT_BLOCK_GAP_PCT    = float(os.environ.get("SHORT_BLOCK_GAP_PCT", "0.5"))
SHORT_BLOCK_WINDOW_MIN = int(os.environ.get("SHORT_BLOCK_WINDOW_MIN", "60"))

# Task 1.2 — WINNER_RE_ARM
WINNER_REARM_MAX = int(os.environ.get("WINNER_REARM_MAX", "3"))

# Task 1.3 — TIME_EXIT_TIGHTENING
FLAT_EXIT_THRESHOLD_PCT = float(os.environ.get("FLAT_EXIT_THRESHOLD_PCT", "0.3"))
FLAT_EXIT_WINDOW_START  = os.environ.get("FLAT_EXIT_WINDOW_START", "13:30")
FLAT_EXIT_WINDOW_END    = os.environ.get("FLAT_EXIT_WINDOW_END",   "14:00")

# Task 1.4 — Cost modeling (Indian retail intraday: brokerage + STT + slippage)
COST_BPS_ROUND_TRIP = float(os.environ.get("COST_BPS_ROUND_TRIP", "12"))


def cost_for_trade(qty: int, entry_price: float, exit_price: float) -> float:
    """Round-trip cost in INR using avg notional × bps. ~12 bps default."""
    notional_avg = qty * (entry_price + exit_price) / 2
    return notional_avg * (COST_BPS_ROUND_TRIP / 10000)


def _short_block_active(state) -> bool:
    """Task 1.1: True iff (premarket BULLISH) AND (gap up > threshold) AND (in first N min)."""
    pm = state.get("premarket", {}) or {}
    overall = pm.get("overall", {}) or {}
    bias_bullish = str(overall.get("bias", "")).upper() == "BULLISH"
    gap = pm.get("gap_prediction", {}) or {}
    gap_up = (str(gap.get("direction", "")).upper() == "UP" and
              float(gap.get("magnitude_pct", 0) or 0) > SHORT_BLOCK_GAP_PCT)
    now = datetime.now()
    minutes_since_open = (now.hour - 9) * 60 + now.minute - 15
    in_window = 0 <= minutes_since_open < SHORT_BLOCK_WINDOW_MIN
    return bias_bullish and gap_up and in_window


def mark_rearmable(state, symbol: str, direction: str, max_rearms: int = None) -> dict:
    """Task 1.2: When a position exits with TARGET, allow up to N re-entries today."""
    if max_rearms is None:
        max_rearms = WINNER_REARM_MAX
    rearm = state.setdefault("rearmable", {})
    if symbol not in rearm:
        rearm[symbol] = {
            "direction": direction,
            "remaining": max_rearms,
            "expires_at_minute": (15 - 9) * 60,  # 15:00 IST cutoff
        }
    return rearm[symbol]


def consume_rearm(state, symbol: str, direction: str) -> bool:
    """Task 1.2: True if a re-arm slot is available for (symbol, direction); consumes it."""
    rearm = state.get("rearmable", {}).get(symbol)
    if not rearm or rearm["direction"] != direction or rearm["remaining"] <= 0:
        return False
    rearm["remaining"] -= 1
    return True


def _in_flat_exit_window(now=None) -> bool:
    """Task 1.3: True iff current time is in the FLAT_EXIT window (default 13:30-14:00 IST)."""
    now = now or datetime.now()
    cur = (now.hour, now.minute)
    sh, sm = (int(x) for x in FLAT_EXIT_WINDOW_START.split(":"))
    eh, em = (int(x) for x in FLAT_EXIT_WINDOW_END.split(":"))
    return (sh, sm) <= cur < (eh, em)
# ═════════ end Track A constants/helpers ═════════

# ═══════════════════════════ IMPORTS (graceful) ═══════════════════════════
_mods = {}
_mod_imports = {
    "regime": ("prototype.v5.regime_detector", "detect_regime"),
    "premarket": ("prototype.v5.premarket_intel", "get_premarket_intel"),
    "pools": ("prototype.v5.pool_manager", "PoolManager"),
    "signals": ("prototype.v5.signal_engine", "generate_signals"),
    "risk": ("prototype.v5.risk_manager", "RiskManager"),
    "allowed_side": ("prototype.v7.regime_gate", "allowed_side"),
    "supertrend":   ("prototype.v7.supertrend_flip", "supertrend"),
    "flip_states":  ("prototype.v7.supertrend_flip", "flip_states"),
    "intraday_candles": ("prototype.v4.data_nse", "get_intraday_candles"),
}

for _key, (_mod_path, _attr) in _mod_imports.items():
    try:
        _m = importlib.import_module(_mod_path)
        _mods[_key] = getattr(_m, _attr)
    except (ImportError, AttributeError) as e:
        _mods[_key] = None
        print(f"[WARN] {_key}: {e}")

# Comparator needs multiple imports
try:
    _comp_mod = importlib.import_module("prototype.v5.comparator")
    _mods["comparator"] = _comp_mod.simulate_v5_decisions
    _mods["comp_print"] = _comp_mod.print_comparison
    _mods["comp_save"] = _comp_mod.save_comparison
except (ImportError, AttributeError) as e:
    _mods["comparator"] = _mods["comp_print"] = _mods["comp_save"] = None
    print(f"[WARN] comparator: {e}")


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def _fmt(val):
    return f"Rs {val/1_00_000:,.2f}L" if abs(val) >= 1_00_000 else f"Rs {val:,.0f}"


# ═══════════════════════════ PRICE FETCH ═══════════════════════════

def get_prices_batch(symbols):
    import yfinance as yf
    prices = {}
    if not symbols: return prices
    ns = [s if ".NS" in s else s + ".NS" for s in symbols]
    try:
        data = yf.download(ns, period="1d", interval="1m", progress=False, threads=True)
        if len(data) > 0:
            if len(ns) == 1:
                c = data["Close"]
                if len(c.dropna()) > 0: prices[symbols[0].replace(".NS", "")] = float(c.dropna().iloc[-1])
            elif "Close" in data.columns.get_level_values(0):
                c = data["Close"]
                for s in ns:
                    if s in c.columns and len(c[s].dropna()) > 0:
                        prices[s.replace(".NS", "")] = float(c[s].dropna().iloc[-1])
    except Exception: pass
    for s in symbols:
        clean = s.replace(".NS", "")
        if clean not in prices:
            try:
                h = yf.Ticker(s if ".NS" in s else s + ".NS").history(period="1d", interval="1m")
                if len(h) > 0: prices[clean] = float(h["Close"].iloc[-1])
            except Exception: pass
    return prices


def get_vix():
    try:
        import yfinance as yf
        d = yf.download("^INDIAVIX", period="2d", interval="1d", progress=False)
        if hasattr(d.columns, 'droplevel') and len(d.columns.names) > 1:
            d.columns = d.columns.droplevel(1)
        if len(d) > 0: return float(d["Close"].iloc[-1])
    except Exception: pass
    return 15.0


# ═══════════════════════════ v7 DIRECTION DECISION (Layer 1 gate + Layer 2 flip) ═══════════════════════════
# This is the ONLY thing v7_regime changes vs v5: how a candidate's side is decided.
# v5 trusted the signal-engine BUY/SELL label; v7 re-decides it from the daily regime
# gate (allowed_side) constrained Supertrend flip, plus an intraday green/red guard.
# Spec: docs/research/2026-06-08_long-short-flip-spec.md (line 61 — "never short a
# stock green/above VWAP"). Daily bars come from prototype/data/<SYMBOL>_NS.csv, the
# same per-symbol daily source the v5 stack already ships (yfinance-format CSVs).

# Per-symbol daily OHLC CSVs (Date,Adj Close,Close,High,Low,Open,Volume), chronological.
V7_DAILY_DATA_DIR = PROJECT_ROOT / "prototype" / "data"
_v7_daily_cache = {}


def _v7_load_daily(symbol):
    """Load a symbol's chronological daily OHLC DataFrame (High/Low/Close) or None.
    Reuses the same prototype/data/<SYMBOL>_NS.csv source the v5 regime stack uses."""
    clean = symbol.replace(".NS", "")
    if clean in _v7_daily_cache:
        return _v7_daily_cache[clean]
    import pandas as pd
    path = V7_DAILY_DATA_DIR / f"{clean}_NS.csv"
    df = None
    if path.exists():
        try:
            d = pd.read_csv(path, parse_dates=["Date"])
            d = d.sort_values("Date").reset_index(drop=True)
            d = d.dropna(subset=["High", "Low", "Close"])
            if len(d) >= 55:  # allowed_side needs sma_period(50)+slope_lookback(5)
                df = d
        except Exception:
            df = None
    _v7_daily_cache[clean] = df
    return df


# Minimum 5-min candles before intraday Supertrend is trustworthy. ~3 bars after
# open we'd have noise; require ~15 (≈75 min) so the ATR(10) band has settled.
V7_INTRADAY_MIN_BARS = 15


def _v7_load_intraday(symbol):
    """Fetch today's 5-min OHLC candles (High/Low/Close) for Layer-2 Supertrend.

    Reuses prototype/v4/data_nse.get_intraday_candles (yfinance period=1d,
    interval=5m). NOT cached — must refresh every scan so the flip can react
    intraday. Returns a DataFrame or None when data is missing/too thin (caller
    then falls back to daily bars, so the engine never does worse than before).
    """
    get_candles = _mods.get("intraday_candles")
    if get_candles is None:
        return None
    try:
        df = get_candles(symbol.replace(".NS", ""), "5m")
    except Exception as e:
        log(f"  [v7] {symbol}: intraday fetch failed ({e}) -> daily fallback")
        return None
    if df is None or len(df) < V7_INTRADAY_MIN_BARS:
        return None
    if not {"High", "Low", "Close"}.issubset(df.columns):
        return None
    return df.dropna(subset=["High", "Low", "Close"])


def _v7_direction_for(symbol, change_pct=0.0):
    """Decide LONG / SHORT / FLAT for a symbol using the v7 two-layer logic.

    Layer 1: allowed_side(DAILY) -> LONG_ONLY/SHORT_ONLY/BOTH/FLAT (swing regime permission)
    Layer 2: flip_states(supertrend(INTRADAY 5m), [allowed]*n)[-1] -> LONG/SHORT/FLAT
             (falls back to daily bars when intraday is missing/thin, e.g. early session)
    Intraday guard: never SHORT a green-on-day stock, never LONG a red-on-day stock.

    Returns "LONG", "SHORT" or "FLAT". Missing/short daily data => FLAT (safe).
    """
    allowed_side = _mods.get("allowed_side")
    supertrend = _mods.get("supertrend")
    flip_states = _mods.get("flip_states")
    if not (allowed_side and supertrend and flip_states):
        return "FLAT"
    daily = _v7_load_daily(symbol)
    if daily is None:
        return "FLAT"
    try:
        allowed = allowed_side(daily)
        # Layer 2 flips on intraday 5-min bars; daily is the graceful fallback so
        # the flip is genuinely intraday whenever live candles are available.
        bars = _v7_load_intraday(symbol)
        src = "5m"
        if bars is None:
            bars, src = daily, "daily"
        states = supertrend(bars["High"], bars["Low"], bars["Close"])
        position = flip_states(list(states), [allowed] * len(states))[-1]
        log(f"  [v7] {symbol}: allowed={allowed} src={src} -> {position}")
    except Exception as e:
        log(f"  [v7] {symbol}: direction calc failed ({e}) -> FLAT")
        return "FLAT"
    # Intraday guard (spec line 61): don't short a riser / long a faller on the day.
    try:
        chg = float(change_pct or 0.0)
    except (TypeError, ValueError):
        chg = 0.0
    if position == "SHORT" and chg > 0:
        return "FLAT"
    if position == "LONG" and chg < 0:
        return "FLAT"
    return position


# ═══════════════════════════ STATE ═══════════════════════════

MULTI_DAY_POOLS = {"SWING", "POSITIONAL", "INVESTMENT"}
ACTIVE_POS_FILE = TRADE_DIR / "positions_active.json"
CARRY_FORWARD_FILE = TRADE_DIR / "carry_forward_v7_regime.json"


def _get_carry_forward_balance():
    """Load previous day's closing balance."""
    if CARRY_FORWARD_FILE.exists():
        try:
            cf = json.load(open(CARRY_FORWARD_FILE))
            bal = cf.get("closing_balance", TOTAL_CAPITAL)
            log(f"  CARRY FORWARD: Rs {bal:,.0f} from {cf.get('date', '?')}")
            return bal
        except Exception:
            pass
    return TOTAL_CAPITAL


def _save_carry_forward_v5(state):
    """Save today's closing balance for tomorrow."""
    pnl = state.get("summary", {}).get("total_pnl", 0)
    closing = TOTAL_CAPITAL + pnl  # Use starting capital + cumulative pnl
    # Check if we have carry forward from before
    if CARRY_FORWARD_FILE.exists():
        try:
            prev = json.load(open(CARRY_FORWARD_FILE))
            prev_bal = prev.get("closing_balance", TOTAL_CAPITAL)
            closing = prev_bal + pnl  # Previous balance + today's P&L
        except Exception:
            pass
    cf = {
        "date": state.get("date"),
        "closing_balance": round(closing, 2),
        "todays_pnl": round(pnl, 2),
        "cumulative_pnl": round(closing - TOTAL_CAPITAL, 2),
        "starting_capital": TOTAL_CAPITAL,
    }
    with open(CARRY_FORWARD_FILE, "w") as f:
        json.dump(cf, f, indent=2)
    log(f"  Balance carried forward: Rs {closing:,.0f}")
SWING_WARN_DAYS, SWING_REVIEW_DAYS = 7, 10
POSITIONAL_WARN_DAYS = 30

def _state_file():
    return TRADE_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"

def fresh_state(capital=None):
    cap = capital or TOTAL_CAPITAL
    return {"date": datetime.now().strftime("%Y-%m-%d"), "engine": "v7_regime",
            "started_at": datetime.now().strftime("%H:%M:%S"),
            "total_capital": cap, "regime": "SIDEWAYS",
            "premarket": {}, "risk_state": {},
            "pools": {n: {"positions": [], "closed": [], "pnl": 0} for n in POOL_NAMES},
            "summary": {"total_pnl": 0, "trades": 0, "wins": 0, "losses": 0,
                        "longs": 0, "shorts": 0, "scan_count": 0, "rescore_count": 0},
            "last_rescore_time": None, "last_signals": []}

def _load_active_positions():
    """Load multi-day positions from persistent file."""
    if ACTIVE_POS_FILE.exists():
        try:
            data = json.loads(ACTIVE_POS_FILE.read_text())
            return data.get("positions", {})
        except (json.JSONDecodeError, KeyError):
            pass
    return {}

def _save_active_positions(state):
    """Save all non-INTRADAY open positions to persistent file."""
    positions = {}
    for pool_name in MULTI_DAY_POOLS:
        pd = state["pools"].get(pool_name, {})
        pos_list = pd.get("positions", [])
        if pos_list:
            positions[pool_name] = pos_list
    data = {
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "positions": positions,
    }
    atomic_write_json(ACTIVE_POS_FILE, data)

def _check_position_aging(state):
    """Warn about positions held too long."""
    today = datetime.now().strftime("%Y-%m-%d")
    for pool_name in MULTI_DAY_POOLS:
        for pos in state["pools"].get(pool_name, {}).get("positions", []):
            entry_date = pos.get("entry_date", today)
            try:
                days_held = (datetime.strptime(today, "%Y-%m-%d") -
                             datetime.strptime(entry_date, "%Y-%m-%d")).days
            except ValueError:
                continue
            pos["days_held"] = days_held
            if pool_name == "SWING":
                if days_held >= SWING_REVIEW_DAYS:
                    log(f"  [AGING] {pos['symbol']} SWING held {days_held}d -- AUTO-REVIEW needed")
                elif days_held >= SWING_WARN_DAYS:
                    log(f"  [AGING] {pos['symbol']} SWING held {days_held}d -- approaching limit")
            elif pool_name == "POSITIONAL" and days_held >= POSITIONAL_WARN_DAYS:
                log(f"  [AGING] {pos['symbol']} POSITIONAL held {days_held}d -- review recommended")

def load_state():
    today = datetime.now().strftime("%Y-%m-%d")
    f = _state_file()
    if f.exists():
        s = json.loads(f.read_text())
        if s.get("date") == today:
            return s
        log("  NEW DAY -- resetting INTRADAY, keeping multi-day positions")
    # Fresh daily state with carried-forward balance
    balance = _get_carry_forward_balance()
    s = fresh_state(capital=balance)
    # Restore multi-day positions from persistent file
    active = _load_active_positions()
    restored = 0
    for pool_name in MULTI_DAY_POOLS:
        positions = active.get(pool_name, [])
        if positions:
            s["pools"][pool_name]["positions"] = positions
            restored += len(positions)
            log(f"  Restored {len(positions)} {pool_name} positions from positions_active.json")
    if restored:
        log(f"  Total restored: {restored} multi-day positions")
    return s

def save_state(s):
    atomic_write_json(_state_file(), s)
    # Always persist multi-day positions separately
    _save_active_positions(s)


# ═══════════════════════════ MANAGERS ═══════════════════════════

def init_managers(state):
    pm = rm = None
    regime = state.get("regime", "SIDEWAYS")
    PoolManager = _mods.get("pools")
    RiskManager = _mods.get("risk")
    if PoolManager:
        pm = PoolManager(total_capital=TOTAL_CAPITAL)
        pm.set_regime(regime)
        # Re-register restored multi-day positions into PoolManager
        for pool_name in MULTI_DAY_POOLS:
            for pos in state["pools"].get(pool_name, {}).get("positions", []):
                try:
                    pm.deploy(pool_name, pos["symbol"], pos["qty"],
                              pos["entry_price"], pos["sl_price"], pos["target_price"])
                except Exception as e:
                    log(f"  [WARN] Failed to re-register {pos['symbol']} in {pool_name}: {e}")
    if RiskManager and pm:
        rm = RiskManager(pm, regime=regime, vix=get_vix())
        rm.reset_daily()  # Clear daily counters (multi-day positions are still tracked)
    return pm, rm


# ═══════════════════════════ PRE-MARKET ═══════════════════════════

def run_premarket(state):
    log(f"\n{'='*65}\n  v5 PRE-MARKET PHASE\n{'='*65}")
    premarket, regime_data = {}, {}
    get_premarket_intel = _mods.get("premarket")
    detect_regime = _mods.get("regime")
    if get_premarket_intel:
        try:
            premarket = get_premarket_intel()
            o = premarket.get("overall", {}); g = premarket.get("gap_prediction", {})
            log(f"  Pre-market: bias={o.get('bias','?')} gap={g.get('direction','?')} "
                f"{g.get('magnitude_pct',0):+.2f}% size={o.get('size_multiplier',1.0):.1f}x")
        except Exception as e: log(f"  Pre-market failed: {e}")
    state["premarket"] = premarket
    if detect_regime:
        try:
            regime_data = detect_regime()
            old_regime = state.get("regime", "SIDEWAYS")
            state["regime"] = regime_data.get("regime", "SIDEWAYS")
            log(f"  Regime: {state['regime']} (score={regime_data.get('score',0)}, "
                f"alloc={regime_data.get('allocation',0.75):.0%})")
            if old_regime != state["regime"]:
                _tg_alert(f"*REGIME CHANGE*\n{old_regime} -> {state['regime']}\nScore: {regime_data.get('score',0)}\nAllocation: {regime_data.get('allocation',0.75):.0%}")
        except Exception as e:
            log(f"  Regime failed: {e}"); state["regime"] = "SIDEWAYS"
    vix = get_vix()
    log(f"  VIX: {vix:.1f}")
    return regime_data, premarket, vix


# ═══════════════════════════ TELEGRAM ═══════════════════════════

def _tg_alert(msg):
    """Send Telegram alert (non-blocking, ignore failures)."""
    try:
        from prototype.v5.telegram_bot import send_alert
        send_alert(msg)
    except Exception:
        pass

# 2026-04-28: per-trade Telegram alerts silenced by default to reduce noise.
# Set TELEGRAM_TRADE_NOISE=1 to re-enable (was firing ~400 messages/day across 4 engines).
# Critical alerts (_tg_alert) for regime change, alpha hunter, daily summary, crash watchdog
# remain unaffected. Digest still sends every 2 hours via telegram-digest.sh.
TELEGRAM_TRADE_NOISE = os.environ.get("TELEGRAM_TRADE_NOISE", "0") == "1"

def _tg_entry(trade):
    if not TELEGRAM_TRADE_NOISE:
        return
    try:
        from prototype.v5.telegram_bot import alert_entry
        alert_entry(trade)
    except Exception:
        pass

def _tg_exit(trade):
    if not TELEGRAM_TRADE_NOISE:
        return
    try:
        from prototype.v5.telegram_bot import alert_exit
        alert_exit(trade)
    except Exception:
        pass


# ═══════════════════════════ DEPLOY ═══════════════════════════

def deploy_signals(state, pm, rm, signals):
    if not pm or not signals: return 0
    held = {pos["symbol"] for pd in state["pools"].values() for pos in pd["positions"]}
    count = 0
    rust_validated = 0

    # Try to connect to Rust engine for validation
    try:
        from prototype.v5.rust_bridge import validate_signal_via_rust, sync_positions_from_state
        rust_available = True
        # Sync Rust's position count with ours BEFORE deploying — prevents drift lockout
        if sync_positions_from_state(state):
            log("  [rust-sync] drift corrected")
    except ImportError:
        rust_available = False

    # ═══ v7 DIRECTION SWAP (Layer 1 gate + Layer 2 flip) ═══
    # The single behavioural difference vs v5: re-decide each candidate's side from
    # the daily regime gate + Supertrend flip instead of trusting the signal-engine
    # BUY/SELL label. FLAT collapses the candidate out of deployment AND closes any
    # open position for that symbol (via v5's existing close path). Everything below
    # this block — sizing, pools, SL/target, cost model, risk guards — is v5 verbatim.
    v7_signals = []
    for sig in signals:
        sym = sig["symbol"]
        v7_pos = _v7_direction_for(sym, sig.get("change_pct", 0.0))
        if v7_pos == "FLAT":
            # Close any existing position for this symbol — the regime no longer permits it.
            for pn, pd in state["pools"].items():
                for pos in list(pd["positions"]):
                    if pos["symbol"] == sym:
                        px = get_prices_batch([sym])
                        if sym in px:
                            close_position(state, pm, rm, pn, pos, px[sym], "REGIME_FLAT")
                        else:
                            log(f"  [v7] {sym}: FLAT but no price to close on")
            continue  # no entry on a FLAT side
        # Rewrite the candidate's direction to the v7 decision; downstream v5 logic
        # keys off sig["direction"] (BUY/SELL) and sig["position_type"] (LONG/SHORT).
        new_dir = "BUY" if v7_pos == "LONG" else "SELL"
        if new_dir != sig.get("direction") or v7_pos != sig.get("position_type"):
            log(f"  [v7] {sym}: {sig.get('position_type','?')}/{sig.get('direction','?')} -> {v7_pos}")
        s2 = dict(sig)
        s2["direction"] = new_dir
        s2["position_type"] = v7_pos
        # When flipping a long candidate into a short (or vice-versa), the entry/SL/target
        # levels v5 computed for the original side no longer apply. Drop them so the
        # downstream deploy block falls back to its own direction-aware defaults.
        if v7_pos != sig.get("position_type"):
            for k in ("entry_price", "sl_price", "target_price"):
                s2.pop(k, None)
            # keep a price hint for sizing/SL defaults
            s2.setdefault("price", sig.get("price", sig.get("entry_price", 0)))
        v7_signals.append(s2)
    signals = v7_signals
    if not signals:
        log("  [v7] no candidates survived the regime gate / flip")
        return 0

    # Task 1.1 — BULLISH_PREMARKET_SHORT_BLOCK (added 2026-04-28)
    # When premarket bias is BULLISH and gap up > threshold, suppress all SELL/SHORT
    # signals for the first N min after market open. On 04-27 this would have blocked
    # all 36 SHORTs that bled into the rising tape.
    if _short_block_active(state):
        allowed_dirs = ("BUY",)
        log(f"  [SHORT_BLOCK] Bullish premarket + gap-up > {SHORT_BLOCK_GAP_PCT}% — "
            f"suppressing SELL signals for first {SHORT_BLOCK_WINDOW_MIN} min")
    else:
        allowed_dirs = ("BUY", "SELL")

    # #3 FIX: rank by score desc so the max-20 cap fills with highest-conviction picks, not FCFS.
    for sig in sorted([s for s in signals if s["direction"] in allowed_dirs],
                      key=lambda s: -float(s.get("score", 0))):
        sym, pool_name = sig["symbol"], sig.get("pool", "INTRADAY")
        if pool_name not in state["pools"] or pool_name == "NONE":
            continue
        # Task 1.2 — WINNER_RE_ARM (added 2026-04-28)
        # If symbol is already held, normally we skip. With re-arm: same-direction
        # re-entry is allowed if a TARGET hit consumed the original (up to 3 per stock per day).
        already_held = sym in held
        rearm_ok = consume_rearm(state, sym, sig["direction"]) if already_held else False
        if already_held and not rearm_ok:
            continue
        if rearm_ok:
            log(f"  [RE-ARM] {sym}: deploying re-entry on {sig['direction']}")
        # #1 FIX: pass position_type so the slot-partition cap can fire per-direction
        _pt = sig.get("position_type", "LONG" if sig["direction"] == "BUY" else "SHORT")
        if rm:
            ok, reason = rm.check_can_trade(pool_name, sym, _pt)
            if not ok: log(f"  {sym}: BLOCKED ({reason})"); continue
        pool = pm.pools.get(pool_name)
        if not pool: continue
        budget = pm.get_pool_budget(pool_name)
        if budget < 10000: continue
        price = sig.get("entry_price", sig.get("price", 0))
        base = budget * 0.15

        sized = rm.get_position_size(pool_name, base) if rm else base

        qty = safe_qty(budget, price, sized=sized)

        if qty is None: continue
        cost = qty * price
        # #2 FIX: widen default SL on strong-gap mornings (|gap|>0.5%) — v5 was stopped out of CIPLA/DRREDDY right before they rallied on 04-24
        _gap = abs(float(state.get("premarket", {}).get("gap_prediction", {}).get("magnitude_pct", 0) or 0))
        _sl_pct = 0.0225 if _gap > 0.5 else 0.015
        sl = sig.get("sl_price", price * ((1 - _sl_pct) if sig["direction"] == "BUY" else (1 + _sl_pct)))
        tgt = sig.get("target_price", price * (1.02 if sig["direction"] == "BUY" else 0.98))
        pos_type = sig.get("position_type", "LONG" if sig["direction"] == "BUY" else "SHORT")
        if is_reentry_blocked(state, sym, pos_type):  # learning 2026-04-17_003: 2-SL same-day block
            log(f"  {sym}: BLOCKED (reentry cap: 2 SL in {pos_type} today)")
            continue

        # ═══ RUST ENGINE VALIDATION ═══
        # If Rust engine is running, validate through it first.
        # Rust catches: missing SL, SL direction errors, daily loss limits,
        # order size limits, position limits, time restrictions.
        # If Rust is offline, fall back to Python-only (current behavior).
        if rust_available:
            rust_sig = {**sig, "qty": qty, "sl_price": sl, "target_price": tgt,
                        "entry_price": price, "pool": pool_name}
            rust_ok, rust_msg = validate_signal_via_rust(rust_sig)
            if rust_ok is False:
                log(f"  {sym}: RUST REJECTED ({rust_msg})")
                continue
            elif rust_ok is True:
                rust_validated += 1
            # rust_ok is None = Rust offline, proceed with Python-only

        if not pm.deploy(pool_name, sym, qty, price, sl, tgt): continue
        state["pools"][pool_name]["positions"].append({
            "symbol": sym, "entry_price": round(price, 2), "qty": qty,
            "cost": round(cost, 2), "entry_time": datetime.now().strftime("%H:%M:%S"),
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "sl_price": round(sl, 2), "target_price": round(tgt, 2),
            "position_type": pos_type, "pool": pool_name,
            "trailing_activated": False, "peak_price": round(price, 2),
            "trough_price": round(price, 2), "score": sig.get("score", 0),
            "direction": sig["direction"], "reasons": sig.get("reasons", [])})
        held.add(sym); count += 1
        tag = "SHORT" if pos_type == "SHORT" else "LONG "
        log(f"  {tag} {sym:>12} x{qty:<4d} @{price:.2f} SL:{sl:.2f} TGT:{tgt:.2f} [{pool_name}]")
        _tg_entry({"symbol": sym, "direction": sig["direction"], "position_type": pos_type,
                    "entry_price": price, "sl_price": sl, "target_price": tgt,
                    "qty": qty, "pool": pool_name, "score": sig.get("score", 0),
                    "regime": state.get("regime", "?")})
    if count:
        rust_note = f" ({rust_validated} Rust-validated)" if rust_validated else " (Python-only mode)"
        log(f"  Deployed {count} positions{rust_note}")
    return count


# ═══════════════════════════ CLOSE ═══════════════════════════

def close_position(state, pm, rm, pool_name, pos, exit_price, reason):
    sym, is_short = pos["symbol"], pos.get("position_type") == "SHORT"
    if is_short:
        pnl = (pos["entry_price"] - exit_price) * pos["qty"]
        pnl_pct = (pos["entry_price"] - exit_price) / pos["entry_price"] * 100
    else:
        pnl = (exit_price - pos["entry_price"]) * pos["qty"]
        pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
    # Task 1.4: realistic Indian retail cost. pnl_gross stays as the reported number
    # for backwards compat with prior reports; pnl_net + cost added as new fields.
    cost = cost_for_trade(pos["qty"], pos["entry_price"], exit_price)
    pnl_gross = pnl
    pnl_net = pnl - cost
    if pm: pm.close_position(pool_name, sym, exit_price, reason)
    if rm: rm.record_trade_result(pool_name, sym, pnl)
    # Sprint 1 — Execution Analyst slippage hook. Failure is non-blocking:
    # any exception in the slippage helper must NOT impact trade close.
    try:
        from scripts.team.slippage import record_slippage
        record_slippage(
            engine="v7_regime", symbol=sym,
            direction="SELL" if is_short else "BUY",
            expected_price=pos.get("target_price") or exit_price,
            fill_price=exit_price,
            quantity=pos["qty"], side="exit",
            trade_id=f"v7_regime-{sym}-{pos.get('entry_time','?')}",
            extra={"reason": reason, "pnl_net": pnl_net})
    except Exception:
        pass
    if reason == "STOPLOSS":  # learning 2026-04-17_003: track SL for same-day reentry block
        record_reentry_sl(state, sym, pos.get("position_type", "LONG"))
    # Task 1.2: WINNER_RE_ARM — only on TARGET exits, never STOPLOSS / TIME_EXIT / FLAT_FORCE_EXIT
    if reason == "TARGET":
        direction = "SELL" if is_short else "BUY"
        slot = mark_rearmable(state, sym, direction)
        log(f"  {sym}: TARGET hit — re-armable for {direction} ({slot['remaining']}/{WINNER_REARM_MAX} slots remaining)")
    state["pools"][pool_name]["closed"].append({
        "symbol": sym, "entry_price": pos["entry_price"], "exit_price": round(exit_price, 2),
        "qty": pos["qty"], "entry_time": pos["entry_time"],
        "exit_time": datetime.now().strftime("%H:%M:%S"),
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "reason": reason,
        "pnl_gross": round(pnl_gross, 2), "pnl_net": round(pnl_net, 2), "cost": round(cost, 2),
        "position_type": pos.get("position_type", "LONG"), "pool": pool_name})
    state["pools"][pool_name]["pnl"] += pnl
    state["pools"][pool_name]["positions"] = [
        p for p in state["pools"][pool_name]["positions"] if p["symbol"] != sym]
    s = state["summary"]
    s["total_pnl"] += pnl; s["trades"] += 1
    s["total_pnl_net"] = s.get("total_pnl_net", 0) + pnl_net
    s["total_cost"]    = s.get("total_cost", 0) + cost
    s["wins" if pnl > 0 else "losses"] += 1
    s["shorts" if is_short else "longs"] = s.get("shorts" if is_short else "longs", 0) + 1
    tag = ("WIN" if pnl > 0 else "LOSS") + f" {'SHORT' if is_short else 'LONG'}"
    log(f"  >> {tag} {sym} x{pos['qty']} @{exit_price:.2f} ({reason}) "
        f"P&L: Rs {pnl:+,.0f} ({pnl_pct:+.2f}%) net Rs {pnl_net:+,.0f} cost Rs {cost:.0f} [{pool_name}]")
    _tg_exit({"symbol": sym, "pnl": pnl, "pnl_pct": pnl_pct, "reason": reason,
              "entry_price": pos["entry_price"], "exit_price": exit_price,
              "position_type": pos.get("position_type", "LONG"), "pool": pool_name,
              "qty": pos["qty"]})


# ═══════════════════════════ SCAN ═══════════════════════════

def scan_positions(state, pm, rm):
    state["summary"]["scan_count"] += 1
    all_pos = [(pn, p) for pn, pd in state["pools"].items() for p in pd["positions"]]
    if not all_pos: log("  No open positions"); return
    prices = get_prices_batch(list({p["symbol"] for _, p in all_pos}))
    unrealized, to_close = 0, []
    log(f"\n{'='*65}\n  SCAN #{state['summary']['scan_count']} | {len(all_pos)} positions\n{'='*65}")
    flat_window_active = _in_flat_exit_window()
    for pool_name, pos in all_pos:
        sym, entry = pos["symbol"], pos["entry_price"]
        if sym not in prices: log(f"  {sym}: no price"); continue
        px = prices[sym]
        is_short = pos.get("position_type") == "SHORT"
        if is_short:
            pnl_rs = (entry - px) * pos["qty"]; pnl_pct = (entry - px) / entry * 100
            if px < pos.get("trough_price", entry): pos["trough_price"] = round(px, 2)
        else:
            pnl_rs = (px - entry) * pos["qty"]; pnl_pct = (px - entry) / entry * 100
            if px > pos.get("peak_price", entry): pos["peak_price"] = round(px, 2)
        unrealized += pnl_rs
        reason = None
        # Task 1.3 — TIME_EXIT_TIGHTENING (added 2026-04-28)
        # In the post-lunch window, force-exit any flat position (|pnl_pct| < 0.3%)
        # to free the slot for fresher signals.
        if flat_window_active and abs(pnl_pct) < FLAT_EXIT_THRESHOLD_PCT:
            reason = "FLAT_FORCE_EXIT"
            log(f"  {sym}: FLAT_FORCE_EXIT @ {px:.2f} (pnl_pct={pnl_pct:+.2f}%)")
            to_close.append((pool_name, pos, px, reason)); continue
        if is_short:
            if px >= pos["sl_price"]: reason = "STOPLOSS"
            elif px <= pos["target_price"]: reason = "TARGET"
            elif pnl_pct >= TRAILING_TRIGGER_PCT:
                if not pos.get("trailing_activated"):
                    pos["trailing_activated"] = True; pos["sl_price"] = entry
                    log(f"  {sym}: SHORT TRAILING -> SL@{entry:.2f}")
                else:
                    trail = round(pos["trough_price"] * (1 + TRAILING_STEP_PCT / 100), 2)
                    if trail < pos["sl_price"]: pos["sl_price"] = trail
        else:
            if px <= pos["sl_price"]: reason = "STOPLOSS"
            elif px >= pos["target_price"]: reason = "TARGET"
            elif pnl_pct >= TRAILING_TRIGGER_PCT:
                if not pos.get("trailing_activated"):
                    pos["trailing_activated"] = True; pos["sl_price"] = entry
                    log(f"  {sym}: LONG TRAILING -> SL@{entry:.2f}")
                else:
                    trail = round(pos["peak_price"] * (1 - TRAILING_STEP_PCT / 100), 2)
                    if trail > pos["sl_price"]: pos["sl_price"] = trail
        if reason: to_close.append((pool_name, pos, px, reason))
        else:
            t = " [T]" if pos.get("trailing_activated") else ""
            tag = "S" if is_short else "L"
            log(f"  {tag} {sym:>12} {px:>8.2f} {pnl_pct:+5.2f}% {pnl_rs:+8,.0f} "
                f"SL:{pos['sl_price']:.2f} TGT:{pos['target_price']:.2f}{t}")
    for args in to_close: close_position(state, pm, rm, *args)
    if rm:
        for k, v in rm.check_all_breakers().items(): log(f"  ** RISK [{k}]: {v}")
    log(f"\n  Realized: {_fmt(state['summary']['total_pnl'])} | Unrealized: {_fmt(unrealized)}")


# ═══════════════════════════ RESCORE ═══════════════════════════

def _held_for_min(pos, min_minutes):
    """#5 helper: return True when position held LESS than min_minutes (i.e., exit should be suppressed)."""
    try:
        et = datetime.strptime(pos.get("entry_time", ""), "%H:%M:%S").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        return (datetime.now() - et).total_seconds() < min_minutes * 60
    except (ValueError, TypeError):
        return False  # if we can't tell, allow normal exit


def _should_rescore(state):
    last = state.get("last_rescore_time")
    if not last: return True
    try:
        t = datetime.strptime(last, "%H:%M:%S").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        return (datetime.now() - t).total_seconds() >= RESCORE_INTERVAL_MIN * 60
    except Exception: return True

def rescore_and_redeploy(state, pm, rm):
    generate_signals = _mods.get("signals")
    if not _should_rescore(state) or not generate_signals: return
    state["summary"]["rescore_count"] += 1
    state["last_rescore_time"] = datetime.now().strftime("%H:%M:%S")
    log(f"\n  RESCORE #{state['summary']['rescore_count']}")
    try: new_sigs = generate_signals(state.get("regime", "SIDEWAYS"))
    except Exception as e: log(f"  Rescore failed: {e}"); return
    new_map = {s["symbol"]: s for s in new_sigs}
    state["last_signals"] = new_sigs
    for pn, pd in state["pools"].items():
        for pos in list(pd["positions"]):
            sym, is_short = pos["symbol"], pos.get("position_type") == "SHORT"
            nd = new_map.get(sym, {}).get("direction", "HOLD")
            exit_it = (not is_short and nd in ("SELL", "HOLD")) or (is_short and nd == "BUY")
            # #5 FIX: 60-min minimum hold before SIGNAL_FLIP — prevents rescore whipsaw
            if exit_it and _held_for_min(pos, 60):
                log(f"  {sym}: flip suppressed (held <60min since {pos.get('entry_time','?')})")
                exit_it = False
            if exit_it:
                log(f"  {sym}: flipped to {nd} -> exit {'SHORT' if is_short else 'LONG'}")
                px = get_prices_batch([sym])
                if sym in px: close_position(state, pm, rm, pn, pos, px[sym], "SIGNAL_FLIP")
    deploy_signals(state, pm, rm, new_sigs)


# ═══════════════════════════ FORCE CLOSE ═══════════════════════════

def force_close_intraday(state, pm, rm):
    positions = state["pools"].get("INTRADAY", {}).get("positions", [])
    if not positions: log("  No intraday positions to close"); return
    log(f"\n  FORCE CLOSING {len(positions)} INTRADAY positions")
    prices = get_prices_batch([p["symbol"] for p in positions])
    for pos in list(positions):
        close_position(state, pm, rm, "INTRADAY", pos,
                       prices.get(pos["symbol"], pos["entry_price"]), "TIME_EXIT")
    # Persist multi-day positions that survive overnight
    multi_day_count = sum(len(state["pools"].get(p, {}).get("positions", [])) for p in MULTI_DAY_POOLS)
    if multi_day_count:
        _save_active_positions(state)
        log(f"  Saved {multi_day_count} multi-day positions to positions_active.json")


# ═══════════════════════════ DISPLAY ═══════════════════════════

def print_status(state):
    regime = state.get("regime", "?")
    gap = state.get("premarket", {}).get("gap_prediction", {})
    vix, s = get_vix(), state.get("summary", {})
    C = {"BULL": "\033[92m", "BEAR": "\033[91m", "SIDEWAYS": "\033[93m"}
    R = "\033[0m"
    print(f"\n{'='*65}")
    print(f"  v5 PAPER TRADING  |  {state.get('date','today')}  |  Capital: {_fmt(TOTAL_CAPITAL)}")
    print(f"  Regime: {C.get(regime,'')}{regime}{R}  |  VIX: {vix:.1f}  |  "
          f"Gap: {gap.get('direction','?')} {gap.get('magnitude_pct',0):+.2f}%")
    print(f"{'='*65}")
    total_open = 0
    for pn in POOL_NAMES:
        pd = state["pools"].get(pn, {}); pos = pd.get("positions", [])
        if not pos and not pd.get("closed"): continue
        longs = [p for p in pos if p.get("position_type") != "SHORT"]
        shorts = [p for p in pos if p.get("position_type") == "SHORT"]
        total_open += len(pos)
        cnt = f"{len(pos)} pos" + (f", {len(longs)}L/{len(shorts)}S" if longs and shorts else "")
        print(f"\n  {pn} ({cnt}) | P&L: {_fmt(pd.get('pnl', 0))}")
        for p in pos:
            tag = "SHORT" if p.get("position_type") == "SHORT" else "LONG "
            t = " [T]" if p.get("trailing_activated") else ""
            age = f" D{p['days_held']}" if p.get("days_held") else ""
            edate = f" ({p['entry_date']})" if p.get("entry_date") and pn in MULTI_DAY_POOLS else ""
            print(f"    {tag} {p['symbol']:>12} x{p['qty']:<4d} @{p['entry_price']:.2f} "
                  f"SL:{p['sl_price']:.2f} TGT:{p['target_price']:.2f}{t}{age}{edate}")
    all_cl = [t for pd in state["pools"].values() for t in pd.get("closed", [])]
    if all_cl:
        w = sum(1 for t in all_cl if t["pnl"] > 0)
        print(f"\n  CLOSED: {len(all_cl)} trades ({w}W/{len(all_cl)-w}L) | {_fmt(s.get('total_pnl',0))}")
    elif not total_open: print("\n  No trades yet")
    # Rust engine status
    try:
        from prototype.v5.rust_bridge import check_rust_risk
        rust = check_rust_risk()
        if rust:
            killed = " ** KILLED **" if rust.get("killed") else ""
            print(f"\n  RUST ENGINE: Online | Daily P&L: Rs {rust.get('daily_pnl','0')} | "
                  f"Positions: {rust.get('positions_count',0)} | Deploy: {rust.get('deployment_pct','0')}%{killed}")
        else:
            print(f"\n  RUST ENGINE: Offline (Python-only mode)")
    except Exception:
        print(f"\n  RUST ENGINE: Not configured")
    print(f"{'='*65}")

def print_summary(state):
    s = state.get("summary", {}); pnl = s.get("total_pnl", 0)
    tr = s.get("trades", 0); w = s.get("wins", 0)
    print(f"\nv5 | {state.get('date','today')} | {_fmt(TOTAL_CAPITAL)} | Regime: {state.get('regime','?')}")
    print(f"P&L: {_fmt(pnl)} ({pnl/TOTAL_CAPITAL*100:+.2f}%)")
    if tr: print(f"Trades: {tr} | Wins: {w} ({w/tr*100:.0f}%) | L:{s.get('longs',0)} S:{s.get('shorts',0)}")
    for pn in POOL_NAMES:
        pd = state["pools"].get(pn, {}); cl = pd.get("closed", [])
        if cl or pd.get("positions"):
            print(f"  {pn}: {len(cl)}cl {len(pd.get('positions',[]))}op | {_fmt(pd.get('pnl',0))}")


# ═══════════════════════════ EOD ═══════════════════════════

def generate_report(state):
    today = datetime.now().strftime("%Y-%m-%d")
    path = TRADE_DIR / f"{today}_report.md"
    all_cl = [t for pd in state["pools"].values() for t in pd.get("closed", [])]
    s = state.get("summary", {}); pp = s.get("total_pnl", 0) / TOTAL_CAPITAL * 100
    wins = [t for t in all_cl if t["pnl"] > 0]; wr = len(wins) / len(all_cl) * 100 if all_cl else 0
    lines = [f"# v5 Paper Trading Report -- {today}\n", "## Summary\n", "| Metric | Value |", "|--------|-------|",
             f"| Engine | v5 multi-pool |", f"| Capital | {_fmt(TOTAL_CAPITAL)} |",
             f"| Regime | {state.get('regime','?')} |",
             f"| **Net P&L** | **{_fmt(s.get('total_pnl',0))} ({pp:+.2f}%)** |",
             f"| Trades | {s.get('trades',0)} (L:{s.get('longs',0)} S:{s.get('shorts',0)}) |",
             f"| Win Rate | {wr:.0f}% |", "",
             "## Trades\n", "| # | Type | Pool | Stock | Entry | Exit | P&L | Reason |",
             "|---|------|------|-------|-------|------|-----|--------|"]
    for i, t in enumerate(all_cl, 1):
        lines.append(f"| {i} | {t.get('position_type','LONG')} | {t.get('pool','')} | "
                     f"{t['symbol']} | {t['entry_price']:.2f} | {t['exit_price']:.2f} | "
                     f"Rs {t['pnl']:+,.0f} | {t['reason']} |")
    path.write_text("\n".join(lines)); log(f"  Report: {path}")

def push_to_devpilot(state):
    try:
        import psycopg2
        conn = psycopg2.connect(host="localhost", port=5499, user="devpilot",
                                password="TsUxQvfc7go5TDH8lsIKRTCv", dbname="devpilot")
        s = state.get("summary", {}); today = datetime.now().strftime("%Y-%m-%d")
        pp = s.get("total_pnl", 0) / TOTAL_CAPITAL * 100
        wr = s.get("wins", 0) / max(s.get("trades", 1), 1) * 100
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO learnings (project,category,title,content,source,tags,active,created_at,updated_at) "
            "VALUES (%s,%s,%s,%s,'v7_regime-paper-trade',%s,true,NOW(),NOW())",
            ("tradepilot", "paper-trade",
             f"v7_regime {today}: {_fmt(s.get('total_pnl',0))} ({pp:+.2f}%) | {s.get('trades',0)}t | {wr:.0f}%w",
             json.dumps({"engine": "v7_regime", "capital": TOTAL_CAPITAL, "regime": state.get("regime", "?"),
                         "pnl": s.get("total_pnl", 0), "trades": s.get("trades", 0),
                         "wins": s.get("wins", 0), "longs": s.get("longs", 0), "shorts": s.get("shorts", 0)}),
             ["paper-trade", "v7_regime", today, state.get("regime", "").lower()]))
        conn.commit(); cur.close(); conn.close(); log("  Saved to DevPilot DB")
    except Exception as e: log(f"  DevPilot push failed: {e}")


# ═══════════════════════════ MAIN LOOP ═══════════════════════════

def run():
    check_model_freshness(max_age_days=3)  # learning #005: refuse stale ML
    log(f"{'='*65}\n  v5 ENGINE | {_fmt(TOTAL_CAPITAL)} | Multi-Pool + Short\n"
        f"  Scan {SCAN_INTERVAL_MIN}m | Rescore {RESCORE_INTERVAL_MIN}m | Exit {FORCE_EXIT_HOUR}:{FORCE_EXIT_MIN:02d}\n"
        f"  Pools: INTRADAY(30%) SWING(25%) POSITIONAL(25%) INVESTMENT(15%)\n{'='*65}")
    state = load_state()
    pm, rm = init_managers(state)
    regime_data, premarket, vix = run_premarket(state)
    if pm: pm.set_regime(state["regime"])
    if rm: rm.set_vix(vix); rm.regime = state["regime"]
    _check_position_aging(state)
    total_open = sum(len(pd.get("positions", [])) for pd in state["pools"].values())
    generate_signals = _mods.get("signals")
    if total_open == 0 and generate_signals:
        log("\n--- INITIAL DEPLOYMENT ---")
        try:
            sigs = generate_signals(state.get("regime", "SIDEWAYS"))
            state["last_signals"] = sigs; deploy_signals(state, pm, rm, sigs)
        except Exception as e: log(f"  Signal gen failed: {e}")
    else: log(f"\n  Resuming {total_open} positions")
    save_state(state)
    while True:
        now = datetime.now()
        fe = now.replace(hour=FORCE_EXIT_HOUR, minute=FORCE_EXIT_MIN, second=0)
        if now >= fe:
            force_close_intraday(state, pm, rm); save_state(state); break
        if now >= now.replace(hour=15, minute=30): break
        wait = min(SCAN_INTERVAL_MIN * 60, (fe - now).total_seconds())
        if wait > 0:
            log(f"\n  Next scan in {wait/60:.0f}m..."); time.sleep(wait)
        # Reuse pm/rm — don't reinitialize (that wipes positions!)
        scan_positions(state, pm, rm); rescore_and_redeploy(state, pm, rm)

        # ALPHA HUNTER: at 10:00-10:15 AM, scan for counter-trend winners
        now_h, now_m = datetime.now().hour, datetime.now().minute
        if now_h == 10 and now_m < 15 and not state.get("alpha_hunter_ran"):
            try:
                from prototype.v5.alpha_hunter import generate_alpha_signals
                total_open = sum(len(pd.get("positions", [])) for pd in state["pools"].values())
                total_capital = state.get("total_capital", 1000000)
                deployed_pct = total_open * 10000 / max(total_capital, 1)  # rough estimate
                alpha_sigs = generate_alpha_signals(state.get("regime", "SIDEWAYS"), min(deployed_pct, 0.9))
                if alpha_sigs:
                    log(f"\n  ALPHA HUNTER: {len(alpha_sigs)} counter-trend signals detected!")
                    deploy_signals(state, pm, rm, alpha_sigs)
                    _tg_alert(f"*ALPHA HUNTER*\n{len(alpha_sigs)} counter-trend stocks found!\nSector rotation in: {', '.join(set(s.get('sector','?') for s in alpha_sigs))}")
                state["alpha_hunter_ran"] = True
            except Exception as e:
                log(f"  Alpha Hunter failed: {e}")

        save_state(state)
    log(f"\n{'='*65}\n  END OF DAY\n{'='*65}")
    print_status(state); generate_report(state); push_to_devpilot(state)
    _save_carry_forward_v5(state)
    # Send daily summary via Telegram
    s = state.get("summary", {})
    pnl = s.get("total_pnl", 0)
    _tg_alert(f"*v5 Daily Summary*\n"
              f"P&L: Rs {pnl:+,.0f} ({pnl/max(state.get('total_capital',1000000),1)*100:+.2f}%)\n"
              f"Trades: {s.get('trades',0)} ({s.get('wins',0)}W/{s.get('losses',0)}L)\n"
              f"Longs: {s.get('longs',0)} | Shorts: {s.get('shorts',0)}\n"
              f"Regime: {state.get('regime','?')}")
    if _mods.get("comparator"):
        try:
            log("\n  v4 vs v5 comparison...")
            comp = _mods["comparator"]()
            _mods["comp_print"](comp); _mods["comp_save"](comp)
        except Exception as e: log(f"  Comparator failed: {e}")
    save_state(state)
    s = state.get("summary", {})
    if s.get("trades"):
        log(f"\n  FINAL: {_fmt(s['total_pnl'])} ({s['total_pnl']/TOTAL_CAPITAL*100:+.2f}%) | "
            f"{s['trades']}t (L:{s.get('longs',0)} S:{s.get('shorts',0)}) | {s['wins']}W/{s['losses']}L")


if __name__ == "__main__":
    if "--status" in sys.argv: print_status(load_state())
    elif "--summary" in sys.argv: print_summary(load_state())
    elif "--compare" in sys.argv:
        if _mods.get("comparator"):
            c = _mods["comparator"](); _mods["comp_print"](c); _mods["comp_save"](c)
        else: print("Comparator unavailable")
    elif "--premarket" in sys.argv:
        if _mods.get("premarket"):
            from prototype.v5.premarket_intel import _print_intel
            _print_intel(_mods["premarket"]())
        else: print("Pre-market module unavailable")
    else: run()
