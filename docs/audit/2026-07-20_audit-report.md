# Trade Audit & Bear-Day Solution — 2026-07-20

*Regime: **SIDEWAYS*** — generated 15:36:27

## Bottom line

- **Realized P&L today: Rs 3,229** across 113 trades (65 long / 48 short)
- **Rs left on the table: Rs 11,897** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 6,362**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 4,197**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 62 | 44/18 | 33 | Rs 1,066 | Rs 6,851 |
| v5_classic | 51 | 21/30 | 25 | Rs 2,163 | Rs 5,046 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 21 | Rs -1,629 | Rs 3,357 |
| GOOD_TRADE | 36 | Rs 6,033 | Rs 3,319 |
| SHORTED_RISER | 27 | Rs -1,518 | Rs 3,038 |
| EXIT_TOO_EARLY | 21 | Rs 376 | Rs 1,983 |
| HELD_LOSER | 4 | Rs -29 | Rs 112 |
| LOSS_OTHER | 3 | Rs 0 | Rs 75 |
| IGNORED_SIGNAL | 1 | Rs -4 | Rs 13 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| AUBANK | AVOID | -3.58% | Rs 1,074 |
| UPL | AVOID | -1.71% | Rs 513 |
| KEC | AVOID | -1.54% | Rs 462 |
| STAR | AVOID | -1.43% | Rs 429 |
| CHOLAFIN | AVOID | -1.22% | Rs 366 |
| BHEL | AVOID | -1.07% | Rs 321 |
| ARVIND | AVOID | -0.97% | Rs 291 |
| ATUL | AVOID | -0.94% | Rs 282 |
| TVSMOTOR | AVOID | -0.77% | Rs 231 |
| GRSE | AVOID | -0.76% | Rs 228 |

## Prescription — flip a bear day

2. **Short selection:** 27 shorts hit risers (Rs 3,038 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 4,197 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | BOSCHLTD | SHORT | 40,500.0→40,720.0 | Rs -220 | SHORTED_RISER | Rs 440 |
| v5 | MOTHERSON | SHORT | 142.3→143.2 | Rs -180 | SHORTED_RISER | Rs 360 |
| v5 | OIL | LONG | 438.2→447.0 | Rs 324 | GOOD_TRADE | Rs 359 |
| v5_classic | OIL | LONG | 438.2→447.0 | Rs 324 | GOOD_TRADE | Rs 359 |
| v5 | HINDZINC | LONG | 529.5→524.4 | Rs -173 | WRONG_DIRECTION | Rs 347 |
| v5 | HAVELLS | LONG | 1,205.8→1,191.5 | Rs -157 | WRONG_DIRECTION | Rs 315 |
| v5_classic | AXISBANK | SHORT | 1,256.8→1,264.5 | Rs -154 | SHORTED_RISER | Rs 308 |
| v5_classic | M&M | LONG | 3,181.4→3,165.5 | Rs -143 | WRONG_DIRECTION | Rs 286 |
| v5_classic | BPCL | SHORT | 310.5→312.1 | Rs -137 | SHORTED_RISER | Rs 274 |
| v5 | JINDALSTEL | LONG | 1,040.0→1,029.6 | Rs -135 | WRONG_DIRECTION | Rs 270 |
| v5 | OFSS | SHORT | 11,640.0→11,626.0 | Rs 42 | EXIT_TOO_EARLY | Rs 246 |
| v5_classic | BHARATFORG | LONG | 2,194.7→2,183.5 | Rs -123 | WRONG_DIRECTION | Rs 246 |
| v5 | KOTAKBANK | LONG | 384.4→377.7 | Rs -122 | WRONG_DIRECTION | Rs 243 |
| v5 | ICICIAMC | SHORT | 3,136.9→3,123.9 | Rs 91 | EXIT_TOO_EARLY | Rs 240 |
| v5 | TVSMOTOR | SHORT | 3,551.8→3,581.6 | Rs -119 | SHORTED_RISER | Rs 238 |
