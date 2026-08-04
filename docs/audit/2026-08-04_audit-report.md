# Trade Audit & Bear-Day Solution — 2026-08-04

*Regime: **BULL*** — generated 15:35:40

## Bottom line

- **Realized P&L today: Rs -5,528** across 88 trades (88 long / 0 short)
- **Rs left on the table: Rs 17,729** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 16,026**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 11,016**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 53 | 53/0 | 19 | Rs -261 | Rs 4,713 |
| v5_classic | 35 | 35/0 | 4 | Rs -5,267 | Rs 13,016 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 65 | Rs -8,012 | Rs 16,026 |
| EXIT_TOO_EARLY | 13 | Rs 212 | Rs 866 |
| GOOD_TRADE | 10 | Rs 2,271 | Rs 837 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| LICI | AVOID | -8.68% | Rs 2,604 |
| SADBHAV | AVOID | -5.62% | Rs 1,686 |
| PRESTIGE | AVOID | -4.49% | Rs 1,347 |
| GRASIM | AVOID | -3.74% | Rs 1,122 |
| STAR | AVOID | -3.3% | Rs 990 |
| QUESS | AVOID | -2.86% | Rs 858 |
| FEDERALBNK | AVOID | -2.49% | Rs 747 |
| JYOTHYLAB | AVOID | -2.01% | Rs 603 |
| BPCL | AVOID | -1.8% | Rs 540 |
| ADANIPOWER | AVOID | -1.73% | Rs 519 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 11,016 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | GRASIM | LONG | 3,260.0→3,150.0 | Rs -1,210 | WRONG_DIRECTION | Rs 2,420 |
| v5_classic | DIVISLAB | LONG | 8,585.0→8,381.0 | Rs -1,020 | WRONG_DIRECTION | Rs 2,040 |
| v5_classic | MOTHERSON | LONG | 155.0→153.1 | Rs -460 | WRONG_DIRECTION | Rs 921 |
| v5 | SUPREMEIND | LONG | 3,564.0→3,508.0 | Rs -392 | WRONG_DIRECTION | Rs 784 |
| v5_classic | TCS | LONG | 2,473.7→2,440.5 | Rs -365 | WRONG_DIRECTION | Rs 730 |
| v5_classic | AXISBANK | LONG | 1,272.0→1,253.0 | Rs -361 | WRONG_DIRECTION | Rs 722 |
| v5_classic | FEDERALBNK | LONG | 371.7→360.0 | Rs -351 | WRONG_DIRECTION | Rs 702 |
| v5_classic | PHOENIXLTD | LONG | 1,955.0→1,917.9 | Rs -297 | WRONG_DIRECTION | Rs 594 |
| v5_classic | INFY | LONG | 1,180.0→1,163.4 | Rs -282 | WRONG_DIRECTION | Rs 564 |
| v5 | NESTLEIND | LONG | 1,532.3→1,466.2 | Rs -264 | WRONG_DIRECTION | Rs 529 |
| v5_classic | BAJAJ-AUTO | LONG | 11,856.0→11,646.0 | Rs -210 | WRONG_DIRECTION | Rs 420 |
| v5_classic | BOSCHLTD | LONG | 41,460.0→41,250.0 | Rs -210 | WRONG_DIRECTION | Rs 420 |
| v5_classic | NYKAA | LONG | 344.9→338.1 | Rs -190 | WRONG_DIRECTION | Rs 381 |
| v5_classic | SHREECEM | LONG | 27,000.0→26,820.0 | Rs -180 | WRONG_DIRECTION | Rs 360 |
| v5_classic | SWIGGY | LONG | 291.4→286.4 | Rs -172 | WRONG_DIRECTION | Rs 343 |
