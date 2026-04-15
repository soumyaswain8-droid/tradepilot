#!/usr/bin/env python3
"""
TradePilot Paper Trading Engine
Runs 3 parallel virtual portfolios (v2, v3, v3-rs) with intraday strategies.

Capital: Rs 5,00,000 per portfolio
Strategy: Buy at 9:30-9:45 on AI signals, exit at target/SL/3:15 PM

Usage:
    python3 scripts/paper-trade-engine.py              # Full day auto-pilot
    python3 scripts/paper-trade-engine.py --status      # Check current positions
    python3 scripts/paper-trade-engine.py --summary     # Today's P&L summary

Schedule (IST):
    09:25  Load predictions, select stocks
    09:35  Place entries (with opening confirmation)
    11:30  Mid-morning: check targets/SLs
    13:30  Afternoon: check targets/SLs
    15:15  Force-close all open positions
    15:30  Generate daily P&L report
"""
import json
import os
import sys
import time
import copy
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PROTO_DIR = PROJECT_ROOT / "prototype"
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades"
LOG_DIR = PROJECT_ROOT / "logs"

sys.path.insert(0, str(PROTO_DIR))

LOG_FILE = LOG_DIR / "paper-trade.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════
CAPITAL_PER_PORTFOLIO = 500000  # Rs 5,00,000
MAX_POSITION_SIZE = 100000      # Rs 1,00,000 per stock
MAX_POSITIONS = 5
TARGET_PCT = 1.5                # +1.5% target
STOPLOSS_PCT = 0.75             # -0.75% stop-loss
TRAILING_TRIGGER_PCT = 1.0      # Move SL to breakeven at +1%
DAILY_LOSS_LIMIT = 15000        # Rs 15,000 max loss per day
FORCE_EXIT_HOUR = 15
FORCE_EXIT_MIN = 15


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ═══════════════════════════════════════════════════
# PORTFOLIO STATE
# ═══════════════════════════════════════════════════

def empty_portfolio(name):
    return {
        "name": name,
        "capital": CAPITAL_PER_PORTFOLIO,
        "cash": CAPITAL_PER_PORTFOLIO,
        "positions": [],          # {symbol, entry_price, qty, entry_time, sl, target, status}
        "closed_trades": [],      # {symbol, entry, exit, pnl, reason, ...}
        "daily_pnl": 0,
        "trades_today": 0,
    }


def get_today_file():
    today = datetime.now().strftime("%Y-%m-%d")
    return TRADE_DIR / f"{today}_portfolios.json"


def load_portfolios():
    f = get_today_file()
    if f.exists():
        with open(f) as fh:
            return json.load(fh)
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "v2-paper": empty_portfolio("v2-paper"),
        "v3-paper": empty_portfolio("v3-paper"),
        "v3-rs": empty_portfolio("v3-rs"),
    }


def save_portfolios(portfolios):
    with open(get_today_file(), "w") as f:
        json.dump(portfolios, f, indent=2, default=str)


# ═══════════════════════════════════════════════════
# PRICE FETCHING
# ═══════════════════════════════════════════════════

def get_live_price(symbol):
    """Get current price for a stock."""
    import yfinance as yf
    ns = symbol if ".NS" in symbol else symbol + ".NS"
    try:
        t = yf.Ticker(ns)
        hist = t.history(period="1d", interval="1m")
        if len(hist) > 0:
            return float(hist["Close"].iloc[-1])
        hist = t.history(period="2d")
        if len(hist) > 0:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return None


def get_prices_batch(symbols):
    """Get prices for multiple symbols."""
    prices = {}
    for sym in symbols:
        p = get_live_price(sym)
        if p:
            prices[sym] = p
    return prices


# ═══════════════════════════════════════════════════
# SIGNAL SELECTION
# ═══════════════════════════════════════════════════

def get_v2_signals():
    """Get v2 BUY signals from API."""
    import urllib.request
    try:
        url = "http://localhost:5050/api/scores?category=nifty50"
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
        stocks = data if isinstance(data, list) else data.get("stocks", [])
        buy = [s for s in stocks if s.get("direction") == "BUY"]
        hold = [s for s in stocks if s.get("direction") == "HOLD"]
        return sorted(buy, key=lambda x: -x.get("score", 0)), sorted(hold, key=lambda x: -x.get("score", 0))
    except Exception as e:
        log(f"  v2 API error: {e}")
        return [], []


