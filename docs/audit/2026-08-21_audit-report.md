# Trade Audit & Bear-Day Solution — 2026-08-21

*Regime: **SIDEWAYS*** — generated 15:35:43

## Bottom line

- **Realized P&L today: Rs -567** across 118 trades (62 long / 56 short)
- **Rs left on the table: Rs 14,046** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,418**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,336**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 72 | 42/30 | 37 | Rs 67 | Rs 8,783 |
| v5_classic | 46 | 20/26 | 21 | Rs -635 | Rs 5,263 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 27 | Rs -2,577 | Rs 5,153 |
| WRONG_DIRECTION | 25 | Rs -1,633 | Rs 3,385 |
| GOOD_TRADE | 34 | Rs 4,068 | Rs 2,161 |
| EXIT_TOO_EARLY | 24 | Rs 528 | Rs 1,827 |
| HELD_LOSER | 7 | Rs -909 | Rs 1,430 |
| IGNORED_SIGNAL | 1 | Rs -45 | Rs 90 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| SADBHAV | AVOID | -3.61% | Rs 1,083 |
| BRITANNIA | AVOID | -3.3% | Rs 990 |
| KEI | AVOID | -2.6% | Rs 780 |
| ZYDUSWELL | AVOID | -2.09% | Rs 627 |
| VBL | AVOID | -1.87% | Rs 561 |
| ATGL | AVOID | -1.76% | Rs 528 |
| JYOTHYLAB | AVOID | -1.68% | Rs 504 |
| TIINDIA | AVOID | -1.51% | Rs 453 |
| CHOLAFIN | AVOID | -1.38% | Rs 414 |
| TATACOMM | AVOID | -1.32% | Rs 396 |

## Prescription — flip a bear day

2. **Short selection:** 27 shorts hit risers (Rs 5,153 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,336 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | GLENMARK | LONG | 2,337.0→2,306.6 | Rs -334 | WRONG_DIRECTION | Rs 669 |
| v5 | SBICARD | LONG | 649.1→640.5 | Rs -310 | WRONG_DIRECTION | Rs 619 |
| v5_classic | POWERINDIA | LONG | 34,620.0→34,190.0 | Rs -430 | HELD_LOSER | Rs 560 |
| v5 | SBICARD | SHORT | 639.2→644.6 | Rs -216 | SHORTED_RISER | Rs 432 |
| v5 | HAVELLS | SHORT | 1,265.7→1,272.7 | Rs -210 | SHORTED_RISER | Rs 420 |
| v5 | SWIGGY | LONG | 280.6→276.8 | Rs -196 | WRONG_DIRECTION | Rs 393 |
| v5_classic | MPHASIS | SHORT | 2,396.0→2,409.1 | Rs -196 | SHORTED_RISER | Rs 393 |
| v5_classic | PNB | SHORT | 115.7→116.4 | Rs -183 | SHORTED_RISER | Rs 365 |
| v5 | ZYDUSLIFE | SHORT | 1,100.4→1,114.2 | Rs -179 | SHORTED_RISER | Rs 359 |
| v5 | ALKEM | SHORT | 5,354.5→5,384.0 | Rs -177 | SHORTED_RISER | Rs 354 |
| v5_classic | MAZDOCK | SHORT | 2,553.7→2,571.0 | Rs -173 | SHORTED_RISER | Rs 346 |
| v5 | DIXON | LONG | 14,803.0→14,637.0 | Rs -166 | WRONG_DIRECTION | Rs 332 |
| v5_classic | BRITANNIA | SHORT | 5,376.5→5,403.5 | Rs -135 | SHORTED_RISER | Rs 270 |
| v5_classic | PERSISTENT | SHORT | 5,620.0→5,653.5 | Rs -134 | SHORTED_RISER | Rs 268 |
| v5_classic | SBICARD | SHORT | 639.5→644.6 | Rs -134 | SHORTED_RISER | Rs 268 |
