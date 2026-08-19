# Trade Audit & Bear-Day Solution — 2026-08-19

*Regime: **SIDEWAYS*** — generated 15:35:47

## Bottom line

- **Realized P&L today: Rs -1,150** across 108 trades (45 long / 63 short)
- **Rs left on the table: Rs 12,333** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,381**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,154**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 58 | 25/33 | 25 | Rs -713 | Rs 6,596 |
| v5_classic | 50 | 20/30 | 20 | Rs -437 | Rs 5,737 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 23 | Rs -2,105 | Rs 4,212 |
| SHORTED_RISER | 35 | Rs -2,084 | Rs 4,169 |
| GOOD_TRADE | 35 | Rs 2,995 | Rs 2,351 |
| EXIT_TOO_EARLY | 10 | Rs 232 | Rs 964 |
| HELD_LOSER | 3 | Rs -126 | Rs 412 |
| IGNORED_SIGNAL | 2 | Rs -63 | Rs 225 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| CUMMINSIND | AVOID | -2.43% | Rs 729 |
| ARVIND | AVOID | -1.9% | Rs 570 |
| KEI | AVOID | -1.88% | Rs 564 |
| TATACOMM | AVOID | -1.76% | Rs 528 |
| VBL | AVOID | -1.7% | Rs 510 |
| NEWGEN | AVOID | -1.61% | Rs 483 |
| SHREECEM | AVOID | -1.56% | Rs 468 |
| ABCAPITAL | AVOID | -1.49% | Rs 447 |
| GRSE | AVOID | -1.45% | Rs 435 |
| OLECTRA | AVOID | -1.4% | Rs 420 |

## Prescription — flip a bear day

2. **Short selection:** 35 shorts hit risers (Rs 4,169 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,154 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | GROWW | LONG | 196.8→195.0 | Rs -248 | WRONG_DIRECTION | Rs 496 |
| v5 | TATASTEEL | SHORT | 182.8→183.9 | Rs -240 | SHORTED_RISER | Rs 481 |
| v5_classic | BHEL | SHORT | 415.0→417.4 | Rs -225 | SHORTED_RISER | Rs 451 |
| v5_classic | OIL | LONG | 483.8→479.9 | Rs -223 | WRONG_DIRECTION | Rs 447 |
| v5_classic | GVT&D | SHORT | 4,048.0→4,081.0 | Rs -198 | SHORTED_RISER | Rs 396 |
| v5 | GVT&D | SHORT | 4,048.0→4,080.7 | Rs -196 | SHORTED_RISER | Rs 392 |
| v5_classic | TATASTEEL | SHORT | 182.8→183.9 | Rs -183 | SHORTED_RISER | Rs 366 |
| v5 | POLICYBZR | LONG | 1,775.0→1,776.8 | Rs 29 | EXIT_TOO_EARLY | Rs 352 |
| v5_classic | NATIONALUM | LONG | 388.9→379.4 | Rs -173 | WRONG_DIRECTION | Rs 346 |
| v5 | BHEL | SHORT | 415.0→417.4 | Rs -172 | SHORTED_RISER | Rs 343 |
| v5 | ATGL | LONG | 664.5→675.3 | Rs 238 | GOOD_TRADE | Rs 277 |
| v5_classic | COCHINSHIP | LONG | 1,484.0→1,477.9 | Rs -134 | WRONG_DIRECTION | Rs 268 |
| v5 | VOLTAS | SHORT | 1,233.3→1,226.8 | Rs 176 | GOOD_TRADE | Rs 265 |
| v5_classic | VOLTAS | SHORT | 1,233.3→1,226.8 | Rs 176 | GOOD_TRADE | Rs 265 |
| v5 | LTM | LONG | 4,632.9→4,592.1 | Rs -122 | WRONG_DIRECTION | Rs 245 |
