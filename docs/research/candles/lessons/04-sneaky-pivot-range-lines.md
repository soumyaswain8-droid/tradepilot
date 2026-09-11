# Lesson 4: "Trading Like an Idiot" / The Sneaky Pivot (26:13)

Video: https://www.youtube.com/watch?v=zspMXJVbfAY · Transcript: `transcripts/zspMXJVbfAY.txt`
Teacher's context: Doug, 26 years, US futures and stocks. One timeframe (15-minute), no indicators, four lines, 15 minutes a day. Shows two live trades: one full winner (AAOI, ran to the upper line by the close), one that reversed on him after a big open profit (GGLL, cut for a small gain).

## Setup: four lines, drawn before the open
- **Range high / range low** = the previous day's high and low.
- **Swing high / swing low** = the next higher high above the range high and the next lower low below the range low, found by scrolling back until a higher high or lower low appears. (On TradingView these are the "Rumors Magic Lines" indicator.)
- **Only trade at a line. Anywhere else, do nothing.** Upper two lines are sell zones (where sellers have shown up every time). Lower two are buy zones.
- Lines are **zones, not exact prices**. Slightly below the swing low still counts.
- If the opening candle is so large it has already eaten most of the daily range, use the opening 15-minute candle's own high and low as the lines instead.

## The daily rhythm the strategy relies on
- For the first 15 minutes price ping-pongs between the range high and range low testing both sides.
- Then one side breaks and price **immediately visits the swing level** on that side "almost every single time".
- The trade is to buy at the swing low or range low and ride back to the range high or swing high, or the mirror on the sell side.

## The three-candle framework (15-minute candles)
1. **Opening range candle**: a strong, bold first candle that drives into one of the lines. It tells you which side you will trade; you do not choose a bias.
2. **Sneaky candle**: the next candle (or the one after) prints the **opposite colour** at the line. It confirms the level held. On lower timeframes this looks like repeated wicks tapping the level.
3. **Entry candle**: usually the third candle, about 45 minutes in. **Entry when price crosses the high of the sneaky candle** (candle over candle, the same trigger as in lesson 1 and as the opening-range reversal in lesson 3).

## Stop and target
- **Stop under the "big buyer"**: just beneath the tested low (or above the tested high for shorts). The teacher's point: traders get stopped because they never drew the levels; a stop behind a level tested for 30 minutes rarely gets hit.
- **Target: the opposite line** (range high or swing high). Range-bound thinking: price goes back to where it came from.
- Patience: sometimes the level is tested for 45 minutes with many wicks before the move. As long as the low holds, the trade is valid.

## Where it agrees and disagrees
- Same trigger as lessons 1 and 3: reversal candle at a level, then candle-over-candle. Same stop logic: behind the level, not a fixed distance.
- Unlike lesson 3 it does not require the opening candle to be big relative to ATR; instead it requires the candle to reach a **pre-drawn level** (prior-day high/low or beyond).
- Unlike lesson 2 it is happy on 15-minute bars.
- The GGLL loss shows the failure mode: a fast 15-minute bar can reverse the whole move; the teacher held expecting a flag and gave back most of the gain.

## Testable rules extracted
| ID | Rule | Direction | Entry | Stop | Target |
|---|---|---|---|---|---|
| S1 | Opening 15-min candle reaches the prior-day low band (within 0.25 ATR), next 15-min candle closes green | long | break of the green candle's high | below the tested low | prior-day high |
| S2 | Mirror: opening candle reaches the prior-day high band, next candle closes red | short | break of the red candle's low | above the tested high | prior-day low |
| S3 | Same as S1/S2 on 5-minute bars with a 3-bar sneaky window, to compare timeframes | | | | |
| S4 | Control: no level requirement (any opposite-colour candle after the opening candle) to isolate the value of the level | | | | |
