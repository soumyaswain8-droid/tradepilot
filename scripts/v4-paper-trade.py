#!/usr/bin/env python3
"""
TradePilot v4 Paper Trading Engine
===================================
Uses v4 composite scorer + position sizer for intraday paper trading.
Rs 10,00,000 daily pool. Deploy into v4's top BUY picks at 9:35 AM.
Monitor every 10 min. Re-score every 30 min. Force exit at 3:15 PM.

Usage:
    python3 scripts/v4-paper-trade.py              # Full day auto-pilot
    python3 scripts/v4-paper-trade.py --status      # Check positions
    python3 scripts/v4-paper-trade.py --summary     # P&L summary
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
TRADE_DIR = PROJECT_ROOT / "docs" / "paper-trades" / "v4"
LOG_DIR = PROJECT_ROOT / "logs"

sys.path.insert(0, str(PROTO_DIR))

LOG_FILE = LOG_DIR / "v4-paper-trade.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)
TRADE_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════
DAILY_POOL = 1_000_000
MAX_PER_STOCK_PCT = 0.20        # Max 20% in one stock (Kelly cap)
TRAILING_TRIGGER_PCT = 1.0      # Move SL to breakeven at +1%
TRAILING_STEP_PCT = 0.5         # Trail 0.5% below peak
SCAN_INTERVAL_MIN = 10          # Price check every 10 min
RESCORE_INTERVAL_MIN = 30       # Full v4 rescore every 30 min
FORCE_EXIT_HOUR = 15
FORCE_EXIT_MIN = 15

# ═══════════════════════════════════════════════════
# RISK CONTROLS (fixes from Day 1 — Apr 9, 2026)
# ═══════════════════════════════════════════════════
CIRCUIT_BREAKER_LOSSES = 5      # Pause all trading after N consecutive losses
MAX_REENTRY_PER_STOCK = 1       # Max re-entries per stock per day (was unlimited)
VIX_HIGH_THRESHOLD = 18         # If VIX > this, reduce position size
VIX_SIZE_MULTIPLIER = 0.50      # Position size multiplier when VIX is high
NIFTY_BEAR_THRESHOLD = -0.5     # If Nifty < this % by 10 AM, go defensive
BEAR_MODE_SIZE_MULT = 0.50      # Position size in bear mode
MAX_DAILY_LOSS_PCT = 3.0        # Kill switch: stop all trading if daily loss exceeds this %

# 2026-05-04 MVP guards (corp_actions filter + abs Rs floors)
ABS_POSITION_SL_RS    = -25_000   # Force-close any single position when unrealized P&L hits this floor
CORP_ACTIONS_PATH     = PROJECT_ROOT / "prototype" / "data" / "corp_actions.json"
CORP_ACTION_BAN_DAYS  = 7         # Ban window: ex_date - 1 day through ex_date + N days

# 2026-05-06 Revival mechanics (replaces flat MAX_REENTRY_PER_STOCK gate + flat kill switch).
# Per pro-trader research consensus (Linda Raschke, SMB, Brett Steenbarger): cut + watch +
# re-enter on technical confirmation. Per Agent A research: Bullish Engulfing + 1.5x volume +
# 11:15-14:45 IST window = ~65% reversal hit rate. See docs/research/2026-05-06_revival_research.md.
STOCK_LOSS_EXIT_PCT          = -10.0     # %-based outer floor — force-exit if position drops 10% from entry
MAX_LOSSES_PER_STOCK_PER_DAY =      2    # Per-stock cap counts LOSING exits only; winners are unrestricted

# Kill switch — 3 tiers replacing the old flat ABS_DAILY_KILL_RS = -5_000
# Industry default per Agent D research: SOFT halt blocks new entries, doesn't liquidate.
# HARD kill is for catastrophic / runaway scenarios only.
ABS_DAILY_WARN_RS         =  -2_500   # Tier 1: telegram alert + log, NO entry block
ABS_DAILY_SOFT_HOLD_RS    =  -5_000   # Tier 2: BLOCK new entries, hold existing positions to their stops
ABS_DAILY_HARD_KILL_RS    = -10_000   # Tier 3: flatten all + halt for the day
HARD_KILL_PCT_SL_COUNT    =       3   # Also tier 3 if N+ stocks force-closed on -10% intraday


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
    return TRADE_DIR / f"{today}.json"


def fresh_state():
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "engine": "v4",
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
        "rescore_count": 0,
        "portfolio_risk": {},
        "last_rescore_time": None,
        # Risk control state
        "consecutive_losses": 0,
        "circuit_breaker_active": False,
        "stock_entry_count": {},       # {symbol: count} — tracks ALL entries (informational)
        "bear_mode": False,
        "vix_high_mode": False,
        "size_multiplier": 1.0,        # Current position size multiplier (always 1.0 since 2026-05-06)
        "risk_events": [],             # Log of risk control triggers
        # 2026-05-06 revival mechanics
        "stock_loss_count": {},        # {symbol: int} — counts ONLY losing exits per stock per day
        "watchlist": {},               # {symbol: {exit_time, exit_price, post_drop_low, exit_reason, loss_pct}}
        "kill_switch_tier": 0,         # 0=clear, 1=WARN, 2=SOFT_HOLD, 3=HARD_KILL
        "force_flatten_now": False,    # Set by tier 3 kill; scan_and_react reads + force_close_all
    }


CARRY_FORWARD_FILE = TRADE_DIR / "carry_forward.json"


def _get_carry_forward_balance():
    """Load previous day's closing balance. Returns DAILY_POOL if no history."""
    if CARRY_FORWARD_FILE.exists():
        try:
            cf = json.load(open(CARRY_FORWARD_FILE))
            bal = cf.get("closing_balance", DAILY_POOL)
            log(f"  CARRY FORWARD: Rs {bal:,.0f} from {cf.get('date', '?')}")
            return bal
        except Exception:
            pass
    return DAILY_POOL


def _save_carry_forward(state):
    """Save today's closing balance for tomorrow."""
    closing = state["cash"] + sum(
        p.get("qty", 0) * p.get("entry_price", 0)
        for p in state.get("positions", []) if p.get("status") == "open"
    )
    # Add realized P&L to get true balance
    closing = state.get("daily_pool", DAILY_POOL) + state.get("realized_pnl", 0)
    cf = {
        "date": state.get("date"),
        "closing_balance": round(closing, 2),
        "realized_pnl": round(state.get("realized_pnl", 0), 2),
        "cumulative_pnl": round(closing - DAILY_POOL, 2),
    }
    with open(CARRY_FORWARD_FILE, "w") as f:
        json.dump(cf, f, indent=2)


