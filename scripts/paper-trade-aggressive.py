#!/usr/bin/env python3
"""
TradePilot AGGRESSIVE Paper Trading Engine v2
Rs 10,00,000 daily pool. Resets every day. Deploy ALL into BUY signals.
React in real-time: buy when signals appear, sell when prediction says sell.

Philosophy: Push the algorithm's limits. Spend the full 10L every day.
            Tomorrow is a fresh 10L. No fear of loss — this is paper money.

Usage:
    python3 scripts/paper-trade-aggressive.py              # Deploy & monitor
    python3 scripts/paper-trade-aggressive.py --status      # Check positions
    python3 scripts/paper-trade-aggressive.py --summary     # P&L summary
"""
import json
import os
import sys
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).parent.parent
PROTO_DIR = PROJECT_ROOT / "prototype"
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades"
LOG_DIR = PROJECT_ROOT / "logs"

sys.path.insert(0, str(PROTO_DIR))

LOG_FILE = LOG_DIR / "paper-trade-aggressive.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════
# CONFIG — FULL DEPLOYMENT, NO LIMITS
# ═══════════════════════════════════════════════════
DAILY_POOL = 1000000            # Rs 10,00,000 daily budget (resets each day)
MAX_POSITIONS = 15              # Enough slots for all BUY signals
TARGET_PCT = 2.0                # +2% target
STOPLOSS_PCT = 1.0              # -1% stop-loss
TRAILING_TRIGGER_PCT = 1.0      # Move SL to breakeven at +1%
TRAILING_STEP_PCT = 0.5         # Trail 0.5% below peak after breakeven
SCAN_INTERVAL_MIN = 10          # Scan for new signals every 10 min
FORCE_EXIT_HOUR = 15
FORCE_EXIT_MIN = 15


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


# ═══════════════════════════════════════════════════
# STATE
# ═══════════════════════════════════════════════════

def get_state_file():
    today = datetime.now().strftime("%Y-%m-%d")
    return TRADE_DIR / f"{today}_aggressive.json"


def fresh_state():
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "started_at": datetime.now().strftime("%H:%M:%S"),
        "daily_pool": DAILY_POOL,
        "cash": DAILY_POOL,
        "positions": [],
        "closed_trades": [],
        "realized_pnl": 0,
        "peak_pnl": 0,
        "max_drawdown": 0,
        "total_deployed": 0,
        "scan_count": 0,
        "signal_history": [],     # track signal changes over time
    }


def load_state():
    f = get_state_file()
    if f.exists():
        with open(f) as fh:
            state = json.load(fh)
            # Reset if date changed (new day = fresh 10L)
            if state.get("date") != datetime.now().strftime("%Y-%m-%d"):
                log("  NEW DAY — resetting to fresh Rs 10,00,000 pool")
                return fresh_state()
            return state
    return fresh_state()


def save_state(state):
    with open(get_state_file(), "w") as f:
        json.dump(state, f, indent=2, default=str)


# ═══════════════════════════════════════════════════
# PRICE FETCHING
# ═══════════════════════════════════════════════════

def get_live_price(symbol):
    """Get current price via yfinance."""
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
    """Get prices for multiple symbols. Batch first, fallback to individual."""
    import yfinance as yf
    prices = {}
    if not symbols:
        return prices

    ns_symbols = [s if ".NS" in s else s + ".NS" for s in symbols]
    try:
        data = yf.download(ns_symbols, period="1d", interval="1m",
                          progress=False, threads=True)
        if len(data) > 0:
            if len(ns_symbols) == 1:
                # Single stock: Close is a Series, not DataFrame
                close = data["Close"]
                if len(close.dropna()) > 0:
                    prices[symbols[0].replace(".NS", "")] = float(close.dropna().iloc[-1])
            elif "Close" in data.columns.get_level_values(0):
                close = data["Close"]
                for ns in ns_symbols:
                    col = ns if ns in close.columns else None
                    if col and len(close[col].dropna()) > 0:
                        prices[ns.replace(".NS", "")] = float(close[col].dropna().iloc[-1])
    except Exception:
        pass

    # Fill gaps individually
    for s in symbols:
        clean = s.replace(".NS", "")
        if clean not in prices:
            p = get_live_price(s)
            if p:
                prices[clean] = p
    return prices


