#!/usr/bin/env python3
"""
build_universe_full — the complete NSE cash-equity universe, so nothing is missed.

WHY. The terminal scored 50 names (NIFTY 50) while the floor screened 938 and Zerodha's
own movers panel covers NIFTY 500. Comparing the three on 2026-09-04 found ZERO overlap
between our top gainers and Zerodha's: our ceiling was +2.74% against their +11.30%, not
because our data was wrong but because a NIFTY 50 list structurally cannot contain the
market's biggest movers. Soumya's instruction was to miss no stock.

WHAT COUNTS AS "EVERY STOCK", stated because the word hides three choices:

  - SERIES EQ ONLY. BE is the trade-for-trade segment (every order settles individually,
    no intraday netting) and its price series is not comparable. SM/ST are SME platform
    boards with different lot sizes and circuit rules. Including them would pad the count
    and corrupt the movers list with names nobody here can trade normally.
  - MUST HAVE A KITE INSTRUMENT TOKEN. A symbol we cannot quote is not in the universe,
    it is a hole in it — and a silent one, since a missing quote just fails to appear.
  - RECENTLY TRADED. A name absent from the last 30 sessions is delisted or suspended.
    Keeping it means permanently requesting a quote that will never come back.

No turnover floor is applied here. This file is the FULL universe; liquidity screening
belongs to whatever consumes it, because the movers view legitimately wants to show an
illiquid name that moved 20% while the trading screen legitimately does not.

    python3 quant/build_universe_full.py            # writes quant/universe_full.txt
    python3 quant/build_universe_full.py --stats    # describe it, write nothing
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
PANEL = ROOT / "quant" / "data" / "bhavcopy_daily.parquet"
OUT = ROOT / "quant" / "universe_full.txt"
RECENT_SESSIONS = 30


def build(verbose: bool = True) -> list:
    if not PANEL.exists():
        raise FileNotFoundError(f"{PANEL} missing — run: python3 quant/bars.py --build")
    d = pd.read_parquet(PANEL)

    last = d["date"].max()
    cutoff = last - timedelta(days=RECENT_SESSIONS * 2)   # calendar days for ~30 sessions
    recent = d[d["date"] >= cutoff]
    syms = sorted(set(recent["symbol"].astype(str)))
    if verbose:
        print(f"  bhavcopy: {len(syms)} EQ symbols traded since {str(cutoff)[:10]}")

    # Intersect with what Kite can actually quote. A symbol with no instrument token is
    # a silent hole — the quote simply never arrives and the name vanishes from every
    # view without an error.
    try:
        from prototype.agents.scouts import ScoutTeam
        names = ScoutTeam(verbose=False)._instrument_names()
        tradeable = [s for s in syms if s in names]
        if verbose:
            print(f"  with a Kite instrument token: {len(tradeable)} "
                  f"({len(syms) - len(tradeable)} dropped as unquotable)")
    except Exception as e:
        print(f"  WARNING could not load Kite instruments ({str(e)[:60]});")
        print("  keeping the bhavcopy list unfiltered — re-run when Kite is reachable.")
        tradeable = syms
    return tradeable


def main() -> int:
    stats_only = "--stats" in sys.argv
    syms = build()
    if stats_only:
        d = pd.read_parquet(PANEL)
        s = d[d["date"] == d["date"].max()]
        s = s[s["symbol"].isin(syms)]
        print(f"\n  on the last session ({str(d['date'].max())[:10]}):")
        for t, lbl in ((0, "any turnover"), (10, ">= Rs 10 lakh"),
                       (100, ">= Rs 1 crore"), (500, ">= Rs 5 crore")):
            print(f"    {lbl:<16} {(s['turnover_lakh'] >= t).sum()}")
        return 0
    OUT.write_text("\n".join(syms) + "\n")
    print(f"  wrote {len(syms)} symbols -> {OUT.name}")
    print(f"  for comparison: nifty50=50, screened=938, expanded=454")
    return 0


if __name__ == "__main__":
    sys.exit(main())
