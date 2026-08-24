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

# Sizing now lives in one module so the paper->real switch on Wednesday is a single
# change and cannot disagree between lanes. See prototype/lane_config.py for why
# Rs3,000 splits into two positions (splitting is free below the fee cliff) and why
# the price ceiling is DERIVED from MIN_QTY rather than chosen.
from prototype.lane_config import (LANE_CAPITAL, LANE_MODE, LEVERAGE, N_POSITIONS,
                                   MIN_QTY, MIN_PRICE, MAX_PRICE, PER_POSITION)
CAPITAL = LANE_CAPITAL

# SMALL-CAPITAL BAND — measured live 2026-08-24, not assumed.
# The engines size for Rs10L; down here the binding constraint is QUANTIZATION, not
# fees. Below Rs80 we drift toward illiquid names where the spread, not the fee, is
# the enemy. Measured across NIFTY-200 in-band:
#   73/200 names tradeable | median spread 2.6 bps | touch absorbs the FULL order
# Two consequences worth stating:
#   1. fees stay 0.106% (percentage brokerage) — small size carries NO fee penalty,
#      and it is identical whether we run one position or two
#   2. slippage is ~ZERO because these orders never move the book — the one genuine
#      ADVANTAGE we have over the Rs1L positions, which pay 0.60 bps of impact
MAX_SPREAD_BPS = 15.0    # wider than this and the spread costs more than the fee
SL_PCT, TGT_PCT = 0.8, 1.5
TIME_STOP = "14:45"


def state_file():
    return DIR / "pilot_state.json"


def load():
    """State carries a LIST of open positions.

    Migrates the old single-position shape transparently: the Rs1k pilot stored
    {"open": {...}} and there may be a live one on disk. Silently dropping it would
    lose a real trade, so it is lifted into the list rather than overwritten.
    """
    f = state_file()
    s = json.loads(f.read_text()) if f.exists() else {}
    o = s.get("open")
    if isinstance(o, dict):
        s["open"] = [o]
    elif o is None:
        s["open"] = []
    s.setdefault("history", [])
    return s


def find_pos(s, status, symbol=None):
    """Pick the position a --filled/--exited refers to.

    With two positions open, a bare price is ambiguous — and guessing which one it
    meant would book a fill against the wrong stock. Ambiguity is an error, not a
    coin flip.
    """
    m = [p for p in s["open"] if p.get("status") == status
         and (symbol is None or p["symbol"].upper() == symbol.upper())]
    if not m:
        return None, (f"no {status} position" +
                      (f" for {symbol}" if symbol else ""))
    if len(m) > 1:
        return None, ("ambiguous — %d %s positions (%s). Pass --symbol"
                      % (len(m), status, ", ".join(p["symbol"] for p in m)))
    return m[0], None


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


def candidates(relaxed=False):
    """Rank the day's tradeable names.

    PRIMARY: the scout team (4 lenses over ~889 liquid names, confluence-ranked).
    It replaced /api/scores here because that endpoint serves NIFTY-50 only — barely
    a dozen names land in our price band, so the lane was choosing from a shortlist
    that had already thrown away 95% of the market before we looked.

    FALLBACK: /api/scores, so the lane still works if Kite is down.
    """
    try:
        from prototype.agents.scouts import ScoutTeam
        board = ScoutTeam(verbose=False).scan(top=60)
        if board:
            return ([{"symbol": b["symbol"], "price": b["ltp"],
                      "score": b["score"], "agree": b["agree"],
                      "why": b["why"], "src": "scouts"} for b in board], True)
    except Exception as e:
        print(f"  scouts unavailable ({str(e)[:60]}) — falling back to /api/scores")
    import requests
    try:
        rows = requests.get("http://127.0.0.1:5050/api/scores", timeout=10).json()
    except Exception:
        rows = []
    pool = [r for r in rows if r.get("price")
            and MIN_PRICE <= float(r["price"]) <= MAX_PRICE]
    buys = [r for r in pool if (r.get("signal") or "").upper() == "BUY"]
    cands = buys if buys else (sorted(pool, key=lambda r: -(r.get("score") or 0))
                               if relaxed else [])
    cands.sort(key=lambda r: -(r.get("score") or 0))
    for c in cands:
        c["src"] = "api/scores"
    return cands, bool(buys)