# ═══════════════════════════════════════════════════
# SIGNAL ENGINE — GET ALL BUY SIGNALS
# ═══════════════════════════════════════════════════

def get_buy_signals():
    """Get BUY signals from both v2 and v3 engines. Merge and rank."""
    v2_buys = {}
    v3_buys = {}

    # v2 from API
    try:
        import urllib.request
        url = "http://localhost:5050/api/scores?category=nifty50"
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
        stocks = data if isinstance(data, list) else data.get("stocks", [])
        for s in stocks:
            if s.get("direction") == "BUY":
                sym = s.get("symbol", s.get("name", "")).replace(".NS", "")
                if sym:
                    v2_buys[sym] = s.get("score", 0)
    except Exception as e:
        log(f"  v2 API error: {e}")

    # v3 from engine
    try:
        from trading_engine_v3 import score_stocks_v3
        from data_engine import NIFTY_50
        scores = score_stocks_v3(NIFTY_50)
        for s in scores:
            if s.get("direction") == "BUY":
                sym = s.get("symbol", s.get("name", "")).replace(".NS", "")
                if sym:
                    v3_buys[sym] = {
                        "score": s.get("score", 0),
                        "rs_5d": s.get("relative_strength_5d", 0),
                    }
    except Exception as e:
        log(f"  v3 engine error: {e}")

    # Also get current direction for ALL stocks (for sell signal detection)
    all_directions = {}
    try:
        import urllib.request
        url = "http://localhost:5050/api/scores?category=nifty50"
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.loads(resp.read())
        stocks = data if isinstance(data, list) else data.get("stocks", [])
        for s in stocks:
            sym = s.get("symbol", s.get("name", "")).replace(".NS", "")
            if sym:
                all_directions[sym] = {
                    "v2_direction": s.get("direction", "?"),
                    "v2_score": s.get("score", 0),
                }
    except Exception:
        pass

    try:
        from trading_engine_v3 import score_stocks_v3
        from data_engine import NIFTY_50
        scores = score_stocks_v3(NIFTY_50)
        for s in scores:
            sym = s.get("symbol", s.get("name", "")).replace(".NS", "")
            if sym:
                if sym not in all_directions:
                    all_directions[sym] = {}
                all_directions[sym]["v3_direction"] = s.get("direction", "?")
                all_directions[sym]["v3_score"] = s.get("score", 0)
                all_directions[sym]["rs_5d"] = s.get("relative_strength_5d", 0)
    except Exception:
        pass

    # Merge BUY signals
    all_buy_symbols = set(v2_buys.keys()) | set(v3_buys.keys())
    candidates = []
    for sym in all_buy_symbols:
        v2_score = v2_buys.get(sym, 0)
        v3_data = v3_buys.get(sym, {})
        v3_score = v3_data.get("score", 0) if isinstance(v3_data, dict) else 0
        rs_5d = v3_data.get("rs_5d", 0) if isinstance(v3_data, dict) else 0

        # Combined score
        scores = [s for s in [v2_score, v3_score] if s > 0]
        combined = sum(scores) / len(scores) if scores else 0

        # Consensus bonus
        is_v2_buy = sym in v2_buys
        is_v3_buy = sym in v3_buys
        if is_v2_buy and is_v3_buy:
            combined += 10  # both engines agree = strong signal
            consensus = "BOTH"
        elif is_v2_buy:
            consensus = "v2"
        else:
            consensus = "v3"

        candidates.append({
            "symbol": sym,
            "combined_score": round(combined, 1),
            "v2_score": round(v2_score, 1),
            "v3_score": round(v3_score, 1),
            "rs_5d": round(rs_5d, 2),
            "consensus": consensus,
        })

    candidates.sort(key=lambda x: -x["combined_score"])

    log(f"  Signals: {len(v2_buys)} v2 BUY, {len(v3_buys)} v3 BUY -> {len(candidates)} unique BUY candidates")

    return candidates, all_directions


