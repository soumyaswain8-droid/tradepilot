# Trade Audit & Bear-Day Solution — 2026-07-22

*Regime: **SIDEWAYS*** — generated 15:35:15

## Bottom line

- **Realized P&L today: Rs -1,532** across 112 trades (44 long / 68 short)
- **Rs left on the table: Rs 9,872** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 9,872**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 63 | 28/35 | 26 | Rs -1,984 | Rs 6,011 |
| v5_classic | 49 | 16/33 | 20 | Rs 452 | Rs 3,861 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 28 | Rs -3,618 | Rs 7,237 |
| SHORTED_RISER | 34 | Rs -1,318 | Rs 2,635 |
| GOOD_TRADE | 46 | Rs 3,404 | Rs 0 |
| LOSS_OTHER | 4 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

2. **Short selection:** 34 shorts hit risers (Rs 2,635 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | EXIDEIND | LONG | 444.3→438.5 | Rs -319 | WRONG_DIRECTION | Rs 638 |
| v5 | TVSMOTOR | LONG | 3,955.0→3,891.3 | Rs -318 | WRONG_DIRECTION | Rs 637 |
| v5 | LAURUSLABS | LONG | 1,599.0→1,580.4 | Rs -316 | WRONG_DIRECTION | Rs 632 |
| v5 | SHRIRAMFIN | LONG | 1,063.0→1,047.5 | Rs -310 | WRONG_DIRECTION | Rs 620 |
| v5_classic | MCX | SHORT | 2,801.2→2,823.2 | Rs -242 | SHORTED_RISER | Rs 484 |
| v5_classic | PIDILITIND | LONG | 1,591.3→1,577.8 | Rs -216 | WRONG_DIRECTION | Rs 432 |
| v5 | IDEA | LONG | 13.6→13.4 | Rs -205 | WRONG_DIRECTION | Rs 410 |
| v5 | SRF | LONG | 2,947.4→2,906.8 | Rs -203 | WRONG_DIRECTION | Rs 406 |
| v5 | KOTAKBANK | LONG | 386.7→382.7 | Rs -196 | WRONG_DIRECTION | Rs 392 |
| v5_classic | EICHERMOT | LONG | 7,689.5→7,606.0 | Rs -167 | WRONG_DIRECTION | Rs 334 |
| v5_classic | FEDERALBNK | LONG | 356.1→353.6 | Rs -162 | WRONG_DIRECTION | Rs 325 |
| v5_classic | ABCAPITAL | LONG | 409.1→407.2 | Rs -137 | WRONG_DIRECTION | Rs 274 |
| v5 | TATASTEEL | SHORT | 185.7→186.6 | Rs -135 | SHORTED_RISER | Rs 270 |
| v5 | LENSKART | LONG | 555.6→551.1 | Rs -130 | WRONG_DIRECTION | Rs 261 |
| v5_classic | UPL | LONG | 618.1→611.1 | Rs -120 | WRONG_DIRECTION | Rs 240 |
