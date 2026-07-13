# Trade Audit & Bear-Day Solution — 2026-07-01

*Regime: **SIDEWAYS*** — generated 15:35:12

## Bottom line

- **Realized P&L today: Rs -4,902** across 146 trades (54 long / 92 short)
- **Rs left on the table: Rs 17,427** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 17,427**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 82 | 34/48 | 36 | Rs -2,527 | Rs 8,881 |
| v5_classic | 64 | 20/44 | 27 | Rs -2,375 | Rs 8,546 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 49 | Rs -5,845 | Rs 11,690 |
| WRONG_DIRECTION | 29 | Rs -2,868 | Rs 5,737 |
| GOOD_TRADE | 63 | Rs 3,811 | Rs 0 |
| LOSS_OTHER | 5 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

2. **Short selection:** 49 shorts hit risers (Rs 11,690 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | DABUR | SHORT | 422.2→432.8 | Rs -728 | SHORTED_RISER | Rs 1,456 |
| v5 | DABUR | SHORT | 422.2→432.6 | Rs -721 | SHORTED_RISER | Rs 1,442 |
| v5 | HINDUNILVR | SHORT | 2,118.2→2,150.3 | Rs -578 | SHORTED_RISER | Rs 1,156 |
| v5_classic | HINDUNILVR | SHORT | 2,118.2→2,150.2 | Rs -576 | SHORTED_RISER | Rs 1,152 |
| v5 | TORNTPHARM | SHORT | 4,620.1→4,674.0 | Rs -377 | SHORTED_RISER | Rs 755 |
| v5_classic | TORNTPHARM | SHORT | 4,620.1→4,674.0 | Rs -377 | SHORTED_RISER | Rs 755 |
| v5 | COROMANDEL | LONG | 2,005.0→1,967.4 | Rs -301 | WRONG_DIRECTION | Rs 602 |
| v5 | COROMANDEL | SHORT | 1,955.7→1,978.3 | Rs -271 | SHORTED_RISER | Rs 542 |
| v5_classic | COROMANDEL | SHORT | 1,955.7→1,978.3 | Rs -271 | SHORTED_RISER | Rs 542 |
| v5 | LICHSGFIN | LONG | 564.0→554.4 | Rs -259 | WRONG_DIRECTION | Rs 518 |
| v5_classic | COROMANDEL | LONG | 2,005.0→1,967.4 | Rs -226 | WRONG_DIRECTION | Rs 451 |
| v5 | FEDERALBNK | LONG | 331.0→327.6 | Rs -217 | WRONG_DIRECTION | Rs 435 |
| v5 | DABUR | LONG | 437.8→431.8 | Rs -200 | WRONG_DIRECTION | Rs 399 |
| v5_classic | POWERINDIA | SHORT | 34,085.0→34,280.0 | Rs -195 | SHORTED_RISER | Rs 390 |
| v5_classic | WAAREEENER | LONG | 2,947.0→2,923.9 | Rs -185 | WRONG_DIRECTION | Rs 370 |
