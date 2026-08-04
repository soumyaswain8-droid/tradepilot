#!/usr/bin/env python3
"""v5_hold — let the thesis finish. Multi-day holds + reversal exit.

THE PROBLEM THIS ATTACKS
v5's exits say the strategy does not earn money the way its geometry assumes:

    reason        trades  win%    gross    avg
    STOPLOSS         154   26%   -9,503    -62
    TARGET            23  100%   +9,484   +412
    TIME_EXIT        135   62%   +4,377    +32
    SIGNAL_FLIP       75   31%   -1,000    -13

Only 4.6% of trades ever reach TARGET while 30% hit STOPLOSS, and the two almost
exactly cancel. Nearly all of v5's profit therefore comes from TIME_EXIT — the
give-up exit fired when the session ends. The stop/target structure is not what is
making the money.

THE EVIDENCE FOR HOLDING LONGER (PDH/PDL backtest, 892 setups, 20 symbols, 180 days,
Kite hourly bars, pessimistic fills)

    hold     win%  target%  unresolved      NET
    1 day     44%      11%         70%  -12,409
    2 days    44%      31%         18%  +28,186
    3 days    42%      35%          9%  +33,913
    5 days    41%      37%          3%   -5,504

Win rate FALLS while net rises sharply. That is the whole point: the constraint was
never picking winners, it was closing positions mid-thesis because the clock ran out.
At one day, 70% of trades never resolved at all. Five days gives it back, so the
optimum is bounded — this is "let it finish", not "hold forever". 3 sessions chosen.

TWO VARIABLES, BOTH AIMED AT THE SAME DEFECT
  MAX_HOLD_DAYS=3       an INTRADAY position survives up to 3 sessions instead of
                        being force-closed as TIME_EXIT at the first EOD
  REVERSAL_EXIT_PCT=0.5 a position in profit that gives back more than half its best
                        excursion is booked, rather than held for a target it
                        statistically will not reach. Soumya's framing: "look for the
                        candle signal; if it says it is time to sell, sell."

This is deliberately NOT single-variable, unlike the other shadows. Both changes
address the identical structural flaw and testing them apart would need six weeks
instead of three. If the engine wins, a follow-up split says which half did it.

THE RISK, MEASURED RATHER THAN ASSUMED
The backtest fills stops AT the stop price. Overnight that is often false. Across 960
overnight gaps on 8 large caps (180 days): median 0.46%, 90th percentile 1.58%, 99th
4.31%, worst 8.66% — and a 1% stop is JUMPED by 24% of overnight gaps. So +Rs 33,913
is an optimistic ceiling, and the live number will be lower. Overnight positions also
attract different margin treatment than intraday, which matters when real money
follows. This runs as a shadow for exactly these reasons.

WATCH: net P&L vs v5; the exit-reason mix (TARGET share should RISE and TIME_EXIT
should fall); and gap losses on carried positions — if overnight gaps eat the gain,
the backtest's fill assumption was the whole edge.

Run:
    python3 scripts/v5_hold-paper-trade.py
"""
import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["ENGINE_NAME"]        = "v5_hold"
os.environ["MAX_HOLD_DAYS"]      = "3"      # carry INTRADAY up to 3 sessions
os.environ["REVERSAL_EXIT_PCT"]  = "0.5"    # book a fade rather than chase target
os.environ["TELEGRAM_DISABLE"]   = "1"      # shadow: only live v5 alerts

# Deliberately NOT set, so this tests exit behaviour and nothing else:
#   MIN_ENTRY_SCORE (v5_pick), POOL_ALLOC (v5_deploy), NO_ENTRY_HOURS (v5_time),
#   NSE_DATA_SOURCE (v5_kite), CHOP_FILTER, RISK_GATE_DRIVE.

target = str(Path(__file__).parent / "v5-paper-trade.py")
sys.argv = [target] + sys.argv[1:]
runpy.run_path(target, run_name="__main__")
