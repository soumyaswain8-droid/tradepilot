# Trade Audit & Bear-Day Solution — 2026-06-19

*Regime: **BEAR*** — generated 15:36:30

## Bottom line

- **Realized P&L today: Rs 2,873** across 91 trades (23 long / 68 short)
- **Rs left on the table: Rs 9,914** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 5,030**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 8,592**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 48 | 12/36 | 25 | Rs 1,564 | Rs 4,331 |
| v5_classic | 43 | 11/32 | 19 | Rs 1,310 | Rs 5,583 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 38 | Rs -1,882 | Rs 3,762 |
| GOOD_TRADE | 29 | Rs 5,287 | Rs 3,119 |
| EXIT_TOO_EARLY | 15 | Rs 120 | Rs 1,730 |
| LONG_IN_BEAR | 8 | Rs -634 | Rs 1,268 |
| IGNORED_SIGNAL | 1 | Rs -19 | Rs 35 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| ICICIPRULI | AVOID | -4.18% | Rs 1,254 |
| KAYNES | AVOID | -3.91% | Rs 1,173 |
| TCS | AVOID | -3.55% | Rs 1,065 |
| BPCL | AVOID | -3.07% | Rs 921 |
| DLF | AVOID | -2.53% | Rs 759 |
| HINDPETRO | AVOID | -2.37% | Rs 711 |
| INDIACEM | AVOID | -2.31% | Rs 693 |
| PERSISTENT | AVOID | -2.26% | Rs 678 |
| LTTS | AVOID | -2.25% | Rs 675 |
| UNITDSPR | AVOID | -2.21% | Rs 663 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 8 longs in a bear regime cost Rs 1,268 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 38 shorts hit risers (Rs 3,762 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 8,592 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | TATACAP | LONG | 347.4→347.9 | Rs 9 | EXIT_TOO_EARLY | Rs 610 |
| v5_classic | SOLARINDS | LONG | 18,350.0→18,084.0 | Rs -266 | LONG_IN_BEAR | Rs 532 |
| v5 | PERSISTENT | SHORT | 4,940.5→4,690.0 | Rs 1,252 | GOOD_TRADE | Rs 440 |
| v5_classic | PERSISTENT | SHORT | 4,940.5→4,690.0 | Rs 1,252 | GOOD_TRADE | Rs 440 |
| v5_classic | TVSMOTOR | SHORT | 3,429.7→3,457.2 | Rs -165 | SHORTED_RISER | Rs 330 |
| v5_classic | GODREJPROP | SHORT | 1,786.1→1,796.7 | Rs -159 | SHORTED_RISER | Rs 318 |
| v5 | ASTRAL | SHORT | 1,535.5→1,544.5 | Rs -153 | SHORTED_RISER | Rs 306 |
| v5_classic | ASTRAL | SHORT | 1,535.5→1,544.5 | Rs -153 | SHORTED_RISER | Rs 306 |
| v5_classic | GLENMARK | LONG | 2,187.6→2,188.7 | Rs 10 | EXIT_TOO_EARLY | Rs 296 |
| v5_classic | TMPV | SHORT | 358.1→360.1 | Rs -139 | SHORTED_RISER | Rs 279 |
| v5_classic | ICICIAMC | SHORT | 3,351.8→3,396.9 | Rs -135 | SHORTED_RISER | Rs 271 |
| v5_classic | MCX | SHORT | 2,772.0→2,791.0 | Rs -133 | SHORTED_RISER | Rs 266 |
| v5_classic | ATGL | LONG | 724.4→732.1 | Rs 202 | GOOD_TRADE | Rs 265 |
| v5 | VEDL | LONG | 306.6→300.0 | Rs -131 | LONG_IN_BEAR | Rs 262 |
| v5_classic | INDHOTEL | LONG | 704.0→717.0 | Rs 288 | GOOD_TRADE | Rs 261 |
