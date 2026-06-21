# Trade Audit & Bear-Day Solution — 2026-06-18

*Regime: **SIDEWAYS*** — generated 15:36:45

## Bottom line

- **Realized P&L today: Rs -1,689** across 108 trades (72 long / 36 short)
- **Rs left on the table: Rs 16,898** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 10,432**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,690**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 58 | 42/16 | 27 | Rs -221 | Rs 7,448 |
| v5_classic | 50 | 30/20 | 22 | Rs -1,467 | Rs 9,450 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 24 | Rs -2,638 | Rs 5,274 |
| WRONG_DIRECTION | 32 | Rs -2,578 | Rs 5,158 |
| EXIT_TOO_EARLY | 24 | Rs 680 | Rs 3,447 |
| GOOD_TRADE | 25 | Rs 2,924 | Rs 2,909 |
| HELD_LOSER | 2 | Rs -67 | Rs 84 |
| IGNORED_SIGNAL | 1 | Rs -10 | Rs 26 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| IDBI | AVOID | -6.35% | Rs 1,905 |
| TATATECH | AVOID | -2.57% | Rs 771 |
| LTF | AVOID | -2.46% | Rs 738 |
| VBL | AVOID | -2.3% | Rs 690 |
| COCHINSHIP | AVOID | -2.04% | Rs 612 |
| THERMAX | AVOID | -1.64% | Rs 492 |
| SWIGGY | AVOID | -1.35% | Rs 405 |
| LTTS | AVOID | -1.33% | Rs 399 |
| TATACONSUM | AVOID | -1.16% | Rs 348 |
| HAL | AVOID | -1.1% | Rs 330 |

## Prescription — flip a bear day

2. **Short selection:** 24 shorts hit risers (Rs 5,274 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,690 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | NYKAA | LONG | 280.9→284.6 | Rs 223 | EXIT_TOO_EARLY | Rs 1,190 |
| v5_classic | POWERINDIA | LONG | 35,950.0→35,460.0 | Rs -490 | WRONG_DIRECTION | Rs 980 |
| v5_classic | NYKAA | LONG | 280.9→284.6 | Rs 151 | EXIT_TOO_EARLY | Rs 806 |
| v5_classic | POWERINDIA | SHORT | 35,375.0→35,715.0 | Rs -340 | SHORTED_RISER | Rs 680 |
| v5 | ABB | SHORT | 7,096.0→7,192.5 | Rs -290 | SHORTED_RISER | Rs 579 |
| v5_classic | ABB | SHORT | 7,096.0→7,192.5 | Rs -290 | SHORTED_RISER | Rs 579 |
| v5 | BIOCON | SHORT | 411.9→414.9 | Rs -281 | SHORTED_RISER | Rs 561 |
| v5_classic | BIOCON | SHORT | 411.9→414.9 | Rs -281 | SHORTED_RISER | Rs 561 |
| v5_classic | BOSCHLTD | LONG | 40,390.0→40,110.0 | Rs -280 | WRONG_DIRECTION | Rs 560 |
| v5_classic | TRENT | LONG | 3,104.0→3,144.0 | Rs 400 | GOOD_TRADE | Rs 480 |
| v5_classic | 360ONE | LONG | 1,155.4→1,141.6 | Rs -235 | WRONG_DIRECTION | Rs 469 |
| v5 | MAXHEALTH | LONG | 1,042.2→1,070.0 | Rs 501 | GOOD_TRADE | Rs 461 |
| v5 | DABUR | SHORT | 429.0→431.6 | Rs -200 | SHORTED_RISER | Rs 400 |
| v5_classic | DABUR | SHORT | 429.0→431.6 | Rs -200 | SHORTED_RISER | Rs 400 |
| v5 | SRF | SHORT | 2,690.1→2,704.9 | Rs -178 | SHORTED_RISER | Rs 355 |
