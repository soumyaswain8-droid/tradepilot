#!/usr/bin/env python3
"""
TradePilot v5 Paper Trading Engine
====================================
Multi-pool (Rs 50L), regime-aware, long+short. Runs ALONGSIDE v4 for comparison.
4 pools: INTRADAY(30%) SWING(25%) POSITIONAL(25%) INVESTMENT(15%) + 5% reserve

Usage:
    python3 scripts/v5-paper-trade.py              # Full auto-pilot
    python3 scripts/v5-paper-trade.py --status      # All pools + positions
    python3 scripts/v5-paper-trade.py --summary     # P&L summary
    python3 scripts/v5-paper-trade.py --compare     # Run v4 vs v5 comparator
    python3 scripts/v5-paper-trade.py --premarket   # Show pre-market analysis only
"""
from dp_creds import devpilot_db_password
import json, os, sys, time, warnings, importlib
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
PROJECT_ROOT = Path(__file__).parent.parent
# Engine identity is env-overridable so a shadow (e.g. ENGINE_NAME=v5_noml) can run
# ALONGSIDE live v5 with its own state dir + log for A/B testing. Default = live v5.
ENGINE = os.environ.get("ENGINE_NAME", "v5")
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades" / ENGINE
LOG_DIR = PROJECT_ROOT / "logs"
sys.path.insert(0, str(PROJECT_ROOT / "prototype"))
sys.path.insert(0, str(PROJECT_ROOT))
# Optional composite-weight override for shadow A/B. ML_SCORE_WEIGHT=0 tests removing
# the dead-weight ML (TP-CLN-008: proven selection-neutral, IC=0.006). Mutates the
# shared COMPOSITE_WEIGHTS dict IN PLACE (renormalizing the other 6 factors to sum 1)
# so composite_scorer's binding sees it; affects ONLY this process. No-op if unset.
_ml_w = os.environ.get("ML_SCORE_WEIGHT")
if _ml_w is not None:
    from prototype.v4.config import COMPOSITE_WEIGHTS as _CW
    _t = float(_ml_w); _oth = {k: v for k, v in _CW.items() if k != "ml_score"}
    _s = sum(_oth.values()) or 1.0; _scale = (1.0 - _t) / _s
    for _k in _oth: _CW[_k] = _oth[_k] * _scale
    _CW["ml_score"] = _t
from prototype.utils.signal_guards import safe_qty, atomic_write_json, check_model_freshness, is_reentry_blocked, record_reentry_sl
# Risk Gate (Phase 0, spec 2026-07-20_risk_gate_three_state_verdict.md S5) --
# log-only verdict module. Graceful import: RISK_GATE_LOG wiring below no-ops
# if unavailable, same pattern as the other optional engine modules.
try:
    from prototype.v5.risk_gate import TradePlan, RiskGate, Verdict
except Exception as e:
    TradePlan = RiskGate = Verdict = None
    print(f"[WARN] risk_gate: {e}")
LOG_FILE = LOG_DIR / f"{ENGINE}-paper-trade.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

# Env-overridable so a small-capital shadow can run alongside the fleet without
# touching it (added 2026-08-03). Default is UNCHANGED at Rs 10L, so every
# existing engine and the whole A/B series is unaffected.
TOTAL_CAPITAL = float(os.environ.get("TOTAL_CAPITAL", 1_000_000))  # Rs 10L default
TRAILING_TRIGGER_PCT, TRAILING_STEP_PCT = 1.0, 0.5
SCAN_INTERVAL_MIN = int(os.environ.get("SCAN_INTERVAL_MIN", "10"))
RESCORE_INTERVAL_MIN = int(os.environ.get("RESCORE_INTERVAL_MIN", "30"))
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

# v5_cut: cut any position this far underwater intraday (% loss). 0 = off (default,
# so v5/v5_noml/etc are unchanged). The watchdog-driven "stop holding losers" fix.
WRONGWAY_CUT_PCT = float(os.environ.get("WRONGWAY_CUT_PCT", "0"))

# v8 April-recipe bracket (env-gated, default None/"trailing" so all other engines are unchanged).
# When TARGET_PCT and STOP_PCT are both set, deploy_signals uses a fixed % bracket off entry.
# STOP_MODE="fixed" disables the trailing-stop trigger so the stop stays at the fixed level.
_tp = os.environ.get("TARGET_PCT"); TARGET_PCT = float(_tp) if _tp is not None else None
_sp = os.environ.get("STOP_PCT");   STOP_PCT   = float(_sp) if _sp is not None else None
STOP_MODE = os.environ.get("STOP_MODE", "trailing")


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


def _tape_is_fresh(df, now=None, max_age_min=15):
    """True iff df (a yf 1-min download) has a last bar within max_age_min of now.

    Pure function — no network — so the outage guard is unit-testable
    (tests/test_data_guard.py). Added after 2026-07-08/10: DNS was down from open,
    signals came off cached CSVs, and deploy_signals opened positions the engine
    could never price again (exit=None, Rs 0 audits).
    """
    import pandas as pd
    if df is None or len(df) == 0:
        return False
    try:
        last = df.index[-1]
        ref = now if now is not None else pd.Timestamp.now(tz=getattr(df.index, "tz", None))
        if getattr(last, "tzinfo", None) is None and getattr(ref, "tzinfo", None) is not None:
            ref = ref.tz_localize(None)
        elif getattr(last, "tzinfo", None) is not None and getattr(ref, "tzinfo", None) is None:
            last = last.tz_localize(None)
        return (ref - last) <= pd.Timedelta(minutes=max_age_min)
    except Exception:
        return False


