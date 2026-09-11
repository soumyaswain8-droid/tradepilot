# Lesson 5: "This 9:15 AM Options Strategy Works Everyday" ft. Rajesh Jain (1:14:13)

Video: https://www.youtube.com/watch?v=GAr-2Cw4LIQ · Transcript: `transcripts/GAr-2Cw4LIQ.txt` (auto-translated from Hindi; wording is rough, the rules below are reconstructed from the worked examples)
Teacher's context: Indian trader since 2000, options buyer, ex-broker pro desk. About half the video is mindset (book the profit, "say goodnight at 9:30", trade one lot, ATM only). The setup itself is short.

## The setup, step by step
1. **Stock selection at 09:15**: open NSE India → market data → gainers and losers → filter **Securities in F&O**. Take the first stock at the top of the losers (he prefers the short side) or gainers. Skip slow movers. Any liquid F&O stock works; Nifty "moves very little", stocks pay more.
2. **Wait 30 to 40 seconds after the open.** No action before that. Note the **open price**.
3. **The trigger is the open price.** Example (Power India, 09:15): opened 35,435, ticked up to a high of 35,500, then **broke back below the open**. That break confirms "it will not go up any more" → sell. Mirror for longs: dips below the open then breaks back above → buy.
4. **Entry timing**: on the 1-minute chart, at the 40th to 50th second of the first minute, or at the open of the second minute. "Even the 4th minute is fine; if you did not get an entry, leave the market."
5. **Instrument**: buy the **ATM option** (put for a short view, call for a long view). Never OTM ("cheap is not good"), never ITM. One lot.
6. **Exit at 09:30, no exceptions.** Claim: "if the first candle is red it mostly remains red for 15 minutes." The 15-minute candle's colour is decided by that first-minute break. Book whatever is there at 09:30 (₹2,000 to ₹8,000 per lot on his examples; 30 to 50% on the premium).
7. **Stop loss**: exists, not specified numerically in the video (it is in the paid course). His claim on frequency: on 20 trading days, about 3 stop-loss days.

## The validity condition (from the failed example)
- Eicher on the same day: "it opened in the middle of the first candle, so **no entry**." The setup needs the open to be at one extreme of the first candle: **open ≈ high** (for the short) or **open ≈ low** (for the long). This is the classic Indian "open = high, sell / open = low, buy" rule, with the extra requirement that price must first probe beyond the open and then break back through it.
- On the option chart the same condition appears as "open and low are the same" for the call being bought.

## Market-structure claims made along the way (not rules, but the teacher's rationale)
- The first 15 minutes carry the day's biggest institutional flow; nothing in the market "happens suddenly", gaps are prepared overnight (GIFT Nifty, global markets), so the first move shows the direction of the informed money.
- FIIs move the market, DIIs stabilise it. Trade in the direction of the first move, "make friends with the rich".
- Every event day (budget, election) shows the first candle's direction too.

## Relation to lessons 3 and 4
This is the **opposite bet** to lesson 3. Lesson 3 says the opening move is a trap and trades the reversal after 15 minutes. Lesson 5 says the first minute's direction holds for 15 minutes and trades **with** it, exiting exactly when lesson 3 starts looking for the reversal. Both can be true at different horizons: continuation for 15 minutes, reversal after. That is directly testable on our bars.

## From the screens (frames in `../frames/GAr-2Cw4LIQ/`)
- 01162: the NSE "Live Analysis → Top 20 gainers/losers" page filtered to F&O securities, sorted by % change. Stock selection is literally the top row of this list.
- 01210 / 01956: Hitachi Energy (the "Power India" example) on TradingView, first a 1-minute then a 15-minute chart with volume. The first 15-minute candle of the session is a single decisive red bar; the 1-minute view shows the open, a brief tick above it, then the break below the open that he calls the entry.
- 02149: the same stock on 15-minute bars over several days; the opening bar of each day is visibly larger than the bars that follow, which is his "the first candle decides the 15 minutes" claim in picture form.
- 02707 / 02773: Nifty 50 on 15-minute bars and the Nifty 24000 call on 1-minute bars. The call's first minute has open = low and then rallies; the Nifty candle itself is small, which is why he says Nifty "moves very little" and prefers stocks.

## What we can and cannot test with our data
- We have 5-minute bars, not 1-minute. The first 5-minute candle's open versus its high/low approximates "open = high / open = low" (tolerance 0.1% of price). The 09:15 to 09:30 outcome is the close of the third 5-minute bar versus the open.
- Stock selection by top gainers/losers at the open is reproducible from our pre-open data (`prototype/data/preopen/<date>.json`) and from the first bar's gap versus the prior close.
- Option premiums are not in our data; test on the underlying and report the underlying move, then note that an ATM option would roughly double the percentage (delta ≈ 0.5, premium ≈ 2 to 3% of spot).

## Testable rules extracted
| ID | Rule | Direction | Entry | Exit | Note |
|---|---|---|---|---|---|
| R1 | First 5-min bar: open within 0.1% of its high | short | close of bar 1 (09:20) | 09:30 close | "open = high, sell" |
| R2 | First 5-min bar: open within 0.1% of its low | long | close of bar 1 (09:20) | 09:30 close | "open = low, buy" |
| R3 | Same as R1/R2 restricted to the day's top 10 gappers up/down (pre-open or first-bar gap) | | | | stock-selection claim |
| R4 | Does the 09:15 bar's colour hold through 09:30? Base rate across all stocks and days | | | | "first candle stays red for 15 minutes" |
| R5 | Hold beyond 09:30 (to 10:15, to close) as controls, to see whether 09:30 is the right exit or lesson 3's reversal takes over | | | | |
