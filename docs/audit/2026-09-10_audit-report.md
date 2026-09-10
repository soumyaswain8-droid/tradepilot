# Trade Audit & Bear-Day Solution — 2026-09-10

*Regime: **BEAR*** — generated 15:36:23

## Bottom line

- **Realized P&L today: Rs -1,299** across 39 trades (10 long / 29 short)
- **Rs left on the table: Rs 5,142** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 4,610**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,037**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 39 | 10/29 | 18 | Rs -1,299 | Rs 5,142 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LONG_IN_BEAR | 7 | Rs -1,350 | Rs 2,700 |
| SHORTED_RISER | 14 | Rs -955 | Rs 1,910 |
| GOOD_TRADE | 15 | Rs 980 | Rs 441 |
| EXIT_TOO_EARLY | 3 | Rs 26 | Rs 91 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| SADBHAV | AVOID | -2.89% | Rs 867 |
| GRSE | AVOID | -2.35% | Rs 705 |
| ADANIENSOL | AVOID | -2.21% | Rs 663 |
| GICRE | AVOID | -1.77% | Rs 531 |
| ATGL | AVOID | -1.57% | Rs 471 |
| MARICO | AVOID | -1.34% | Rs 402 |
| VEDL | AVOID | -1.27% | Rs 381 |
| HINDALCO | AVOID | -1.26% | Rs 378 |
| INDUSINDBK | AVOID | -1.07% | Rs 321 |
| LUPIN | AVOID | -1.06% | Rs 318 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 7 longs in a bear regime cost Rs 2,700 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 14 shorts hit risers (Rs 1,910 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,037 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ADANIENSOL | LONG | 1,439.4→1,413.8 | Rs -333 | LONG_IN_BEAR | Rs 666 |
| v5 | PAYTM | LONG | 1,751.0→1,727.6 | Rs -328 | LONG_IN_BEAR | Rs 655 |
| v5 | TECHM | LONG | 1,539.1→1,519.0 | Rs -201 | LONG_IN_BEAR | Rs 402 |
| v5 | TRENT | LONG | 2,841.4→2,812.8 | Rs -200 | LONG_IN_BEAR | Rs 400 |
| v5 | MANKIND | SHORT | 2,252.4→2,270.0 | Rs -176 | SHORTED_RISER | Rs 352 |
| v5 | LODHA | SHORT | 1,151.9→1,159.0 | Rs -163 | SHORTED_RISER | Rs 327 |
| v5 | WIPRO | LONG | 168.9→167.2 | Rs -131 | LONG_IN_BEAR | Rs 262 |
| v5 | ADANIENSOL | SHORT | 1,403.9→1,411.7 | Rs -109 | SHORTED_RISER | Rs 218 |
| v5 | TIINDIA | SHORT | 2,639.7→2,660.0 | Rs -102 | SHORTED_RISER | Rs 203 |
| v5 | TATAELXSI | LONG | 3,433.0→3,408.6 | Rs -98 | LONG_IN_BEAR | Rs 195 |
| v5 | ADANIPORTS | SHORT | 1,757.4→1,768.1 | Rs -86 | SHORTED_RISER | Rs 171 |
| v5 | AMBUJACEM | SHORT | 394.9→396.4 | Rs -86 | SHORTED_RISER | Rs 171 |
| v5 | BHEL | SHORT | 430.9→433.5 | Rs -74 | SHORTED_RISER | Rs 148 |
| v5 | M&M | SHORT | 3,104.0→3,120.2 | Rs -65 | SHORTED_RISER | Rs 130 |
| v5 | PERSISTENT | LONG | 5,495.0→5,465.0 | Rs -60 | LONG_IN_BEAR | Rs 120 |
