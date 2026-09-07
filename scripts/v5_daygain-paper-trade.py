#!/usr/bin/env python3
"""
v5_daygain — DAYGAIN top-gainer concentration lane (paper). Pre-registered spec:
1cr-roadmap/design/2026-09-05-daygain-lane-spec.md. The rule is FROZEN; this file
implements it and nothing else. One decision per day at 09:35 IST.

  Universe  NSE cash (quant/universe_full.txt), price >= 50, 20-day ADV >= Rs 5 cr
  Signal    rank by %change vs prior close at 09:35
  Filters   skip chg > +15%; skip upper-circuit proxy (at day high and chg >= 9.5%);
            ASM/GSM: NO DATA SOURCE — skipped and logged
  Entry     top 10 LONG, Rs 1.125L each, fill = 09:36 price * 1.001
  Stop      -3.0% hard from fill, checked every 60s
  Exit      15:15 square-off; no trailing, no target, no re-entry
  Kill      Nifty < -1.0% at 09:35 -> no entries
  Costs     real intraday schedule (real_cost, copied from v5_god)

Env: ENGINE_NAME (default v5_daygain), DAYGAIN_DRY_RUN=1 (decide now with current
quotes, no waiting — smoke test only, writes to docs/paper-trades/<ENGINE>_dryrun/).
"""
from __future__ import annotations
import json, math, os, sys, time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NSE_DATA_SOURCE", "kite")
from prototype.v4 import kite_data as kd            # noqa: E402
from prototype import movers as mv                  # noqa: E402
from prototype.utils.signal_guards import atomic_write_json  # noqa: E402

DRY = os.environ.get("DAYGAIN_DRY_RUN") == "1"
ENGINE = os.environ.get("ENGINE_NAME", "v5_daygain") + ("_dryrun" if DRY else "")
TODAY = datetime.now().strftime("%Y-%m-%d")
TRADE_DIR = ROOT / "docs" / "paper-trades" / ENGINE
TRADE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = TRADE_DIR / f"{TODAY}.json"
ACTIVE_FILE = TRADE_DIR / "positions_active.json"

# ── frozen parameters (do not edit; see spec) ────────────────────────────────
CAPITAL = 1_125_000
SLOT = 112_500
N_POS = 10
DECIDE_AT = "09:35"
FILL_AT = "09:36"
SQUARE_OFF = "15:15"
SLIP = 0.001
STOP_PCT = -3.0
MAX_CHG = 15.0
CIRCUIT_CHG = 9.5
MIN_PRICE = 50.0
MIN_ADV = 5e7
NIFTY_KILL = -1.0
POLL_S = 60
ADV_DAYS = 20
CANDIDATES = 40


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def real_cost(qty: int, entry: float, exit_: float, side: str = "LONG") -> dict:
    """Copied verbatim from scripts/v5_god-paper-trade.py (Zerodha intraday ledger)."""
    buy_val = qty * (entry if side == "LONG" else exit_)
    sell_val = qty * (exit_ if side == "LONG" else entry)
    turnover = buy_val + sell_val
    brokerage = min(0.0003 * buy_val, 20.0) + min(0.0003 * sell_val, 20.0)
    stt = 0.00025 * sell_val
    exch = 0.0000297 * turnover
    sebi = 0.000001 * turnover
    stamp = 0.00003 * buy_val
    gst = 0.18 * (brokerage + exch + sebi)
    total = brokerage + stt + exch + sebi + stamp + gst
    return {"brokerage": round(brokerage, 2), "stt": round(stt, 2), "exchange": round(exch, 2),
            "sebi": round(sebi, 2), "stamp": round(stamp, 2), "gst": round(gst, 2),
            "total": round(total, 2),
            "pct_of_turnover": round(total / turnover * 100, 4) if turnover else 0.0}


def now_hm() -> str:
    return datetime.now().strftime("%H:%M")


def wait_until(hm: str) -> None:
    target = datetime.strptime(f"{TODAY} {hm}", "%Y-%m-%d %H:%M")
    while datetime.now() < target:
        time.sleep(min(30, max(1, (target - datetime.now()).total_seconds())))


