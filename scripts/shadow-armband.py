#!/usr/bin/env python3
"""
shadow-armband — arm-band shadow ledgers (pre-registered 2026-09-08, docs/research/shadows/).
Replays every closed trade of the given engines against Kite 5-min candles under alternate
trailing-arm bands. Same entry, same hard stop, same target; only the trailing rule differs.

  python3 scripts/shadow-armband.py <date> [engines=v5,v5_wide] [candles.json]

candles.json (optional) = a docs/watchdog/reports/<date>_eod/left-on-table.json with a "candles"
map; otherwise candles are fetched from Kite. Output: docs/research/shadows/armband/<date>.json + .md
"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
DATE = sys.argv[1]; ENGINES = (sys.argv[2] if len(sys.argv) > 2 else "v5,v5_wide").split(",")
CAND = json.load(open(sys.argv[3]))["candles"] if len(sys.argv) > 3 else {}
BANDS = {"live": (1.0, 0.5), "arm0.5": (0.5, 0.25), "arm0.3": (0.3, 0.25), "fixed": (None, None)}
CLOSE_AT = "15:15"; FLEET_BPS = 12.0
OUT = ROOT / "docs/research/shadows/armband"; OUT.mkdir(parents=True, exist_ok=True)

def candles(sym):
    if sym in CAND:
        if CAND[sym] and isinstance(CAND[sym][0].get("o"), str):
            CAND[sym] = [dict(t=b["t"], o=float(b["o"]), h=float(b["h"]), l=float(b["l"]), c=float(b["c"])) for b in CAND[sym]]
        return CAND[sym]
    from prototype.v4 import kite_data as kd
    try:
        df = kd.get_candles(sym, interval="5minute", days=1)
    except Exception:
        CAND[sym] = []; return []
    time.sleep(0.34)
    rows = [] if df is None else [dict(t=str(i)[11:19], o=float(r.Open), h=float(r.High), l=float(r.Low), c=float(r.Close)) for i, r in df.iterrows() if str(i)[:10] == DATE]
    CAND[sym] = rows; return rows

def cost(qty, e, x): return round(qty * (e + x) / 2 * FLEET_BPS / 1e4, 2)

def replay(t, arm, step):
    """Walk 5-min bars from entry under one band. Returns (exit_px, reason, exit_time) or None."""
    short = t["position_type"] == "SHORT"; entry = t["entry_price"]; sl = t.get("sl_price"); tg = t.get("target_price")
    bars = [b for b in candles(t["symbol"]) if b["t"] >= t["entry_time"]] if t.get("entry_date", DATE) == DATE else candles(t["symbol"])
    if not bars: return None
    sl0 = sl if sl else (entry * (1.02 if short else 0.98)); armed = False; best = entry
    for b in bars:
        hi, lo, c = b["h"], b["l"], b["c"]
        if short:
            if hi >= sl0: return (sl0, "STOPLOSS" if not armed else "TRAIL", b["t"])
            if tg and lo <= tg: return (tg, "TARGET", b["t"])
            best = min(best, lo); pnl_pct = (entry - c) / entry * 100
            if arm is not None and pnl_pct >= arm:
                if not armed: armed, sl0 = True, entry
                else: sl0 = min(sl0, round(best * (1 + step / 100), 2))
        else:
            if lo <= sl0: return (sl0, "STOPLOSS" if not armed else "TRAIL", b["t"])
            if tg and hi >= tg: return (tg, "TARGET", b["t"])
            best = max(best, hi); pnl_pct = (c - entry) / entry * 100
            if arm is not None and pnl_pct >= arm:
                if not armed: armed, sl0 = True, entry
                else: sl0 = max(sl0, round(best * (1 - step / 100), 2))
        if b["t"] >= CLOSE_AT: return (c, "TIME_EXIT", b["t"])
    return (bars[-1]["c"], "TIME_EXIT", bars[-1]["t"])

res = {"date": DATE, "bands": {k: {"arm": v[0], "step": v[1]} for k, v in BANDS.items()}, "engines": {}}
for e in ENGINES:
    d = json.load(open(ROOT / "docs/paper-trades" / e / f"{DATE}.json"))
    trades = [t for p in d["pools"].values() for t in p.get("closed", [])]
    tot = {k: {"gross": 0.0, "net": 0.0, "n": 0, "stops": 0, "targets": 0, "worst_trade": 0.0} for k in BANDS}
    live_actual = round(sum(t["pnl"] for t in trades), 2); live_net_actual = round(sum(t.get("pnl_net", t["pnl"]) for t in trades), 2)
    rows = []
    for t in trades:
        r = {"symbol": t["symbol"], "dir": t["position_type"], "qty": t["qty"], "entry": t["entry_price"], "actual_exit": t["exit_price"], "actual_reason": t["reason"], "actual_pnl": round(t["pnl"], 1)}
        for k, (arm, step) in BANDS.items():
            o = replay(t, arm, step)
            if o is None: r[k] = None; continue
            px, reason, when = o; sign = -1 if t["position_type"] == "SHORT" else 1
            g = round(sign * (px - t["entry_price"]) * t["qty"], 1); n = round(g - cost(t["qty"], t["entry_price"], px), 1)
            r[k] = {"exit": round(px, 2), "reason": reason, "at": when, "gross": g, "net": n}
            tot[k]["gross"] += g; tot[k]["net"] += n; tot[k]["n"] += 1; tot[k]["stops"] += reason in ("STOPLOSS", "TRAIL"); tot[k]["targets"] += reason == "TARGET"; tot[k]["worst_trade"] = min(tot[k]["worst_trade"], n)
        rows.append(r)
    for k in tot: tot[k] = {kk: (round(v, 1) if isinstance(v, float) else v) for kk, v in tot[k].items()}
    res["engines"][e] = {"live_actual_gross": live_actual, "live_actual_net": live_net_actual, "bands": tot, "trades": rows}
    print(f"{e}: actual net {live_net_actual:+,.0f} | " + " | ".join(f"{k} {tot[k]['net']:+,.0f} ({tot[k]['n']}t, {tot[k]['stops']} stops)" for k in BANDS))
(OUT / f"{DATE}.json").write_text(json.dumps(res, indent=1))
md = [f"# Arm-band shadow — {DATE}", "", "| Engine | Actual net | " + " | ".join(BANDS) + " |", "|---|---:|" + "---:|" * len(BANDS)]
for e, v in res["engines"].items():
    md.append(f"| {e} | {v['live_actual_net']:+,.0f} | " + " | ".join(f"{v['bands'][k]['net']:+,.0f} ({v['bands'][k]['stops']} st / {v['bands'][k]['targets']} tg)" for k in BANDS) + " |")
md += ["", "Replayed 5-min bars, 12 bps fleet cost model, same entries/stops/targets as live; only the trailing arm differs. 'live' band replayed is the sanity check against actual (bar granularity explains small gaps)."]
(OUT / f"{DATE}.md").write_text("\n".join(md)); print("->", OUT / f"{DATE}.md")
