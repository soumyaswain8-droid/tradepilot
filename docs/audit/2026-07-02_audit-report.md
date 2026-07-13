# Trade Audit & Bear-Day Solution — 2026-07-02

*Regime: **SIDEWAYS*** — generated 15:35:36

## Bottom line

- **Realized P&L today: Rs 540** across 141 trades (71 long / 70 short)
- **Rs left on the table: Rs 20,569** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 11,661**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,212**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 79 | 41/38 | 37 | Rs 131 | Rs 10,961 |
| v5_classic | 62 | 30/32 | 28 | Rs 409 | Rs 9,608 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 45 | Rs -3,942 | Rs 7,884 |
| GOOD_TRADE | 44 | Rs 5,883 | Rs 5,537 |
| WRONG_DIRECTION | 25 | Rs -1,888 | Rs 3,777 |
| EXIT_TOO_EARLY | 21 | Rs 523 | Rs 3,084 |
| IGNORED_SIGNAL | 5 | Rs -36 | Rs 161 |
| LOSS_OTHER | 1 | Rs 0 | Rs 126 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| BANKBARODA | AVOID | -4.2% | Rs 1,260 |
| THERMAX | AVOID | -3.97% | Rs 1,191 |
| DMART | AVOID | -3.27% | Rs 981 |
| BHEL | AVOID | -2.9% | Rs 870 |
| ELGIEQUIP | AVOID | -1.96% | Rs 588 |
| CGPOWER | AVOID | -1.75% | Rs 525 |
| PAGEIND | AVOID | -1.66% | Rs 498 |
| GMRAIRPORT | AVOID | -1.53% | Rs 459 |
| CUMMINSIND | AVOID | -1.49% | Rs 447 |
| INDUSTOWER | AVOID | -1.31% | Rs 393 |

## Prescription — flip a bear day

2. **Short selection:** 45 shorts hit risers (Rs 7,884 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,212 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | TATAELXSI | SHORT | 3,587.8→3,694.0 | Rs -531 | SHORTED_RISER | Rs 1,062 |
| v5_classic | BOSCHLTD | LONG | 40,785.0→40,915.0 | Rs 130 | EXIT_TOO_EARLY | Rs 760 |
| v5 | LODHA | LONG | 988.2→992.2 | Rs 116 | EXIT_TOO_EARLY | Rs 648 |
| v5_classic | PRESTIGE | LONG | 1,625.3→1,648.7 | Rs 398 | GOOD_TRADE | Rs 575 |
| v5 | MCX | LONG | 3,021.0→2,977.1 | Rs -263 | WRONG_DIRECTION | Rs 527 |
| v5 | TATASTEEL | SHORT | 185.2→186.4 | Rs -232 | SHORTED_RISER | Rs 463 |
| v5_classic | ETERNAL | LONG | 279.7→281.9 | Rs 249 | GOOD_TRADE | Rs 458 |
| v5_classic | PHOENIXLTD | LONG | 2,018.5→1,990.8 | Rs -222 | WRONG_DIRECTION | Rs 443 |
| v5 | HINDPETRO | LONG | 404.0→400.8 | Rs -214 | WRONG_DIRECTION | Rs 429 |
| v5 | ETERNAL | LONG | 277.1→280.8 | Rs 304 | GOOD_TRADE | Rs 417 |
| v5 | BLUESTARCO | SHORT | 1,606.4→1,621.0 | Rs -204 | SHORTED_RISER | Rs 409 |
| v5_classic | TATASTEEL | SHORT | 185.2→186.3 | Rs -197 | SHORTED_RISER | Rs 395 |
| v5 | CGPOWER | SHORT | 959.6→967.0 | Rs -176 | SHORTED_RISER | Rs 353 |
| v5 | CUMMINSIND | SHORT | 5,581.5→5,624.0 | Rs -170 | SHORTED_RISER | Rs 340 |
| v5 | PAYTM | LONG | 1,187.2→1,207.5 | Rs 325 | GOOD_TRADE | Rs 323 |
