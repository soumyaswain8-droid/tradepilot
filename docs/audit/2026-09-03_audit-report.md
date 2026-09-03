# Trade Audit & Bear-Day Solution — 2026-09-03

*Regime: **BEAR*** — generated 15:36:11

## Bottom line

- **Realized P&L today: Rs 2,585** across 48 trades (17 long / 31 short)
- **Rs left on the table: Rs 1,875** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 1,875**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 48 | 17/31 | 27 | Rs 2,585 | Rs 1,875 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 14 | Rs -643 | Rs 1,284 |
| LONG_IN_BEAR | 6 | Rs -296 | Rs 591 |
| GOOD_TRADE | 27 | Rs 3,523 | Rs 0 |
| LOSS_OTHER | 1 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 6 longs in a bear regime cost Rs 591 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 14 shorts hit risers (Rs 1,284 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | MOTILALOFS | SHORT | 1,008.7→1,022.1 | Rs -241 | SHORTED_RISER | Rs 482 |
| v5 | MCX | SHORT | 3,187.8→3,211.0 | Rs -116 | SHORTED_RISER | Rs 232 |
| v5 | ADANIENSOL | LONG | 1,393.4→1,381.9 | Rs -115 | LONG_IN_BEAR | Rs 230 |
| v5 | 360ONE | SHORT | 1,152.5→1,161.6 | Rs -109 | SHORTED_RISER | Rs 218 |
| v5 | SWIGGY | LONG | 273.7→269.7 | Rs -76 | LONG_IN_BEAR | Rs 152 |
| v5 | INDUSTOWER | LONG | 378.1→374.1 | Rs -67 | LONG_IN_BEAR | Rs 134 |
| v5 | TITAN | SHORT | 4,961.0→4,992.0 | Rs -62 | SHORTED_RISER | Rs 124 |
| v5 | TMPV | LONG | 312.1→311.1 | Rs -27 | LONG_IN_BEAR | Rs 54 |
| v5 | GLENMARK | SHORT | 2,431.6→2,444.2 | Rs -25 | SHORTED_RISER | Rs 50 |
| v5 | NESTLEIND | SHORT | 1,409.7→1,413.6 | Rs -23 | SHORTED_RISER | Rs 47 |
| v5 | SUPREMEIND | SHORT | 3,497.3→3,510.8 | Rs -14 | SHORTED_RISER | Rs 27 |
| v5 | MCX | SHORT | 3,183.4→3,187.1 | Rs -11 | SHORTED_RISER | Rs 22 |
| v5 | ZYDUSLIFE | SHORT | 1,137.9→1,140.6 | Rs -11 | SHORTED_RISER | Rs 22 |
| v5 | ADANIGREEN | LONG | 1,293.4→1,292.6 | Rs -10 | LONG_IN_BEAR | Rs 21 |
| v5 | HINDALCO | SHORT | 1,003.2→1,004.4 | Rs -10 | SHORTED_RISER | Rs 19 |