def load_state():
    f = get_state_file()
    if f.exists():
        with open(f) as fh:
            state = json.load(fh)
            if state.get("date") != datetime.now().strftime("%Y-%m-%d"):
                log("  NEW DAY -- carrying forward balance")
                balance = _get_carry_forward_balance()
                s = fresh_state()
                s["daily_pool"] = balance
                s["cash"] = balance
                return s
            return state
    # First day or no state — check carry forward
    balance = _get_carry_forward_balance()
    s = fresh_state()
    s["daily_pool"] = balance
    s["cash"] = balance
    return s


def save_state(state):
    with open(get_state_file(), "w") as f:
        json.dump(state, f, indent=2, default=str)


# ═══════════════════════════════════════════════════
# PRICE FETCHING (yfinance batch)
# ═══════════════════════════════════════════════════

def get_prices_batch(symbols):
    """Get live prices for multiple symbols via yfinance."""
    import yfinance as yf
    prices = {}
    if not symbols:
        return prices
    ns_syms = [s if ".NS" in s else s + ".NS" for s in symbols]
    try:
        data = yf.download(ns_syms, period="1d", interval="1m", progress=False, threads=True)
        if len(data) > 0:
            if len(ns_syms) == 1:
                close = data["Close"]
                if len(close.dropna()) > 0:
                    prices[symbols[0].replace(".NS", "")] = float(close.dropna().iloc[-1])
            elif "Close" in data.columns.get_level_values(0):
                close = data["Close"]
                for ns in ns_syms:
                    if ns in close.columns and len(close[ns].dropna()) > 0:
                        prices[ns.replace(".NS", "")] = float(close[ns].dropna().iloc[-1])
    except Exception:
        pass
    for s in symbols:  # Fill gaps individually
        clean = s.replace(".NS", "")
        if clean not in prices:
            try:
                hist = yf.Ticker(s if ".NS" in s else s + ".NS").history(period="1d", interval="1m")
                if len(hist) > 0:
                    prices[clean] = float(hist["Close"].iloc[-1])
            except Exception:
                pass
    return prices


# ═══════════════════════════════════════════════════
# V4 SIGNAL ENGINE
# ═══════════════════════════════════════════════════

def run_v4_scorer():
    """Run v4 composite scorer on all Nifty 50. Returns full scored list."""
    from v4.composite_scorer import score_all_stocks
    return score_all_stocks()


def get_v4_buys_and_directions():
    """Score all stocks, return (buy_list, full_direction_map)."""
    all_scored = run_v4_scorer()
    buys = [s for s in all_scored if s.get("direction") == "BUY"]
    directions = {s["symbol"]: s for s in all_scored}
    log(f"  v4 scorer: {len(all_scored)} scored | "
        f"BUY={len(buys)} HOLD={sum(1 for s in all_scored if s['direction']=='HOLD')} "
        f"AVOID={sum(1 for s in all_scored if s['direction']=='AVOID')}")
    return buys, directions


# ═══════════════════════════════════════════════════
# POSITION SIZING (v4 Kelly-weighted)
# ═══════════════════════════════════════════════════

def size_and_deploy(buys, capital):
    """Use v4 position_sizer for Kelly-weighted allocation."""
    from v4.position_sizer import size_positions, compute_portfolio_risk
    positions = size_positions(buys, capital=capital, max_per_stock_pct=MAX_PER_STOCK_PCT)
    risk = compute_portfolio_risk(positions, capital=capital)
    return positions, risk


# ═══════════════════════════════════════════════════
# TRADING ACTIONS
# ═══════════════════════════════════════════════════

# ═══════════════════════════════════════════════════
# RISK CONTROLS
# ═══════════════════════════════════════════════════

def check_circuit_breaker(state):
    """3-tier kill switch + 5-consec-loss circuit breaker.

    Returns True to BLOCK new entries (tier 2 or 3, or 5-consec loss).
    Tier 3 ALSO sets state['force_flatten_now'] so scan_and_react flushes positions.

    Tiers (replaces 2026-05-04 MVP single-threshold ABS_DAILY_KILL_RS):
      0 — clear
      1 WARN     : realized <= ABS_DAILY_WARN_RS  → alert only, no block
      2 SOFT_HOLD: realized <= ABS_DAILY_SOFT_HOLD_RS → block new entries
      3 HARD_KILL: realized <= ABS_DAILY_HARD_KILL_RS OR pct-SL exits >= HARD_KILL_PCT_SL_COUNT
                   → flatten all + halt for the day
    """
    realized = state.get("realized_pnl", 0)

    # 5-consecutive-loss breaker (independent of tiers; existing behavior)
    if state.get("consecutive_losses", 0) >= CIRCUIT_BREAKER_LOSSES:
        if not state.get("circuit_breaker_active"):
            state["circuit_breaker_active"] = True
            state["risk_events"].append(
                f"{datetime.now().strftime('%H:%M')} CIRCUIT_BREAKER: "
                f"{state['consecutive_losses']} consecutive losses"
            )
            log(f"  ** CIRCUIT BREAKER ** {state['consecutive_losses']} consecutive losses — NO NEW ENTRIES")
        return True

    # Count -10% pct-SL force-closes today (a separate signal of cascade)
    pct_sl_today = sum(
        1 for t in state.get("closed_trades", [])
        if t.get("reason") in ("ABS_PCT_SL", "ABS_RS_SL")
    )

    current_tier = state.get("kill_switch_tier", 0)

    # Tier 3 — HARD KILL (catastrophic / cascade)
    hard_kill_rs   = ABS_DAILY_HARD_KILL_RS is not None and realized <= ABS_DAILY_HARD_KILL_RS
    hard_kill_cnt  = pct_sl_today >= HARD_KILL_PCT_SL_COUNT
    if hard_kill_rs or hard_kill_cnt:
        if current_tier < 3:
            state["kill_switch_tier"] = 3
            state["circuit_breaker_active"] = True
            state["force_flatten_now"] = True
            trigger = (f"realized Rs {realized:+,.0f} <= floor Rs {ABS_DAILY_HARD_KILL_RS:+,.0f}"
                       if hard_kill_rs
                       else f"{pct_sl_today} stocks force-closed at -10% (cascade)")
            state["risk_events"].append(
                f"{datetime.now().strftime('%H:%M')} HARD_KILL: {trigger}"
            )
            log(f"  ** HARD KILL ** {trigger} — FLATTEN ALL + HALT")
        return True

    # Tier 2 — SOFT HOLD (block new entries, hold existing to their own stops)
    if ABS_DAILY_SOFT_HOLD_RS is not None and realized <= ABS_DAILY_SOFT_HOLD_RS:
        if current_tier < 2:
            state["kill_switch_tier"] = 2
            state["risk_events"].append(
                f"{datetime.now().strftime('%H:%M')} SOFT_HOLD: "
                f"realized Rs {realized:+,.0f} <= Rs {ABS_DAILY_SOFT_HOLD_RS:+,.0f}"
            )
            log(f"  ** SOFT HOLD ** Realized Rs {realized:+,.0f} <= Rs {ABS_DAILY_SOFT_HOLD_RS:+,.0f} — "
                f"blocking new entries, existing positions ride to their own stops")
        return True

    # Tier 1 — WARN (alert only, do NOT block)
    if ABS_DAILY_WARN_RS is not None and realized <= ABS_DAILY_WARN_RS:
        if current_tier < 1:
            state["kill_switch_tier"] = 1
            state["risk_events"].append(
                f"{datetime.now().strftime('%H:%M')} WARN: "
                f"realized Rs {realized:+,.0f} <= Rs {ABS_DAILY_WARN_RS:+,.0f}"
            )
            log(f"  ** WARN ** Realized Rs {realized:+,.0f} approaching limits — alert only, no block")
        # fall through (no block at tier 1)

    # Legacy %-based kill (kept as final safety net; should rarely trigger before tier 3)
    daily_loss_pct = abs(realized) / state.get("daily_pool", DAILY_POOL) * 100
    if realized < 0 and daily_loss_pct >= MAX_DAILY_LOSS_PCT:
        if current_tier < 3:
            state["circuit_breaker_active"] = True
            state["risk_events"].append(
                f"{datetime.now().strftime('%H:%M')} LEGACY_KILL: -{daily_loss_pct:.1f}% daily loss"
            )
            log(f"  ** LEGACY KILL ** Daily loss -{daily_loss_pct:.1f}% exceeds {MAX_DAILY_LOSS_PCT}% — STOPPING")
        return True

    return False