def fresh_state() -> dict:
    return {"date": TODAY, "engine": ENGINE, "started_at": datetime.now().strftime("%H:%M:%S"),
            "total_capital": CAPITAL, "regime": "NA", "premarket": {},
            "risk_state": {"lane": "daygain", "spec": "2026-09-05-daygain-lane-spec.md", "asm_gsm_filter": "skipped-no-data"},
            "pools": {"INTRADAY": {"positions": [], "closed": [], "pnl": 0.0}},
            "summary": {"total_pnl": 0.0, "trades": 0, "wins": 0, "losses": 0, "longs": 0, "shorts": 0,
                        "scan_count": 0, "rescore_count": 0, "total_pnl_net": 0.0, "total_cost": 0.0},
            "decision": {}}


def save(state: dict) -> None:
    atomic_write_json(STATE_FILE, state)
    atomic_write_json(ACTIVE_FILE, {"saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                    "positions": {"INTRADAY": state["pools"]["INTRADAY"]["positions"]}})


def adv_20d(symbol: str) -> float | None:
    """20-day average daily turnover from Kite daily candles (close*volume)."""
    try:
        df = kd.get_candles(symbol, interval="day", days=ADV_DAYS + 12)
    except Exception as e:
        log(f"  adv {symbol}: {type(e).__name__}"); return None
    if df is None or len(df) < 5:
        return None
    df = df.tail(ADV_DAYS)
    return float((df["Close"] * df["Volume"]).mean())


def decide() -> tuple[list[dict], dict]:
    """The one decision. Returns (picks, decision_log)."""
    dlog = {"at": datetime.now().strftime("%H:%M:%S"), "asm_gsm": "skipped-no-data"}
    try:
        nifty = kd.get_index("NIFTY 50")
        dlog["nifty_chg"] = round(float(nifty.get("change_pct") or 0.0), 3)
    except Exception as e:
        dlog["nifty_chg"] = None; dlog["nifty_error"] = type(e).__name__
    if dlog["nifty_chg"] is not None and dlog["nifty_chg"] < NIFTY_KILL:
        dlog["killed"] = f"nifty {dlog['nifty_chg']}% < {NIFTY_KILL}%"
        log(f"INDEX KILL: {dlog['killed']} — no entries today"); return [], dlog

    snap = mv.movers(n=200, min_turnover=0.0)
    rows = snap.get("gainers", [])
    dlog.update({"universe": snap.get("universe"), "quoted": snap.get("quoted"), "gainers_seen": len(rows)})
    # Data-quality guards: a thin sweep or a flat tape means stale/broken quotes, not a signal.
    uni, quoted = snap.get("universe") or 0, snap.get("quoted") or 0
    if uni and quoted < 0.5 * uni:
        dlog["killed"] = f"quote coverage {quoted}/{uni} < 50% — data, not signal"
        log(f"DATA KILL: {dlog['killed']}"); return [], dlog
    if not DRY and rows and max(abs(r["change"]) for r in rows[:50]) < 0.05:
        dlog["killed"] = "top-50 gainers all within 0.05% — stale/pre-open quotes"
        log(f"DATA KILL: {dlog['killed']}"); return [], dlog
    cands, rejected = [], {"price": 0, "chg>15": 0, "circuit": 0, "adv": 0}
    for r in rows:
        if r["price"] < MIN_PRICE: rejected["price"] += 1; continue
        if r["change"] > MAX_CHG: rejected["chg>15"] += 1; continue
        if r.get("high") and r["price"] >= r["high"] and r["change"] >= CIRCUIT_CHG: rejected["circuit"] += 1; continue
        cands.append(r)
        if len(cands) >= CANDIDATES: break
    picks = []
    for r in cands:
        adv = adv_20d(r["symbol"]); time.sleep(0.34)
        r["adv20"] = adv
        if adv is None or adv < MIN_ADV: rejected["adv"] += 1; continue
        picks.append(r)
        if len(picks) >= N_POS: break
    dlog["rejected"] = rejected
    dlog["picks"] = [{k: r.get(k) for k in ("symbol", "price", "change", "turnover", "adv20")} for r in picks]
    log(f"decision: {len(picks)} picks from {len(rows)} gainers; rejected {rejected}")
    for r in picks: log(f"  {r['symbol']:<12} {r['price']:>9.2f} {r['change']:>+6.2f}%  adv20 {r['adv20']/1e7:.1f} cr")
    return picks, dlog


def fill(picks: list[dict]) -> list[dict]:
    if not DRY: wait_until(FILL_AT)
    q = kd.get_quotes([p["symbol"] for p in picks])
    positions = []
    for p in picks:
        px = (q.get(p["symbol"]) or {}).get("last_price") or p["price"]
        fill_px = round(px * (1 + SLIP), 2)
        qty = math.floor(SLOT / fill_px)
        if qty <= 0: continue
        positions.append({"symbol": p["symbol"], "entry_price": fill_px, "qty": qty, "position_type": "LONG",
                          "direction": "BUY", "pool": "INTRADAY", "entry_time": datetime.now().strftime("%H:%M:%S"),
                          "entry_date": TODAY, "sl_price": round(fill_px * (1 + STOP_PCT / 100), 2), "target_price": None,
                          "score": round(p["change"], 2), "reasons": [{"text": f"top-gainer rank at {DECIDE_AT}: {p['change']:+.2f}%", "type": "positive"}],
                          "ref_price_0935": p["price"], "trailing_activated": False})
        log(f"  FILL {p['symbol']:<12} x{qty:<5} @{fill_px:.2f} (ref {px:.2f} +0.10%) SL {positions[-1]['sl_price']:.2f}")
    return positions


def close(pos: dict, px: float, reason: str) -> dict:
    gross = round((px - pos["entry_price"]) * pos["qty"], 2)
    cost = real_cost(pos["qty"], pos["entry_price"], px, "LONG")["total"]
    t = dict(pos); t.update({"exit_price": px, "exit_time": datetime.now().strftime("%H:%M:%S"), "reason": reason,
                             "pnl": gross, "pnl_gross": gross, "cost": cost, "pnl_net": round(gross - cost, 2),
                             "pnl_pct": round((px / pos["entry_price"] - 1) * 100, 2)})
    log(f"  >> {'WIN' if gross >= 0 else 'LOSS'} {pos['symbol']} x{pos['qty']} @{px:.2f} ({reason}) P&L Rs {gross:+.0f} net {t['pnl_net']:+.0f}")
    return t


def summarise(state: dict) -> None:
    cl = state["pools"]["INTRADAY"]["closed"]
    s = state["summary"]
    s.update({"total_pnl": round(sum(t["pnl"] for t in cl), 2), "trades": len(cl),
              "wins": sum(1 for t in cl if t["pnl"] >= 0), "losses": sum(1 for t in cl if t["pnl"] < 0),
              "longs": len(cl), "total_cost": round(sum(t["cost"] for t in cl), 2),
              "total_pnl_net": round(sum(t["pnl_net"] for t in cl), 2)})
    state["pools"]["INTRADAY"]["pnl"] = s["total_pnl"]


def main() -> int:
    log(f"{ENGINE} start — DAYGAIN lane, capital Rs {CAPITAL:,} (dry-run={DRY})")
    if STATE_FILE.exists() and not DRY:
        log(f"state for {TODAY} already exists ({STATE_FILE.name}) — one decision per day; refusing to re-run"); return 0
    state = fresh_state(); save(state)
    if not DRY:
        log(f"waiting for {DECIDE_AT}"); wait_until(DECIDE_AT)
    picks, dlog = decide()
    state["decision"] = dlog; state["summary"]["scan_count"] = 1
    if not picks:
        save(state); log("no entries today — done"); return 0
    state["pools"]["INTRADAY"]["positions"] = fill(picks); save(state)
    if DRY:
        log("dry-run: skipping the monitoring loop"); return 0
    pool = state["pools"]["INTRADAY"]
    while pool["positions"]:
        time.sleep(POLL_S)
        sq = now_hm() >= SQUARE_OFF
        try:
            q = kd.get_quotes([p["symbol"] for p in pool["positions"]])
        except Exception as e:
            log(f"quotes failed: {type(e).__name__} — retry next poll"); continue
        keep = []
        for p in pool["positions"]:
            px = (q.get(p["symbol"]) or {}).get("last_price")
            if not px: keep.append(p); continue
            if sq: pool["closed"].append(close(p, px, "TIME_EXIT"))
            elif px <= p["sl_price"]: pool["closed"].append(close(p, p["sl_price"], "STOPLOSS"))
            else: keep.append(p)
        pool["positions"] = keep
        summarise(state); save(state)
        if sq and keep:
            log(f"{len(keep)} positions had no quote at square-off; retrying"); time.sleep(20)
    summarise(state); save(state)
    log(f"done — net Rs {state['summary']['total_pnl_net']:+,.0f} on {state['summary']['trades']} trades"); return 0


if __name__ == "__main__":
    sys.exit(main())
