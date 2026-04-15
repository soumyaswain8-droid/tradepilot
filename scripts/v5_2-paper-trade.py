#!/usr/bin/env python3
"""
TradePilot v5.2 Paper Trading Engine — F&O Options Experiment
==============================================================
Separate experiment alongside v4 (equity intraday) and v5 (multi-horizon).
Own capital pool: Rs 10,00,000. Carry-forward balance daily.

Strategies deployed based on v5 regime detection:
    1. Protective Puts     (BEAR regime)
    2. Straddle Selling    (SIDEWAYS + expiry week)
    3. Directional Options (high-confidence BULL/BEAR)
    4. Covered Calls       (on v5 SWING holdings — future)

Usage:
    python3 scripts/v5_2-paper-trade.py              # Full auto-pilot
    python3 scripts/v5_2-paper-trade.py --status      # Current positions
    python3 scripts/v5_2-paper-trade.py --summary     # P&L summary
"""
import json
import sys
import time
import warnings
from datetime import datetime, date, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).parent.parent
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades" / "v5_2"
LOG_DIR = PROJECT_ROOT / "logs"
sys.path.insert(0, str(PROJECT_ROOT))

LOG_FILE = LOG_DIR / "v5_2-paper-trade.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

INITIAL_CAPITAL = 1_000_000  # Rs 10L — same as v4/v5 for fair comparison
CARRY_FILE = TRADE_DIR / "carry_forward_v5_2.json"
SCAN_INTERVAL_MIN = 10
FORCE_EXIT_HOUR = 15
FORCE_EXIT_MIN = 15

# ═══════════════════════════ IMPORTS (graceful) ═══════════════════════════

def _import_module(mod_path, attr_name):
    try:
        import importlib
        m = importlib.import_module(mod_path)
        return getattr(m, attr_name)
    except (ImportError, AttributeError) as e:
        print(f"[WARN] {mod_path}.{attr_name}: {e}")
        return None

detect_regime = _import_module("prototype.v5.regime_detector", "detect_regime")
generate_fo_signals = _import_module("prototype.v5_2.options_engine", "generate_fo_signals")
analyze_options_opportunity = _import_module("prototype.v5_2.options_engine", "analyze_options_opportunity")
estimate_premium = _import_module("prototype.v5_2.options_engine", "estimate_premium")
calculate_option_pnl = _import_module("prototype.v5_2.options_engine", "calculate_option_pnl")
_is_expiry_week = _import_module("prototype.v5_2.options_engine", "_is_expiry_week")
_days_to_expiry = _import_module("prototype.v5_2.options_engine", "_days_to_expiry")


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def _fmt(val):
    return f"Rs {val/1_00_000:,.2f}L" if abs(val) >= 1_00_000 else f"Rs {val:,.0f}"


# ═══════════════════════════ STATE MANAGEMENT ═══════════════════════════

def load_carry_forward() -> dict:
    """Load carry-forward state or initialize fresh."""
    if CARRY_FILE.exists():
        try:
            data = json.loads(CARRY_FILE.read_text())
            return data
        except Exception:
            pass
    return {
        "capital": INITIAL_CAPITAL,
        "total_pnl": 0,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "best_day": 0,
        "worst_day": 0,
        "history": [],
        "start_date": date.today().isoformat(),
    }


def save_carry_forward(state: dict):
    CARRY_FILE.write_text(json.dumps(state, indent=2, default=str))


def load_today_state() -> dict:
    """Load today's trading state or create fresh."""
    today_file = TRADE_DIR / f"{date.today().isoformat()}.json"
    if today_file.exists():
        try:
            return json.loads(today_file.read_text())
        except Exception:
            pass

    carry = load_carry_forward()
    return {
        "date": date.today().isoformat(),
        "capital": carry["capital"],
        "starting_capital": carry["capital"],
        "open_positions": [],
        "closed_positions": [],
        "signals_generated": [],
        "regime": None,
        "vix": None,
        "nifty_price": None,
        "day_pnl": 0,
        "status": "initialized",
        "timestamps": {"start": datetime.now().isoformat()},
    }


