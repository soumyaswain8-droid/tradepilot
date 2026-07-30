# Trade Audit & Bear-Day Solution — 2026-07-30

*Regime: **SIDEWAYS*** — generated 15:36:21

## Bottom line

- **Realized P&L today: Rs -1,329** across 115 trades (45 long / 70 short)
- **Rs left on the table: Rs 15,339** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 9,996**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 9,321**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 60 | 22/38 | 27 | Rs -426 | Rs 6,528 |
| v5_classic | 55 | 23/32 | 21 | Rs -903 | Rs 8,811 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 42 | Rs -3,033 | Rs 6,065 |
| WRONG_DIRECTION | 25 | Rs -1,965 | Rs 3,931 |
| EXIT_TOO_EARLY | 15 | Rs 822 | Rs 3,101 |
| GOOD_TRADE | 33 | Rs 2,848 | Rs 2,242 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| SADBHAV | AVOID | -4.98% | Rs 1,494 |
| PRESTIGE | AVOID | -4.67% | Rs 1,401 |
| COLPAL | AVOID | -3.77% | Rs 1,131 |
| TIINDIA | AVOID | -3.51% | Rs 1,053 |
| GLENMARK | AVOID | -3.16% | Rs 948 |
| WELCORP | AVOID | -2.47% | Rs 741 |
| ZYDUSWELL | AVOID | -2.32% | Rs 696 |
| GODREJPROP | AVOID | -2.09% | Rs 627 |
| ARVIND | AVOID | -2.07% | Rs 621 |
| HDFCLIFE | AVOID | -2.03% | Rs 609 |

## Prescription — flip a bear day

2. **Short selection:** 42 shorts hit risers (Rs 6,065 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 9,321 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | EXIDEIND | LONG | 429.9→433.9 | Rs 99 | EXIT_TOO_EARLY | Rs 689 |
| v5 | MAZDOCK | SHORT | 2,272.0→2,293.2 | Rs -339 | SHORTED_RISER | Rs 678 |
| v5_classic | MAZDOCK | SHORT | 2,272.0→2,293.2 | Rs -339 | SHORTED_RISER | Rs 678 |
| v5_classic | M&M | SHORT | 3,221.8→3,256.7 | Rs -314 | SHORTED_RISER | Rs 628 |
| v5_classic | EXIDEIND | LONG | 434.1→441.2 | Rs 214 | EXIT_TOO_EARLY | Rs 604 |
| v5_classic | RADICO | LONG | 4,473.0→4,409.1 | Rs -256 | WRONG_DIRECTION | Rs 511 |
| v5_classic | DMART | LONG | 3,934.0→3,886.1 | Rs -240 | WRONG_DIRECTION | Rs 479 |
| v5_classic | PHOENIXLTD | SHORT | 1,910.5→1,900.7 | Rs 167 | EXIT_TOO_EARLY | Rs 398 |
| v5 | M&M | LONG | 3,259.0→3,259.1 | Rs 0 | EXIT_TOO_EARLY | Rs 340 |
| v5_classic | TMCV | SHORT | 411.4→414.5 | Rs -167 | SHORTED_RISER | Rs 335 |
| v5 | MOTILALOFS | SHORT | 840.5→846.4 | Rs -161 | SHORTED_RISER | Rs 321 |
| v5_classic | PERSISTENT | LONG | 5,678.6→5,600.3 | Rs -157 | WRONG_DIRECTION | Rs 313 |
| v5 | IDFCFIRSTB | SHORT | 83.8→84.4 | Rs -151 | SHORTED_RISER | Rs 303 |
| v5 | KPITTECH | SHORT | 589.8→597.2 | Rs -134 | SHORTED_RISER | Rs 268 |
| v5_classic | IDFCFIRSTB | SHORT | 83.8→84.4 | Rs -134 | SHORTED_RISER | Rs 268 |
