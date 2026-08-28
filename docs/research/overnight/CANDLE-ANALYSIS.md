# Candle Analysis — the 12 chart cases, bar by bar

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — overnight research |
| **Purpose** | Identify the breakout candle in each of the 12 runs mechanically, measure its geometry, and count how often the same candle failed |
| **Data** | Kite Connect daily bars, fetched 2026-08-28 (live token) |
| **Companion to** | `CHART-EVIDENCE.md` — same 12 symbols, same run windows |
| **Version** | `v1.0.0` |
| **Created** | 2026-08-28 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## Method — stated before the results, so it cannot be fitted to them

**The breakout candle is defined in code, not chosen by eye.**

> **Breakout** = the first session after the run low whose **close exceeds the highest
> high of the preceding 20 sessions**, with a reset rule: after one signal fires, no
> further signal is counted until the close has dropped back below the 20-day MA.

**Why 20 sessions.** Twenty sessions is one trading month and is already the window every
other measure in this pack uses (the 20-day MA, the 20-day volume average), so the
breakout is measured against the same clock as its own confirmation. Nothing was tuned.

**Why this and not the MA50 reclaim.** Both were computed. The MA50 reclaim fires earlier
on 11 of 12 names — but it fires *while price is still inside the prior range*, so it is a
mean-reversion marker, not a breakout, and on 2 of the 12 (`ORIENTTECH`, `NIBE`, both
recent listings) the MA50 does not exist at the entry bar at all, which makes it unusable
as a common definition and produces no failure census for those names. The 20-day
channel breakout is defined for any symbol with 20 bars of history. The MA50 reclaim date
is still reported per symbol as a secondary marker.

**Geometry is measured, not asserted.** Every label carries its ratio so it can be
checked: marubozu = body ≥ 90% of range; long-body bullish = bullish and body ≥ 60%;
hammer = lower wick ≥ 2× body and upper wick ≤ body; inverted hammer = the mirror; doji =
body ≤ 10% of range; bullish engulfing = up candle whose body fully covers a prior down
candle's body; gap-up = open above the prior high. Where nothing matched, the section says
**no named pattern**. One of the twelve says exactly that.

