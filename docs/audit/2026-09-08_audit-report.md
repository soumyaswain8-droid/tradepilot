# Trade Audit & Bear-Day Solution — 2026-09-08

*Regime: **SIDEWAYS*** — generated 15:36:53

## Bottom line

- **Realized P&L today: Rs -1,887** across 48 trades (20 long / 28 short)
- **Rs left on the table: Rs 5,360** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 4,351**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,753**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 48 | 20/28 | 17 | Rs -1,887 | Rs 5,360 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 12 | Rs -1,370 | Rs 2,739 |
| SHORTED_RISER | 14 | Rs -805 | Rs 1,612 |
| IGNORED_SIGNAL | 2 | Rs -253 | Rs 436 |
| GOOD_TRADE | 11 | Rs 499 | Rs 266 |
| EXIT_TOO_EARLY | 6 | Rs 67 | Rs 226 |
| HELD_LOSER | 2 | Rs -25 | Rs 69 |
| LOSS_OTHER | 1 | Rs 0 | Rs 12 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| GICRE | AVOID | -2.89% | Rs 867 |
| BPCL | AVOID | -2.89% | Rs 867 |
| HINDPETRO | AVOID | -2.77% | Rs 831 |
| JINDALSTEL | AVOID | -2.46% | Rs 738 |
| NEWGEN | AVOID | -2.06% | Rs 618 |
| SBILIFE | AVOID | -2.04% | Rs 612 |
| ICICIBANK | AVOID | -1.97% | Rs 591 |
| SADBHAV | AVOID | -1.96% | Rs 588 |
| EXIDEIND | AVOID | -1.79% | Rs 537 |
| GODREJIND | AVOID | -1.68% | Rs 504 |

## Prescription — flip a bear day

2. **Short selection:** 14 shorts hit risers (Rs 1,612 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,753 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | COFORGE | LONG | 1,951.6→1,928.2 | Rs -374 | WRONG_DIRECTION | Rs 749 |
| v5 | KEI | LONG | 4,762.0→4,690.0 | Rs -288 | WRONG_DIRECTION | Rs 576 |
| v5 | HINDZINC | LONG | 603.2→597.4 | Rs -232 | WRONG_DIRECTION | Rs 464 |
| v5 | BEL | LONG | 413.4→410.5 | Rs -194 | IGNORED_SIGNAL | Rs 365 |
| v5 | OBEROIRLTY | SHORT | 1,831.0→1,841.8 | Rs -173 | SHORTED_RISER | Rs 346 |
| v5 | MCX | SHORT | 3,307.0→3,323.9 | Rs -169 | SHORTED_RISER | Rs 338 |
| v5 | NATIONALUM | LONG | 377.4→374.4 | Rs -142 | WRONG_DIRECTION | Rs 284 |
| v5 | APLAPOLLO | SHORT | 2,179.7→2,191.2 | Rs -126 | SHORTED_RISER | Rs 253 |
| v5 | LT | SHORT | 3,967.0→3,976.5 | Rs -86 | SHORTED_RISER | Rs 171 |
| v5 | BHARATFORG | LONG | 2,025.3→1,996.9 | Rs -85 | WRONG_DIRECTION | Rs 170 |
| v5 | NHPC | SHORT | 75.2→76.0 | Rs -71 | SHORTED_RISER | Rs 141 |
| v5 | MARUTI | SHORT | 12,634.0→12,701.0 | Rs -67 | SHORTED_RISER | Rs 134 |
| v5 | LTM | LONG | 4,468.0→4,435.9 | Rs -64 | WRONG_DIRECTION | Rs 128 |
| v5 | POLYCAB | LONG | 8,425.5→8,377.5 | Rs -48 | WRONG_DIRECTION | Rs 96 |
| v5 | VEDL | LONG | 272.6→271.4 | Rs -47 | WRONG_DIRECTION | Rs 94 |
