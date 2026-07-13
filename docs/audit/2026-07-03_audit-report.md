# Trade Audit & Bear-Day Solution — 2026-07-03

*Regime: **SIDEWAYS*** — generated 15:35:25

## Bottom line

- **Realized P&L today: Rs 6,975** across 125 trades (53 long / 72 short)
- **Rs left on the table: Rs 18,174** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 7,715**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 9,342**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 65 | 30/35 | 37 | Rs 2,579 | Rs 8,201 |
| v5_classic | 60 | 23/37 | 36 | Rs 4,396 | Rs 9,973 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| GOOD_TRADE | 49 | Rs 10,704 | Rs 7,030 |
| SHORTED_RISER | 28 | Rs -2,141 | Rs 4,283 |
| WRONG_DIRECTION | 20 | Rs -1,715 | Rs 3,432 |
| EXIT_TOO_EARLY | 24 | Rs 355 | Rs 2,769 |
| IGNORED_SIGNAL | 2 | Rs -228 | Rs 506 |
| LOSS_OTHER | 2 | Rs 0 | Rs 154 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| THERMAX | AVOID | -6.29% | Rs 1,887 |
| BHEL | AVOID | -4.57% | Rs 1,371 |
| TIINDIA | AVOID | -3.71% | Rs 1,113 |
| BANKBARODA | AVOID | -3.09% | Rs 927 |
| JSWENERGY | AVOID | -2.68% | Rs 804 |
| ELGIEQUIP | AVOID | -2.6% | Rs 780 |
| ICICIPRULI | AVOID | -2.16% | Rs 648 |
| MARICO | AVOID | -2.04% | Rs 612 |
| RADICO | AVOID | -2.02% | Rs 606 |
| INDIANB | AVOID | -1.98% | Rs 594 |

## Prescription — flip a bear day

2. **Short selection:** 28 shorts hit risers (Rs 4,283 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 9,342 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | BHEL | SHORT | 401.9→393.9 | Rs 526 | GOOD_TRADE | Rs 705 |
| v5_classic | BHEL | SHORT | 401.9→393.9 | Rs 526 | GOOD_TRADE | Rs 705 |
| v5 | NESTLEIND | SHORT | 1,446.2→1,456.8 | Rs -276 | SHORTED_RISER | Rs 551 |
| v5 | ADANIGREEN | SHORT | 1,526.0→1,546.5 | Rs -266 | SHORTED_RISER | Rs 533 |
| v5_classic | MUTHOOTFIN | LONG | 3,075.2→3,054.9 | Rs -183 | IGNORED_SIGNAL | Rs 441 |
| v5_classic | LODHA | LONG | 1,047.8→1,038.5 | Rs -213 | WRONG_DIRECTION | Rs 426 |
| v5 | ABB | SHORT | 6,861.0→6,853.5 | Rs 30 | EXIT_TOO_EARLY | Rs 406 |
| v5_classic | ABB | SHORT | 6,861.0→6,853.5 | Rs 30 | EXIT_TOO_EARLY | Rs 406 |
| v5_classic | PERSISTENT | LONG | 4,580.6→4,686.7 | Rs 530 | GOOD_TRADE | Rs 396 |
| v5_classic | NESTLEIND | SHORT | 1,446.2→1,453.8 | Rs -198 | SHORTED_RISER | Rs 395 |
| v5 | PERSISTENT | LONG | 4,580.6→4,688.0 | Rs 537 | GOOD_TRADE | Rs 390 |
| v5_classic | HUDCO | LONG | 214.7→212.8 | Rs -194 | WRONG_DIRECTION | Rs 388 |
| v5_classic | POWERINDIA | SHORT | 31,485.0→30,785.0 | Rs 700 | GOOD_TRADE | Rs 385 |
| v5_classic | HCLTECH | LONG | 1,078.1→1,123.5 | Rs 454 | GOOD_TRADE | Rs 355 |
| v5 | TECHM | LONG | 1,421.3→1,422.0 | Rs 10 | EXIT_TOO_EARLY | Rs 322 |
