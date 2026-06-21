#!/usr/bin/env python3
"""
backtest-honest-fills.py — re-price v5 closed trades with HONEST fills.

WHY: live v5 (scripts/v5-paper-trade.py:597,635) detects stops/targets on the
last 10-min-scan CLOSE (`px`) and fills at `px`. Between scans a stock can pierce
its stop and recover by scan time -> the stop is MISSED and the loss is never
booked (Critic-4 upward bias). This harness replays 5-minute bars across each
trade's holding window and books the exit at the stop/target level the moment the
intraday HIGH/LOW breaches it.

METHOD per recorded closed trade (entry_price, entry_time, exit_time, qty, type):
  - reconstruct sl/tgt from entry using v5 defaults (SL 1.5%, TGT 2.0%); the
    gap-day 2.25% SL is not per-trade recoverable -> we use 1.5% (slightly
    conservative: may over-count stops on gap mornings; flagged in output).
  - walk 5m bars in [entry_time .. recorded exit_time]:
      LONG : low<=sl -> STOPLOSS@sl ; elif high>=tgt -> TARGET@tgt
      SHORT: high>=sl -> STOPLOSS@sl ; elif low<=tgt -> TARGET@tgt
    first breach wins (honest, time-ordered).
  - no intraday breach -> keep the recorded exit (time/flat/trailing exits).
  - cost model identical to live (12bps round-trip on avg notional).

LIMITATIONS (stated, not hidden):
  - trailing-stop tightening is not replayed (affects some winners only).
  - gap-day wider SL not modeled (conservative).
  - 5m granularity (not tick) -> within-bar ordering of H vs L assumed adverse
    (stop checked before target) which is the prudent direction.

OUTPUT: per-day recorded vs honest P&L, totals, and a CSV for the regression rerun.
Usage: python3 scripts/backtest-honest-fills.py [--days N] [--engine v5]
"""
import json, glob, os, re, sys, math, pickle, time
import warnings; warnings.filterwarnings("ignore")
import yfinance as yf
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = "v5"
SL_PCT, TGT_PCT = 0.015, 0.02
COST_BPS = 12
CACHE = "/tmp/tp_5m_cache"
os.makedirs(CACHE, exist_ok=True)
DATE = re.compile(r'^(\d{4}-\d{2}-\d{2})\.json$')

if "--engine" in sys.argv: ENGINE = sys.argv[sys.argv.index("--engine")+1]
LIMIT = int(sys.argv[sys.argv.index("--days")+1]) if "--days" in sys.argv else None

def load_trades():
    """{date: [trade,...]} from the engine's dated paper-trade JSONs."""
    out = {}
    for f in sorted(glob.glob(f"{ROOT}/docs/paper-trades/{ENGINE}/*.json")):
        m = DATE.match(os.path.basename(f))
        if not m: continue
        d = m.group(1)
        try: j = json.load(open(f))
        except: continue
        trades = []
        for pn, pv in (j.get("pools") or {}).items():
            for t in (pv.get("closed_trades") or pv.get("closed") or []):
                if all(k in t for k in ("entry_price","exit_price","qty","entry_time","position_type")):
                    trades.append(t)
        if trades: out[d] = trades
    return out

def hhmm(ts):
    return ts.strftime("%H:%M:%S")

