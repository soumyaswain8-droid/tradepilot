# Lesson 3: The "ONE CANDLE" Scalping Strategy / Quick Flip Scalper (23:27)

Video: https://www.youtube.com/watch?v=XFtayhPIdEs · Transcript: `transcripts/XFtayhPIdEs.txt`
Teacher's context: Carl, 20 years, indices (Nasdaq 100) and large stocks (NVIDIA), CFDs. Claims most of a trader's money is made in the **first 90 minutes**. Strategy taught to him in 2011.

## The idea in one line
The first 15-minute candle of the day is often an engineered "liquidity" move that pulls retail traders in and triggers their stops; **most of the time that candle gets reversed**. Trade the reversal, not the move.

## The three steps
1. **Box the opening range.** On a 15-minute chart, wait for the first candle of the session to close. Draw a box from its high to its low and extend it forward for about 75 minutes (the trade window is the first 90 minutes).
2. **Confirm it is a liquidity candle.** Take the daily ATR(14). If the opening candle's high-to-low range is **≥ 25% of the daily ATR**, it is a liquidity (manipulation) candle. Around 22-23% is acceptable. Should be a fast, one-directional candle; a big wick against the move weakens it but does not disqualify.
3. **Enter on a reversal candle outside the box.** Drop to a 5-minute chart (1 to 5 minutes all work). Wait for one of two candles, **outside the box, on the far side of the opening move, within 90 minutes of the open**:
   - **Hammer** (after a red opening move; long lower wick = the big buyer absorbed the liquidity) or **inverted hammer** (after a green opening move; long upper wick).
   - **Bullish or bearish engulfing** (large candle fully engulfing the previous smaller one).
   A hammer **inside the box is invalid**. If no such candle appears within 90 minutes, no trade that day.

## Entry, stop, target
- Hammer / inverted hammer: enter on the **break of the candle** (at the open of the next candle once the high/low is taken). Stop just beyond the wick.
- Engulfing: place the entry **at the high (or low) of the previous small candle**, so the fill itself confirms the engulf. Stop beyond the engulfing candle's low/high.
- **Target: the opposite edge of the opening-range box** (the box gives two natural targets, its high and its low). Worked examples: 28-point stop for a 212-point win on Nasdaq; ₹2.65 stop for ₹7 target on NVIDIA (about 2.7:1).
- Once in profit and near the target, move the stop to the near box edge.

## Claims worth testing
- Reversal frequency: "almost every time it reverses" (shows four consecutive days on Nasdaq).
- Liquidity candles are **more prominent in individual stocks** than in indices.
- Including the 15 minutes before the open (where available) raises the hit rate. Not applicable in India; pre-open is an auction.

## Relation to our engines
- Our engines already use an opening-range breakout (ORB) signal: they enter **with** the opening move. This lesson says the opening move is the trap and the edge is **against** it once a reversal candle prints outside the range. Directly testable on our 5-minute bars: ORB-continuation vs ORB-reversal.
- The Floor's SWEEP_RECLAIM (low broken then reclaimed) is the same phenomenon: a stop hunt followed by absorption.

## Testable rules extracted
| ID | Rule | Direction | Entry | Stop | Target |
|---|---|---|---|---|---|
| Q1 | Opening 15-min candle range ≥ 25% of daily ATR(14) (liquidity candle) | filter | | | |
| Q2 | After a green Q1, first inverted hammer or bearish engulfing on 5-min **above** the box within 90 min | short | break of the candle low | above its high | box low |
| Q3 | After a red Q1, first hammer or bullish engulfing on 5-min **below** the box within 90 min | long | break of the candle high | below its low | box high |
| Q4 | Same as Q2/Q3 but target = box near edge (conservative) and 2R (standard) for comparison | | | | |
| Q5 | Control: ORB continuation (enter with the opening move on the break of the box) with the same stop and target sizing | with-move | | | |
