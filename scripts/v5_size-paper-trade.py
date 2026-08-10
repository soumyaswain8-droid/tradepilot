#!/usr/bin/env python3
"""v5_size — v5 with FEWER, LARGER positions. The cost-cliff shadow.

THE QUESTION
Zerodha intraday brokerage is "0.03% or Rs20 per order, whichever is LOWER". Below
Rs66,667 per position the 0.03% binds and the round trip costs 0.1060%. Above it the
flat Rs20 binds and cost FALLS as size rises:

    position      round-trip cost
    Rs 12,000            0.1060%
    Rs 45,000            0.1060%     <- our historical maximum
    Rs100,000            0.0824%
    Rs200,000            0.0588%
    Rs500,000            0.0447%

Measured 2026-08-10 across 3,526 live paper trades: median position Rs7,252, largest
ever Rs44,992. Not one trade in three months crossed Rs66,667. Every engine has been
running permanently inside the most expensive fee bracket.

WHY THAT WAS STRUCTURAL, NOT BAD LUCK
    pool_manager.get_pool_budget() returns REMAINING cash, and
    v5-paper-trade.py:806 sets  base = budget * 0.15
    with MAX_POSITIONS_TOTAL = 20.
So size decays geometrically as the pool fills: Rs45,000, Rs38,250, Rs32,512 ...
Rs7,530 by the twelfth position. The median had to land near Rs7k. Raising capital
would not have fixed it — v5_deploy already ran a Rs6L INTRADAY pool and still had a
Rs12,891 median, because the dilution, not the capital, sets the size.

WHY THIS MATTERS MORE THAN ANY SIGNAL WORK
Measured gross edge across three independent families: v5's technical scorer +0.069%,
SMC/ICT +0.051%, evidenced baseline +0.057%, best confluence pair +0.091% — all
against a 0.1060% toll. Every one of them clears at Rs100,000-Rs200,000 per position
and none of them clears at Rs7,252. The binding constraint was never signal quality.

THE TWO VARIABLES, AND THEY ARE DELIBERATELY BOTH
    POOL_ALLOC          = {"INTRADAY": 1.0}   pool Rs10L instead of Rs3L
    MAX_POSITIONS_TOTAL = 5                   instead of 20

Both are needed and neither is sufficient. POOL_ALLOC alone still dilutes to a small
median across 20 slots; MAX_POSITIONS_TOTAL alone starts from a Rs3L pool. Together
the projected ladder is Rs150,000 / 127,500 / 108,375 / 92,119 / 78,301 — a median
near Rs108,000 and every position above the cliff.

    projected cost at the median: ~0.078% vs 0.1060% today, a saving of ~0.028%/trade
    which is larger than the entire net deficit we have been failing to close.

THIS IS NOT A TWO-VARIABLE CONFOUND IN THE USUAL SENSE
Both knobs move the SAME quantity — rupees per position. Neither touches selection,
entry timing, exits, or the score. v5 continues unchanged as the control, so the
comparison isolates position size and nothing else.

WHAT TO WATCH, AND WHAT WOULD FALSIFY IT
  - median position size: must exceed Rs66,667 or the experiment did not happen
  - cost as a % of turnover: must fall toward ~0.078% from 0.1060%
  - net P&L per trade vs v5 on the same names
  - SLIPPAGE, which is the real risk. A larger order can move the book, and every
    saving here is ~3 bps. If a Rs1.5L order in a NIFTY-200 name slips more than
    ~2 bps the gain is erased. NIFTY-200 medians run tens of crores of daily turnover
    so Rs1.5L is ~0.0075% of a day's volume, but this must be MEASURED against the
    order-book depth data, not assumed.
  - fewer positions means less diversification and lumpier daily P&L. A worse
    max-drawdown at the same net edge is a real cost, not a rounding error.

Run:
    python3 scripts/v5_size-paper-trade.py
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]          = "v5_size"
os.environ["POOL_ALLOC"]           = '{"INTRADAY":1.0}'
os.environ["MAX_POSITIONS_TOTAL"]  = "5"
os.environ["TELEGRAM_DISABLE"]     = "1"       # shadow: only live v5 alerts

# Deliberately NOT set, to keep position size the single variable against v5:
#   UNIVERSE_FILE (v5_wide), MIN_ENTRY_SCORE (v5_pick), NO_ENTRY_HOURS (v5_time),
#   MAX_HOLD_DAYS (v5_hold), NSE_DATA_SOURCE (v5_kite), WRONGWAY_CUT_PCT (v5_cut).
# TOTAL_CAPITAL is left at its Rs10L default — the same capital every engine has had
# all along. This experiment spends it differently, it does not add any.

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
