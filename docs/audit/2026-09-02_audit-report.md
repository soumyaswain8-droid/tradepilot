# Trade Audit & Bear-Day Solution — 2026-09-02

*Regime: **SIDEWAYS*** — generated 15:35:34

## Bottom line

- **Realized P&L today: Rs -829** across 44 trades (30 long / 14 short)
- **Rs left on the table: Rs 8,241** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 5,903**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,000**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 44 | 30/14 | 28 | Rs -829 | Rs 8,241 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 5 | Rs -1,750 | Rs 3,500 |
| SHORTED_RISER | 10 | Rs -1,202 | Rs 2,403 |
| EXIT_TOO_EARLY | 14 | Rs 394 | Rs 1,330 |
| GOOD_TRADE | 14 | Rs 1,835 | Rs 836 |
| HELD_LOSER | 1 | Rs -107 | Rs 172 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| KEI | AVOID | -3.33% | Rs 999 |
| HAVELLS | AVOID | -2.44% | Rs 732 |
| EXIDEIND | AVOID | -2.43% | Rs 729 |
| NEWGEN | AVOID | -2.4% | Rs 720 |
| KEC | AVOID | -2.21% | Rs 663 |
| ASIANPAINT | AVOID | -1.86% | Rs 558 |
| GRSE | AVOID | -1.39% | Rs 417 |
| TATACOMM | AVOID | -1.37% | Rs 411 |
| JYOTHYLAB | AVOID | -1.33% | Rs 399 |
| DRREDDY | AVOID | -1.24% | Rs 372 |

## Prescription — flip a bear day

2. **Short selection:** 10 shorts hit risers (Rs 2,403 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,000 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | BLUESTARCO | LONG | 1,483.8→1,442.7 | Rs -781 | WRONG_DIRECTION | Rs 1,562 |
| v5 | FORTIS | LONG | 916.5→904.4 | Rs -329 | WRONG_DIRECTION | Rs 659 |
| v5 | PERSISTENT | LONG | 5,766.0→5,660.5 | Rs -316 | WRONG_DIRECTION | Rs 633 |
| v5 | HCLTECH | LONG | 1,355.5→1,329.5 | Rs -312 | WRONG_DIRECTION | Rs 624 |
| v5 | ICICIAMC | SHORT | 2,951.0→2,970.2 | Rs -230 | SHORTED_RISER | Rs 461 |
| v5 | HINDPETRO | SHORT | 356.2→358.1 | Rs -179 | SHORTED_RISER | Rs 357 |
| v5 | TVSMOTOR | SHORT | 4,088.9→4,111.8 | Rs -160 | SHORTED_RISER | Rs 321 |
| v5 | IDEA | LONG | 14.4→14.5 | Rs 160 | GOOD_TRADE | Rs 303 |
| v5 | ASHOKLEY | SHORT | 165.4→166.3 | Rs -142 | SHORTED_RISER | Rs 284 |
| v5 | BLUESTARCO | SHORT | 1,447.7→1,456.9 | Rs -138 | SHORTED_RISER | Rs 276 |
| v5 | TATAPOWER | LONG | 358.4→359.4 | Rs 56 | EXIT_TOO_EARLY | Rs 258 |
| v5 | KALYANKJIL | SHORT | 557.4→560.3 | Rs -116 | SHORTED_RISER | Rs 232 |
| v5 | TMCV | SHORT | 446.6→448.1 | Rs -116 | SHORTED_RISER | Rs 232 |
| v5 | RELIANCE | LONG | 1,296.4→1,304.2 | Rs 94 | EXIT_TOO_EARLY | Rs 212 |
| v5 | HAVELLS | SHORT | 1,189.6→1,193.2 | Rs -86 | SHORTED_RISER | Rs 173 |