def _live_tape_ok(max_age_min=15):
    """Fetch a 1-min NIFTY bar and check freshness. DATA_GUARD=0 disables (default on)."""
    if os.environ.get("DATA_GUARD", "1") != "1":
        return True
    try:
        import yfinance as yf
        n = yf.download("^NSEI", period="1d", interval="1m", progress=False)
    except Exception:
        return False
    return _tape_is_fresh(n, max_age_min=max_age_min)


def get_vix():
    try:
        import yfinance as yf
        d = yf.download("^INDIAVIX", period="2d", interval="1d", progress=False)
        if hasattr(d.columns, 'droplevel') and len(d.columns.names) > 1:
            d.columns = d.columns.droplevel(1)
        if len(d) > 0: return float(d["Close"].iloc[-1])
    except Exception: pass
    return 15.0


# ═══════════════════════════ STATE ═══════════════════════════

MULTI_DAY_POOLS = {"SWING", "POSITIONAL", "INVESTMENT"}
ACTIVE_POS_FILE = TRADE_DIR / "positions_active.json"
CARRY_FORWARD_FILE = TRADE_DIR / "carry_forward_v5.json"


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
    return {"date": datetime.now().strftime("%Y-%m-%d"), "engine": ENGINE,
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
    """Save open positions that must survive to the next session.

    INTRADAY is included ONLY when MAX_HOLD_DAYS > 0. Without this the carry feature
    would silently lose every position it decided to hold: force_close_intraday()
    would keep them in memory, the process would exit, and the next session would
    start with an empty INTRADAY book and no record that anything was carried. The
    hold and the persistence have to agree, or the feature quietly does nothing.
    """
    pools = set(MULTI_DAY_POOLS)
    if int(os.environ.get("MAX_HOLD_DAYS", "0") or 0) > 0:
        pools.add("INTRADAY")
    positions = {}
    for pool_name in pools:
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
    # Mirror of _save_active_positions: INTRADAY is restored only when carrying is
    # enabled. Save and restore MUST agree on the pool set — if they disagree the
    # positions are written to disk and then never read back, which looks exactly
    # like the carry working while the book silently empties every morning.
    _restore_pools = set(MULTI_DAY_POOLS)
    if int(os.environ.get("MAX_HOLD_DAYS", "0") or 0) > 0:
        _restore_pools.add("INTRADAY")
    for pool_name in _restore_pools:
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


# ═══════════════════════════ RISK GATE (log-only, Phase 0) ═══════════════════════════
# spec: 1cr-roadmap/research/2026-07-20_risk_gate_three_state_verdict.md S5 "Phase 0" --
# schema + gate module, wired in LOG-ONLY mode: the gate runs and records
# verdicts, but execution still follows today's inline path unchanged. Runs
# AFTER deploy_signals' own decisions are already locked in for this scan
# (see prototype/v5/risk_gate.py's module docstring for why that ordering
# matters). Verdicts are appended to
# docs/paper-trades/<ENGINE>/YYYY-MM-DD_verdicts.json. Kill switch:
# RISK_GATE_LOG=0 disables this block entirely (default ON -- behavior-neutral).

def _verdicts_file():
    return TRADE_DIR / f"{datetime.now().strftime('%Y-%m-%d')}_verdicts.json"


def _build_trade_plan(sig, pool_budget_rs, score_threshold, rm=None):
    """One TradePlan per candidate signal (spec S4.1). Phase 0: invalidation
    defaults to the recorded-not-enforced 'score_drop_below:<threshold>' form
    (spec S7 Q3 lean). threshold = the lowest score among this scan's
    candidates -- v5's BUY/SELL selection is regime-aware percentile cuts
    (signal_engine.py), not a single fixed global score cutoff, so the
    realized cutoff for this batch is the closest honest reading of "the
    signal threshold in use" from engine context.

    size_rs mirrors the deploy path's sizing (base 15% of budget, then
    rm.get_position_size's multipliers + caps). The plan must carry the size
    the engine would actually request: the raw 15% base exceeds the 10%
    position cap, which made the gate reject 494/494 candidates on v5_gate's
    first drive day (2026-07-21)."""
    price = sig.get("entry_price", sig.get("price", 0.0)) or 0.0
    side = sig.get("position_type") or ("LONG" if sig.get("direction") == "BUY" else "SHORT")
    reasons = sig.get("reasons") or []
    base = pool_budget_rs * 0.15
    size = base
    if rm is not None:
        try:
            size = rm.get_position_size(sig.get("pool", "INTRADAY"), base)
        except Exception:
            size = base
    rationale = (f"{sig.get('direction', '?')} rank={sig.get('rank', '?')} "
                 f"score={sig.get('score', 0)} chg={float(sig.get('change_pct', 0) or 0):+.2f}% "
                 f"{'; '.join(str(r) for r in reasons[:2])}").strip()
    return TradePlan(
        symbol=sig.get("symbol", "?"),
        side=side,
        entry=float(price),
        target=float(sig.get("target_price", price) or price),
        stop=float(sig.get("sl_price", price) or price),
        invalidation=f"score_drop_below:{score_threshold}",
        size_rs=round(size, 2),
        pool=sig.get("pool", "INTRADAY"),
        score=float(sig.get("score", 0) or 0),
        rationale=rationale,
    )


def _log_risk_gate_verdicts(state, pm, rm, candidates, deployed_syms, alloc_mult,
                             drive_mode=False, promoted=None):
    """Evaluate every candidate through RiskGate and append rows to the daily
    verdicts artifact. Log-only w.r.t. THIS function -- it never touches
    execution itself. Caller wraps this in its own try/except too (belt and
    suspenders) so a bug here can never affect deployments. When called from
    a RISK_GATE_DRIVE=1 scan, `drive_mode`/`promoted` (spec S5 Phase 1)
    annotate each row with whether the gate was actually steering that scan's
    deployments and whether this symbol was promoted off the watchlist."""
    if not candidates or rm is None or RiskGate is None or TradePlan is None:
        return
    promoted = promoted or set()
    score_threshold = min(float(s.get("score", 0) or 0) for s in candidates)
    gate = RiskGate(rm, score_threshold=score_threshold)
    rows = []
    for sig in candidates:
        pool_name = sig.get("pool", "INTRADAY")
        try:
            budget = pm.get_pool_budget(pool_name) * alloc_mult
        except Exception:
            budget = 0.0
        plan = _build_trade_plan(sig, budget, score_threshold, rm=rm)
        pos_type = sig.get("position_type") or ("LONG" if sig.get("direction") == "BUY" else "SHORT")
        result = gate.evaluate(plan, position_type=pos_type)
        rows.append({
            "symbol": plan.symbol,
            "plan": {
                "symbol": plan.symbol, "side": plan.side, "entry": plan.entry,
                "target": plan.target, "stop": plan.stop,
                "invalidation": plan.invalidation, "size_rs": plan.size_rs,
                "pool": plan.pool, "score": plan.score, "rationale": plan.rationale,
            },
            "verdict": result.verdict.value,
            "reasons": result.reasons,
            "checked_at": result.checked_at,
            "inline_outcome": "deployed" if plan.symbol in deployed_syms else "filtered",
            "engine": ENGINE,
            "regime": state.get("regime", "?"),
            "drive_mode": drive_mode,
            "promoted_from_watchlist": bool(drive_mode and plan.symbol in promoted),
        })
    if not rows:
        return
    path = _verdicts_file()
    existing = {"date": datetime.now().strftime("%Y-%m-%d"), "engine": ENGINE, "verdicts": []}
    if path.exists():
        try:
            loaded = json.loads(path.read_text())
            if isinstance(loaded, dict) and isinstance(loaded.get("verdicts"), list):
                existing = loaded
        except (json.JSONDecodeError, OSError):
            pass
    existing["verdicts"].extend(rows)
    existing["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    atomic_write_json(path, existing)


# spec: 1cr-roadmap/research/2026-07-20_risk_gate_three_state_verdict.md S5 Phase 1 --
# RISK_GATE_DRIVE=1 (default OFF) makes the gate DRIVE execution instead of
# only logging it. REJECTED -> skip. WATCHLIST -> defer THIS scan (recorded
# in state["gate_watchlist"]; spec S7 Q1/Q2 -- re-evaluated fresh every scan,
# no capital reserved, and it expires implicitly at EOD along with the rest
# of daily state -- nothing here persists it past the trading day).
# APPROVED -> deploy; if the symbol was on the watchlist this is a
# promotion, annotated in the verdicts artifact by the caller.
# Fail-CLOSED per spec: if the gate itself throws, fall back to the
# well-tested inline path for THIS SCAN ONLY and log loudly -- a broken
# gate module must never silently halt a shadow engine's whole session.
def _gate_drive_filter(state, pm, rm, candidates, alloc_mult):
    if RiskGate is None or TradePlan is None or Verdict is None or rm is None:
        log("  [RISK_GATE_DRIVE] gate unavailable (no RiskGate/rm) — falling back to inline path")
        return candidates, set(), {}
    try:
        watchlist = state.setdefault("gate_watchlist", {})
        scan_no = state.get("summary", {}).get("scan_count", 0)
        score_threshold = min(float(s.get("score", 0) or 0) for s in candidates) if candidates else 0.0
        gate = RiskGate(rm, score_threshold=score_threshold)
        approved, promoted, invalidation_map = [], set(), {}
        for sig in candidates:
            pool_name = sig.get("pool", "INTRADAY")
            try:
                budget = pm.get_pool_budget(pool_name) * alloc_mult
            except Exception:
                budget = 0.0
            plan = _build_trade_plan(sig, budget, score_threshold, rm=rm)
            pos_type = sig.get("position_type") or ("LONG" if sig.get("direction") == "BUY" else "SHORT")
            result = gate.evaluate(plan, position_type=pos_type)
            sym = plan.symbol
            invalidation_map[sym] = plan.invalidation
            if result.verdict == Verdict.REJECTED:
                watchlist.pop(sym, None)
                log(f"  [GATE] {sym}: REJECTED — {'; '.join(result.reasons)}")
                continue
            if result.verdict == Verdict.WATCHLIST:
                entry = watchlist.setdefault(
                    sym, {"reasons": [], "first_seen_scan": scan_no, "times_deferred": 0})
                entry["reasons"] = result.reasons
                entry["times_deferred"] = entry.get("times_deferred", 0) + 1
                log(f"  [GATE] {sym}: WATCHLIST (deferred {entry['times_deferred']}x, "
                    f"since scan #{entry['first_seen_scan']})")
                continue
            # APPROVED
            if sym in watchlist:
                promoted.add(sym)
                del watchlist[sym]
                log(f"  [GATE] {sym}: APPROVED — promoted from WATCHLIST")
            approved.append(sig)
        return approved, promoted, invalidation_map
    except Exception as e:
        log(f"  [RISK_GATE_DRIVE] gate raised, falling back to inline path this scan: {e}")
        return candidates, set(), {}


# ═══════════════════════════ DEPLOY ═══════════════════════════

def deploy_signals(state, pm, rm, signals):
    if not pm or not signals: return 0
    # DATA-GUARD (2026-07-12): never open NEW positions off a dead/stale tape.
    # On 07-08 and 07-10 DNS was down from open — signals came from cached CSVs and
    # the engine entered trades it could never price again. Exits are NOT gated.
    # NOTE (2026-07-24 fix): this used to `return 0` here, which skipped candidate
    # construction entirely and starved the RISK_GATE_LOG block at the tail of this
    # function of `all_candidates` -- a DATA-GUARD trip (common right at market open
    # while the tape is still catching up) silently erased that whole scan's rows
    # from the Phase-0 divergence artifact instead of logging them as filtered.
    # Deployment stays vetoed (`_data_guard_blocked` skips the entry loop below);
    # only the audit trail is no longer skipped.
    _data_guard_blocked = not _live_tape_ok()
    if _data_guard_blocked:
        log("  [DATA-GUARD] live tape unavailable/stale — blocking new entries this scan")

    # CHOP-FILTER (spec 2026-07-17): trade less + smaller in chop. Entries only.
    _chop_on = os.environ.get("CHOP_FILTER") == "1"
    _size_mult = _alloc_mult = 1.0
    if _chop_on:
        _update_trend_mode(state)
        from prototype.v5.trend_mode import apply_ladder
        signals, _size_mult, _alloc_mult = apply_ladder(signals, state.get("trend_mode", "CHOP"))
        log(f"  [chop] mode={state.get('trend_mode')} score={state.get('trend_score_last')} "
            f"-> {len(signals)} signals, size x{_size_mult}, alloc x{_alloc_mult}")

    held = {pos["symbol"] for pd in state["pools"].values() for pos in pd["positions"]}
    initial_held = set(held)  # RISK_GATE_LOG: diff against `held` post-loop -> which candidates deployed
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
    # (named so RISK_GATE_LOG below can replay the exact same candidate set post-loop)
    candidates = sorted([s for s in signals if s["direction"] in allowed_dirs],
                        key=lambda s: -float(s.get("score", 0)))

    # MIN_ENTRY_SCORE — entry-quality floor. DEFAULT 0 = disabled, so every existing
    # engine is byte-for-byte unchanged and its history stays comparable.
    #
    # WHY (measured 2026-08-04 over v5's last 25 sessions, 414 closed trades):
    # score barely predicts WIN RATE — winners averaged 56.3, losers 54.9, Cohen's
    # d = 0.06, i.e. noise. But it strongly predicts NET P&L, because payoff size
    # differs even when hit rate does not:
    #     floor  trades  gross   costs    NET
    #        0      414  6,177   5,920    256    <- costs eat 96% of gross
    #       70      193  7,121   2,760  4,361
    # Gross profit is HIGHER with 53% fewer trades, so sub-70 entries lose money
    # before costs are counted; costs then convert a thin edge into nearly nothing.
    #
    # This is a selectivity change, NOT a shorting change — it filters candidates by
    # score only, and both directions are treated identically.
    # NO_ENTRY_HOURS — time-of-day entry gate. DEFAULT empty = disabled.
    #
    # WHY (v5's last 30 sessions, 504 closed trades with entry times):
    #   hour   trades  win%   net       net/trade
    #   09:00     121   40%   -2,550      -21.1   <- worst hour by a wide margin
    #   13:00      92   45%   +1,503      +16.3   <- the only profitable hour
    # Skipping 09h alone: 504 -> 383 trades, net -3,425 -> -875 (+2,550).
    #
    # EVIDENCE STRENGTH, stated honestly: only 9 of 30 sessions traded the 09:00
    # hour. 6 of those 9 were net negative (median -Rs 363), so the direction is
    # consistent, but one session at -Rs 2,253 carries much of the magnitude. This
    # is suggestive, not established — which is exactly why it ships as a shadow
    # rather than a change to v5.
    #
    # It is a pure GATE: subtractive, mechanical, no discretion, and it can only
    # reduce trade count. That matters because this stack's documented failure mode
    # is win rate falling 82% -> 48% as trade count rose 17 -> 45.
    _no_hours = {int(h) for h in os.environ.get("NO_ENTRY_HOURS", "").replace(" ", "").split(",") if h}
    if _no_hours:
        from datetime import datetime as _dt
        _hh = _dt.now().hour
        if _hh in _no_hours:
            if candidates:
                log(f"  [time-gate] {_hh:02d}:00 is a no-entry hour — "
                    f"{len(candidates)} candidates skipped")
            candidates = []

    _min_score = float(os.environ.get("MIN_ENTRY_SCORE", "0") or 0)
    if _min_score > 0:
        _before = len(candidates)
        candidates = [s for s in candidates if float(s.get("score", 0) or 0) >= _min_score]
        if _before != len(candidates):
            log(f"  [score-floor] {_before} -> {len(candidates)} candidates "
                f"(dropped {_before - len(candidates)} below {_min_score:g})")
    all_candidates = candidates  # RISK_GATE_LOG below replays this full pre-gate set, drive or not
    _drive_on = os.environ.get("RISK_GATE_DRIVE") == "1"
    _gate_promoted, _gate_invalidation_map = set(), {}
    if _drive_on:
        candidates, _gate_promoted, _gate_invalidation_map = _gate_drive_filter(
            state, pm, rm, candidates, _alloc_mult)
    for sig in ([] if _data_guard_blocked else candidates):
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
        budget = pm.get_pool_budget(pool_name) * _alloc_mult
        if budget < 10000: continue
        price = sig.get("entry_price", sig.get("price", 0))
        base = budget * 0.15

        sized = (rm.get_position_size(pool_name, base) if rm else base) * _size_mult

        qty = safe_qty(budget, price, sized=sized)

        if qty is None: continue
        cost = qty * price
        # #2 FIX: widen default SL on strong-gap mornings (|gap|>0.5%) — v5 was stopped out of CIPLA/DRREDDY right before they rallied on 04-24
        _gap = abs(float(state.get("premarket", {}).get("gap_prediction", {}).get("magnitude_pct", 0) or 0))
        if TARGET_PCT is not None and STOP_PCT is not None:
            # v8: fixed April bracket off entry, ignoring signal-supplied sl/tgt
            _is_buy = sig["direction"] == "BUY"
            sl  = price * ((1 - STOP_PCT / 100)   if _is_buy else (1 + STOP_PCT / 100))
            tgt = price * ((1 + TARGET_PCT / 100) if _is_buy else (1 - TARGET_PCT / 100))
        else:
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
        new_pos = {
            "symbol": sym, "entry_price": round(price, 2), "qty": qty,
            "cost": round(cost, 2), "entry_time": datetime.now().strftime("%H:%M:%S"),
            "entry_date": datetime.now().strftime("%Y-%m-%d"),
            "sl_price": round(sl, 2), "target_price": round(tgt, 2),
            "position_type": pos_type, "pool": pool_name,
            "trailing_activated": False, "peak_price": round(price, 2),
            "trough_price": round(price, 2), "score": sig.get("score", 0),
            "direction": sig["direction"], "reasons": sig.get("reasons", [])}
        # Phase 2 (spec S4.3): persist the TradePlan invalidation onto the
        # position record at entry, DRIVE-mode only -- scan_positions'
        # INVALIDATION_MONITOR reads it back at MONITOR time.
        if _drive_on:
            new_pos["invalidation"] = _gate_invalidation_map.get(sym, "")
        state["pools"][pool_name]["positions"].append(new_pos)
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

    # RISK_GATE_LOG (default ON): log-only, runs AFTER the deploy decisions
    # above are already final. Fail-open -- any exception here is swallowed
    # and logged; it can never change `count` or what was deployed.
    if os.environ.get("RISK_GATE_LOG", "1") == "1":
        try:
            _log_risk_gate_verdicts(state, pm, rm, all_candidates, held - initial_held, _alloc_mult,
                                     drive_mode=_drive_on, promoted=_gate_promoted)
        except Exception as e:
            log(f"  [RISK_GATE_LOG] failed: {e}")

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
            engine="v5", symbol=sym,
            direction="SELL" if is_short else "BUY",
            expected_price=pos.get("target_price") or exit_price,
            fill_price=exit_price,
            quantity=pos["qty"], side="exit",
            trade_id=f"v5-{sym}-{pos.get('entry_time','?')}",
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
        "position_type": pos.get("position_type", "LONG"), "pool": pool_name,
        # TP-RCA 2026-06-30: carry ENTRY CONVICTION into the closed record so we can
        # validate conviction->P&L (previously captured on the open position then dropped
        # at close — the gap that made conviction-weighting unprovable). "store everything".
        "score": pos.get("score"), "direction": pos.get("direction"),
        "reasons": pos.get("reasons"), "sl_price": pos.get("sl_price"),
        "target_price": pos.get("target_price"), "entry_date": pos.get("entry_date"),
        "trailing_activated": pos.get("trailing_activated")})
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


