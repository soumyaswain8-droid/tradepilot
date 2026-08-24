#!/usr/bin/env python3
"""
opt1k — the Rs1,000 OPTIONS-BUYING lane. One weekly NIFTY option, manual, tracked.

BORN 2026-08-23 (Soumya, reaffirmed after the odds were stated): the Rs3-4k-in-days
ambition is mechanically an options-buying target, so it gets its own lane — built
with the same discipline as everything else, not dressed up as something it isn't.

THE RISK, ON THE RECORD (stated once, then we work)
  Buying OTM weeklies: modal outcome is -100% of premium. We have measured ZERO
  directional edge intraday. This lane's own envelope is Rs1,000 and it never
  borrows from the equity pilot. PAPER for the first 2 weeks (>=8 cards) — the same
  pre-registered gate every other lane passed or died at: paper net > 0 after real
  fees, else the lane closes before a rupee of premium is spent.

FEES ARE DIFFERENT HERE AND THEY BITE
  Zerodha options: flat Rs20 brokerage per executed order -> Rs40+taxes round trip
  ~ Rs47. On a Rs700 premium ticket that is ~6-7% — the 2x target has to clear it.

MECHANICS
  Direction  fleet breadth at card time: BUY signals >=60% of scored -> CE,
             <=40% -> PE, else NO TRADE (no-signal days are free).
  Contract   nearest weekly NIFTY expiry (READ from the NFO instrument dump, never
             hardcoded — expiry-day conventions have changed before), the OTM strike
             whose premium fits one lot inside Rs1,000.
  Exits      SL -50% of premium | target +100% | time-stop 14:45 SAME DAY — no
             overnight theta on weeklies, no expiry-day carry.

USAGE
  python3 scripts/opt1k.py --card            # paper by default until the gate
  python3 scripts/opt1k.py --filled 9.85
  python3 scripts/opt1k.py --exited 14.20
  python3 scripts/opt1k.py --status
"""
from __future__ import annotations

import argparse, json, sys, warnings
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v4 import kite_data as kd

ENGINE = "opt1k"
DIR = ROOT / "docs" / "paper-trades" / ENGINE
from prototype.lane_config import OPT_BUDGET, OPT_RT_FEES, LANE_MODE
BUDGET = OPT_BUDGET
SL_PCT, TGT_PCT = 50.0, 100.0      # of premium
TIME_STOP = "14:45"
RT_FEES = OPT_RT_FEES               # brokerage + taxes, flat-ish
GATE_MIN_CARDS = 8                  # paper gate before any real premium
MIN_OI = 500_000                    # an affordable strike nobody trades can't be exited

# EXPIRY-DAY RULES. On expiry the entire extrinsic value of an OTM option decays to
# zero by 15:30 with certainty — theta is not a drag that day, it is the dominant
# term, and it accelerates through the afternoon. Two consequences:
#   - new entries stop early: after this, we are buying a melting ice cube
#   - the square-off is earlier, because the final half hour is where OTM premium
#     collapses fastest and the bid can vanish entirely
# Budget forces us ONTO expiry day (it is the only expiry where Rs3,000 reaches a
# near-ATM strike), so these guards are what make that affordable rather than reckless.
EXPIRY_DAY_NO_ENTRY_AFTER = "13:00"
EXPIRY_DAY_SQUARE_OFF = "15:00"

def load():
    f = DIR / "pilot_state.json"
    if f.exists():
        return json.loads(f.read_text())
    return {"open": None, "history": []}

def save(s):
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "pilot_state.json").write_text(json.dumps(s, indent=2))

def day_file():
    f = DIR / f"{datetime.now():%Y-%m-%d}.json"
    if f.exists():
        return json.loads(f.read_text()), f
    return {"date": f.stem, "engine": ENGINE, "total_capital": BUDGET,
            "pools": {"OPTIONS": {"positions": [], "closed": [], "pnl": 0.0}},
            "summary": {"total_pnl": 0.0, "trades": 0, "wins": 0, "losses": 0}}, f

def tg(msg):
    try:
        from prototype.v5.telegram_bot import send_alert
        send_alert(msg)
    except Exception as e:
        print(f"  (telegram failed: {e})")

def breadth():
    """Fleet direction: fraction of scored names on BUY."""
    import requests
    try:
        rows = requests.get("http://127.0.0.1:5050/api/scores", timeout=10).json()
    except Exception:
        return None, 0, 0
    if not rows:
        return None, 0, 0
    buys = sum(1 for r in rows if (r.get("signal") or "").upper() == "BUY")
    frac = buys / len(rows)
    side = "CE" if frac >= 0.60 else "PE" if frac <= 0.40 else None
    return side, frac, len(rows)

