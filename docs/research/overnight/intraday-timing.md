# Intraday timing of big winners — when does the move actually happen?

**VERDICT: NOT VIABLE.** There is no tradeable intraday timing edge in big winners.
The move is *already over* by the time it is identifiable, and what remains after a
+2% signal is **negative**.

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Date** | 2026-08-28 |
| **Data** | `quant/data/panel_5min.pkl` (200 sym x 42 sessions, Jul–Aug 2026) + `prototype/data/intraday/*_5m.csv` (201 sym x 79 sessions, Jan–May 2026) |
| **Sample** | 20,027 symbol-days, **121 sessions**, 19,624 with a prior close |
| **Cost charged** | 0.107% intraday round trip (MIS, measured) |

---

## THE NUMBER

**Entering a stock once it is already up 2% on the day returns −0.118% to the close,
market-neutralised (n = 5,802, t = −4.78). After the 0.107% toll: −0.225% per trade,
t = −19.8.** The chase is not merely unprofitable — the raw further gain is negative
before a single rupee of cost is charged.

---

## 1. Winner definitions

Per session, top decile by close-to-close return, and separately anything > +5%.

| Cohort | n | Mean close-to-close |
|:--|--:|--:|
| Top decile | 2,003 | +3.73% |
| > +5% | 514 | +7.13% |
| All names | 19,624 | +0.04% |

---

## 2. Average intraday path, normalised to the open

`cum` = mean cumulative gain from the open. `frac` = share of the day's *total intraday*
gain accrued by that clock time (Agg = ratio of means; Med = median of per-name ratios,
restricted to names whose intraday gain exceeded 1%).

### Top decile (mean intraday gain, open→close: **+3.13%**)

| Time | cum from open | frac (agg) | frac (median) |
|:--|--:|--:|--:|
| 09:30 | +0.97% | 31.1% | 27.2% |
| 10:00 | +1.28% | 40.8% | 37.3% |
| 11:00 | +1.76% | 56.1% | 54.8% |
| 12:00 | +2.10% | 67.1% | 68.5% |
| 13:00 | +2.39% | 76.3% | 78.6% |
| 14:00 | +2.66% | 85.1% | 88.1% |
| 15:00 | +2.99% | 95.5% | 97.3% |
| close | +3.13% | 100% | 100% |

### > +5% cohort (mean intraday gain: **+5.07%**)

| Time | cum from open | frac (agg) | frac (median) |
|:--|--:|--:|--:|
| 09:30 | +1.63% | 32.1% | 26.1% |
| 10:00 | +2.13% | 42.1% | 41.1% |
| 11:00 | +2.89% | 57.0% | 59.6% |
| 12:00 | +3.35% | 66.2% | 69.2% |
| 13:00 | +3.86% | 76.2% | 80.8% |
| 14:00 | +4.31% | 85.0% | 87.9% |
| 15:00 | +4.77% | 94.2% | 96.1% |
| close | +5.07% | 100% | 100% |

**Shape:** a hard front-load, then a near-linear grind. **~31% of the whole day's gain
lands in the first 15 minutes** (09:15–09:30) — a rate of ~2%/hour that never recurs.
By 10:00 the day is 41% done; the remaining 5.5 hours deliver the other 59% at a steady
~11%/hour. Both cohorts are nearly identical in shape, so this is a scale-invariant
property of winning days, not an artefact of the extreme tail. The last 25 minutes add
only 5% — an exit at 15:00 costs almost nothing versus holding to the close.

The flat back half is the trap: it *looks* like there is plenty of day left to
participate in. Section 3 shows there is not.

---

## 3. THE DECISIVE QUESTION — what is left after it becomes obvious?

Trigger: the stock's 5-min **high** touches +2% versus the prior close (i.e. the moment a
screen would flag it). Fill at `max(bar close, trigger price)` — conservative, no
look-ahead. Trades triggering after 15:20 are dropped. Market leg = equal-weight mean of
all symbols in the same session over the identical window.

| Trigger | n | Raw to close | t | Market-neutral | t | Net long (−0.107%) |
|:--|--:|--:|--:|--:|--:|--:|
| +1% | 10,621 | −0.094% | −5.17 | −0.147% | −8.57 | **−0.254%** |
| **+2%** | **5,802** | **−0.067%** | **−2.60** | **−0.118%** | **−4.78** | **−0.225%** |
| +3% | 3,166 | −0.050% | −1.34 | −0.088% | −2.41 | −0.195% |
| +5% | 1,000 | −0.118% | −1.50 | −0.125% | −1.63 | −0.232% |
| +2% vs *open* | 4,775 | −0.130% | −4.53 | −0.142% | −5.19 | −0.237% |

Holding period makes no difference — the drift is negative at every horizon:

| Hold after +2% trigger | n | Market-neutral | t | Net long | Net short |
|:--|--:|--:|--:|--:|--:|
| 15 min | 5,802 | −0.120% | −10.49 | −0.227% | +0.013% |
| 30 min | 5,802 | −0.119% | −8.77 | −0.226% | +0.012% |
| 60 min | 5,802 | −0.124% | −7.80 | −0.231% | +0.017% |
| 120 min | 5,802 | −0.117% | −6.26 | −0.224% | +0.010% |
| to close | 5,802 | −0.118% | −4.78 | −0.225% | +0.011% |

**The arithmetic that kills it.** Available further gain after the signal: **−0.118%**.
Toll: **0.107%**. You are down 0.225% before slippage on a fast-moving stock. There is
no threshold, no holding period, and no capital size that repairs this, because the
numerator is the wrong sign.