# spec: 1cr-roadmap/research/2026-07-20_risk_gate_three_state_verdict.md S4.3/S5
# Phase 2 -- INVALIDATION_MONITOR=1 (default OFF). Evaluate ONLY the forms
# cleanly computable from data already sitting in scan_positions' loop --
# per spec S7 Q3 lean, we do NOT fetch new data or invent indicator plumbing
# under this. `state["last_signals"]` is the most recent rescore's signal
# batch (populated by rescore_and_redeploy the PRIOR cycle -- already in
# state, nothing fetched here), so `score_drop_below:<n>` is enforceable.
# `close_below:<ind>` (needs a moving-average series) and
# `rrg_quadrant_exit:<sector>` (needs a per-sector quadrant read, not just
# the session-level RRG tilt v5_rrg computes) have no data source in this
# loop -- recorded as not_enforced, never invented. Never raises: malformed
# or empty invalidation strings are ignored gracefully.
def _check_invalidation(inv, sym, state):
    if not inv or ":" not in str(inv):
        return False, "not_enforced: malformed/empty invalidation string"
    form, _, arg = str(inv).partition(":")
    form = form.strip()
    if form == "score_drop_below":
        try:
            threshold = float(arg)
        except (TypeError, ValueError):
            return False, f"not_enforced: bad threshold in '{inv}'"
        sig_map = {s.get("symbol"): s for s in state.get("last_signals", []) if isinstance(s, dict)}
        sig = sig_map.get(sym)
        if not sig or sig.get("score") is None:
            return False, "checked: no fresh rescore data for symbol this cycle"
        try:
            score = float(sig.get("score", 0) or 0)
        except (TypeError, ValueError):
            return False, "checked: unreadable score"
        if score < threshold:
            return True, f"score {score} < threshold {threshold}"
        return False, f"checked: score {score} >= threshold {threshold}"
    return False, f"not_enforced: form '{form}' has no data source in scan_positions"


