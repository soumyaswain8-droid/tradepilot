# Trade Audit & Bear-Day Solution — 2026-08-05

*Regime: **BULL*** — generated 15:35:36

## Bottom line

- **Realized P&L today: Rs -2,866** across 117 trades (117 long / 0 short)
- **Rs left on the table: Rs 16,022** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 11,192**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 6,150**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 67 | 67/0 | 31 | Rs -1,190 | Rs 8,184 |
| v5_classic | 50 | 50/0 | 21 | Rs -1,676 | Rs 7,838 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 64 | Rs -5,597 | Rs 11,297 |
| EXIT_TOO_EARLY | 21 | Rs 490 | Rs 3,014 |
| GOOD_TRADE | 31 | Rs 2,408 | Rs 1,413 |
| HELD_LOSER | 1 | Rs -168 | Rs 298 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| ZYDUSWELL | AVOID | -3.6% | Rs 1,080 |
| QUESS | AVOID | -2.65% | Rs 795 |
| STAR | AVOID | -2.43% | Rs 729 |
| DIVISLAB | AVOID | -2.29% | Rs 687 |
| NAUKRI | AVOID | -2.11% | Rs 633 |
| TATACOMM | AVOID | -1.73% | Rs 519 |
| GRSE | AVOID | -1.55% | Rs 465 |
| PGEL | AVOID | -1.47% | Rs 441 |
| PETRONET | AVOID | -1.42% | Rs 426 |
| PHOENIXLTD | AVOID | -1.25% | Rs 375 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 6,150 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | ICICIGI | LONG | 1,723.5→1,692.4 | Rs -653 | WRONG_DIRECTION | Rs 1,306 |
| v5_classic | ICICIGI | LONG | 1,723.5→1,692.4 | Rs -653 | WRONG_DIRECTION | Rs 1,306 |
| v5 | JUBLFOOD | LONG | 477.8→480.0 | Rs 147 | EXIT_TOO_EARLY | Rs 1,025 |
| v5_classic | JUBLFOOD | LONG | 477.6→480.0 | Rs 157 | EXIT_TOO_EARLY | Rs 1,025 |
| v5 | RADICO | LONG | 4,555.0→4,499.2 | Rs -446 | WRONG_DIRECTION | Rs 893 |
| v5_classic | RADICO | LONG | 4,555.0→4,499.2 | Rs -446 | WRONG_DIRECTION | Rs 893 |
| v5 | NHPC | LONG | 82.3→80.8 | Rs -416 | WRONG_DIRECTION | Rs 832 |
| v5_classic | NHPC | LONG | 82.3→80.8 | Rs -416 | WRONG_DIRECTION | Rs 832 |
| v5_classic | CONCOR | LONG | 525.8→519.9 | Rs -218 | WRONG_DIRECTION | Rs 437 |
| v5_classic | LODHA | LONG | 1,257.2→1,247.1 | Rs -212 | WRONG_DIRECTION | Rs 424 |
| v5 | CONCOR | LONG | 525.8→519.9 | Rs -189 | WRONG_DIRECTION | Rs 378 |
| v5_classic | POWERINDIA | LONG | 32,515.0→32,335.0 | Rs -180 | WRONG_DIRECTION | Rs 360 |
| v5_classic | LTF | LONG | 324.4→320.1 | Rs -168 | WRONG_DIRECTION | Rs 335 |
| v5 | LODHA | LONG | 1,258.0→1,250.0 | Rs -168 | HELD_LOSER | Rs 298 |
| v5 | LTF | LONG | 324.4→320.1 | Rs -142 | WRONG_DIRECTION | Rs 284 |
