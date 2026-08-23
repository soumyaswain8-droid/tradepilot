#!/usr/bin/env python3
"""
real1k — the Rs1,000 REAL-MONEY pilot. Manual execution, system-tracked.

BORN 2026-08-23 (Soumya): three months of paper iteration; deploy Rs1,000 of real
cash and measure what it actually earns. NO order API — Soumya places orders by hand
in the broker app; this script supplies ONE trade card a day and keeps the ledger.

WHY MANUAL IS THE RIGHT CALL HERE (not a compromise)
  - Zero added cost, zero new attack surface, and the live-order safety chain
    (KITE_LIVE_ORDERS etc.) stays untouched.
  - The pilot's PURPOSE is ground truth: real fills vs our assumed fills, real
    slippage vs the +0.60bps we measured from depth data, manual latency, and the
    psychological reality of pressing the button. Rs1,000 caps the tuition.

WHAT Rs1,000 CAN HONESTLY EARN (said up front, on the record)
  Intraday MIS at Rs1,000: round trip ~Rs1.1 at Zerodha-style min(0.03%, Rs20)
  brokerage. A well-captured 1% move = Rs10 gross, ~Rs9 net. Our measured intraday
  edge is ~zero net — expect single-digit rupees either way per day. The dataset is
  the product; the rupees are the receipt.

  DELIVERY IS FORBIDDEN AT THIS SIZE: the DP charge (~Rs18.8/scrip on sell) is 1.9%
  of the whole account — CNC round trip ~2.2%. Intraday only, square off same day.

USAGE
  python3 scripts/real1k.py --card            # morning: pick + send the trade card
  python3 scripts/real1k.py --filled 123.45   # you got filled at this price
  python3 scripts/real1k.py --exited 124.60   # you exited at this price
  python3 scripts/real1k.py --skip "reason"   # no trade today
  python3 scripts/real1k.py --status
"""
from __future__ import annotations

import argparse, json, sys, warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENGINE = "real1k"
DIR = ROOT / "docs" / "paper-trades" / ENGINE     # fleet schema -> desk shows it
CAPITAL = 1000.0
LEVERAGE = 4.0           # MIS intraday leverage (broker gives ~4-5x on liquid names).
                         # Exposure = Rs4,000 on Rs1,000 capital: a caught 1% move
                         # = ~Rs40 = 4% ON CAPITAL. This is the only honest
                         # accelerant in cash equity; the Rs3-4k ambition otherwise
                         # belongs to options (modal outcome -100%) or to months of
                         # compounding. SL 0.8% on 4x = 3.2% of capital at risk per
                         # day — the practical ceiling for a pilot.
MAX_PRICE = 3500.0       # qty from exposure, so pricier liquid names now fit
SL_PCT, TGT_PCT = 0.8, 1.5
TIME_STOP = "14:45"


def state_file():
    return DIR / "pilot_state.json"


def load():
    f = state_file()
    if f.exists():
        return json.loads(f.read_text())
    return {"open": None, "history": []}


def save(s):
    DIR.mkdir(parents=True, exist_ok=True)
    state_file().write_text(json.dumps(s, indent=2))


def day_file():
    f = DIR / f"{datetime.now():%Y-%m-%d}.json"
    if f.exists():
        return json.loads(f.read_text()), f
    return {"date": f.stem, "engine": ENGINE, "total_capital": CAPITAL,
            "pools": {"INTRADAY": {"positions": [], "closed": [], "pnl": 0.0}},
            "summary": {"total_pnl": 0.0, "trades": 0, "wins": 0, "losses": 0}}, f


def tg(msg):
    try:
        from prototype.v5.telegram_bot import send_alert
        send_alert(msg)
    except Exception as e:
        print(f"  (telegram failed: {e})")


def pick():
    """One candidate: the fleet's strongest BUY under Rs900, liquid. Uses the same
    scorer the dashboard shows — no new signal claims, this is a pipeline test."""
    import requests
    try:
        rows = requests.get("http://127.0.0.1:5050/api/scores", timeout=10).json()
    except Exception:
        rows = []
    cands = [r for r in rows
             if (r.get("signal") or "").upper() == "BUY"
             and r.get("price") and 20 < float(r["price"]) <= MAX_PRICE]
    cands.sort(key=lambda r: -(r.get("score") or 0))
    return cands[0] if cands else None


