#!/usr/bin/env python3
"""v5_wide — v5 on a liquidity-screened 837-stock universe. Selection-quality shadow.

THE QUESTION
Our engines scan 200 stocks (NIFTY 200). NSE lists 4,353. Does the extra choice
improve which 20 positions we end up holding?

WHY THIS IS NOT "TRADE MORE", WHICH THE EVIDENCE FORBIDS
Yesterday's finding was that costs consume 96% of gross profit and that
correlation(turnover, net) is -0.36 — trading more is how this stack loses. A wider
universe sounds like exactly that. Measured, it is not:

    engine   universe   median trades/session
    v5            200                     53
    v5_cut        446                     60

2.23x the universe produced 1.14x the trades. MAX_POSITIONS_TOTAL=20 and the
per-scan cap bind first, so a wider universe changes WHICH names fill the 20 slots
rather than how many trades happen. That makes this a selection-quality experiment,
not a frequency one. (Caveat: v5_cut also runs WRONGWAY_CUT and a different short
gate, so that comparison is suggestive rather than clean — which is the reason this
runs as a shadow.)

HOW THE UNIVERSE WAS BUILT — screened, not index-derived
Index membership is not liquidity. 3MINDIA is a NIFTY 500 constituent that traded
275 shares in a day; EIHOTEL did Rs 0.40 Cr. So every one of the 837 passed a 60-day
screen (scripts/screen-liquidity.py): median (not mean) turnover >= Rs 5 Cr, traded
on >=95% of sessions, our Rs 45,000 position <= 0.5% of daily turnover, price >=
Rs 10, position buys >= 10 shares, and mean/median <= 3.0x.

That last test matters most. NIACL looked like the single best addition on a
snapshot — it was trading at 6.4x normal that day, and its 60-day mean is 9.5x its
median. Screening on one day's turnover would have bought precisely the stocks
having an unusual day.

THE ONE VARIABLE: UNIVERSE_FILE=quant/universe_screened.txt (837 vs v5's 200).
Same strategy, capital, risk, sizing, feed, exits.

WATCH: trades per session (should stay near v5's 53 — if it jumps, the cap is not
binding as measured and this becomes a frequency change); net P&L; and whether the
newly added names actually appear in the book or the score ranking keeps favouring
the NIFTY 200 anyway.

Run:
    python3 scripts/v5_wide-paper-trade.py
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]      = "v5_wide"
os.environ["UNIVERSE_FILE"]    = str(ROOT / "quant" / "universe_screened.txt")
os.environ["TELEGRAM_DISABLE"] = "1"       # shadow: only live v5 alerts

# Deliberately NOT set, to keep this single-variable against v5:
#   MIN_ENTRY_SCORE (v5_pick), POOL_ALLOC (v5_deploy), NO_ENTRY_HOURS (v5_time),
#   MAX_HOLD_DAYS (v5_hold), NSE_DATA_SOURCE (v5_kite), WRONGWAY_CUT_PCT (v5_cut).

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
