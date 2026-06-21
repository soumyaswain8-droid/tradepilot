#!/usr/bin/env python3
"""
Missed-Opportunities Watchdog
==============================
Runs continuously during market hours. Every 3 minutes:
  1. Pulls live prices for NIFTY 200 (the engine's actual universe)
  2. Reads each engine's current open positions
  3. Computes 4 categories:
     - WINNERS HELD       : positions moving in our favor
     - WINNERS MISSED     : big movers we don't have
     - LOSERS HELD WRONG  : positions moving against us (we're long, stock down OR we're short, stock up)
     - ON THE TABLE       : stocks moving 2%+ where engine should have signal
  4. Writes the report to prototype/data/missed-opportunities.json
  5. Logs human-readable summary to logs/missed-opps-watchdog.log

Reads-only — does NOT touch engine state or modify trading logic.

Built 2026-05-12 during market hours after observing engines were losing in a
bearish market (NIFTY -0.79%) with several large movers (OIL +6.62%, tech down
3-4%) uncovered by our positioning.

Usage:
  python3 scripts/missed-opportunities-watchdog.py              # run continuously
  python3 scripts/missed-opportunities-watchdog.py --once        # one snapshot then exit
  python3 scripts/missed-opportunities-watchdog.py --interval 60 # every 60 sec instead of 180
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Constants
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "prototype"))
sys.path.insert(0, str(ROOT / "prototype" / "v4"))

OUTPUT_FILE = ROOT / "prototype" / "data" / "missed-opportunities.json"
LOG_FILE = ROOT / "logs" / "missed-opps-watchdog.log"
DEFAULT_INTERVAL = 180  # 3 minutes
SIGNIFICANT_MOVE_PCT = 2.0  # mark movers >= +-2%
MARKET_OPEN = (9, 15)
MARKET_CLOSE = (15, 30)


def log(msg):
    """Append to log file + print."""
    stamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def is_market_hours():
    now = datetime.now()
    h, m = now.hour, now.minute
    after_open = (h, m) >= MARKET_OPEN
    before_close = (h, m) <= MARKET_CLOSE
    return after_open and before_close


def load_our_positions():
    """Read all 7 engines' current positions. Returns {symbol: [{engine, direction}, ...]}"""
    today = datetime.now().strftime("%Y-%m-%d")
    positions_by_sym = {}

    def _add(sym, engine, direction):
        positions_by_sym.setdefault(sym, []).append({
            "engine": engine, "direction": direction
        })

    # v4: date-stamped
    v4f = ROOT / "docs" / "paper-trades" / "v4" / f"{today}.json"
    if v4f.exists():
        try:
            state = json.load(open(v4f))
            for p in state.get("positions", []):
                if p.get("status") == "open":
                    _add(p.get("symbol", ""), "v4", p.get("direction", "LONG"))
        except Exception:
            pass

    # v5 family: positions_active.json
    for eng in ["v5", "v5_classic", "v5_6", "v5_7", "v5_8", "v6"]:
        f = ROOT / "docs" / "paper-trades" / eng / "positions_active.json"
        if not f.exists():
            continue
        try:
            data = json.load(open(f))
            pos = data.get("positions", {})
            if isinstance(pos, dict):
                for pool, plist in pos.items():
                    if not isinstance(plist, list):
                        continue
                    for p in plist:
                        d = p.get("direction", p.get("position_type", "LONG"))
                        _add(p.get("symbol", ""), eng, d)
            elif isinstance(pos, list):
                for p in pos:
                    _add(p.get("symbol", ""), eng, p.get("direction", "LONG"))
        except Exception:
            continue

    return positions_by_sym


def fetch_movers():
    """Batch-fetch today's prices for NIFTY 200. Returns list of (symbol, last, prev, pct)."""
    try:
        import yfinance as yf
        import pandas as pd
        from config import ACTIVE_SYMBOLS_YF
    except ImportError as e:
        log(f"FATAL: import failed: {e}")
        return []

    yf_str = " ".join(ACTIVE_SYMBOLS_YF)
    try:
        df = yf.download(yf_str, period="2d", interval="1d",
                         group_by="ticker", progress=False, timeout=30, threads=True)
    except Exception as e:
        log(f"yfinance batch failed: {e}")
        return []

    movers = []
    for sym in ACTIVE_SYMBOLS_YF:
        try:
            if isinstance(df.columns, pd.MultiIndex) and sym in df.columns.get_level_values(0):
                s = df[sym]
                if len(s) < 2:
                    continue
                today = float(s.iloc[-1]["Close"])
                prev = float(s.iloc[-2]["Close"])
                if prev > 0 and today > 0:
                    chg = (today - prev) / prev * 100
                    movers.append((sym.replace(".NS", ""), today, prev, chg))
        except Exception:
            continue
    return movers


