# Trade Audit & Bear-Day Solution — 2026-06-17

*Regime: **SIDEWAYS*** — generated 15:35:48

## Bottom line

- **Realized P&L today: Rs 1,694** across 110 trades (56 long / 54 short)
- **Rs left on the table: Rs 15,250** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,117**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,885**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 60 | 35/25 | 28 | Rs -474 | Rs 7,174 |
| v5_classic | 50 | 21/29 | 25 | Rs 2,168 | Rs 8,076 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 34 | Rs -2,563 | Rs 5,126 |
| GOOD_TRADE | 32 | Rs 5,239 | Rs 3,480 |
| EXIT_TOO_EARLY | 21 | Rs 543 | Rs 3,449 |
| WRONG_DIRECTION | 19 | Rs -1,496 | Rs 2,991 |
| IGNORED_SIGNAL | 2 | Rs -19 | Rs 146 |
| HELD_LOSER | 2 | Rs -12 | Rs 58 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| TMPV | AVOID | -8.3% | Rs 2,490 |
| FORTIS | AVOID | -2.01% | Rs 603 |
| ATUL | AVOID | -1.96% | Rs 588 |
| INDIACEM | AVOID | -1.81% | Rs 543 |
| CIPLA | AVOID | -1.63% | Rs 489 |
| ZYDUSLIFE | AVOID | -1.6% | Rs 480 |
| PIIND | AVOID | -1.49% | Rs 447 |
| DABUR | AVOID | -1.48% | Rs 444 |
| SUPREMEIND | AVOID | -1.38% | Rs 414 |
| ONGC | AVOID | -1.29% | Rs 387 |

## Prescription — flip a bear day

2. **Short selection:** 34 shorts hit risers (Rs 5,126 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,885 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | IDEA | SHORT | 14.6→14.8 | Rs -445 | SHORTED_RISER | Rs 889 |
| v5_classic | IDEA | SHORT | 14.6→14.8 | Rs -445 | SHORTED_RISER | Rs 889 |
| v5 | GVT&D | LONG | 5,045.0→5,057.0 | Rs 60 | EXIT_TOO_EARLY | Rs 595 |
| v5_classic | GVT&D | LONG | 5,045.0→5,057.0 | Rs 60 | EXIT_TOO_EARLY | Rs 595 |
| v5_classic | OBEROIRLTY | LONG | 1,704.8→1,675.0 | Rs -238 | WRONG_DIRECTION | Rs 477 |
| v5_classic | TMPV | SHORT | 388.0→367.2 | Rs 726 | GOOD_TRADE | Rs 429 |
| v5_classic | TRENT | LONG | 2,993.2→3,044.0 | Rs 305 | GOOD_TRADE | Rs 426 |
| v5 | VBL | LONG | 553.1→546.9 | Rs -206 | WRONG_DIRECTION | Rs 412 |
| v5 | TVSMOTOR | SHORT | 3,435.5→3,464.2 | Rs -201 | SHORTED_RISER | Rs 402 |
| v5_classic | TVSMOTOR | SHORT | 3,435.5→3,464.2 | Rs -201 | SHORTED_RISER | Rs 402 |
| v5_classic | PRESTIGE | LONG | 1,503.8→1,509.2 | Rs 97 | EXIT_TOO_EARLY | Rs 317 |
| v5 | ENRIN | LONG | 3,715.0→3,720.4 | Rs 22 | EXIT_TOO_EARLY | Rs 310 |
| v5 | UNITDSPR | SHORT | 1,290.7→1,300.3 | Rs -154 | SHORTED_RISER | Rs 307 |
| v5_classic | ONGC | LONG | 248.2→244.9 | Rs -152 | WRONG_DIRECTION | Rs 304 |
| v5 | EICHERMOT | SHORT | 7,560.5→7,522.0 | Rs 154 | GOOD_TRADE | Rs 278 |
