# Trade Audit & Bear-Day Solution — 2026-07-31

*Regime: **SIDEWAYS*** — generated 15:35:29

## Bottom line

- **Realized P&L today: Rs 5,527** across 106 trades (47 long / 59 short)
- **Rs left on the table: Rs 14,710** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 6,948**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 8,340**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 53 | 25/28 | 29 | Rs 2,163 | Rs 6,702 |
| v5_classic | 53 | 22/31 | 31 | Rs 3,364 | Rs 8,008 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 29 | Rs -2,592 | Rs 5,183 |
| GOOD_TRADE | 40 | Rs 8,632 | Rs 4,150 |
| EXIT_TOO_EARLY | 20 | Rs 616 | Rs 2,821 |
| WRONG_DIRECTION | 12 | Rs -882 | Rs 1,765 |
| HELD_LOSER | 4 | Rs -146 | Rs 523 |
| IGNORED_SIGNAL | 1 | Rs -101 | Rs 268 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| SADBHAV | AVOID | -4.92% | Rs 1,476 |
| STAR | AVOID | -4.46% | Rs 1,338 |
| APLAPOLLO | AVOID | -3.89% | Rs 1,167 |
| LICHSGFIN | AVOID | -3.29% | Rs 987 |
| MAXHEALTH | AVOID | -2.34% | Rs 702 |
| VBL | AVOID | -2.01% | Rs 603 |
| JYOTHYLAB | AVOID | -1.95% | Rs 585 |
| BRITANNIA | AVOID | -1.95% | Rs 585 |
| SHREECEM | AVOID | -1.51% | Rs 453 |
| COFORGE | AVOID | -1.48% | Rs 444 |

## Prescription — flip a bear day

2. **Short selection:** 29 shorts hit risers (Rs 5,183 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 8,340 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | HYUNDAI | LONG | 2,018.2→2,103.9 | Rs 857 | GOOD_TRADE | Rs 1,041 |
| v5_classic | EXIDEIND | LONG | 452.7→449.1 | Rs -238 | WRONG_DIRECTION | Rs 476 |
| v5 | VEDL | SHORT | 264.5→266.3 | Rs -227 | SHORTED_RISER | Rs 454 |
| v5_classic | TVSMOTOR | LONG | 4,208.4→4,237.0 | Rs 143 | EXIT_TOO_EARLY | Rs 440 |
| v5 | ONGC | SHORT | 239.2→240.4 | Rs -207 | SHORTED_RISER | Rs 413 |
| v5_classic | LGEINDIA | SHORT | 1,499.6→1,508.8 | Rs -202 | SHORTED_RISER | Rs 405 |
| v5 | COLPAL | SHORT | 2,064.9→2,077.8 | Rs -181 | SHORTED_RISER | Rs 361 |
| v5_classic | UNITDSPR | LONG | 1,531.9→1,516.0 | Rs -175 | WRONG_DIRECTION | Rs 350 |
| v5 | VBL | SHORT | 446.6→445.6 | Rs 51 | EXIT_TOO_EARLY | Rs 331 |
| v5_classic | VEDL | SHORT | 264.5→266.3 | Rs -164 | SHORTED_RISER | Rs 328 |
| v5 | SWIGGY | SHORT | 286.5→285.7 | Rs 45 | EXIT_TOO_EARLY | Rs 301 |
| v5_classic | ONGC | SHORT | 239.2→240.4 | Rs -150 | SHORTED_RISER | Rs 299 |
| v5_classic | ADANIPORTS | SHORT | 1,664.1→1,672.8 | Rs -148 | SHORTED_RISER | Rs 296 |
| v5_classic | TMPV | LONG | 334.2→335.1 | Rs 35 | EXIT_TOO_EARLY | Rs 283 |
| v5_classic | AUROPHARMA | SHORT | 1,576.3→1,584.7 | Rs -134 | SHORTED_RISER | Rs 269 |
