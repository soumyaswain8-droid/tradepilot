# Trade Audit & Bear-Day Solution — 2026-07-10

*Regime: **SIDEWAYS*** — generated 15:35:23

## Bottom line

- **Realized P&L today: Rs 0** across 3 trades (3 long / 0 short)
- **Rs left on the table: Rs 0** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 0**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 2 | 2/0 | 0 | Rs 0 | Rs 0 |
| v5_classic | 1 | 1/0 | 0 | Rs 0 | Rs 0 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LOSS_OTHER | 3 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | KALYANKJIL | LONG | 445.5→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | PNB | LONG | 103.4→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5_classic | KALYANKJIL | LONG | 443.6→None | Rs 0 | LOSS_OTHER | Rs 0 |
