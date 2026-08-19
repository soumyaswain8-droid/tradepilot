# EOD 2026-08-19 + left-on-table

Fleet: 596 trades, gross **+₹3,296**, net **−₹2,927** — a day where the edge was real
and the fees ate all of it, the thesis wall in miniature. v5_wide +₹6,043 (third
strong day). v5_size **+₹831, #2** (day 7, median ₹88,543 above cliff, **104/300**).
v5_swing day 1: 7 positions holding. Guards: 5th clean session.

## Left on the table (538 matched trades, yfinance bars)

| Bucket | ₹ | Reading |
|:--|--:|:--|
| A. MFE ceiling | 32,946 | hindsight ceiling |
| — inside STOPLOSS trades | **17,383** | winners that round-tripped through stops — **the trail-arm band, second measurement, same shape as 08-17 (₹23.6k)** |
| B. Post-exit drift | **−2,993** | exits SAVED money again (2 for 2) |

The pattern is now consistent across both measured days: the giveback lives in the
gap between "in profit" and "trail armed at +1.0%", exits themselves are net savers,
and the arm0.3/0.25 fix from the paired backtest targets exactly bucket A's
biggest component. **The v5_trail shadow is the next build.**

## Operational gotcha (cost an hour tonight)

Kite's historical API backfills the previous session AFTER midnight — at 00:15,
2026-08-19 candles existed for small-caps but not RELIANCE/TCS-class names (not even
the daily bar). Bar-level EOD autopsies must run BEFORE midnight on Kite, or fall
back to yfinance after. Also: throttle Kite historical loops (~3 req/s) and never
swallow the exceptions — an unthrottled loop earlier silently lost 94% of symbols.
