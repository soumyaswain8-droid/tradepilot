# Trade Audit & Bear-Day Solution — 2026-07-17

*Regime: **SIDEWAYS*** — generated 15:36:21

## Bottom line

- **Realized P&L today: Rs -263** across 124 trades (53 long / 71 short)
- **Rs left on the table: Rs 12,594** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,190**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 9,546**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 64 | 29/35 | 30 | Rs 27 | Rs 3,921 |
| v5_classic | 60 | 24/36 | 22 | Rs -290 | Rs 8,673 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 26 | Rs -2,572 | Rs 5,143 |
| SHORTED_RISER | 39 | Rs -1,524 | Rs 3,047 |
| GOOD_TRADE | 30 | Rs 3,516 | Rs 2,495 |
| EXIT_TOO_EARLY | 22 | Rs 370 | Rs 1,459 |
| IGNORED_SIGNAL | 5 | Rs -53 | Rs 321 |
| LOSS_OTHER | 2 | Rs 0 | Rs 129 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| TORNTPHARM | AVOID | -4.5% | Rs 1,350 |
| NATIONALUM | AVOID | -4.1% | Rs 1,230 |
| POLYCAB | AVOID | -3.83% | Rs 1,149 |
| KEI | AVOID | -3.33% | Rs 999 |
| BHEL | AVOID | -3.08% | Rs 924 |
| PATANJALI | AVOID | -2.75% | Rs 825 |
| CUMMINSIND | AVOID | -2.58% | Rs 774 |
| MFSL | AVOID | -2.56% | Rs 768 |
| ALKEM | AVOID | -2.56% | Rs 768 |
| SUPREMEIND | AVOID | -2.53% | Rs 759 |

## Prescription — flip a bear day

2. **Short selection:** 39 shorts hit risers (Rs 3,047 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 9,546 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | EXIDEIND | LONG | 434.1→427.1 | Rs -364 | WRONG_DIRECTION | Rs 728 |
| v5_classic | HDFCLIFE | LONG | 575.8→569.1 | Rs -299 | WRONG_DIRECTION | Rs 598 |
| v5_classic | BHEL | LONG | 434.0→439.1 | Rs 352 | GOOD_TRADE | Rs 511 |
| v5_classic | DLF | LONG | 676.3→667.5 | Rs -239 | WRONG_DIRECTION | Rs 478 |
| v5_classic | UPL | LONG | 619.9→614.6 | Rs -220 | WRONG_DIRECTION | Rs 441 |
| v5_classic | WIPRO | LONG | 177.7→174.7 | Rs -208 | WRONG_DIRECTION | Rs 416 |
| v5_classic | BEL | SHORT | 407.1→409.4 | Rs -160 | SHORTED_RISER | Rs 320 |
| v5_classic | SUZLON | SHORT | 52.0→51.7 | Rs 213 | GOOD_TRADE | Rs 302 |
| v5_classic | SRF | LONG | 2,889.3→2,874.8 | Rs -116 | WRONG_DIRECTION | Rs 232 |
| v5_classic | BIOCON | LONG | 443.6→436.3 | Rs -109 | WRONG_DIRECTION | Rs 218 |
| v5_classic | EXIDEIND | LONG | 421.3→431.0 | Rs 369 | GOOD_TRADE | Rs 211 |
| v5_classic | POWERINDIA | SHORT | 32,180.0→32,110.0 | Rs 70 | EXIT_TOO_EARLY | Rs 210 |
| v5_classic | KPITTECH | SHORT | 548.2→551.5 | Rs -102 | SHORTED_RISER | Rs 205 |
| v5_classic | LODHA | LONG | 1,192.8→1,176.0 | Rs -101 | WRONG_DIRECTION | Rs 202 |
| v5 | UPL | LONG | 625.3→616.2 | Rs -100 | WRONG_DIRECTION | Rs 200 |