**The failure census.** The same signal rule is run over the **126 sessions (~6 months)
before the run low**. Each signal is scored: **worked** = the close gained ≥ +10% within
20 sessions without first closing below the breakout candle's own low; **failed** =
anything else (stopped out below the candle's low, or stalled without reaching +10%).
Two names (`ORIENTTECH`, `NIBE`) had only 7 and 5 sessions of listed history in that
window and are excluded from the census rather than scored as zero.

---

## Synthesis — read this first

### The selection bias, in plain words

**These 12 names were selected by searching for the biggest gains in the scan.** Every
candle described below is, by construction, a candle that worked. This document therefore
shows **what winning breakouts looked like** and says **nothing whatsoever about how often
a candle of that description appears and fails.** No geometry statistic, no volume median,
no "dominant pattern" in the sections below is evidence that the pattern is tradeable.
They are descriptions of survivors.

There is exactly **one unbiased number in this analysis**, and it is the failure census,
because that census was run over a period chosen by the calendar (the six months before
each low) rather than by outcome. It is the lead result:

### The lead result: 0 of 11

| Prior-breakout census (126 sessions before each run low) | Value |
|:--|--:|
| Names with a usable 6-month lookback | 10 of 12 |
| Breakout signals that fired under the identical rule | **11** |
| Of those, **worked** (+10% in 20 sessions, no stop) | **0** |
| Of those, **failed** | **11 (100%)** |
| Best any of them managed within 20 sessions | +10.1% (`EDELWEISS`, 2024-04-22 — stopped out first) |
| Median failed prior breakouts, per name | **1** |
| Loosening the rule to "touched +10% at any point, ignore the stop" | still only **1 of 11** |

Traded mechanically on these same twelve names, this pattern was **wrong every time
before it was right once.** That is the hit rate the chart pack cannot show, and it is
the number to carry forward.

### The finding that matters more than the hit rate

The failed candles were **not distinguishable from the winning ones.**

| Median across | Body / range | Volume vs 20-day avg |
|:--|--:|--:|
| The 12 winning breakout candles | 0.63 | **2.92x** |
| The 11 failed prior breakout candles | 0.63 | **2.92x** |

Identical to two decimal places, by accident of the data rather than design. And it goes
further: on **4 of the 8 names that had any prior signal** — `HFCL`, `EDELWEISS`,
`JINDALPOLY`, `PLAZACABLE` — a **failed** candle had *both* a bigger body *and* more
volume than the candle that went on to double the stock. `JINDALPOLY` is the extreme:
its failed 2025-08-29 signal printed a 71% body on **18.16x** average volume and went
nowhere; the signal that preceded a +122% run printed a 63% body on **0.43x** volume.

**Candle geometry and volume confirmation did not separate the winners from the losers in
this sample.** Any strategy that selects breakouts on body size or volume multiple needs
to defend itself against that.

### The descriptive statistics (conditioned on success — not predictive)

| Measure across the 12 winning breakouts | Median |
|:--|--:|
| Sessions from the run low to the breakout candle | 6.5 |
| How far above the low the breakout closed | +25.8% |
| Volume vs its own 20-day average | 2.92x |
| Body as a share of range | 0.63 |
| **Breakout close → run peak (still on the table)** | **+100.3%** |
| **Peak → 60 sessions later (the give-back)** | **−22.4%** |

Geometry counts across the 12: **marubozu 3** (`DBREALTY` 95%, `CONFIPET` 92%,
`SINDHUTRAD` 97%), **long-body bullish 4** (`HFCL`, `OLAELEC`, `JINDALPOLY`, `NACLIND`),
**gap-up 5** (overlapping), **bullish engulfing 1**, **hammer 1**, **no named pattern 1**.
Seven of twelve had a body ≥ 60% of range and **11 of 12 closed green** — the single
exception, `ORIENTTECH`, gapped up and closed below its open.

So: a wide green body is the modal shape, present in 7 of 12. That is a real majority but
it is **not a signature** — it is roughly what any up-session in a rising stock looks
like, the failed candles shared it, and with n=12 selected for success the split is not
distinguishable from noise. **Volume confirmation was near-universal in direction but not
in degree**: 11 of 12 were at or above their 20-day average, but only 8 of 12 reached
1.5x, and one winner (`JINDALPOLY`, 0.43x) broke out on *less than half* its normal volume.

### The exit is not the free part

Nine of twelve were lower 60 sessions after the peak, median **−22.4%**. Three were
higher — `NACLIND` (+31.2%), `HFCL` (+23.3%) and `CONFIPET` (+2.8%) — and nothing at the
breakout candle distinguished those three from `ORIENTTECH` (−42.2%) or `NIBE` (−38.0%).
Two of the give-back figures are measured at 56 and 59 sessions rather than 60 because
the data ends 2026-08-27; both are labelled in their sections.

---
## HFCL — breakout 2026-02-18

| | |
|:--|--:|
| Breakout candle | **2026-02-18** — 17 sessions after the low |
| OHLC | 72.12 / 74.10 / 71.40 / 73.79 |
| Volume | 25.1M = **1.30x** its 20-day average |
| Body / range | **62%** (upper wick 11%, lower 27%) |
| Geometry | **long-body bullish** (body 62% of range) |
| Close vs MA20 / MA50 | +7.9% / +10.6% |
| Prior 20 sessions | Rs59.82–73.50, 20.2% wide, slope +0.86%/day |
| Above the run low | +21.1% |
| **Breakout close → peak** | **+170.3%** (Rs199.43, 2026-06-03) |
| MA50 reclaim (secondary) | 2026-01-30, 3 sessions after the low |
| **Failed prior breakouts, 6m** | **1 of 1** |
| Peak +60 sessions | **+23.3%** |

**Structure.** Not a tight base — a 20% range that had already turned up (+0.86%/day) with
the breakout printing 8% above the MA20. Price had spent seventeen sessions climbing off
the low before it cleared the month's high, so this is a confirmation candle, not a turn.

**Why it moved.** On **17 February 2026** — one session *before* the breakout candle —
HFCL and subsidiary HTL announced an optical fibre cable order worth **Rs60.95 crore**
from a private telecom operator, described as the second order win in a week
(*NewsX*). The bars agree: 17 Feb closed +4.5% on 32.1M shares, the heaviest print of the
month. Caveat: order-size figures differ across outlets (*Goodreturns* cites a much larger
Rs1,366 cr HTL order, *Business Standard* Rs76 cr) and I could not reconcile them, so
treat the exact number as unverified. The direction of the news is confirmed; the
magnitude is not.

**The honest column.** The catalyst was public a full session before the mechanical
signal — this one was knowable. But the same rule fired once before, on **2025-09-16**,
on a **70% body and 2.28x volume** — a *stronger-looking* candle than the winner — and it
was stopped out within 20 sessions having gained 1.5%. Score to date on this name: 1 for 2.

---

## OLAELEC — breakout 2026-04-02

| | |
|:--|--:|
| Breakout candle | **2026-04-02** — 2 sessions after the low |
| OHLC | 25.62 / 28.62 / 25.06 / 28.34 |
| Volume | 456M = **5.13x** its 20-day average |
| Body / range | **76%** (upper wick 8%, lower 16%) |
| Geometry | **long-body bullish** (body 76% of range) |
| Close vs MA20 / MA50 | +17.1% / +2.8% |
| Prior 20 sessions | Rs22.25–26.36, 17.1% wide, slope −0.00%/day |
| Above the run low | +24.3% |
| **Breakout close → peak** | **+73.1%** (Rs49.05, 2026-06-09) |
| MA50 reclaim (secondary) | 2026-04-02 — same candle |
| **Failed prior breakouts, 6m** | **1 of 1** |
| Peak +56 sessions | **−20.5%** (data ends 2026-08-27) |

**Structure.** A dead-flat 20-session range (slope −0.00%/day, 17% wide) after a −60%
collapse, broken by a single 13.8%-range session on five times normal volume. This is the
cleanest "flat base, violent exit" geometry in the pack, and the breakout came just two
sessions after the low — the trigger and the turn were almost the same event.

**Why it moved.** **No catalyst dated on or before 2 April was found.** The available
explanations — April VAHAN registrations of 12,166 units, +20% MoM against a 22% MoM
industry decline (*Univest*, *Multibagg.ai*), and commercialisation of the 4680-format
Bharat Cells (*India TV*, 10 April) — are all dated **9–10 April, a week after the
breakout**. They explain the run's continuation. They were not knowable on 2 April.

**The honest column.** One prior signal, **2026-01-02**, on an **86% body and 2.92x
volume** — a bigger body than the winner — stopped out after reaching +7.4%. On body size
alone the failed candle was the more convincing of the two.

---

## EDELWEISS — breakout 2024-07-30

| | |
|:--|--:|
| Breakout candle | **2024-07-30** — 6 sessions after the low |
| OHLC | 65.84 / 69.49 / 64.48 / 68.56 |
| Volume | 9.25M = **2.47x** its 20-day average |
| Body / range | **54%** (upper wick 19%, lower 27%) |
| Geometry | **bullish engulfing** (covers the prior down candle's body) |
| Close vs MA20 / MA50 | +5.9% / **−1.1%** |
| Prior 20 sessions | Rs59.41–67.99, 13.3% wide, slope −0.18%/day |
| Above the run low | +13.3% |
| **Breakout close → peak** | **+112.3%** (Rs145.53, 2024-09-30) |
| MA50 reclaim (secondary) | 2024-07-31, 7 sessions after the low |
| **Failed prior breakouts, 6m** | **3 of 3** |
| Peak +60 sessions | **−11.5%** |

**Structure.** The tightest base of the twelve — a 13.3% range drifting slightly down —
and the only breakout that cleared the 20-day channel while still **below** its own 50-day
MA (−1.1%). A trend filter keyed to the MA50 would have rejected this candle by one day.

**Why it moved.** **No catalyst was isolated for 30 July.** What is documented is Q1 FY25:
the earnings call was held **6 August 2024**, reporting consolidated PAT of Rs590 cr
(+17% YoY) and alternatives AUM +17% YoY to Rs5,635 cr; by **14 August** the stock hit a
52-week high, +33% on the month (*Equitymaster*, 16 Aug 2024). That is a week *after* the
breakout — continuation, not trigger.

**The honest column.** This name carries the worst prior record in the pack: **three**
signals in six months (2024-02-19, 2024-04-22, 2024-05-17), **all three failed**. Two of
them — 62% body/2.51x and 78% body/4.37x — beat the winner on *both* body and volume. The
April signal reached +10.1% before being stopped. Score: 1 for 4.

---

## DBREALTY — breakout 2025-03-21

| | |
|:--|--:|
| Breakout candle | **2025-03-21** — 4 sessions after the low |
| OHLC | 127.70 / 152.40 / 127.25 / 151.61 |
| Volume | 24.1M = **5.22x** its 20-day average |
| Body / range | **95%** (upper wick 3%, lower 2%) |
| Geometry | **marubozu** (body 95% of range) |
| Close vs MA20 / MA50 | +20.2% / +6.2% |
| Prior 20 sessions | Rs115.11–138.08, 18.3% wide, slope −0.29%/day |
| Above the run low | +29.1% |
| **Breakout close → peak** | **+66.7%** (Rs252.67, 2025-07-09) |
| MA50 reclaim (secondary) | 2025-03-21 — same candle |
| **Failed prior breakouts, 6m** | **2 of 2** |
| Peak +60 sessions | **−32.0%** |

**Structure.** The most emphatic single bar in the pack: a near-perfect marubozu with a
19.8% range, opening near the low and closing near the high on 5.2x volume, clearing the
20-day channel and the MA50 in one session. If any candle here deserves the textbook
label, it is this one.

**Why it moved.** **No catalyst found in public sources.** Three targeted searches over
the February–April 2025 window returned nothing dated that explains 21 March. Q4 FY25
results (net sales +347% YoY) came later — the quarter had not even closed on the
breakout date, so they cannot be the trigger. A 19.8%-range marubozu on 5x volume implies
*someone* knew something; the public record does not say what, and this note will not
invent it.

**The honest column.** Two prior signals, **both failed** — 2024-10-11 (62% body, 4.08x
volume, never went green) and 2024-12-04 (68% body, 1.58x, +3.6% then stopped). Neither
matched this bar's 95% body, which is the one case in the pack where geometry did
separate the winner from the losers.

---

## ORIENTTECH — breakout 2024-11-04

| | |
|:--|--:|
| Breakout candle | **2024-11-04** — 20 sessions after the low |
| OHLC | 290.85 / 292.75 / 280.45 / 286.70 |
| Volume | 1.21M = **3.37x** its 20-day average |
| Body / range | **34%** — and the close was **below the open** |
| Geometry | **gap-up** (+3.3% over the prior high); no body pattern matched |
| Close vs MA20 / MA50 | +10.0% / **MA50 undefined** |
| Prior 20 sessions | Rs224.60–281.65, 22.1% wide, slope +0.60%/day |
| Above the run low | +24.8% |
| **Breakout close → peak** | **+114.0%** (Rs613.50, 2025-01-20) |
| MA50 reclaim (secondary) | 2024-11-06, 22 sessions after the low |
| **Failed prior breakouts, 6m** | **census not possible** — only 7 sessions of listed history |

**Structure.** The odd one out. This is the **only breakout candle in the twelve that
closed red** — it gapped 3.3% above the prior high and then sold off into the close,
finishing 34% body, down on the day. It still cleared the 20-day channel on close, so the
rule fired. A trader waiting for a strong close would have skipped it and missed +114%.

**Why it moved.** **Anticipation of Q2 FY25 results.** The stock ran on 5–6 November
"amid heavy volumes on expectations of healthy earnings," with a board meeting scheduled
**11 November 2024** to approve results and consider an interim dividend (*Business
Standard*, 6 Nov 2024). Results confirmed it — total income Rs225.07 cr (+50.7% QoQ), PAT
Rs15.06 cr (+62.2% QoQ) — and the stock hit a 52-week high on 12 November (*Business
Standard*). The board-meeting date was public in advance; the numbers were not.

**The honest column.** **No failure count is available.** ORIENTTECH listed in August 2024
and had 7 sessions of history in the 126-session lookback. The hit rate on this name is
unmeasurable, and reporting it as "0 failures" would be a lie of omission.

---

## NIBE — breakout 2025-04-01

| | |
|:--|--:|
| Breakout candle | **2025-04-01** — 9 sessions after the low |
| OHLC | 1054.90 / 1093.40 / 1026.05 / 1093.40 |
| Volume | 77,415 = **1.11x** its 20-day average |
| Body / range | **57%** (upper wick **0%**, lower 43%) |
| Geometry | **gap-up** (+1.3% over the prior high), closed on its high |
| Close vs MA20 / MA50 | +18.1% / **MA50 undefined** |
| Prior 20 sessions | Rs761.50–1080.70, 34.7% wide, slope +0.11%/day |
| Above the run low | +42.3% |
| **Breakout close → peak** | **+83.0%** (Rs2,001, 2025-06-12) |
| MA50 reclaim (secondary) | 2025-04-25, 24 sessions after the low |
| **Failed prior breakouts, 6m** | **census not possible** — only 5 sessions of listed history |

**Structure.** The loosest "base" in the pack — a 34.7% range is not a consolidation, it
is a whipsaw. The breakout closed on its high with a zero upper wick, but the price had
already travelled **+42.3% off the low** by then, the second-largest entry cost here. It
also broke out on essentially *average* volume (1.11x), so the volume confirmation people
associate with this pattern was absent.

**Why it moved.** **No catalyst found in public sources.** NIBE has a genuine record of
defence order announcements — Rs57 cr from L&T (Mar 2023), a Rs292.69 cr Indian Army order
(Jan 2026), a Rs563 cr loiter-munition order (Aug 2026) — but **none of them fall in the
window around 1 April 2025**. They are listed here only to be explicit that they were
checked and rejected on date grounds, not used.

**The honest column.** As with ORIENTTECH, the failure census is **unmeasurable** — 5
sessions of history. Two of the twelve names, both the ones the chart pack flagged for
undefined MAs, also produce no hit-rate evidence. That is a systematic blind spot for
recent listings, not a coincidence.

---

## JINDALPOLY — breakout 2026-02-13

| | |
|:--|--:|
| Breakout candle | **2026-02-13** — 17 sessions after the low |
| OHLC | 440.00 / 460.00 / 433.25 / 456.95 |
| Volume | 114,384 = **0.43x** its 20-day average |
| Body / range | **63%** (upper wick 11%, lower 25%) |
| Geometry | **long-body bullish** (body 63% of range) |
| Close vs MA20 / MA50 | +13.0% / +2.3% |
| Prior 20 sessions | Rs365.00–447.35, 20.5% wide, slope +0.68%/day |
| Above the run low | +24.4% |
| **Breakout close → peak** | **+121.7%** (Rs1,012.90, 2026-03-18) |
| MA50 reclaim (secondary) | 2026-02-13 — same candle |
| **Failed prior breakouts, 6m** | **1 of 1** |
| Peak +60 sessions | **−31.4%** |

**Structure.** Textbook shape, one glaring defect: the breakout printed on **0.43x its
20-day average volume** — the only sub-1x volume breakout in the pack, and by some margin
the weakest confirmation. It still preceded a +122% run. Every volume-filter rule we own
would have vetoed this candle.

**Why it moved.** A **board meeting on 13–14 February 2026** — the breakout date itself —
approved Q3 FY26 results: standalone profit Rs75.4 cr against a consolidated loss of
Rs96.9 cr, the loss driven by the May 2025 Nashik plant fire and new labour-code costs
(*scanx.trade*). The nonwoven demerger to Global Nonwovens (board-approved Aug 2025) was
live in the same news cycle. Confidence: medium — the results landed on the day, but the
sharpest single-day moves around it (+7.2% on 6 Feb, +8.3% on 17 Feb, *marketsmojo*)
carry no stated reason.

**The honest column.** The single most instructive pair in this document. The one prior
signal — **2025-08-29** — fired on a **71% body and 18.16x average volume**, a far more
convincing bar than the winner, and it **stalled without reaching +10%**. Volume screamed
on the failure and whispered on the success.

---

## CONFIPET — breakout 2026-03-12

| | |
|:--|--:|
| Breakout candle | **2026-03-12** — 3 sessions after the low |
| OHLC | 29.80 / 35.49 / 29.35 / 35.45 |
| Volume | 9.38M = **10.73x** its 20-day average |
| Body / range | **92%** (upper wick 1%, lower 7%) |
| Geometry | **marubozu** (body 92% of range) |
| Close vs MA20 / MA50 | +12.4% / +8.2% |
| Prior 20 sessions | Rs28.06–34.56, 20.7% wide, slope −0.82%/day |
| Above the run low | +23.0% |
| **Breakout close → peak** | **+127.3%** (Rs80.57, 2026-06-04) |
| MA50 reclaim (secondary) | 2026-03-12 — same candle |
| **Failed prior breakouts, 6m** | **0 signals fired** (full 126-session lookback) |
| Peak +59 sessions | **+2.8%** (data ends 2026-08-27) |

**Structure.** A steadily falling 20-session range (−0.82%/day) reversed by a 20.8%-range
marubozu on **10.7x** volume — the second-heaviest confirmation in the pack. Combined with
`DBREALTY` and `SINDHUTRAD`, all three marubozu breakouts came on ≥5x volume.

**Why it moved.** **No catalyst found in public sources.** The move is well documented and
the *cause* is not: a 19.98% upper-circuit close and delivery volume of 27.39 lakh shares,
**+740.7% over the 5-day average** (*marketsmojo*) — but that is a description of the
buying, not a reason for it. No order win, results date, or policy item was found for the
window. Note a source discrepancy: *marketsmojo* dates the +19.98% close to 13 March at
Rs35.49; the Kite bars put the +19.84% close on **12 March at Rs35.45**, with Rs35.49 as
that day's *high*. Q4 FY26 results (PAT +37.5%) came later and explain continuation only.

**The honest column.** **Zero prior signals in a full six-month lookback** — the stock
never once closed above its 20-day high before this. No false starts to report, and none
to take comfort from either: an untested rule on this name.

---

## NACLIND — breakout 2024-12-10

| | |
|:--|--:|
| Breakout candle | **2024-12-10** — 11 sessions after the low |
| OHLC | 50.42 / 58.59 / 49.66 / 57.93 |
| Volume | 4.04M = **14.73x** its 20-day average |
| Body / range | **84%** (upper wick 7%, lower 9%) |
| Geometry | **long-body bullish** (84%) + **gap-up** (+2.2% over the prior high) |
| Close vs MA20 / MA50 | +21.6% / +19.7% |
| Prior 20 sessions | Rs44.92–49.91, **10.6% wide** — the tightest base in the pack |
| Above the run low | +26.8% |
| **Breakout close → peak** | **+231.1%** (Rs191.78, 2025-04-22) |
| MA50 reclaim (secondary) | 2024-12-03, 6 sessions after the low |
| **Failed prior breakouts, 6m** | **1 of 1** |
| Peak +60 sessions | **+31.2%** |

**Structure.** The best-formed setup here by a distance: a **10.6%-wide** twenty-session
coil, resolved by a gap-up 84%-body candle on **14.73x** average volume — the heaviest
confirmation of the twelve — closing 21.6% above the MA20. If the pack contains one candle
that a mechanical system should want to buy, this is it, and it went on to be the largest
move (+231% from the breakout close).

**Why it moved.** A verified two-stage catalyst. **On 10 December 2024 — the breakout date
itself** — the stock jumped ~7.8% to Rs57.32 after the company announced a board meeting
for **12 December** to consider fundraising via equity, warrants or preferential issue
(*Business Standard*). Warrants and shares were approved in January 2025. The far bigger
driver came later: on **12 March 2025**, Coromandel International agreed to acquire a
controlling **53% stake from promoter KLR Products at Rs76.7/share** (~Rs820 cr); the
stock rose 65% in four sessions (*Business Standard*, 17 Mar 2025). Only the first was
knowable at the breakout.

**The honest column.** One prior signal, **2024-06-14** — 55% body, 2.60x volume — reached
+6.7% and was stopped out. The winner beat it on both metrics, which is the exception
rather than the rule in this sample.

---

## SINDHUTRAD — breakout 2025-03-19

| | |
|:--|--:|
| Breakout candle | **2025-03-19** — 2 sessions after the low |
| OHLC | 16.25 / 19.18 / 16.25 / 19.08 |
| Volume | 11.18M = **8.02x** its 20-day average |
| Body / range | **97%** (upper wick 3%, lower **0%**) |
| Geometry | **marubozu** (body 97% — the largest here) + **gap-up** (+1.6%) |
| Close vs MA20 / MA50 | +28.0% / +7.3% |
| Prior 20 sessions | Rs13.00–17.14, 28.0% wide, slope −0.70%/day |
| Above the run low | +43.1% |
| **Breakout close → peak** | **+88.4%** (Rs35.94, 2025-07-04) |
| MA50 reclaim (secondary) | 2025-03-19 — same candle |
| **Failed prior breakouts, 6m** | **1 of 1** |
| Peak +60 sessions | **−21.0%** |

**Structure.** The purest marubozu in the pack — 97% body, opening exactly on its low and
closing 0.5% off its high, on 8x volume. But it fired **43.1% above the run low**, the
second-worst entry cost here, and closed **28% above its own MA20**. That is not a
breakout from a base; it is a chase. On a Rs16 stock the gap between the signal price and
any realistic fill is material.

**Why it moved.** **No catalyst found in public sources.** Two items surfaced and both
were rejected: Q4 FY25 results showed a **net loss of Rs58.98 cr** — a negative, not a
driver — and the large coal-asset acquisitions (Advent Coal Resources ~Rs697 cr, Sainik
Mining ~Rs225 cr) trace to an EGM dated **June 2026**, fifteen months after the breakout.
Whether an initial announcement predated March 2025 could not be confirmed, so it is not
being counted.

**The honest column.** One prior signal, **2024-10-09** — 59% body, **6.14x** volume, also
a gap-up. It reached +3.5% and was stopped out. Two heavy-volume gap-up breakouts on the
same stock; one doubled it, one did nothing, and they looked alike.

---

## PLAZACABLE — breakout 2026-04-10

| | |
|:--|--:|
| Breakout candle | **2026-04-10** — 7 sessions after the low |
| OHLC | 37.41 / 38.50 / 37.05 / 38.01 |
| Volume | 81,693 = **1.19x** its 20-day average |
| Body / range | **41%** (upper wick 34%, lower 25%) |
| Geometry | **no named pattern** — fits nothing in the reference set |
| Close vs MA20 / MA50 | +12.9% / +3.3% |
| Prior 20 sessions | Rs27.00–37.80, 32.2% wide, slope −0.26%/day |
| Above the run low | +34.9% |
| **Breakout close → peak** | **+71.0%** (Rs65.00, 2026-05-08) |
| MA50 reclaim (secondary) | 2026-04-09, 6 sessions after the low |
| **Failed prior breakouts, 6m** | **1 of 1** |
| Peak +60 sessions | **−23.7%** |

**Structure.** The signal candle is unremarkable in every measurable way — a 41% body
inside a 3.9% range, wicked on both sides, on 1.19x volume, after a 32%-wide sprawl that
was drifting down. **This is the candle that refuses a label**, and it preceded +71%. It
is included precisely because a pack that only showed marubozus would be misleading about
what the winning bar can look like.

**Why it moved.** **No catalyst found in public sources.** Nothing dated in the window was
located. Q4 FY26 results (net profit Rs3.91 cr, +113.66%) were board-approved on **29 May
2026** — three weeks after the run had already peaked on 8 May — so they cannot be the
trigger.

**The honest column.** One prior signal, **2026-01-29**, on a **63% body and 4.02x
volume** — larger body, over three times the volume of the winner — which **stalled and
went −6.0%**. On this name, the better-looking candle lost and the shapeless one won. Also
recall the chart pack's constraint: at Rs0.20 cr/day median turnover, none of this is
capturable at size regardless of the signal.

---

## BHANDARI — breakout 2026-04-06

| | |
|:--|--:|
| Breakout candle | **2026-04-06** — 3 sessions after the low |
| OHLC | 3.10 / 3.21 / 2.83 / 3.17 |
| Volume | 1.53M = **1.96x** its 20-day average |
| Body / range | **18%** (upper wick 11%, lower **71%**) |
| Geometry | **hammer** (lower wick **3.9x** body) + **gap-up** (+6.5% over the prior high) |
| Close vs MA20 / MA50 | +24.2% / +3.4% |
| Prior 20 sessions | Rs2.00–2.93, 36.7% wide, slope −0.63%/day |
| Above the run low | **+56.2%** — the worst entry cost in the pack |
| **Breakout close → peak** | **+21.8%** (Rs3.86, 2026-05-11) |
| MA50 reclaim (secondary) | 2026-04-06 — same candle |
| **Failed prior breakouts, 6m** | **0 signals fired** (full 126-session lookback) |
| Peak +60 sessions | **−25.5%** |

**Structure.** The only hammer, and the only case where the mechanical rule was
effectively useless: the stock had already run **+56.2%** off the low in three sessions
before the signal fired, leaving just **+21.8%** to the peak. A +93% move became a +22%
trade. The candle itself gapped 6.5% over the prior high and then gave most of it back
intraday — an 18% body with a 71% lower wick.

**Why it moved.** **Partial and contradictory — not a confirmed catalyst.** A 4-for-5
rights issue at Rs2.56 (Rs49.30 cr) closed 20 March with allotment 23–25 March, lifting
promoter entity Tikani Exports from **31.02% to 41.83%** (*Chittorgarh*, *TipRanks*). But
a board meeting on **6 April — the breakout date** — was convened to modify the
fund-utilisation plan **because the issue was undersubscribed** (*scanx.trade*), which is
not a bullish event. The bars confirm the ambiguity: 9 April closed **−8.08%**, three
sessions after the signal. A promoter stake rose; whether that caused the move is not
established.

**The honest column.** **Zero prior signals** in a full six-month lookback. Untested, like
`CONFIPET` — an absence of failures, not a record of success.

---

## Appendix — the full prior-signal census

Every signal the rule produced in the 126 sessions before each run low, with the same
measurements applied. This is the table that is *not* conditioned on success.

| Symbol | Signal date | Outcome | Best close gain in 20 sessions | Body/range | Volume |
|:--|:--|:--|--:|--:|--:|
| HFCL | 2025-09-16 | failed — stopped | +1.5% | 0.70 | 2.28x |
| OLAELEC | 2026-01-02 | failed — stopped | +7.4% | 0.86 | 2.92x |
| EDELWEISS | 2024-02-19 | failed — stopped | +3.2% | 0.62 | 2.51x |
| EDELWEISS | 2024-04-22 | failed — stopped | +10.1% | 0.56 | 1.22x |
| EDELWEISS | 2024-05-17 | failed — stopped | +1.5% | 0.78 | 4.37x |
| DBREALTY | 2024-10-11 | failed — stopped | −4.0% | 0.62 | 4.08x |
| DBREALTY | 2024-12-04 | failed — stopped | +3.6% | 0.68 | 1.58x |
| JINDALPOLY | 2025-08-29 | failed — stalled | +1.8% | 0.71 | **18.16x** |
| NACLIND | 2024-06-14 | failed — stopped | +6.7% | 0.55 | 2.60x |
| SINDHUTRAD | 2024-10-09 | failed — stopped | +3.5% | 0.59 | 6.14x |
| PLAZACABLE | 2026-01-29 | failed — stalled | −6.0% | 0.63 | 4.02x |
| **Total** | | **0 worked / 11 failed** | median +3.2% | **median 0.63** | **median 2.92x** |

`CONFIPET` and `BHANDARI` produced **zero** signals across a full lookback. `ORIENTTECH`
and `NIBE` had 7 and 5 sessions of listed history and are excluded rather than scored.

Compare the last row against the twelve winners: **median body 0.63 vs 0.63, median volume
2.92x vs 2.92x.** The distributions overlap so completely that no filter built on these
two variables would have separated them.

