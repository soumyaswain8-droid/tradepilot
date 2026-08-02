#!/usr/bin/env python3
"""
us-paper-trade — US equity paper-trading engine (LONG-ONLY CASH).

Run:
    python3 scripts/us-paper-trade.py --once     # one scan, then exit
    python3 scripts/us-paper-trade.py            # session loop
    python3 scripts/us-paper-trade.py --status

WHAT IT IS
    A long-only, cash, unleveraged US equity engine on named factors (momentum,
    trend, low-vol, quality proxy) with momentum weight cut in elevated-volatility
    regimes. Signals come from prototype/us/signals_us.py; fills from
    prototype/us/broker.py (internal simulator by default, Alpaca paper optional).

WHY LONG-ONLY — a regulatory boundary, not a strategy choice
    RBI bars LRS remittance for forex trading and for margins/margin calls
    (VERIFIED, rbi.org.in). For an Indian resident the only clearly-safe lane is
    long-only cash. The India fleet's short book is NOT portable here. The block is
    enforced in broker.py, which raises ShortSellingBlocked rather than trusting
    strategy code to behave.
    See docs/research/us-market/04-regulatory-lrs-tax.md

ISOLATION FROM THE INDIA FLEET — deliberate, and load-bearing
    Separate state dir, separate cache namespace, separate logs, separate schedule.
    The India stack has had two incidents traced to a shared cache, and a rescue job
    that relaunched the whole fleet. Nothing here can touch docs/paper-trades/v5* or
    prototype/data/cache/.

SESSION
    US regular hours 09:30-16:00 ET = 19:00-01:30 IST (EDT) / 20:00-02:30 IST (EST).
    This engine CANNOT share the India 08:50-15:35 IST cadence — it runs overnight,
    unattended, which is exactly why it exits cleanly and writes state every scan.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prototype.us.data_us import get_history, get_quotes, load_universe  # noqa: E402
from prototype.us.signals_us import generate_signals                     # noqa: E402
from prototype.us.broker import get_broker, ShortSellingBlocked          # noqa: E402

ENGINE = os.environ.get("US_ENGINE_NAME", "us_v1")
TRADE_DIR = ROOT / "docs" / "paper-trades" / ENGINE
LOG_DIR = ROOT / "logs"
TRADE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = TRADE_DIR / "positions_active.json"
CARRY_FILE = TRADE_DIR / "carry_forward.json"
LOG_FILE = LOG_DIR / f"{ENGINE}-paper-trade.log"

TOTAL_CAPITAL = float(os.environ.get("US_CAPITAL", "100000"))   # USD 100k paper
MAX_POSITIONS = int(os.environ.get("US_MAX_POSITIONS", "10"))
SCAN_INTERVAL_MIN = int(os.environ.get("US_SCAN_MIN", "15"))
BROKER_NAME = os.environ.get("US_BROKER", "sim")

logging.basicConfig(level=logging.INFO, format="%(message)s",
                    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()])
log = logging.getLogger(ENGINE).info


def _now() -> str:
    return datetime.now().strftime("%H:%M:%S")


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception as e:
            log(f"[{_now()}] state unreadable ({e}) — starting fresh")
    return {"engine": ENGINE, "capital": TOTAL_CAPITAL, "cash": TOTAL_CAPITAL,
            "positions": {}, "closed": [], "started": datetime.now().isoformat()}


def save_state(st: dict) -> None:
    st["updated"] = datetime.now().isoformat()
    STATE_FILE.write_text(json.dumps(st, indent=2, default=str))
    day = TRADE_DIR / f"{datetime.now():%Y-%m-%d}.json"
    day.write_text(json.dumps(st, indent=2, default=str))


def summarise(st: dict, quotes: dict) -> dict:
    pos = st["positions"]
    mv = sum(p["qty"] * quotes.get(s, {}).get("price", p["entry_price"]) for s, p in pos.items())
    unreal = sum(p["qty"] * (quotes.get(s, {}).get("price", p["entry_price"]) - p["entry_price"])
                 for s, p in pos.items())
    realised = sum(c["pnl"] for c in st["closed"])
    wins = sum(1 for c in st["closed"] if c["pnl"] > 0)
    n = len(st["closed"])
    return {"cash": round(st["cash"], 2), "market_value": round(mv, 2),
            "equity": round(st["cash"] + mv, 2), "unrealised": round(unreal, 2),
            "realised": round(realised, 2), "open_positions": len(pos),
            "closed_trades": n, "win_rate": round(wins / n * 100, 1) if n else 0.0}


def scan(st: dict, broker) -> dict:
    universe = load_universe("nasdaq100")
    log(f"[{_now()}] scanning {len(universe)} symbols...")

    hist = get_history(universe, years=2)
    if hist is None:
        log(f"[{_now()}] ERROR no history — skipping scan (no trades on bad data)")
        return st
    close = hist["Close"] if "Close" in hist else hist

    held = set(st["positions"].keys())
    sigs = generate_signals(close, held=held)
    if not sigs:
        log(f"[{_now()}] no signals produced — skipping")
        return st

    quotes = get_quotes(list({s.symbol for s in sigs[:40]} | held))
    regimes = {}
    for s in sigs:
        regimes[s.vol_regime] = regimes.get(s.vol_regime, 0) + 1
    log(f"[{_now()}] regime: " + ", ".join(f"{k} {v}" for k, v in regimes.items()))

    # ── EXITS first, so capital is freed before entries ──
    for s in [x for x in sigs if x.action == "EXIT" and x.symbol in st["positions"]]:
        p = st["positions"][s.symbol]
        px = quotes.get(s.symbol, {}).get("price", s.price)
        try:
            f = broker.place_order(s.symbol, "sell", p["qty"], px, holding_qty=p["qty"])
        except ShortSellingBlocked as e:
            log(f"[{_now()}] BLOCKED {s.symbol}: {e}")
            continue
        if not f:
            continue
        pnl = (f.price - p["entry_price"]) * p["qty"] - f.commission
        st["cash"] += f.price * p["qty"] - f.commission
        st["closed"].append({"symbol": s.symbol, "qty": p["qty"],
                             "entry_price": p["entry_price"], "exit_price": f.price,
                             "pnl": round(pnl, 2), "exit_ts": f.ts,
                             "reason": f"score {s.score} < exit floor"})
        del st["positions"][s.symbol]
        log(f"[{_now()}]   EXIT  {s.symbol:<6} {p['qty']:>4} @ ${f.price:<9.2f} pnl ${pnl:+.2f}")

    # ── ENTRIES ──
    slots = MAX_POSITIONS - len(st["positions"])
    if slots > 0:
        budget = st["cash"] / max(slots, 1)
        for s in [x for x in sigs if x.action == "BUY" and x.symbol not in st["positions"]][:slots]:
            px = quotes.get(s.symbol, {}).get("price", s.price)
            if px <= 0:
                continue
            qty = int(budget // px)
            if qty < 1:
                continue
            cost = qty * px
            if cost > st["cash"]:
                continue
            try:
                f = broker.place_order(s.symbol, "buy", qty, px, holding_qty=0)
            except ShortSellingBlocked as e:
                log(f"[{_now()}] BLOCKED {s.symbol}: {e}")
                continue
            if not f:
                continue
            st["cash"] -= f.price * qty + f.commission
            st["positions"][s.symbol] = {
                "qty": qty, "entry_price": f.price, "entry_ts": f.ts,
                "score": s.score, "vol_regime": s.vol_regime, "reason": s.reason}
            log(f"[{_now()}]   BUY   {s.symbol:<6} {qty:>4} @ ${f.price:<9.2f} "
                f"score {s.score} [{s.vol_regime}]")

    st["summary"] = summarise(st, quotes)
    save_state(st)
    sm = st["summary"]
    log(f"[{_now()}] equity ${sm['equity']:,.2f} | cash ${sm['cash']:,.2f} | "
        f"open {sm['open_positions']} | realised ${sm['realised']:+,.2f} | "
        f"unrealised ${sm['unrealised']:+,.2f}")
    return st


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="single scan then exit")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--broker", default=BROKER_NAME, choices=["sim", "alpaca"])
    a = ap.parse_args()

    st = load_state()
    if a.status:
        print(json.dumps(st.get("summary", {}) or summarise(st, {}), indent=2))
        return 0

    broker = get_broker(a.broker)
    log("=" * 62)
    log(f"  {ENGINE} | US LONG-ONLY CASH | ${TOTAL_CAPITAL:,.0f} | broker={broker.name}")
    log(f"  max positions {MAX_POSITIONS} | scan {SCAN_INTERVAL_MIN}m")
    log(f"  RBI lane: long-only cash, no margin, no FX. Shorts blocked in broker.py")
    log("=" * 62)

    if a.once:
        scan(st, broker)
        return 0

    while True:
        try:
            st = scan(st, broker)
        except KeyboardInterrupt:
            log(f"[{_now()}] interrupted — state saved")
            save_state(st)
            return 0
        except Exception as e:
            log(f"[{_now()}] scan error: {type(e).__name__}: {e}")
        time.sleep(SCAN_INTERVAL_MIN * 60)


if __name__ == "__main__":
    sys.exit(main())
