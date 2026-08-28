# Delta-Hedged Short Straddle — NIFTY Weekly

**VERDICT: FAIL.** Delta hedging worked exactly as theorised — it cut the years-to-t=2 from the condor's **637 years to 6.4 years**, a ~100x collapse in variance. It still fails every one of the six pre-registered bars: Sharpe 0.79 (bar 1.0), t = 1.13 (bar 2.0), 6.4 years to t=2 (bar 4.0), max drawdown **-42.5%** (bar 15%), worst week **-18.7%** (bar 10%).

The premium is real and hedging does isolate it. What kills this is not detectability — it is that the residual gamma tail is still large enough to be a ruin path on a small account, and the hedge's own turnover is 64x the premium it is trying to collect. **Do not paper-trade. This thread is closed.**

Correction to the brief: **options STT is 0.15%, not 0.1%** — see Costs below. Your 0.05% futures figure was right.

---

## 1. Pre-registered bar

Written to `quant/data/dh_straddle_PREREG.txt` **before** the strategy was run. Verbatim:

| # | Criterion | Bar | Observed | |
|---|---|---|---|---|
| 1 | Annualised Sharpe, net | ≥ 1.0 | **0.79** | FAIL |
| 2 | t-statistic on sample | ≥ 2.0 | **1.13** | FAIL |
| 3 | Years to t=2 at observed Sharpe | ≤ 4.0 | **6.4** | FAIL |
| 4 | Max drawdown | ≤ 15% | **42.5%** | FAIL |
| 5 | Worst single week | ≤ 10% | **18.7%** | FAIL |
| 6 | Survives integer-lot hedging ≤ 5 lots | pass | 1 lot: SR 0.54, DD 66% | FAIL |

Six for six. No partial credit was available and none is being claimed.

**Both Sharpe and t are invariant to the capital denominator** (scaling all returns by 1/C leaves mean/sd unchanged). So bars 1–3 do not depend on the ₹2,00,000 margin assumption at all. Only bars 4 and 5 do.

---

## 2. Data — what was fetched, and what could not be

**Downloaded: 83.3 MB, 530 files.** Free space went from 7.8 GB to 8.4 GB (net of other activity); the guard never fired.

The archive was re-fetched with a new script, `quant/fetch_fo_nifty_only.py`, written specifically to avoid repeating last night's outage. The full F&O bhavcopy is ~20 MB/day, ~10 GB for this window — more than the free disk. Instead each daily zip is pulled into **memory**, filtered to `TckrSymb == NIFTY`, and only those ~3,000 rows written. ~250 KB/day instead of ~20 MB/day, an **80x reduction**. Free space is checked before every single write and the process hard-aborts below 2 GB.

- Window: **2024-07-08 → 2026-08-27**, 530 sessions, 29 misses (holidays).
- 882,502 NIFTY option rows, 1,590 index-future rows.
- UDiFF format only. The legacy pre-2024-07 format lacks `UndrlygPric`, and mixing the two would silently change the spot source mid-sample.
- Every option price in the P&L path is `ClsPric` — an actual traded print on the actual expired contract. Black-Scholes is used **only** to invert a traded close into an IV, and that IV is used **only** to compute a hedge ratio. No price is modelled.

### What is NOT obtainable — intraday hedging

**Intraday delta hedging could not be tested and is not simulated.** Bhavcopy is end-of-day only. Kite historical drops expired instruments — expired weekly option contracts are absent from the instrument dump, so no `instrument_token` exists to request minute bars against. There is no path to an intraday option price series for a contract that has already settled.

To test intraday hedging you would need one of: (a) a tick/minute archive of NSE F&O captured live at the time, which this project does not have and cannot retroactively create; (b) a paid vendor F&O intraday history feed (GDFL, TrueData or similar); or (c) forward-collection — start recording NIFTY option minute bars now and revisit in a year. **I did not substitute a proxy.** Note the direction of the bias: more frequent hedging reduces gamma slippage but multiplies the hedge cost, which is already the dominant cost here — so intraday hedging is not obviously a rescue.

---

## 3. Simulation — every assumption stated

