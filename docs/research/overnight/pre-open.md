# Pre-Open Alpha — Verdict: Not Viable on Prior-Close Information

*The gap is not the obstacle. Forecasting is.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — quant research |
| **Version** | `v1.0.0` |
| **Status** | Complete — negative result |
| **Created** | 2026-08-28 |
| **Updated** | 2026-08-28 |
| **Panel** | 5yr bhavcopy, 1,232 sessions, 3,046 symbols |
| **Verdict** | **NOT VIABLE** — 0 of 96 variants net-positive |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

> **Transcription note.** The analysis behind this report ran to completion overnight on 2026-07-27/28. Only the file write failed, because the disk filled. **These findings are transcribed verbatim from that completed run — nothing here has been re-computed.** One item was left genuinely untested and is flagged as such in §7.

---

## 1. Verdict

**Not viable on prior-close information.** Ninety-six pre-registered variants were tested. Not one was net-positive after costs.

The important part is *why*, and it is not the reason the project assumed. The overnight gap is not what stands between us and a winning day. **85% of a winning stock's day is still available at 09:15.** The barrier is that we cannot tell in advance which stock it will be.

---

## 2. Pre-open data availability

Kite serves **no pre-open call-auction data**. There is no order-book, no indicative price, no imbalance feed. The pre-open decision set is therefore **prior close only** — whatever we knew when yesterday's session ended.

This constraint framed every test below: all signals are computed from data available before the open, and all entries are at the actual 09:15 open.

---

## 3. Where a winning day actually happens

Panel: 5-year bhavcopy, 1,232 sessions, 3,046 symbols, universe = top 500 by trailing turnover, **599,661 symbol-days**.

Decomposing each day into the overnight gap (prior close to 09:15 open) and the intraday leg (09:15 open to close):

::: {.metrics-table}

| Cohort | Gap | Open to close | Total | Gap share |
|:--|--:|--:|--:|--:|
| Top decile day | +0.664% | +3.758% | +4.436% | **15.0%** |
| Top 1% day | +1.323% | +8.679% | +10.075% | **13.1%** |
| Days > +5% | +1.196% | +6.239% | +7.480% | **16.0%** |
| All names | +0.212% | -0.153% | +0.056% | — |

:::

**The gap is 13-16% of a winner's move. The other 85% is reachable from the open.** Missing the pre-open auction costs roughly one seventh of the opportunity — a real cost, but not a disqualifying one.

This also resolves a loose end from `intraday-timing.md`. The "31% of the day's move happens in the first 15 minutes" figure was **already measured from the open**, not from the prior close. It therefore sits *inside* the reachable 85% rather than competing with it. Both facts are consistent: the day is front-loaded, and the front-loaded part is available to us.

**Full-scale split across all names:** +21.2 bps overnight gap versus **-15.3 bps/day intraday drag**. The market's positive drift is overnight; the intraday leg is negative on average. Any long-only intraday strategy fights this.

---

## 4. The 96-variant test

::: {.metrics-table}

| Parameter | Setting |
|:--|:--|
| Variants | 96 = 12 signals x 4 basket sizes x 2 ends (long/short) |
| Entry | actual 09:15 open |
| Exit | close, same day |
| Construction | market-neutral |
| Cost | net 0.107% |
| Train | 721 sessions before a **pre-fixed** 2024-06-01 split |
| Multiplicity bar | Bonferroni \|t\| = 3.47 |

:::

**Result: not one variant was net-positive.**

- Best net variant: **atr20, bottom-20, -0.032%/day, t = -1.15, max drawdown -29.3%**
- Best **gross** result of any variant: **+0.075%/day** — against a 0.107% toll. Short by 30%.

The best idea in the entire search does not clear costs even before we ask whether it is real. **The holdout was never touched, because nothing qualified to be tested on it.** That discipline is worth preserving: the 2024-06-01 split remains unused and therefore still valid for a future test.

---

## 5. Signal strength — rank IC vs market-neutral 09:15-open-to-close

::: {.metrics-table}

| Signal | Train IC (t) | Holdout IC (t) |
|:--|--:|--:|
| atr20 | -0.073 (-11.9) | -0.067 (-8.3) |
| gap_prev | -0.043 (-15.0) | -0.040 (-10.4) |
| ret1 | -0.029 (-7.1) | -0.026 (-5.0) |
| vol_ratio | -0.026 (-9.4) | -0.022 (-6.3) |
| deliv | +0.033 (7.4) | **+0.059 (9.5)** |
| mom_12_1 | -0.011 (-2.1) | -0.007 (-1.3) |

:::

**The signals are real and split-stable — and about 2x too weak.** Every one holds its sign and rough magnitude across the split, which is more than most factor research achieves. They simply do not carry enough information to pay a 0.107% round trip.

`deliv` (delivery percentage) is the one signal that **strengthens out of sample** (+0.033 to +0.059). That is unusual and worth remembering, though on its own it is nowhere near sufficient.

---

## 6. Interpretation

The pre-open framing was the wrong question. We do not lose because we cannot trade the auction — we lose because prior-close information does not identify tomorrow's winner with enough precision to pay for the attempt. Adding pre-open order-book data, if Kite ever served it, would improve the entry price on the 15% we currently miss. It would not fix a forecasting deficit of roughly 2x.

---

## 7. One open thread — untested

`gap_prev` **top-10 held long returned -0.365%/day gross, t = -8.6.** Mechanically, this implies that **shorting yesterday's biggest gap-ups is +0.365%/day gross** — comfortably above the toll, and the only number produced by this study that clears costs.

It was not tested. Before it is taken seriously it needs, in order:

1. **The sign flipped and the holdout taken — once.** The holdout is still clean; this would spend it.
2. **Two-leg costing.** 0.214% rather than 0.107%, cutting +0.365% to roughly **+0.151%**.
3. **A circuit-limit filter — expected to be fatal.** These names sit at or near the *upper* circuit by construction. Stock at upper circuit cannot be borrowed and generally cannot be shorted at all. This is the most likely cause of death.
4. **A liquidity and price screen.** The long leg's **-97% drawdown** says this population lives in extreme low-priced names. Whatever survives step 3 will likely not survive a Rs 1 crore/day and minimum-price filter.

Honest expectation: step 3 kills it. It is recorded here so the thread is not silently lost, not because it is promising.

---

## 8. Status

**Closed as a negative result.** The pre-open direction requires no further work unless the open thread in §7 is pursued deliberately, with the holdout spent knowingly.
