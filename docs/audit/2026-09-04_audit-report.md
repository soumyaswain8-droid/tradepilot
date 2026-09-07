# Trade Audit & Bear-Day Solution — 2026-09-04

*Regime: **BEAR*** — generated 15:38:23

## Bottom line

- **Realized P&L today: Rs -1,145** across 62 trades (15 long / 47 short)
- **Rs left on the table: Rs 6,384** (recoverable with the right side + timing)
- **Flip every wrong-direction trade → +Rs 4,486**
- **Short the dashboard's top SELLs (Rs 30,000 ea) → Rs 8,349**

## Where each engine went wrong

| Engine | Trades | L/S | Wins | Realized | On table |
|--------|-------:|----:|-----:|---------:|---------:|
| v5 | 62 | 15/47 | 30 | Rs -1,145 | Rs 6,384 |

## The leak, by mistake class

| Mistake | Count | Realized | Rs on table |
|---------|------:|---------:|------------:|
| SHORTED_RISER | 24 | Rs -1,686 | Rs 3,372 |
| EXIT_TOO_EARLY | 12 | Rs 409 | Rs 1,263 |
| LONG_IN_BEAR | 7 | Rs -557 | Rs 1,114 |
| GOOD_TRADE | 18 | Rs 689 | Rs 552 |
| LOSS_OTHER | 1 | Rs 0 | Rs 83 |

## What would have made money today

*The scorer emitted **0 SELL** signals today — 237 stocks were labelled AVOID (its only bearish output). Shorting the AVOID stocks that actually fell most:*

| Symbol | Label | Day % | Short P&L |
|--------|-------|------:|----------:|
| KEI | AVOID | -8.95% | Rs 2,685 |
| QUESS | AVOID | -3.22% | Rs 966 |
| SRF | AVOID | -2.67% | Rs 801 |
| ARVIND | AVOID | -2.48% | Rs 744 |
| HDFCAMC | AVOID | -2.09% | Rs 627 |
| WELCORP | AVOID | -1.93% | Rs 579 |
| PRESTIGE | AVOID | -1.75% | Rs 525 |
| DIVISLAB | AVOID | -1.62% | Rs 486 |
| TVSMOTOR | AVOID | -1.59% | Rs 477 |
| LAURUSLABS | AVOID | -1.53% | Rs 459 |

## Prescription — flip a bear day

1. **BEAR regime gate (long-only engines):** 7 longs in a bear regime cost Rs 1,114 on the table. In BEAR, block new longs unless the stock is a confirmed dashboard BUY with positive day momentum.
2. **Short selection:** 24 shorts hit risers (Rs 3,372 on the table). Only short dashboard SELLs with negative day return AND price below VWAP — never short a stock that's green on the day.
3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / 121 HOLD / 237 AVOID / **0 SELL**. The engines literally cannot follow a short signal because none is produced — that is why a bear day becomes a long-only bloodbath. Add a real SELL tier to the scorer.
4. **Act on the bearish list:** shorting the AVOID stocks that fell would have made Rs 8,349 today with Rs 30,000 per name. The information was there; nothing acted on it.

## Worst 15 trades (by Rs on table)

| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |
|--------|--------|------|-----------|---------:|-------|---------:|
| v5 | SRF | SHORT | 2,544.0→2,581.6 | Rs -376 | SHORTED_RISER | Rs 752 |
| v5 | PAYTM | LONG | 1,648.8→1,660.1 | Rs 136 | EXIT_TOO_EARLY | Rs 451 |
| v5 | INDIANB | SHORT | 881.0→889.0 | Rs -185 | SHORTED_RISER | Rs 370 |
| v5 | LENSKART | LONG | 692.2→684.7 | Rs -165 | LONG_IN_BEAR | Rs 330 |
| v5 | AUROPHARMA | SHORT | 1,626.4→1,638.7 | Rs -160 | SHORTED_RISER | Rs 320 |
| v5 | SWIGGY | LONG | 275.0→277.8 | Rs 129 | EXIT_TOO_EARLY | Rs 313 |
| v5 | DABUR | SHORT | 377.7→379.9 | Rs -143 | SHORTED_RISER | Rs 286 |
| v5 | GODREJCP | SHORT | 868.1→875.3 | Rs -137 | SHORTED_RISER | Rs 274 |
| v5 | HUDCO | SHORT | 180.0→181.1 | Rs -120 | SHORTED_RISER | Rs 239 |
| v5 | COALINDIA | SHORT | 412.6→415.0 | Rs -115 | SHORTED_RISER | Rs 230 |
| v5 | VEDL | LONG | 273.8→272.2 | Rs -115 | LONG_IN_BEAR | Rs 229 |
| v5 | COCHINSHIP | LONG | 1,515.2→1,506.4 | Rs -106 | LONG_IN_BEAR | Rs 211 |
| v5 | COLPAL | SHORT | 1,833.9→1,844.5 | Rs -95 | SHORTED_RISER | Rs 191 |
| v5 | COCHINSHIP | LONG | 1,502.0→1,507.4 | Rs 65 | EXIT_TOO_EARLY | Rs 186 |
| v5 | DIXON | SHORT | 14,189.0→14,274.0 | Rs -85 | SHORTED_RISER | Rs 170 |
