# Trade Audit & Bear-Day Solution — 2026-08-17

*Regime: **SIDEWAYS*** — generated 15:35:43

## Bottom line

- **Realized P&L today: Rs -1,721** across 112 trades (58 long / 54 short)
- **Rs left on the table: Rs 13,639** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 9,769**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,961**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 61 | 34/27 | 26 | Rs -1,864 | Rs 7,829 |
| v5_classic | 51 | 24/27 | 25 | Rs 143 | Rs 5,810 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 24 | Rs -2,610 | Rs 5,220 |
| SHORTED_RISER | 31 | Rs -2,275 | Rs 4,549 |
| GOOD_TRADE | 32 | Rs 2,890 | Rs 1,821 |
| EXIT_TOO_EARLY | 19 | Rs 489 | Rs 1,695 |
| HELD_LOSER | 4 | Rs -121 | Rs 232 |
| IGNORED_SIGNAL | 2 | Rs -92 | Rs 122 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| ARVIND | AVOID | -3.42% | Rs 1,026 |
| SADBHAV | AVOID | -3.28% | Rs 984 |
| GODREJIND | AVOID | -2.36% | Rs 708 |
| TATAINVEST | AVOID | -1.91% | Rs 573 |
| ADANIENSOL | AVOID | -1.66% | Rs 498 |
| DMART | AVOID | -1.6% | Rs 480 |
| GAIL | AVOID | -1.6% | Rs 480 |
| PIDILITIND | AVOID | -1.42% | Rs 426 |
| PAYTM | AVOID | -1.42% | Rs 426 |
| BIOCON | AVOID | -1.2% | Rs 360 |

## Prescription — flip a bear day

2. **Short selection:** 31 shorts hit risers (Rs 4,549 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,961 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | LGEINDIA | LONG | 1,720.3→1,692.5 | Rs -473 | WRONG_DIRECTION | Rs 945 |
| v5 | VOLTAS | LONG | 1,336.8→1,307.0 | Rs -447 | WRONG_DIRECTION | Rs 894 |
| v5_classic | LICHSGFIN | LONG | 504.2→497.4 | Rs -367 | WRONG_DIRECTION | Rs 734 |
| v5 | IDEA | LONG | 14.1→13.9 | Rs -332 | WRONG_DIRECTION | Rs 664 |
| v5 | UNIONBANK | SHORT | 185.0→186.5 | Rs -259 | SHORTED_RISER | Rs 518 |
| v5_classic | UNIONBANK | SHORT | 185.0→186.5 | Rs -259 | SHORTED_RISER | Rs 518 |
| v5 | INFY | SHORT | 1,154.4→1,145.0 | Rs 235 | GOOD_TRADE | Rs 383 |
| v5_classic | SOLARINDS | LONG | 20,153.0→19,970.0 | Rs -183 | WRONG_DIRECTION | Rs 366 |
| v5_classic | BHEL | LONG | 423.0→427.1 | Rs 168 | EXIT_TOO_EARLY | Rs 363 |
| v5_classic | LODHA | SHORT | 1,227.6→1,235.2 | Rs -175 | SHORTED_RISER | Rs 350 |
| v5_classic | INFY | SHORT | 1,154.4→1,145.0 | Rs 207 | GOOD_TRADE | Rs 337 |
| v5 | ADANIGREEN | LONG | 1,339.1→1,323.6 | Rs -155 | WRONG_DIRECTION | Rs 310 |
| v5_classic | LAURUSLABS | LONG | 1,813.8→1,799.8 | Rs -154 | WRONG_DIRECTION | Rs 308 |
| v5 | LODHA | SHORT | 1,227.6→1,235.2 | Rs -152 | SHORTED_RISER | Rs 304 |
| v5 | TATAELXSI | SHORT | 3,722.2→3,750.0 | Rs -139 | SHORTED_RISER | Rs 278 |