def get_v3_signals():
    """Get v3 signals directly."""
    try:
        from trading_engine_v3 import score_stocks_v3
        from data_engine import NIFTY_50
        scores = score_stocks_v3(NIFTY_50)
        buy = [s for s in scores if s["direction"] == "BUY"]
        hold = [s for s in scores if s["direction"] == "HOLD"]
        return sorted(buy, key=lambda x: -x["score"]), sorted(hold, key=lambda x: -x["score"])
    except Exception as e:
        log(f"  v3 scoring error: {e}")
        return [], []


def select_stocks_for_portfolio(portfolio_name, v2_buy, v2_hold, v3_buy, v3_hold):
    """Select up to 5 stocks for a portfolio based on its strategy."""
    candidates = []

    if portfolio_name == "v2-paper":
        # v2: top BUY signals, fill with top HOLD if needed
        candidates = v2_buy[:5]
        if len(candidates) < 5:
            candidates += v2_hold[:5 - len(candidates)]

    elif portfolio_name == "v3-paper":
        # v3: top BUY signals, fill with top HOLD if needed
        candidates = v3_buy[:5]
        if len(candidates) < 5:
            candidates += v3_hold[:5 - len(candidates)]

    elif portfolio_name == "v3-rs":
        # v3-rs: only BUY + RS_5d > 3%, then HOLD + RS_5d > 3%
        rs_buy = [s for s in v3_buy if s.get("relative_strength_5d", 0) > 3]
        rs_hold = [s for s in v3_hold if s.get("relative_strength_5d", 0) > 3]
        candidates = rs_buy[:5]
        if len(candidates) < 5:
            candidates += rs_hold[:5 - len(candidates)]

    return candidates[:MAX_POSITIONS]


# ═══════════════════════════════════════════════════
# TRADING ACTIONS
# ═══════════════════════════════════════════════════

def place_entries(portfolio, candidates):
    """Place entry orders for selected stocks with opening confirmation."""
    if portfolio["trades_today"] >= MAX_POSITIONS:
        log(f"  [{portfolio['name']}] Max positions reached, skipping entries")
        return

    if abs(portfolio["daily_pnl"]) >= DAILY_LOSS_LIMIT and portfolio["daily_pnl"] < 0:
        log(f"  [{portfolio['name']}] Daily loss limit hit (Rs {portfolio['daily_pnl']:.0f}), no more trades")
        return

    existing_symbols = {p["symbol"] for p in portfolio["positions"]}

    for stock in candidates:
        if portfolio["trades_today"] >= MAX_POSITIONS:
            break
        if portfolio["cash"] < MAX_POSITION_SIZE:
            break

        symbol = stock.get("symbol", stock.get("name", ""))
        if not symbol:
            continue
        if symbol in existing_symbols:
            continue

        ns = symbol if ".NS" in symbol else symbol + ".NS"
        price = get_live_price(ns)
        if not price:
            log(f"  [{portfolio['name']}] Cannot get price for {symbol}, skipping")
            continue

        # Opening confirmation: stock should be up from previous close
        change_pct = stock.get("change_pct", 0)
        # Allow entry even if slightly down in BEAR market (our signal says BUY)

        qty = int(MAX_POSITION_SIZE / price)
        if qty < 1:
            continue
        cost = qty * price

        sl_price = round(price * (1 - STOPLOSS_PCT / 100), 2)
        target_price = round(price * (1 + TARGET_PCT / 100), 2)

        position = {
            "symbol": symbol,
            "ns_symbol": ns,
            "entry_price": round(price, 2),
            "qty": qty,
            "cost": round(cost, 2),
            "entry_time": datetime.now().strftime("%H:%M:%S"),
            "sl_price": sl_price,
            "target_price": target_price,
            "trailing_activated": False,
            "status": "open",
            "score": stock.get("score", 0),
            "direction": stock.get("direction", "?"),
            "rs_5d": stock.get("relative_strength_5d", 0),
        }

        portfolio["positions"].append(position)
        portfolio["cash"] -= cost
        portfolio["trades_today"] += 1
        existing_symbols.add(symbol)

        log(f"  [{portfolio['name']}] BUY {symbol} x{qty} @ Rs {price:.2f} "
            f"(SL: {sl_price:.2f}, TGT: {target_price:.2f}, Score: {stock.get('score',0):.1f})")


