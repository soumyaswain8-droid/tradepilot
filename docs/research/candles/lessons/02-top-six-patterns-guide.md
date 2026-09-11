# Lesson 2: The BEST Candlestick Pattern Guide (22:59)

Video: https://www.youtube.com/watch?v=m4WOwgUMQuc · Transcript: `transcripts/m4WOwgUMQuc.txt`
Teacher's context: forex and crypto price-action trader. Claim: "99% of patterns don't work; these six do." Prefers **1-hour and higher** timeframes and says candle patterns are much less effective on lower timeframes. Every entry uses stop at the pattern's wick and take-profit at **2× the stop distance**.

## Reading a single candle (same base rules as lesson 1)
- Big body = one side dominant. Small body = contested.
- Long lower wick = strong buying pressure (sellers pushed down, buyers reclaimed). Long upper wick = strong selling pressure.
- Small body with equal wicks = neither side in control.
- Candles beat line charts because the wick shows a level was pierced and reclaimed, which a close-only line hides.

## The six patterns
| # | Pattern | Definition | Trade | Stop |
|---|---|---|---|---|
| 1 | **Engulfing** | small candle, then a larger opposite-colour candle whose **body fully covers** the first body. Bigger second candle = stronger. | reversal; enter at close of the engulfing candle | wick of the engulfing candle |
| 2 | **Pin bar** | one candle, small body, long wick on one side. Bullish: green, long lower wick. Bearish: red, long upper wick. | reversal; teacher waits for **one more candle in the new direction** before entering | end of the pin bar's wick |
| 3 | **Three-bar continuation** | big candle, then a small opposite-colour candle **no more than half** the first body, then another big candle closing beyond the second | continuation; enter at close of the third candle | wick of the second candle |
| 4 | **Three-bar reversal** | big full-bodied candle, a smaller same-colour candle, then a big opposite-colour candle. Strong when the third body ≥ the first body; weak when smaller | reversal; enter at close (or high) of the third candle | low/high of the second candle |
| 5 | **Breakout candles** | ≥3 small-bodied consolidation candles (any colour) then one large candle. More consolidation candles = higher success | continuation in breakout direction; enter at close of the breakout candle | open of the breakout candle |
| 6 | **Shrinking candles** | ≥3 same-colour candles each smaller than the last, then a large opposite candle, ideally closing beyond the second candle | reversal; enter at close of the large candle | beyond the previous candle |

## The strategy layer
- On their own the patterns are unreliable. Combine with a **key level**: support/resistance, trendline, dynamic level, Fibonacci. Two levels meeting is a **confluence** and reversals are more likely there.
- Procedure: identify the level → wait for price to return to it → require one of the six patterns pointing in the bounce direction → enter, stop at the pattern's extreme, target 2× stop.
- Worked examples: third touch of support confirmed by a three-bar reversal; support-turned-resistance plus a descending trendline confirmed by shrinking candles.

## Where it agrees and disagrees with lesson 1
- Agrees: wick logic, body logic, "confirm with the next candle" for the single-candle pin bar, 2:1 reward-to-risk, context (a level or a trend) is required.
- Disagrees on **timeframe**: lesson 1 trades 1-minute and 5-minute; lesson 2 says patterns are weak below 1 hour. This is a testable disagreement for our 5-minute engines.
- Lesson 2 formalises **engulfing** and the two **three-bar** patterns, which lesson 1 covers loosely as candle-over-candle after a reversal candle.

## Testable rules extracted
| ID | Rule | Direction | Entry | Stop | Target |
|---|---|---|---|---|---|
| G1 | Bullish / bearish engulfing (body covers prior body) | reversal | close of candle 2 | wick of candle 2 | 2R |
| G2 | Pin bar (wick ≥ 2× body, body in the opposite third) + one confirming candle | reversal | close of confirming candle | pin bar wick | 2R |
| G3 | Three-bar continuation (big, ≤½ opposite, big closing beyond) | continuation | close of candle 3 | wick of candle 2 | 2R |
| G4 | Three-bar reversal (big, small same colour, big opposite ≥ first) | reversal | close of candle 3 | extreme of candle 2 | 2R |
| G5 | Breakout candle after ≥3 small candles | continuation | close of breakout candle | open of breakout candle | 2R |
| G6 | Shrinking candles (3 same colour, each smaller) then large opposite closing beyond candle 2 | reversal | close of candle 4 | extreme of candle 3 | 2R |
| G7 | Key-level filter: G1–G6 only within a band around a prior swing high/low or prior-day high/low | filter | | | |
| G8 | Timeframe test: run G1–G6 on 5-minute, 15-minute, hourly and daily bars and compare | test | | | |
