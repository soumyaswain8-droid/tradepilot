#!/usr/bin/env python3
"""
TradePilot v5.4 Paper Trading Engine — Bi-Directional
=======================================================
Based on v5 but trades BOTH long AND short based on regime.
Fixes v5's bullish bias by actively deploying short signals.

Direction budget by regime:
  BULL:     80% long, 20% short
  SIDEWAYS: 50% long, 50% short
  BEAR:     20% long, 80% short

Key differences from v5:
  - Short signals deployed to SWING pool (not just INTRADAY)
  - Regime-weighted capital allocation between long/short
  - Separate long/short P&L tracking
  - Fixed PoolManager P&L for shorts

Usage:
    python3 scripts/v5_4-paper-trade.py              # Full auto-pilot
    python3 scripts/v5_4-paper-trade.py --status      # All pools + positions
    python3 scripts/v5_4-paper-trade.py --summary     # P&L summary
"""
import json, sys, time, warnings, importlib
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
PROJECT_ROOT = Path(__file__).parent.parent
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades" / "v5_4"
LOG_DIR = PROJECT_ROOT / "logs"
sys.path.insert(0, str(PROJECT_ROOT / "prototype"))
sys.path.insert(0, str(PROJECT_ROOT))
LOG_FILE = LOG_DIR / "v5_4-paper-trade.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

TOTAL_CAPITAL = 1_000_000
TRAILING_TRIGGER_PCT, TRAILING_STEP_PCT = 1.0, 0.5
SCAN_INTERVAL_MIN, RESCORE_INTERVAL_MIN = 10, 30
FORCE_EXIT_HOUR, FORCE_EXIT_MIN = 15, 15
POOL_NAMES = ["INTRADAY", "SWING", "POSITIONAL", "INVESTMENT"]
MULTI_DAY_POOLS = {"SWING", "POSITIONAL", "INVESTMENT"}

# Regime-based direction budget (what % of capital goes to each direction)
DIRECTION_BUDGET = {
    "BULL":     {"long": 0.80, "short": 0.20},
    "SIDEWAYS": {"long": 0.50, "short": 0.50},
    "BEAR":     {"long": 0.20, "short": 0.80},
}

# Short signals go to these pools (v5 only allowed INTRADAY)
SHORT_ALLOWED_POOLS = {"INTRADAY", "SWING"}

# ═══════════════════════════ IMPORTS ═══════════════════════════
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

# Also import short signal scoring
try:
    _sig_mod = importlib.import_module("prototype.v5.signal_engine")
    _mods["get_short_signals"] = _sig_mod.get_short_signals
    _mods["get_long_signals"] = _sig_mod.get_long_signals
except (ImportError, AttributeError):
    _mods["get_short_signals"] = None
    _mods["get_long_signals"] = None


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

ACTIVE_POS_FILE = TRADE_DIR / "positions_active.json"
CARRY_FORWARD_FILE = TRADE_DIR / "carry_forward_v5_4.json"


def _get_carry_forward_balance():
    if CARRY_FORWARD_FILE.exists():
        try:
            cf = json.load(open(CARRY_FORWARD_FILE))
            bal = cf.get("closing_balance", TOTAL_CAPITAL)
            log(f"  CARRY FORWARD: Rs {bal:,.0f} from {cf.get('date', '?')}")
            return bal
        except Exception: pass
    return TOTAL_CAPITAL


def _save_carry_forward(state):
    pnl = state.get("summary", {}).get("total_pnl", 0)
    closing = TOTAL_CAPITAL + pnl
    if CARRY_FORWARD_FILE.exists():
        try:
            prev = json.load(open(CARRY_FORWARD_FILE))
            closing = prev.get("closing_balance", TOTAL_CAPITAL) + pnl
        except Exception: pass
    cf = {"date": state.get("date"), "closing_balance": round(closing, 2),
          "todays_pnl": round(pnl, 2), "cumulative_pnl": round(closing - TOTAL_CAPITAL, 2),
          "starting_capital": TOTAL_CAPITAL}
    with open(CARRY_FORWARD_FILE, "w") as f:
        json.dump(cf, f, indent=2)
    log(f"  Balance carried forward: Rs {closing:,.0f}")


