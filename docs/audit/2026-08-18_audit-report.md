# Trade Audit & Bear-Day Solution — 2026-08-18

*Regime: **BULL*** — generated 15:35:25

## Bottom line

- **Realized P&L today: Rs -1,862** across 86 trades (86 long / 0 short)
- **Rs left on the table: Rs 5,783** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 5,783**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 48 | 48/0 | 16 | Rs -982 | Rs 3,033 |
| v5_classic | 38 | 38/0 | 5 | Rs -881 | Rs 2,750 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 58 | Rs -2,891 | Rs 5,783 |
| GOOD_TRADE | 21 | Rs 1,029 | Rs 0 |
| LOSS_OTHER | 7 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | VBL | LONG | 441.9→437.3 | Rs -465 | WRONG_DIRECTION | Rs 929 |
| v5 | ADANIENSOL | LONG | 1,626.0→1,603.6 | Rs -448 | WRONG_DIRECTION | Rs 896 |
| v5 | DIXON | LONG | 14,321.0→14,100.0 | Rs -221 | WRONG_DIRECTION | Rs 442 |
| v5 | ADANIPORTS | LONG | 1,694.8→1,674.1 | Rs -207 | WRONG_DIRECTION | Rs 414 |
| v5 | AUROPHARMA | LONG | 1,643.0→1,632.8 | Rs -112 | WRONG_DIRECTION | Rs 224 |
| v5_classic | ADANIENSOL | LONG | 1,626.0→1,603.6 | Rs -112 | WRONG_DIRECTION | Rs 224 |
| v5_classic | SUZLON | LONG | 48.8→48.0 | Rs -109 | WRONG_DIRECTION | Rs 217 |
| v5 | SUZLON | LONG | 49.0→48.2 | Rs -102 | WRONG_DIRECTION | Rs 204 |
| v5 | MOTILALOFS | LONG | 963.1→946.6 | Rs -99 | WRONG_DIRECTION | Rs 198 |
| v5 | OIL | LONG | 483.8→481.5 | Rs -99 | WRONG_DIRECTION | Rs 198 |
| v5_classic | ONGC | LONG | 240.6→239.2 | Rs -97 | WRONG_DIRECTION | Rs 194 |
| v5_classic | LTF | LONG | 313.7→309.0 | Rs -94 | WRONG_DIRECTION | Rs 188 |
| v5_classic | BHEL | LONG | 434.6→428.8 | Rs -93 | WRONG_DIRECTION | Rs 186 |
| v5_classic | FORTIS | LONG | 915.9→912.0 | Rs -86 | WRONG_DIRECTION | Rs 172 |
| v5 | LTF | LONG | 313.2→309.0 | Rs -76 | WRONG_DIRECTION | Rs 151 |
