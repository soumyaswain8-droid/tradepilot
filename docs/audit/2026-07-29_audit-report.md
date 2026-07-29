# Trade Audit & Bear-Day Solution — 2026-07-29

*Regime: **SIDEWAYS*** — generated 15:35:59

## Bottom line

- **Realized P&L today: Rs 3,421** across 129 trades (69 long / 60 short)
- **Rs left on the table: Rs 17,542** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 10,413**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,322**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 64 | 34/30 | 31 | Rs 1,054 | Rs 6,486 |
| v5_classic | 65 | 35/30 | 32 | Rs 2,366 | Rs 11,056 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 42 | Rs -3,477 | Rs 6,953 |
| GOOD_TRADE | 45 | Rs 8,325 | Rs 5,206 |
| WRONG_DIRECTION | 23 | Rs -1,731 | Rs 3,460 |
| EXIT_TOO_EARLY | 18 | Rs 314 | Rs 1,821 |
| HELD_LOSER | 1 | Rs -10 | Rs 102 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| PHOENIXLTD | AVOID | -5.57% | Rs 1,671 |
| ADANIPORTS | AVOID | -3.1% | Rs 930 |
| MPHASIS | AVOID | -2.16% | Rs 648 |
| TIINDIA | AVOID | -1.37% | Rs 411 |
| CUMMINSIND | AVOID | -1.33% | Rs 399 |
| GODREJIND | AVOID | -1.21% | Rs 363 |
| POWERGRID | AVOID | -0.86% | Rs 258 |
| BPCL | AVOID | -0.83% | Rs 249 |
| LICI | AVOID | -0.76% | Rs 228 |
| PRESTIGE | AVOID | -0.55% | Rs 165 |

## Prescription — flip a bear day

2. **Short selection:** 42 shorts hit risers (Rs 6,953 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,322 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | SWIGGY | LONG | 268.5→279.9 | Rs 918 | GOOD_TRADE | Rs 875 |
| v5_classic | KALYANKJIL | LONG | 608.4→614.1 | Rs 157 | EXIT_TOO_EARLY | Rs 555 |
| v5_classic | MARICO | SHORT | 874.1→880.7 | Rs -264 | SHORTED_RISER | Rs 528 |
| v5_classic | BANKBARODA | SHORT | 239.2→241.3 | Rs -256 | SHORTED_RISER | Rs 512 |
| v5_classic | LODHA | LONG | 1,301.4→1,283.4 | Rs -252 | WRONG_DIRECTION | Rs 504 |
| v5_classic | KPITTECH | LONG | 602.5→631.2 | Rs 461 | GOOD_TRADE | Rs 502 |
| v5_classic | SAIL | LONG | 174.7→172.0 | Rs -247 | WRONG_DIRECTION | Rs 495 |
| v5 | MARICO | SHORT | 875.0→880.7 | Rs -245 | SHORTED_RISER | Rs 490 |
| v5_classic | VEDL | SHORT | 259.4→261.2 | Rs -243 | SHORTED_RISER | Rs 486 |
| v5_classic | INDUSINDBK | SHORT | 992.0→998.2 | Rs -239 | SHORTED_RISER | Rs 479 |
| v5 | COFORGE | LONG | 1,755.9→1,734.3 | Rs -238 | WRONG_DIRECTION | Rs 475 |
| v5_classic | SAIL | LONG | 166.1→173.4 | Rs 1,261 | GOOD_TRADE | Rs 432 |
| v5_classic | INDUSTOWER | SHORT | 381.6→384.6 | Rs -198 | SHORTED_RISER | Rs 396 |
| v5 | GVT&D | SHORT | 4,058.0→4,149.1 | Rs -182 | SHORTED_RISER | Rs 364 |
| v5_classic | BEL | SHORT | 382.9→385.4 | Rs -176 | SHORTED_RISER | Rs 352 |
