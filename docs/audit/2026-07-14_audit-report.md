# Trade Audit & Bear-Day Solution — 2026-07-14

*Regime: **SIDEWAYS*** — generated 15:35:38

## Bottom line

- **Realized P&L today: Rs 1,253** across 102 trades (41 long / 61 short)
- **Rs left on the table: Rs 12,103** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 6,495**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 11,226**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 57 | 24/33 | 34 | Rs 1,053 | Rs 5,512 |
| v5_classic | 45 | 17/28 | 20 | Rs 200 | Rs 6,591 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 20 | Rs -2,161 | Rs 4,321 |
| GOOD_TRADE | 38 | Rs 4,276 | Rs 2,847 |
| SHORTED_RISER | 23 | Rs -1,087 | Rs 2,174 |
| EXIT_TOO_EARLY | 16 | Rs 419 | Rs 2,049 |
| IGNORED_SIGNAL | 4 | Rs -194 | Rs 697 |
| LOSS_OTHER | 1 | Rs 0 | Rs 15 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| THERMAX | AVOID | -6.09% | Rs 1,827 |
| HCLTECH | AVOID | -4.46% | Rs 1,338 |
| LODHA | AVOID | -4.29% | Rs 1,287 |
| JMFINANCIL | AVOID | -3.38% | Rs 1,014 |
| GODREJIND | AVOID | -3.31% | Rs 993 |
| TATAELXSI | AVOID | -3.3% | Rs 990 |
| HDFCAMC | AVOID | -3.24% | Rs 972 |
| HDFCLIFE | AVOID | -3.17% | Rs 951 |
| KPITTECH | AVOID | -3.11% | Rs 933 |
| ATUL | AVOID | -3.07% | Rs 921 |

## Prescription — flip a bear day

2. **Short selection:** 23 shorts hit risers (Rs 2,174 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 11,226 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | ASIANPAINT | SHORT | 2,652.1→2,640.0 | Rs 145 | EXIT_TOO_EARLY | Rs 721 |
| v5_classic | UNIONBANK | LONG | 170.4→168.2 | Rs -277 | WRONG_DIRECTION | Rs 553 |
| v5_classic | KOTAKBANK | LONG | 384.6→380.4 | Rs -267 | WRONG_DIRECTION | Rs 533 |
| v5 | ADANIENSOL | LONG | 1,695.9→1,690.3 | Rs -95 | IGNORED_SIGNAL | Rs 401 |
| v5_classic | MOTHERSON | LONG | 144.7→141.4 | Rs -196 | WRONG_DIRECTION | Rs 391 |
| v5_classic | GROWW | LONG | 208.2→206.7 | Rs -192 | WRONG_DIRECTION | Rs 383 |
| v5_classic | CONCOR | LONG | 463.9→483.8 | Rs 594 | GOOD_TRADE | Rs 368 |
| v5_classic | CANBK | LONG | 129.3→127.0 | Rs -168 | WRONG_DIRECTION | Rs 336 |
| v5 | ASTRAL | LONG | 1,371.1→1,356.3 | Rs -163 | WRONG_DIRECTION | Rs 326 |
| v5_classic | HDFCLIFE | LONG | 574.5→564.2 | Rs -163 | WRONG_DIRECTION | Rs 326 |
| v5 | BDL | SHORT | 1,272.8→1,279.6 | Rs -150 | SHORTED_RISER | Rs 299 |
| v5 | GROWW | SHORT | 206.3→206.0 | Rs 20 | EXIT_TOO_EARLY | Rs 289 |
| v5_classic | VOLTAS | LONG | 1,349.5→1,334.1 | Rs -139 | WRONG_DIRECTION | Rs 277 |
| v5_classic | IOC | LONG | 139.9→138.2 | Rs -133 | WRONG_DIRECTION | Rs 266 |
| v5 | PFC | LONG | 405.4→406.1 | Rs 48 | EXIT_TOO_EARLY | Rs 262 |
