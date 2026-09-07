# Trade Audit & Bear-Day Solution — 2026-09-07

*Regime: **BEAR*** — generated 15:35:28

## Bottom line

- **Realized P&L today: Rs 1,593** across 50 trades (10 long / 40 short)
- **Rs left on the table: Rs 4,230** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 1,449**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 8,157**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 50 | 10/40 | 34 | Rs 1,593 | Rs 4,230 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| GOOD_TRADE | 18 | Rs 1,917 | Rs 1,401 |
| EXIT_TOO_EARLY | 16 | Rs 400 | Rs 1,380 |
| SHORTED_RISER | 12 | Rs -383 | Rs 765 |
| LONG_IN_BEAR | 4 | Rs -342 | Rs 684 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| QUESS | AVOID | -4.27% | Rs 1,281 |
| PIDILITIND | AVOID | -3.34% | Rs 1,002 |
| JYOTHYLAB | AVOID | -3.2% | Rs 960 |
| KEI | AVOID | -3.01% | Rs 903 |
| SBILIFE | AVOID | -2.42% | Rs 726 |
| GICRE | AVOID | -2.41% | Rs 723 |
| PRESTIGE | AVOID | -2.33% | Rs 699 |
| BHEL | AVOID | -2.24% | Rs 672 |
| SHREECEM | AVOID | -2.05% | Rs 615 |
| COFORGE | AVOID | -1.92% | Rs 576 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 4 longs in a bear regime cost Rs 684 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 12 shorts hit risers (Rs 765 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 8,157 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ADANIENSOL | LONG | 1,406.5→1,391.1 | Rs -246 | LONG_IN_BEAR | Rs 493 |
| v5 | SAIL | SHORT | 190.3→189.6 | Rs 63 | EXIT_TOO_EARLY | Rs 219 |
| v5 | TECHM | SHORT | 1,567.6→1,559.9 | Rs 116 | GOOD_TRADE | Rs 219 |
| v5 | ICICIAMC | LONG | 2,991.0→3,010.5 | Rs 136 | GOOD_TRADE | Rs 194 |
| v5 | JINDALSTEL | SHORT | 1,144.7→1,140.2 | Rs 81 | EXIT_TOO_EARLY | Rs 184 |
| v5 | DIVISLAB | LONG | 9,143.5→9,226.0 | Rs 165 | GOOD_TRADE | Rs 178 |
| v5 | ICICIAMC | SHORT | 2,942.2→2,959.2 | Rs -85 | SHORTED_RISER | Rs 170 |
| v5 | MCX | LONG | 3,324.0→3,332.3 | Rs 33 | EXIT_TOO_EARLY | Rs 168 |
| v5 | SUPREMEIND | LONG | 3,552.0→3,575.0 | Rs 115 | GOOD_TRADE | Rs 141 |
| v5 | SHRIRAMFIN | SHORT | 1,031.1→1,038.8 | Rs -69 | SHORTED_RISER | Rs 139 |
| v5 | LTM | SHORT | 4,481.6→4,438.9 | Rs 171 | GOOD_TRADE | Rs 136 |
| v5 | OFSS | SHORT | 11,869.0→11,806.0 | Rs 63 | EXIT_TOO_EARLY | Rs 127 |
| v5 | TATACAP | SHORT | 369.7→368.8 | Rs 32 | EXIT_TOO_EARLY | Rs 122 |
| v5 | EXIDEIND | SHORT | 418.6→421.1 | Rs -54 | SHORTED_RISER | Rs 107 |
| v5 | TCS | SHORT | 2,265.0→2,271.8 | Rs -48 | SHORTED_RISER | Rs 95 |
