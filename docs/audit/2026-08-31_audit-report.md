# Trade Audit & Bear-Day Solution — 2026-08-31

*Regime: **SIDEWAYS*** — generated 15:36:17

## Bottom line

- **Realized P&L today: Rs 1,258** across 66 trades (34 long / 32 short)
- **Rs left on the table: Rs 10,245** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 5,273**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 15,510**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 66 | 34/32 | 27 | Rs 1,258 | Rs 10,245 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 18 | Rs -1,841 | Rs 3,679 |
| GOOD_TRADE | 18 | Rs 3,773 | Rs 2,966 |
| EXIT_TOO_EARLY | 9 | Rs 219 | Rs 1,769 |
| SHORTED_RISER | 20 | Rs -796 | Rs 1,594 |
| HELD_LOSER | 1 | Rs -98 | Rs 237 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| ADANIENT | AVOID | -9.76% | Rs 2,928 |
| ADANIPOWER | AVOID | -6.88% | Rs 2,064 |
| NEWGEN | AVOID | -6.74% | Rs 2,022 |
| ADANIPORTS | AVOID | -6.7% | Rs 2,010 |
| SADBHAV | AVOID | -4.95% | Rs 1,485 |
| MUTHOOTFIN | AVOID | -3.65% | Rs 1,095 |
| VEDL | AVOID | -3.39% | Rs 1,017 |
| SHREECEM | AVOID | -3.33% | Rs 999 |
| VBL | AVOID | -3.27% | Rs 981 |
| NAUKRI | AVOID | -3.03% | Rs 909 |

## Prescription — flip a bear day

2. **Short selection:** 20 shorts hit risers (Rs 1,594 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 15,510 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ADANIENT | SHORT | 3,091.1→2,989.7 | Rs 1,217 | GOOD_TRADE | Rs 1,567 |
| v5 | KPITTECH | LONG | 605.1→592.1 | Rs -546 | WRONG_DIRECTION | Rs 1,092 |
| v5 | SBICARD | LONG | 647.5→639.8 | Rs -316 | WRONG_DIRECTION | Rs 631 |
| v5 | PREMIERENE | LONG | 1,011.1→1,011.2 | Rs 2 | EXIT_TOO_EARLY | Rs 577 |
| v5 | ASTRAL | LONG | 1,534.6→1,546.0 | Rs 148 | EXIT_TOO_EARLY | Rs 455 |
| v5 | HDFCBANK | LONG | 733.4→725.8 | Rs -181 | WRONG_DIRECTION | Rs 362 |
| v5 | OIL | LONG | 482.7→490.6 | Rs 294 | GOOD_TRADE | Rs 346 |
| v5 | M&M | LONG | 3,359.6→3,282.0 | Rs -155 | WRONG_DIRECTION | Rs 310 |
| v5 | TMCV | LONG | 469.6→463.8 | Rs -152 | WRONG_DIRECTION | Rs 304 |
| v5 | COFORGE | LONG | 1,965.8→1,999.9 | Rs 477 | GOOD_TRADE | Rs 298 |
| v5 | LTF | SHORT | 307.8→310.0 | Rs -139 | SHORTED_RISER | Rs 277 |
| v5 | HINDZINC | SHORT | 594.8→597.9 | Rs -133 | SHORTED_RISER | Rs 267 |
| v5 | GMRAIRPORT | SHORT | 96.2→96.1 | Rs 15 | EXIT_TOO_EARLY | Rs 267 |
| v5 | MARICO | LONG | 839.0→820.0 | Rs -133 | WRONG_DIRECTION | Rs 265 |
| v5 | SBICARD | LONG | 654.5→644.8 | Rs -98 | HELD_LOSER | Rs 237 |