def save_today_state(state: dict):
    today_file = TRADE_DIR / f"{date.today().isoformat()}.json"
    today_file.write_text(json.dumps(state, indent=2, default=str))


# ═══════════════════════════ NIFTY PRICE ═══════════════════════════

def get_nifty_live() -> float:
    """Get current Nifty price via yfinance."""
    try:
        import yfinance as yf
        data = yf.download("^NSEI", period="1d", interval="1m", progress=False)
        if not data.empty:
            close = data["Close"]
            if hasattr(close, "iloc"):
                val = close.iloc[-1]
                if hasattr(val, "item"):
                    return round(float(val.item()), 2)
                return round(float(val), 2)
    except Exception:
        pass
    return 0.0


def get_vix_live() -> float:
    """Get current India VIX via yfinance."""
    try:
        import yfinance as yf
        data = yf.download("^INDIAVIX", period="5d", progress=False)
        if not data.empty:
            close = data["Close"]
            if hasattr(close, "iloc"):
                val = close.iloc[-1]
                if hasattr(val, "item"):
                    return round(float(val.item()), 2)
                return round(float(val), 2)
    except Exception:
        pass
    return 18.0  # Default


# ═══════════════════════════ POSITION MANAGEMENT ═══════════════════════════

def deploy_signals(state: dict, signals: list) -> dict:
    """Deploy F&O signals as paper positions."""
    for sig in signals:
        pos = {
            "id": f"FO-{len(state['open_positions'])+1:03d}",
            "strategy": sig["strategy"],
            "instrument": sig["instrument"],
            "option_type": sig["option_type"],
            "strike": sig["strike"],
            "action": sig["action"],
            "lot_size": sig["lot_size"],
            "lots": sig["lots"],
            "qty": sig["qty"],
            "entry_premium": sig["premium"],
            "current_premium": sig["premium"],
            "sl_premium": sig.get("sl_premium", 0),
            "target_premium": sig.get("target_premium", 0),
            "cost": sig.get("cost", 0),
            "credit": sig.get("credit", 0),
            "expiry": sig["expiry"],
            "entry_time": datetime.now().isoformat(),
            "entry_nifty": state.get("nifty_price", 0),
            "pnl": 0,
            "status": "OPEN",
        }
        state["open_positions"].append(pos)

        action_str = f"{sig['action']} NIFTY {sig['strike']}{sig['option_type']} x{sig['qty']}"
        if sig["cost"] > 0:
            log(f"  DEPLOYED: {action_str} @Rs {sig['premium']:.1f} Cost: {_fmt(sig['cost'])} [{sig['strategy']}]")
        else:
            log(f"  DEPLOYED: {action_str} @Rs {sig['premium']:.1f} Credit: {_fmt(sig.get('credit',0))} [{sig['strategy']}]")

    state["signals_generated"] = signals
    return state


def update_positions(state: dict, nifty_now: float, vix: float) -> dict:
    """Update option premiums and check SL/target for all open positions."""
    if not estimate_premium:
        return state

    dte = _days_to_expiry() if _days_to_expiry else 1.0
    still_open = []

    for pos in state["open_positions"]:
        # Estimate current premium based on new Nifty price
        new_prem = estimate_premium(
            nifty_now, pos["strike"], pos["option_type"], vix, dte
        )
        pos["current_premium"] = round(new_prem, 2)

        # Calculate unrealized P&L
        if calculate_option_pnl:
            pos["pnl"] = calculate_option_pnl(
                pos["entry_premium"], new_prem, pos["qty"], pos["action"]
            )

        # Check SL
        hit_sl = False
        hit_target = False

        if pos["action"] == "BUY":
            if pos["sl_premium"] > 0 and new_prem <= pos["sl_premium"]:
                hit_sl = True
            if pos["target_premium"] > 0 and new_prem >= pos["target_premium"]:
                hit_target = True
        else:  # SELL
            # For sellers, loss = premium going UP
            if pos["sl_premium"] > 0 and new_prem >= pos["sl_premium"]:
                hit_sl = True
            # Target = premium going to 0 (full decay)
            if new_prem <= pos["entry_premium"] * 0.2:
                hit_target = True

        if hit_sl or hit_target:
            exit_reason = "SL_HIT" if hit_sl else "TARGET_HIT"
            _close_position(state, pos, new_prem, exit_reason)
        else:
            still_open.append(pos)

    state["open_positions"] = still_open
    return state