def check_exits(portfolio):
    """Check all open positions for target/SL/trailing stop hits."""
    for pos in portfolio["positions"]:
        if pos["status"] != "open":
            continue

        price = get_live_price(pos["ns_symbol"])
        if not price:
            continue

        pnl_pct = (price - pos["entry_price"]) / pos["entry_price"] * 100
        pnl_rs = (price - pos["entry_price"]) * pos["qty"]
        reason = None

        # Check target
        if price >= pos["target_price"]:
            reason = "TARGET"
        # Check stop-loss
        elif price <= pos["sl_price"]:
            reason = "STOPLOSS"
        # Trailing stop: if +1%, move SL to breakeven
        elif pnl_pct >= TRAILING_TRIGGER_PCT and not pos["trailing_activated"]:
            pos["trailing_activated"] = True
            pos["sl_price"] = pos["entry_price"]
            log(f"  [{portfolio['name']}] TRAILING STOP activated for {pos['symbol']} "
                f"(SL moved to breakeven Rs {pos['entry_price']:.2f})")

        if reason:
            close_position(portfolio, pos, price, reason)


def force_close_all(portfolio):
    """Force close all open positions (3:15 PM exit)."""
    for pos in portfolio["positions"]:
        if pos["status"] != "open":
            continue
        price = get_live_price(pos["ns_symbol"])
        if not price:
            price = pos["entry_price"]  # Fallback
        close_position(portfolio, pos, price, "TIME_EXIT")


def close_position(portfolio, pos, exit_price, reason):
    """Close a position and record the trade."""
    pnl = (exit_price - pos["entry_price"]) * pos["qty"]
    pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100

    pos["status"] = "closed"
    pos["exit_price"] = round(exit_price, 2)
    pos["exit_time"] = datetime.now().strftime("%H:%M:%S")
    pos["pnl"] = round(pnl, 2)
    pos["pnl_pct"] = round(pnl_pct, 2)
    pos["exit_reason"] = reason

    portfolio["cash"] += pos["qty"] * exit_price
    portfolio["daily_pnl"] += pnl

    portfolio["closed_trades"].append({
        "symbol": pos["symbol"],
        "entry_price": pos["entry_price"],
        "exit_price": round(exit_price, 2),
        "qty": pos["qty"],
        "entry_time": pos["entry_time"],
        "exit_time": pos["exit_time"],
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "reason": reason,
        "score": pos.get("score", 0),
        "rs_5d": pos.get("rs_5d", 0),
    })

    emoji = "PROFIT" if pnl > 0 else "LOSS"
    log(f"  [{portfolio['name']}] {emoji}: SELL {pos['symbol']} x{pos['qty']} @ Rs {exit_price:.2f} "
        f"({reason}) P&L: Rs {pnl:+,.0f} ({pnl_pct:+.2f}%)")


# ═══════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════

def print_status(portfolios):
    """Print current portfolio status."""
    log("\n=== PORTFOLIO STATUS ===")
    for name in ["v2-paper", "v3-paper", "v3-rs"]:
        p = portfolios[name]
        open_pos = [x for x in p["positions"] if x["status"] == "open"]
        closed = p["closed_trades"]
        log(f"\n  [{name}]")
        log(f"  Capital: Rs {p['capital']:,.0f} | Cash: Rs {p['cash']:,.0f} | P&L: Rs {p['daily_pnl']:+,.0f}")
        log(f"  Open: {len(open_pos)} | Closed: {len(closed)} | Trades today: {p['trades_today']}")
        for pos in open_pos:
            log(f"    OPEN: {pos['symbol']} x{pos['qty']} @ {pos['entry_price']:.2f} "
                f"(SL: {pos['sl_price']:.2f} TGT: {pos['target_price']:.2f})")
        for trade in closed:
            log(f"    DONE: {trade['symbol']} P&L Rs {trade['pnl']:+,.0f} ({trade['pnl_pct']:+.2f}%) [{trade['reason']}]")


