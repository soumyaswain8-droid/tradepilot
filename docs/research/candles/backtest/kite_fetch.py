#!/usr/bin/env python3
"""Fetch 5-minute bars for the engine universe from Kite's historical API (needs a live
access token in .env) and save them in the same shape as ../data/bars_5m.pkl:
MultiIndex (symbol, ts) with Open/High/Low/Close/Volume.

    python3 kite_fetch.py --days 95 --out ../data/bars_5m_kite.pkl

Kite serves at most 100 days of 5-minute bars per request; one request per symbol.
Rate limit is 3 requests/second, so ~410 symbols take about 2.5 minutes.
"""
from __future__ import annotations
import os, sys, time, argparse
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "prototype"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=95)
    ap.add_argument("--out", default=os.path.join(HERE, "..", "data", "bars_5m_kite.pkl"))
    args = ap.parse_args()
    from prototype.v4 import kite_data as kd
    from data_engine import NIFTY_STOCKS
    ok, detail = kd.token_alive()
    if not ok:
        print("Kite token not alive:", detail); sys.exit(2)
    frames = {}
    syms = list(NIFTY_STOCKS)
    for i, s in enumerate(syms):
        sym = s.replace(".NS", "")
        try:
            df = kd.get_candles(sym, "5minute", days=args.days)
        except Exception as e:
            print("skip", sym, type(e).__name__, str(e)[:60], flush=True); df = None
        if df is not None and len(df):
            df = df.rename(columns=str.lower)
            cols = {c: c.capitalize() for c in ("open", "high", "low", "close", "volume") if c in df.columns}
            df = df.rename(columns=cols)
            if "date" in df.columns:
                df = df.set_index("date")
            df.index = pd.to_datetime(df.index)
            if df.index.tz is None:
                df.index = df.index.tz_localize("Asia/Kolkata")
            frames[s] = df[["Open", "High", "Low", "Close", "Volume"]]
        if i % 50 == 0:
            print(i, "of", len(syms), "ok", len(frames), flush=True)
        time.sleep(0.35)
    allf = pd.concat(frames, names=["symbol", "ts"])
    allf.to_pickle(args.out)
    days = allf.index.get_level_values("ts").normalize().nunique()
    print("saved", args.out, allf.shape, "symbols", len(frames), "sessions", days, flush=True)


if __name__ == "__main__":
    main()
