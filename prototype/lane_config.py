"""
Shared sizing for the small-capital lanes (real / opt / sarathi).

One place to change the number, because on Wednesday it stops being paper money.
Every lane reads LANE_CAPITAL rather than carrying its own constant — the previous
arrangement had 1000.0 hardcoded in two files, which is exactly how a lane ends up
trading a different size from the one you think you authorised.

    LANE_CAPITAL=3000 LANE_MODE=paper   python3 scripts/real1k.py --card
    LANE_CAPITAL=3000 LANE_MODE=real    python3 scripts/real1k.py --card

WHY Rs3,000 AND WHY TWO POSITIONS (measured 2026-08-24)
Below the Rs66,667 brokerage cliff EVERY fee component is proportional — brokerage
at 0.03%, STT, exchange txn, GST, stamp. Verified: a Rs12,000 position and a Rs6,000
position both cost 0.1060% round trip. So splitting is FREE, and two positions double
the observations per session at no cost. That matters when the gate is "10 sessions".

Three positions would drop the tradeable universe from 82% to 58% of liquid names,
because the price ceiling falls with the per-position budget. Two is the corner.

QUANTISATION, THE REAL CONSTRAINT AT THIS SIZE
At Rs1,000/4x the binding constraint was never fees — it was that a Rs2,500 stock
buys one share. MIN_QTY sets the worst-case sizing error: 10 shares means at most a
10% miss on intended size. The price ceiling is DERIVED from that, never guessed.
"""
from __future__ import annotations
import os

LANE_CAPITAL = float(os.environ.get("LANE_CAPITAL", 3000.0))
LANE_MODE = os.environ.get("LANE_MODE", "paper").lower()   # "paper" | "real"

# ── equity lane ──────────────────────────────────────────────────────────────
LEVERAGE = 4.0                      # MIS intraday on liquid names
N_POSITIONS = 2
MIN_QTY = 10                        # <=10% quantisation error (was 5 at Rs1k)
MIN_PRICE = 80.0

EXPOSURE = LANE_CAPITAL * LEVERAGE
PER_POSITION = EXPOSURE / N_POSITIONS
MAX_PRICE = PER_POSITION / MIN_QTY  # derived, not chosen

# ── options lane ─────────────────────────────────────────────────────────────
OPT_BUDGET = LANE_CAPITAL
OPT_RT_FEES = 47.0                  # brokerage + taxes on a round trip, flat-ish


def summary() -> str:
    return (f"capital Rs{LANE_CAPITAL:,.0f} [{LANE_MODE.upper()}] | "
            f"{N_POSITIONS} x Rs{PER_POSITION:,.0f} @ {LEVERAGE:.0f}x "
            f"= Rs{EXPOSURE:,.0f} | band Rs{MIN_PRICE:.0f}-{MAX_PRICE:,.0f} "
            f"(>={MIN_QTY} sh) | options budget Rs{OPT_BUDGET:,.0f} "
            f"(fees {OPT_RT_FEES/OPT_BUDGET*100:.2f}% of budget)")


if __name__ == "__main__":
    print("  " + summary())