# ═══════════════════════════ SCAN ═══════════════════════════

def scan_positions(state, pm, rm):
    state["summary"]["scan_count"] += 1
    all_pos = [(pn, p) for pn, pd in state["pools"].items() for p in pd["positions"]]
    if not all_pos: log("  No open positions"); return
    prices = get_prices_batch(list({p["symbol"] for _, p in all_pos}))
    unrealized, to_close = 0, []
    log(f"\n{'='*65}\n  SCAN #{state['summary']['scan_count']} | {len(all_pos)} positions\n{'='*65}")
    flat_window_active = _in_flat_exit_window()
    _inv_monitor_on = os.environ.get("INVALIDATION_MONITOR") == "1"
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
        # REVERSAL_EXIT_PCT — take profit on a fade instead of waiting for target.
        # DEFAULT 0 = disabled.
        #
        # WHY: only 4.6% of v5's trades ever reach TARGET while 30% hit STOPLOSS, and
        # the two almost exactly cancel (+9,484 vs -9,503). A position that has moved
        # in your favour and then stalls is currently held until the clock or the stop
        # decides — this books the move instead. Soumya's framing: "look for the
        # candle signal; if it says it is time to sell, sell."
        #
        # The signal is deliberately crude and mechanical: the position is in profit
        # by at least REVERSAL_EXIT_PCT, and price has since retraced more than half
        # of its best excursion. peak_price/trough_price are already tracked above, so
        # this needs no new data and cannot disagree with the price the engine used.
        _rev = float(os.environ.get("REVERSAL_EXIT_PCT", "0") or 0)
        if _rev > 0 and pnl_pct >= _rev:
            best = pos.get("trough_price" if is_short else "peak_price", entry)
            excursion = (entry - best) if is_short else (best - entry)
            giveback = (px - best) if is_short else (best - px)
            if excursion > 0 and giveback > excursion * 0.5:
                reason = "REVERSAL_EXIT"
                log(f"  {sym}: REVERSAL_EXIT @ {px:.2f} (peak {best:.2f}, "
                    f"gave back {giveback/excursion*100:.0f}% of the move, "
                    f"booking {pnl_pct:+.2f}%)")
                to_close.append((pool_name, pos, px, reason)); continue

        if flat_window_active and abs(pnl_pct) < FLAT_EXIT_THRESHOLD_PCT:
            reason = "FLAT_FORCE_EXIT"
            log(f"  {sym}: FLAT_FORCE_EXIT @ {px:.2f} (pnl_pct={pnl_pct:+.2f}%)")
            to_close.append((pool_name, pos, px, reason)); continue
        # WRONGWAY_CUT (v5_cut, env-gated, default off): cut a position as soon as it's
        # this far underwater intraday — stops the "hold the loser all day" bleed the
        # watchdog flagged (e.g. ADANIENT held wrong-way 82 cycles on 06-19).
        if WRONGWAY_CUT_PCT > 0 and pnl_pct <= -WRONGWAY_CUT_PCT:
            reason = "WRONGWAY_CUT"
            log(f"  {sym}: WRONGWAY_CUT @ {px:.2f} (pnl_pct={pnl_pct:+.2f}%)")
            to_close.append((pool_name, pos, px, reason)); continue
        # INVALIDATION_MONITOR (Phase 2, env-gated, default off): thesis
        # falsifier distinct from STOP/TARGET/AGED -- see _check_invalidation.
        if _inv_monitor_on:
            inv = pos.get("invalidation")
            if inv:
                triggered, note = _check_invalidation(inv, sym, state)
                pos["invalidation_check"] = note
                if triggered:
                    reason = "INVALIDATED"
                    log(f"  {sym}: INVALIDATED ({inv}) — {note}")
                    to_close.append((pool_name, pos, px, reason)); continue
        if is_short:
            if px >= pos["sl_price"]: reason = "STOPLOSS"
            elif px <= pos["target_price"]: reason = "TARGET"
            elif STOP_MODE != "fixed" and pnl_pct >= TRAILING_TRIGGER_PCT:
                if not pos.get("trailing_activated"):
                    pos["trailing_activated"] = True; pos["sl_price"] = entry
                    log(f"  {sym}: SHORT TRAILING -> SL@{entry:.2f}")
                else:
                    trail = round(pos["trough_price"] * (1 + TRAILING_STEP_PCT / 100), 2)
                    if trail < pos["sl_price"]: pos["sl_price"] = trail
        else:
            if px <= pos["sl_price"]: reason = "STOPLOSS"
            elif px >= pos["target_price"]: reason = "TARGET"
            elif STOP_MODE != "fixed" and pnl_pct >= TRAILING_TRIGGER_PCT:
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

