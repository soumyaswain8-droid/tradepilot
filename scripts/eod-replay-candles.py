"""Left-on-the-table for 2026-09-04: per closed trade, what happened AFTER we exited."""
import json, sys, time
from pathlib import Path
ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot"); sys.path.insert(0, str(ROOT))
from prototype.v4 import kite_data as kd
DATE = sys.argv[2] if len(sys.argv) > 2 else "2026-09-04"; EOD = "15:15:00"
out = {"date": DATE, "engines": {}, "candles": {}}
cache = {}
def candles(sym):
    if sym in cache: return cache[sym]
    try:
        df = kd.get_candles(sym, interval="5minute", days=1)
        rows = [] if df is None else [dict(date=str(i), open=r.Open, high=r.High, low=r.Low, close=r.Close)
                                      for i, r in df.iterrows() if str(i)[:10] == DATE]
    except Exception as e:
        print("  candle fail", sym, type(e).__name__, str(e)[:80]); rows = []
    cache[sym] = rows; time.sleep(0.34); return rows
def t(s): return str(s)[11:19] if len(str(s)) > 8 else str(s)
for eng in (sys.argv[3].split(",") if len(sys.argv) > 3 else ("v5", "v5_wide")):
    d = json.load(open(ROOT/"docs/paper-trades"/eng/f"{DATE}.json"))
    trades = []
    for pool, v in d["pools"].items():
        for tr in v.get("closed", []):
            sym = tr["symbol"]; short = tr.get("position_type") == "SHORT"; q = tr["qty"]
            rows = candles(sym)
            after = [r for r in rows if t(r["date"]) >= tr["exit_time"]]
            since_entry = rows if (tr.get("entry_date") and tr["entry_date"] != DATE) else [r for r in rows if t(r["date"]) >= tr["entry_time"]]
            rec = dict(engine=eng, symbol=sym, dir="SHORT" if short else "LONG", qty=q, pool=pool,
                       entry=tr["entry_price"], exit=tr["exit_price"], entry_time=tr["entry_time"],
                       exit_time=tr["exit_time"], pnl=round(tr["pnl"], 1), reason=tr["reason"], candles=len(rows),
                       carried=bool(tr.get("entry_date") and tr["entry_date"] != DATE))
            if after:
                close_eod = after[-1]["close"]
                best_after = min(r["low"] for r in after) if short else max(r["high"] for r in after)
                worst_after = max(r["high"] for r in after) if short else min(r["low"] for r in after)
                sign = -1 if short else 1
                rec["hold_to_eod_pnl"] = round(sign * (close_eod - tr["entry_price"]) * q, 1)
                rec["hold_delta"] = round(rec["hold_to_eod_pnl"] - tr["pnl"], 1)
                rec["best_after_exit"] = round(sign * (best_after - tr["exit_price"]) * q, 1)
                rec["worst_after_exit"] = round(sign * (worst_after - tr["exit_price"]) * q, 1)
                rec["hit_target_later"] = bool(tr.get("target") and ((best_after <= tr["target"]) if short else (best_after >= tr["target"])))
            if since_entry:
                sign = -1 if short else 1
                mfe = min(r["low"] for r in since_entry) if short else max(r["high"] for r in since_entry)
                rec["mfe_pnl"] = round(sign * (mfe - tr["entry_price"]) * q, 1)
            trades.append(rec)
    have = [x for x in trades if "hold_delta" in x]
    out["engines"][eng] = dict(
        n=len(trades), n_with_candles=len(have),
        actual_pnl=round(sum(x["pnl"] for x in trades), 1),
        hold_to_eod_pnl=round(sum(x.get("hold_to_eod_pnl", x["pnl"]) for x in trades), 1),
        hold_delta=round(sum(x.get("hold_delta", 0) for x in trades), 1),
        best_case_after_exit=round(sum(max(0, x.get("best_after_exit", 0)) for x in trades), 1),
        mfe_total=round(sum(max(0, x.get("mfe_pnl", 0)) for x in trades), 1),
        stoploss_then_reversed=[x for x in trades if x["reason"] == "STOPLOSS" and x.get("hold_delta", 0) > 0],
        trades=trades)
    e = out["engines"][eng]
    print(eng, "n", e["n"], "candles", e["n_with_candles"], "actual", e["actual_pnl"], "hold-to-EOD", e["hold_to_eod_pnl"],
          "delta", e["hold_delta"], "best-after-exit", e["best_case_after_exit"], "MFE", e["mfe_total"],
          "SL-then-reversed", len(e["stoploss_then_reversed"]), round(sum(x["hold_delta"] for x in e["stoploss_then_reversed"]), 1))
out["candles"] = {k: [dict(t=t(r["date"]), o=r["open"], h=r["high"], l=r["low"], c=r["close"]) for r in v] for k, v in cache.items()}
json.dump(out, open(Path(sys.argv[1]) if len(sys.argv) > 1 else "left_on_table.json", "w"), default=str)
print("health", kd.health())
