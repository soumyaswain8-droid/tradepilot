# Trade Audit & Bear-Day Solution — 2026-06-29

*Regime: **SIDEWAYS*** — generated 15:36:22

## Bottom line

- **Realized P&L today: Rs -683** across 117 trades (48 long / 69 short)
- **Rs left on the table: Rs 16,309** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 11,829**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 17,364**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 62 | 27/35 | 29 | Rs -1,101 | Rs 8,062 |
| v5_classic | 55 | 21/34 | 33 | Rs 418 | Rs 8,247 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 30 | Rs -4,727 | Rs 9,453 |
| GOOD_TRADE | 48 | Rs 5,203 | Rs 3,625 |
| SHORTED_RISER | 24 | Rs -1,188 | Rs 2,376 |
| EXIT_TOO_EARLY | 14 | Rs 101 | Rs 774 |
| HELD_LOSER | 1 | Rs -72 | Rs 81 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| PERSISTENT | AVOID | -11.22% | Rs 3,366 |
| ASTRAL | AVOID | -8.0% | Rs 2,400 |
| SUPREMEIND | AVOID | -6.66% | Rs 1,998 |
| LTTS | AVOID | -5.8% | Rs 1,740 |
| HINDPETRO | AVOID | -4.8% | Rs 1,440 |
| JKCEMENT | AVOID | -4.62% | Rs 1,386 |
| TATATECH | AVOID | -4.46% | Rs 1,338 |
| ECLERX | AVOID | -4.22% | Rs 1,266 |
| KPITTECH | AVOID | -4.09% | Rs 1,227 |
| KITEX | AVOID | -4.01% | Rs 1,203 |

## Prescription — flip a bear day

2. **Short selection:** 24 shorts hit risers (Rs 2,376 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 17,364 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ASHOKLEY | LONG | 161.2→156.8 | Rs -587 | WRONG_DIRECTION | Rs 1,174 |
| v5 | M&M | LONG | 3,197.9→3,136.3 | Rs -493 | WRONG_DIRECTION | Rs 986 |
| v5_classic | ASHOKLEY | LONG | 160.7→156.8 | Rs -387 | WRONG_DIRECTION | Rs 774 |
| v5_classic | M&MFIN | LONG | 328.6→323.7 | Rs -349 | WRONG_DIRECTION | Rs 698 |
| v5 | UNITDSPR | LONG | 1,387.0→1,352.7 | Rs -309 | WRONG_DIRECTION | Rs 617 |
| v5_classic | SUPREMEIND | SHORT | 3,329.0→3,252.1 | Rs 615 | GOOD_TRADE | Rs 609 |
| v5_classic | M&MFIN | SHORT | 321.7→314.9 | Rs 483 | GOOD_TRADE | Rs 596 |
| v5_classic | SIEMENS | LONG | 3,627.9→3,576.3 | Rs -258 | WRONG_DIRECTION | Rs 516 |
| v5 | M&MFIN | LONG | 328.6→323.7 | Rs -247 | WRONG_DIRECTION | Rs 495 |
| v5_classic | INDIGO | LONG | 5,450.0→5,376.2 | Rs -221 | WRONG_DIRECTION | Rs 443 |
| v5_classic | ASTRAL | SHORT | 1,389.3→1,401.2 | Rs -214 | SHORTED_RISER | Rs 428 |
| v5_classic | MARUTI | LONG | 13,820.0→13,628.0 | Rs -192 | WRONG_DIRECTION | Rs 384 |
| v5_classic | ADANIGREEN | SHORT | 1,486.0→1,493.7 | Rs -169 | SHORTED_RISER | Rs 339 |
| v5_classic | TVSMOTOR | LONG | 3,569.7→3,513.6 | Rs -168 | WRONG_DIRECTION | Rs 337 |
| v5_classic | MAXHEALTH | LONG | 1,132.5→1,146.2 | Rs 355 | GOOD_TRADE | Rs 334 |
