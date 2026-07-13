# Trade Audit & Bear-Day Solution — 2026-06-30

*Regime: **SIDEWAYS*** — generated 15:36:18

## Bottom line

- **Realized P&L today: Rs -3,344** across 142 trades (56 long / 86 short)
- **Rs left on the table: Rs 27,090** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 19,235**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 10,632**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 83 | 37/46 | 37 | Rs -1,198 | Rs 14,312 |
| v5_classic | 59 | 19/40 | 29 | Rs -2,146 | Rs 12,778 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| WRONG_DIRECTION | 27 | Rs -5,812 | Rs 11,622 |
| SHORTED_RISER | 45 | Rs -3,808 | Rs 7,613 |
| GOOD_TRADE | 42 | Rs 6,074 | Rs 5,866 |
| EXIT_TOO_EARLY | 24 | Rs 289 | Rs 1,562 |
| LOSS_OTHER | 1 | Rs 0 | Rs 264 |
| IGNORED_SIGNAL | 1 | Rs -60 | Rs 110 |
| HELD_LOSER | 2 | Rs -29 | Rs 53 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 350 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| KPITTECH | AVOID | -5.71% | Rs 1,713 |
| TATATECH | AVOID | -4.32% | Rs 1,296 |
| TATAELXSI | AVOID | -3.79% | Rs 1,137 |
| YESBANK | AVOID | -3.63% | Rs 1,089 |
| INFY | AVOID | -3.5% | Rs 1,050 |
| TATACONSUM | AVOID | -3.34% | Rs 1,002 |
| TCS | AVOID | -3.17% | Rs 951 |
| IDBI | AVOID | -2.83% | Rs 849 |
| HCLTECH | AVOID | -2.78% | Rs 834 |
| ASTRAL | AVOID | -2.37% | Rs 711 |

## Prescription — flip a bear day

2. **Short selection:** 45 shorts hit risers (Rs 7,613 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 350 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 10,632 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5_classic | BHARATFORG | LONG | 2,170.9→2,077.3 | Rs -1,123 | WRONG_DIRECTION | Rs 2,246 |
| v5 | BHARATFORG | LONG | 2,170.9→2,077.3 | Rs -1,030 | WRONG_DIRECTION | Rs 2,059 |
| v5 | KPITTECH | SHORT | 712.2→695.8 | Rs 869 | GOOD_TRADE | Rs 1,402 |
| v5_classic | KPITTECH | SHORT | 712.2→695.8 | Rs 869 | GOOD_TRADE | Rs 1,402 |
| v5_classic | NATIONALUM | LONG | 347.4→339.2 | Rs -574 | WRONG_DIRECTION | Rs 1,148 |
| v5 | KEI | LONG | 5,452.0→5,342.5 | Rs -548 | WRONG_DIRECTION | Rs 1,095 |
| v5_classic | KEI | LONG | 5,452.0→5,342.5 | Rs -548 | WRONG_DIRECTION | Rs 1,095 |
| v5 | HINDZINC | SHORT | 519.1→529.2 | Rs -332 | SHORTED_RISER | Rs 663 |
| v5 | MCX | LONG | 2,914.5→2,873.5 | Rs -287 | WRONG_DIRECTION | Rs 574 |
| v5_classic | HINDZINC | SHORT | 519.1→527.4 | Rs -272 | SHORTED_RISER | Rs 544 |
| v5 | COCHINSHIP | SHORT | 1,427.6→1,441.3 | Rs -247 | SHORTED_RISER | Rs 493 |
| v5_classic | COCHINSHIP | SHORT | 1,427.6→1,441.3 | Rs -247 | SHORTED_RISER | Rs 493 |
| v5_classic | MCX | LONG | 2,914.5→2,873.5 | Rs -246 | WRONG_DIRECTION | Rs 492 |
| v5 | LICHSGFIN | SHORT | 556.5→561.2 | Rs -211 | SHORTED_RISER | Rs 422 |
| v5_classic | LICHSGFIN | SHORT | 556.5→561.2 | Rs -211 | SHORTED_RISER | Rs 422 |
