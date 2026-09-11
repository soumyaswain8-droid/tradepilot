# Trade Audit & Bear-Day Solution — 2026-09-11

*Regime: **BEAR*** — generated 15:36:26

## Bottom line

- **Realized P&L today: Rs -542** across 54 trades (16 long / 38 short)
- **Rs left on the table: Rs 5,142** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 3,499**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,404**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 54 | 16/38 | 23 | Rs -542 | Rs 5,142 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 22 | Rs -1,272 | Rs 2,544 |
| GOOD_TRADE | 12 | Rs 1,176 | Rs 1,056 |
| LONG_IN_BEAR | 5 | Rs -477 | Rs 955 |
| EXIT_TOO_EARLY | 11 | Rs 92 | Rs 322 |
| IGNORED_SIGNAL | 3 | Rs -11 | Rs 161 |
| HELD_LOSER | 1 | Rs -49 | Rs 104 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| WELCORP | AVOID | -3.61% | Rs 1,083 |
| JSWSTEEL | AVOID | -2.99% | Rs 897 |
| STAR | AVOID | -2.76% | Rs 828 |
| ZYDUSWELL | AVOID | -2.53% | Rs 759 |
| SADBHAV | AVOID | -2.36% | Rs 708 |
| GODFRYPHLP | AVOID | -2.28% | Rs 684 |
| OIL | AVOID | -2.1% | Rs 630 |
| RADICO | AVOID | -2.06% | Rs 618 |
| QUESS | AVOID | -2.0% | Rs 600 |
| VEDL | AVOID | -1.99% | Rs 597 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 5 longs in a bear regime cost Rs 955 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 22 shorts hit risers (Rs 2,544 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,404 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | IDEA | LONG | 15.1→14.9 | Rs -236 | LONG_IN_BEAR | Rs 473 |
| v5 | COCHINSHIP | SHORT | 1,444.0→1,408.3 | Rs 393 | GOOD_TRADE | Rs 399 |
| v5 | INDUSTOWER | LONG | 381.9→378.0 | Rs -198 | LONG_IN_BEAR | Rs 395 |
| v5 | MUTHOOTFIN | SHORT | 2,748.8→2,769.8 | Rs -168 | SHORTED_RISER | Rs 336 |
| v5 | NATIONALUM | SHORT | 355.9→358.0 | Rs -154 | SHORTED_RISER | Rs 308 |
| v5 | KALYANKJIL | SHORT | 592.0→595.6 | Rs -139 | SHORTED_RISER | Rs 277 |
| v5 | DRREDDY | LONG | 1,143.9→1,163.5 | Rs 294 | GOOD_TRADE | Rs 277 |
| v5 | DLF | SHORT | 632.8→636.5 | Rs -120 | SHORTED_RISER | Rs 240 |
| v5 | KEI | SHORT | 4,470.5→4,499.0 | Rs -114 | SHORTED_RISER | Rs 228 |
| v5 | BIOCON | SHORT | 385.2→387.9 | Rs -99 | SHORTED_RISER | Rs 198 |
| v5 | GROWW | SHORT | 192.8→193.9 | Rs -89 | SHORTED_RISER | Rs 178 |
| v5 | BSE | SHORT | 3,199.5→3,216.7 | Rs -86 | SHORTED_RISER | Rs 172 |
| v5 | YESBANK | LONG | 22.6→23.1 | Rs 121 | GOOD_TRADE | Rs 170 |
| v5 | CIPLA | SHORT | 1,349.5→1,356.5 | Rs -70 | SHORTED_RISER | Rs 140 |
| v5 | DIXON | SHORT | 13,107.0→13,173.0 | Rs -66 | SHORTED_RISER | Rs 132 |
