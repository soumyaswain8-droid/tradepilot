# Trade Audit & Bear-Day Solution — 2026-08-27

*Regime: **SIDEWAYS*** — generated 15:35:50

## Bottom line

- **Realized P&L today: Rs 765** across 52 trades (24 long / 28 short)
- **Rs left on the table: Rs 4,881** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 3,011**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,995**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 52 | 24/28 | 26 | Rs 765 | Rs 4,881 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 13 | Rs -802 | Rs 1,605 |
| WRONG_DIRECTION | 12 | Rs -704 | Rs 1,406 |
| GOOD_TRADE | 19 | Rs 2,210 | Rs 1,333 |
| EXIT_TOO_EARLY | 7 | Rs 96 | Rs 490 |
| IGNORED_SIGNAL | 1 | Rs -35 | Rs 47 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| MUTHOOTFIN | AVOID | -3.8% | Rs 1,140 |
| QUESS | AVOID | -3.71% | Rs 1,113 |
| HDFCAMC | AVOID | -3.48% | Rs 1,044 |
| HINDALCO | AVOID | -2.75% | Rs 825 |
| RVNL | AVOID | -2.43% | Rs 729 |
| PFC | AVOID | -2.27% | Rs 681 |
| PAYTM | AVOID | -2.16% | Rs 648 |
| KEC | AVOID | -2.03% | Rs 609 |
| AUBANK | AVOID | -2.02% | Rs 606 |
| MFSL | AVOID | -2.0% | Rs 600 |

## Prescription — flip a bear day

2. **Short selection:** 13 shorts hit risers (Rs 1,605 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,995 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | SAIL | SHORT | 192.5→193.9 | Rs -237 | SHORTED_RISER | Rs 474 |
| v5 | TMCV | SHORT | 470.0→473.1 | Rs -217 | SHORTED_RISER | Rs 433 |
| v5 | MOTILALOFS | LONG | 1,035.7→1,022.9 | Rs -154 | WRONG_DIRECTION | Rs 307 |
| v5 | TATASTEEL | LONG | 189.1→187.8 | Rs -128 | WRONG_DIRECTION | Rs 256 |
| v5 | SHRIRAMFIN | SHORT | 1,104.8→1,099.0 | Rs 197 | GOOD_TRADE | Rs 255 |
| v5 | POWERGRID | SHORT | 262.6→264.0 | Rs -122 | SHORTED_RISER | Rs 244 |
| v5 | DLF | LONG | 676.8→682.3 | Rs 244 | GOOD_TRADE | Rs 229 |
| v5 | JINDALSTEL | LONG | 1,184.0→1,185.0 | Rs 19 | EXIT_TOO_EARLY | Rs 217 |
| v5 | ASTRAL | LONG | 1,541.9→1,531.6 | Rs -103 | WRONG_DIRECTION | Rs 206 |
| v5 | HINDZINC | LONG | 616.3→626.5 | Rs 408 | GOOD_TRADE | Rs 196 |
| v5 | VEDL | SHORT | 283.5→281.0 | Rs 258 | GOOD_TRADE | Rs 185 |
| v5 | SUPREMEIND | LONG | 3,588.7→3,577.6 | Rs -78 | WRONG_DIRECTION | Rs 155 |
| v5 | CGPOWER | LONG | 892.4→883.0 | Rs -75 | WRONG_DIRECTION | Rs 150 |
| v5 | SOLARINDS | LONG | 20,400.0→20,514.0 | Rs 114 | GOOD_TRADE | Rs 135 |
| v5 | GVT&D | LONG | 4,504.6→4,451.0 | Rs -54 | WRONG_DIRECTION | Rs 107 |