def _close_position(state: dict, pos: dict, exit_premium: float, reason: str):
    """Close a position and record P&L."""
    pos["exit_premium"] = exit_premium
    pos["exit_time"] = datetime.now().isoformat()
    pos["exit_reason"] = reason
    pos["exit_nifty"] = state.get("nifty_price", 0)

    if calculate_option_pnl:
        pos["pnl"] = calculate_option_pnl(
            pos["entry_premium"], exit_premium, pos["qty"], pos["action"]
        )
    pos["status"] = "CLOSED"

    state["closed_positions"].append(pos)
    state["day_pnl"] += pos["pnl"]

    result = "WIN" if pos["pnl"] > 0 else "LOSS"
    pnl_pct = (pos["pnl"] / max(pos["cost"], pos["credit"], 1)) * 100
    log(f"  CLOSED [{reason}]: {pos['action']} NIFTY {pos['strike']}{pos['option_type']}"
        f" @{pos['entry_premium']:.1f}->{exit_premium:.1f}"
        f" P&L: {_fmt(pos['pnl'])} ({pnl_pct:+.1f}%) [{result}]")


def force_close_all(state: dict, nifty_now: float, vix: float) -> dict:
    """Close all open positions at 3:15 PM."""
    if not estimate_premium:
        return state

    dte = 0.01  # Nearly expired at EOD
    for pos in list(state["open_positions"]):
        exit_prem = estimate_premium(
            nifty_now, pos["strike"], pos["option_type"], vix, dte
        )
        _close_position(state, pos, exit_prem, "EOD_EXIT")

    state["open_positions"] = []
    return state


# ═══════════════════════════ EOD SETTLEMENT ═══════════════════════════

def settle_day(state: dict) -> dict:
    """Settle the day: update carry forward, save history."""
    carry = load_carry_forward()
    carry["capital"] += state["day_pnl"]
    carry["total_pnl"] += state["day_pnl"]
    carry["total_trades"] += len(state["closed_positions"])

    wins = sum(1 for p in state["closed_positions"] if p["pnl"] > 0)
    losses = sum(1 for p in state["closed_positions"] if p["pnl"] <= 0)
    carry["wins"] += wins
    carry["losses"] += losses

    if state["day_pnl"] > carry.get("best_day", 0):
        carry["best_day"] = state["day_pnl"]
    if state["day_pnl"] < carry.get("worst_day", 0):
        carry["worst_day"] = state["day_pnl"]

    carry["history"].append({
        "date": state["date"],
        "pnl": state["day_pnl"],
        "trades": len(state["closed_positions"]),
        "wins": wins,
        "losses": losses,
        "capital_after": carry["capital"],
        "regime": state.get("regime", "?"),
    })

    # Keep last 60 days of history
    carry["history"] = carry["history"][-60:]
    save_carry_forward(carry)

    state["status"] = "settled"
    state["timestamps"]["end"] = datetime.now().isoformat()
    save_today_state(state)

    return state


# ═══════════════════════════ DISPLAY ═══════════════════════════

