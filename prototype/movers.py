#!/usr/bin/env python3
"""
movers — market-wide top gainers and losers across the FULL NSE cash universe.

WHY THIS EXISTS. The terminal's Market tab scores 50 names (NIFTY 50). Compared against
Zerodha's own panel on 2026-09-04, the two lists had ZERO overlap: our best gainer was
+2.74% against their +11.30%, and not one of their movers was in our universe. That is
not a data fault — a NIFTY 50 list structurally cannot contain the market's biggest
movers, because index constituents are the largest and least volatile names listed.

It also mattered internally: the floor trades small and mid caps (AARTIIND, GNFC,
JAYNECOIND) while the Market tab showed large caps, so the screen being watched had no
relationship to the book being traded.

COST. 2,634 symbols is six quote() batches of 500 — about two seconds. Cheap enough to
serve on demand, expensive enough that it is cached rather than recomputed per request.

TWO THINGS THIS DELIBERATELY DOES NOT DO:

  - It applies NO turnover floor by default. A 20% move on an illiquid name IS a market
    mover and belongs in the list; hiding it would misrepresent the day. The `min_turnover`
    argument exists so a caller who needs tradeable-only can say so explicitly, and the
    response always reports how many names were excluded rather than silently shrinking.
  - It does not rank by our score. A "gainers" list ranked by anything other than gain is
    not a gainers list — that exact bug was live in the terminal until 2026-09-04, where
    Losers led with -0.28% while a -1.73% name sat at the bottom.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE = ROOT / "quant" / "universe_full.txt"
BATCH = 500                      # Kite's documented per-call instrument cap
TTL = 30.0                       # seconds; the console polls faster than the market moves

_CACHE = {"at": 0.0, "data": None}


def universe() -> list:
    if not UNIVERSE.exists():
        raise FileNotFoundError(
            f"{UNIVERSE} missing — run: python3 quant/build_universe_full.py")
    return [l.strip() for l in UNIVERSE.read_text().splitlines() if l.strip()]


def _sweep() -> dict:
    from prototype.v4 import kite_data as kd
    k = kd.client()
    syms = universe()
    live, failed = {}, 0
    for i in range(0, len(syms), BATCH):
        chunk = syms[i:i + BATCH]
        try:
            live.update(k.quote([f"NSE:{s}" for s in chunk]))
        except Exception:
            failed += 1
    # A total failure must raise, not return an empty market. Returning {} here would
    # render as "nothing moved today", which is indistinguishable from a healthy quiet
    # session — the same silent-zero failure that blanked the floor for three days.
    if failed and not live:
        raise RuntimeError(f"all {failed} quote batches failed — check the Kite token")

    rows = []
    for s in syms:
        d = live.get(f"NSE:{s}")
        if not d:
            continue
        o = d.get("ohlc") or {}
        px = float(d.get("last_price") or 0)
        prev = float(o.get("close") or 0)
        if not px or not prev:
            continue
        rows.append({
            "symbol": s,
            "price": round(px, 2),
            "change": round((px / prev - 1) * 100, 2),
            "prev_close": round(prev, 2),
            "volume": int(d.get("volume") or 0),
            # Kite reports volume in shares; turnover in rupees is the useful figure and
            # is approximated here from the day's average trade price when available.
            "turnover": int(float(d.get("average_price") or px) * float(d.get("volume") or 0)),
            "high": float(o.get("high") or 0),
            "low": float(o.get("low") or 0),
        })
    return {"rows": rows, "at": datetime.now().strftime("%H:%M:%S"),
            "universe": len(syms), "quoted": len(rows), "failed_batches": failed}


def snapshot(force: bool = False) -> dict:
    now = time.time()
    if not force and _CACHE["data"] and now - _CACHE["at"] < TTL:
        return _CACHE["data"]
    d = _sweep()
    _CACHE["data"], _CACHE["at"] = d, now
    return d


def movers(n: int = 20, min_turnover: float = 0.0) -> dict:
    """Top n gainers and losers. min_turnover is in RUPEES, 0 = no filter."""
    snap = snapshot()
    rows = snap["rows"]
    excluded = 0
    if min_turnover > 0:
        before = len(rows)
        rows = [r for r in rows if r["turnover"] >= min_turnover]
        excluded = before - len(rows)
    gainers = sorted(rows, key=lambda r: -r["change"])[:n]
    losers = sorted(rows, key=lambda r: r["change"])[:n]
    return {
        "gainers": gainers,
        "losers": losers,
        "at": snap["at"],
        "universe": snap["universe"],
        "quoted": snap["quoted"],
        # reported, never silent — a filtered list that does not say what it hid is a
        # different claim from the one the reader thinks they are looking at
        "excluded_by_filter": excluded,
        "advances": sum(1 for r in rows if r["change"] > 0),
        "declines": sum(1 for r in rows if r["change"] < 0),
        "unchanged": sum(1 for r in rows if r["change"] == 0),
    }


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(ROOT))
    m = movers(10)
    print(f"  universe {m['universe']} · quoted {m['quoted']} · as of {m['at']}")
    print(f"  advances {m['advances']} · declines {m['declines']}")
    print("\n  TOP GAINERS")
    for r in m["gainers"]:
        print(f"    {r['symbol']:<14} {r['change']:+7.2f}%  Rs{r['price']:>10,.2f}")
    print("\n  TOP LOSERS")
    for r in m["losers"]:
        print(f"    {r['symbol']:<14} {r['change']:+7.2f}%  Rs{r['price']:>10,.2f}")
