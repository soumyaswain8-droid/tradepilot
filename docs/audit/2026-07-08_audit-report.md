# Trade Audit & Bear-Day Solution — 2026-07-08

*Regime: **BEAR*** — generated 15:35:16

## Bottom line

- **Realized P&L today: Rs 0** across 12 trades (12 long / 0 short)
- **Rs left on the table: Rs 0** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 0**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 0**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 10 | 10/0 | 0 | Rs 0 | Rs 0 |
| v5_classic | 2 | 2/0 | 0 | Rs 0 | Rs 0 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| LOSS_OTHER | 12 | Rs 0 | Rs 0 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*


## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | NAUKRI | LONG | 1,159.1→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | PERSISTENT | LONG | 4,887.4→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | HAVELLS | LONG | 1,226.0→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | SWIGGY | LONG | 262.8→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | HDFCLIFE | LONG | 573.0→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | LTM | LONG | 3,865.4→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | JUBLFOOD | LONG | 455.1→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | TORNTPHARM | LONG | 4,865.7→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | ADANIENSOL | LONG | 1,653.7→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5 | CHOLAFIN | LONG | 1,855.9→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5_classic | LODHA | LONG | 1,094.6→None | Rs 0 | LOSS_OTHER | Rs 0 |
| v5_classic | HCLTECH | LONG | 1,167.1→None | Rs 0 | LOSS_OTHER | Rs 0 |