def print_status(state: dict):
    """Print current v5.2 status."""
    carry = load_carry_forward()
    regime = state.get("regime", "?")
    vix = state.get("vix", "?")
    nifty = state.get("nifty_price", "?")
    capital = carry["capital"]

    color = {"BULL": "\033[92m", "BEAR": "\033[91m", "SIDEWAYS": "\033[93m"}
    reset = "\033[0m"
    c = color.get(regime, "")

    # Expiry info
    expiry_str = "Expiry week" if (_is_expiry_week and _is_expiry_week()) else "Non-expiry"
    dte = _days_to_expiry() if _days_to_expiry else "?"

    print(f"\n{'='*64}")
    print(f"  v5.2 F&O EXPERIMENT  |  {state.get('date', date.today())}  |  Capital: {_fmt(capital)}")
    print(f"  Regime: {c}{regime}{reset}  |  VIX: {vix}  |  {expiry_str} (DTE: {dte})")
    print(f"{'='*64}")

    # Open positions
    open_pos = state.get("open_positions", [])
    if open_pos:
        print(f"\n  OPEN ({len(open_pos)}):")
        for p in open_pos:
            pnl_str = f"{_fmt(p['pnl'])}" if p["pnl"] != 0 else "---"
            act_color = "\033[92m" if p["action"] == "BUY" else "\033[91m"
            print(f"    {act_color}{p['action']:4s}{reset} NIFTY {p['strike']}{p['option_type']}"
                  f"  x{p['qty']}  @Rs {p['entry_premium']:.0f}"
                  f"  Now: Rs {p['current_premium']:.0f}"
                  f"  P&L: {pnl_str}  [{p['strategy']}]")
    else:
        print(f"\n  OPEN (0): No positions")

    # Closed positions
    closed = state.get("closed_positions", [])
    if closed:
        wins = sum(1 for p in closed if p["pnl"] > 0)
        losses = len(closed) - wins
        print(f"\n  CLOSED ({len(closed)}): {wins}W/{losses}L")
        for p in closed:
            result = "\033[92mWIN \033[0m" if p["pnl"] > 0 else "\033[91mLOSS\033[0m"
            pnl_pct = (p["pnl"] / max(p.get("cost", 1), p.get("credit", 1), 1)) * 100
            print(f"    {result} NIFTY {p['strike']}{p['option_type']}"
                  f"  {p['qty']}x @{p['entry_premium']:.0f}->{p.get('exit_premium',0):.0f}"
                  f"  {_fmt(p['pnl'])} ({pnl_pct:+.1f}%)"
                  f"  [{p['strategy']}]")

    # Day P&L
    print(f"\n  Day P&L: {_fmt(state.get('day_pnl', 0))}  |  Capital: {_fmt(capital)}")
    print(f"{'='*64}\n")


def print_summary():
    """Print cumulative P&L summary across all days."""
    carry = load_carry_forward()
    total_trades = carry.get("total_trades", 0)
    wins = carry.get("wins", 0)
    losses = carry.get("losses", 0)
    win_rate = (wins / max(total_trades, 1)) * 100
    total_pnl = carry.get("total_pnl", 0)
    capital = carry.get("capital", INITIAL_CAPITAL)
    roi = (total_pnl / INITIAL_CAPITAL) * 100

    print(f"\n{'='*64}")
    print(f"  v5.2 F&O EXPERIMENT — CUMULATIVE SUMMARY")
    print(f"  Since: {carry.get('start_date', '?')}")
    print(f"{'='*64}")
    print(f"  Starting Capital:  {_fmt(INITIAL_CAPITAL)}")
    print(f"  Current Capital:   {_fmt(capital)}")
    print(f"  Total P&L:         {_fmt(total_pnl)} ({roi:+.2f}%)")
    print(f"  Total Trades:      {total_trades}")
    print(f"  Win Rate:          {win_rate:.1f}% ({wins}W / {losses}L)")
    print(f"  Best Day:          {_fmt(carry.get('best_day', 0))}")
    print(f"  Worst Day:         {_fmt(carry.get('worst_day', 0))}")

    history = carry.get("history", [])
    if history:
        print(f"\n  {'Date':<12} {'Regime':<10} {'P&L':>12} {'Trades':>8} {'W/L':>8} {'Capital':>14}")
        print(f"  {'-'*66}")
        for h in history[-10:]:
            wl = f"{h.get('wins',0)}W/{h.get('losses',0)}L"
            print(f"  {h['date']:<12} {h.get('regime','?'):<10} {_fmt(h['pnl']):>12}"
                  f" {h.get('trades',0):>8} {wl:>8} {_fmt(h.get('capital_after', 0)):>14}")

    print(f"{'='*64}\n")


# ═══════════════════════════ MAIN LOOP ═══════════════════════════