- **Entry**: last session between 5 and 9 calendar days before expiry — the same rule as the condor study, so the two are directly comparable. ~1 week hold, 107 expiries.
- **Structure**: sell 1 ATM straddle (CE + PE) at the strike nearest the entry-day spot, at that day's close.
- **Hedge instrument**: the nearest NIFTY index future expiring on or after the option expiry. `dF/dS = 1` is assumed; basis *level* is irrelevant to a hedge P&L (only basis *changes* matter) but basis drift adds unmodelled noise.
- **Hedge frequency**: **daily close**. Target position = `-(1 - 2·N(d1))·lot`, recomputed each session from an IV re-inverted from that day's traded closes on the same strike. If inversion fails (no print / no time value), the previous day's IV carries forward.
- **Hold**: to expiry. Short options settle against intrinsic at the expiry spot. Residual hedge closed at the expiry settlement.
- **Lot**: 75. **Capital**: ₹2,00,000 per 1-lot hedged straddle (SPAN + exposure, with the straddle's margin benefit). This is an assumption and moves the absolute return only, not Sharpe or t.
- Holding to expiry is deliberately *cheaper* for a seller: exercise STT of 0.15% on intrinsic falls on the **buyer**, not the writer. Squaring off early would add a full round of premium STT and spread.

---

## 4. Costs — and a correction

Rates verified against `zerodha.com/charges` on 2026-08-28, not recalled from memory.

| Charge | Futures | Options |
|---|---|---|
| STT | **0.05%** sell side | **0.15%** sell side, on premium |
| Brokerage | ₹20 or 0.03%, whichever **lower** | flat ₹20/executed order |
| NSE transaction | 0.00183% | 0.03553% on premium |
| SEBI | ₹10/crore | ₹10/crore |
| Stamp | 0.002% buy side | 0.003% buy side |
| GST | 18% on (brokerage + txn + SEBI) | same |

**You were right on futures and wrong on options.** Futures STT is indeed 0.05%, raised 0.0125% → 0.02% (Oct 2024) → 0.05%. But options STT is now **0.15% on the sell side of premium, not 0.1%** — Budget 2026 raised it from 0.10% to 0.15% effective 1 April 2026, alongside the futures hike you correctly recalled. Since this strategy is a premium *seller*, that 50% understatement lands entirely on the wrong side of the ledger, so it is charged at 0.15% throughout.

Current rates are charged across the **whole** sample, including the pre-April-2026 portion where they were lower. That is deliberate: the decision is whether to trade this *now*, so it must be costed at today's rates.

**Bid-ask**: 0.50 index points half-spread per option leg (NIFTY ATM weeklies, tick 0.05, typical full spread ~1.0 pt) and 0.25 points per futures hedge adjustment, charged on **every** adjustment. Sensitivity run at half and double these.

---

## 5. The decisive measurement

| Variant | n | mean ₹/wk | t | Sharpe (ann) | **yrs → t=2** | win% | worst ₹ | maxDD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Delta-hedged daily** | 107 | 1,287 | **1.13** | **0.79** | **6.4** | 62.6% | -37,480 | -42.5% |
| Unhedged short straddle | 107 | 1,536 | 0.87 | 0.61 | 10.9 | 57.9% | -51,705 | -62.0% |
| Hedged, integer lots, 1 lot | 107 | 1,077 | 0.78 | 0.54 | 13.7 | 53.3% | -48,225 | -66.1% |
| Hedged, integer lots, 5 lots | 107 | 7,706 | 1.36 | 0.95 | 4.5 | 61.7% | -192,567 | -43.0% |
| Hedged, optimistic spreads | 107 | 1,340 | 1.18 | 0.82 | 5.9 | 62.6% | -37,423 | -42.3% |
| Hedged, wide spreads | 107 | 1,187 | 1.04 | 0.73 | 7.5 | 62.6% | -37,586 | -43.0% |
| *Iron condor (prior study)* | | | | *~0.08 implied* | *637* | | |

**Did hedging collapse the variance? Yes — decisively, and it is the one thing that worked.** 637 years → 6.4 years is a ~100x improvement in statistical detectability, and it came from exactly the mechanism predicted: removing the directional term. Sharpe roughly 10x'd. The theory was correct.

**Was it enough? No.** 6.4 years to t=2 misses the 4-year bar, and the sample's own t of 1.13 does not clear 2 after two full years of weekly trading. The hedge costs ₹249/week in fees and slippage against the unhedged version and buys a variance reduction that improves the Sharpe from 0.61 to 0.79 — real, but not transformative.

Note the integer-lot rows. At **1 lot** — the realistic small account — the hedge is bang-bang between 0 and 75 units and the rounding noise destroys most of the benefit: Sharpe falls to 0.54, *worse than not hedging at all*. The 5-lot row looks better than fractional (Sharpe 0.95) because the flat ₹20/order brokerage amortises across five lots and coarser rounding means fewer adjustments. That is a genuine fixed-cost effect, not an artefact — but it means **this structure requires ~₹10 lakh of margin before the hedge even starts working**, which disqualifies it for the account this project is sized for.

---

## 6. The tail — reported honestly

Short vol is short a fat left tail and this sample shows it.

- **Worst single week: -₹37,480 = -18.7% of capital** (expiry 2025-04-09) on a realised move of only 2.2%.
- **Max drawdown -42.5%**, bottoming 2025-05-15.
- **Underwater 85 of 107 weeks** — the equity curve spends 79% of its life below a prior high.
- **Worst 5 weeks sum to -77.4% of capital.** Four separate weeks lost more than 10%.
- Strategy annualised vol **42.4%** against a 68.9% cumulative return over two years.
- `corr(|move|, P&L) = -0.72`. Breakeven move is 1.24% of spot; **31.8% of weeks exceeded it.**

### Gap risk

A daily-close hedge gives *zero* protection against an overnight gap. The position is set delta-neutral at Friday's close; a Monday gap is pure gamma loss realised in full before any adjustment is possible.

| Overnight gap | Adverse move | P&L on 1 lot | % of ₹2L capital |
|---|---:|---:|---:|
| 2% | 490 pts | -₹14,095 | **-7.0%** |
| 3% | 735 pts | -₹32,461 | **-16.2%** |
| 5% | 1,224 pts | -₹69,195 | **-34.6%** |
| 7% | 1,714 pts | -₹1,05,928 | **-53.0%** |

A single 5% gap — well inside the range of an India-Pakistan escalation headline, a surprise RBI move, or a US-led global risk-off open — takes **a third of the account in one morning**. At 7% it takes half. Against a strategy that earns ₹1,287 a week, a 5% gap erases **54 weeks of accumulated edge in one print**, and the margin call arrives before the recovery does.

**A Sharpe of 0.79 with a 42.5% drawdown and a one-morning-half-the-account tail is not a viable strategy for a small account.** It fails on the same axis the project has killed everything else on.

---

## 7. Conclusion

The variance risk premium on NIFTY is real — that standing result survives. The hypothesis that delta hedging isolates it was also correct: it removed the dominant variance term and improved detectability 100-fold. Both halves of the reasoning were sound.

The structure still fails, for a reason neither the VRP measurement nor the condor failure predicted: **what remains after the directional term is removed is not clean premium, it is gamma**, and gamma on a weekly ATM straddle is large, fat-tailed, un-hedgeable overnight, and requires ~₹10 lakh of margin before the hedge is even granular enough to help.

This was the last open thread from the 18-agent search. It is now closed. Nothing here warrants paper-trading.

**If it were ever revisited**, the single thing that would change the answer is intraday hedging data — and only if intraday hedging reduced gamma slippage faster than it multiplied hedge costs, which the ₹1.4M/week hedge turnover against ₹22.6k of premium collected makes unlikely. That would require forward-collecting NIFTY option minute bars, or a paid vendor feed. It is not worth buying one on this evidence.

---

*Files: `quant/fetch_fo_nifty_only.py` (fetcher), `quant/dh_straddle.py` (backtest), `quant/data/dh_straddle_weekly.csv` (107 weekly records), `quant/data/dh_straddle_PREREG.txt` (pre-registered bar), `quant/data/fo_nifty/` (83.3 MB, 530 sessions).*