def check_market_regime(state):
    """Check VIX and Nifty trend — INFORMATIONAL ONLY since 2026-05-06.

    Previously this function returned a size_mult that halved capital when
    VIX > 18 or Nifty < -0.5%. That structural cut caused 2026-05-05's
    zero-trades event because halved capital + 40 BUYs + Rs 20K floor =
    no allocation could clear the floor.

    New approach (per pro-trader research consensus): keep VIX/Nifty as
    awareness signals only. Risk is now managed BEHAVIORALLY at the
    per-stock level (-10% absolute floor + watchlist + candle re-entry
    gate) and at the portfolio level (3-tier kill switch). High VIX days
    don't need pre-emptive capital cuts; they need tighter active risk.

    Always returns 1.0. State flags vix_high_mode/bear_mode kept for
    dashboards and EOD reports.
    """
    state["size_multiplier"] = 1.0  # always full capital — behavioral risk only

    try:
        import yfinance as yf
        # India VIX — log only
        vix_data = yf.download("^INDIAVIX", period="2d", interval="1d", progress=False)
        if hasattr(vix_data.columns, 'droplevel') and len(vix_data.columns.names) > 1:
            vix_data.columns = vix_data.columns.droplevel(1)
        if len(vix_data) > 0:
            vix = float(vix_data["Close"].iloc[-1])
            state["vix_high_mode"] = vix > VIX_HIGH_THRESHOLD
            if state["vix_high_mode"]:
                log(f"  ** REGIME NOTE ** VIX={vix:.1f}>{VIX_HIGH_THRESHOLD} (informational; no capital cut)")

        # Nifty intraday trend — log only
        now = datetime.now()
        if now.hour >= 10:
            nifty = yf.download("^NSEI", period="2d", interval="1d", progress=False)
            if hasattr(nifty.columns, 'droplevel') and len(nifty.columns.names) > 1:
                nifty.columns = nifty.columns.droplevel(1)
            if len(nifty) >= 2:
                prev_close = float(nifty["Close"].iloc[-2])
                today_close = float(nifty["Close"].iloc[-1])
                nifty_change = (today_close - prev_close) / prev_close * 100
                state["bear_mode"] = nifty_change < NIFTY_BEAR_THRESHOLD
                if state["bear_mode"]:
                    log(f"  ** REGIME NOTE ** NIFTY={nifty_change:+.2f}%<{NIFTY_BEAR_THRESHOLD}% (informational; no capital cut)")
    except Exception as e:
        log(f"  Regime check failed: {e}")

    return 1.0


def can_enter_stock(state, symbol):
    """2026-05-06: gate on LOSING exits only — winners are unrestricted.

    Rationale: if a stock made profit on a previous trade today, the engine
    should be free to re-enter it as the algorithm signals. Only losses
    indicate "this stock isn't working today" and warrant a per-stock cap.

    Returns True if loss_count < MAX_LOSSES_PER_STOCK_PER_DAY (default 2).
    """
    loss_count = state.get("stock_loss_count", {}).get(symbol, 0)
    return loss_count < MAX_LOSSES_PER_STOCK_PER_DAY


def record_entry(state, symbol):
    """Track stock entry count."""
    if "stock_entry_count" not in state:
        state["stock_entry_count"] = {}
    state["stock_entry_count"][symbol] = state["stock_entry_count"].get(symbol, 0) + 1