def _state_file():
    return TRADE_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.json"


def fresh_state(capital=None):
    cap = capital or TOTAL_CAPITAL
    return {"date": datetime.now().strftime("%Y-%m-%d"), "engine": "v5.4-bidirectional",
            "started_at": datetime.now().strftime("%H:%M:%S"),
            "total_capital": cap, "regime": "SIDEWAYS",
            "premarket": {}, "risk_state": {},
            "pools": {n: {"positions": [], "closed": [], "pnl": 0} for n in POOL_NAMES},
            "summary": {"total_pnl": 0, "trades": 0, "wins": 0, "losses": 0,
                        "longs": 0, "shorts": 0, "long_pnl": 0, "short_pnl": 0,
                        "scan_count": 0, "rescore_count": 0},
            "last_rescore_time": None, "last_signals": [],
            "direction_budget": DIRECTION_BUDGET.get("SIDEWAYS", {"long": 0.5, "short": 0.5})}


def _load_active_positions():
    if ACTIVE_POS_FILE.exists():
        try:
            return json.loads(ACTIVE_POS_FILE.read_text()).get("positions", {})
        except (json.JSONDecodeError, KeyError): pass
    return {}


def _save_active_positions(state):
    positions = {}
    for pool_name in MULTI_DAY_POOLS:
        pos_list = state["pools"].get(pool_name, {}).get("positions", [])
        if pos_list: positions[pool_name] = pos_list
    ACTIVE_POS_FILE.write_text(json.dumps(
        {"saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "positions": positions},
        indent=2, default=str))


def load_state():
    today = datetime.now().strftime("%Y-%m-%d")
    f = _state_file()
    if f.exists():
        s = json.loads(f.read_text())
        if s.get("date") == today: return s
        log("  NEW DAY -- resetting INTRADAY, keeping multi-day positions")
    balance = _get_carry_forward_balance()
    s = fresh_state(capital=balance)
    active = _load_active_positions()
    restored = 0
    for pool_name in MULTI_DAY_POOLS:
        positions = active.get(pool_name, [])
        if positions:
            s["pools"][pool_name]["positions"] = positions
            restored += len(positions)
            log(f"  Restored {len(positions)} {pool_name} positions")
    if restored: log(f"  Total restored: {restored} multi-day positions")
    return s


def save_state(s):
    _state_file().write_text(json.dumps(s, indent=2, default=str))
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
        for pool_name in MULTI_DAY_POOLS:
            for pos in state["pools"].get(pool_name, {}).get("positions", []):
                try:
                    pm.deploy(pool_name, pos["symbol"], pos["qty"],
                              pos["entry_price"], pos["sl_price"], pos["target_price"])
                except Exception as e:
                    log(f"  [WARN] Failed to re-register {pos['symbol']} in {pool_name}: {e}")
    if RiskManager and pm:
        rm = RiskManager(pm, regime=regime, vix=get_vix())
        rm.reset_daily()
    return pm, rm


# ═══════════════════════════ PRE-MARKET ═══════════════════════════

def run_premarket(state):
    log(f"\n{'='*65}\n  v5.4 BI-DIRECTIONAL PRE-MARKET\n{'='*65}")
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
            log(f"  Regime: {state['regime']} (score={regime_data.get('score', 0)})")
            # Update direction budget based on regime
            state["direction_budget"] = DIRECTION_BUDGET.get(
                state["regime"], {"long": 0.5, "short": 0.5})
            db = state["direction_budget"]
            log(f"  Direction budget: {db['long']*100:.0f}% LONG / {db['short']*100:.0f}% SHORT")
            if old_regime != state["regime"]:
                _tg_alert(f"*v5.4 REGIME CHANGE*\n{old_regime} -> {state['regime']}\n"
                          f"Long: {db['long']*100:.0f}% | Short: {db['short']*100:.0f}%")
        except Exception as e:
            log(f"  Regime failed: {e}"); state["regime"] = "SIDEWAYS"
    vix = get_vix()
    log(f"  VIX: {vix:.1f}")
    return regime_data, premarket, vix


# ═══════════════════════════ TELEGRAM ═══════════════════════════

def _tg_alert(msg):
    try:
        from prototype.v5.telegram_bot import send_alert
        send_alert(msg)
    except Exception: pass

def _tg_entry(trade):
    try:
        from prototype.v5.telegram_bot import alert_entry
        alert_entry(trade)
    except Exception: pass

def _tg_exit(trade):
    try:
        from prototype.v5.telegram_bot import alert_exit
        alert_exit(trade)
    except Exception: pass


# ═══════════════════════════ DEPLOY (BI-DIRECTIONAL) ═══════════════════════════

def deploy_signals(state, pm, rm, signals):
    """Deploy both LONG and SHORT signals with regime-weighted budgets."""
    if not pm or not signals: return 0
    held = {pos["symbol"] for pd in state["pools"].values() for pos in pd["positions"]}
    db = state.get("direction_budget", {"long": 0.5, "short": 0.5})
    count = 0

    for sig in signals:
        if sig["direction"] not in ("BUY", "SELL"): continue
        sym = sig["symbol"]
        is_short = sig["direction"] == "SELL"

        # Pool assignment: shorts can go to SWING too (v5 only allowed INTRADAY)
        pool_name = sig.get("pool", "INTRADAY")
        if is_short and pool_name not in SHORT_ALLOWED_POOLS:
            pool_name = "SWING"  # Promote short to SWING for multi-day holding

        if sym in held or pool_name not in state["pools"] or pool_name == "NONE": continue
        if rm:
            ok, reason = rm.check_can_trade(pool_name, sym)
            if not ok: continue
        pool = pm.pools.get(pool_name)
        if not pool: continue

        # Direction-weighted budget
        full_budget = pm.get_pool_budget(pool_name)
        direction_weight = db["short"] if is_short else db["long"]
        budget = full_budget * direction_weight
        if budget < 10000: continue

        price = sig.get("entry_price", sig.get("price", 0))
        if price <= 0: continue

        base = budget * 0.15
        sized = rm.get_position_size(pool_name, base) if rm else base
        qty = max(1, int(min(sized, budget) / price))
        cost = qty * price
        sl = sig.get("sl_price", price * (0.985 if not is_short else 1.015))
        tgt = sig.get("target_price", price * (1.02 if not is_short else 0.98))
        pos_type = "SHORT" if is_short else "LONG"

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
        tag = "SHORT" if is_short else "LONG "
        log(f"  {tag} {sym:>12} x{qty:<4d} @{price:.2f} SL:{sl:.2f} TGT:{tgt:.2f} [{pool_name}]")
        _tg_entry({"symbol": sym, "direction": sig["direction"], "position_type": pos_type,
                    "entry_price": price, "sl_price": sl, "target_price": tgt,
                    "qty": qty, "pool": pool_name, "score": sig.get("score", 0),
                    "regime": state.get("regime", "?")})
    if count:
        longs = sum(1 for s in signals if s["direction"] == "BUY" and s["symbol"] in held)
        shorts = sum(1 for s in signals if s["direction"] == "SELL" and s["symbol"] in held)
        log(f"  Deployed {count} positions (direction budget: {db['long']*100:.0f}%L/{db['short']*100:.0f}%S)")
    return count


# ═══════════════════════════ CLOSE (with correct short P&L) ═══════════════════════════

def close_position(state, pm, rm, pool_name, pos, exit_price, reason):
    sym, is_short = pos["symbol"], pos.get("position_type") == "SHORT"
    if is_short:
        pnl = (pos["entry_price"] - exit_price) * pos["qty"]
        pnl_pct = (pos["entry_price"] - exit_price) / pos["entry_price"] * 100
    else:
        pnl = (exit_price - pos["entry_price"]) * pos["qty"]
        pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100

    # Fix: pass correct P&L to PoolManager (v5 bug: PM uses long-only formula)
    if pm:
        try:
            pm.close_position(pool_name, sym, exit_price, reason)
            # Correct the PM's internal P&L tracking for shorts
            if is_short:
                wrong_pnl = (exit_price - pos["entry_price"]) * pos["qty"]
                correction = pnl - wrong_pnl
                pool_obj = pm.pools.get(pool_name)
                if pool_obj:
                    pool_obj.capital += correction
                    pool_obj.daily_pnl += correction
                    pm.total_capital += correction
        except Exception: pass
    if rm: rm.record_trade_result(pool_name, sym, pnl)

    state["pools"][pool_name]["closed"].append({
        "symbol": sym, "entry_price": pos["entry_price"], "exit_price": round(exit_price, 2),
        "qty": pos["qty"], "entry_time": pos.get("entry_time", ""),
        "exit_time": datetime.now().strftime("%H:%M:%S"),
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "reason": reason,
        "position_type": pos.get("position_type", "LONG"), "pool": pool_name})
    state["pools"][pool_name]["pnl"] += pnl
    state["pools"][pool_name]["positions"] = [
        p for p in state["pools"][pool_name]["positions"] if p["symbol"] != sym]
    s = state["summary"]
    s["total_pnl"] += pnl; s["trades"] += 1
    s["wins" if pnl > 0 else "losses"] += 1
    if is_short:
        s["shorts"] = s.get("shorts", 0) + 1
        s["short_pnl"] = s.get("short_pnl", 0) + pnl
    else:
        s["longs"] = s.get("longs", 0) + 1
        s["long_pnl"] = s.get("long_pnl", 0) + pnl

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
    longs_open = sum(1 for _, p in all_pos if p.get("position_type") != "SHORT")
    shorts_open = sum(1 for _, p in all_pos if p.get("position_type") == "SHORT")
    log(f"\n{'='*65}\n  SCAN #{state['summary']['scan_count']} | {len(all_pos)} pos ({longs_open}L/{shorts_open}S)\n{'='*65}")

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
    s = state["summary"]
    log(f"\n  Realized: {_fmt(s['total_pnl'])} (L:{_fmt(s.get('long_pnl',0))} S:{_fmt(s.get('short_pnl',0))}) | Unrealized: {_fmt(unrealized)}")


# ═══════════════════════════ RESCORE ═══════════════════════════

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

    # Count directions
    buys = sum(1 for s in new_sigs if s["direction"] == "BUY")
    sells = sum(1 for s in new_sigs if s["direction"] == "SELL")
    log(f"  Signals: {buys} BUY / {sells} SELL / {len(new_sigs)-buys-sells} HOLD")

    # Flip check: exit positions whose signals reversed
    for pn, pd in state["pools"].items():
        for pos in list(pd["positions"]):
            sym, is_short = pos["symbol"], pos.get("position_type") == "SHORT"
            nd = new_map.get(sym, {}).get("direction", "HOLD")
            exit_it = (not is_short and nd == "SELL") or (is_short and nd == "BUY")
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
    multi_day_count = sum(len(state["pools"].get(p, {}).get("positions", [])) for p in MULTI_DAY_POOLS)
    if multi_day_count:
        _save_active_positions(state)
        log(f"  Saved {multi_day_count} multi-day positions (incl. swing shorts)")


# ═══════════════════════════ DISPLAY ═══════════════════════════

def print_status(state):
    regime = state.get("regime", "?")
    gap = state.get("premarket", {}).get("gap_prediction", {})
    vix, s = get_vix(), state.get("summary", {})
    db = state.get("direction_budget", {"long": 0.5, "short": 0.5})
    C = {"BULL": "\033[92m", "BEAR": "\033[91m", "SIDEWAYS": "\033[93m"}
    R = "\033[0m"
    print(f"\n{'='*65}")
    print(f"  v5.4 BI-DIRECTIONAL  |  {state.get('date','today')}  |  Capital: {_fmt(TOTAL_CAPITAL)}")
    print(f"  Regime: {C.get(regime,'')}{regime}{R}  |  VIX: {vix:.1f}  |  "
          f"Budget: {db.get('long',0.5)*100:.0f}%L/{db.get('short',0.5)*100:.0f}%S")
    print(f"{'='*65}")
    total_open = 0
    for pn in POOL_NAMES:
        pd = state["pools"].get(pn, {}); pos = pd.get("positions", [])
        if not pos and not pd.get("closed"): continue
        longs = [p for p in pos if p.get("position_type") != "SHORT"]
        shorts = [p for p in pos if p.get("position_type") == "SHORT"]
        total_open += len(pos)
        cnt = f"{len(pos)} pos"
        if longs or shorts: cnt += f" ({len(longs)}L/{len(shorts)}S)"
        print(f"\n  {pn} ({cnt}) | P&L: {_fmt(pd.get('pnl', 0))}")
        for p in pos:
            tag = "SHORT" if p.get("position_type") == "SHORT" else "LONG "
            t = " [T]" if p.get("trailing_activated") else ""
            edate = f" ({p['entry_date']})" if p.get("entry_date") and pn in MULTI_DAY_POOLS else ""
            print(f"    {tag} {p['symbol']:>12} x{p['qty']:<4d} @{p['entry_price']:.2f} "
                  f"SL:{p['sl_price']:.2f} TGT:{p['target_price']:.2f}{t}{edate}")
    all_cl = [t for pd in state["pools"].values() for t in pd.get("closed", [])]
    if all_cl:
        w = sum(1 for t in all_cl if t["pnl"] > 0)
        l_cl = [t for t in all_cl if t.get("position_type") != "SHORT"]
        s_cl = [t for t in all_cl if t.get("position_type") == "SHORT"]
        print(f"\n  CLOSED: {len(all_cl)} trades ({w}W/{len(all_cl)-w}L)")
        print(f"    Longs:  {len(l_cl)} trades | {_fmt(s.get('long_pnl',0))}")
        print(f"    Shorts: {len(s_cl)} trades | {_fmt(s.get('short_pnl',0))}")
        print(f"    Total:  {_fmt(s.get('total_pnl',0))}")
    elif not total_open: print("\n  No trades yet")
    print(f"{'='*65}")


def print_summary(state):
    s = state.get("summary", {}); pnl = s.get("total_pnl", 0)
    db = state.get("direction_budget", {"long": 0.5, "short": 0.5})
    tr = s.get("trades", 0); w = s.get("wins", 0)
    print(f"\nv5.4 BI-DIRECTIONAL | {state.get('date','today')} | {_fmt(TOTAL_CAPITAL)} | "
          f"Regime: {state.get('regime','?')} | Budget: {db.get('long',0.5)*100:.0f}%L/{db.get('short',0.5)*100:.0f}%S")
    print(f"P&L: {_fmt(pnl)} ({pnl/TOTAL_CAPITAL*100:+.2f}%)")
    if tr:
        print(f"Trades: {tr} | Wins: {w} ({w/tr*100:.0f}%) | L:{s.get('longs',0)} S:{s.get('shorts',0)}")
        print(f"Long P&L:  {_fmt(s.get('long_pnl',0))}")
        print(f"Short P&L: {_fmt(s.get('short_pnl',0))}")


# ═══════════════════════════ EOD ═══════════════════════════

def generate_report(state):
    today = datetime.now().strftime("%Y-%m-%d")
    path = TRADE_DIR / f"{today}_report.md"
    all_cl = [t for pd in state["pools"].values() for t in pd.get("closed", [])]
    s = state.get("summary", {}); pp = s.get("total_pnl", 0) / TOTAL_CAPITAL * 100
    wr = sum(1 for t in all_cl if t["pnl"] > 0) / len(all_cl) * 100 if all_cl else 0
    db = state.get("direction_budget", {"long": 0.5, "short": 0.5})
    lines = [f"# v5.4 Bi-Directional Report -- {today}\n",
             "## Summary\n", "| Metric | Value |", "|--------|-------|",
             f"| Engine | v5.4 bi-directional |",
             f"| Capital | {_fmt(TOTAL_CAPITAL)} |",
             f"| Regime | {state.get('regime','?')} |",
             f"| Direction | {db.get('long',0.5)*100:.0f}% Long / {db.get('short',0.5)*100:.0f}% Short |",
             f"| **Net P&L** | **{_fmt(s.get('total_pnl',0))} ({pp:+.2f}%)** |",
             f"| Long P&L | {_fmt(s.get('long_pnl',0))} |",
             f"| Short P&L | {_fmt(s.get('short_pnl',0))} |",
             f"| Trades | {s.get('trades',0)} (L:{s.get('longs',0)} S:{s.get('shorts',0)}) |",
             f"| Win Rate | {wr:.0f}% |", "",
             "## Trades\n", "| # | Type | Pool | Stock | Entry | Exit | P&L | Reason |",
             "|---|------|------|-------|-------|------|-----|--------|"]
    for i, t in enumerate(all_cl, 1):
        lines.append(f"| {i} | {t.get('position_type','LONG')} | {t.get('pool','')} | "
                     f"{t['symbol']} | {t['entry_price']:.2f} | {t['exit_price']:.2f} | "
                     f"Rs {t['pnl']:+,.0f} | {t['reason']} |")
    path.write_text("\n".join(lines)); log(f"  Report: {path}")


# ═══════════════════════════ MAIN LOOP ═══════════════════════════

def run():
    log(f"{'='*65}\n  v5.4 BI-DIRECTIONAL ENGINE | {_fmt(TOTAL_CAPITAL)}\n"
        f"  Long+Short | Regime-Weighted | Scan {SCAN_INTERVAL_MIN}m | Rescore {RESCORE_INTERVAL_MIN}m\n"
        f"  Exit {FORCE_EXIT_HOUR}:{FORCE_EXIT_MIN:02d} | Short pools: {', '.join(SHORT_ALLOWED_POOLS)}\n{'='*65}")
    state = load_state()
    pm, rm = init_managers(state)
    regime_data, premarket, vix = run_premarket(state)
    if pm: pm.set_regime(state["regime"])
    if rm: rm.set_vix(vix); rm.regime = state["regime"]
    total_open = sum(len(pd.get("positions", [])) for pd in state["pools"].values())
    generate_signals = _mods.get("signals")
    if total_open == 0 and generate_signals:
        log("\n--- INITIAL DEPLOYMENT (BI-DIRECTIONAL) ---")
        try:
            sigs = generate_signals(state.get("regime", "SIDEWAYS"))
            buys = sum(1 for s in sigs if s["direction"] == "BUY")
            sells = sum(1 for s in sigs if s["direction"] == "SELL")
            log(f"  Signal engine: {buys} BUY / {sells} SELL / {len(sigs)-buys-sells} HOLD")
            state["last_signals"] = sigs
            deploy_signals(state, pm, rm, sigs)
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
        scan_positions(state, pm, rm)
        rescore_and_redeploy(state, pm, rm)
        save_state(state)

    log(f"\n{'='*65}\n  END OF DAY — v5.4 BI-DIRECTIONAL\n{'='*65}")
    print_status(state); generate_report(state); _save_carry_forward(state)
    s = state.get("summary", {})
    _tg_alert(f"*v5.4 Daily Summary*\n"
              f"P&L: Rs {s.get('total_pnl',0):+,.0f}\n"
              f"Long P&L: Rs {s.get('long_pnl',0):+,.0f}\n"
              f"Short P&L: Rs {s.get('short_pnl',0):+,.0f}\n"
              f"Trades: {s.get('trades',0)} ({s.get('wins',0)}W/{s.get('losses',0)}L)\n"
              f"Regime: {state.get('regime','?')}")
    save_state(state)
    if s.get("trades"):
        log(f"\n  FINAL: {_fmt(s['total_pnl'])} | L:{_fmt(s.get('long_pnl',0))} S:{_fmt(s.get('short_pnl',0))} | "
            f"{s['trades']}t ({s.get('longs',0)}L/{s.get('shorts',0)}S) | {s['wins']}W/{s['losses']}L")


if __name__ == "__main__":
    if "--status" in sys.argv: print_status(load_state())
    elif "--summary" in sys.argv: print_summary(load_state())
    else: run()
