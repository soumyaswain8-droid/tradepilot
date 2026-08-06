# Trade Audit & Bear-Day Solution — 2026-08-06

*Regime: **BULL*** — generated 15:35:39

## Bottom line

- **Realized P&L today: Rs 793** across 123 trades (123 long / 0 short)
- **Rs left on the table: Rs 18,222** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 11,691**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,475**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 63 | 63/0 | 33 | Rs 1,338 | Rs 10,067 |
| v5_classic | 60 | 60/0 | 23 | Rs -545 | Rs 8,155 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 65 | Rs -5,846 | Rs 11,691 |
| GOOD_TRADE | 39 | Rs 6,154 | Rs 3,241 |
| EXIT_TOO_EARLY | 17 | Rs 602 | Rs 2,913 |
| HELD_LOSER | 1 | Rs -25 | Rs 219 |
| IGNORED_SIGNAL | 1 | Rs -93 | Rs 158 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| NEWGEN | AVOID | -2.54% | Rs 762 |
| HEROMOTOCO | AVOID | -2.45% | Rs 735 |
| SHREECEM | AVOID | -2.43% | Rs 729 |
| TVSMOTOR | AVOID | -1.8% | Rs 540 |
| RADICO | AVOID | -1.76% | Rs 528 |
| JSWSTEEL | AVOID | -1.66% | Rs 498 |
| MPHASIS | AVOID | -1.55% | Rs 465 |
| LICI | AVOID | -1.39% | Rs 417 |
| PETRONET | AVOID | -1.37% | Rs 411 |
| POLICYBZR | AVOID | -1.3% | Rs 390 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,475 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | HINDALCO | LONG | 1,040.0→1,021.1 | Rs -490 | WRONG_DIRECTION | Rs 980 |
| v5 | SWIGGY | LONG | 300.8→294.8 | Rs -474 | WRONG_DIRECTION | Rs 948 |
| v5 | LODHA | LONG | 1,258.0→1,239.9 | Rs -380 | WRONG_DIRECTION | Rs 760 |
| v5 | TRENT | LONG | 3,180.0→3,070.0 | Rs -330 | WRONG_DIRECTION | Rs 660 |
| v5_classic | SAIL | LONG | 178.9→177.3 | Rs -326 | WRONG_DIRECTION | Rs 652 |
| v5_classic | NTPC | LONG | 349.9→345.8 | Rs -279 | WRONG_DIRECTION | Rs 558 |
| v5 | SAIL | LONG | 178.9→177.2 | Rs -257 | WRONG_DIRECTION | Rs 513 |
| v5 | SHRIRAMFIN | LONG | 1,149.0→1,134.0 | Rs -255 | WRONG_DIRECTION | Rs 510 |
| v5_classic | VEDL | LONG | 277.0→278.1 | Rs 130 | EXIT_TOO_EARLY | Rs 502 |
| v5 | MAZDOCK | LONG | 2,406.0→2,450.0 | Rs 176 | EXIT_TOO_EARLY | Rs 496 |
| v5_classic | SHRIRAMFIN | LONG | 1,122.4→1,141.3 | Rs 756 | GOOD_TRADE | Rs 496 |
| v5_classic | TRENT | LONG | 3,180.7→3,070.0 | Rs -221 | WRONG_DIRECTION | Rs 443 |
| v5_classic | HEROMOTOCO | LONG | 5,690.0→5,622.5 | Rs -202 | WRONG_DIRECTION | Rs 405 |
| v5 | APLAPOLLO | LONG | 1,988.5→1,962.5 | Rs -182 | WRONG_DIRECTION | Rs 364 |
| v5 | BDL | LONG | 1,255.4→1,263.5 | Rs 65 | EXIT_TOO_EARLY | Rs 361 |