def pick(relaxed=False, exclude=None):
    """Strongest candidate that is actually TRADEABLE at this size: in the
    quantization band, spread under the fee, and with the touch deep enough to fill
    the whole order. Screens against LIVE depth, not just the ranking — a signal we
    cannot fill cleanly is not a signal down here."""
    exclude = {s.upper() for s in (exclude or set())}
    cands, is_signal = candidates(relaxed)
    cands = [c for c in cands
             if c["symbol"].upper() not in exclude
             and c.get("price") and MIN_PRICE <= float(c["price"]) <= MAX_PRICE]
    if not cands:
        return None, ("nothing in the Rs%.0f-%.0f band (excluding %d already held)"
                      % (MIN_PRICE, MAX_PRICE, len(exclude)))
    from prototype.v4 import kite_data as kd
    k = kd.client()
    names = [c["symbol"] for c in cands[:25]]
    try:
        q = k.quote([f"NSE:{s}" for s in names])
    except Exception as e:
        return None, f"quote failed: {e}"
    for c in cands[:25]:
        d = q.get(f"NSE:{c['symbol']}")
        if not d:
            continue
        px = float(d.get("last_price") or 0)
        if not (MIN_PRICE <= px <= MAX_PRICE):
            continue
        dep = d.get("depth") or {}
        bid = (dep.get("buy") or [{}])[0]
        ask = (dep.get("sell") or [{}])[0]
        bp, ap = bid.get("price") or 0, ask.get("price") or 0
        if not bp or not ap:
            continue
        spread = (ap - bp) / px * 10000
        qty = int(PER_POSITION / px)     # per SLOT, not the whole book
        if qty < MIN_QTY or spread > MAX_SPREAD_BPS:
            continue
        c = dict(c)
        c["price"] = px
        c["spread_bps"] = round(spread, 2)
        c["touch_qty"] = ask.get("quantity") or 0
        c["fills_at_touch"] = (ask.get("quantity") or 0) >= qty
        c["relaxed"] = not is_signal
        return c, None
    return None, "candidates found but none passed the spread/depth screen"


def cmd_card():
    s = load()
    free = N_POSITIONS - len(s["open"])
    if free <= 0:
        print(f"  all {N_POSITIONS} slots full: "
              f"{', '.join(p['symbol'] for p in s['open'])} — exit one first")
        return
    now = datetime.now()
    if not (now.weekday() < 5 and (9, 15) <= (now.hour, now.minute) < (14, 0)):
        print("  [SESSION-GUARD] cards only 09:15-14:00 on trading days")
        return
    held = {p["symbol"] for p in s["open"]}
    made = 0
    for _ in range(free):
        c, why = pick(relaxed="--relaxed" in sys.argv, exclude=held)
        if not c:
            print(f"  no further card: {why}")
            break
        px = float(c["price"])
        # size to PER_POSITION, not the whole book — two slots share the exposure
        qty = int(PER_POSITION / px)
        if qty < MIN_QTY:
            print(f"  {c['symbol']} @ {px:.2f} gives only {qty} sh "
                  f"(<{MIN_QTY}) — quantisation too coarse, skipping")
            held.add(c["symbol"])
            continue
        sl = round(px * (1 - SL_PCT / 100), 2)
        tgt = round(px * (1 + TGT_PCT / 100), 2)
        card = {"symbol": c["symbol"], "ref_price": px, "qty": qty,
                "exposure": round(px * qty, 2),
                "sl": sl, "target": tgt, "time_stop": TIME_STOP,
                "carded_at": now.strftime("%Y-%m-%d %H:%M:%S"),
                "score": c.get("score"), "spread_bps": c.get("spread_bps"),
                "fills_at_touch": c.get("fills_at_touch"),
                "relaxed_pick": c.get("relaxed", False),
                "paper": ("--paper" in sys.argv) or LANE_MODE != "real",
                "status": "CARDED"}
        s["open"].append(card)
        held.add(c["symbol"])
        made += 1
        save(s)
        tg(f"*Rs{CAPITAL:,.0f} {'PAPER' if card['paper'] else 'REAL'} — trade card "
           f"{len(s['open'])}/{N_POSITIONS}*\n"
           f"BUY {c['symbol']} x{qty} (MIS) = Rs{px*qty:,.0f} exposure\n"
           f"ref {px:.2f} | SL {sl} | target {tgt}\n"
           f"spread {c.get('spread_bps')}bps | touch fills all: "
           f"{'yes' if c.get('fills_at_touch') else 'no'}\n"
           f"{'(RELAXED: no BUY signal — mechanics test only)' if c.get('relaxed') else ''}\n"
           f"time-stop {TIME_STOP} — square off, never carry\n"
           f"after fill: real1k.py --filled <price> --symbol {c['symbol']}")
        print(f"  CARD {len(s['open'])}/{N_POSITIONS}: BUY {c['symbol']} x{qty} "
              f"@ ~{px:.2f} = Rs{px*qty:,.0f}  SL {sl}  TGT {tgt}")
    if made:
        print(f"  sent to Telegram. Log fills with --filled <price> --symbol <SYM>.")


