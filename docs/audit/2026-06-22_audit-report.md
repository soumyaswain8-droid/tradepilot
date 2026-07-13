# Trade Audit & Bear-Day Solution — 2026-06-22

*Regime: **SIDEWAYS*** — generated 15:35:38

## Bottom line

- **Realized P&L today: Rs -442** across 128 trades (61 long / 67 short)
- **Rs left on the table: Rs 18,471** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 13,275**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,409**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 67 | 32/35 | 28 | Rs -798 | Rs 8,474 |
| v5_classic | 61 | 29/32 | 28 | Rs 355 | Rs 9,997 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 39 | Rs -4,269 | Rs 8,539 |
| WRONG_DIRECTION | 30 | Rs -2,369 | Rs 4,736 |
| GOOD_TRADE | 36 | Rs 5,777 | Rs 3,113 |
| EXIT_TOO_EARLY | 20 | Rs 483 | Rs 1,956 |
| IGNORED_SIGNAL | 2 | Rs -64 | Rs 112 |
| LOSS_OTHER | 1 | Rs 0 | Rs 15 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| VBL | AVOID | -3.13% | Rs 939 |
| INDUSINDBK | AVOID | -2.79% | Rs 837 |
| ASIANPAINT | AVOID | -2.16% | Rs 648 |
| YESBANK | AVOID | -1.77% | Rs 531 |
| CUMMINSIND | AVOID | -1.72% | Rs 516 |
| PAGEIND | AVOID | -1.64% | Rs 492 |
| EMAMILTD | AVOID | -1.62% | Rs 486 |
| HDFCAMC | AVOID | -1.07% | Rs 321 |
| TITAN | AVOID | -1.07% | Rs 321 |
| KITEX | AVOID | -1.06% | Rs 318 |

## Prescription — flip a bear day

2. **Short selection:** 39 shorts hit risers (Rs 8,539 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,409 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | HUDCO | SHORT | 208.7→212.7 | Rs -654 | SHORTED_RISER | Rs 1,309 |
| v5_classic | HUDCO | SHORT | 208.7→212.4 | Rs -603 | SHORTED_RISER | Rs 1,206 |
| v5_classic | TATACOMM | LONG | 1,988.8→2,054.3 | Rs 917 | GOOD_TRADE | Rs 780 |
| v5 | BPCL | SHORT | 306.6→309.7 | Rs -384 | SHORTED_RISER | Rs 769 |
| v5_classic | MRF | LONG | 131,035.0→131,300.0 | Rs 265 | EXIT_TOO_EARLY | Rs 740 |
| v5 | TATACOMM | LONG | 1,988.8→2,054.3 | Rs 852 | GOOD_TRADE | Rs 724 |
| v5_classic | BPCL | SHORT | 306.6→309.3 | Rs -335 | SHORTED_RISER | Rs 670 |
| v5 | TATACAP | LONG | 366.8→361.0 | Rs -313 | WRONG_DIRECTION | Rs 626 |
| v5_classic | TMPV | LONG | 368.5→364.6 | Rs -261 | WRONG_DIRECTION | Rs 523 |
| v5_classic | BAJAJ-AUTO | LONG | 10,258.0→10,155.0 | Rs -206 | WRONG_DIRECTION | Rs 412 |
| v5_classic | TORNTPHARM | SHORT | 4,383.7→4,423.1 | Rs -197 | SHORTED_RISER | Rs 394 |
| v5 | JUBLFOOD | LONG | 434.9→432.0 | Rs -183 | WRONG_DIRECTION | Rs 365 |
| v5_classic | ADANIPOWER | SHORT | 230.5→231.7 | Rs -174 | SHORTED_RISER | Rs 349 |
| v5_classic | POLYCAB | SHORT | 10,010.0→10,065.0 | Rs -165 | SHORTED_RISER | Rs 330 |
| v5_classic | GVT&D | LONG | 5,533.5→5,454.5 | Rs -158 | WRONG_DIRECTION | Rs 316 |
