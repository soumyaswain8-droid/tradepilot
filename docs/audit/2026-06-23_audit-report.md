# Trade Audit & Bear-Day Solution — 2026-06-23

*Regime: **SIDEWAYS*** — generated 15:36:56

## Bottom line

- **Realized P&L today: Rs 6,797** across 100 trades (32 long / 68 short)
- **Rs left on the table: Rs 9,076** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 4,389**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 10,962**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 50 | 17/33 | 29 | Rs 3,450 | Rs 5,139 |
| v5_classic | 50 | 15/35 | 26 | Rs 3,347 | Rs 3,937 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| GOOD_TRADE | 46 | Rs 8,969 | Rs 3,773 |
| WRONG_DIRECTION | 23 | Rs -1,793 | Rs 3,585 |
| SHORTED_RISER | 21 | Rs -400 | Rs 804 |
| EXIT_TOO_EARLY | 9 | Rs 167 | Rs 604 |
| IGNORED_SIGNAL | 1 | Rs -145 | Rs 310 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| NATIONALUM | AVOID | -5.97% | Rs 1,791 |
| ECLERX | AVOID | -4.5% | Rs 1,350 |
| ASHOKLEY | AVOID | -3.65% | Rs 1,095 |
| CANBK | AVOID | -3.3% | Rs 990 |
| SBICARD | AVOID | -3.28% | Rs 984 |
| INDUSTOWER | AVOID | -3.24% | Rs 972 |
| TCS | AVOID | -3.21% | Rs 963 |
| ADANIENT | AVOID | -3.16% | Rs 948 |
| WIPRO | AVOID | -3.16% | Rs 948 |
| AMBUJACEM | AVOID | -3.07% | Rs 921 |

## Prescription — flip a bear day

2. **Short selection:** 21 shorts hit risers (Rs 804 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 10,962 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ADANIGREEN | LONG | 1,549.7→1,529.0 | Rs -352 | WRONG_DIRECTION | Rs 704 |
| v5 | RECLTD | LONG | 368.2→363.2 | Rs -288 | WRONG_DIRECTION | Rs 576 |
| v5_classic | VEDL | SHORT | 287.4→283.9 | Rs 354 | GOOD_TRADE | Rs 490 |
| v5 | NATIONALUM | SHORT | 364.7→355.6 | Rs 824 | GOOD_TRADE | Rs 482 |
| v5_classic | NATIONALUM | SHORT | 364.7→355.6 | Rs 824 | GOOD_TRADE | Rs 482 |
| v5 | VEDL | SHORT | 287.4→283.8 | Rs 364 | GOOD_TRADE | Rs 480 |
| v5 | SUNPHARMA | LONG | 1,884.1→1,868.0 | Rs -145 | IGNORED_SIGNAL | Rs 310 |
| v5_classic | MANKIND | LONG | 2,579.6→2,558.0 | Rs -151 | WRONG_DIRECTION | Rs 302 |
| v5_classic | SRF | LONG | 2,757.7→2,727.9 | Rs -119 | WRONG_DIRECTION | Rs 238 |
| v5_classic | GVT&D | LONG | 5,583.5→5,467.5 | Rs -116 | WRONG_DIRECTION | Rs 232 |
| v5 | MAZDOCK | LONG | 2,556.0→2,503.0 | Rs -106 | WRONG_DIRECTION | Rs 212 |
| v5_classic | SUNPHARMA | LONG | 1,883.8→1,876.7 | Rs -99 | WRONG_DIRECTION | Rs 199 |
| v5 | UNIONBANK | SHORT | 175.6→175.2 | Rs 67 | EXIT_TOO_EARLY | Rs 191 |
| v5 | BHARATFORG | LONG | 2,076.0→2,136.0 | Rs 480 | GOOD_TRADE | Rs 180 |
| v5 | SRF | LONG | 2,757.7→2,727.9 | Rs -89 | WRONG_DIRECTION | Rs 179 |
