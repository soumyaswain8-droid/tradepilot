# Trade Audit & Bear-Day Solution — 2026-08-13

*Regime: **SIDEWAYS*** — generated 15:35:44

## Bottom line

- **Realized P&L today: Rs -619** across 94 trades (40 long / 54 short)
- **Rs left on the table: Rs 10,404** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,379**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,244**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 48 | 24/24 | 19 | Rs -666 | Rs 5,342 |
| v5_classic | 46 | 16/30 | 14 | Rs 47 | Rs 5,062 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 24 | Rs -2,433 | Rs 4,868 |
| SHORTED_RISER | 35 | Rs -1,757 | Rs 3,511 |
| GOOD_TRADE | 27 | Rs 3,430 | Rs 1,212 |
| EXIT_TOO_EARLY | 6 | Rs 174 | Rs 723 |
| HELD_LOSER | 1 | Rs -26 | Rs 58 |
| IGNORED_SIGNAL | 1 | Rs -7 | Rs 32 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| HINDALCO | AVOID | -2.99% | Rs 897 |
| GICRE | AVOID | -2.15% | Rs 645 |
| ARVIND | AVOID | -1.98% | Rs 594 |
| GODFRYPHLP | AVOID | -1.77% | Rs 531 |
| ICICIBANK | AVOID | -1.74% | Rs 522 |
| VEDL | AVOID | -1.7% | Rs 510 |
| LUPIN | AVOID | -1.35% | Rs 405 |
| UNITDSPR | AVOID | -1.3% | Rs 390 |
| SHREECEM | AVOID | -1.27% | Rs 381 |
| FEDERALBNK | AVOID | -1.23% | Rs 369 |

## Prescription — flip a bear day

2. **Short selection:** 35 shorts hit risers (Rs 3,511 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,244 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ASTRAL | LONG | 1,579.2→1,557.0 | Rs -377 | WRONG_DIRECTION | Rs 755 |
| v5_classic | UNITDSPR | LONG | 1,536.0→1,515.0 | Rs -315 | WRONG_DIRECTION | Rs 630 |
| v5_classic | BHARTIARTL | SHORT | 1,933.3→1,958.2 | Rs -274 | SHORTED_RISER | Rs 548 |
| v5 | HINDZINC | LONG | 593.4→587.2 | Rs -223 | WRONG_DIRECTION | Rs 446 |
| v5_classic | PAGEIND | SHORT | 37,450.0→37,655.0 | Rs -205 | SHORTED_RISER | Rs 410 |
| v5 | KPITTECH | LONG | 617.5→612.4 | Rs -204 | WRONG_DIRECTION | Rs 408 |
| v5_classic | ASTRAL | LONG | 1,578.6→1,557.0 | Rs -194 | WRONG_DIRECTION | Rs 389 |
| v5_classic | NATIONALUM | SHORT | 408.4→410.8 | Rs -189 | SHORTED_RISER | Rs 377 |
| v5 | INDUSINDBK | SHORT | 1,009.5→1,014.7 | Rs -172 | SHORTED_RISER | Rs 343 |
| v5 | ASHOKLEY | LONG | 181.3→178.8 | Rs -136 | WRONG_DIRECTION | Rs 272 |
| v5_classic | INDUSINDBK | SHORT | 1,009.5→1,014.7 | Rs -130 | SHORTED_RISER | Rs 260 |
| v5 | RECLTD | SHORT | 342.8→345.0 | Rs -128 | SHORTED_RISER | Rs 256 |
| v5_classic | LICHSGFIN | LONG | 504.2→502.0 | Rs -119 | WRONG_DIRECTION | Rs 238 |
| v5 | BPCL | SHORT | 311.9→314.0 | Rs -109 | SHORTED_RISER | Rs 217 |
| v5_classic | ZYDUSLIFE | SHORT | 1,175.0→1,172.0 | Rs 75 | EXIT_TOO_EARLY | Rs 212 |
