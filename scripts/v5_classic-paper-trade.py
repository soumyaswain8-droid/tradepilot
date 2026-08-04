#!/usr/bin/env python3
"""
TradePilot v5-CLASSIC Paper Trading Engine (pre-Rust, pre-safeguards)
This is the ORIGINAL v5 from commit 236d6e4 (Apr 16 morning), when v5 was making +Rs 49,713/day (Apr 15) and +Rs 17,295 (Apr 16).
Kept unchanged except: (1) separate state directory (2) NaN guard for crash safety
Purpose: A/B credibility test against current hardened v5
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
import json, sys, time, warnings, importlib
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
PROJECT_ROOT = Path(__file__).parent.parent
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades" / "v5_classic"
LOG_DIR = PROJECT_ROOT / "logs"
sys.path.insert(0, str(PROJECT_ROOT / "prototype"))
sys.path.insert(0, str(PROJECT_ROOT))
LOG_FILE = LOG_DIR / "v5_classic-paper-trade.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

TOTAL_CAPITAL = 1_000_000  # Same Rs 10L as v4 for fair comparison
TRAILING_TRIGGER_PCT, TRAILING_STEP_PCT = 1.0, 0.5
SCAN_INTERVAL_MIN, RESCORE_INTERVAL_MIN = 10, 30
FORCE_EXIT_HOUR, FORCE_EXIT_MIN = 15, 15
POOL_NAMES = ["INTRADAY", "SWING", "POSITIONAL", "INVESTMENT"]

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
CARRY_FORWARD_FILE = TRADE_DIR / "carry_forward_v5_classic.json"


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
    return {"date": datetime.now().strftime("%Y-%m-%d"), "engine": "v5_classic",
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
    ACTIVE_POS_FILE.write_text(json.dumps(data, indent=2, default=str))

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
    _state_file().write_text(json.dumps(s, indent=2, default=str))
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


import os as _os_tgnoise
TELEGRAM_TRADE_NOISE = _os_tgnoise.environ.get("TELEGRAM_TRADE_NOISE", "0") == "1"

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
    # #3 FIX: rank by score desc so the max-20 cap fills with highest-conviction picks, not FCFS.
    for sig in sorted([s for s in signals if s["direction"] in ("BUY", "SELL")],
                      key=lambda s: -float(s.get("score", 0))):
        sym, pool_name = sig["symbol"], sig.get("pool", "INTRADAY")
        if sym in held or pool_name not in state["pools"] or pool_name == "NONE": continue
        if rm:
            # #1 FIX: pass position_type so the slot-partition cap can fire per-direction
            _pt = sig.get("position_type", "LONG" if sig["direction"] == "BUY" else "SHORT")
            ok, reason = rm.check_can_trade(pool_name, sym, _pt)
            if not ok: log(f"  {sym}: BLOCKED ({reason})"); continue
        pool = pm.pools.get(pool_name)
        if not pool: continue
        budget = pm.get_pool_budget(pool_name)
        if budget < 10000: continue
        price = sig.get("entry_price", sig.get("price", 0))
        if not (price > 0): continue  # NaN-safe (only patch)
        base = budget * 0.15
        sized = rm.get_position_size(pool_name, base) if rm else base
        qty = max(1, int(min(sized, budget) / price))
        cost = qty * price
        # #2 FIX: widen default SL on strong-gap mornings (|gap|>0.5%)
        _gap = abs(float(state.get("premarket", {}).get("gap_prediction", {}).get("magnitude_pct", 0) or 0))
        _sl_pct = 0.0225 if _gap > 0.5 else 0.015
        sl = sig.get("sl_price", price * ((1 - _sl_pct) if sig["direction"] == "BUY" else (1 + _sl_pct)))
        tgt = sig.get("target_price", price * (1.02 if sig["direction"] == "BUY" else 0.98))
        pos_type = sig.get("position_type", "LONG" if sig["direction"] == "BUY" else "SHORT")
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
    if count: log(f"  Deployed {count} positions")
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
    if pm: pm.close_position(pool_name, sym, exit_price, reason)
    if rm: rm.record_trade_result(pool_name, sym, pnl)
    # Sprint 1 — Execution Analyst slippage hook. Non-blocking on failure.
    try:
        from scripts.team.slippage import record_slippage
        record_slippage(
            engine="v5_classic", symbol=sym,
            direction="SELL" if is_short else "BUY",
            expected_price=pos.get("target_price") or exit_price,
            fill_price=exit_price,
            quantity=pos["qty"], side="exit",
            trade_id=f"v5_classic-{sym}-{pos.get('entry_time','?')}",
            extra={"reason": reason})
    except Exception:
        pass
    state["pools"][pool_name]["closed"].append({
        "symbol": sym, "entry_price": pos["entry_price"], "exit_price": round(exit_price, 2),
        "qty": pos["qty"], "entry_time": pos["entry_time"],
        "exit_time": datetime.now().strftime("%H:%M:%S"),
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "reason": reason,
        "position_type": pos.get("position_type", "LONG"), "pool": pool_name,
        # TP-RCA 2026-06-30: carry entry conviction into closed record ("store everything").
        "score": pos.get("score"), "direction": pos.get("direction"),
        "reasons": pos.get("reasons"), "sl_price": pos.get("sl_price"),
        "target_price": pos.get("target_price"), "entry_date": pos.get("entry_date"),
        "trailing_activated": pos.get("trailing_activated")})
    state["pools"][pool_name]["pnl"] += pnl
    state["pools"][pool_name]["positions"] = [
        p for p in state["pools"][pool_name]["positions"] if p["symbol"] != sym]
    s = state["summary"]
    s["total_pnl"] += pnl; s["trades"] += 1
    s["wins" if pnl > 0 else "losses"] += 1
    s["shorts" if is_short else "longs"] = s.get("shorts" if is_short else "longs", 0) + 1
    tag = ("WIN" if pnl > 0 else "LOSS") + f" {'SHORT' if is_short else 'LONG'}"
    log(f"  >> {tag} {sym} x{pos['qty']} @{exit_price:.2f} ({reason}) "
        f"P&L: Rs {pnl:+,.0f} ({pnl_pct:+.2f}%) [{pool_name}]")
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
    """#5 helper: True when position held LESS than min_minutes (exit should be suppressed)."""
    try:
        et = datetime.strptime(pos.get("entry_time", ""), "%H:%M:%S").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        return (datetime.now() - et).total_seconds() < min_minutes * 60
    except (ValueError, TypeError):
        return False


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
            # #5 FIX: 60-min minimum hold before SIGNAL_FLIP
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
             f"v5 {today}: {_fmt(s.get('total_pnl',0))} ({pp:+.2f}%) | {s.get('trades',0)}t | {wr:.0f}%w",
             json.dumps({"engine": "v5_classic", "capital": TOTAL_CAPITAL, "regime": state.get("regime", "?"),
                         "pnl": s.get("total_pnl", 0), "trades": s.get("trades", 0),
                         "wins": s.get("wins", 0), "longs": s.get("longs", 0), "shorts": s.get("shorts", 0)}),
             ["paper-trade", "v5", today, state.get("regime", "").lower()]))
        conn.commit(); cur.close(); conn.close(); log("  Saved to DevPilot DB")
    except Exception as e: log(f"  DevPilot push failed: {e}")


# ═══════════════════════════ MAIN LOOP ═══════════════════════════

def run():
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