def pick_contract(side):
    """Nearest weekly NIFTY expiry; the CLOSEST-TO-SPOT strike whose lot fits budget.

    Closest-to-spot matters more than cheap. A near-ATM option carries ~0.5 delta, so
    it responds to the index move we actually forecast; a far-OTM at 0.1 delta needs a
    move several times larger just to break even, which is how a budget lane turns
    into a lottery ticket. Measured 2026-08-24 at Rs3,000: the nearest affordable
    strike sat 31 points from spot on the current expiry, but 330+ points out on the
    following one — the budget, not the view, decides moneyness.

    Also screens OI: an affordable strike nobody trades cannot be exited.
    """
    k = kd.client()
    nfo = k.instruments("NFO")
    opts = [i for i in nfo if i.get("name") == "NIFTY"
            and i.get("instrument_type") == side]
    if not opts:
        return None
    expiry = min(i["expiry"] for i in opts if i.get("expiry"))
    week = [i for i in opts if i["expiry"] == expiry]
    try:
        spot = float(k.quote(["NSE:NIFTY 50"])["NSE:NIFTY 50"]["last_price"])
    except Exception:
        return None
    week.sort(key=lambda i: i["strike"])
    otm = [i for i in week
           if (i["strike"] > spot if side == "CE" else i["strike"] < spot)]
    otm.sort(key=lambda i: abs(i["strike"] - spot))     # nearest the money first
    scan = otm[:14]
    if not scan:
        return None
    try:                                    # one batched call, not 14 round trips
        q = k.quote([f"NFO:{i['tradingsymbol']}" for i in scan])
    except Exception:
        return None
    for inst in scan:
        d = q.get(f"NFO:{inst['tradingsymbol']}") or {}
        px = float(d.get("last_price") or 0)
        oi = float(d.get("oi") or 0)
        lot = int(inst.get("lot_size") or 75)
        if px <= 0 or px * lot > BUDGET:
            continue
        if oi < MIN_OI:                     # nobody to sell it back to
            continue
        return {"tradingsymbol": inst["tradingsymbol"], "strike": inst["strike"],
                "expiry": str(inst["expiry"]), "lot": lot, "premium": px,
                "spot": spot, "cost": round(px * lot, 2), "oi": int(oi),
                "otm_points": round(abs(inst["strike"] - spot), 1),
                "is_expiry_day": expiry == datetime.now().date()}
    return None

def cmd_card(force_real=False):
    s = load()
    if s["open"]:
        print(f"  already open: {s['open']['tradingsymbol']}"); return
    now = datetime.now()
    if not (now.weekday() < 5 and (9, 20) <= (now.hour, now.minute) < (14, 0)):
        print("  [SESSION-GUARD] cards only 09:20-14:00 on trading days"); return
    paper_done = sum(1 for h in s["history"] if h.get("paper") and "pnl" in h)
    is_paper = not force_real or paper_done < GATE_MIN_CARDS
    if force_real and paper_done < GATE_MIN_CARDS:
        print(f"  GATE: only {paper_done}/{GATE_MIN_CARDS} paper cards closed — "
              f"real premium stays locked. Running paper.")
    side, frac, n = breadth()
    if side is None:
        print(f"  NO TRADE: breadth {frac:.0%} of {n} is inside the 40-60% dead zone "
              f"— no-signal days are free"); return
    c = pick_contract(side)
    if not c:
        print(f"  no affordable {side} with OI >= {MIN_OI:,} in budget Rs{BUDGET:,.0f}")
        return
    # expiry-day guards — see the constants block for why theta makes these binding
    stop_at = TIME_STOP
    if c.get("is_expiry_day"):
        if now.strftime("%H:%M") >= EXPIRY_DAY_NO_ENTRY_AFTER:
            print(f"  [EXPIRY-DAY] no new entries after "
                  f"{EXPIRY_DAY_NO_ENTRY_AFTER} — all remaining premium is "
                  f"extrinsic and decays to zero by close"); return
        stop_at = EXPIRY_DAY_SQUARE_OFF
    sl = round(c["premium"] * (1 - SL_PCT / 100), 2)
    tgt = round(c["premium"] * (1 + TGT_PCT / 100), 2)
    # the honest breakeven: the target must clear fees, not just the premium
    be = round(c["premium"] + RT_FEES / c["lot"], 2)
    card = {**c, "side": side, "breadth": round(frac, 3),
            "sl": sl, "target": tgt, "time_stop": stop_at, "breakeven": be,
            "paper": is_paper, "status": "CARDED",
            "carded_at": now.strftime("%Y-%m-%d %H:%M:%S")}
    s["open"] = card
    save(s)
    mode = "PAPER" if is_paper else "REAL"
    exp_tag = "  *EXPIRY DAY*" if c.get("is_expiry_day") else ""
    msg = (f"*Rs{BUDGET:,.0f} OPTIONS {mode} — card*{exp_tag}\n"
           f"BUY {c['tradingsymbol']} x{c['lot']}\n"
           f"premium ~{c['premium']:.2f} = Rs{c['cost']:,.0f} "
           f"({c['otm_points']:.0f} pts OTM, spot {c['spot']:,.0f}, "
           f"breadth {frac:.0%}, OI {c['oi']:,})\n"
           f"SL {sl} (-50%) | target {tgt} (+100%) | square-off {stop_at}\n"
           f"breakeven {be} — fees Rs{RT_FEES:.0f} = "
           f"{RT_FEES/c['cost']*100:.1f}% of the position")
    tg(msg)
    print(f"  {mode} CARD{exp_tag}: BUY {c['tradingsymbol']} x{c['lot']} "
          f"@ ~{c['premium']:.2f} (Rs{c['cost']:,.0f}, {c['otm_points']:.0f}pts OTM)")
    print(f"    SL {sl}  TGT {tgt}  breakeven {be}  square-off {stop_at}")

