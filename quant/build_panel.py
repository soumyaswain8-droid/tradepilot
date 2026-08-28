#!/usr/bin/env python3
"""
build_panel — cache a minute-bar panel for the hypothesis search.

One Kite call per symbol (the API serves up to 60 days of minute data per request),
resampled to 5-minute bars. 200 symbols x ~60 sessions x 75 bars is roughly 900k
rows: small enough to hold in memory, long enough that a rule cannot survive on one
lucky fortnight.

UNIVERSE. Drawn from quant/universe_screened.txt, which is liquidity-screened, and
filtered to the tradeable band. Deliberately NOT the names the engines happened to
trade — that would only ever tell us about stocks we already like, and the question
is where money is available, not where we have been looking.

    python3 quant/build_panel.py            # build/refresh the cache
    python3 quant/build_panel.py --status
"""
from __future__ import annotations
import pickle, sys, time, warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Pickle is safe HERE and only here: this file is written by this script, read by
# this repo, and never sourced externally. It is a numeric cache of price bars, not
# a transport format. If it ever needs to cross a trust boundary, switch to parquet
# or msgspec — pickle would then be arbitrary code execution.
CACHE = ROOT / "quant" / "data" / "panel_5min.pkl"
N_SYMBOLS = 200
LOOKBACK_DAYS = 58          # Kite serves 60 days of minute data per request
BAR_MIN = 5


def universe(n=N_SYMBOLS):
    """Most liquid names in the tradeable band, by today's turnover."""
    from prototype.agents.scouts import ScoutTeam
    t = ScoutTeam(verbose=False)
    rows = t.sweep()
    rows.sort(key=lambda r: -r["turnover"])
    return [r["sym"] for r in rows[:n]]


def resample(raw, minutes=BAR_MIN):
    """Minute bars -> N-minute bars, keyed (date, HH:MM). Plain python; the whole
    panel is under a million rows and pandas adds more overhead than it saves."""
    out = {}
    for x in raw:
        d = str(x["date"])
        day, hh, mm = d[:10], int(d[11:13]), int(d[14:16])
        slot = (hh * 60 + mm) // minutes * minutes
        key = (day, f"{slot//60:02d}:{slot%60:02d}")
        o, h, l, c = float(x["open"]), float(x["high"]), float(x["low"]), float(x["close"])
        v = float(x.get("volume") or 0)
        if key not in out:
            out[key] = [o, h, l, c, v]
        else:
            b = out[key]
            b[1] = max(b[1], h); b[2] = min(b[2], l); b[3] = c; b[4] += v
    return out


def main():
    if "--status" in sys.argv:
        if CACHE.exists():
            p = pickle.loads(CACHE.read_bytes())
            days = sorted({d for s in p["bars"].values() for d, _ in s})
            print(f"  {len(p['bars'])} symbols, {len(days)} sessions "
                  f"({days[0]} -> {days[-1]})")
            print(f"  {sum(len(v) for v in p['bars'].values()):,} bars, "
                  f"{CACHE.stat().st_size/1e6:.1f} MB")
        else:
            print("  no panel cached")
        return 0

    from quant.diskguard import report
    report(2.0, "the 5-minute panel cache runs to tens of MB and grows with the universe")

    from prototype.v4 import kite_data as kd
    k = kd.client()
    syms = universe()
    print(f"  universe: {len(syms)} names")
    end = datetime.now()
    start = end - timedelta(days=LOOKBACK_DAYS)
    bars, failed = {}, []
    t0 = time.time()
    for i, s in enumerate(syms, 1):
        tok = kd.token_for(s)
        if not tok:
            failed.append(s); continue
        try:
            raw = k.historical_data(tok, start, end, "minute")
        except Exception as e:
            failed.append(s)
            if len(failed) < 4:
                print(f"    {s}: {str(e)[:50]}")
            continue
        if len(raw) < 2000:          # too little history to be usable
            failed.append(s); continue
        bars[s] = resample(raw)
        if i % 25 == 0:
            print(f"    {i}/{len(syms)}  ({time.time()-t0:.0f}s)", flush=True)
        time.sleep(0.34)             # Kite historical: 3 req/s
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_bytes(pickle.dumps({"bars": bars, "built": datetime.now().isoformat()}))
    days = sorted({d for s in bars.values() for d, _ in s})
    print(f"\n  cached {len(bars)} symbols, {len(days)} sessions "
          f"({days[0]} -> {days[-1]})")
    print(f"  {sum(len(v) for v in bars.values()):,} five-minute bars, "
          f"{CACHE.stat().st_size/1e6:.1f} MB, {len(failed)} symbols unavailable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
