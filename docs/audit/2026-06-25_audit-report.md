# Trade Audit & Bear-Day Solution — 2026-06-25

*Regime: **SIDEWAYS*** — generated 15:35:45

## Bottom line

- **Realized P&L today: Rs 7,535** across 132 trades (70 long / 62 short)
- **Rs left on the table: Rs 24,041** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 11,626**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 9,675**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 74 | 45/29 | 41 | Rs 4,647 | Rs 12,043 |
| v5_classic | 58 | 25/33 | 37 | Rs 2,888 | Rs 11,998 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| GOOD_TRADE | 60 | Rs 13,388 | Rs 7,453 |
| SHORTED_RISER | 24 | Rs -3,688 | Rs 7,376 |
| WRONG_DIRECTION | 21 | Rs -2,124 | Rs 4,250 |
| EXIT_TOO_EARLY | 18 | Rs 683 | Rs 3,345 |
| IGNORED_SIGNAL | 8 | Rs -723 | Rs 1,545 |
| LOSS_OTHER | 1 | Rs 0 | Rs 72 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| NATIONALUM | AVOID | -4.71% | Rs 1,413 |
| SUPREMEIND | AVOID | -3.89% | Rs 1,167 |
| MUTHOOTFIN | AVOID | -3.33% | Rs 999 |
| KITEX | AVOID | -3.25% | Rs 975 |
| ASTRAL | AVOID | -3.24% | Rs 972 |
| MFSL | AVOID | -3.06% | Rs 918 |
| ONGC | AVOID | -2.87% | Rs 861 |
| JINDALSTEL | AVOID | -2.77% | Rs 831 |
| OIL | AVOID | -2.69% | Rs 807 |
| SOLARINDS | AVOID | -2.44% | Rs 732 |

## Prescription — flip a bear day

2. **Short selection:** 24 shorts hit risers (Rs 7,376 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 9,675 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | PAGEIND | LONG | 41,635.0→41,080.0 | Rs -555 | WRONG_DIRECTION | Rs 1,110 |
| v5 | HEROMOTOCO | SHORT | 4,897.2→4,970.4 | Rs -512 | SHORTED_RISER | Rs 1,025 |
| v5_classic | HEROMOTOCO | SHORT | 4,897.2→4,970.4 | Rs -512 | SHORTED_RISER | Rs 1,025 |
| v5 | MOTHERSON | LONG | 148.0→149.0 | Rs 111 | EXIT_TOO_EARLY | Rs 679 |
| v5 | NATIONALUM | SHORT | 348.6→340.4 | Rs 603 | GOOD_TRADE | Rs 666 |
| v5_classic | NATIONALUM | SHORT | 348.6→340.4 | Rs 530 | GOOD_TRADE | Rs 585 |
| v5_classic | LTF | LONG | 305.9→302.3 | Rs -281 | WRONG_DIRECTION | Rs 562 |
| v5_classic | M&MFIN | LONG | 320.2→321.7 | Rs 86 | EXIT_TOO_EARLY | Rs 527 |
| v5 | POWERGRID | SHORT | 286.6→289.1 | Rs -252 | SHORTED_RISER | Rs 505 |
| v5 | LTF | LONG | 305.9→302.4 | Rs -248 | WRONG_DIRECTION | Rs 497 |
| v5 | BSE | SHORT | 3,886.6→3,921.9 | Rs -247 | SHORTED_RISER | Rs 494 |
| v5_classic | BSE | SHORT | 3,886.6→3,921.9 | Rs -247 | SHORTED_RISER | Rs 494 |
| v5_classic | M&MFIN | LONG | 310.9→321.8 | Rs 569 | GOOD_TRADE | Rs 476 |
| v5 | ASHOKLEY | LONG | 152.7→157.3 | Rs 434 | GOOD_TRADE | Rs 465 |
| v5 | M&MFIN | LONG | 320.2→322.4 | Rs 115 | EXIT_TOO_EARLY | Rs 434 |
