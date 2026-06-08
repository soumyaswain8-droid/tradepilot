# Trade Audit & Bear-Day Solution — 2026-06-08

*Regime: **BEAR*** — generated 16:34:05

## Bottom line

- **Realized P&L today: Rs -11,128** across 194 trades (121 long / 73 short)
- **Rs left on the table: Rs 52,221** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 40,718**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 8,850**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v4 | 94 | 94/0 | 32 | Rs -8,325 | Rs 32,764 |
| v5 | 53 | 13/40 | 32 | Rs 465 | Rs 6,817 |
| v5_classic | 47 | 14/33 | 28 | Rs -3,268 | Rs 12,640 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LONG_IN_BEAR | 78 | Rs -18,826 | Rs 37,650 |
| GOOD_TRADE | 57 | Rs 8,245 | Rs 6,258 |
| EXIT_TOO_EARLY | 35 | Rs 994 | Rs 5,205 |
| SHORTED_RISER | 22 | Rs -1,535 | Rs 3,068 |
| IGNORED_SIGNAL | 2 | Rs -7 | Rs 40 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 113 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| JSWINFRA | AVOID | -3.47% | Rs 1,041 |
| EXIDEIND | AVOID | -3.42% | Rs 1,026 |
| BAJAJHLDNG | AVOID | -3.25% | Rs 975 |
| CHOLAFIN | AVOID | -3.14% | Rs 942 |
| ASTRAZEN | AVOID | -2.98% | Rs 894 |
| SHRIRAMFIN | AVOID | -2.89% | Rs 867 |
| THERMAX | AVOID | -2.81% | Rs 843 |
| INDIGO | AVOID | -2.71% | Rs 813 |
| SBICARD | AVOID | -2.55% | Rs 765 |
| SHREECEM | AVOID | -2.28% | Rs 684 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 78 longs in a bear regime cost Rs 37,650 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 22 shorts hit risers (Rs 3,068 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 113 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 8,850 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | PERSISTENT | LONG | 5,482.0→4,952.5 | Rs -1,588 | LONG_IN_BEAR | Rs 3,177 |
| v5_classic | LTM | LONG | 4,265.8→3,955.8 | Rs -930 | LONG_IN_BEAR | Rs 1,860 |
| v5_classic | TCS | LONG | 2,327.5→2,153.7 | Rs -869 | LONG_IN_BEAR | Rs 1,738 |
| v5_classic | TECHM | LONG | 1,548.4→1,468.0 | Rs -724 | LONG_IN_BEAR | Rs 1,447 |
| v4 | OIL | LONG | 489.3→479.9 | Rs -539 | LONG_IN_BEAR | Rs 1,077 |
| v4 | UNIONBANK | LONG | 168.2→164.2 | Rs -537 | LONG_IN_BEAR | Rs 1,074 |
| v5 | BHEL | SHORT | 378.0→387.1 | Rs -522 | SHORTED_RISER | Rs 1,043 |
| v4 | BIOCON | LONG | 415.7→409.3 | Rs -512 | LONG_IN_BEAR | Rs 1,024 |
| v4 | TATACOMM | LONG | 1,972.8→1,941.5 | Rs -501 | LONG_IN_BEAR | Rs 1,002 |
| v4 | RADICO | LONG | 3,513.0→3,459.1 | Rs -485 | LONG_IN_BEAR | Rs 970 |
| v4 | CANBK | LONG | 136.4→134.7 | Rs -417 | LONG_IN_BEAR | Rs 834 |
| v4 | VOLTAS | LONG | 1,322.2→1,302.5 | Rs -414 | LONG_IN_BEAR | Rs 827 |
| v4 | DRREDDY | LONG | 1,291.6→1,275.7 | Rs -413 | LONG_IN_BEAR | Rs 827 |
| v4 | ADANIENSOL | LONG | 1,596.8→1,571.2 | Rs -410 | LONG_IN_BEAR | Rs 819 |
| v4 | MCX | LONG | 2,832.1→2,788.0 | Rs -397 | LONG_IN_BEAR | Rs 794 |
