# Trade Audit & Bear-Day Solution — 2026-06-09

*Regime: **SIDEWAYS*** — generated 15:36:34

## Bottom line

- **Realized P&L today: Rs 11,709** across 188 trades (122 long / 66 short)
- **Rs left on the table: Rs 25,997** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 14,916**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,550**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v4 | 77 | 77/0 | 48 | Rs 6,246 | Rs 14,968 |
| v5 | 55 | 19/36 | 29 | Rs 1,793 | Rs 5,091 |
| v5_classic | 56 | 26/30 | 31 | Rs 3,670 | Rs 5,938 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 42 | Rs -5,556 | Rs 11,111 |
| GOOD_TRADE | 84 | Rs 18,365 | Rs 7,984 |
| SHORTED_RISER | 35 | Rs -1,902 | Rs 3,805 |
| EXIT_TOO_EARLY | 24 | Rs 841 | Rs 2,886 |
| LOSS_OTHER | 1 | Rs 0 | Rs 144 |
| IGNORED_SIGNAL | 2 | Rs -39 | Rs 67 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 389 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| ZEEL | AVOID | -3.12% | Rs 936 |
| ONGC | AVOID | -2.13% | Rs 639 |
| TITAN | AVOID | -2.09% | Rs 627 |
| NTPC | AVOID | -1.86% | Rs 558 |
| IDEA | AVOID | -1.81% | Rs 543 |
| NAUKRI | AVOID | -1.66% | Rs 498 |
| POWERGRID | AVOID | -1.58% | Rs 474 |
| INDUSTOWER | AVOID | -1.58% | Rs 474 |
| TATAPOWER | AVOID | -1.37% | Rs 411 |
| TECHM | AVOID | -1.3% | Rs 390 |

## Prescription — flip a bear day

2. **Short selection:** 35 shorts hit risers (Rs 3,805 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 389 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,550 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v4 | KALYANKJIL | LONG | 362.8→354.1 | Rs -675 | WRONG_DIRECTION | Rs 1,349 |
| v4 | MCX | LONG | 2,883.6→2,828.0 | Rs -500 | WRONG_DIRECTION | Rs 1,001 |
| v4 | PIIND | LONG | 2,851.2→2,786.0 | Rs -456 | WRONG_DIRECTION | Rs 913 |
| v4 | BSE | LONG | 4,024.4→3,968.0 | Rs -395 | WRONG_DIRECTION | Rs 790 |
| v4 | PIIND | LONG | 2,720.6→2,801.1 | Rs 805 | GOOD_TRADE | Rs 729 |
| v4 | BANKINDIA | LONG | 142.4→144.8 | Rs 478 | GOOD_TRADE | Rs 619 |
| v4 | TIINDIA | LONG | 3,142.2→3,105.9 | Rs -290 | WRONG_DIRECTION | Rs 581 |
| v4 | KEI | LONG | 5,215.5→5,161.0 | Rs -272 | WRONG_DIRECTION | Rs 545 |
| v4 | LAURUSLABS | LONG | 1,430.0→1,415.9 | Rs -254 | WRONG_DIRECTION | Rs 508 |
| v5_classic | GAIL | SHORT | 166.6→167.7 | Rs -227 | SHORTED_RISER | Rs 454 |
| v4 | KOTAKBANK | LONG | 381.9→378.4 | Rs -217 | WRONG_DIRECTION | Rs 433 |
| v4 | PRESTIGE | LONG | 1,352.9→1,341.2 | Rs -211 | WRONG_DIRECTION | Rs 421 |
| v4 | JUBLFOOD | LONG | 420.2→416.6 | Rs -205 | WRONG_DIRECTION | Rs 410 |
| v5_classic | TATACONSUM | SHORT | 1,100.8→1,108.4 | Rs -190 | SHORTED_RISER | Rs 380 |
| v4 | PHOENIXLTD | LONG | 1,759.9→1,747.7 | Rs -183 | WRONG_DIRECTION | Rs 366 |