_flip_st = {"off": 0, "on": 0}

def _fast_flip(state, pm, rm):
    """TP-RCA 2026-06-30 (v5_flip, env FAST_FLIP=1): fast INTRADAY regime tilt.

    The slow daily regime is set once at launch and rarely flips, so the engine stays
    long-heavy on red days (validated: short-share flat ~45% across UP/DOWN days). This
    re-checks the live tape every scan and activates the EXISTING BEAR slot split (8L/12S)
    intraday when the day is a CONFIRMED hard-down (NIFTY < -0.6%, validated threshold —
    mild-down still favours longs). Bidirectional: reverts to SIDEWAYS on a confirmed green
    reversal (captures the 2nd-half up-trend). Keeps both legs (never 0 longs). Re-arm on
    TARGET already works both directions. Confirmation (2 reads) + hysteresis = anti-whipsaw.
    Live v5 is unaffected (flag off). No new code-path for direction yet — that needs the
    conviction data we just started logging.
    """
    if os.environ.get("FAST_FLIP") != "1":
        return
    try:
        import yfinance as yf  # per-process cache already set via data_nse._get_yfinance
        n = yf.download("^NSEI", period="1d", interval="5m", progress=False)
        if not len(n):
            return
        o = float(n["Open"].iloc[0]); c = float(n["Close"].iloc[-1])
        pct = 100 * (c - o) / o
    except Exception as e:
        log(f"  fast-flip tape fetch failed (non-fatal): {e}")
        return
    HARD_DOWN, GREEN = -0.6, 0.15        # validated: short-tilt only on confirmed hard-down
    cur = state.get("regime", "SIDEWAYS")
    if pct <= HARD_DOWN:
        _flip_st["off"] += 1; _flip_st["on"] = 0
    elif pct >= GREEN:
        _flip_st["on"] += 1; _flip_st["off"] = 0
    else:
        _flip_st["off"] = _flip_st["on"] = 0
    new = None
    if _flip_st["off"] >= 2 and cur != "BEAR":
        new = "BEAR"
    elif _flip_st["on"] >= 2 and cur == "BEAR":
        new = "SIDEWAYS"
    if new:
        state["regime"] = new
        if pm: pm.set_regime(new)
        if rm: rm.regime = new
        log(f"  FAST-FLIP: tape {pct:+.2f}% -> regime {cur} -> {new} (slot tilt now active)")


