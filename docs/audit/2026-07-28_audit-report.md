# Trade Audit & Bear-Day Solution — 2026-07-28

*Regime: **SIDEWAYS*** — generated 15:35:59

## Bottom line

- **Realized P&L today: Rs 4,758** across 102 trades (60 long / 42 short)
- **Rs left on the table: Rs 18,881** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 11,136**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 10,695**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 49 | 29/20 | 24 | Rs 2,023 | Rs 7,332 |
| v5_classic | 53 | 31/22 | 26 | Rs 2,735 | Rs 11,549 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 25 | Rs -4,434 | Rs 8,866 |
| GOOD_TRADE | 36 | Rs 9,968 | Rs 4,382 |
| EXIT_TOO_EARLY | 14 | Rs 479 | Rs 2,609 |
| SHORTED_RISER | 22 | Rs -1,135 | Rs 2,270 |
| HELD_LOSER | 2 | Rs -65 | Rs 348 |
| LOSS_OTHER | 2 | Rs 0 | Rs 268 |
| IGNORED_SIGNAL | 1 | Rs -53 | Rs 138 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| GODFRYPHLP | AVOID | -8.11% | Rs 2,433 |
| VBL | AVOID | -7.43% | Rs 2,229 |
| BEL | AVOID | -4.46% | Rs 1,338 |
| ADANIPOWER | AVOID | -2.67% | Rs 801 |
| BHEL | AVOID | -2.45% | Rs 735 |
| CANBK | AVOID | -2.37% | Rs 711 |
| ARVIND | AVOID | -2.31% | Rs 693 |
| ATUL | AVOID | -2.05% | Rs 615 |
| VEDL | AVOID | -2.0% | Rs 600 |
| CHOLAFIN | AVOID | -1.8% | Rs 540 |

## Prescription — flip a bear day

2. **Short selection:** 22 shorts hit risers (Rs 2,270 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 10,695 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | GODFRYPHLP | LONG | 2,210.5→2,051.9 | Rs -1,269 | WRONG_DIRECTION | Rs 2,538 |
| v5_classic | SWIGGY | LONG | 269.6→265.2 | Rs -406 | WRONG_DIRECTION | Rs 813 |
| v5 | SWIGGY | LONG | 269.6→265.8 | Rs -366 | WRONG_DIRECTION | Rs 731 |
| v5_classic | LODHA | LONG | 1,198.7→1,290.6 | Rs 2,298 | GOOD_TRADE | Rs 645 |
| v5 | LTM | LONG | 4,020.0→4,190.8 | Rs 512 | GOOD_TRADE | Rs 587 |
| v5 | KALYANKJIL | LONG | 597.5→598.8 | Rs 58 | EXIT_TOO_EARLY | Rs 549 |
| v5 | HCLTECH | LONG | 1,340.6→1,321.3 | Rs -251 | WRONG_DIRECTION | Rs 502 |
| v5_classic | EXIDEIND | SHORT | 427.0→430.1 | Rs -238 | SHORTED_RISER | Rs 476 |
| v5_classic | HCLTECH | LONG | 1,340.6→1,321.3 | Rs -232 | WRONG_DIRECTION | Rs 463 |
| v5 | KPITTECH | LONG | 604.5→598.2 | Rs -231 | WRONG_DIRECTION | Rs 462 |
| v5_classic | KPITTECH | LONG | 604.5→598.4 | Rs -220 | WRONG_DIRECTION | Rs 439 |
| v5_classic | GODREJPROP | LONG | 2,068.8→2,112.3 | Rs 566 | GOOD_TRADE | Rs 417 |
| v5 | KALYANKJIL | LONG | 573.8→589.0 | Rs 274 | GOOD_TRADE | Rs 397 |
| v5_classic | KALYANKJIL | LONG | 573.8→588.8 | Rs 255 | GOOD_TRADE | Rs 378 |
| v5 | LODHA | LONG | 1,290.2→1,273.3 | Rs -186 | WRONG_DIRECTION | Rs 373 |
