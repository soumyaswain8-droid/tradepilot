# Trade Audit & Bear-Day Solution — 2026-06-12

*Regime: **BEAR*** — generated 15:36:25

## Bottom line

- **Realized P&L today: Rs 1,167** across 92 trades (26 long / 66 short)
- **Rs left on the table: Rs 11,227** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 6,446**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 5,178**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 53 | 16/37 | 25 | Rs 2,114 | Rs 6,276 |
| v5_classic | 39 | 10/29 | 13 | Rs -947 | Rs 4,951 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 40 | Rs -1,780 | Rs 3,559 |
| GOOD_TRADE | 22 | Rs 4,023 | Rs 3,073 |
| LONG_IN_BEAR | 14 | Rs -1,443 | Rs 2,887 |
| EXIT_TOO_EARLY | 16 | Rs 368 | Rs 1,708 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 389 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| NESTLEIND | AVOID | -3.29% | Rs 987 |
| OIL | AVOID | -2.69% | Rs 807 |
| ONGC | AVOID | -2.53% | Rs 759 |
| TECHM | AVOID | -2.45% | Rs 735 |
| COFORGE | AVOID | -1.91% | Rs 573 |
| PERSISTENT | AVOID | -1.29% | Rs 387 |
| ICICIGI | AVOID | -0.98% | Rs 294 |
| SBILIFE | AVOID | -0.76% | Rs 228 |
| TATACONSUM | AVOID | -0.71% | Rs 213 |
| POWERGRID | AVOID | -0.65% | Rs 195 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 14 longs in a bear regime cost Rs 2,887 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 40 shorts hit risers (Rs 3,559 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 389 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 5,178 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ABCAPITAL | LONG | 336.6→344.9 | Rs 412 | GOOD_TRADE | Rs 722 |
| v5 | AUBANK | LONG | 963.3→970.0 | Rs 94 | EXIT_TOO_EARLY | Rs 692 |
| v5_classic | LT | LONG | 4,000.1→3,939.3 | Rs -243 | LONG_IN_BEAR | Rs 486 |
| v5 | BPCL | LONG | 286.4→297.0 | Rs 735 | GOOD_TRADE | Rs 469 |
| v5_classic | HINDPETRO | LONG | 378.8→373.8 | Rs -230 | LONG_IN_BEAR | Rs 460 |
| v5_classic | TMCV | LONG | 372.6→385.9 | Rs 477 | GOOD_TRADE | Rs 437 |
| v5 | ENRIN | LONG | 3,412.5→3,501.9 | Rs 268 | GOOD_TRADE | Rs 429 |
| v5_classic | GODREJPROP | LONG | 1,674.8→1,651.4 | Rs -187 | LONG_IN_BEAR | Rs 374 |
| v5_classic | MOTILALOFS | LONG | 874.6→867.0 | Rs -182 | LONG_IN_BEAR | Rs 365 |
| v5_classic | LODHA | LONG | 895.0→881.0 | Rs -181 | LONG_IN_BEAR | Rs 363 |
| v5 | DLF | LONG | 563.0→576.3 | Rs 359 | GOOD_TRADE | Rs 348 |
| v5_classic | LENSKART | SHORT | 495.8→498.7 | Rs -151 | SHORTED_RISER | Rs 302 |
| v5 | HCLTECH | SHORT | 1,101.7→1,110.3 | Rs -138 | SHORTED_RISER | Rs 275 |
| v5_classic | COFORGE | SHORT | 1,378.1→1,387.2 | Rs -127 | SHORTED_RISER | Rs 255 |
| v5 | PIDILITIND | LONG | 1,540.5→1,530.5 | Rs -120 | LONG_IN_BEAR | Rs 240 |