def _rrg_score_for_session(state):
    """REGIME_SENSOR=rrg score producer (Gate-1 PASS, commit d23726e — see
    prototype/v5/rrg_regime.py for the encoded config: form=count,
    set=extended, N=1, threshold=-0.2143, pc85/lc73).

    Computed ONCE per session and cached in state["_rrg_score_cache"] keyed
    by date -- the sensor is daily-bar-driven (no intraday component), so
    recomputing it mid-session would just re-fetch the same closes for the
    same answer (design doc §5/§7: "tilt input, not trading trigger", held
    constant across the session). Fetches ~10 calendar days of daily closes
    per ticker (enough for N=1 across weekends/holidays), using ONLY closes
    strictly before today (no-lookahead -- any bar dated today is dropped).
    Fail-closed: fetch failure or a None signal (NO-DATA, per rrg_regime's
    fail-closed set-membership rules) -> score 0.0 (=> CHOP).
    """
    from prototype.v5.rrg_regime import (
        rotation_signal, rrg_score, ALL_TICKERS, DEFENSIVE, CYCLICAL_EXTENDED,
    )
    today = datetime.now().strftime("%Y-%m-%d")
    cache = state.get("_rrg_score_cache")
    if cache and cache.get("date") == today:
        return cache["score"]

    closes_by_ticker = {}
    try:
        import yfinance as yf
        import pandas as pd
        for t in ALL_TICKERS:
            try:
                df = yf.download(t, period="10d", interval="1d", progress=False)
                if df is None or len(df) == 0:
                    continue
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                closes = df["Close"].dropna()
                # NO-LOOKAHEAD: only closes strictly before today.
                pairs = sorted((str(idx.date()), float(v)) for idx, v in closes.items()
                                if str(idx.date()) < today)
                if pairs:
                    closes_by_ticker[t] = [v for _, v in pairs]
            except Exception as e:
                log(f"  [rrg] {t} fetch failed (fail-closed skip): {e}")
    except Exception as e:
        log(f"  [rrg] yfinance unavailable (fail-closed): {e}")

    signal = rotation_signal(closes_by_ticker)
    score = rrg_score(signal)
    if signal is None:
        log("  [rrg] NO-DATA this session (fail-closed to CHOP)")
    def_present = sum(1 for t in DEFENSIVE if len(closes_by_ticker.get(t, [])) >= 2)
    cyc_present = sum(1 for t in CYCLICAL_EXTENDED if len(closes_by_ticker.get(t, [])) >= 2)
    # Amendment C parity (2026-07-20): persist raw signal + member counts so
    # daily JSONs support Gate-2 post-hoc analysis without re-fetching bars.
    state["rrg_signal"] = {
        "signal": round(signal, 4) if signal is not None else None,
        "defensive_present": def_present, "defensive_total": len(DEFENSIVE),
        "cyclical_present": cyc_present, "cyclical_total": len(CYCLICAL_EXTENDED),
    }
    state["_rrg_score_cache"] = {"date": today, "score": score}
    return score


