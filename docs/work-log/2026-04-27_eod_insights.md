# EOD Insights — 2026-04-27

## Current Roadmap Phase
- **Week 2** — Position size 15% → 20% of pool budget
- **Target**: Rs 18,000 to Rs 22,000
- **Gate**: P&L scales linearly with position size?

## Today vs 3-Day Baseline

| Engine | Today P&L | Trades | WR | Baseline avg |
|--------|----------:|-------:|---:|-------------:|
| v4 | Rs +0 | 0 | 0% | Rs -1,578 |
| v5 | Rs +737 | 46 | 50% | Rs +21,794 |
| v5_classic | Rs +286 | 40 | 52% | Rs +5,865 |
| v5_2 | Rs +0 | 0 | 0% | — |
| v5_3 | Rs +0 | 0 | 0% | Rs -9 |
| v5_6 | Rs +880 | 58 | 48% | Rs +26,819 |
| v5_7 | Rs +435 | 48 | 46% | Rs +23,295 |

## Insights & Actions

- ⚠ Combined P&L Rs +2,337 is -97% vs baseline. Investigate.
- ✅ v5 vs v5_classic gap closed to Rs -451. Rust fix holding.
- ⚠ v5_6 win rate dropped to 48% (28W/30L). Below 60% is abnormal.
- ⚠ v5_7 win rate dropped to 46% (22W/26L). Below 60% is abnormal.
- ⚠ v5_classic win rate dropped to 52% (21W/19L). Below 60% is abnormal.
- ● Week 2 target not yet hit: v5 Rs +737 < Rs 18,000. Need: P&L scales linearly with position size?
- ⚠ v4 took 0 trades today. Likely dormant or over-filtered.
- ⚠ v5_3 took 0 trades today. Likely dormant or over-filtered.
