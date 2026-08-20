# Trade Audit & Bear-Day Solution — 2026-08-20

*Regime: **SIDEWAYS*** — generated 15:35:56

## Bottom line

- **Realized P&L today: Rs -157** across 88 trades (56 long / 32 short)
- **Rs left on the table: Rs 13,957** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,493**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 3,495**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 49 | 34/15 | 24 | Rs 140 | Rs 7,367 |
| v5_classic | 39 | 22/17 | 19 | Rs -297 | Rs 6,590 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 16 | Rs -2,210 | Rs 4,421 |
| WRONG_DIRECTION | 20 | Rs -2,036 | Rs 4,072 |
| GOOD_TRADE | 32 | Rs 4,196 | Rs 2,318 |
| EXIT_TOO_EARLY | 11 | Rs 264 | Rs 1,892 |
| HELD_LOSER | 6 | Rs -273 | Rs 924 |
| IGNORED_SIGNAL | 3 | Rs -99 | Rs 330 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| PFC | AVOID | -2.84% | Rs 852 |
| BHEL | AVOID | -1.5% | Rs 450 |
| ATUL | AVOID | -1.3% | Rs 390 |
| NAUKRI | AVOID | -1.27% | Rs 381 |
| OLECTRA | AVOID | -1.1% | Rs 330 |
| LUPIN | AVOID | -1.06% | Rs 318 |
| HINDALCO | AVOID | -0.88% | Rs 264 |
| GRSE | AVOID | -0.78% | Rs 234 |
| TATAINVEST | AVOID | -0.54% | Rs 162 |
| HAL | AVOID | -0.38% | Rs 114 |

## Prescription — flip a bear day

2. **Short selection:** 16 shorts hit risers (Rs 4,421 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 3,495 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | HINDALCO | SHORT | 1,018.4→1,032.5 | Rs -465 | SHORTED_RISER | Rs 931 |
| v5_classic | HINDALCO | SHORT | 1,018.5→1,032.5 | Rs -462 | SHORTED_RISER | Rs 924 |
| v5_classic | SBICARD | LONG | 652.5→641.5 | Rs -374 | WRONG_DIRECTION | Rs 748 |
| v5 | LENSKART | LONG | 641.8→642.3 | Rs 20 | EXIT_TOO_EARLY | Rs 562 |
| v5 | OIL | SHORT | 466.3→469.8 | Rs -245 | SHORTED_RISER | Rs 490 |
| v5_classic | OIL | SHORT | 466.3→469.8 | Rs -245 | SHORTED_RISER | Rs 490 |
| v5 | ONGC | SHORT | 233.9→235.3 | Rs -217 | SHORTED_RISER | Rs 434 |
| v5_classic | ONGC | SHORT | 233.9→235.3 | Rs -217 | SHORTED_RISER | Rs 434 |
| v5_classic | AMBUJACEM | LONG | 412.4→408.4 | Rs -168 | WRONG_DIRECTION | Rs 336 |
| v5_classic | VEDL | LONG | 271.4→269.1 | Rs -166 | WRONG_DIRECTION | Rs 331 |
| v5_classic | DIXON | LONG | 14,576.0→14,623.0 | Rs 47 | EXIT_TOO_EARLY | Rs 330 |
| v5_classic | JINDALSTEL | LONG | 1,140.6→1,128.0 | Rs -164 | WRONG_DIRECTION | Rs 328 |
| v5 | SWIGGY | LONG | 280.6→279.0 | Rs -84 | HELD_LOSER | Rs 326 |
| v5_classic | SAIL | LONG | 176.4→174.2 | Rs -160 | WRONG_DIRECTION | Rs 320 |
| v5 | NAUKRI | LONG | 1,375.7→1,361.8 | Rs -153 | WRONG_DIRECTION | Rs 306 |