# ═══════════════════════════════════════════════════
# TRADING ACTIONS
# ═══════════════════════════════════════════════════

def deploy_into_buys(state):
    """Deploy available cash into all BUY signals. Equal allocation."""
    if state["cash"] < 10000:
        return

    candidates, _ = get_buy_signals()
    if not candidates:
        log("  No BUY signals right now. Will scan again next cycle.")
        return

    # Filter out stocks we already hold
    held_symbols = {p["symbol"] for p in state["positions"] if p["status"] == "open"}
    new_candidates = [c for c in candidates if c["symbol"] not in held_symbols]

    if not new_candidates:
        log("  Already holding all BUY signals")
        return

    # Get live prices
    symbols = [c["symbol"] for c in new_candidates]
    log(f"  Fetching prices for {len(symbols)} BUY candidates...")
    prices = get_prices_batch(symbols)

    tradeable = [c for c in new_candidates if c["symbol"] in prices]
    if not tradeable:
        log("  Could not get prices for any candidate")
        return

    # Allocate cash evenly across all BUY signals — no per-stock cap
    available = state["cash"]
    per_stock = available / len(tradeable)

    log(f"\n  DEPLOYING Rs {available:,.0f} into {len(tradeable)} BUY signals (Rs {per_stock:,.0f} each)")
    log(f"  {'Symbol':>12s}  {'Price':>8s}  {'Qty':>5s}  {'Cost':>10s}  {'SL':>8s}  {'TGT':>8s}  {'Score':>6s}  {'Source':>6s}")
    log(f"  {'-'*80}")

    for stock in tradeable:
        sym = stock["symbol"]
        price = prices[sym]

        alloc = min(per_stock, state["cash"])
        if alloc < 5000:
            break

        qty = int(alloc / price)
        if qty < 1:
            continue
        cost = qty * price

        sl_price = round(price * (1 - STOPLOSS_PCT / 100), 2)
        target_price = round(price * (1 + TARGET_PCT / 100), 2)

        position = {
            "symbol": sym,
            "ns_symbol": sym + ".NS",
            "entry_price": round(price, 2),
            "qty": qty,
            "cost": round(cost, 2),
            "entry_time": datetime.now().strftime("%H:%M:%S"),
            "sl_price": sl_price,
            "target_price": target_price,
            "trailing_activated": False,
            "peak_price": round(price, 2),
            "status": "open",
            "combined_score": stock["combined_score"],
            "v2_score": stock["v2_score"],
            "v3_score": stock["v3_score"],
            "consensus": stock["consensus"],
            "rs_5d": stock["rs_5d"],
        }

        state["positions"].append(position)
        state["cash"] -= cost
        state["total_deployed"] += cost

        log(f"  {sym:>12s}  {price:>8.2f}  {qty:>5d}  {cost:>10,.0f}  {sl_price:>8.2f}  {target_price:>8.2f}  "
            f"{stock['combined_score']:>6.1f}  {stock['consensus']:>6s}")

    open_count = sum(1 for p in state["positions"] if p["status"] == "open")
    log(f"\n  Total open: {open_count} | Cash left: Rs {state['cash']:,.0f}")


