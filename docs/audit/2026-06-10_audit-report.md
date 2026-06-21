# Trade Audit & Bear-Day Solution — 2026-06-10

*Regime: **BEAR*** — generated 15:36:01

## Bottom line

- **Realized P&L today: Rs -9,919** across 172 trades (99 long / 73 short)
- **Rs left on the table: Rs 42,125** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 36,636**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 14,001**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v4 | 71 | 71/0 | 8 | Rs -13,881 | Rs 33,018 |
| v5 | 54 | 16/38 | 32 | Rs 1,350 | Rs 4,988 |
| v5_classic | 47 | 12/35 | 31 | Rs 2,612 | Rs 4,119 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LONG_IN_BEAR | 73 | Rs -16,710 | Rs 33,670 |
| GOOD_TRADE | 58 | Rs 8,118 | Rs 3,551 |
| SHORTED_RISER | 28 | Rs -1,606 | Rs 3,211 |
| EXIT_TOO_EARLY | 13 | Rs 278 | Rs 1,693 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 389 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| OIL | AVOID | -10.21% | Rs 3,063 |
| BHEL | AVOID | -4.85% | Rs 1,455 |
| INDIANB | AVOID | -4.74% | Rs 1,422 |
| KALYANKJIL | AVOID | -4.6% | Rs 1,380 |
| ZEEL | AVOID | -4.36% | Rs 1,308 |
| INDUSINDBK | AVOID | -4.21% | Rs 1,263 |
| ECLERX | AVOID | -3.91% | Rs 1,173 |
| COALINDIA | AVOID | -3.41% | Rs 1,023 |
| YESBANK | AVOID | -3.29% | Rs 987 |
| MUTHOOTFIN | AVOID | -3.09% | Rs 927 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 73 longs in a bear regime cost Rs 33,670 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 28 shorts hit risers (Rs 3,211 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 389 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 14,001 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v4 | PATANJALI | LONG | 425.0→417.4 | Rs -551 | LONG_IN_BEAR | Rs 1,102 |
| v4 | SBICARD | LONG | 589.8→581.2 | Rs -439 | LONG_IN_BEAR | Rs 877 |
| v4 | PHOENIXLTD | LONG | 1,801.7→1,765.6 | Rs -433 | LONG_IN_BEAR | Rs 866 |
| v4 | ASTRAL | LONG | 1,550.5→1,522.0 | Rs -428 | LONG_IN_BEAR | Rs 855 |
| v4 | COLPAL | LONG | 2,091.8→2,054.0 | Rs -416 | LONG_IN_BEAR | Rs 832 |
| v4 | HDFCLIFE | LONG | 566.0→557.9 | Rs -408 | LONG_IN_BEAR | Rs 815 |
| v4 | RELIANCE | LONG | 1,297.8→1,274.9 | Rs -389 | LONG_IN_BEAR | Rs 779 |
| v4 | VBL | LONG | 534.7→527.4 | Rs -390 | LONG_IN_BEAR | Rs 779 |
| v4 | CGPOWER | LONG | 921.5→905.4 | Rs -373 | LONG_IN_BEAR | Rs 745 |
| v4 | BANKINDIA | LONG | 148.7→146.2 | Rs -368 | LONG_IN_BEAR | Rs 735 |
| v4 | POLICYBZR | LONG | 1,528.4→1,504.0 | Rs -366 | LONG_IN_BEAR | Rs 732 |
| v4 | LTF | LONG | 266.8→263.2 | Rs -366 | LONG_IN_BEAR | Rs 731 |
| v4 | TATACAP | LONG | 325.9→320.1 | Rs -365 | LONG_IN_BEAR | Rs 731 |
| v4 | COFORGE | LONG | 1,431.5→1,409.0 | Rs -360 | LONG_IN_BEAR | Rs 720 |
| v4 | DABUR | LONG | 436.9→430.0 | Rs -356 | LONG_IN_BEAR | Rs 712 |
