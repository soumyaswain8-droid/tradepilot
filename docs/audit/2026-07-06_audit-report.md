# Trade Audit & Bear-Day Solution — 2026-07-06

*Regime: **SIDEWAYS*** — generated 15:35:37

## Bottom line

- **Realized P&L today: Rs 2,943** across 111 trades (53 long / 58 short)
- **Rs left on the table: Rs 15,463** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 7,339**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,705**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 63 | 29/34 | 41 | Rs 1,711 | Rs 8,645 |
| v5_classic | 48 | 24/24 | 24 | Rs 1,232 | Rs 6,818 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 30 | Rs -2,541 | Rs 5,081 |
| GOOD_TRADE | 39 | Rs 5,676 | Rs 4,394 |
| EXIT_TOO_EARLY | 26 | Rs 938 | Rs 3,273 |
| WRONG_DIRECTION | 16 | Rs -1,129 | Rs 2,715 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| VBL | AVOID | -4.06% | Rs 1,218 |
| KOTAKBANK | AVOID | -3.89% | Rs 1,167 |
| SUZLON | AVOID | -2.46% | Rs 738 |
| BAJAJHLDNG | AVOID | -2.35% | Rs 705 |
| MAXHEALTH | AVOID | -1.81% | Rs 543 |
| TCS | AVOID | -1.71% | Rs 513 |
| AUROPHARMA | AVOID | -1.6% | Rs 480 |
| MOTILALOFS | AVOID | -1.59% | Rs 477 |
| ATUL | AVOID | -1.47% | Rs 441 |
| CONCOR | AVOID | -1.41% | Rs 423 |

## Prescription — flip a bear day

2. **Short selection:** 30 shorts hit risers (Rs 5,081 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,705 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | LODHA | LONG | 1,057.0→1,074.9 | Rs 448 | GOOD_TRADE | Rs 595 |
| v5 | ADANIENSOL | LONG | 1,645.3→1,624.2 | Rs -295 | WRONG_DIRECTION | Rs 591 |
| v5 | LODHA | LONG | 1,057.0→1,074.9 | Rs 430 | GOOD_TRADE | Rs 571 |
| v5 | TMCV | SHORT | 432.0→429.8 | Rs 147 | EXIT_TOO_EARLY | Rs 506 |
| v5_classic | TMCV | SHORT | 432.0→429.8 | Rs 147 | EXIT_TOO_EARLY | Rs 506 |
| v5 | BLUESTARCO | SHORT | 1,583.2→1,594.4 | Rs -235 | SHORTED_RISER | Rs 470 |
| v5_classic | BLUESTARCO | SHORT | 1,583.2→1,594.4 | Rs -235 | SHORTED_RISER | Rs 470 |
| v5 | HUDCO | SHORT | 212.2→214.4 | Rs -218 | SHORTED_RISER | Rs 436 |
| v5 | KEI | SHORT | 5,201.0→5,240.0 | Rs -195 | SHORTED_RISER | Rs 390 |
| v5 | FEDERALBNK | SHORT | 325.7→327.5 | Rs -167 | SHORTED_RISER | Rs 335 |
| v5_classic | FEDERALBNK | SHORT | 325.7→327.5 | Rs -167 | SHORTED_RISER | Rs 335 |
| v5_classic | LTF | LONG | 327.0→328.8 | Rs 76 | EXIT_TOO_EARLY | Rs 315 |
| v5_classic | MUTHOOTFIN | LONG | 3,075.2→3,116.5 | Rs 372 | GOOD_TRADE | Rs 284 |
| v5_classic | HUDCO | LONG | 215.6→214.3 | Rs -141 | WRONG_DIRECTION | Rs 281 |
| v5 | DMART | SHORT | 3,994.4→4,021.0 | Rs -133 | SHORTED_RISER | Rs 266 |
