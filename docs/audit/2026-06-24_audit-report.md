# Trade Audit & Bear-Day Solution — 2026-06-24

*Regime: **SIDEWAYS*** — generated 15:35:24

## Bottom line

- **Realized P&L today: Rs -189** across 130 trades (60 long / 70 short)
- **Rs left on the table: Rs 14,512** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 14,512**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 70 | 32/38 | 19 | Rs -2,044 | Rs 8,600 |
| v5_classic | 60 | 28/32 | 32 | Rs 1,855 | Rs 5,912 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 36 | Rs -4,567 | Rs 9,133 |
| WRONG_DIRECTION | 19 | Rs -2,689 | Rs 5,379 |
| GOOD_TRADE | 51 | Rs 7,067 | Rs 0 |
| LOSS_OTHER | 24 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

2. **Short selection:** 36 shorts hit risers (Rs 9,133 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | LAURUSLABS | LONG | 1,481.0→1,454.1 | Rs -484 | WRONG_DIRECTION | Rs 968 |
| v5_classic | ADANIENT | SHORT | 2,962.9→3,001.0 | Rs -457 | SHORTED_RISER | Rs 914 |
| v5 | BDL | LONG | 1,426.9→1,404.7 | Rs -422 | WRONG_DIRECTION | Rs 844 |
| v5 | ADANIENT | SHORT | 2,962.9→2,996.3 | Rs -401 | SHORTED_RISER | Rs 802 |
| v5_classic | LAURUSLABS | LONG | 1,481.0→1,460.9 | Rs -362 | WRONG_DIRECTION | Rs 724 |
| v5 | INFY | SHORT | 1,029.3→1,042.9 | Rs -326 | SHORTED_RISER | Rs 653 |
| v5_classic | INFY | SHORT | 1,029.3→1,041.9 | Rs -302 | SHORTED_RISER | Rs 605 |
| v5 | NAUKRI | SHORT | 1,001.9→1,013.3 | Rs -274 | SHORTED_RISER | Rs 547 |
| v5_classic | NATIONALUM | SHORT | 349.4→351.6 | Rs -194 | SHORTED_RISER | Rs 387 |
| v5 | JSWENERGY | SHORT | 568.9→572.0 | Rs -186 | SHORTED_RISER | Rs 372 |
| v5 | TCS | SHORT | 2,059.6→2,077.9 | Rs -183 | SHORTED_RISER | Rs 366 |
| v5 | SUNPHARMA | LONG | 1,884.1→1,864.0 | Rs -181 | WRONG_DIRECTION | Rs 362 |
| v5 | OFSS | LONG | 10,236.0→10,148.0 | Rs -176 | WRONG_DIRECTION | Rs 352 |
| v5_classic | JSWENERGY | SHORT | 568.9→571.9 | Rs -174 | SHORTED_RISER | Rs 348 |
| v5_classic | HDFCLIFE | SHORT | 587.4→591.7 | Rs -170 | SHORTED_RISER | Rs 339 |
