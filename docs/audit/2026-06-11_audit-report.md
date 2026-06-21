# Trade Audit & Bear-Day Solution — 2026-06-11

*Regime: **BEAR*** — generated 15:36:27

## Bottom line

- **Realized P&L today: Rs -2,164** across 194 trades (92 long / 102 short)
- **Rs left on the table: Rs 35,112** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 25,958**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 10,155**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v4 | 73 | 73/0 | 20 | Rs -5,133 | Rs 22,512 |
| v5 | 59 | 9/50 | 30 | Rs 2,341 | Rs 4,552 |
| v5_classic | 62 | 10/52 | 29 | Rs 627 | Rs 8,048 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LONG_IN_BEAR | 62 | Rs -10,067 | Rs 20,133 |
| SHORTED_RISER | 51 | Rs -2,911 | Rs 5,825 |
| GOOD_TRADE | 56 | Rs 9,917 | Rs 4,702 |
| EXIT_TOO_EARLY | 23 | Rs 959 | Rs 4,342 |
| IGNORED_SIGNAL | 1 | Rs -63 | Rs 87 |
| LOSS_OTHER | 1 | Rs 0 | Rs 23 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 389 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| ADANIENSOL | AVOID | -4.49% | Rs 1,347 |
| PFC | AVOID | -4.12% | Rs 1,236 |
| PAYTM | AVOID | -4.05% | Rs 1,215 |
| IDBI | AVOID | -3.5% | Rs 1,050 |
| RECLTD | AVOID | -3.43% | Rs 1,029 |
| SOLARINDS | AVOID | -3.14% | Rs 942 |
| TIINDIA | AVOID | -2.84% | Rs 852 |
| UPL | AVOID | -2.82% | Rs 846 |
| SRF | AVOID | -2.77% | Rs 831 |
| JUBLFOOD | AVOID | -2.69% | Rs 807 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 62 longs in a bear regime cost Rs 20,133 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 51 shorts hit risers (Rs 5,825 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 389 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 10,155 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v4 | IDEA | LONG | 14.4→14.2 | Rs -424 | LONG_IN_BEAR | Rs 848 |
| v4 | ATGL | LONG | 742.0→731.9 | Rs -374 | LONG_IN_BEAR | Rs 747 |
| v4 | LICHSGFIN | LONG | 543.6→535.5 | Rs -367 | LONG_IN_BEAR | Rs 734 |
| v4 | ONGC | LONG | 255.2→251.4 | Rs -349 | LONG_IN_BEAR | Rs 698 |
| v4 | BSE | LONG | 3,934.7→3,878.0 | Rs -340 | LONG_IN_BEAR | Rs 680 |
| v5_classic | ATGL | SHORT | 728.4→740.9 | Rs -336 | SHORTED_RISER | Rs 672 |
| v4 | ASTRAL | LONG | 1,507.5→1,487.5 | Rs -320 | LONG_IN_BEAR | Rs 640 |
| v4 | KOTAKBANK | LONG | 398.1→392.9 | Rs -307 | LONG_IN_BEAR | Rs 614 |
| v4 | VBL | LONG | 528.8→521.7 | Rs -303 | LONG_IN_BEAR | Rs 606 |
| v5_classic | OFSS | SHORT | 9,183.5→9,328.5 | Rs -290 | SHORTED_RISER | Rs 580 |
| v4 | IRCTC | LONG | 514.6→520.1 | Rs 278 | EXIT_TOO_EARLY | Rs 578 |
| v4 | INDUSTOWER | LONG | 418.1→412.9 | Rs -286 | LONG_IN_BEAR | Rs 572 |
| v5_classic | RECLTD | SHORT | 345.0→343.6 | Rs 94 | EXIT_TOO_EARLY | Rs 556 |
| v4 | ENRIN | LONG | 3,461.0→3,415.3 | Rs -274 | LONG_IN_BEAR | Rs 548 |
| v4 | ADANIGREEN | LONG | 1,489.2→1,473.7 | Rs -264 | LONG_IN_BEAR | Rs 527 |
