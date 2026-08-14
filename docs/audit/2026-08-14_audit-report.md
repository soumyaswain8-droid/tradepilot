# Trade Audit & Bear-Day Solution — 2026-08-14

*Regime: **SIDEWAYS*** — generated 15:35:24

## Bottom line

- **Realized P&L today: Rs -1,065** across 102 trades (49 long / 53 short)
- **Rs left on the table: Rs 10,412** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 10,412**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 59 | 32/27 | 19 | Rs -558 | Rs 5,058 |
| v5_classic | 43 | 17/26 | 6 | Rs -507 | Rs 5,354 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 22 | Rs -3,026 | Rs 6,054 |
| SHORTED_RISER | 17 | Rs -2,179 | Rs 4,358 |
| GOOD_TRADE | 25 | Rs 4,140 | Rs 0 |
| LOSS_OTHER | 38 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

2. **Short selection:** 17 shorts hit risers (Rs 4,358 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | NATIONALUM | SHORT | 379.4→382.9 | Rs -350 | SHORTED_RISER | Rs 700 |
| v5_classic | NATIONALUM | SHORT | 379.4→382.9 | Rs -350 | SHORTED_RISER | Rs 700 |
| v5_classic | JUBLFOOD | LONG | 517.8→507.3 | Rs -334 | WRONG_DIRECTION | Rs 669 |
| v5_classic | UNITDSPR | LONG | 1,536.0→1,515.0 | Rs -315 | WRONG_DIRECTION | Rs 630 |
| v5 | ETERNAL | LONG | 322.8→319.1 | Rs -296 | WRONG_DIRECTION | Rs 592 |
| v5 | JUBLFOOD | LONG | 517.8→506.9 | Rs -294 | WRONG_DIRECTION | Rs 589 |
| v5_classic | ETERNAL | LONG | 322.8→319.1 | Rs -285 | WRONG_DIRECTION | Rs 570 |
| v5 | GMRAIRPORT | SHORT | 102.1→103.3 | Rs -238 | SHORTED_RISER | Rs 476 |
| v5_classic | GMRAIRPORT | SHORT | 101.7→103.3 | Rs -217 | SHORTED_RISER | Rs 434 |
| v5 | TMPV | LONG | 348.3→336.1 | Rs -207 | WRONG_DIRECTION | Rs 413 |
| v5_classic | WIPRO | LONG | 185.7→183.9 | Rs -203 | WRONG_DIRECTION | Rs 406 |
| v5 | WIPRO | LONG | 185.8→183.9 | Rs -198 | WRONG_DIRECTION | Rs 396 |
| v5 | RADICO | SHORT | 4,585.3→4,612.2 | Rs -188 | SHORTED_RISER | Rs 377 |
| v5_classic | CONCOR | LONG | 541.7→532.0 | Rs -155 | WRONG_DIRECTION | Rs 310 |
| v5_classic | RADICO | SHORT | 4,587.5→4,612.2 | Rs -148 | SHORTED_RISER | Rs 296 |
