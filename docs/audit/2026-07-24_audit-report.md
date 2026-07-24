# Trade Audit & Bear-Day Solution — 2026-07-24

*Regime: **BEAR*** — generated 15:36:24

## Bottom line

- **Realized P&L today: Rs -1,092** across 138 trades (55 long / 83 short)
- **Rs left on the table: Rs 19,307** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 15,013**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,748**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 68 | 27/41 | 27 | Rs -1,460 | Rs 10,107 |
| v5_classic | 70 | 28/42 | 29 | Rs 368 | Rs 9,200 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LONG_IN_BEAR | 31 | Rs -3,965 | Rs 7,931 |
| SHORTED_RISER | 48 | Rs -3,541 | Rs 7,082 |
| GOOD_TRADE | 45 | Rs 6,301 | Rs 3,159 |
| EXIT_TOO_EARLY | 11 | Rs 234 | Rs 851 |
| IGNORED_SIGNAL | 2 | Rs -121 | Rs 263 |
| LOSS_OTHER | 1 | Rs 0 | Rs 21 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| HEROMOTOCO | AVOID | -3.14% | Rs 942 |
| BAJFINANCE | AVOID | -2.6% | Rs 780 |
| TIINDIA | AVOID | -2.04% | Rs 612 |
| SHRIRAMFIN | AVOID | -2.02% | Rs 606 |
| OIL | AVOID | -1.97% | Rs 591 |
| PRESTIGE | AVOID | -1.92% | Rs 576 |
| ATGL | AVOID | -1.47% | Rs 441 |
| TATACOMM | AVOID | -1.41% | Rs 423 |
| HINDALCO | AVOID | -1.34% | Rs 402 |
| DRREDDY | AVOID | -1.25% | Rs 375 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 31 longs in a bear regime cost Rs 7,931 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 48 shorts hit risers (Rs 7,082 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,748 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | SRF | SHORT | 2,622.7→2,665.4 | Rs -384 | SHORTED_RISER | Rs 769 |
| v5_classic | TMCV | LONG | 407.9→401.6 | Rs -375 | LONG_IN_BEAR | Rs 750 |
| v5 | EXIDEIND | LONG | 445.2→439.8 | Rs -327 | LONG_IN_BEAR | Rs 654 |
| v5_classic | SIEMENS | LONG | 3,686.3→3,643.3 | Rs -301 | LONG_IN_BEAR | Rs 602 |
| v5 | SHRIRAMFIN | SHORT | 1,000.5→1,009.3 | Rs -290 | SHORTED_RISER | Rs 581 |
| v5 | SHRIRAMFIN | LONG | 1,045.7→1,030.5 | Rs -274 | LONG_IN_BEAR | Rs 547 |
| v5 | NESTLEIND | LONG | 1,457.4→1,444.9 | Rs -262 | LONG_IN_BEAR | Rs 525 |
| v5 | NAUKRI | LONG | 1,172.8→1,155.0 | Rs -231 | LONG_IN_BEAR | Rs 463 |
| v5 | ETERNAL | SHORT | 280.8→282.4 | Rs -231 | SHORTED_RISER | Rs 462 |
| v5 | BAJAJHLDNG | LONG | 10,733.0→10,620.0 | Rs -226 | LONG_IN_BEAR | Rs 452 |
| v5_classic | MOTHERSON | SHORT | 143.5→144.9 | Rs -225 | SHORTED_RISER | Rs 450 |
| v5_classic | RVNL | LONG | 224.1→221.8 | Rs -221 | LONG_IN_BEAR | Rs 443 |
| v5 | ASHOKLEY | SHORT | 148.0→149.4 | Rs -205 | SHORTED_RISER | Rs 410 |
| v5 | HCLTECH | LONG | 1,264.0→1,240.0 | Rs -192 | LONG_IN_BEAR | Rs 384 |
| v5_classic | VEDL | LONG | 264.6→260.5 | Rs -172 | LONG_IN_BEAR | Rs 344 |