def cmd_filled(price):
    s = load(); o = s.get("open")
    if not o or o["status"] != "CARDED":
        print("  nothing carded"); return
    o["entry_premium"] = price
    o["entry_time"] = datetime.now().strftime("%H:%M:%S")
    o["status"] = "OPEN"
    save(s)
    print(f"  FILLED {o['tradingsymbol']} @ {price} "
          f"(card said {o['premium']:.2f}, slip {(price/o['premium']-1)*100:+.2f}%)")

def cmd_exited(price):
    s = load(); o = s.get("open")
    if not o or o["status"] != "OPEN":
        print("  nothing open"); return
    pnl = (price - o["entry_premium"]) * o["lot"] - (0 if o.get("paper") else RT_FEES)
    pct = (price / o["entry_premium"] - 1) * 100
    j, f = day_file()
    j["pools"]["OPTIONS"]["closed"].append({
        "symbol": o["tradingsymbol"], "entry_price": o["entry_premium"],
        "qty": o["lot"], "cost": round(o["entry_premium"] * o["lot"], 2),
        "entry_time": o["entry_time"], "entry_date": f.stem,
        "exit_price": price, "exit_time": datetime.now().strftime("%H:%M:%S"),
        "sl_price": o["sl"], "target_price": o["target"],
        "pnl": round(pnl, 2), "pnl_pct": round(pct, 2),
        "reason": "MANUAL", "position_type": "LONG", "pool": "OPTIONS",
        "real_money": not o.get("paper", True)})
    j["pools"]["OPTIONS"]["pnl"] += pnl
    j["summary"]["total_pnl"] += pnl
    j["summary"]["trades"] += 1
    j["summary"]["wins" if pnl > 0 else "losses"] += 1
    f.write_text(json.dumps(j, indent=2))
    s["history"].append({**o, "exit_premium": price, "pnl": round(pnl, 2)})
    s["open"] = None
    save(s)
    mode = "PAPER" if o.get("paper") else "REAL"
    print(f"  CLOSED [{mode}] {o['tradingsymbol']}: Rs{pnl:+.2f} ({pct:+.1f}% on premium)")
    tg(f"*opt1k {mode} closed*: {o['tradingsymbol']} Rs{pnl:+.2f} ({pct:+.1f}%)")

def cmd_status():
    s = load()
    if s["open"]:
        print(json.dumps(s["open"], indent=2))
    hist = [h for h in s.get("history", []) if "pnl" in h]
    paper = [h for h in hist if h.get("paper")]
    real = [h for h in hist if not h.get("paper")]
    print(f"  paper cards closed: {len(paper)}/{GATE_MIN_CARDS} toward the gate "
          f"(paper P&L Rs{sum(h['pnl'] for h in paper):+,.0f})")
    print(f"  real trades: {len(real)} (real P&L Rs{sum(h['pnl'] for h in real):+,.0f})")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--card", action="store_true")
    ap.add_argument("--real", action="store_true", help="request real mode (gate-checked)")
    ap.add_argument("--filled", type=float)
    ap.add_argument("--exited", type=float)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.card: cmd_card(force_real=a.real)
    elif a.filled: cmd_filled(a.filled)
    elif a.exited: cmd_exited(a.exited)
    else: cmd_status()

if __name__ == "__main__":
    main()
