# Trade Audit & Bear-Day Solution — 2026-06-15

*Regime: **SIDEWAYS*** — generated 15:36:22

## Bottom line

- **Realized P&L today: Rs 5,348** across 94 trades (45 long / 49 short)
- **Rs left on the table: Rs 13,028** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 5,878**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,239**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 52 | 26/26 | 32 | Rs 2,791 | Rs 6,964 |
| v5_classic | 42 | 19/23 | 30 | Rs 2,557 | Rs 6,064 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| GOOD_TRADE | 47 | Rs 8,448 | Rs 5,155 |
| WRONG_DIRECTION | 16 | Rs -1,753 | Rs 3,506 |
| SHORTED_RISER | 11 | Rs -1,186 | Rs 2,372 |
| EXIT_TOO_EARLY | 15 | Rs 297 | Rs 1,202 |
| IGNORED_SIGNAL | 5 | Rs -457 | Rs 793 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 389 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| AUROPHARMA | AVOID | -4.38% | Rs 1,314 |
| ZEEL | AVOID | -3.65% | Rs 1,095 |
| NMDC | AVOID | -2.71% | Rs 813 |
| GODFRYPHLP | AVOID | -2.69% | Rs 807 |
| VEDL | AVOID | -2.31% | Rs 693 |
| NATCOPHARM | AVOID | -1.89% | Rs 567 |
| INDUSTOWER | AVOID | -1.89% | Rs 567 |
| NTPC | AVOID | -1.64% | Rs 492 |
| ZYDUSLIFE | AVOID | -1.5% | Rs 450 |
| TORNTPHARM | AVOID | -1.47% | Rs 441 |

## Prescription — flip a bear day

2. **Short selection:** 11 shorts hit risers (Rs 2,372 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 389 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,239 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | GVT&D | SHORT | 4,781.5→4,846.5 | Rs -325 | SHORTED_RISER | Rs 650 |
| v5_classic | KALYANKJIL | LONG | 370.4→378.3 | Rs 490 | GOOD_TRADE | Rs 521 |
| v5 | KALYANKJIL | LONG | 370.4→378.3 | Rs 466 | GOOD_TRADE | Rs 496 |
| v5_classic | BPCL | LONG | 315.3→310.1 | Rs -237 | WRONG_DIRECTION | Rs 474 |
| v5 | BPCL | LONG | 315.4→310.1 | Rs -220 | WRONG_DIRECTION | Rs 441 |
| v5_classic | LTF | LONG | 296.2→294.3 | Rs -203 | WRONG_DIRECTION | Rs 407 |
| v5 | AUROPHARMA | SHORT | 1,446.8→1,415.9 | Rs 494 | GOOD_TRADE | Rs 398 |
| v5_classic | GVT&D | SHORT | 4,781.5→4,846.5 | Rs -195 | SHORTED_RISER | Rs 390 |
| v5_classic | FEDERALBNK | SHORT | 313.8→316.0 | Rs -184 | SHORTED_RISER | Rs 369 |
| v5 | LTF | LONG | 296.1→294.4 | Rs -182 | WRONG_DIRECTION | Rs 364 |
| v5_classic | SRF | SHORT | 2,724.0→2,747.0 | Rs -161 | SHORTED_RISER | Rs 322 |
| v5 | HDFCAMC | LONG | 2,562.2→2,605.4 | Rs 432 | GOOD_TRADE | Rs 318 |
| v5_classic | HDFCAMC | LONG | 2,562.2→2,605.4 | Rs 432 | GOOD_TRADE | Rs 318 |
| v5 | ONGC | SHORT | 243.1→244.4 | Rs -155 | SHORTED_RISER | Rs 309 |
| v5 | SWIGGY | LONG | 259.1→261.8 | Rs 154 | GOOD_TRADE | Rs 300 |
