# Trade Audit & Bear-Day Solution — 2026-07-07

*Regime: **SIDEWAYS*** — generated 15:36:18

## Bottom line

- **Realized P&L today: Rs -56** across 114 trades (65 long / 49 short)
- **Rs left on the table: Rs 13,935** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 8,680**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 12,861**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 68 | 44/24 | 24 | Rs -1,138 | Rs 9,068 |
| v5_classic | 46 | 21/25 | 24 | Rs 1,082 | Rs 4,867 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 37 | Rs -3,525 | Rs 7,048 |
| GOOD_TRADE | 28 | Rs 4,037 | Rs 2,581 |
| EXIT_TOO_EARLY | 20 | Rs 371 | Rs 1,958 |
| SHORTED_RISER | 19 | Rs -816 | Rs 1,632 |
| IGNORED_SIGNAL | 7 | Rs -110 | Rs 588 |
| LOSS_OTHER | 2 | Rs 0 | Rs 76 |
| HELD_LOSER | 1 | Rs -14 | Rs 52 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| TRENT | AVOID | -12.44% | Rs 3,732 |
| KALYANKJIL | AVOID | -6.95% | Rs 2,085 |
| BIOCON | AVOID | -4.1% | Rs 1,230 |
| DLF | AVOID | -3.3% | Rs 990 |
| ADANIENT | AVOID | -3.1% | Rs 930 |
| GALAXYSURF | AVOID | -2.97% | Rs 891 |
| BHEL | AVOID | -2.85% | Rs 855 |
| NATIONALUM | AVOID | -2.42% | Rs 726 |
| OBEROIRLTY | AVOID | -2.41% | Rs 723 |
| RECLTD | AVOID | -2.33% | Rs 699 |

## Prescription — flip a bear day

2. **Short selection:** 19 shorts hit risers (Rs 1,632 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 12,861 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ENRIN | LONG | 3,415.0→3,343.1 | Rs -575 | WRONG_DIRECTION | Rs 1,150 |
| v5_classic | ENRIN | LONG | 3,405.3→3,343.1 | Rs -498 | WRONG_DIRECTION | Rs 995 |
| v5 | CGPOWER | LONG | 921.0→904.6 | Rs -329 | WRONG_DIRECTION | Rs 658 |
| v5 | SWIGGY | LONG | 257.2→261.9 | Rs 355 | GOOD_TRADE | Rs 422 |
| v5 | HINDALCO | LONG | 978.0→966.0 | Rs -191 | WRONG_DIRECTION | Rs 382 |
| v5_classic | GROWW | SHORT | 200.2→196.0 | Rs 456 | GOOD_TRADE | Rs 379 |
| v5 | TECHM | LONG | 1,456.2→1,444.9 | Rs -170 | WRONG_DIRECTION | Rs 339 |
| v5 | VMM | SHORT | 116.6→117.2 | Rs -167 | SHORTED_RISER | Rs 334 |
| v5 | PREMIERENE | LONG | 1,038.3→1,027.4 | Rs -153 | WRONG_DIRECTION | Rs 305 |
| v5_classic | BANKBARODA | SHORT | 249.9→248.2 | Rs 268 | GOOD_TRADE | Rs 283 |
| v5 | MCX | SHORT | 2,616.0→2,631.5 | Rs -140 | SHORTED_RISER | Rs 279 |
| v5_classic | BDL | LONG | 1,409.6→1,387.0 | Rs -136 | WRONG_DIRECTION | Rs 271 |
| v5 | NHPC | SHORT | 78.7→78.7 | Rs 7 | EXIT_TOO_EARLY | Rs 253 |
| v5 | TVSMOTOR | LONG | 3,751.1→3,713.0 | Rs -114 | WRONG_DIRECTION | Rs 229 |
| v5 | BDL | LONG | 1,409.6→1,387.0 | Rs -113 | WRONG_DIRECTION | Rs 226 |
