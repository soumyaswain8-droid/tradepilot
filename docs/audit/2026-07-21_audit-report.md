# Trade Audit & Bear-Day Solution — 2026-07-21

*Regime: **SIDEWAYS*** — generated 15:35:25

## Bottom line

- **Realized P&L today: Rs -836** across 87 trades (39 long / 48 short)
- **Rs left on the table: Rs 6,512** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 6,512**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 40 | 21/19 | 11 | Rs -411 | Rs 1,881 |
| v5_classic | 47 | 18/29 | 13 | Rs -425 | Rs 4,631 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 17 | Rs -1,944 | Rs 3,888 |
| WRONG_DIRECTION | 9 | Rs -1,312 | Rs 2,624 |
| GOOD_TRADE | 24 | Rs 2,420 | Rs 0 |
| LOSS_OTHER | 37 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

2. **Short selection:** 17 shorts hit risers (Rs 3,888 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | DIXON | LONG | 14,589.0→14,219.0 | Rs -370 | WRONG_DIRECTION | Rs 740 |
| v5_classic | M&M | LONG | 3,181.4→3,145.5 | Rs -323 | WRONG_DIRECTION | Rs 646 |
| v5_classic | IDEA | SHORT | 13.5→13.6 | Rs -322 | SHORTED_RISER | Rs 644 |
| v5 | OIL | SHORT | 448.9→452.6 | Rs -319 | SHORTED_RISER | Rs 638 |
| v5_classic | LTF | LONG | 308.7→305.9 | Rs -238 | WRONG_DIRECTION | Rs 476 |
| v5_classic | ICICIAMC | SHORT | 3,117.4→3,136.6 | Rs -230 | SHORTED_RISER | Rs 461 |
| v5_classic | AUBANK | SHORT | 993.3→1,000.0 | Rs -194 | SHORTED_RISER | Rs 389 |
| v5 | KALYANKJIL | SHORT | 559.8→562.9 | Rs -186 | SHORTED_RISER | Rs 372 |
| v5_classic | EXIDEIND | LONG | 445.2→441.6 | Rs -170 | WRONG_DIRECTION | Rs 341 |
| v5_classic | KALYANKJIL | SHORT | 559.6→562.6 | Rs -121 | SHORTED_RISER | Rs 242 |
| v5 | ZYDUSLIFE | SHORT | 1,139.2→1,146.7 | Rs -120 | SHORTED_RISER | Rs 240 |
| v5 | ULTRACEMCO | LONG | 12,071.0→11,963.0 | Rs -108 | WRONG_DIRECTION | Rs 216 |
| v5_classic | OIL | SHORT | 448.7→451.0 | Rs -104 | SHORTED_RISER | Rs 207 |
| v5 | BANKBARODA | LONG | 254.1→250.2 | Rs -75 | WRONG_DIRECTION | Rs 150 |
| v5_classic | CGPOWER | SHORT | 904.1→910.0 | Rs -65 | SHORTED_RISER | Rs 131 |
