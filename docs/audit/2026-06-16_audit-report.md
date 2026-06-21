# Trade Audit & Bear-Day Solution — 2026-06-16

*Regime: **SIDEWAYS*** — generated 15:35:47

## Bottom line

- **Realized P&L today: Rs -2,551** across 151 trades (93 long / 58 short)
- **Rs left on the table: Rs 23,692** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 16,724**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,283**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 85 | 56/29 | 37 | Rs -1,114 | Rs 11,565 |
| v5_classic | 66 | 37/29 | 20 | Rs -1,437 | Rs 12,127 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 43 | Rs -4,250 | Rs 8,498 |
| SHORTED_RISER | 43 | Rs -4,113 | Rs 8,226 |
| GOOD_TRADE | 35 | Rs 5,087 | Rs 3,370 |
| EXIT_TOO_EARLY | 22 | Rs 849 | Rs 3,175 |
| IGNORED_SIGNAL | 4 | Rs -52 | Rs 221 |
| HELD_LOSER | 4 | Rs -71 | Rs 202 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| NATIONALUM | AVOID | -4.11% | Rs 1,233 |
| IDEA | AVOID | -2.21% | Rs 663 |
| SOLARINDS | AVOID | -2.19% | Rs 657 |
| EXIDEIND | AVOID | -1.6% | Rs 480 |
| BLUEDART | AVOID | -1.43% | Rs 429 |
| KEI | AVOID | -1.36% | Rs 408 |
| ELGIEQUIP | AVOID | -1.23% | Rs 369 |
| HDFCLIFE | AVOID | -1.17% | Rs 351 |
| KALYANKJIL | AVOID | -1.16% | Rs 348 |
| PAYTM | AVOID | -1.15% | Rs 345 |

## Prescription — flip a bear day

2. **Short selection:** 43 shorts hit risers (Rs 8,226 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,283 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | SUZLON | LONG | 59.0→58.2 | Rs -354 | WRONG_DIRECTION | Rs 708 |
| v5 | TVSMOTOR | LONG | 3,473.6→3,418.5 | Rs -331 | WRONG_DIRECTION | Rs 661 |
| v5 | COCHINSHIP | SHORT | 1,411.8→1,422.7 | Rs -294 | SHORTED_RISER | Rs 589 |
| v5_classic | COCHINSHIP | SHORT | 1,411.8→1,422.7 | Rs -294 | SHORTED_RISER | Rs 589 |
| v5 | PERSISTENT | LONG | 5,004.5→4,953.0 | Rs -258 | WRONG_DIRECTION | Rs 515 |
| v5_classic | GROWW | LONG | 207.3→204.6 | Rs -258 | WRONG_DIRECTION | Rs 515 |
| v5_classic | COFORGE | LONG | 1,441.1→1,424.3 | Rs -235 | WRONG_DIRECTION | Rs 470 |
| v5 | SAIL | SHORT | 182.5→181.6 | Rs 164 | EXIT_TOO_EARLY | Rs 453 |
| v5_classic | SAIL | SHORT | 182.5→181.6 | Rs 164 | EXIT_TOO_EARLY | Rs 453 |
| v5 | GROWW | LONG | 207.3→204.6 | Rs -225 | WRONG_DIRECTION | Rs 449 |
| v5 | VEDL | SHORT | 302.5→301.6 | Rs 63 | EXIT_TOO_EARLY | Rs 448 |
| v5_classic | VEDL | SHORT | 302.5→301.6 | Rs 63 | EXIT_TOO_EARLY | Rs 448 |
| v5_classic | PREMIERENE | SHORT | 1,023.5→1,031.9 | Rs -218 | SHORTED_RISER | Rs 437 |
| v5 | PAYTM | SHORT | 1,101.1→1,111.3 | Rs -214 | SHORTED_RISER | Rs 428 |
| v5_classic | NATIONALUM | SHORT | 362.0→364.0 | Rs -210 | SHORTED_RISER | Rs 420 |
