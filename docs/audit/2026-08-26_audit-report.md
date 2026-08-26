# Trade Audit & Bear-Day Solution — 2026-08-26

*Regime: **SIDEWAYS*** — generated 15:36:25

## Bottom line

- **Realized P&L today: Rs 3,055** across 49 trades (22 long / 27 short)
- **Rs left on the table: Rs 6,925** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 3,039**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,329**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 49 | 22/27 | 29 | Rs 3,055 | Rs 6,925 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| GOOD_TRADE | 22 | Rs 4,229 | Rs 2,463 |
| SHORTED_RISER | 9 | Rs -785 | Rs 1,570 |
| WRONG_DIRECTION | 10 | Rs -735 | Rs 1,469 |
| EXIT_TOO_EARLY | 7 | Rs 346 | Rs 1,169 |
| LOSS_OTHER | 1 | Rs 0 | Rs 254 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| VBL | AVOID | -3.82% | Rs 1,146 |
| JUBLFOOD | AVOID | -3.01% | Rs 903 |
| TATACOMM | AVOID | -2.98% | Rs 894 |
| INDUSTOWER | AVOID | -2.47% | Rs 741 |
| GODREJIND | AVOID | -2.39% | Rs 717 |
| POWERGRID | AVOID | -2.14% | Rs 642 |
| LICI | AVOID | -2.05% | Rs 615 |
| LT | AVOID | -1.96% | Rs 588 |
| NAUKRI | AVOID | -1.96% | Rs 588 |
| WELCORP | AVOID | -1.65% | Rs 495 |

## Prescription — flip a bear day

2. **Short selection:** 9 shorts hit risers (Rs 1,570 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,329 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | PREMIERENE | SHORT | 1,018.2→1,011.9 | Rs 120 | EXIT_TOO_EARLY | Rs 564 |
| v5 | KEI | SHORT | 5,532.1→5,576.2 | Rs -265 | SHORTED_RISER | Rs 529 |
| v5 | GROWW | LONG | 202.8→196.8 | Rs -260 | WRONG_DIRECTION | Rs 520 |
| v5 | LICHSGFIN | LONG | 501.8→518.0 | Rs 618 | GOOD_TRADE | Rs 338 |
| v5 | IDEA | SHORT | 15.1→15.2 | Rs -155 | SHORTED_RISER | Rs 310 |
| v5 | GMRAIRPORT | SHORT | 99.1→99.1 | Rs 0 | LOSS_OTHER | Rs 254 |
| v5 | SAIL | SHORT | 182.7→184.0 | Rs -119 | SHORTED_RISER | Rs 238 |
| v5 | HINDZINC | LONG | 616.3→626.5 | Rs 408 | GOOD_TRADE | Rs 220 |
| v5 | LGEINDIA | LONG | 1,668.1→1,689.0 | Rs 314 | GOOD_TRADE | Rs 210 |
| v5 | INDIANB | LONG | 897.2→888.0 | Rs -101 | WRONG_DIRECTION | Rs 202 |
| v5 | GROWW | SHORT | 195.8→196.9 | Rs -100 | SHORTED_RISER | Rs 200 |
| v5 | IDEA | LONG | 15.1→15.2 | Rs 219 | GOOD_TRADE | Rs 189 |
| v5 | UNIONBANK | LONG | 191.2→189.0 | Rs -86 | WRONG_DIRECTION | Rs 172 |
| v5 | BANKBARODA | LONG | 245.1→243.8 | Rs -85 | WRONG_DIRECTION | Rs 170 |
| v5 | MAXHEALTH | LONG | 1,000.4→1,007.6 | Rs 72 | EXIT_TOO_EARLY | Rs 162 |
