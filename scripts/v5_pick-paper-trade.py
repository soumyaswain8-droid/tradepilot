#!/usr/bin/env python3
"""v5_pick — v5 with an entry-quality floor. Selectivity shadow.

THE HYPOTHESIS
Trade fewer, better-scored stocks and keep more of the gross profit. Soumya's brief
was "scan good stocks and make more profit" and explicitly NOT "short more" — this
tests exactly that, and nothing else.

WHAT THE DATA SAID (v5's last 25 sessions, 414 closed trades, measured 2026-08-04)
Score barely predicts WIN RATE: winners averaged 56.3, losers 54.9, Cohen's d 0.06.
That is noise. But it predicts NET P&L strongly, because payoff SIZE differs even
where hit rate does not:

    floor   trades   gross    costs      NET   net/trade
        0      414   6,177    5,920      256         0.6
       70      193   7,121    2,760    4,361        22.6
       80       92   5,107    1,316    3,791        41.2

Two things stand out. Gross profit is HIGHER at the 70 floor than with no floor, so
sub-70 entries lose money before costs are even counted. And at 414 trades, costs
(Rs 14.30 round trip) consume 96% of gross — the strategy earns an edge and hands
almost all of it to the broker.

THE ONE VARIABLE: MIN_ENTRY_SCORE=70. Same strategy, capital, risk, universe, feed.
Direction-neutral: it filters on score alone and treats LONG and SHORT identically,
so it cannot quietly become a shorting experiment.

EXPECTED SIDE EFFECT, stated up front: turnover falls from ~50% to ~23%, BELOW the
45-55% band Soumya set. That band and the profit target conflict here, and this
shadow exists to find out which one is worth keeping. Backtest says the profit is
17x better at roughly half the churn — but a counterfactual replay assumes every
surviving trade fills the same way, which live trading will test and a spreadsheet
cannot.

WATCH: net P&L per session vs v5, trades per session, and whether gross P&L holds up
when the low-score entries are gone. If gross collapses, the counterfactual was
selection bias and the floor should be dropped.

Run:
    python3 scripts/v5_pick-paper-trade.py
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]       = "v5_pick"
os.environ["MIN_ENTRY_SCORE"]   = "70"     # THE one variable under test
os.environ["TELEGRAM_DISABLE"]  = "1"      # shadow: only live v5 alerts

# Deliberately NOT set, to keep this a single-variable experiment against v5:
#   CHOP_FILTER, RISK_GATE_DRIVE, MAX_POSITION_PCT, NSE_DATA_SOURCE,
#   SHORT_REQ_* — the brief was explicitly "do not short more".

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