def cmd_filled(price, symbol=None):
    s = load()
    o, err = find_pos(s, "CARDED", symbol)
    if err:
        print(f"  {err}"); return
    o["entry_price"] = price
    o["entry_time"] = datetime.now().strftime("%H:%M:%S")
    o["slippage_vs_ref_pct"] = round((price / o["ref_price"] - 1) * 100, 4)
    o["status"] = "OPEN"
    save(s)
    print(f"  FILLED {o['symbol']} x{o['qty']} @ {price} "
          f"(slippage vs card: {o['slippage_vs_ref_pct']:+.3f}%)")


def cmd_exited(price, symbol=None):
    s = load()
    o, err = find_pos(s, "OPEN", symbol)
    if err:
        print(f"  {err}"); return
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
    s["open"] = [p for p in s["open"] if p is not o]
    save(s)
    print(f"  CLOSED {o['symbol']}: Rs{pnl:+.2f} ({pct:+.2f}%) — ledger + dashboard updated")
    tg(f"*Rs{CAPITAL:,.0f} PILOT closed*: {o['symbol']} Rs{pnl:+.2f} ({pct:+.2f}%)")


def cmd_status():
    from prototype.lane_config import summary
    s = load()
    print("  " + summary())
    if s["open"]:
        for p in s["open"]:
            print(f"  [{p.get('status')}] {p['symbol']:<12} x{p['qty']:<5} "
                  f"ref {p['ref_price']:<9} SL {p['sl']:<9} TGT {p['target']}"
                  + (f"  entry {p['entry_price']}" if p.get("entry_price") else ""))
    else:
        print(f"  no open positions (0/{N_POSITIONS} slots used)")
    hist = [h for h in s.get("history", []) if "pnl" in h]
    tot = sum(h["pnl"] for h in hist)
    real = [h for h in hist if not h.get("paper", True)]
    print(f"  closed: {len(hist)} ({len(real)} real) | cumulative P&L: Rs{tot:+.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", action="store_true")
    ap.add_argument("--filled", type=float)
    ap.add_argument("--exited", type=float)
    ap.add_argument("--skip", type=str)
    ap.add_argument("--relaxed", action="store_true",
                    help="no BUY signal available: card the top-scored in-band name "
                         "as an explicit mechanics test (marked relaxed in the ledger)")
    ap.add_argument("--paper", action="store_true",
                    help="rehearsal mode: identical flow, ledger marked paper")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--symbol", type=str,
                    help="which position a --filled/--exited refers to "
                         "(required when more than one is open)")
    a = ap.parse_args()
    if a.card: cmd_card()
    elif a.filled: cmd_filled(a.filled, a.symbol)
    elif a.exited: cmd_exited(a.exited, a.symbol)
    elif a.skip:
        s = load(); s["open"] = []
        s.setdefault("history", []).append({"skipped": a.skip,
            "date": datetime.now().strftime("%Y-%m-%d")})
        save(s); print(f"  skipped: {a.skip}")
    else: cmd_status()


if __name__ == "__main__":
    main()