def scan_and_react(state):
    """Core loop: check prices + check for new BUY signals + react to SELL signals."""
    state["scan_count"] += 1
    open_pos = [p for p in state["positions"] if p["status"] == "open"]

    log(f"\n{'='*60}")
    log(f"  SCAN #{state['scan_count']} | {len(open_pos)} open | Cash: Rs {state['cash']:,.0f}")
    log(f"{'='*60}")

    # 1. Get fresh signals (to detect direction changes)
    _, all_directions = get_buy_signals()

    # 2. Check all open positions
    if open_pos:
        symbols = [p["symbol"] for p in open_pos]
        prices = get_prices_batch(symbols)

        unrealized = 0
        for pos in open_pos:
            sym = pos["symbol"]
            if sym not in prices:
                log(f"  {sym}: price unavailable")
                continue

            price = prices[sym]
            entry = pos["entry_price"]
            pnl_pct = (price - entry) / entry * 100
            pnl_rs = (price - entry) * pos["qty"]
            unrealized += pnl_rs

            # Update peak
            if price > pos.get("peak_price", entry):
                pos["peak_price"] = round(price, 2)

            reason = None

            # A. Signal says SELL now? Respect the algorithm — exit immediately
            dir_info = all_directions.get(sym, {})
            v2_dir = dir_info.get("v2_direction", "?")
            v3_dir = dir_info.get("v3_direction", "?")
            if v2_dir == "SELL" or v3_dir == "SELL":
                reason = "SIGNAL_SELL"
                log(f"  {sym}: Algorithm says SELL (v2:{v2_dir} v3:{v3_dir}) — exiting!")

            # B. Target hit
            elif price >= pos["target_price"]:
                reason = "TARGET"

            # C. Stop-loss hit
            elif price <= pos["sl_price"]:
                reason = "STOPLOSS"

            # D. Trailing stop logic
            elif pnl_pct >= TRAILING_TRIGGER_PCT:
                if not pos["trailing_activated"]:
                    pos["trailing_activated"] = True
                    pos["sl_price"] = entry
                    log(f"  {sym}: TRAILING ON -> SL at breakeven Rs {entry:.2f}")
                else:
                    trail_sl = round(pos["peak_price"] * (1 - TRAILING_STEP_PCT / 100), 2)
                    if trail_sl > pos["sl_price"]:
                        pos["sl_price"] = trail_sl

            if reason:
                close_position(state, pos, price, reason)
            else:
                trail_tag = " [TRAILING]" if pos["trailing_activated"] else ""
                log(f"  {sym:>12s}  Rs {price:>8.2f}  {pnl_pct:+5.2f}%  P&L Rs {pnl_rs:+8,.0f}  "
                    f"SL:{pos['sl_price']:.2f}  TGT:{pos['target_price']:.2f}{trail_tag}")

        total_pnl = state["realized_pnl"] + unrealized
        if total_pnl > state["peak_pnl"]:
            state["peak_pnl"] = total_pnl
        dd = state["peak_pnl"] - total_pnl
        if dd > state["max_drawdown"]:
            state["max_drawdown"] = dd

        log(f"\n  Realized: Rs {state['realized_pnl']:+,.0f} | Unrealized: Rs {unrealized:+,.0f} | "
            f"Total: Rs {total_pnl:+,.0f}")

    # 3. Deploy any free cash into new BUY signals
    if state["cash"] >= 10000:
        log(f"\n  Free cash Rs {state['cash']:,.0f} — looking for new BUY signals...")
        deploy_into_buys(state)


def close_position(state, pos, exit_price, reason):
    """Close a position and record it."""
    pnl = (exit_price - pos["entry_price"]) * pos["qty"]
    pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100

    pos["status"] = "closed"
    pos["exit_price"] = round(exit_price, 2)
    pos["exit_time"] = datetime.now().strftime("%H:%M:%S")
    pos["pnl"] = round(pnl, 2)
    pos["pnl_pct"] = round(pnl_pct, 2)
    pos["exit_reason"] = reason

    state["cash"] += pos["qty"] * exit_price
    state["realized_pnl"] += pnl

    state["closed_trades"].append({
        "symbol": pos["symbol"],
        "entry_price": pos["entry_price"],
        "exit_price": round(exit_price, 2),
        "qty": pos["qty"],
        "entry_time": pos["entry_time"],
        "exit_time": pos["exit_time"],
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "reason": reason,
        "combined_score": pos.get("combined_score", 0),
        "consensus": pos.get("consensus", "?"),
    })

    tag = "WIN" if pnl > 0 else "LOSS"
    log(f"  >> {tag}: {pos['symbol']} x{pos['qty']} @ Rs {exit_price:.2f} ({reason}) "
        f"P&L: Rs {pnl:+,.0f} ({pnl_pct:+.2f}%)")


