# Lesson 1: How to Read Candlestick Patterns (Warrior Trading, 54:55)

Video: https://www.youtube.com/watch?v=dvetF0H3pNo · Transcript: `transcripts/dvetF0H3pNo.txt`
Teacher's context: US small-cap day trader, 1-minute and 5-minute charts, trades breaking-news stocks, average hold about 5 minutes. Claims 65-70% hit rate on a 2:1 reward-to-risk.

## Anatomy and the two base rules
- A candle carries open, high, low, close. The shape is the story of the buyer/seller battle for that period.
- **Upper wick = bearish** (sellers pushed price back down). **Lower wick = bullish** (buyers bought the dip back). Best bullish candle: opens at the low, closes at the high, no upper wick.
- **Long body = strong sentiment, small body = weak.** Bigger candles mean more emotion; the teacher wants emotion because it brings volatility.

## Single-candle names
| Name | Shape | Where it matters | Meaning |
|---|---|---|---|
| Long body | large body, small wicks | anywhere | strong conviction in the candle's direction |
| Short body | small body | anywhere | weak conviction |
| Hammer | small body near the top, long lower wick, at the **bottom of a decline** | after a run of red candles | buyers hammered out a base; a buy signal once confirmed |
| Hanging man | same shape, red, at the **top of an uptrend** | after a run of green candles | first sign of weakness |
| Shooting star | small body near the bottom, long upper wick, at the top | after an uptrend | price rejected the high; reversal likely; red is stronger than green |
| Gravestone doji | open ≈ close at the low, long upper wick | top of a move | rejection, worse than a shooting star |
| Dragonfly doji | open ≈ close at the high, long lower wick | bottom of a move | buyers absorbed the dip |
| Long-legged doji | open ≈ close, long wicks both sides | top or bottom | pure indecision |
| Standard doji | small cross | top or bottom | indecision |
| Spinning top | small real body, wicks both sides | anywhere | indecision, weaker than a doji |

**Context names the candle.** The same shape is a hammer at the bottom and a hanging man at the top.

## Two rules the teacher writes on the board
1. **Dojis only matter when the stock is trending.** In a sideways range the market is already indecisive, so a doji adds nothing. They matter at the top or bottom of a move as a possible reversal.
2. **Hammers, shooting stars and hanging men only matter in a strong trend.** Same logic.

## Two-candle triggers (the actual entry and exit rules)
- **Candle over candle**: the current candle breaks the **high of the previous candle**. That is the buy trigger. Colour of the previous candle does not matter.
- **Candle under candle**: the current candle breaks the **low of the previous candle**. That is the exit for longs and the short trigger.
- A reversal candle (hammer, doji, shooting star) is only a **signal**; it needs the next candle to **confirm** by breaking over or under it. For a hanging man with a long lower wick, use the break of the body's low rather than waiting for the wick low.
- Candle-over-candle in a sideways range is meaningless. It only counts after a pullback within a trend.

## Multi-candle setups
- **Bull flag** (the teacher's bread-and-butter): catalyst → two long green candles → a doji or shooting star at the top → two small red pullback candles → ideally a hammer → **entry on the first candle to make a new high** over the previous candle. Stop at the pullback low. First target: high of day. Target 2:1 reward to risk, so break-even is a 33% hit rate.
- **ABCD**: a bull flag that rallies back to the prior high (B), fails, pulls back again (C), and breaks out on the second attempt (D). The longer consolidation coils energy; breakouts from ABCD are often larger. Enter at C only if there is room to the prior high; otherwise enter on the break of the high with the stop at the pullback low.
- **Moving-average pullback**: after repeated failed attempts at the high, wait for a pullback to the 9 EMA on the 1-minute or 5-minute chart; that becomes support for the final break.

## Support and resistance from wicks
- Clusters of **topping tails** mark resistance (supply). Clusters of **bottoming tails** mark support (demand). The hammer's low is the new base.
- Price moves in waves; the pivots at the top and bottom of each wave are the only places worth analysing.

## Instrument selection (not a candle rule, but stated as a precondition)
- Trade only what is trending, volatile, and watched by many people (catalyst, news). Patterns on ignored stocks resolve poorly because nobody else sees them.
- Real charts are messy; judge the message of the whole shape, not textbook perfection.

## From the screens (frames in `../frames/dvetF0H3pNo/`)
- Whiteboard hammer (00749): five shrinking red candles stepping down, then a small green body with a long lower wick. The lesson's hammer is drawn **green**, at the end of a run.
- Doji board (01027): three ascending green bodies then a red doji drawn as a line with a small cross; the "standard doji" is a plain cross.
- Real chart, SPWR 1-minute (01147): the entry is marked "as candle breaks high of previous candle" on a hammer-like bar after a shallow pullback. Two confirmations are written on the slide that the narration skipped: **"Light Vol Selling"** on the pullback bars and **"MACD is above signal line"**. Both are filters we can test.
- Supply/demand board (01443): topping tails at resistance drawn as a cluster of upper wicks; bottoming tails at support as lower wicks; the entry is the green candle over the last red candle at the support cluster.
- Bull flag board (02845): two tall green bodies, a doji, one small red, then a small green with a lower wick. Pullback is 1 to 2 candles, not more.
- Bull flag / ABCD / MA pullback board (03096): a long sideways stretch of small candles riding a rising 9 EMA before the breakout candle.

## Testable rules extracted
| ID | Rule | Direction | Confirmation | Exit |
|---|---|---|---|---|
| W1 | Hammer after ≥3 red candles, then next candle breaks hammer high | long | candle over candle | stop below hammer low; target 2R |
| W2 | Shooting star / gravestone after ≥3 green candles, then next candle breaks its low | short (or exit long) | candle under candle | stop above star high; target 2R |
| W3 | Doji at top of a ≥3-candle run, then break of doji low | exit long / short | candle under candle | 2R |
| W4 | Bull flag: 2 long green, 1-3 small red, first candle over previous high | long | candle over candle | stop at pullback low; target prior high / 2R |
| W5 | Trend filter: W1-W4 only when the preceding move is a run (not a range) | filter | | |
| W6 | Candle-under-candle after an up-run as an exit signal for open longs | exit | | |