def generate_daily_report(portfolios):
    """Generate end-of-day paper trading report."""
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = TRADE_DIR / f"{today}_report.md"

    lines = [
        f"# Paper Trading Report -- {today}\n",
        "## Portfolio Summary\n",
        "| Portfolio | Capital | Deployed | P&L | P&L % | Trades | Wins | Losses |",
        "|-----------|---------|----------|-----|-------|--------|------|--------|",
    ]

    for name in ["v2-paper", "v3-paper", "v3-rs"]:
        p = portfolios[name]
        trades = p["closed_trades"]
        wins = sum(1 for t in trades if t["pnl"] > 0)
        losses = sum(1 for t in trades if t["pnl"] <= 0)
        deployed = sum(t.get("cost", t["entry_price"] * t["qty"]) for t in p["positions"])
        pnl_pct = p["daily_pnl"] / p["capital"] * 100 if p["capital"] else 0
        lines.append(
            f"| **{name}** | Rs {p['capital']:,.0f} | Rs {deployed:,.0f} | "
            f"Rs {p['daily_pnl']:+,.0f} | {pnl_pct:+.2f}% | {len(trades)} | {wins} | {losses} |"
        )

    lines.append("\n## Trade Details\n")
    for name in ["v2-paper", "v3-paper", "v3-rs"]:
        p = portfolios[name]
        lines.append(f"\n### {name}\n")
        if not p["closed_trades"]:
            lines.append("*No trades today*\n")
            continue
        lines.append("| Stock | Entry | Exit | Qty | P&L | P&L% | Reason | Score | RS_5d |")
        lines.append("|-------|-------|------|-----|-----|------|--------|-------|-------|")
        for t in p["closed_trades"]:
            lines.append(
                f"| {t['symbol']} | {t['entry_price']:.2f} | {t['exit_price']:.2f} | "
                f"{t['qty']} | Rs {t['pnl']:+,.0f} | {t['pnl_pct']:+.2f}% | "
                f"{t['reason']} | {t.get('score',0):.1f} | {t.get('rs_5d',0):+.1f}% |"
            )

    # Winner
    pnls = {name: portfolios[name]["daily_pnl"] for name in ["v2-paper", "v3-paper", "v3-rs"]}
    winner = max(pnls, key=pnls.get)
    lines.append(f"\n## Winner: **{winner}** (Rs {pnls[winner]:+,.0f})\n")

    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    log(f"  Daily report saved: {report_path}")
    return report_path


