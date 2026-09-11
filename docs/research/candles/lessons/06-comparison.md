# What the five lessons agree on, where they differ, and what is testable

Sources: lessons 01 to 05 in this folder (full transcripts read, screens reviewed for lessons 1 to 4; lesson 5's screens pending a download fix).

## The common core (all five, in different words)

| Principle | L1 Warrior | L2 Six patterns | L3 Quick flip | L4 Sneaky pivot | L5 Rajesh 9:15 |
|---|---|---|---|---|---|
| A wick is the message: long lower wick = buyers absorbed a dip, long upper wick = sellers rejected a high | yes | yes | yes ("the big buyer stepped in") | yes ("look at the wicks tapping the low") | implied (open = low) |
| A single reversal candle is a signal, not an entry; **the next candle must confirm** by breaking the reversal candle's extreme | candle over/under candle | wait one more candle (pin bar) | enter on the break of the hammer | entry when price crosses the sneaky candle's high | enter when price breaks back through the open |
| Location beats shape: the same candle means nothing in a range and everything at a level or the end of a run | "dojis only matter when trending" | "combine with key levels" | outside the opening box | at the four lines only | at the day's open price |
| Stop goes behind the structure, not a fixed distance | below the hammer low | at the pattern wick | beyond the reversal wick | under the tested low | (course content) |
| Reward-to-risk of about 2 or a structural target | 2:1 | 2× stop | far edge of the box (≈2.7:1 in examples) | opposite line | 15-minute time exit |
| The first 90 minutes is where the money is | trades 07:00-11:00 | (prefers ≥1h charts) | first 90 min only | first 45 min | first 15 min |

## The disagreements, which are the interesting tests

1. **Opening move: trap or truth?** L3 (and L4 by construction) say the first 15-minute candle is engineered liquidity and gets reversed; trade against it once a reversal candle prints outside the range. L5 says the first minute's direction holds for 15 minutes; trade with it and leave at 09:30. Our engines' ORB logic sides with L5 but holds far longer. Test: continuation to 09:30 vs reversal after 09:30, on the same days and stocks.
2. **Timeframe.** L1 works on 1- and 5-minute bars. L2 says patterns are unreliable below 1 hour. L3/L4 use 15-minute for structure and 5-minute for entry. Test every pattern on 5-minute, 15-minute and daily bars.
3. **Which reversal candles count.** L1 has a full vocabulary (hammer, hanging man, shooting star, four dojis, spinning top). L3 keeps only two (hammer/inverted hammer, engulfing). L2 keeps six but they are mostly two- and three-bar structures. Test whether the extra names add anything beyond hammer + engulfing.
4. **Level source.** L2: swing support/resistance and trendlines. L3: today's opening range. L4: yesterday's high/low and the next swing beyond. L1: wick clusters. Test the key-level filter with prior-day high/low/close and the session's running high/low.
5. **Stock selection.** L1: news catalyst and crowd attention. L5: top gainers/losers at the open. L3: liquidity candle ≥ 25% of ATR. L4: any instrument. Test the gap and ATR filters.

## Patterns and rules carried into the backtest

| Family | Detector | Lesson |
|---|---|---|
| Single-candle reversal + confirmation | hammer, shooting star, doji at top, doji at bottom, pin bar (bull/bear) | L1, L2, L3 |
| Two-candle reversal | engulfing (bull/bear) | L2, L3 |
| Three-candle | three-bar reversal, three-bar continuation, shrinking candles, breakout candle | L2 |
| Multi-candle continuation | bull flag / bear flag (candle-over-candle after a 1-3 bar pullback) | L1 |
| Opening range | liquidity candle + reversal outside the box (Q), ORB continuation control (Q5) | L3 |
| Range lines | sneaky pivot at prior-day high/low on 15-minute bars (S) | L4 |
| Open price | open = high / open = low on the first 5-minute bar, exit 09:30 (R), plus longer holds as controls | L5 |
| Filters | trend run of 3 before the pattern; key-level band of 0.15 ATR; first 90 minutes only; top-decile gappers | L1, L2, L3, L5 |

Uniform exit model for the pattern families so they are comparable: entry at the next bar's open, stop at the lesson's level, target 2R, flat at the session end, 12 bps costs, ₹500 risk per trade. The opening-range strategies additionally use the exits their lessons prescribe.

## Not tested, and why
- Volume confirmation and MACD-above-signal (L1 slide): worth a follow-up; the first pass tests price structure alone.
- Trendlines and Fibonacci levels (L2): subjective to draw; prior-day and session levels stand in for them.
- Option premiums (L5): not in our data; results are on the underlying.
- Pre-market (L3): not applicable to NSE.
