<div class="masthead">

![](../../brand/letterhead/tradepilot-mark.svg)

<div class="doctitle">TradePilot</div>
<div class="docsub">Weekly Review · 3–7 August 2026</div>
<div class="doccode">TP-WK-32 · Soumya Swain · Confidential</div>

</div>

<div class="masthead-rule"></div>
<div class="masthead-rule-b"></div>

## What this covers

Five trading sessions, every engine, every rupee — measured from the trade records
rather than recalled. This is the first week TradePilot is treated as a product in its
own right and the first with a revenue target attached, so the closing sections say
plainly what that target requires and how far the system is from it.

<div class="kv">

| | |
|:--|:--|
| **Sessions** | 5 (Mon 3 – Fri 7 August) |
| **Engines run** | 18 distinct, 11–17 on any given day |
| **Trades placed** | 3,526 |
| **Net result** | **−₹17,162** |
| **Changes shipped** | 50 |
| **Findings that changed the plan** | 5 |

</div>

> **A note on the number.** The −₹17,162 is after trading costs, with costs corrected
> for the engines that have never booked any. Two experiments started mid-week and
> have only two sessions behind them; their figures are shown but should not be read
> as results.

## At a glance

```
┌──────────────────────────────────────────────────────────────────────┐
│  FOUND - AND IT CHANGES EVERYTHING                                   │
│    The strategy's entry timing is measurably worse than picking a    │
│    random moment in the same stock on the same day.                  │
│                                                                      │
│  THE REAL SHAPE OF THE PROBLEM                                       │
│    There IS an edge. It earns 0.069% per trade. Costs take 0.120%.   │
│    We are not broken - we are smaller than the toll.                 │
│                                                                      │
│  RUNNING                                                             │
│    Order-book collection began Friday. First real data in hand.      │
└──────────────────────────────────────────────────────────────────────┘
```

## Where the week went

<div class="spec">

| Day | Trades | Net | What happened |
|:--|--:|--:|:--|
| Mon 3 | 539 | **+₹17,273** | Best day of the week |
| Tue 4 | 478 | −₹21,291 | Gave it all back |
| Wed 5 | 853 | −₹16,903 | Losses before costs, on a flat market |
| Thu 6 | 817 | +₹5,628 | |
| Fri 7 | 839 | −₹1,869 | |

</div>

The primary engine lost ₹933 across the week. In isolation that reads badly; against
the preceding eight weeks — which ran −1,894, +1,377, −7,575, −4,634, +805, −6,233,
+681 — it is an ordinary week, not a bad one. That consistency is itself the finding:
the system has not been getting worse. It has been flat-to-negative since June and
this week did not change that.

## What was found

### The entry signal is worse than a coin flip

Holding the stock, the day and the stop-loss constant and changing only *when* the
position was opened, a randomly chosen moment beat our timed entry by 0.18% per trade.
Across five independent random draws, random won all five; giving those entries our
own stop-loss did not close the gap. This is not a weak signal — it is one that fires
reliably after the move it was meant to catch, a median of 126 minutes late, with only
0.76% of the day's range still available.

### And the reason is structural

Every one of the six inputs the strategy scores on describes what has already
happened: relative strength means the stock already outperformed, the breakout
measure only fires once the range is broken, and the institutional-flow figure is
published at the end of the day, so today's reading is yesterday's information.
Nothing in the score looks forward. The 126-minute lag is not a defect in the code —
it is the arithmetic of that input set.

### The edge is real. It is just smaller than the toll

This is the week's most useful correction. The strategy earns **0.069% per trade**
before costs, with a 47% win rate against a 42% break-even — genuinely above water.
Trading costs take **0.120%**. The toll is 1.75 times the edge.

"No edge" and "edge smaller than the toll" are different problems with different
answers, and the system had been diagnosed as the first. It is the second.

### Holding longer does not fix it

The obvious response — pay the toll once, capture a bigger move — was tested against
every entry since June. Held three days the trades looked profitable; subtracting what
the market did over the same window, the profit was **zero to four decimal places**.
Not skill, but being invested while the index rose 4.1%.

## What was built

Fifty changes shipped. The substantial ones: the universe was audited against the
exchange's lists and four dead symbols removed; the full 4,353-stock market was made
browsable while the engines stay restricted to what they can fill; a portfolio view
with a per-stock ledger went live; and the data feed moved to the licensed broker
connection, 22 times faster and agreeing with the old source to the paisa. Three
infrastructure faults were also fixed, each of which had been reporting success while
doing nothing — the launch gate blocked the fleet from an open, the dashboard served
an eighteen-day-old market, and the order-book collector ran two days producing zero
bytes while recording success every time.

## The ₹1 crore target

The target is ₹1 crore in a year from product revenue and trading profit together,
with trading returns staged — 30% to begin, then 40%, then 50%, and capital scaled up
once 70% is cleared. Measured against where the engines actually are:

<div class="spec">

| Return goal | Needed per day | Needed per trade | Versus today |
|:--|--:|--:|:--|
| 30% | 0.105% | ₹23.52 | 4.6× the current gross edge |
| 40% | 0.135% | ₹30.17 | 5.4× |
| 50% | 0.162% | ₹36.36 | 6.2× |
| 70% | 0.212% | ₹47.60 | 7.5× |

</div>

Today the primary engine returns **−0.031% per day**, or −7.7% annualised. The first
milestone is therefore not 30% — it is **zero**. Every multiple above assumes the
gross edge first clears the cost, and it does not yet.

On the revenue side the arithmetic is friendlier and does not depend on the strategy
working: ₹1 crore is roughly 835 subscribers at ₹999 a month held for a year, or 278
at ₹2,999. That is a distribution problem rather than a trading one — with the
condition that the product must describe honestly what it does, which today means not
selling a signal that loses to a coin flip.

## What to be aware of

The strategy has produced no measurable skill at any horizon tested — intraday or
multi-day, long or short. Four findings reported during the week collapsed when
re-tested, every one because the measurement used information the system would not
have had at the time; that pattern is now a standing check rather than a lesson. The
live-money plan is on hold — it existed to promote whichever engine won a
head-to-head, and every engine has lost money since June. One dependency remains
manual: the broker connection expires at 6am daily and must be renewed by hand, and a
missed renewal now costs a day of order-book collection.

## Next week

1. **Protect the collection.** Friday produced the first real order-book data, 65 MB.
   Two to three weeks are needed before it can be tested, and it silently collected
   nothing for two days before that was caught. Verify daily.
2. **Test the two cheap ideas left** — whether index futures move before their
   constituents, and whether an overnight gap predicts the day. Both use data held.
3. **Leave the engines alone** — they are the out-of-sample record — and **start the
   product track**, which does not depend on the edge working.

<div class="closing">

Evidence · 3,526 trades, 18 engines, 5 sessions, costs 12 bps and corrected where
unbooked · 50 commits · entry-vs-random 5 seeds t 2.76–4.24 · timeframe 1,924 entries
vs same-window index · liquidity validated on 18,053 closed trades · from trade
records, 9 Aug. Soumya Swain · soumya@suryaai.co.in

</div>