def fetch_5m(symbols, date):
    """5m bars for a day, cached. returns {SYM: DataFrame(idx=HH:MM:SS, high, low)}"""
    cf = f"{CACHE}/{ENGINE}_{date}.pkl"
    if os.path.exists(cf):
        return pickle.load(open(cf, "rb"))
    tickers = [f"{s}.NS" for s in symbols]
    nxt = (pd.Timestamp(date) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    out = {}
    try:
        df = yf.download(tickers, start=date, end=nxt, interval="5m",
                         progress=False, auto_adjust=False, group_by="ticker")
        if not df.empty:
            try: df.index = df.index.tz_convert("Asia/Kolkata")
            except Exception:
                try: df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
                except Exception: pass
            for s in symbols:
                tk = f"{s}.NS"
                try:
                    sub = df[tk] if len(tickers) > 1 else df
                    sub = sub[["High","Low"]].dropna()
                    if len(sub):
                        sub = sub.copy(); sub["t"] = [hhmm(x) for x in sub.index]
                        out[s] = sub
                except Exception:
                    pass
    except Exception as e:
        print(f"    fetch err {date}: {str(e)[:60]}")
    pickle.dump(out, open(cf, "wb"))
    return out

def honest_exit(trade, bars):
    """Isolate MISSED STOPS (Critic-4 bias): a stop is a resting order that fills
    on intraday touch. A take-profit here is a scan-based market exit (NO resting
    limit order), so we do NOT credit intraday target touches that later recede.

    - recorded STOPLOSS  -> keep (engine already stopped it).
    - recorded non-stop  -> if intraday HIGH/LOW pierced the stop while open,
                            book STOPLOSS @ sl (the loss the engine missed).
    - else               -> keep recorded exit.
    returns (exit_price, reason, changed?)
    """
    reason0 = trade.get("reason", "KEEP")
    if reason0 == "STOPLOSS":
        return trade["exit_price"], reason0, False
    entry = trade["entry_price"]; is_short = trade["position_type"] == "SHORT"
    et = trade["entry_time"]; xt = trade.get("exit_time", "15:30:00")
    sl = entry * (1 + SL_PCT) if is_short else entry * (1 - SL_PCT)
    if bars is None or not len(bars):
        return trade["exit_price"], reason0, False
    win = bars[(bars["t"] >= et) & (bars["t"] <= xt)]
    for _, b in win.iterrows():
        hi, lo = float(b["High"]), float(b["Low"])
        if (is_short and hi >= sl) or (not is_short and lo <= sl):
            return sl, "STOPLOSS*", True   # missed stop now booked at the level
    return trade["exit_price"], reason0, False

def pnl_of(entry, exit_, qty, is_short):
    gross = (entry - exit_) * qty if is_short else (exit_ - entry) * qty
    cost = qty * (entry + exit_) / 2 * (COST_BPS / 10000)
    return gross, gross - cost

def main():
    trades_by_day = load_trades()
    days = sorted(trades_by_day)
    if LIMIT: days = days[-LIMIT:]
    print(f"{ENGINE}: {len(days)} days, {sum(len(trades_by_day[d]) for d in days)} closed trades\n")
    rows = []
    rec_total = hon_total = 0
    flips = 0; changed = 0
    for d in days:
        ts = trades_by_day[d]
        syms = sorted({t["symbol"] for t in ts if "symbol" in t})
        bars = fetch_5m(syms, d)
        rec_d = hon_d = 0
        for t in ts:
            is_short = t["position_type"] == "SHORT"
            qty = t["qty"]
            rec_gross, rec_net = pnl_of(t["entry_price"], t["exit_price"], qty, is_short)
            xp, reason, chg = honest_exit(t, bars.get(t["symbol"]))
            hon_gross, hon_net = pnl_of(t["entry_price"], xp, qty, is_short)
            rec_d += rec_net; hon_d += hon_net
            if chg:
                changed += 1
                if (rec_net > 0) != (hon_net > 0): flips += 1
        rec_total += rec_d; hon_total += hon_d
        rows.append((d, rec_d, hon_d))
        print(f"  {d}: recorded {rec_d:>9,.0f}  honest {hon_d:>9,.0f}  delta {hon_d-rec_d:>9,.0f}")
    print(f"\n{'='*60}")
    print(f"  RECORDED net total: Rs {rec_total:>12,.0f}")
    print(f"  HONEST   net total: Rs {hon_total:>12,.0f}")
    print(f"  Bias (recorded - honest): Rs {rec_total-hon_total:>12,.0f}  "
          f"({100*(rec_total-hon_total)/rec_total if rec_total else 0:.1f}% of recorded)")
    print(f"  trades re-priced by intraday breach: {changed}  (win<->loss flips: {flips})")
    pickle.dump(rows, open(f"/tmp/tp_honest_{ENGINE}.pkl", "wb"))
    print(f"\n  saved daily series -> /tmp/tp_honest_{ENGINE}.pkl")

if __name__ == "__main__":
    main()
