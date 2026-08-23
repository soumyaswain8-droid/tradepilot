# hi52_break on survivorship-free data — KILLED

The pre-registered condition for the v5_hi52 lane was a rerun on the bhavcopy panel
(3,046 symbols including delisted, point-in-time top-200-liquidity universe, nothing
retuned). Verdict:

| | n | net/trade after 0.24% | t |
|:--|--:|--:|--:|
| Train (<2025) | 907 | +4.056% | +4.91 |
| **Holdout (2025+)** | **298** | **−1.019%** | **−0.95** |

**FAILS. No v5_hi52 lane.** The biased holdout's +1.97% was survivorship almost in its
entirety: **+2.99%/trade of phantom edge** from testing on today's index members.

## The reasoning error worth keeping

Yesterday I argued the 2025+ holdout was "nearly clean" because membership ≈ current
there. Wrong, and instructively: survivorship operates INSIDE the holdout too —
names that joined the index during 2025-26 are included precisely for their winning
run-up, and the names that fell out are excluded for their losses. End-of-window
membership contaminates every window that ends at it. Only a point-in-time universe
is clean, anywhere.

## What remains true

- Train is strongly positive even survivorship-free (+4.06%, t=4.91): 2021-24 was a
  genuine breakout regime. 2025-26 is not (−1.02%). Regime-dependence, not noise —
  a breakout lane would need a regime gate to even be a candidate, and that is a new
  thesis requiring its own gate, not a patch to sneak this one through.
- The five delisting exits used last-close (optimistic); the honest number is thus
  an upper bound and it STILL fails.
- CNC fee correction shipped: v5_swing now charged 0.24% delivery in the terminal's
  accounting and its own backtest constant (was 0.0787 intraday — undercharging).
