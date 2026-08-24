# Trade Audit & Bear-Day Solution — 2026-08-24

*Regime: **SIDEWAYS*** — generated 15:36:24

## Bottom line

- **Realized P&L today: Rs 2,319** across 45 trades (23 long / 22 short)
- **Rs left on the table: Rs 4,857** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 1,798**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 4,800**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 45 | 23/22 | 25 | Rs 2,319 | Rs 4,857 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| GOOD_TRADE | 19 | Rs 3,268 | Rs 1,649 |
| WRONG_DIRECTION | 6 | Rs -574 | Rs 1,147 |
| EXIT_TOO_EARLY | 6 | Rs 130 | Rs 710 |
| SHORTED_RISER | 9 | Rs -326 | Rs 651 |
| HELD_LOSER | 3 | Rs -175 | Rs 618 |
| IGNORED_SIGNAL | 1 | Rs -4 | Rs 64 |
| LOSS_OTHER | 1 | Rs 0 | Rs 18 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| GODREJIND | AVOID | -3.7% | Rs 1,110 |
| HAL | AVOID | -1.88% | Rs 564 |
| ADANIPORTS | AVOID | -1.64% | Rs 492 |
| OLECTRA | AVOID | -1.58% | Rs 474 |
| AMBUJACEM | AVOID | -1.39% | Rs 417 |
| ATUL | AVOID | -1.3% | Rs 390 |
| BEL | AVOID | -1.21% | Rs 363 |
| DIVISLAB | AVOID | -1.17% | Rs 351 |
| SHREECEM | AVOID | -1.07% | Rs 321 |
| KEC | AVOID | -1.06% | Rs 318 |

## Prescription — flip a bear day

2. **Short selection:** 9 shorts hit risers (Rs 651 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 4,800 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | VEDL | LONG | 278.6→273.5 | Rs -360 | WRONG_DIRECTION | Rs 721 |
| v5 | RADICO | SHORT | 4,614.7→4,608.0 | Rs 47 | EXIT_TOO_EARLY | Rs 322 |
| v5 | LGEINDIA | LONG | 1,668.1→1,664.2 | Rs -59 | HELD_LOSER | Rs 282 |
| v5 | POWERGRID | LONG | 272.2→268.5 | Rs -133 | WRONG_DIRECTION | Rs 266 |
| v5 | BEL | SHORT | 411.8→408.2 | Rs 327 | GOOD_TRADE | Rs 248 |
| v5 | HINDZINC | LONG | 597.8→607.9 | Rs 374 | GOOD_TRADE | Rs 235 |
| v5 | HINDZINC | LONG | 609.5→604.0 | Rs -117 | HELD_LOSER | Rs 214 |
| v5 | MOTILALOFS | LONG | 994.1→1,004.0 | Rs 169 | GOOD_TRADE | Rs 186 |
| v5 | NATIONALUM | LONG | 397.4→402.4 | Rs 323 | GOOD_TRADE | Rs 163 |
| v5 | PAYTM | SHORT | 1,614.2→1,623.9 | Rs -78 | SHORTED_RISER | Rs 155 |
| v5 | MCX | LONG | 3,255.0→3,257.0 | Rs 8 | EXIT_TOO_EARLY | Rs 131 |
| v5 | BDL | LONG | 1,361.9→1,368.0 | Rs 128 | GOOD_TRADE | Rs 122 |
| v5 | SAIL | LONG | 179.7→179.6 | Rs -0 | HELD_LOSER | Rs 122 |
| v5 | VMM | LONG | 110.8→113.8 | Rs 217 | GOOD_TRADE | Rs 117 |
| v5 | PRESTIGE | LONG | 1,624.5→1,628.6 | Rs 37 | EXIT_TOO_EARLY | Rs 117 |
