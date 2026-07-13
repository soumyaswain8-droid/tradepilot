# Trade Audit & Bear-Day Solution — 2026-06-26

*Regime: **SIDEWAYS*** — generated 15:35:59

## Bottom line

- **Realized P&L today: Rs -401** across 40 trades (30 long / 10 short)
- **Rs left on the table: Rs 4,965** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 0**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 7,128**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 20 | 15/5 | 2 | Rs -367 | Rs 2,317 |
| v5_classic | 20 | 15/5 | 5 | Rs -34 | Rs 2,648 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| IGNORED_SIGNAL | 15 | Rs -723 | Rs 2,278 |
| LOSS_OTHER | 15 | Rs 0 | Rs 1,370 |
| EXIT_TOO_EARLY | 5 | Rs 0 | Rs 734 |
| HELD_LOSER | 3 | Rs -0 | Rs 379 |
| GOOD_TRADE | 2 | Rs 322 | Rs 204 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| MUTHOOTFIN | AVOID | -3.33% | Rs 999 |
| KITEX | AVOID | -3.25% | Rs 975 |
| JINDALSTEL | AVOID | -2.77% | Rs 831 |
| SOLARINDS | AVOID | -2.44% | Rs 732 |
| MAPMYINDIA | AVOID | -2.41% | Rs 723 |
| FORTIS | AVOID | -2.11% | Rs 633 |
| INDIGOPNTS | AVOID | -2.1% | Rs 630 |
| BPCL | AVOID | -1.88% | Rs 564 |
| IDEA | AVOID | -1.75% | Rs 525 |
| EMAMILTD | AVOID | -1.72% | Rs 516 |

## Prescription — flip a bear day

3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 7,128 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | MAXHEALTH | LONG | 1,132.5→1,123.3 | Rs -238 | IGNORED_SIGNAL | Rs 428 |
| v5_classic | HUDCO | LONG | 208.3→208.3 | Rs 0 | EXIT_TOO_EARLY | Rs 298 |
| v5 | HUDCO | LONG | 208.3→208.3 | Rs 0 | EXIT_TOO_EARLY | Rs 247 |
| v5 | MAXHEALTH | LONG | 1,127.0→1,123.3 | Rs -50 | IGNORED_SIGNAL | Rs 230 |
| v5 | M&M | LONG | 3,197.9→3,182.2 | Rs -126 | IGNORED_SIGNAL | Rs 210 |
| v5 | ASHOKLEY | LONG | 161.2→160.7 | Rs -70 | IGNORED_SIGNAL | Rs 205 |
| v5_classic | SIEMENS | LONG | 3,627.9→3,627.9 | Rs -0 | IGNORED_SIGNAL | Rs 186 |
| v5_classic | M&MFIN | LONG | 328.6→328.5 | Rs -0 | HELD_LOSER | Rs 173 |
| v5_classic | MARUTI | LONG | 13,820.0→13,745.0 | Rs -75 | IGNORED_SIGNAL | Rs 172 |
| v5 | FORTIS | SHORT | 954.8→954.8 | Rs 0 | LOSS_OTHER | Rs 170 |
| v5_classic | FORTIS | SHORT | 954.8→954.8 | Rs 0 | LOSS_OTHER | Rs 170 |
| v5_classic | ASHOKLEY | LONG | 160.7→160.7 | Rs -0 | IGNORED_SIGNAL | Rs 154 |
| v5_classic | TMCV | LONG | 426.2→431.9 | Rs 279 | GOOD_TRADE | Rs 152 |
| v5_classic | MOTHERSON | LONG | 151.7→151.7 | Rs 0 | EXIT_TOO_EARLY | Rs 152 |
| v5 | SWIGGY | SHORT | 240.8→240.8 | Rs 0 | LOSS_OTHER | Rs 145 |
