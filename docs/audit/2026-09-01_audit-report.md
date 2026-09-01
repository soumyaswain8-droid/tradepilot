# Trade Audit & Bear-Day Solution — 2026-09-01

*Regime: **SIDEWAYS*** — generated 15:36:26

## Bottom line

- **Realized P&L today: Rs 893** across 70 trades (33 long / 37 short)
- **Rs left on the table: Rs 8,326** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 4,503**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 12,729**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 70 | 33/37 | 35 | Rs 893 | Rs 8,326 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 18 | Rs -1,148 | Rs 2,558 |
| SHORTED_RISER | 14 | Rs -1,103 | Rs 2,207 |
| EXIT_TOO_EARLY | 12 | Rs 249 | Rs 1,765 |
| GOOD_TRADE | 23 | Rs 2,986 | Rs 1,390 |
| HELD_LOSER | 2 | Rs -91 | Rs 373 |
| LOSS_OTHER | 1 | Rs 0 | Rs 33 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| KEI | AVOID | -6.83% | Rs 2,049 |
| SADBHAV | AVOID | -4.97% | Rs 1,491 |
| PAYTM | AVOID | -4.87% | Rs 1,461 |
| SHRIRAMFIN | AVOID | -4.58% | Rs 1,374 |
| PRESTIGE | AVOID | -3.86% | Rs 1,158 |
| MAXHEALTH | AVOID | -3.75% | Rs 1,125 |
| BHEL | AVOID | -3.64% | Rs 1,092 |
| INDUSTOWER | AVOID | -3.55% | Rs 1,065 |
| DIVISLAB | AVOID | -3.19% | Rs 957 |
| TVSMOTOR | AVOID | -3.19% | Rs 957 |

## Prescription — flip a bear day

2. **Short selection:** 14 shorts hit risers (Rs 2,207 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 12,729 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | HCLTECH | LONG | 1,343.2→1,328.5 | Rs -294 | WRONG_DIRECTION | Rs 588 |
| v5 | ABB | SHORT | 7,370.5→7,430.5 | Rs -240 | SHORTED_RISER | Rs 480 |
| v5 | PAYTM | SHORT | 1,657.7→1,668.8 | Rs -189 | SHORTED_RISER | Rs 377 |
| v5 | PRESTIGE | SHORT | 1,570.1→1,568.8 | Rs 21 | EXIT_TOO_EARLY | Rs 330 |
| v5 | IDEA | SHORT | 14.0→14.1 | Rs -158 | SHORTED_RISER | Rs 316 |
| v5 | M&M | LONG | 3,359.6→3,282.0 | Rs -155 | WRONG_DIRECTION | Rs 310 |
| v5 | HAVELLS | SHORT | 1,213.5→1,221.5 | Rs -152 | SHORTED_RISER | Rs 304 |
| v5 | NAUKRI | LONG | 1,346.9→1,354.3 | Rs 126 | EXIT_TOO_EARLY | Rs 296 |
| v5 | MARICO | LONG | 839.0→820.0 | Rs -133 | WRONG_DIRECTION | Rs 265 |
| v5 | KEI | SHORT | 5,480.0→5,513.0 | Rs -132 | SHORTED_RISER | Rs 264 |
| v5 | PERSISTENT | LONG | 5,765.0→5,765.0 | Rs 0 | WRONG_DIRECTION | Rs 262 |
| v5 | TATAELXSI | LONG | 3,622.2→3,623.0 | Rs 4 | EXIT_TOO_EARLY | Rs 244 |
| v5 | ASIANPAINT | SHORT | 2,585.2→2,568.0 | Rs 172 | GOOD_TRADE | Rs 228 |
| v5 | NATIONALUM | SHORT | 374.1→373.7 | Rs 20 | EXIT_TOO_EARLY | Rs 224 |
| v5 | HCLTECH | LONG | 1,355.5→1,351.4 | Rs -49 | HELD_LOSER | Rs 199 |