def categorize(movers, our_positions):
    """Slice movers into 4 categories vs our positions."""
    winners_held = []   # we hold, moving in our favor
    losers_held = []    # we hold, moving against us
    winners_missed = [] # big movers we don't have, model should have signaled
    on_table = []       # all 2%+ movers we have no position in

    for sym, last, prev, chg in movers:
        positions = our_positions.get(sym, [])
        if positions:
            # We hold this. Classify each engine's position vs the move.
            for p in positions:
                if p["direction"] == "LONG":
                    if chg > 0:
                        winners_held.append({"symbol": sym, "engine": p["engine"], "direction": "LONG", "price": last, "chg_pct": chg})
                    elif chg < 0:
                        losers_held.append({"symbol": sym, "engine": p["engine"], "direction": "LONG", "price": last, "chg_pct": chg})
                else:  # SHORT
                    if chg < 0:
                        winners_held.append({"symbol": sym, "engine": p["engine"], "direction": "SHORT", "price": last, "chg_pct": chg})
                    elif chg > 0:
                        losers_held.append({"symbol": sym, "engine": p["engine"], "direction": "SHORT", "price": last, "chg_pct": chg})
        else:
            # We don't hold. Is it a significant move?
            if abs(chg) >= SIGNIFICANT_MOVE_PCT:
                on_table.append({"symbol": sym, "price": last, "chg_pct": chg,
                                  "suggested": "LONG" if chg > 0 else "SHORT"})
                if abs(chg) >= 3.0:  # big moves
                    winners_missed.append({"symbol": sym, "price": last, "chg_pct": chg,
                                            "suggested": "LONG" if chg > 0 else "SHORT"})

    return {
        "winners_held": sorted(winners_held, key=lambda x: -abs(x["chg_pct"])),
        "losers_held": sorted(losers_held, key=lambda x: -abs(x["chg_pct"])),
        "winners_missed": sorted(winners_missed, key=lambda x: -abs(x["chg_pct"])),
        "on_table": sorted(on_table, key=lambda x: -abs(x["chg_pct"])),
    }


def snapshot():
    """Run one watchdog cycle."""
    log("─── Watchdog cycle ───")
    movers = fetch_movers()
    if not movers:
        log("⚠ no movers fetched (yfinance failure?) — skipping cycle")
        return

    our_positions = load_our_positions()
    n_our = sum(len(v) for v in our_positions.values())

    cats = categorize(movers, our_positions)

    # Compute summary stats
    n_winners_held = len(cats["winners_held"])
    n_losers_held = len(cats["losers_held"])
    n_missed = len(cats["winners_missed"])
    n_on_table = len(cats["on_table"])

    log(f"  Universe: {len(movers)} stocks  |  Our positions: {n_our} (across {len(our_positions)} symbols)")
    log(f"  ✅ Winners held: {n_winners_held}  |  ❌ Losers held: {n_losers_held}  |  🎯 Missed gainers/losers (>3%): {n_missed}  |  💡 On table (>2%): {n_on_table}")

    # Print top missed (where we should have signaled)
    if cats["winners_missed"]:
        log("  Top missed opportunities (we have no position):")
        for m in cats["winners_missed"][:5]:
            log(f"    {m['suggested']:>5}  {m['symbol']:>14}  Rs {m['price']:>9,.2f}  {m['chg_pct']:+7.2f}%")

    # Print biggest wrong-way positions
    if cats["losers_held"][:3]:
        log("  Worst wrong-way positions (we hold, moving against us):")
        for p in cats["losers_held"][:5]:
            log(f"    {p['engine']:>11} {p['direction']:>5}  {p['symbol']:>14}  {p['chg_pct']:+7.2f}%")

    # Write JSON snapshot
    output = {
        "generated_at": datetime.now().isoformat(),
        "time_ist": datetime.now().strftime("%H:%M:%S"),
        "in_market_hours": is_market_hours(),
        "universe_size": len(movers),
        "our_open_positions": n_our,
        "our_unique_symbols": len(our_positions),
        "summary": {
            "winners_held": n_winners_held,
            "losers_held": n_losers_held,
            "winners_missed": n_missed,
            "on_table": n_on_table,
        },
        "top_movers": [
            {"symbol": m[0], "price": m[1], "chg_pct": round(m[3], 2)}
            for m in sorted(movers, key=lambda x: -abs(x[3]))[:30]
        ],
        "categories": {
            "winners_held": cats["winners_held"][:30],
            "losers_held": cats["losers_held"][:30],
            "winners_missed": cats["winners_missed"][:30],
            "on_table": cats["on_table"][:30],
        },
    }
    try:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write — write tmp then rename
        tmp = OUTPUT_FILE.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(output, f, indent=2)
        os.replace(tmp, OUTPUT_FILE)
        log(f"  Snapshot written: {OUTPUT_FILE.name} ({OUTPUT_FILE.stat().st_size} bytes)")
    except Exception as e:
        log(f"  ⚠ Failed to write snapshot: {e}")


def main():
    interval = DEFAULT_INTERVAL
    once = False
    args = sys.argv[1:]
    if "--once" in args:
        once = True
    if "--interval" in args:
        try:
            interval = int(args[args.index("--interval") + 1])
        except (ValueError, IndexError):
            pass

    log(f"=== Missed-Opportunities Watchdog START ===")
    log(f"  Interval: {interval}s · Once: {once}")
    log(f"  Output: {OUTPUT_FILE}")
    log(f"  Market hours: {is_market_hours()}")

    while True:
        try:
            snapshot()
        except KeyboardInterrupt:
            log("=== Watchdog stopped (user) ===")
            return
        except Exception as e:
            log(f"⚠ snapshot error: {e}")

        if once:
            log("=== Watchdog stopped (--once) ===")
            return

        # Sleep but break early if market closed (save battery)
        if not is_market_hours():
            log("  Outside market hours — sleeping longer (600s)")
            time.sleep(600)
        else:
            time.sleep(interval)


if __name__ == "__main__":
    main()