def run_autopilot():
    """Main auto-pilot loop: detect regime, deploy options, monitor, settle."""
    log("=" * 60)
    log("  TradePilot v5.2 — F&O Options Experiment")
    log(f"  Date: {date.today().isoformat()}")
    log("=" * 60)

    state = load_today_state()

    if state["status"] == "settled":
        log("Today already settled. Use --status or --summary.")
        print_status(state)
        return

    # Step 1: Detect regime
    log("[1/4] Detecting market regime...")
    if detect_regime:
        try:
            regime_result = detect_regime()
            state["regime"] = regime_result.get("regime", "SIDEWAYS")
            state["nifty_price"] = regime_result.get("nifty_close", 0)
            vix_ind = regime_result.get("indicators", {}).get("india_vix", {})
            state["vix"] = vix_ind.get("value", 18.0)
            if state["vix"] is None or (isinstance(state["vix"], float) and state["vix"] != state["vix"]):
                state["vix"] = 18.0
            log(f"  Regime: {state['regime']} | Nifty: {state['nifty_price']} | VIX: {state['vix']}")
        except Exception as e:
            log(f"  [WARN] Regime detection failed: {e}")
            state["regime"] = "SIDEWAYS"
            state["vix"] = get_vix_live()
            state["nifty_price"] = get_nifty_live()
    else:
        state["regime"] = "SIDEWAYS"
        state["vix"] = get_vix_live()
        state["nifty_price"] = get_nifty_live() or 23500

    # Refresh Nifty live if regime gave stale data
    if state["nifty_price"] == 0:
        state["nifty_price"] = get_nifty_live() or 23500

    save_today_state(state)

    # Step 2: Generate and deploy F&O signals
    log("[2/4] Generating F&O signals...")
    if generate_fo_signals:
        regime_dict = {
            "regime": state["regime"],
            "score": regime_result.get("score", 0) if detect_regime else 0,
            "confidence": regime_result.get("confidence", 0.5) if detect_regime else 0.5,
        }
        signals = generate_fo_signals(
            regime_dict, state["vix"], state["nifty_price"],
            capital=state["capital"],
        )
        if signals:
            log(f"  Generated {len(signals)} signal(s)")
            state = deploy_signals(state, signals)
        else:
            log("  No signals — sitting out F&O today")
    else:
        log("  [WARN] options_engine not available")

    save_today_state(state)

    # Step 3: Monitor loop
    log("[3/4] Monitoring positions...")
    if not state["open_positions"]:
        log("  No positions to monitor")
    else:
        while True:
            now = datetime.now()

            # Force exit at 3:15 PM
            if now.hour >= FORCE_EXIT_HOUR and now.minute >= FORCE_EXIT_MIN:
                log("  3:15 PM — Force closing all positions")
                nifty_now = get_nifty_live() or state["nifty_price"]
                state["nifty_price"] = nifty_now
                state = force_close_all(state, nifty_now, state["vix"])
                break

            # Update premiums and check SL/target
            nifty_now = get_nifty_live()
            if nifty_now > 0:
                state["nifty_price"] = nifty_now
                state = update_positions(state, nifty_now, state["vix"])

            if not state["open_positions"]:
                log("  All positions closed (SL/target hit)")
                break

            save_today_state(state)

            # Wait for next scan
            log(f"  [{len(state['open_positions'])} open] Nifty: {state['nifty_price']}"
                f" | Day P&L: {_fmt(state['day_pnl'])}")
            time.sleep(SCAN_INTERVAL_MIN * 60)

    # Step 4: Settle
    log("[4/4] Settling day...")
    state = settle_day(state)

    log(f"  Day P&L: {_fmt(state['day_pnl'])}")
    log(f"  Capital: {_fmt(load_carry_forward()['capital'])}")
    log("  Done.")

    print_status(state)


# ═══════════════════════════ CLI ═══════════════════════════

def main():
    if "--status" in sys.argv:
        state = load_today_state()
        print_status(state)
    elif "--summary" in sys.argv:
        print_summary()
    else:
        run_autopilot()


if __name__ == "__main__":
    main()