def force_close_all(state):
    """Force close all open positions at 3:15 PM."""
    open_pos = [p for p in state["positions"] if p["status"] == "open"]
    if not open_pos:
        log("  No positions to close")
        return

    log(f"\n  FORCE CLOSING {len(open_pos)} positions...")
    symbols = [p["symbol"] for p in open_pos]
    prices = get_prices_batch(symbols)

    for pos in open_pos:
        price = prices.get(pos["symbol"], pos["entry_price"])
        close_position(state, pos, price, "TIME_EXIT")


# ═══════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════

def print_status(state):
    """Print current status."""
    open_pos = [p for p in state["positions"] if p["status"] == "open"]
    closed = state.get("closed_trades", [])

    print(f"\n{'='*65}")
    print(f"  AGGRESSIVE PAPER TRADING  |  {state.get('date', 'today')}  |  Pool: Rs 10,00,000")
    print(f"{'='*65}")
    print(f"  Cash: Rs {state['cash']:,.0f}  |  Deployed: Rs {state['total_deployed']:,.0f}")
    print(f"  Realized P&L: Rs {state['realized_pnl']:+,.0f}  |  Scans: {state['scan_count']}")

    if open_pos:
        print(f"\n  OPEN ({len(open_pos)}):")
        for p in open_pos:
            trail = " [T]" if p.get("trailing_activated") else ""
            print(f"    {p['symbol']:>12s}  x{p['qty']:<5d}  @ {p['entry_price']:.2f}  "
                  f"SL:{p['sl_price']:.2f}  TGT:{p['target_price']:.2f}  "
                  f"Score:{p.get('combined_score',0):.0f} ({p.get('consensus','?')}){trail}")

    if closed:
        wins = [t for t in closed if t["pnl"] > 0]
        losses = [t for t in closed if t["pnl"] <= 0]
        print(f"\n  CLOSED ({len(closed)}):  {len(wins)} wins, {len(losses)} losses  |  "
              f"Win rate: {len(wins)/len(closed)*100:.0f}%")
        for t in closed:
            tag = "WIN " if t["pnl"] > 0 else "LOSS"
            print(f"    {tag} {t['symbol']:>12s}  {t['entry_price']:.2f} -> {t['exit_price']:.2f}  "
                  f"Rs {t['pnl']:+,.0f} ({t['pnl_pct']:+.2f}%) [{t['reason']}]")

    if not open_pos and not closed:
        print(f"\n  No trades yet")
    print(f"{'='*65}")


