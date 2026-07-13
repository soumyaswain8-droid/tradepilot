# Trade Audit & Bear-Day Solution — 2026-07-13

*Regime: **BULL*** — generated 15:35:25

## Bottom line

- **Realized P&L today: Rs 6,044** across 141 trades (141 long / 0 short)
- **Rs left on the table: Rs 25,158** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 9,899**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 4,944**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 73 | 73/0 | 32 | Rs 3,425 | Rs 10,779 |
| v5_classic | 68 | 68/0 | 34 | Rs 2,620 | Rs 14,379 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 72 | Rs -4,949 | Rs 9,899 |
| EXIT_TOO_EARLY | 20 | Rs 2,285 | Rs 7,800 |
| GOOD_TRADE | 46 | Rs 8,777 | Rs 7,343 |
| IGNORED_SIGNAL | 3 | Rs -69 | Rs 116 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| THERMAX | AVOID | -3.03% | Rs 909 |
| GODREJIND | AVOID | -2.49% | Rs 747 |
| MUTHOOTFIN | AVOID | -2.27% | Rs 681 |
| BIOCON | AVOID | -1.8% | Rs 540 |
| IDEA | AVOID | -1.62% | Rs 486 |
| IREDA | AVOID | -1.26% | Rs 378 |
| CUMMINSIND | AVOID | -1.18% | Rs 354 |
| GALAXYSURF | AVOID | -0.97% | Rs 291 |
| BHARTIARTL | AVOID | -0.97% | Rs 291 |
| UNITDSPR | AVOID | -0.89% | Rs 267 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 4,944 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | KALYANKJIL | LONG | 476.1→492.4 | Rs 1,532 | EXIT_TOO_EARLY | Rs 3,708 |
| v5_classic | IREDA | LONG | 126.4→124.0 | Rs -537 | WRONG_DIRECTION | Rs 1,074 |
| v5 | PAYTM | LONG | 1,347.6→1,352.8 | Rs 104 | EXIT_TOO_EARLY | Rs 892 |
| v5 | OFSS | LONG | 11,865.0→11,704.0 | Rs -322 | WRONG_DIRECTION | Rs 644 |
| v5_classic | LTM | LONG | 4,190.3→4,137.1 | Rs -319 | WRONG_DIRECTION | Rs 638 |
| v5_classic | RVNL | LONG | 232.7→229.1 | Rs -312 | WRONG_DIRECTION | Rs 625 |
| v5_classic | KALYANKJIL | LONG | 443.6→480.2 | Rs 439 | GOOD_TRADE | Rs 620 |
| v5 | VOLTAS | LONG | 1,329.0→1,332.0 | Rs 81 | EXIT_TOO_EARLY | Rs 616 |
| v5 | LAURUSLABS | LONG | 1,549.7→1,537.2 | Rs -300 | WRONG_DIRECTION | Rs 600 |
| v5 | KALYANKJIL | LONG | 445.5→480.2 | Rs 382 | GOOD_TRADE | Rs 569 |
| v5 | KALYANKJIL | LONG | 496.2→513.5 | Rs 467 | GOOD_TRADE | Rs 497 |
| v5 | HCLTECH | LONG | 1,203.0→1,223.4 | Rs 714 | GOOD_TRADE | Rs 476 |
| v5_classic | KALYANKJIL | LONG | 520.2→511.4 | Rs -238 | WRONG_DIRECTION | Rs 475 |
| v5 | BLUESTARCO | LONG | 1,690.0→1,697.5 | Rs 135 | EXIT_TOO_EARLY | Rs 446 |
| v5_classic | GODREJPROP | LONG | 2,133.0→2,140.9 | Rs 118 | EXIT_TOO_EARLY | Rs 411 |
