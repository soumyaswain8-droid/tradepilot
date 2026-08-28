# Trade Audit & Bear-Day Solution — 2026-08-28

*Regime: **SIDEWAYS*** — generated 15:35:31

## Bottom line

- **Realized P&L today: Rs 1,047** across 43 trades (18 long / 25 short)
- **Rs left on the table: Rs 4,861** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 2,446**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,211**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 43 | 18/25 | 22 | Rs 1,047 | Rs 4,861 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 14 | Rs -811 | Rs 1,623 |
| GOOD_TRADE | 13 | Rs 2,099 | Rs 1,445 |
| WRONG_DIRECTION | 6 | Rs -411 | Rs 823 |
| EXIT_TOO_EARLY | 9 | Rs 170 | Rs 787 |
| LOSS_OTHER | 1 | Rs 0 | Rs 183 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| ADANIENSOL | AVOID | -2.2% | Rs 660 |
| SHREECEM | AVOID | -1.96% | Rs 588 |
| GODREJPROP | AVOID | -1.95% | Rs 585 |
| ATUL | AVOID | -1.91% | Rs 573 |
| HINDPETRO | AVOID | -1.89% | Rs 567 |
| PGEL | AVOID | -1.7% | Rs 510 |
| PAYTM | AVOID | -1.67% | Rs 501 |
| ZYDUSWELL | AVOID | -1.62% | Rs 486 |
| WELCORP | AVOID | -1.33% | Rs 399 |
| GRSE | AVOID | -1.14% | Rs 342 |

## Prescription — flip a bear day

2. **Short selection:** 14 shorts hit risers (Rs 1,623 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,211 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | PREMIERENE | SHORT | 981.0→988.1 | Rs -270 | SHORTED_RISER | Rs 540 |
| v5 | EXIDEIND | LONG | 451.2→445.4 | Rs -168 | WRONG_DIRECTION | Rs 336 |
| v5 | ZYDUSLIFE | SHORT | 1,173.8→1,185.3 | Rs -126 | SHORTED_RISER | Rs 253 |
| v5 | GODREJPROP | SHORT | 2,033.3→2,047.9 | Rs -102 | SHORTED_RISER | Rs 204 |
| v5 | ADANIENSOL | SHORT | 1,591.8→1,581.0 | Rs 151 | GOOD_TRADE | Rs 197 |
| v5 | GROWW | SHORT | 192.9→191.5 | Rs 146 | GOOD_TRADE | Rs 189 |
| v5 | IDEA | SHORT | 14.8→14.7 | Rs 46 | EXIT_TOO_EARLY | Rs 183 |
| v5 | MANKIND | SHORT | 2,396.2→2,396.2 | Rs 0 | LOSS_OTHER | Rs 183 |
| v5 | KPITTECH | LONG | 605.1→609.4 | Rs 179 | GOOD_TRADE | Rs 170 |
| v5 | WIPRO | LONG | 179.9→180.1 | Rs 14 | EXIT_TOO_EARLY | Rs 167 |
| v5 | HCLTECH | LONG | 1,315.3→1,322.8 | Rs 105 | GOOD_TRADE | Rs 160 |
| v5 | BHEL | LONG | 432.9→427.6 | Rs -79 | WRONG_DIRECTION | Rs 158 |
| v5 | ADANIPOWER | SHORT | 213.2→212.1 | Rs 136 | GOOD_TRADE | Rs 149 |
| v5 | TCS | LONG | 2,321.7→2,333.1 | Rs 103 | GOOD_TRADE | Rs 139 |
| v5 | CGPOWER | LONG | 893.1→882.0 | Rs -67 | WRONG_DIRECTION | Rs 134 |