def load_corp_action_bans():
    """Read prototype/data/corp_actions.json and return {symbol: reason_str} for stocks
    currently inside the [ex_date - 1, ex_date + CORP_ACTION_BAN_DAYS] window.

    Mirrors prototype/v5/risk_manager.py:load_corp_actions_file so v4 and v5 ban the same
    symbols on the same days without v4 needing v5's multi-pool RiskManager. Single source
    of truth = the JSON file."""
    if CORP_ACTIONS_PATH is None or not CORP_ACTIONS_PATH.exists():
        return {}
    try:
        data = json.loads(CORP_ACTIONS_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    today = datetime.now().date()
    bans = {}
    for ev in data.get("events", []):
        sym = ev.get("symbol")
        ex_date_str = ev.get("ex_date", "")
        if not sym or not ex_date_str:
            continue
        try:
            ex_date = datetime.strptime(ex_date_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        ban_end = ex_date + timedelta(days=CORP_ACTION_BAN_DAYS)
        if (ex_date - timedelta(days=1)) <= today <= ban_end:
            bans[sym] = (
                f"Corp action ({ev.get('action_type', '?')}) ex-date {ex_date_str}: "
                f"{ev.get('note', '')[:80]}"
            )
    return bans


def deploy_into_buys(state):
    """Deploy available cash into v4 BUY signals using Kelly sizing."""
    if state["cash"] < 10000:
        return

    # Risk check: circuit breaker
    if check_circuit_breaker(state):
        log("  Skipping deployment — circuit breaker active")
        return

    # Risk check: market regime (VIX + Nifty trend)
    size_mult = check_market_regime(state)

    buys, _ = get_v4_buys_and_directions()
    if not buys:
        log("  No BUY signals from v4. Will scan again next cycle."); return
    held = {p["symbol"] for p in state["positions"] if p["status"] == "open"}

    # 2026-05-04 MVP: corp-action ex-date ban (would have blocked VEDL on 2026-04-30)
    corp_bans = load_corp_action_bans()
    if corp_bans:
        log(f"  Corp-action bans active today: {', '.join(sorted(corp_bans.keys()))}")

    # 2026-05-06 revival mechanics — watchlist contains stocks that recently exited at a loss.
    # Re-entry is gated by revival_signal() — must show Bullish Engulfing + 1.5x volume +
    # 11:15-14:45 IST window + price within 0.5% of post-drop low.
    watchlist = state.get("watchlist", {})
    loss_counts = state.get("stock_loss_count", {})

    # Filter: held / corp-action / loss-count / watchlist-revival-gate
    new_buys = []
    revival_module = None  # lazy-import only if a watchlist entry needs checking
    for b in buys:
        sym = b["symbol"]
        if sym in held:
            continue
        if sym in corp_bans:
            log(f"  {sym}: SKIPPED ({corp_bans[sym][:80]})")
            continue
        loss_count = loss_counts.get(sym, 0)
        if loss_count >= MAX_LOSSES_PER_STOCK_PER_DAY:
            log(f"  {sym}: SKIPPED (blacklisted — {loss_count} losses today, max {MAX_LOSSES_PER_STOCK_PER_DAY})")
            continue
        # If symbol is in watchlist (just exited at loss), require revival confirmation
        if sym in watchlist:
            if revival_module is None:
                try:
                    # v4-paper-trade adds prototype/ to sys.path (line 29), so import
                    # bare 'v4.candle_patterns' — same pattern as composite_scorer/position_sizer.
                    from v4.candle_patterns import revival_signal, fetch_recent_bars
                    revival_module = (revival_signal, fetch_recent_bars)
                except ImportError as e:
                    log(f"  WARN: candle_patterns import failed ({e}) — skipping watchlist re-entries")
                    revival_module = (None, None)
            rs_fn, fetch_fn = revival_module
            if rs_fn is None:
                continue  # safety: if module broken, don't allow watchlist re-entry
            bars = fetch_fn(sym)
            if bars is None or len(bars) < 21:
                log(f"  {sym}: SKIPPED (watchlist — insufficient bars for revival check)")
                continue
            ok, reason = rs_fn(bars, current_price=b["price"],
                               post_drop_low=watchlist[sym].get("post_drop_low", b["price"]))
            if not ok:
                log(f"  {sym}: SKIPPED (watchlist — {reason})")
                continue
            log(f"  {sym}: WATCHLIST CLEARED — re-entry allowed ({reason})")
            # Clear from watchlist so we don't re-check; loss_count still gates 2nd loss
            del watchlist[sym]
        new_buys.append(b)

    if not new_buys:
        log("  Already holding all v4 BUY signals or re-entry caps hit"); return

    # 2026-05-09: Late-start preflight filter (specced 2026-04-27).
    # If boot was after 09:30, apply per-signal late-mode filter and reduce
    # Kelly to 55% of normal. Once applied, clear preflight_mode so subsequent
    # scans run normal logic.
    preflight_mode = state.get("preflight_mode", "NORMAL")
    if preflight_mode == "LATE_ENTRY":
        from prototype.v4.preflight import apply_late_start_filter, kelly_scale_for_mode
        symbols = [b["symbol"] for b in new_buys]
        filtered_signals, ctx, mode_label = apply_late_start_filter(new_buys, symbols)
        if not filtered_signals:
            log("  Late-start filter rejected all signals — skipping deploy")
            state["preflight_mode"] = "NORMAL"  # one-shot, disable for next scan
            return
        rejected_n = len(new_buys) - len(filtered_signals)
        if rejected_n > 0:
            log(f"  Late-start filter: {len(filtered_signals)}/{len(new_buys)} signals passed ({rejected_n} rejected)")
        new_buys = filtered_signals
        # Apply Kelly reduction
        size_mult = size_mult * kelly_scale_for_mode(mode_label)
        log(f"  Late-start: Kelly reduced to {kelly_scale_for_mode(mode_label)*100:.0f}% (effective size_mult={size_mult:.2f})")
        state["preflight_mode"] = "NORMAL"  # one-shot, disable for next scan

    # Apply regime-adjusted capital
    available_capital = state["cash"] * size_mult
    sized, risk = size_and_deploy(new_buys, available_capital)
    if not sized:
        log("  Position sizer returned no positions"); return
    state["portfolio_risk"] = risk

    log(f"\n  DEPLOYING Rs {state['cash']:,.0f} into {len(sized)} v4 BUY signals (Kelly-weighted)")
    log(f"  {'Symbol':>12s}  {'Price':>8s}  {'Qty':>5s}  {'Alloc':>10s}  {'%':>6s}  {'SL':>8s}  {'TGT':>8s}  {'Score':>5s}")
    log(f"  {'-'*75}")

    for pos in sized:
        sym, price, qty = pos["symbol"], pos["price"], pos["qty"]
        alloc, alloc_pct = pos["position_size_rs"], pos["position_pct"] * 100
        if alloc > state["cash"]:
            qty = int(state["cash"] / price)
            if qty < 1: continue
            alloc = qty * price
        state["positions"].append({
            "symbol": sym, "entry_price": round(price, 2), "qty": qty,
            "cost": round(alloc, 2), "entry_time": datetime.now().strftime("%H:%M:%S"),
            "sl_price": pos["sl_price"], "target_price": pos["target_price"],
            "sl_pct": pos["sl_pct"], "target_pct": pos["target_pct"],
            "trailing_activated": False, "peak_price": round(price, 2), "status": "open",
            "v4_score": pos["score"], "v4_direction": pos["direction"],
            "composite_breakdown": pos.get("composite_breakdown", {}),
            "reasons": [r["text"] for r in pos.get("reasons", [])],
            "risk_reward": pos.get("risk_reward", 0), "position_pct": round(alloc_pct, 1),
        })
        state["cash"] -= alloc
        state["total_deployed"] += alloc
        record_entry(state, sym)
        log(f"  {sym:>12s}  {price:>8.2f}  {qty:>5d}  {alloc:>10,.0f}  {alloc_pct:>5.1f}%  "
            f"{pos['sl_price']:>8.2f}  {pos['target_price']:>8.2f}  {pos['score']:>5.1f}")

    n_open = sum(1 for p in state["positions"] if p["status"] == "open")
    log(f"\n  Open: {n_open} | Cash: Rs {state['cash']:,.0f} | "
        f"Risk: {risk.get('total_risk_pct', 0)*100:.1f}% | R:R: {risk.get('portfolio_risk_reward', 0):.1f}")


def should_rescore(state):
    """Check if it's time for a full v4 rescore (every 30 min)."""
    last = state.get("last_rescore_time")
    if not last:
        return True
    try:
        last_dt = datetime.strptime(last, "%H:%M:%S").replace(
            year=datetime.now().year, month=datetime.now().month, day=datetime.now().day)
        return (datetime.now() - last_dt).total_seconds() >= RESCORE_INTERVAL_MIN * 60
    except (ValueError, TypeError):
        return True


def scan_and_react(state):
    """Core loop: price check + optional rescore + signal change detection."""
    state["scan_count"] += 1
    open_pos = [p for p in state["positions"] if p["status"] == "open"]
    log(f"\n{'='*65}\n  SCAN #{state['scan_count']} | {len(open_pos)} open | Cash: Rs {state['cash']:,.0f}\n{'='*65}")

    directions, do_rescore = {}, should_rescore(state)
    if do_rescore:
        log("  Running full v4 RESCORE...")
        state["rescore_count"] += 1
        state["last_rescore_time"] = datetime.now().strftime("%H:%M:%S")
        try:
            _, directions = get_v4_buys_and_directions()
        except Exception as e:
            log(f"  Rescore failed: {e}")

    if open_pos:
        prices = get_prices_batch([p["symbol"] for p in open_pos])
        unrealized = 0
        for pos in open_pos:
            sym, entry = pos["symbol"], pos["entry_price"]
            if sym not in prices:
                log(f"  {sym}: price unavailable"); continue
            price = prices[sym]
            pnl_pct = (price - entry) / entry * 100
            pnl_rs = (price - entry) * pos["qty"]
            unrealized += pnl_rs
            if price > pos.get("peak_price", entry):
                pos["peak_price"] = round(price, 2)
            reason = None
            # A. Signal change: BUY -> AVOID = exit
            if do_rescore and directions:
                sd = directions.get(sym, {})
                new_dir = sd.get("direction", pos.get("v4_direction", "BUY"))
                if new_dir == "AVOID":
                    reason = "SIGNAL_EXIT"
                    log(f"  {sym}: v4 flipped to AVOID (score {sd.get('score',0):.1f}) -- exiting!")
                elif new_dir != pos.get("v4_direction"):
                    pos["v4_direction"] = new_dir
                    pos["v4_score"] = sd.get("score", pos.get("v4_score", 0))
            # 2026-05-04 MVP: absolute Rs SL — fires before % targets so a single position
            # can't bleed past ABS_POSITION_SL_RS regardless of % SL distance or v4 direction
            if not reason and ABS_POSITION_SL_RS is not None and pnl_rs <= ABS_POSITION_SL_RS:
                reason = "ABS_RS_SL"
                log(f"  {sym}: ABS Rs SL hit — unrealized Rs {pnl_rs:+,.0f} <= floor Rs {ABS_POSITION_SL_RS:+,.0f}")
            # 2026-05-06 revival outer floor: -10% from entry forces exit regardless of trailing SL.
            # Catches outlier moves where 1% SL was trailed up to breakeven and price collapsed past it.
            if not reason and STOCK_LOSS_EXIT_PCT is not None and pnl_pct <= STOCK_LOSS_EXIT_PCT:
                reason = "ABS_PCT_SL"
                log(f"  {sym}: -10% SL hit — unrealized {pnl_pct:+.2f}% <= floor {STOCK_LOSS_EXIT_PCT:.0f}%")
            if not reason and price >= pos["target_price"]: reason = "TARGET"
            if not reason and price <= pos["sl_price"]: reason = "STOPLOSS"
            if not reason and pnl_pct >= TRAILING_TRIGGER_PCT:
                if not pos["trailing_activated"]:
                    pos["trailing_activated"] = True; pos["sl_price"] = entry
                    log(f"  {sym}: TRAILING ON -> SL at breakeven Rs {entry:.2f}")
                else:
                    trail_sl = round(pos["peak_price"] * (1 - TRAILING_STEP_PCT / 100), 2)
                    if trail_sl > pos["sl_price"]: pos["sl_price"] = trail_sl
            if reason:
                close_position(state, pos, price, reason)
            else:
                t = " [T]" if pos["trailing_activated"] else ""
                log(f"  {sym:>12s} Rs {price:>8.2f} {pnl_pct:+5.2f}% Rs {pnl_rs:+8,.0f} "
                    f"SL:{pos['sl_price']:.2f} TGT:{pos['target_price']:.2f}{t}")
        total_pnl = state["realized_pnl"] + unrealized
        if total_pnl > state["peak_pnl"]: state["peak_pnl"] = total_pnl
        dd = state["peak_pnl"] - total_pnl
        if dd > state["max_drawdown"]: state["max_drawdown"] = dd
        log(f"\n  Realized: Rs {state['realized_pnl']:+,.0f} | Unrealized: Rs {unrealized:+,.0f} | Total: Rs {total_pnl:+,.0f}")

    # 2026-05-06 revival mechanics: update post_drop_low for watchlisted stocks.
    # Tracks the lowest price seen since exit so the "near low" gate measures from the
    # actual bottom, not just the exit price.
    watchlist = state.get("watchlist", {})
    if watchlist:
        watch_prices = get_prices_batch(list(watchlist.keys()))
        for sym, current_px in watch_prices.items():
            entry = watchlist.get(sym)
            if entry and current_px < entry.get("post_drop_low", current_px):
                entry["post_drop_low"] = round(current_px, 2)

    # 2026-05-06: tier-3 HARD KILL request — flatten all positions immediately
    if state.get("force_flatten_now"):
        log(f"\n  ** HARD KILL TRIGGERED ** flattening all open positions")
        force_close_all(state)
        state["force_flatten_now"] = False  # clear so we don't loop

    if do_rescore and state["cash"] >= 10000:
        if check_circuit_breaker(state):
            tier = state.get("kill_switch_tier", 0)
            tier_name = ["clear", "WARN", "SOFT_HOLD", "HARD_KILL"][min(tier, 3)]
            log(f"\n  Free cash Rs {state['cash']:,.0f} -- entries blocked (kill switch tier {tier} {tier_name})")
        else:
            log(f"\n  Free cash Rs {state['cash']:,.0f} -- checking for new v4 BUY signals...")
            deploy_into_buys(state)


def close_position(state, pos, exit_price, reason):
    """Close a position and record it."""
    pnl = (exit_price - pos["entry_price"]) * pos["qty"]
    pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
    pos.update({"status": "closed", "exit_price": round(exit_price, 2),
                "exit_time": datetime.now().strftime("%H:%M:%S"),
                "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "exit_reason": reason})
    state["cash"] += pos["qty"] * exit_price
    state["realized_pnl"] += pnl
    state["closed_trades"].append({
        "symbol": pos["symbol"], "entry_price": pos["entry_price"],
        "exit_price": round(exit_price, 2), "qty": pos["qty"],
        "entry_time": pos["entry_time"], "exit_time": pos["exit_time"],
        "pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2), "reason": reason,
        "v4_score": pos.get("v4_score", 0), "composite_breakdown": pos.get("composite_breakdown", {}),
        "risk_reward": pos.get("risk_reward", 0), "position_pct": pos.get("position_pct", 0),
    })
    # Track consecutive losses for circuit breaker
    if pnl > 0:
        state["consecutive_losses"] = 0
        if state.get("circuit_breaker_active"):
            state["circuit_breaker_active"] = False
            log(f"  ** Circuit breaker RESET ** (win streak started)")
        # 2026-05-06: profitable exits do NOT increment stock_loss_count or
        # add to watchlist. Winners are unrestricted for re-entry.
    else:
        state["consecutive_losses"] = state.get("consecutive_losses", 0) + 1
        if state["consecutive_losses"] >= CIRCUIT_BREAKER_LOSSES and not state.get("circuit_breaker_active"):
            state["circuit_breaker_active"] = True
            state.setdefault("risk_events", []).append(
                f"{datetime.now().strftime('%H:%M')} CIRCUIT_BREAKER: {state['consecutive_losses']} consecutive losses")
            log(f"  ** CIRCUIT BREAKER ACTIVATED ** {state['consecutive_losses']} consecutive losses")
        # 2026-05-06 revival mechanics: increment per-stock loss count + add to watchlist
        sym = pos["symbol"]
        loss_counts = state.setdefault("stock_loss_count", {})
        loss_counts[sym] = loss_counts.get(sym, 0) + 1
        # Watchlist entry only on first loss of the day for this symbol; second loss goes
        # straight to blacklist via MAX_LOSSES_PER_STOCK_PER_DAY gate in deploy_into_buys.
        if loss_counts[sym] < MAX_LOSSES_PER_STOCK_PER_DAY:
            state.setdefault("watchlist", {})[sym] = {
                "exit_time": datetime.now().strftime("%H:%M:%S"),
                "exit_price": round(exit_price, 2),
                "post_drop_low": round(exit_price, 2),  # initial; updated by scan_and_react if price falls further
                "exit_reason": reason,
                "loss_pct": round(pnl_pct, 2),
            }
            log(f"  {sym}: added to watchlist (loss #{loss_counts[sym]}, exit {reason} @ Rs {exit_price:.2f}); "
                f"re-entry requires Bullish Engulfing + 1.5x volume + 11:15-14:45 IST + price within 0.5% of low")
        else:
            log(f"  {sym}: BLACKLISTED for the day ({loss_counts[sym]} losses; max {MAX_LOSSES_PER_STOCK_PER_DAY})")
            # Remove from watchlist so it's clearly in blacklist state, not "watching"
            state.get("watchlist", {}).pop(sym, None)

    tag = "WIN" if pnl > 0 else "LOSS"
    log(f"  >> {tag}: {pos['symbol']} x{pos['qty']} @ Rs {exit_price:.2f} ({reason}) "
        f"P&L: Rs {pnl:+,.0f} ({pnl_pct:+.2f}%)")


def force_close_all(state):
    """Force close all open positions at 3:15 PM."""
    open_pos = [p for p in state["positions"] if p["status"] == "open"]
    if not open_pos:
        log("  No positions to close")
        return

    log(f"\n  FORCE CLOSING {len(open_pos)} positions at market...")
    symbols = [p["symbol"] for p in open_pos]
    prices = get_prices_batch(symbols)

    for pos in open_pos:
        price = prices.get(pos["symbol"], pos["entry_price"])
        close_position(state, pos, price, "TIME_EXIT")


# ═══════════════════════════════════════════════════
# REPORTING
# ═══════════════════════════════════════════════════

def print_status(state):
    op = [p for p in state["positions"] if p["status"] == "open"]
    cl = state.get("closed_trades", [])
    print(f"\n{'='*70}\n  v4 PAPER TRADING  |  {state.get('date','today')}  |  Pool: Rs 10,00,000\n{'='*70}")
    cb = "ON" if state.get("circuit_breaker_active") else "off"
    bear = "BEAR" if state.get("bear_mode") else "normal"
    vix = "HIGH-VIX" if state.get("vix_high_mode") else "normal"
    sz = state.get("size_multiplier", 1.0)
    consec = state.get("consecutive_losses", 0)
    print(f"  Cash: Rs {state['cash']:,.0f} | Deployed: Rs {state['total_deployed']:,.0f} | "
          f"P&L: Rs {state['realized_pnl']:+,.0f} | Scans: {state['scan_count']} | Rescores: {state['rescore_count']}")
    print(f"  Risk: CB={cb} | Losses={consec} | Market={bear}/{vix} | Size={sz:.0%}")
    if op:
        print(f"\n  OPEN ({len(op)}):")
        for p in op:
            t = " [T]" if p.get("trailing_activated") else ""
            print(f"    {p['symbol']:>12s} x{p['qty']:<5d} @{p['entry_price']:.2f} "
                  f"SL:{p['sl_price']:.2f} TGT:{p['target_price']:.2f} v4:{p.get('v4_score',0):.0f}{t}")
    if cl:
        w = sum(1 for t in cl if t["pnl"] > 0)
        print(f"\n  CLOSED ({len(cl)}): {w} wins, {len(cl)-w} losses | Win rate: {w/len(cl)*100:.0f}%")
        for t in cl:
            print(f"    {'WIN ' if t['pnl']>0 else 'LOSS'} {t['symbol']:>12s} {t['entry_price']:.2f}->{t['exit_price']:.2f} "
                  f"Rs {t['pnl']:+,.0f} ({t['pnl_pct']:+.2f}%) [{t['reason']}]")
    if not op and not cl:
        print("\n  No trades yet")
    print(f"{'='*70}")


def generate_report(state):
    """Generate end-of-day markdown report."""
    today = datetime.now().strftime("%Y-%m-%d")
    report_path = TRADE_DIR / f"{today}_report.md"

    closed = state.get("closed_trades", [])
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    total_profit = sum(t["pnl"] for t in wins)
    total_loss = sum(t["pnl"] for t in losses)
    pnl_pct = state["realized_pnl"] / state["daily_pool"] * 100

    risk = state.get("portfolio_risk", {})

    s = state
    rr = risk.get('portfolio_risk_reward', 0)
    rows = [f"| Engine | **v4 composite scorer** |", f"| Daily Pool | Rs {s['daily_pool']:,.0f} |",
            f"| Total Deployed | Rs {s['total_deployed']:,.0f} |",
            f"| **Net P&L** | **Rs {s['realized_pnl']:+,.0f} ({pnl_pct:+.2f}%)** |",
            f"| Gross Profit | Rs {total_profit:+,.0f} |", f"| Gross Loss | Rs {total_loss:+,.0f} |",
            f"| Trades | {len(closed)} |", f"| Wins / Losses | {len(wins)} / {len(losses)} |",
            f"| **Win Rate** | **{win_rate:.0f}%** |", f"| Peak P&L | Rs {s['peak_pnl']:+,.0f} |",
            f"| Max Drawdown | Rs {s['max_drawdown']:,.0f} |",
            f"| Scans / Rescores | {s['scan_count']} / {s['rescore_count']} |",
            f"| Portfolio R:R | {rr:.1f} |"]
    lines = [f"# v4 Paper Trading Report -- {today}\n", "## Summary\n",
             "| Metric | Value |", "|--------|-------|"] + rows + [
             "", "## Trade Log\n",
             "| # | Stock | Entry | Exit | Qty | P&L | P&L% | Reason | v4 Score |",
             "|---|-------|-------|------|-----|-----|------|--------|----------|"]
    for i, t in enumerate(closed, 1):
        lines.append(f"| {i} | {t['symbol']} | {t['entry_price']:.2f} | {t['exit_price']:.2f} | "
                     f"{t['qty']} | Rs {t['pnl']:+,.0f} | {t['pnl_pct']:+.2f}% | "
                     f"{t['reason']} | {t.get('v4_score', 0):.1f} |")

    lines.append("\n## v4 Signal Quality Analysis\n")
    if closed:
        avg_w = sum(t.get("v4_score", 0) for t in wins) / len(wins) if wins else 0
        avg_l = sum(t.get("v4_score", 0) for t in losses) / len(losses) if losses else 0
        lines += [f"- Avg v4 score (winners): {avg_w:.1f}", f"- Avg v4 score (losers): {avg_l:.1f}",
                  f"- {'Score IS predictive' if avg_w > avg_l + 2 else 'Score not strongly predictive this session'}"]
        reasons = {}
        for t in closed:
            reasons.setdefault(t["reason"], {"count": 0, "pnl": 0})
            reasons[t["reason"]]["count"] += 1; reasons[t["reason"]]["pnl"] += t["pnl"]
        lines += ["\n### Exit Reason Breakdown\n", "| Reason | Count | P&L |", "|--------|-------|-----|"]
        lines += [f"| {r} | {d['count']} | Rs {d['pnl']:+,.0f} |" for r, d in sorted(reasons.items())]
        bds = [t.get("composite_breakdown", {}) for t in closed if t.get("composite_breakdown")]
        if bds:
            lines += ["\n### Avg Composite Breakdown\n", "| Sub-Score | Avg |", "|-----------|-----|"]
            for k in bds[0]:
                lines.append(f"| {k} | {sum(b.get(k,0) for b in bds)/len(bds):.3f} |")

    with open(report_path, "w") as f:
        f.write("\n".join(lines))
    log(f"  Report saved: {report_path}")
    return report_path


def push_to_devpilot(state):
    """Store results in DevPilot DB learnings table."""
    try:
        import psycopg2
        conn = psycopg2.connect(host="localhost", port=5499, user="devpilot",
                                password="TsUxQvfc7go5TDH8lsIKRTCv", dbname="devpilot")
        cur = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        cl = state.get("closed_trades", [])
        w = sum(1 for t in cl if t["pnl"] > 0)
        wr = w / len(cl) * 100 if cl else 0
        pp = state["realized_pnl"] / state["daily_pool"] * 100
        cur.execute("""INSERT INTO learnings (project, category, title, content, source, tags, active, created_at, updated_at)
            VALUES (%s,%s,%s,%s,'v4-paper-trade',%s,true,NOW(),NOW())""", (
            "tradepilot", "paper-trade",
            f"v4 {today}: Rs {state['realized_pnl']:+,.0f} ({pp:+.2f}%) | {len(cl)} trades | {wr:.0f}% win",
            json.dumps({"engine": "v4", "pool": DAILY_POOL, "deployed": state["total_deployed"],
                        "pnl": state["realized_pnl"], "pnl_pct": round(pp, 2), "trades": len(cl),
                        "wins": w, "win_rate": round(wr, 1), "peak_pnl": state["peak_pnl"],
                        "max_drawdown": state["max_drawdown"], "scans": state["scan_count"],
                        "rescores": state["rescore_count"], "portfolio_risk": state.get("portfolio_risk", {})}),
            ["paper-trade", "v4", today, f"wr-{wr:.0f}"]))
        conn.commit(); cur.close(); conn.close()
        log("  Results saved to DevPilot DB")
    except Exception as e:
        log(f"  DevPilot push failed: {e}")


# ═══════════════════════════════════════════════════
# MAIN LOOP
# ═══════════════════════════════════════════════════

def run():
    """Deploy and monitor. Runs until market close."""
    # Surface corp-action bans + revival mechanics + kill-switch tiers at startup
    _bans_at_boot = load_corp_action_bans()
    _bans_str = ", ".join(sorted(_bans_at_boot.keys())) if _bans_at_boot else "none"
    log(f"{'='*65}\n  v4 PAPER TRADING ENGINE | Rs {DAILY_POOL:,.0f} | Kelly-weighted\n"
        f"  Scan {SCAN_INTERVAL_MIN}min | Rescore {RESCORE_INTERVAL_MIN}min | "
        f"Exit {FORCE_EXIT_HOUR}:{FORCE_EXIT_MIN:02d}\n"
        f"  LEGACY GUARDS:\n"
        f"    Circuit breaker (consecutive losses): {CIRCUIT_BREAKER_LOSSES}\n"
        f"    VIX/Nifty regime check: INFORMATIONAL ONLY (no capital cut since 2026-05-06)\n"
        f"    Legacy daily-loss safety: {MAX_DAILY_LOSS_PCT}%\n"
        f"  MVP GUARDS (2026-05-04):\n"
        f"    Abs position SL: Rs {ABS_POSITION_SL_RS:+,.0f}\n"
        f"    Corp-action bans: {_bans_str}\n"
        f"  REVIVAL MECHANICS (2026-05-06):\n"
        f"    Per-stock pct SL: {STOCK_LOSS_EXIT_PCT:.0f}% (outer floor)\n"
        f"    Max losses per stock per day: {MAX_LOSSES_PER_STOCK_PER_DAY} (winners unrestricted)\n"
        f"    Re-entry gate: Bullish Engulfing + 1.5x volume + 11:15-14:45 IST + price within 0.5% of low\n"
        f"  KILL SWITCH (3-tier, 2026-05-06):\n"
        f"    WARN      Rs {ABS_DAILY_WARN_RS:+,.0f}  alert only\n"
        f"    SOFT HOLD Rs {ABS_DAILY_SOFT_HOLD_RS:+,.0f}  block new entries, hold existing\n"
        f"    HARD KILL Rs {ABS_DAILY_HARD_KILL_RS:+,.0f} OR {HARD_KILL_PCT_SL_COUNT}+ pct-SL exits  flatten all\n{'='*65}")
    state = load_state()
    n_open = sum(1 for p in state["positions"] if p["status"] == "open")

    # 2026-05-08: warm-up window. yfinance daily-bar aggregation lags 09:15-09:30 IST
    # at market open. Initial deployments before 09:30 are based on incomplete /
    # potentially NaN data. Bug bit 2026-05-08 — engine deployed at 09:19 into
    # the only 2 stocks with valid prices (cache was poisoned overnight), both
    # lost 1.3% on huge concentrated positions. Total: -Rs 6,884 from 2 trades.
    # Fix: refuse to do initial deploy before 09:30. Wait if necessary.
    WARMUP_HOUR = 9
    WARMUP_MIN = 30
    now = datetime.now()
    warmup_end = now.replace(hour=WARMUP_HOUR, minute=WARMUP_MIN, second=0, microsecond=0)
    if now < warmup_end:
        wait_sec = (warmup_end - now).total_seconds()
        log(f"\n  Warm-up window — waiting {wait_sec/60:.0f} min for yfinance "
            f"daily-bar to settle (until {warmup_end.strftime('%H:%M')} IST)")
        time.sleep(wait_sec)

    # 2026-05-09: Late-start preflight (specced 2026-04-27, finally coded today).
    # If boot time > 09:30, the morning's intraday signals are stale. Apply
    # late-mode filters: skip overextended stocks, reject LONGs with DOWN trend,
    # reject SHORTs with UP trend. If boot > 14:00, skip first deploy entirely.
    # Stores mode_label in state so deploy_into_buys can read it and adjust Kelly.
    from prototype.v4.preflight import is_late_start, should_skip_first_deploy
    now = datetime.now()
    if is_late_start(now):
        if should_skip_first_deploy(now):
            log(f"\n  ⚠ LATE BOOT ({now.strftime('%H:%M')} IST > 14:00) — skipping initial deploy. Will only manage existing positions.")
            state["preflight_mode"] = "MANAGE_ONLY"
        else:
            log(f"\n  ⚠ LATE BOOT ({now.strftime('%H:%M')} IST > 09:30) — entering LATE_ENTRY mode. Half-Kelly + filters active.")
            state["preflight_mode"] = "LATE_ENTRY"
        save_state(state)

    if n_open == 0 and state["cash"] > 10000:
        if state.get("preflight_mode") == "MANAGE_ONLY":
            log("\n--- v4 LATE BOOT: skipping initial deploy ---")
        else:
            log("\n--- INITIAL v4 DEPLOYMENT ---")
            deploy_into_buys(state); save_state(state)
    elif n_open > 0:
        log(f"\n  Resuming with {n_open} open positions")

    while True:
        now = datetime.now()
        force_exit = now.replace(hour=FORCE_EXIT_HOUR, minute=FORCE_EXIT_MIN, second=0)
        if now >= force_exit:
            state = load_state(); force_close_all(state); save_state(state); break
        if now >= now.replace(hour=15, minute=30, second=0):
            break
        next_scan = min(now + timedelta(minutes=SCAN_INTERVAL_MIN), force_exit)
        wait = (next_scan - now).total_seconds()
        if wait > 0:
            log(f"\n  Next scan in {wait/60:.0f} min (at {next_scan.strftime('%H:%M')})...")
            time.sleep(wait)
        state = load_state(); scan_and_react(state); save_state(state)

    log(f"\n{'='*65}\n  END OF DAY\n{'='*65}")
    state = load_state()
    print_status(state); generate_report(state); push_to_devpilot(state)
    _save_carry_forward(state)
    save_state(state)
    log(f"  Balance carried forward: Rs {state.get('daily_pool', DAILY_POOL) + state.get('realized_pnl', 0):,.0f}")
    cl = state.get("closed_trades", [])
    if cl:
        pp = state["realized_pnl"] / state["daily_pool"] * 100
        w = sum(1 for t in cl if t["pnl"] > 0)
        best, worst = max(cl, key=lambda t: t["pnl"]), min(cl, key=lambda t: t["pnl"])
        log(f"\n  FINAL: Rs {state['realized_pnl']:+,.0f} ({pp:+.2f}%) | {len(cl)} trades | {w} wins")
        log(f"  Best: {best['symbol']} Rs {best['pnl']:+,.0f} | Worst: {worst['symbol']} Rs {worst['pnl']:+,.0f}")
    else:
        log("  No trades today")


if __name__ == "__main__":
    if "--status" in sys.argv:
        print_status(load_state())
    elif "--summary" in sys.argv:
        s = load_state()
        cl = s.get("closed_trades", [])
        w = sum(1 for t in cl if t["pnl"] > 0)
        pp = s["realized_pnl"] / s["daily_pool"] * 100
        print(f"\nv4 Paper Trade | {s.get('date','today')} | Pool: Rs {s['daily_pool']:,.0f}")
        print(f"P&L: Rs {s['realized_pnl']:+,.0f} ({pp:+.2f}%)")
        if cl:
            print(f"Trades: {len(cl)} | Wins: {w} | Win rate: {w/len(cl)*100:.0f}%")
            print(f"Best: {max(cl,key=lambda t:t['pnl'])['symbol']} | Worst: {min(cl,key=lambda t:t['pnl'])['symbol']}")
        else:
            print("No trades yet")
        print(f"Deployed: Rs {s['total_deployed']:,.0f} | Cash: Rs {s['cash']:,.0f} | Rescores: {s['rescore_count']}")
    else:
        run()