def _update_trend_mode(state):
    """v5_chop sensor (spec 2026-07-17) + REGIME_SENSOR score-producer swap
    (2026-07-20, design doc §5 "swap the score producer, not the
    consumer"): recompute the mode-driving score each scan.

    CHOP_FILTER=1 only. REGIME_SENSOR selects which score feeds the SAME
    mode_for() hysteresis + apply_ladder() consumer either way:
      - "trendscore" (default, unchanged): tape efficiency + breadth +
        premarket regime, recomputed every scan from fresh intraday data.
      - "rrg": prototype/v5/rrg_regime.py's Gate-1-PASSED rotation-count
        sensor (see _rrg_score_for_session above), computed once per
        session and cached.
    Fail-closed: any missing input contributes 0 -> mode decays toward CHOP.
    """
    if os.environ.get("CHOP_FILTER") != "1":
        return
    from prototype.v5.trend_mode import mode_for
    sensor = os.environ.get("REGIME_SENSOR", "trendscore")
    if sensor == "rrg":
        s = _rrg_score_for_session(state)
    else:
        from prototype.v5.trend_mode import tape_efficiency, breadth_strength, trend_score
        tape = 0.0
        try:
            import yfinance as yf
            n = yf.download("^NSEI", period="1d", interval="5m", progress=False)
            if len(n):
                tape = tape_efficiency([float(c) for c in n["Close"].dropna().values])
        except Exception as e:
            log(f"  [chop] tape fetch failed (fail-closed): {e}")
        b = state.get("_breadth_cache")
        if b is None:
            try:
                from prototype.v5.market_breadth import compute_breadth_indicators
                ind = compute_breadth_indicators()
                b = {"today": ind.get("pct_20"), "prev": state.get("_pct20_prev")}
            except Exception as e:
                log(f"  [chop] breadth failed (fail-closed): {e}")
                b = {"today": None, "prev": None}
            state["_breadth_cache"] = b
        breadth = breadth_strength(b["today"], b["prev"])
        regime_score = int(state.get("premarket", {}).get("regime_score", 0) or 0)
        s = trend_score(tape, breadth, regime_score)
        # Amendment C (2026-07-20): persist raw components so daily JSONs let us
        # re-sweep any (td, bm, rd, thresholds) at the Gate-2 review without
        # re-fetching bars.
        state["trend_components"] = {"tape": round(tape, 2), "breadth": round(breadth, 2), "regime": regime_score}
    cur = state.get("trend_mode", "CHOP")
    mode, pending = mode_for(s, state.get("trend_pending"), cur)
    if mode != cur:
        log(f"  [chop] mode {cur} -> {mode} (score {s:.0f}, sensor={sensor})")
    state["trend_mode"], state["trend_pending"], state["trend_score_last"] = mode, pending, round(s, 1)


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

