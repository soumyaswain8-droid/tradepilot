#!/usr/bin/env python3
"""
daygain-baseline — DAYGAIN as a computed row, not an engine (Soumya, 2026-09-08).
The lane died on its Phase 0 gates; the baseline survives as arithmetic: what would
"top-10 gainers at 09:35, hold to 15:15" have made today, next to each engine's net.

  python3 scripts/daygain-baseline.py snapshot   # run AT 09:35 — one movers() call, frozen filters, no orders
  python3 scripts/daygain-baseline.py eod [date] # after close — price the basket from Kite 5-min candles

Rule + filters are imported from the retired engine so nothing is re-typed (and nothing is tuned).
"""
import sys, json, importlib.util, time
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("daygain", ROOT / "scripts/retired/v5_daygain-paper-trade.py")
dg = importlib.util.module_from_spec(spec); dg.DRY = True; spec.loader.exec_module(dg)
OUT = ROOT / "docs/research/daygain/baseline"; OUT.mkdir(parents=True, exist_ok=True)

def snapshot():
    date = datetime.now().strftime("%Y-%m-%d")
    picks, dlog = dg.decide()
    basket = []
    for p in picks:
        fill = round(p["price"] * (1 + dg.SLIP), 2); qty = int(dg.SLOT // fill)
        basket.append({"symbol": p["symbol"], "chg_0935": round(p["change"], 2), "ref": p["price"], "fill": fill, "qty": qty, "adv20": p.get("adv20")})
    doc = {"date": date, "at": dlog.get("at"), "decision": dlog, "basket": basket, "capital": dg.CAPITAL, "rule": "top-10 gainers 09:35, fill 09:36+0.10%, -3% stop, 15:15 close (frozen)"}
    (OUT / f"{date}.json").write_text(json.dumps(doc, indent=1, default=str))
    print(f"snapshot {date}: {len(basket)} names -> {OUT / (date + '.json')}"); return 0

def eod(date: str):
    from prototype.v4 import kite_data as kd
    f = OUT / f"{date}.json"
    if not f.exists(): print(f"no snapshot for {date}"); return 1
    doc = json.loads(f.read_text()); rows = []
    for b in doc["basket"]:
        df = kd.get_candles(b["symbol"], interval="5minute", days=1); time.sleep(0.34)
        if df is None: rows.append({**b, "note": "no candles"}); continue
        day = df[[str(i)[:10] == date for i in df.index]]
        after = day[[str(i)[11:16] >= "09:35" for i in day.index]]
        if after.empty: rows.append({**b, "note": "no bars after 09:35"}); continue
        stop = round(b["fill"] * (1 + dg.STOP_PCT / 100), 2); exit_px, reason = None, "TIME_EXIT"
        for i, r in after.iterrows():
            if float(r["Low"]) <= stop: exit_px, reason = stop, "STOPLOSS"; break
        if exit_px is None:
            upto = after[[str(i)[11:16] <= "15:15" for i in after.index]]
            exit_px = float((upto if not upto.empty else after)["Close"].iloc[-1])
        gross = round((exit_px - b["fill"]) * b["qty"], 2); cost = dg.real_cost(b["qty"], b["fill"], exit_px, "LONG")["total"]
        rows.append({**b, "exit": round(exit_px, 2), "reason": reason, "gross": gross, "cost": cost, "net": round(gross - cost, 2)})
    priced = [r for r in rows if "net" in r]
    doc["eod"] = {"priced": len(priced), "gross": round(sum(r["gross"] for r in priced), 2), "cost": round(sum(r["cost"] for r in priced), 2),
                  "net": round(sum(r["net"] for r in priced), 2), "stops": sum(1 for r in priced if r["reason"] == "STOPLOSS"), "rows": rows}
    f.write_text(json.dumps(doc, indent=1, default=str))
    print(f"DAYGAIN baseline {date}: net Rs {doc['eod']['net']:+,.0f} ({doc['eod']['stops']} stops of {len(priced)})"); return 0

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "snapshot"
    sys.exit(snapshot() if cmd == "snapshot" else eod(sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y-%m-%d")))