def cmd_card():
    s = load()
    if s["open"]:
        print(f"  position already open: {s['open']['symbol']} — exit it first")
        return
    now = datetime.now()
    if not (now.weekday() < 5 and (9, 15) <= (now.hour, now.minute) < (14, 0)):
        print("  [SESSION-GUARD] cards only 09:15-14:00 on trading days")
        return
    c = pick()
    if not c:
        print("  no BUY under Rs900 right now — try again after the next score refresh")
        return
    px = float(c["price"])
    qty = int(CAPITAL * LEVERAGE / px)
    if qty < 1:
        print(f"  {c['symbol']} too pricey even at {LEVERAGE}x — widen MAX_PRICE"); return
    sl = round(px * (1 - SL_PCT / 100), 2)
    tgt = round(px * (1 + TGT_PCT / 100), 2)
    card = {"symbol": c["symbol"], "ref_price": px, "qty": qty,
            "sl": sl, "target": tgt, "time_stop": TIME_STOP,
            "carded_at": now.strftime("%Y-%m-%d %H:%M:%S"),
            "score": c.get("score")}
    card["paper"] = "--paper" in sys.argv
    s["open"] = {**card, "status": "CARDED"}
    save(s)
    msg = (f"*Rs1000 REAL PILOT — trade card*\n"
           f"BUY {c['symbol']} x{qty} (MIS, intraday)\n"
           f"ref {px:.2f} | SL {sl} | target {tgt}\n"
           f"time-stop {TIME_STOP} — square off, never carry\n"
           f"after fill: real1k.py --filled <price>")
    tg(msg)
    print(f"  CARD: BUY {c['symbol']} x{qty} @ ~{px:.2f}  SL {sl}  TGT {tgt}")
    print(f"  sent to Telegram. Log the real fill with --filled <price>.")


def cmd_filled(price):
    s = load()
    o = s.get("open")
    if not o or o["status"] != "CARDED":
        print("  no carded trade waiting for a fill"); return
    o["entry_price"] = price
    o["entry_time"] = datetime.now().strftime("%H:%M:%S")
    o["slippage_vs_ref_pct"] = round((price / o["ref_price"] - 1) * 100, 4)
    o["status"] = "OPEN"
    save(s)
    print(f"  FILLED {o['symbol']} x{o['qty']} @ {price} "
          f"(slippage vs card: {o['slippage_vs_ref_pct']:+.3f}%)")


def cmd_exited(price):
    s = load()
    o = s.get("open")
    if not o or o["status"] != "OPEN":
        print("  no open position"); return
    pnl = (price - o["entry_price"]) * o["qty"]
    pct = (price / o["entry_price"] - 1) * 100
    j, f = day_file()
    j["pools"]["INTRADAY"]["closed"].append({
        "symbol": o["symbol"], "entry_price": o["entry_price"], "qty": o["qty"],
        "cost": round(o["entry_price"] * o["qty"], 2),
        "entry_time": o["entry_time"], "entry_date": f.stem,
        "exit_price": price, "exit_time": datetime.now().strftime("%H:%M:%S"),
        "sl_price": o["sl"], "target_price": o["target"],
        "pnl": round(pnl, 2), "pnl_pct": round(pct, 2),
        "reason": "MANUAL", "position_type": "LONG", "pool": "INTRADAY",
        "slippage_entry_pct": o.get("slippage_vs_ref_pct"),
        "real_money": not o.get("paper", False)})
    j["pools"]["INTRADAY"]["pnl"] += pnl
    j["summary"]["total_pnl"] += pnl
    j["summary"]["trades"] += 1
    j["summary"]["wins" if pnl > 0 else "losses"] += 1
    f.write_text(json.dumps(j, indent=2))
    s["history"].append({**o, "exit_price": price, "pnl": round(pnl, 2),
                         "exit_date": f.stem})
    s["open"] = None
    save(s)
    print(f"  CLOSED {o['symbol']}: Rs{pnl:+.2f} ({pct:+.2f}%) — ledger + dashboard updated")
    tg(f"*Rs1000 PILOT closed*: {o['symbol']} Rs{pnl:+.2f} ({pct:+.2f}%)")


def cmd_status():
    s = load()
    if s["open"]:
        print(f"  open: {json.dumps(s['open'], indent=2)}")
    hist = s.get("history", [])
    tot = sum(h["pnl"] for h in hist)
    print(f"  closed pilots: {len(hist)} | cumulative REAL P&L: Rs{tot:+.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", action="store_true")
    ap.add_argument("--filled", type=float)
    ap.add_argument("--exited", type=float)
    ap.add_argument("--skip", type=str)
    ap.add_argument("--paper", action="store_true",
                    help="rehearsal mode: identical flow, ledger marked paper")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.card: cmd_card()
    elif a.filled: cmd_filled(a.filled)
    elif a.exited: cmd_exited(a.exited)
    elif a.skip:
        s = load(); s["open"] = None
        s.setdefault("history", []).append({"skipped": a.skip,
            "date": datetime.now().strftime("%Y-%m-%d")})
        save(s); print(f"  skipped: {a.skip}")
    else: cmd_status()


if __name__ == "__main__":
    main()