def _sessions_held(pos) -> int:
    """Trading sessions this position has been open. Weekend-aware: counts distinct
    weekdays, so a Friday entry seen on Monday is 1 session old, not 3."""
    from datetime import date as _date, timedelta as _td
    ed = str(pos.get("entry_date") or pos.get("entry_time") or "")[:10]
    try:
        y, m, d = (int(x) for x in ed.split("-"))
        start = _date(y, m, d)
    except Exception:
        return 0
    n, cur = 0, start
    today = _date.today()
    while cur < today:
        cur += _td(days=1)
        if cur.weekday() < 5:        # NSE holidays not modelled — errs toward closing
            n += 1
    return n


def force_close_intraday(state, pm, rm):
    positions = state["pools"].get("INTRADAY", {}).get("positions", [])
    if not positions: log("  No intraday positions to close"); return

    # MAX_HOLD_DAYS — let an INTRADAY position live past the session. DEFAULT 0 =
    # close everything at EOD, exactly as before, so all existing engines are
    # unchanged.
    #
    # WHY (PDH/PDL backtest, 892 setups, 20 symbols, 180 days, Kite hourly bars):
    #     hold     win%  target%  unresolved      NET
    #     1 day     44%      11%         70%  -12,409
    #     2 days    44%      31%         18%  +28,186
    #     3 days    42%      35%          9%  +33,913
    #     5 days    41%      37%          3%   -5,504
    # Win rate FALLS while net rises sharply — the problem was never picking
    # winners, it was closing positions mid-thesis on the clock. 70% of one-day
    # trades never resolved at all. v5's live book has the same shape: only 4.6% of
    # trades reach TARGET, and nearly all its profit comes from TIME_EXIT, i.e. from
    # giving up rather than from the stop/target geometry working.
    #
    # KNOWN RISK, measured not assumed: this backtest fills stops AT the stop price.
    # Overnight that is often false — across 960 gaps on 8 large caps (180d) the
    # median gap was 0.46%, the 90th percentile 1.58%, worst 8.66%, and a 1% stop is
    # JUMPED by 24% of overnight gaps. So +Rs 33,913 is an optimistic ceiling. This
    # ships as a shadow precisely because the backtest cannot see fill quality.
    _max_hold = int(os.environ.get("MAX_HOLD_DAYS", "0") or 0)
    if _max_hold > 0:
        keep = [p for p in positions if _sessions_held(p) < _max_hold]
        expire = [p for p in positions if _sessions_held(p) >= _max_hold]
        if keep:
            log(f"\n  HOLDING {len(keep)} INTRADAY positions overnight "
                f"(MAX_HOLD_DAYS={_max_hold}); {len(expire)} aged out")
            positions = expire
            if not positions:
                _save_active_positions(state)
                log(f"  Saved {len(keep)} carried positions to positions_active.json")
                return

    log(f"\n  FORCE CLOSING {len(positions)} INTRADAY positions")
    prices = get_prices_batch([p["symbol"] for p in positions])
    for pos in list(positions):
        close_position(state, pm, rm, "INTRADAY", pos,
                       prices.get(pos["symbol"], pos["entry_price"]),
                       "MAX_HOLD_EXIT" if _max_hold > 0 else "TIME_EXIT")
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
                                password=devpilot_db_password(), dbname="devpilot")
        s = state.get("summary", {}); today = datetime.now().strftime("%Y-%m-%d")
        pp = s.get("total_pnl", 0) / TOTAL_CAPITAL * 100
        wr = s.get("wins", 0) / max(s.get("trades", 1), 1) * 100
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO learnings (project,category,title,content,source,tags,active,created_at,updated_at) "
            "VALUES (%s,%s,%s,%s,'v5-paper-trade',%s,true,NOW(),NOW())",
            ("tradepilot", "paper-trade",
             f"{ENGINE} {today}: {_fmt(s.get('total_pnl',0))} ({pp:+.2f}%) | {s.get('trades',0)}t | {wr:.0f}%w",
             json.dumps({"engine": ENGINE, "capital": TOTAL_CAPITAL, "regime": state.get("regime", "?"),
                         "pnl": s.get("total_pnl", 0), "trades": s.get("trades", 0),
                         "wins": s.get("wins", 0), "longs": s.get("longs", 0), "shorts": s.get("shorts", 0)}),
             ["paper-trade", ENGINE, today, state.get("regime", "").lower()]))
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
        scan_positions(state, pm, rm); _fast_flip(state, pm, rm); rescore_and_redeploy(state, pm, rm)

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
