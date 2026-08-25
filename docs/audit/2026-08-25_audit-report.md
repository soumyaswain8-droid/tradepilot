# Trade Audit & Bear-Day Solution — 2026-08-25

*Regime: **SIDEWAYS*** — generated 15:36:40

## Bottom line

- **Realized P&L today: Rs 1,292** across 62 trades (34 long / 28 short)
- **Rs left on the table: Rs 8,365** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 4,065**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 3,906**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 62 | 34/28 | 37 | Rs 1,292 | Rs 8,365 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 16 | Rs -1,328 | Rs 2,657 |
| EXIT_TOO_EARLY | 16 | Rs 657 | Rs 2,419 |
| GOOD_TRADE | 21 | Rs 2,667 | Rs 1,881 |
| WRONG_DIRECTION | 9 | Rs -704 | Rs 1,408 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| WELCORP | AVOID | -2.64% | Rs 792 |
| OIL | AVOID | -1.99% | Rs 597 |
| GODREJIND | AVOID | -1.57% | Rs 471 |
| GICRE | AVOID | -1.22% | Rs 366 |
| PETRONET | AVOID | -1.17% | Rs 351 |
| KEC | AVOID | -1.16% | Rs 348 |
| EXIDEIND | AVOID | -1.0% | Rs 300 |
| DABUR | AVOID | -0.85% | Rs 255 |
| VEDL | AVOID | -0.72% | Rs 216 |
| HINDALCO | AVOID | -0.7% | Rs 210 |

## Prescription — flip a bear day

2. **Short selection:** 16 shorts hit risers (Rs 2,657 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 3,906 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | IDEA | LONG | 14.6→14.8 | Rs 280 | EXIT_TOO_EARLY | Rs 708 |
| v5 | HINDZINC | LONG | 609.5→595.6 | Rs -292 | WRONG_DIRECTION | Rs 584 |
| v5 | BDL | LONG | 1,361.9→1,371.6 | Rs 204 | EXIT_TOO_EARLY | Rs 464 |
| v5 | SAIL | LONG | 179.7→182.1 | Rs 228 | GOOD_TRADE | Rs 445 |
| v5 | ADANIENT | SHORT | 2,965.5→2,989.2 | Rs -190 | SHORTED_RISER | Rs 379 |
| v5 | KALYANKJIL | LONG | 620.1→612.0 | Rs -187 | WRONG_DIRECTION | Rs 375 |
| v5 | PIIND | SHORT | 2,457.3→2,471.1 | Rs -179 | SHORTED_RISER | Rs 359 |
| v5 | PREMIERENE | SHORT | 1,020.1→1,029.1 | Rs -162 | SHORTED_RISER | Rs 324 |
| v5 | JSWENERGY | SHORT | 540.3→543.0 | Rs -159 | SHORTED_RISER | Rs 319 |
| v5 | TATAELXSI | SHORT | 3,615.9→3,643.8 | Rs -140 | SHORTED_RISER | Rs 279 |
| v5 | NHPC | SHORT | 76.0→76.6 | Rs -139 | SHORTED_RISER | Rs 277 |
| v5 | SIEMENS | LONG | 4,069.2→4,097.4 | Rs 141 | GOOD_TRADE | Rs 260 |
| v5 | HAL | SHORT | 4,827.0→4,852.0 | Rs -100 | SHORTED_RISER | Rs 200 |
| v5 | LICHSGFIN | LONG | 495.3→496.6 | Rs 26 | EXIT_TOO_EARLY | Rs 185 |
| v5 | IDEA | LONG | 15.1→15.2 | Rs 146 | GOOD_TRADE | Rs 175 |