def generate_report(state):
    """Generate end-of-day markdown report."""
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = TRADE_DIR / f"{today}_aggressive_report.md"

    closed = state.get("closed_trades", [])
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    total_profit = sum(t["pnl"] for t in wins)
    total_loss = sum(t["pnl"] for t in losses)
    pnl_pct = state["realized_pnl"] / state["daily_pool"] * 100

    lines = [
        f"# Aggressive Paper Trading Report -- {today}\n",
        f"## Summary\n",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Daily Pool | Rs {state['daily_pool']:,.0f} |",
        f"| Total Deployed | Rs {state['total_deployed']:,.0f} |",
        f"| **Net P&L** | **Rs {state['realized_pnl']:+,.0f} ({pnl_pct:+.2f}%)** |",
        f"| Gross Profit | Rs {total_profit:+,.0f} |",
        f"| Gross Loss | Rs {total_loss:+,.0f} |",
        f"| Trades | {len(closed)} |",
        f"| Wins / Losses | {len(wins)} / {len(losses)} |",
        f"| **Win Rate** | **{win_rate:.0f}%** |",
        f"| Peak P&L | Rs {state['peak_pnl']:+,.0f} |",
        f"| Max Drawdown | Rs {state['max_drawdown']:,.0f} |",
        f"| Scans | {state['scan_count']} |",
        "",
        "## Trade Log\n",
        "| # | Stock | Entry | Exit | Qty | Cost | P&L | P&L% | Reason | Score | Signal |",
        "|---|-------|-------|------|-----|------|-----|------|--------|-------|--------|",
    ]

    for i, t in enumerate(closed, 1):
        cost = t["entry_price"] * t["qty"]
        lines.append(
            f"| {i} | {t['symbol']} | {t['entry_price']:.2f} | {t['exit_price']:.2f} | "
            f"{t['qty']} | Rs {cost:,.0f} | Rs {t['pnl']:+,.0f} | {t['pnl_pct']:+.2f}% | "
            f"{t['reason']} | {t.get('combined_score',0):.1f} | {t.get('consensus','?')} |"
        )

    # Insights
    lines.append("\n## Key Insights\n")
    if closed:
        # Score correlation
        avg_win = sum(t.get("combined_score", 0) for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.get("combined_score", 0) for t in losses) / len(losses) if losses else 0
        lines.append(f"- Avg score winners: {avg_win:.1f} | Avg score losers: {avg_loss:.1f}")
        if avg_win > avg_loss + 3:
            lines.append(f"- Higher scores = better trades (score IS predictive)")
        else:
            lines.append(f"- Score not strongly predictive this session")

        # Consensus analysis
        both_trades = [t for t in closed if t.get("consensus") == "BOTH"]
        single_trades = [t for t in closed if t.get("consensus") != "BOTH"]
        if both_trades:
            both_pnl = sum(t["pnl"] for t in both_trades)
            lines.append(f"- Consensus (BOTH) trades: {len(both_trades)}, P&L Rs {both_pnl:+,.0f}")
        if single_trades:
            single_pnl = sum(t["pnl"] for t in single_trades)
            lines.append(f"- Single-engine trades: {len(single_trades)}, P&L Rs {single_pnl:+,.0f}")

        # Exit reason breakdown
        reasons = {}
        for t in closed:
            r = t["reason"]
            if r not in reasons:
                reasons[r] = {"count": 0, "pnl": 0}
            reasons[r]["count"] += 1
            reasons[r]["pnl"] += t["pnl"]
        lines.append("\n### Exit Reason Breakdown\n")
        lines.append("| Reason | Count | P&L |")
        lines.append("|--------|-------|-----|")
        for r, d in sorted(reasons.items()):
            lines.append(f"| {r} | {d['count']} | Rs {d['pnl']:+,.0f} |")

    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    log(f"  Report: {report_path}")
    return report_path


