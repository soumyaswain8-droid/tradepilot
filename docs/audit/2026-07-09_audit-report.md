# Trade Audit & Bear-Day Solution — 2026-07-09

*Regime: **BEAR*** — generated 15:35:19

## Bottom line

- **Realized P&L today: Rs -2,567** across 106 trades (43 long / 63 short)
- **Rs left on the table: Rs 15,089** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 11,714**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,680**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 54 | 25/29 | 23 | Rs -2,037 | Rs 8,088 |
| v5_classic | 52 | 18/34 | 26 | Rs -530 | Rs 7,001 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LONG_IN_BEAR | 23 | Rs -3,783 | Rs 7,567 |
| SHORTED_RISER | 32 | Rs -2,074 | Rs 4,147 |
| GOOD_TRADE | 28 | Rs 3,007 | Rs 1,649 |
| EXIT_TOO_EARLY | 21 | Rs 318 | Rs 1,611 |
| IGNORED_SIGNAL | 2 | Rs -35 | Rs 115 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| DRREDDY | AVOID | -5.89% | Rs 1,767 |
| SOLARINDS | AVOID | -3.29% | Rs 987 |
| MAZDOCK | AVOID | -3.18% | Rs 954 |
| ADANIENSOL | AVOID | -2.23% | Rs 669 |
| ATUL | AVOID | -1.96% | Rs 588 |
| UNITDSPR | AVOID | -1.96% | Rs 588 |
| PAGEIND | AVOID | -1.93% | Rs 579 |
| INFY | AVOID | -1.73% | Rs 519 |
| POLYCAB | AVOID | -1.73% | Rs 519 |
| OIL | AVOID | -1.7% | Rs 510 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 23 longs in a bear regime cost Rs 7,567 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 32 shorts hit risers (Rs 4,147 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,680 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | JUBLFOOD | LONG | 455.1→428.2 | Rs -1,235 | LONG_IN_BEAR | Rs 2,470 |
| v5 | CHOLAFIN | LONG | 1,855.9→1,769.4 | Rs -606 | LONG_IN_BEAR | Rs 1,211 |
| v5 | PERSISTENT | LONG | 4,887.4→4,761.0 | Rs -379 | LONG_IN_BEAR | Rs 758 |
| v5 | HDFCLIFE | LONG | 573.0→555.7 | Rs -329 | LONG_IN_BEAR | Rs 657 |
| v5 | HAVELLS | LONG | 1,226.0→1,207.8 | Rs -237 | LONG_IN_BEAR | Rs 473 |
| v5_classic | LODHA | LONG | 1,094.6→1,143.5 | Rs 293 | GOOD_TRADE | Rs 459 |
| v5_classic | SOLARINDS | SHORT | 17,189.0→17,399.0 | Rs -210 | SHORTED_RISER | Rs 420 |
| v5_classic | MOTILALOFS | LONG | 927.2→929.2 | Rs 42 | EXIT_TOO_EARLY | Rs 410 |
| v5_classic | TCS | SHORT | 2,039.9→2,055.3 | Rs -200 | SHORTED_RISER | Rs 400 |
| v5_classic | SOLARINDS | SHORT | 17,420.0→17,388.0 | Rs 32 | EXIT_TOO_EARLY | Rs 360 |
| v5_classic | MCX | LONG | 2,832.0→2,807.4 | Rs -172 | LONG_IN_BEAR | Rs 344 |
| v5_classic | BAJFINANCE | SHORT | 997.7→1,007.8 | Rs -172 | SHORTED_RISER | Rs 343 |
| v5 | LTM | LONG | 3,865.4→3,788.9 | Rs -153 | LONG_IN_BEAR | Rs 306 |
| v5_classic | NATIONALUM | SHORT | 344.6→346.8 | Rs -143 | SHORTED_RISER | Rs 286 |
| v5_classic | CHOLAFIN | SHORT | 1,757.7→1,772.0 | Rs -143 | SHORTED_RISER | Rs 286 |