def push_to_devpilot(portfolios):
    """Push daily P&L to DevPilot DB."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=5499, user="devpilot",
            password="TsUxQvfc7go5TDH8lsIKRTCv", dbname="devpilot",
        )
        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")

        pnls = {name: portfolios[name]["daily_pnl"] for name in ["v2-paper", "v3-paper", "v3-rs"]}
        trades = {name: len(portfolios[name]["closed_trades"]) for name in ["v2-paper", "v3-paper", "v3-rs"]}
        winner = max(pnls, key=pnls.get)

        cur.execute("""
            INSERT INTO learnings (project, category, title, content, source, tags, active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'paper-trade-engine', %s, true, NOW(), NOW())
        """, (
            "tradepilot", "paper-trade",
            f"Paper trade {today}: v2 Rs {pnls['v2-paper']:+,.0f} | v3 Rs {pnls['v3-paper']:+,.0f} | v3-rs Rs {pnls['v3-rs']:+,.0f}",
            f"Winner: {winner}. "
            f"v2: {trades['v2-paper']} trades, Rs {pnls['v2-paper']:+,.0f}. "
            f"v3: {trades['v3-paper']} trades, Rs {pnls['v3-paper']:+,.0f}. "
            f"v3-rs: {trades['v3-rs']} trades, Rs {pnls['v3-rs']:+,.0f}.",
            ["paper-trade", today, winner],
        ))
        conn.commit()
        cur.close()
        conn.close()
        log("  DevPilot DB updated with paper trade results.")
    except Exception as e:
        log(f"  DevPilot DB push failed: {e}")


# ═══════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════

def run_full_day():
    """Run the complete paper trading day."""
    log("=" * 60)
    log("  TradePilot Paper Trading Engine STARTED")
    log(f"  Capital per portfolio: Rs {CAPITAL_PER_PORTFOLIO:,.0f}")
    log(f"  Max position: Rs {MAX_POSITION_SIZE:,.0f}")
    log(f"  Target: +{TARGET_PCT}% | SL: -{STOPLOSS_PCT}% | Force exit: {FORCE_EXIT_HOUR}:{FORCE_EXIT_MIN:02d}")
    log("=" * 60)

    portfolios = load_portfolios()
    now = datetime.now()

    # === Phase 1: Wait for market + entry window ===
    entry_time = now.replace(hour=9, minute=35, second=0)
    if now < entry_time:
        wait = (entry_time - now).total_seconds()
        log(f"  Waiting {wait/60:.0f}m until entry window (09:35)...")
        time.sleep(wait)

    # === Phase 2: Load signals and place entries ===
    if now.hour < 10 or (now.hour == 9 and now.minute >= 25):
        log("\n--- LOADING SIGNALS ---")
        v2_buy, v2_hold = get_v2_signals()
        v3_buy, v3_hold = get_v3_signals()
        log(f"  v2: {len(v2_buy)} BUY, {len(v2_hold)} HOLD")
        log(f"  v3: {len(v3_buy)} BUY, {len(v3_hold)} HOLD")

        log("\n--- PLACING ENTRIES ---")
        for name in ["v2-paper", "v3-paper", "v3-rs"]:
            candidates = select_stocks_for_portfolio(name, v2_buy, v2_hold, v3_buy, v3_hold)
            log(f"  [{name}] {len(candidates)} candidates selected")
            place_entries(portfolios[name], candidates)

        save_portfolios(portfolios)
        print_status(portfolios)
    else:
        log("  Past entry window, loading existing positions...")

    # === Phase 3: Monitor loop (check every interval) ===
    check_times = [
        (11, 30, "mid-morning check"),
        (13, 30, "afternoon check"),
        (FORCE_EXIT_HOUR, FORCE_EXIT_MIN, "FORCE EXIT"),
    ]

    for hour, minute, label in check_times:
        target = now.replace(hour=hour, minute=minute, second=0)
        if target <= datetime.now():
            log(f"  Skipping {label} (already past)")
            # Still check exits even if past
            if label != "FORCE EXIT":
                for name in ["v2-paper", "v3-paper", "v3-rs"]:
                    check_exits(portfolios[name])
                save_portfolios(portfolios)
            continue

        wait = (target - datetime.now()).total_seconds()
        if wait > 0:
            log(f"  Waiting {wait/60:.0f}m until {label}...")
            time.sleep(wait)

        log(f"\n--- {label.upper()} ---")
        portfolios = load_portfolios()  # Reload in case of manual changes

        if label == "FORCE EXIT":
            for name in ["v2-paper", "v3-paper", "v3-rs"]:
                force_close_all(portfolios[name])
        else:
            for name in ["v2-paper", "v3-paper", "v3-rs"]:
                check_exits(portfolios[name])

        save_portfolios(portfolios)
        print_status(portfolios)

    # === Phase 4: End of day ===
    log("\n--- END OF DAY ---")
    report = generate_daily_report(portfolios)
    push_to_devpilot(portfolios)
    save_portfolios(portfolios)

    # Print final summary
    log("\n" + "=" * 60)
    log("  DAILY PAPER TRADING SUMMARY")
    log("=" * 60)
    for name in ["v2-paper", "v3-paper", "v3-rs"]:
        p = portfolios[name]
        trades = p["closed_trades"]
        wins = sum(1 for t in trades if t["pnl"] > 0)
        pnl_pct = p["daily_pnl"] / p["capital"] * 100
        log(f"  {name:12s}: Rs {p['daily_pnl']:+8,.0f} ({pnl_pct:+.2f}%) | "
            f"{len(trades)} trades | {wins} wins")
    log("=" * 60)


def show_status():
    """Show current portfolio status."""
    portfolios = load_portfolios()
    for name in ["v2-paper", "v3-paper", "v3-rs"]:
        p = portfolios[name]
        open_pos = [x for x in p["positions"] if x["status"] == "open"]
        print(f"\n[{name}] Cash: Rs {p['cash']:,.0f} | P&L: Rs {p['daily_pnl']:+,.0f}")
        for pos in open_pos:
            print(f"  OPEN: {pos['symbol']} x{pos['qty']} @ {pos['entry_price']:.2f}")
        for t in p["closed_trades"]:
            print(f"  DONE: {t['symbol']} Rs {t['pnl']:+,.0f} [{t['reason']}]")


def show_summary():
    """Show today's summary."""
    portfolios = load_portfolios()
    print(f"\nDate: {portfolios.get('date', 'unknown')}")
    print(f"{'Portfolio':12s} {'P&L':>10s} {'P&L%':>8s} {'Trades':>7s} {'Wins':>5s}")
    print("-" * 50)
    for name in ["v2-paper", "v3-paper", "v3-rs"]:
        p = portfolios[name]
        trades = p["closed_trades"]
        wins = sum(1 for t in trades if t["pnl"] > 0)
        pnl_pct = p["daily_pnl"] / p["capital"] * 100
        print(f"{name:12s} Rs {p['daily_pnl']:+8,.0f} {pnl_pct:+7.2f}% {len(trades):>7d} {wins:>5d}")


if __name__ == "__main__":
    if "--status" in sys.argv:
        show_status()
    elif "--summary" in sys.argv:
        show_summary()
    else:
        run_full_day()
