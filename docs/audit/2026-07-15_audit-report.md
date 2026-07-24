# Trade Audit & Bear-Day Solution — 2026-07-15

*Regime: **SIDEWAYS*** — generated 15:35:26

## Bottom line

- **Realized P&L today: Rs 4,954** across 105 trades (47 long / 58 short)
- **Rs left on the table: Rs 20,080** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,793**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 10,359**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 49 | 19/30 | 28 | Rs 2,267 | Rs 8,131 |
| v5_classic | 56 | 28/28 | 35 | Rs 2,687 | Rs 11,949 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| EXIT_TOO_EARLY | 20 | Rs 2,917 | Rs 7,781 |
| WRONG_DIRECTION | 25 | Rs -2,279 | Rs 4,557 |
| SHORTED_RISER | 15 | Rs -2,119 | Rs 4,236 |
| GOOD_TRADE | 43 | Rs 6,469 | Rs 3,341 |
| IGNORED_SIGNAL | 2 | Rs -35 | Rs 165 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| PATANJALI | AVOID | -14.64% | Rs 4,392 |
| ADANIPOWER | AVOID | -3.18% | Rs 954 |
| ADANIGREEN | AVOID | -3.06% | Rs 918 |
| EMAMILTD | AVOID | -2.28% | Rs 684 |
| POLYCAB | AVOID | -2.18% | Rs 654 |
| DLF | AVOID | -2.04% | Rs 612 |
| POWERGRID | AVOID | -1.9% | Rs 570 |
| HINDALCO | AVOID | -1.9% | Rs 570 |
| LT | AVOID | -1.68% | Rs 504 |
| 3MINDIA | AVOID | -1.67% | Rs 501 |

## Prescription — flip a bear day

2. **Short selection:** 15 shorts hit risers (Rs 4,236 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 10,359 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | PATANJALI | SHORT | 383.9→366.8 | Rs 1,303 | EXIT_TOO_EARLY | Rs 2,934 |
| v5_classic | PATANJALI | SHORT | 383.9→366.8 | Rs 1,080 | EXIT_TOO_EARLY | Rs 2,432 |
| v5 | ADANIENSOL | LONG | 1,695.9→1,671.5 | Rs -415 | WRONG_DIRECTION | Rs 830 |
| v5_classic | LODHA | SHORT | 1,147.2→1,161.0 | Rs -356 | SHORTED_RISER | Rs 712 |
| v5_classic | VMM | SHORT | 113.5→115.0 | Rs -300 | SHORTED_RISER | Rs 600 |
| v5_classic | LUPIN | SHORT | 2,469.2→2,487.6 | Rs -276 | SHORTED_RISER | Rs 552 |
| v5_classic | KALYANKJIL | LONG | 529.8→540.5 | Rs 484 | GOOD_TRADE | Rs 472 |
| v5_classic | TMCV | LONG | 428.9→423.2 | Rs -228 | WRONG_DIRECTION | Rs 456 |
| v5_classic | PAGEIND | SHORT | 40,285.0→40,500.0 | Rs -215 | SHORTED_RISER | Rs 430 |
| v5_classic | CGPOWER | LONG | 913.9→916.4 | Rs 51 | EXIT_TOO_EARLY | Rs 429 |
| v5_classic | PATANJALI | SHORT | 352.5→346.6 | Rs 129 | EXIT_TOO_EARLY | Rs 406 |
| v5 | VMM | SHORT | 113.5→115.0 | Rs -187 | SHORTED_RISER | Rs 374 |
| v5_classic | MARUTI | SHORT | 13,489.0→13,579.0 | Rs -180 | SHORTED_RISER | Rs 360 |
| v5_classic | GROWW | LONG | 209.2→211.6 | Rs 107 | EXIT_TOO_EARLY | Rs 352 |
| v5_classic | BHEL | SHORT | 403.9→406.6 | Rs -176 | SHORTED_RISER | Rs 351 |