**Does the reverse work?** Shorting the pop nets +0.011% to +0.017% per trade — but the
per-trade standard error is 0.0115%, so **t = 1.14 on the net**, versus the ~4.0 required
after 1,000+ tests. A 1.3 bp expected edge is inside the slippage band of a stock that
just moved 2% in minutes, before considering borrow and short-sale constraints. Not a
trade.

**The hindsight contrast.** Run the identical +2% entry but only on names that *ended*
in the top decile: **+1.55%, t = 33.3 (n = 1,776)**. That 1.67 percentage-point gap
between +1.55% and −0.118% is the entire cost of not knowing the future. Any backtest
that filters on the eventual winner will show a spectacular chase strategy. It is
measuring the filter, not the trade.

---

## 4. The hindsight ceiling (unreachable)

Perfect entry at the day's low, perfect exit at the day's high:

| Cohort | Mean low→high | Median | n |
|:--|--:|--:|--:|
| Top decile | **+4.99%** | +4.46% | 2,003 |
| > +5% | **+7.10%** | — | 514 |
| All names | +3.02% | — | 20,027 |

**State plainly: this is unreachable.** It requires knowing both extremes in advance.
Against the only realistic figure we could construct — −0.225% net from a +2% chase —
the ceiling exceeds the tradeable number by **5.2 percentage points**, i.e. the
"opportunity" is ~22x the realistic outcome *and of the opposite sign*. Note also that
+3.02% low-to-high exists on an **average** stock on an average day; the perfect-timing
number is barely a winner-specific phenomenon at all. It is a measure of noise
amplitude, not of opportunity.

---

## 5. Best fixed time-of-day rule

Equal-weight long the whole universe, enter at time X, exit at time Y, every day.
All 5-min pairs with X < Y tested: **2,775 pairs**. Split by date: in-sample = first
72 sessions, out-of-sample = last 49. Net of 0.107%.

| X → Y | IS net/day | IS t | n | OOS net/day | OOS t | n |
|:--|--:|--:|--:|--:|--:|--:|
| 10:50 → 14:55 | +0.070% | 0.90 | 72 | −0.138% | −2.03 | 49 |
| 10:45 → 14:55 | +0.062% | 0.80 | 72 | −0.147% | −2.15 | 49 |
| 10:55 → 14:55 | +0.059% | 0.77 | 72 | −0.128% | −1.81 | 49 |
| 11:45 → 14:55 | +0.048% | 0.73 | 72 | −0.114% | −1.72 | 49 |
| 12:05 → 14:55 | +0.043% | 0.70 | 72 | −0.107% | −1.65 | 49 |

**Multiplicity correction:** 2,775 tests requires |t| ≈ 4.0 (Bonferroni at 5%). The best
of 2,775 in-sample pairs reaches **t = 0.90**. It does not clear t = 2, let alone t = 4 —
in fact with 2,775 draws you would expect the best pure-noise t to land near +3.5, so
+0.90 is *worse than random selection noise*. And every one of the top 5 flips negative
out of sample. There is no fixed clock rule.

The "best short" pairs (11:35→11:40, 15:20→15:25, all at t ≈ −18) are an artefact: their
gross return is ≈ −0.01%, i.e. flat. The t-statistic is measuring the constant 0.107%
cost being subtracted from a 5-minute window with almost no variance. Reversing them
loses money too.

---

## 6. Gap versus intraday accrual

| Cohort | Overnight gap | Intraday (open→close) | Total | n | % gap > 0 | % intraday > 0 |
|:--|--:|--:|--:|--:|--:|--:|
| Top decile | +0.59% | **+3.13%** | +3.73% | 2,003 | 67.5% | 95.3% |
| > +5% | +2.01% | **+5.07%** | +7.13% | 514 | 83.9% | 96.7% |
| All names | **+0.076%** | **−0.035%** | +0.041% | 19,624 | 54.5% | 46.9% |

**Big winners defy the market-wide pattern, decisively.** Across all names our sample
reproduces the overnight result qualitatively: the entire (small) return is earned
overnight, +7.6 bps, while the session itself is **−3.5 bps/day** and is positive on only
46.9% of symbol-days. But winners earn **84% of their move inside the session**
(+3.13% of +3.73%), and 95.3% of them close above their open. The >5% cohort still takes
71% of its move intraday despite a large +2.01% gap.

So the overnight effect is a property of the *broad cross-section*; the tail is an
intraday phenomenon. This does not create a trade, because §3 shows the intraday portion
is only capturable by someone already positioned before the move was identifiable.

**Caveat on magnitude:** our −3.5 bps/day intraday drag is milder than the −19 bps/day
reported market-wide. Our sample is 121 sessions in 2026 on a ~200-name liquid universe
(survivor-selected: only names with continuous 5-min coverage), so it is neither the same
period nor the same breadth. Direction agrees; magnitude should be taken from the
survivorship-free daily dataset, not from here.

---

## What this rules out

1. Chasing intraday strength at any threshold (+1/+2/+3/+5%) or horizon (15 min → close).
2. Fading intraday strength — real mean reversion exists (t = −10.5 gross) but the edge
   is 1.2 bps against a 10.7 bp toll.
3. Any fixed enter-at-X / exit-at-Y clock rule over 2,775 candidates.
4. "There's still plenty of day left" as a thesis: 95% of a winner's gain is in hand by
   15:00 and 31% of it by 09:30.

The only unexhausted direction this analysis points at is **pre-open selection** — being
positioned before 09:15 on names that will run, since the 09:15–09:30 window alone carries
31% of the move. That is a forecasting problem, not a timing problem, and it belongs to a
different lane.
