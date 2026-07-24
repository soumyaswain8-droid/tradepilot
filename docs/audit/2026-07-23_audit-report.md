# Trade Audit & Bear-Day Solution — 2026-07-23

*Regime: **BEAR*** — generated 15:35:44

## Bottom line

- **Realized P&L today: Rs 1,720** across 111 trades (26 long / 85 short)
- **Rs left on the table: Rs 12,193** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 7,555**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 11,721**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 53 | 8/45 | 27 | Rs 776 | Rs 4,228 |
| v5_classic | 58 | 18/40 | 29 | Rs 943 | Rs 7,965 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LONG_IN_BEAR | 20 | Rs -2,190 | Rs 4,378 |
| SHORTED_RISER | 35 | Rs -1,590 | Rs 3,177 |
| GOOD_TRADE | 39 | Rs 4,956 | Rs 2,544 |
| EXIT_TOO_EARLY | 17 | Rs 543 | Rs 2,094 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| SRF | AVOID | -8.53% | Rs 2,559 |
| INDUSINDBK | AVOID | -5.97% | Rs 1,791 |
| NEWGEN | AVOID | -4.57% | Rs 1,371 |
| ZYDUSWELL | AVOID | -3.66% | Rs 1,098 |
| PETRONET | AVOID | -3.65% | Rs 1,095 |
| ATGL | AVOID | -2.79% | Rs 837 |
| PIDILITIND | AVOID | -2.76% | Rs 828 |
| HINDPETRO | AVOID | -2.54% | Rs 762 |
| ADANIENSOL | AVOID | -2.35% | Rs 705 |
| ADANIPORTS | AVOID | -2.25% | Rs 675 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 20 longs in a bear regime cost Rs 4,378 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 35 shorts hit risers (Rs 3,177 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 11,721 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | IDEA | LONG | 13.5→13.3 | Rs -472 | LONG_IN_BEAR | Rs 945 |
| v5_classic | NESTLEIND | LONG | 1,493.6→1,473.0 | Rs -330 | LONG_IN_BEAR | Rs 659 |
| v5_classic | HINDPETRO | SHORT | 395.2→384.9 | Rs 756 | GOOD_TRADE | Rs 606 |
| v5_classic | M&MFIN | LONG | 378.1→365.6 | Rs -262 | LONG_IN_BEAR | Rs 525 |
| v5 | SRF | SHORT | 2,844.7→2,785.5 | Rs 178 | EXIT_TOO_EARLY | Rs 511 |
| v5_classic | ADANIENSOL | SHORT | 1,705.3→1,704.1 | Rs 16 | EXIT_TOO_EARLY | Rs 507 |
| v5_classic | ABCAPITAL | SHORT | 392.8→398.1 | Rs -180 | SHORTED_RISER | Rs 360 |
| v5_classic | ADANIPORTS | SHORT | 1,801.8→1,823.5 | Rs -174 | SHORTED_RISER | Rs 347 |
| v5_classic | RADICO | LONG | 4,147.5→4,094.0 | Rs -160 | LONG_IN_BEAR | Rs 321 |
| v5_classic | SWIGGY | SHORT | 263.9→265.4 | Rs -154 | SHORTED_RISER | Rs 307 |
| v5 | PNB | SHORT | 110.1→110.8 | Rs -146 | SHORTED_RISER | Rs 292 |
| v5 | AUBANK | SHORT | 974.9→970.1 | Rs 130 | EXIT_TOO_EARLY | Rs 273 |
| v5_classic | AUBANK | SHORT | 980.2→966.8 | Rs 523 | GOOD_TRADE | Rs 265 |
| v5_classic | AMBUJACEM | SHORT | 426.4→429.2 | Rs -132 | SHORTED_RISER | Rs 263 |
| v5_classic | IOC | SHORT | 142.0→139.8 | Rs 512 | GOOD_TRADE | Rs 234 |
