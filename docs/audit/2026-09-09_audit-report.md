# Trade Audit & Bear-Day Solution — 2026-09-09

*Regime: **SIDEWAYS*** — generated 15:36:06

## Bottom line

- **Realized P&L today: Rs 381** across 62 trades (27 long / 35 short)
- **Rs left on the table: Rs 3,567** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 3,567**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 62 | 27/35 | 33 | Rs 381 | Rs 3,567 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 13 | Rs -1,005 | Rs 2,009 |
| WRONG_DIRECTION | 9 | Rs -779 | Rs 1,558 |
| GOOD_TRADE | 33 | Rs 2,165 | Rs 0 |
| LOSS_OTHER | 7 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

2. **Short selection:** 13 shorts hit risers (Rs 2,009 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | BAJFINANCE | SHORT | 1,045.7→1,057.7 | Rs -384 | SHORTED_RISER | Rs 768 |
| v5 | BEL | LONG | 413.4→409.0 | Rs -298 | WRONG_DIRECTION | Rs 596 |
| v5 | ADANIENSOL | LONG | 1,432.4→1,416.3 | Rs -209 | WRONG_DIRECTION | Rs 419 |
| v5 | KPITTECH | SHORT | 552.8→555.9 | Rs -113 | SHORTED_RISER | Rs 226 |
| v5 | SUZLON | LONG | 46.2→46.0 | Rs -103 | WRONG_DIRECTION | Rs 207 |
| v5 | TATACONSUM | SHORT | 1,005.4→1,010.7 | Rs -80 | SHORTED_RISER | Rs 159 |
| v5 | LGEINDIA | SHORT | 1,653.4→1,664.4 | Rs -77 | SHORTED_RISER | Rs 154 |
| v5 | BHARATFORG | SHORT | 1,974.9→1,988.6 | Rs -68 | SHORTED_RISER | Rs 137 |
| v5 | ICICIAMC | SHORT | 2,965.4→2,988.1 | Rs -68 | SHORTED_RISER | Rs 136 |
| v5 | ENRIN | SHORT | 3,169.0→3,185.9 | Rs -68 | SHORTED_RISER | Rs 135 |
| v5 | GVT&D | LONG | 4,756.9→4,689.7 | Rs -67 | WRONG_DIRECTION | Rs 134 |
| v5 | ASHOKLEY | SHORT | 166.5→167.3 | Rs -63 | SHORTED_RISER | Rs 125 |
| v5 | ITC | SHORT | 260.7→262.2 | Rs -58 | SHORTED_RISER | Rs 117 |
| v5 | POWERGRID | LONG | 268.7→267.4 | Rs -55 | WRONG_DIRECTION | Rs 109 |
| v5 | NTPC | LONG | 335.4→334.9 | Rs -24 | WRONG_DIRECTION | Rs 48 |
