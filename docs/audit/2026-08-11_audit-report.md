# Trade Audit & Bear-Day Solution — 2026-08-11

*Regime: **BULL*** — generated 15:35:46

## Bottom line

- **Realized P&L today: Rs 2,822** across 137 trades (137 long / 0 short)
- **Rs left on the table: Rs 22,443** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 9,723**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,939**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 75 | 75/0 | 37 | Rs 268 | Rs 8,704 |
| v5_classic | 62 | 62/0 | 36 | Rs 2,554 | Rs 13,739 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 60 | Rs -4,862 | Rs 9,723 |
| GOOD_TRADE | 49 | Rs 6,907 | Rs 6,697 |
| EXIT_TOO_EARLY | 24 | Rs 1,138 | Rs 4,819 |
| IGNORED_SIGNAL | 3 | Rs -333 | Rs 1,158 |
| HELD_LOSER | 1 | Rs -28 | Rs 46 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| KEC | AVOID | -5.27% | Rs 1,581 |
| VEDL | AVOID | -3.05% | Rs 915 |
| JINDALSTEL | AVOID | -2.67% | Rs 801 |
| SHREECEM | AVOID | -2.26% | Rs 678 |
| ZYDUSWELL | AVOID | -1.94% | Rs 582 |
| VBL | AVOID | -1.91% | Rs 573 |
| HDFCAMC | AVOID | -1.76% | Rs 528 |
| BHEL | AVOID | -1.47% | Rs 441 |
| NEWGEN | AVOID | -1.44% | Rs 432 |
| PHOENIXLTD | AVOID | -1.36% | Rs 408 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,939 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | ZYDUSLIFE | LONG | 1,123.0→1,144.8 | Rs 698 | EXIT_TOO_EARLY | Rs 1,926 |
| v5 | OIL | LONG | 480.5→473.5 | Rs -574 | WRONG_DIRECTION | Rs 1,148 |
| v5_classic | OIL | LONG | 480.5→473.5 | Rs -574 | WRONG_DIRECTION | Rs 1,148 |
| v5 | POLICYBZR | LONG | 1,648.0→1,681.9 | Rs 508 | GOOD_TRADE | Rs 976 |
| v5 | EXIDEIND | LONG | 491.9→485.0 | Rs -469 | WRONG_DIRECTION | Rs 938 |
| v5_classic | PAYTM | LONG | 1,603.2→1,593.7 | Rs -190 | IGNORED_SIGNAL | Rs 924 |
| v5 | NAUKRI | LONG | 1,322.0→1,349.1 | Rs 596 | GOOD_TRADE | Rs 922 |
| v5_classic | NAUKRI | LONG | 1,322.0→1,349.1 | Rs 542 | GOOD_TRADE | Rs 838 |
| v5_classic | EXIDEIND | LONG | 491.9→486.9 | Rs -337 | WRONG_DIRECTION | Rs 673 |
| v5_classic | ZYDUSLIFE | LONG | 1,136.5→1,161.1 | Rs 344 | GOOD_TRADE | Rs 615 |
| v5_classic | POLICYBZR | LONG | 1,648.0→1,681.9 | Rs 305 | GOOD_TRADE | Rs 586 |
| v5_classic | BOSCHLTD | LONG | 45,180.0→45,200.0 | Rs 20 | EXIT_TOO_EARLY | Rs 550 |
| v5 | ZYDUSLIFE | LONG | 1,112.9→1,120.0 | Rs 43 | EXIT_TOO_EARLY | Rs 510 |
| v5 | BAJAJ-AUTO | LONG | 11,795.0→11,712.0 | Rs -249 | WRONG_DIRECTION | Rs 498 |
| v5_classic | BAJAJ-AUTO | LONG | 11,795.0→11,712.0 | Rs -249 | WRONG_DIRECTION | Rs 498 |
