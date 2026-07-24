# Trade Audit & Bear-Day Solution — 2026-07-16

*Regime: **SIDEWAYS*** — generated 15:35:58

## Bottom line

- **Realized P&L today: Rs -3,197** across 138 trades (69 long / 69 short)
- **Rs left on the table: Rs 20,985** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 15,013**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,506**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 75 | 38/37 | 33 | Rs -1,126 | Rs 10,935 |
| v5_classic | 63 | 31/32 | 25 | Rs -2,071 | Rs 10,050 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 36 | Rs -4,646 | Rs 9,294 |
| SHORTED_RISER | 35 | Rs -2,859 | Rs 5,719 |
| GOOD_TRADE | 39 | Rs 4,140 | Rs 3,315 |
| EXIT_TOO_EARLY | 19 | Rs 448 | Rs 2,064 |
| IGNORED_SIGNAL | 9 | Rs -280 | Rs 593 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| HDFCAMC | AVOID | -4.65% | Rs 1,395 |
| ICICIPRULI | AVOID | -3.1% | Rs 930 |
| GODREJIND | AVOID | -2.91% | Rs 873 |
| ETERNAL | AVOID | -2.83% | Rs 849 |
| PRESTIGE | AVOID | -2.63% | Rs 789 |
| UNIONBANK | AVOID | -2.09% | Rs 627 |
| NATIONALUM | AVOID | -1.95% | Rs 585 |
| INDIGOPNTS | AVOID | -1.81% | Rs 543 |
| INDHOTEL | AVOID | -1.58% | Rs 474 |
| DLF | AVOID | -1.47% | Rs 441 |

## Prescription — flip a bear day

2. **Short selection:** 35 shorts hit risers (Rs 5,719 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,506 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | POWERINDIA | LONG | 33,980.0→32,970.0 | Rs -1,010 | WRONG_DIRECTION | Rs 2,020 |
| v5_classic | HDFCAMC | LONG | 2,729.2→2,661.3 | Rs -611 | WRONG_DIRECTION | Rs 1,222 |
| v5 | SWIGGY | LONG | 267.0→273.1 | Rs 707 | GOOD_TRADE | Rs 1,190 |
| v5 | ETERNAL | LONG | 295.3→287.7 | Rs -524 | WRONG_DIRECTION | Rs 1,049 |
| v5 | GVT&D | LONG | 4,668.6→4,574.9 | Rs -468 | WRONG_DIRECTION | Rs 937 |
| v5 | SWIGGY | LONG | 280.6→276.4 | Rs -351 | WRONG_DIRECTION | Rs 702 |
| v5 | ABB | LONG | 7,204.5→7,310.5 | Rs 106 | EXIT_TOO_EARLY | Rs 614 |
| v5_classic | BHARATFORG | SHORT | 2,100.4→2,120.6 | Rs -303 | SHORTED_RISER | Rs 606 |
| v5_classic | SAIL | SHORT | 164.6→165.8 | Rs -262 | SHORTED_RISER | Rs 524 |
| v5 | HDFCLIFE | SHORT | 561.8→565.5 | Rs -258 | SHORTED_RISER | Rs 517 |
| v5 | LODHA | LONG | 1,192.0→1,181.2 | Rs -184 | WRONG_DIRECTION | Rs 367 |
| v5_classic | TATAINVEST | LONG | 672.8→666.0 | Rs -181 | WRONG_DIRECTION | Rs 362 |
| v5_classic | HDFCLIFE | SHORT | 557.7→562.2 | Rs -180 | SHORTED_RISER | Rs 360 |
| v5 | TORNTPHARM | SHORT | 4,981.3→4,880.7 | Rs 503 | GOOD_TRADE | Rs 342 |
| v5_classic | TATACAP | SHORT | 355.8→358.7 | Rs -165 | SHORTED_RISER | Rs 330 |
