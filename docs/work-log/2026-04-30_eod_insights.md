# EOD Insights — 2026-04-30

## Current Roadmap Phase
- **Week 2** — Position size 15% → 20% of pool budget
- **Target**: Rs 18,000 to Rs 22,000
- **Gate**: P&L scales linearly with position size?

## Today vs 3-Day Baseline

| Engine | Today P&L | Trades | WR | Baseline avg |
|--------|----------:|-------:|---:|-------------:|
| v4 | Rs -34,555 | 40 | 15% | Rs +22,625 |
| v5 | Rs -16,735 | 22 | 14% | Rs +7,893 |
| v5_classic | Rs -14,344 | 23 | 22% | Rs +5,774 |
| v5_6 | Rs -13,315 | 19 | 37% | Rs +6,445 |
| v5_7 | Rs -15,015 | 24 | 25% | Rs +10,570 |

## Insights & Actions

- ⚠ Combined P&L Rs -93,963 is -269% vs baseline. Investigate.
- ● v5 vs v5_classic gap Rs +2,391 (narrowing but not closed).
- ⚠ v4 win rate dropped to 15% (6W/34L). Below 60% is abnormal.
- ⚠ v5_6 win rate dropped to 37% (7W/12L). Below 60% is abnormal.
- ⚠ v5_7 win rate dropped to 25% (6W/18L). Below 60% is abnormal.
- ⚠ v5_classic win rate dropped to 22% (5W/18L). Below 60% is abnormal.
- ⚠ v5 trade count 22 vs baseline 68. May be throttled — check rejection logs.
- ⚠ v5_6 trade count 19 vs baseline 64. May be throttled — check rejection logs.
- ⚠ v5_7 trade count 24 vs baseline 65. May be throttled — check rejection logs.
- ⚠ v5_classic trade count 23 vs baseline 58. May be throttled — check rejection logs.
- ● Week 2 target not yet hit: v5 Rs -16,735 < Rs 18,000. Need: P&L scales linearly with position size?
