# Trade Audit & Bear-Day Solution — 2026-08-07

*Regime: **BULL*** — generated 15:35:50

## Bottom line

- **Realized P&L today: Rs 1,413** across 160 trades (160 long / 0 short)
- **Rs left on the table: Rs 20,175** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 12,159**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 4,314**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 85 | 85/0 | 37 | Rs 97 | Rs 10,369 |
| v5_classic | 75 | 75/0 | 25 | Rs 1,316 | Rs 9,806 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 94 | Rs -6,080 | Rs 12,159 |
| GOOD_TRADE | 34 | Rs 6,927 | Rs 4,735 |
| EXIT_TOO_EARLY | 28 | Rs 651 | Rs 3,067 |
| IGNORED_SIGNAL | 3 | Rs -62 | Rs 188 |
| HELD_LOSER | 1 | Rs -23 | Rs 26 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| CHOLAFIN | AVOID | -3.8% | Rs 1,140 |
| AUBANK | AVOID | -1.89% | Rs 567 |
| PIDILITIND | AVOID | -1.54% | Rs 462 |
| QUESS | AVOID | -1.33% | Rs 399 |
| NAUKRI | AVOID | -1.19% | Rs 357 |
| OLECTRA | AVOID | -1.03% | Rs 309 |
| PHOENIXLTD | AVOID | -0.91% | Rs 273 |
| SHREECEM | AVOID | -0.9% | Rs 270 |
| LUPIN | AVOID | -0.9% | Rs 270 |
| DIVISLAB | AVOID | -0.89% | Rs 267 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 4,314 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | TATAINVEST | LONG | 703.0→693.2 | Rs -627 | WRONG_DIRECTION | Rs 1,254 |
| v5 | TATAINVEST | LONG | 703.0→693.8 | Rs -589 | WRONG_DIRECTION | Rs 1,178 |
| v5 | HCLTECH | LONG | 1,364.0→1,349.6 | Rs -346 | WRONG_DIRECTION | Rs 691 |
| v5_classic | HCLTECH | LONG | 1,363.9→1,349.6 | Rs -343 | WRONG_DIRECTION | Rs 686 |
| v5 | FORTIS | LONG | 942.8→930.5 | Rs -318 | WRONG_DIRECTION | Rs 637 |
| v5_classic | KALYANKJIL | LONG | 598.0→622.1 | Rs 1,811 | GOOD_TRADE | Rs 589 |
| v5_classic | MAZDOCK | LONG | 2,530.0→2,511.4 | Rs -279 | WRONG_DIRECTION | Rs 558 |
| v5 | AUROPHARMA | LONG | 1,615.8→1,633.8 | Rs 306 | GOOD_TRADE | Rs 486 |
| v5 | MOTHERSON | LONG | 166.1→167.9 | Rs 430 | GOOD_TRADE | Rs 463 |
| v5 | INDIANB | LONG | 877.5→886.3 | Rs 319 | GOOD_TRADE | Rs 457 |
| v5_classic | BANKBARODA | LONG | 251.0→249.3 | Rs -218 | WRONG_DIRECTION | Rs 436 |
| v5 | HINDALCO | LONG | 1,032.8→1,038.4 | Rs 105 | EXIT_TOO_EARLY | Rs 403 |
| v5_classic | ENRIN | LONG | 3,579.1→3,673.0 | Rs 563 | GOOD_TRADE | Rs 372 |
| v5_classic | MOTHERSON | LONG | 161.6→166.1 | Rs 448 | GOOD_TRADE | Rs 362 |
| v5_classic | PIDILITIND | LONG | 1,686.0→1,668.0 | Rs -180 | WRONG_DIRECTION | Rs 360 |
