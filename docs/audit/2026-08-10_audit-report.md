# Trade Audit & Bear-Day Solution — 2026-08-10

*Regime: **BULL*** — generated 15:35:30

## Bottom line

- **Realized P&L today: Rs 3,084** across 120 trades (120 long / 0 short)
- **Rs left on the table: Rs 15,856** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,268**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,218**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 57 | 57/0 | 26 | Rs 2,849 | Rs 5,375 |
| v5_classic | 63 | 63/0 | 35 | Rs 235 | Rs 10,481 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 59 | Rs -4,133 | Rs 8,268 |
| EXIT_TOO_EARLY | 22 | Rs 1,411 | Rs 4,121 |
| GOOD_TRADE | 39 | Rs 5,806 | Rs 3,467 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| BHARATFORG | AVOID | -7.6% | Rs 2,280 |
| ZYDUSWELL | AVOID | -3.32% | Rs 996 |
| LUPIN | AVOID | -2.69% | Rs 807 |
| CANBK | AVOID | -2.24% | Rs 672 |
| ARVIND | AVOID | -1.77% | Rs 531 |
| GODREJIND | AVOID | -1.47% | Rs 441 |
| PGEL | AVOID | -1.4% | Rs 420 |
| GICRE | AVOID | -1.23% | Rs 369 |
| OLECTRA | AVOID | -1.21% | Rs 363 |
| DRREDDY | AVOID | -1.13% | Rs 339 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,218 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | M&MFIN | LONG | 408.4→396.8 | Rs -1,083 | WRONG_DIRECTION | Rs 2,167 |
| v5_classic | PAYTM | LONG | 1,485.1→1,515.3 | Rs 544 | EXIT_TOO_EARLY | Rs 1,498 |
| v5_classic | RECLTD | LONG | 367.0→359.5 | Rs -668 | WRONG_DIRECTION | Rs 1,335 |
| v5 | PAYTM | LONG | 1,485.1→1,515.3 | Rs 302 | EXIT_TOO_EARLY | Rs 832 |
| v5 | PAYTM | LONG | 1,531.9→1,553.3 | Rs 278 | EXIT_TOO_EARLY | Rs 588 |
| v5 | ENRIN | LONG | 3,706.0→3,647.5 | Rs -234 | WRONG_DIRECTION | Rs 468 |
| v5_classic | HEROMOTOCO | LONG | 5,910.0→5,875.5 | Rs -207 | WRONG_DIRECTION | Rs 414 |
| v5_classic | BAJAJFINSV | LONG | 2,033.8→2,021.0 | Rs -192 | WRONG_DIRECTION | Rs 384 |
| v5 | POWERINDIA | LONG | 35,470.0→36,065.0 | Rs 595 | GOOD_TRADE | Rs 325 |
| v5_classic | POWERINDIA | LONG | 35,470.0→36,065.0 | Rs 595 | GOOD_TRADE | Rs 325 |
| v5_classic | PATANJALI | LONG | 357.5→353.8 | Rs -161 | WRONG_DIRECTION | Rs 322 |
| v5_classic | PAYTM | LONG | 1,530.6→1,553.3 | Rs 136 | GOOD_TRADE | Rs 271 |
| v5 | CANBK | LONG | 132.0→129.8 | Rs -133 | WRONG_DIRECTION | Rs 266 |
| v5_classic | LENSKART | LONG | 569.7→578.8 | Rs 172 | GOOD_TRADE | Rs 252 |
| v5_classic | SOLARINDS | LONG | 18,650.0→18,532.0 | Rs -118 | WRONG_DIRECTION | Rs 236 |