def push_to_devpilot(state):
    """Store results in DevPilot DB."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=5499, user="devpilot",
            password="TsUxQvfc7go5TDH8lsIKRTCv", dbname="devpilot",
        )
        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        closed = state.get("closed_trades", [])
        wins = sum(1 for t in closed if t["pnl"] > 0)
        win_rate = wins / len(closed) * 100 if closed else 0

        cur.execute("""
            INSERT INTO learnings (project, category, title, content, source, tags, active, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'paper-trade-aggressive-v2', %s, true, NOW(), NOW())
        """, (
            "tradepilot", "paper-trade",
            f"AGG {today}: Rs {state['realized_pnl']:+,.0f} | {len(closed)} trades | {win_rate:.0f}% win",
            json.dumps({
                "pool": DAILY_POOL,
                "deployed": state["total_deployed"],
                "pnl": state["realized_pnl"],
                "trades": len(closed),
                "wins": wins,
                "win_rate": win_rate,
                "peak_pnl": state["peak_pnl"],
                "max_drawdown": state["max_drawdown"],
                "scans": state["scan_count"],
            }),
            ["paper-trade", "aggressive", today, f"wr-{win_rate:.0f}"],
        ))
        conn.commit()
        cur.close()
        conn.close()
        log("  Results saved to DevPilot DB")
    except Exception as e:
        log(f"  DevPilot push failed: {e}")


# ═══════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════

def run():
    """Deploy and monitor. Runs until market close."""
    log("=" * 60)
    log("  AGGRESSIVE PAPER TRADING v2")
    log(f"  Daily pool: Rs {DAILY_POOL:,.0f} (resets tomorrow)")
    log(f"  Strategy: ALL BUY signals, equal allocation, no cap")
    log(f"  Target: +{TARGET_PCT}% | SL: -{STOPLOSS_PCT}% | Trail: +{TRAILING_TRIGGER_PCT}%")
    log(f"  Scan every: {SCAN_INTERVAL_MIN} min | Force exit: {FORCE_EXIT_HOUR}:{FORCE_EXIT_MIN:02d}")
    log("=" * 60)

    state = load_state()

    # Initial deployment
    open_count = sum(1 for p in state["positions"] if p["status"] == "open")
    if open_count == 0 and state["cash"] > 10000:
        log("\n--- INITIAL DEPLOYMENT ---")
        deploy_into_buys(state)
        save_state(state)
    elif open_count > 0:
        log(f"\n  Resuming with {open_count} open positions")

    # Scan loop
    while True:
        now = datetime.now()
        force_exit = now.replace(hour=FORCE_EXIT_HOUR, minute=FORCE_EXIT_MIN, second=0)

        if now >= force_exit:
            state = load_state()
            force_close_all(state)
            save_state(state)
            break

        market_close = now.replace(hour=15, minute=30, second=0)
        if now >= market_close:
            break

        # Wait for next scan
        next_scan = now + timedelta(minutes=SCAN_INTERVAL_MIN)
        if next_scan > force_exit:
            next_scan = force_exit

        wait = (next_scan - now).total_seconds()
        if wait > 0:
            log(f"\n  Next scan in {wait/60:.0f} min (at {next_scan.strftime('%H:%M')})...")
            time.sleep(wait)

        # Scan: check prices, detect signal changes, deploy free cash
        state = load_state()
        scan_and_react(state)
        save_state(state)

    # End of day
    log("\n" + "=" * 60)
    log("  END OF DAY")
    log("=" * 60)
    state = load_state()
    print_status(state)
    report = generate_report(state)
    push_to_devpilot(state)
    save_state(state)

    pnl_pct = state["realized_pnl"] / state["daily_pool"] * 100
    closed = state.get("closed_trades", [])
    wins = sum(1 for t in closed if t["pnl"] > 0)
    log(f"\n  FINAL: Rs {state['realized_pnl']:+,.0f} ({pnl_pct:+.2f}%) | "
        f"{len(closed)} trades | {wins} wins | "
        f"Win rate: {wins/len(closed)*100:.0f}%" if closed else "  No trades today")


if __name__ == "__main__":
    if "--status" in sys.argv:
        state = load_state()
        print_status(state)
    elif "--summary" in sys.argv:
        state = load_state()
        closed = state.get("closed_trades", [])
        wins = sum(1 for t in closed if t["pnl"] > 0)
        pnl_pct = state["realized_pnl"] / state["daily_pool"] * 100
        print(f"\nDate: {state.get('date', 'today')} | Pool: Rs {state['daily_pool']:,.0f}")
        print(f"P&L: Rs {state['realized_pnl']:+,.0f} ({pnl_pct:+.2f}%)")
        if closed:
            print(f"Trades: {len(closed)} | Wins: {wins} | Win rate: {wins/len(closed)*100:.0f}%")
        else:
            print("No trades yet")
        print(f"Deployed: Rs {state['total_deployed']:,.0f} | Cash: Rs {state['cash']:,.0f}")
    else:
        run()
