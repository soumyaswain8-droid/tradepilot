# Trade Audit & Bear-Day Solution — 2026-08-12

*Regime: **SIDEWAYS*** — generated 15:35:52

## Bottom line

- **Realized P&L today: Rs -4,109** across 109 trades (46 long / 63 short)
- **Rs left on the table: Rs 12,831** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 11,312**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,780**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 68 | 31/37 | 12 | Rs -2,817 | Rs 7,039 |
| v5_classic | 41 | 15/26 | 8 | Rs -1,292 | Rs 5,792 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 54 | Rs -3,215 | Rs 6,430 |
| WRONG_DIRECTION | 34 | Rs -2,442 | Rs 5,002 |
| EXIT_TOO_EARLY | 10 | Rs 279 | Rs 905 |
| GOOD_TRADE | 10 | Rs 1,269 | Rs 468 |
| LOSS_OTHER | 1 | Rs 0 | Rs 26 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| GODREJIND | AVOID | -4.23% | Rs 1,269 |
| NEWGEN | AVOID | -3.58% | Rs 1,074 |
| MAXHEALTH | AVOID | -3.12% | Rs 936 |
| TATAELXSI | AVOID | -2.19% | Rs 657 |
| KEC | AVOID | -1.99% | Rs 597 |
| JYOTHYLAB | AVOID | -1.85% | Rs 555 |
| NAUKRI | AVOID | -1.54% | Rs 462 |
| ADANIENSOL | AVOID | -1.42% | Rs 426 |
| MUTHOOTFIN | AVOID | -1.36% | Rs 408 |
| TMPV | AVOID | -1.32% | Rs 396 |

## Prescription — flip a bear day

2. **Short selection:** 54 shorts hit risers (Rs 6,430 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,780 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | VMM | LONG | 110.2→108.4 | Rs -629 | WRONG_DIRECTION | Rs 1,259 |
| v5 | IDEA | LONG | 13.5→13.3 | Rs -361 | WRONG_DIRECTION | Rs 722 |
| v5 | JIOFIN | SHORT | 250.2→253.2 | Rs -313 | SHORTED_RISER | Rs 626 |
| v5 | TATAINVEST | SHORT | 680.6→686.0 | Rs -300 | SHORTED_RISER | Rs 599 |
| v5_classic | PRESTIGE | SHORT | 1,560.0→1,574.7 | Rs -279 | SHORTED_RISER | Rs 559 |
| v5_classic | JIOFIN | SHORT | 250.2→253.2 | Rs -251 | SHORTED_RISER | Rs 502 |
| v5_classic | TATAINVEST | SHORT | 680.6→686.0 | Rs -209 | SHORTED_RISER | Rs 417 |
| v5 | PRESTIGE | SHORT | 1,560.4→1,574.7 | Rs -200 | SHORTED_RISER | Rs 400 |
| v5 | UPL | LONG | 573.5→568.9 | Rs -181 | WRONG_DIRECTION | Rs 363 |
| v5 | PNB | LONG | 118.9→118.1 | Rs -180 | WRONG_DIRECTION | Rs 361 |
| v5 | GMRAIRPORT | SHORT | 103.5→103.2 | Rs 93 | EXIT_TOO_EARLY | Rs 341 |
| v5 | UNIONBANK | LONG | 187.3→185.7 | Rs -166 | WRONG_DIRECTION | Rs 333 |
| v5_classic | SHREECEM | SHORT | 25,300.0→25,450.0 | Rs -150 | SHORTED_RISER | Rs 300 |
| v5 | ATGL | SHORT | 659.1→662.5 | Rs -147 | SHORTED_RISER | Rs 295 |
| v5_classic | PAYTM | LONG | 1,603.2→1,610.0 | Rs 136 | EXIT_TOO_EARLY | Rs 274 |
