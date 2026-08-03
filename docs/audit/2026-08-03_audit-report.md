# Trade Audit & Bear-Day Solution — 2026-08-03

*Regime: **BULL*** — generated 15:36:20

## Bottom line

- **Realized P&L today: Rs 7,788** across 97 trades (97 long / 0 short)
- **Rs left on the table: Rs 15,307** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 6,791**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 3,048**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 52 | 52/0 | 27 | Rs 3,654 | Rs 8,248 |
| v5_classic | 45 | 45/0 | 26 | Rs 4,134 | Rs 7,059 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 44 | Rs -3,395 | Rs 6,967 |
| GOOD_TRADE | 40 | Rs 10,790 | Rs 6,097 |
| EXIT_TOO_EARLY | 13 | Rs 393 | Rs 2,243 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| SADBHAV | AVOID | -4.85% | Rs 1,455 |
| ZYDUSWELL | AVOID | -3.06% | Rs 918 |
| LUPIN | AVOID | -0.91% | Rs 273 |
| GRSE | AVOID | -0.71% | Rs 213 |
| HDFCAMC | AVOID | -0.58% | Rs 174 |
| TATAINVEST | AVOID | -0.41% | Rs 123 |
| LAURUSLABS | AVOID | -0.26% | Rs 78 |
| COLPAL | AVOID | 0.04% | Rs -12 |
| JINDALSTEL | AVOID | 0.24% | Rs -72 |
| STAR | AVOID | 0.34% | Rs -102 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 3,048 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | ITC | LONG | 292.1→289.4 | Rs -416 | WRONG_DIRECTION | Rs 832 |
| v5_classic | JUBLFOOD | LONG | 447.6→458.2 | Rs 654 | GOOD_TRADE | Rs 781 |
| v5_classic | ASHOKLEY | LONG | 164.2→171.2 | Rs 1,250 | GOOD_TRADE | Rs 664 |
| v5 | JUBLFOOD | LONG | 447.6→463.1 | Rs 1,318 | GOOD_TRADE | Rs 650 |
| v5 | TMCV | LONG | 436.9→446.5 | Rs 589 | GOOD_TRADE | Rs 528 |
| v5 | MOTILALOFS | LONG | 872.9→867.8 | Rs -263 | WRONG_DIRECTION | Rs 525 |
| v5 | FORTIS | LONG | 958.0→961.6 | Rs 106 | EXIT_TOO_EARLY | Rs 521 |
| v5_classic | PAYTM | LONG | 1,414.7→1,390.9 | Rs -238 | WRONG_DIRECTION | Rs 476 |
| v5 | ASHOKLEY | LONG | 166.4→171.9 | Rs 767 | GOOD_TRADE | Rs 430 |
| v5 | BSE | LONG | 3,632.0→3,578.7 | Rs -213 | WRONG_DIRECTION | Rs 426 |
| v5 | JIOFIN | LONG | 266.2→262.6 | Rs -212 | WRONG_DIRECTION | Rs 425 |
| v5 | APLAPOLLO | LONG | 1,931.0→1,901.0 | Rs -210 | WRONG_DIRECTION | Rs 420 |
| v5 | BAJFINANCE | LONG | 1,145.1→1,160.5 | Rs 400 | GOOD_TRADE | Rs 413 |
| v5_classic | MOTILALOFS | LONG | 872.4→867.8 | Rs -200 | WRONG_DIRECTION | Rs 400 |
| v5_classic | FORTIS | LONG | 958.0→961.6 | Rs 77 | EXIT_TOO_EARLY | Rs 377 |
