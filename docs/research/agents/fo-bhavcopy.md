# F&O bhavcopy — real NIFTY weekly option data, and the actual variance risk premium

**VERDICT: not viable** (iron condor). Data acquisition: **succeeded** — NSE did not block us.

## THE NUMBER

Two separate results, and they point in opposite directions:

| Measurement | Value | n | t-stat |
|---|---|---|---|
| Variance risk premium (ATM IV − realised vol) | **+1.55 vol points** | 106 weekly expiries | **2.59** |
| Iron condor net expectancy after 0.60%-of-premium cost | **+0.19% of max risk** | 106 | **0.05** |

The variance risk premium is **real and significant**. The iron condor that is supposed to
harvest it has **no measurable edge even gross of costs**.

## WHAT I TESTED

Wrote `quant/fetch_fo_bhavcopy.py` (companion to the equity fetcher) and pulled **535 daily
F&O bhavcopies, 2024-07-01 → 2026-08-27, 3.4 GB**, into `quant/data/fo_bhavcopy/`. NSE
serves these freely — no block, no auth, no captcha. Both archive formats are live and the
fetcher handles both:

- **UDiFF** (2024-07 onward): `nsearchives.nseindia.com/content/fo/BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip`
- **Legacy** (pre-2024-07): `.../content/historical/DERIVATIVES/YYYY/MMM/foDDMMMYYYYbhav.csv.zip` (verified working back to 2023-01)

Only requirement is a browser `User-Agent` + `Referer: nseindia.com`. Throttled to 5 workers
+ 0.25 s; whole 2-year pull took under 3 minutes.

**Important schema fact: neither format carries an implied-volatility column.** UDiFF *does*
carry `UndrlygPric` (exact NIFTY spot on the print) and `SttlmPric`. So I inverted IV out of
the actual traded closes with Black–Scholes (r = 6.5%). BS is used *only* as an inversion
function — every price in the P&L path is a real print, and settlement is real spot at expiry.

From 890,908 NIFTY option rows I built 106 weekly chains: entry on the roll day 5–9 calendar
days before expiry, held to cash settlement. Iron condor = short strikes at N×(priced-in 1-sd
move), long wings 5 strike steps further out. Liquidity filter: `volume > 0 AND OI > 0`.

## THE ANSWER TO THE OPEN QUESTION

**Weekly ATM IV averages 12.16%** (median 11.32%, 10th–90th pct 8.6%–16.3%). India VIX over
the same window ran ~13–14%, so the prior agent's "weekly IV ≈ 30-day VIX" assumption was
**mildly optimistic but not the flaw** — real weekly IV sits a little *below* VIX, as it
suspected. Realised vol over the matched windows averaged 10.61%. So yes: sellers are paid
~1.5 vol points, in 69.8% of weeks.

**And it does not matter, because costs were never the binding constraint here.** This is the
first lane in this project where that is true:

| Short strike | 0.60% cost in points | as % of capital at risk |
|---|---|---|
| 0.75 sd | 0.39 | 0.209% |
| 1.00 sd | 0.25 | 0.123% |
| 1.25 sd | 0.17 | 0.075% |
| 1.50 sd | 0.11 | 0.046% |

Compare equity intraday's 0.107% toll against a 0.005% edge. Here the toll is ~0.1% of capital
against a gross expectancy of ~0.3%. **The cost structure genuinely is different — the prior
agent was right about that.** The strategy still fails, for a different reason.

## WHY IT FAILED — the specific arithmetic

Gross-of-cost results, all four strike distances, held to expiry:

| Short | n | gross mean (%maxrisk) | t | win% | net after 0.60% | max DD | worst trade |
|---|---|---|---|---|---|---|---|
| 0.75 sd | 106 | +0.20 | 0.04 | 65.1 | −0.01 | −532% | −100% |
| 1.00 sd | 106 | +0.32 | 0.08 | 73.6 | +0.19 | −446% | −100% |
| 1.25 sd | 106 | +0.42 | 0.14 | 83.0 | +0.34 | −333% | −100% |
| 1.50 sd | 106 | +0.24 | 0.10 | 88.7 | +0.19 | −218% | −100% |

Every t-stat is under 0.15. Not "fails Bonferroni" — fails to clear zero.

The mechanism: per-trade standard deviation is **24–51% of max risk** against a mean of
0.2–0.4%. The premium arrives in 70–89% of weeks and is handed back whole in the rest —
26.4% of weeks delivered a move larger than the priced-in 1-sd, worst was 4.48%. To establish
the 1.25-sd variant at t = 2 you would need **33,101 weekly expiries — 637 years**. At 1.0 sd,
3,125 years.

The VRP is real, but a condor is the wrong instrument to collect it: it converts a small,
significant edge in *vol points* into an insignificant edge in *P&L* by loading all the
variance into the tail. "Capped tail by construction" caps the loss per trade at 100% of max
risk — it does not make the return distribution tradeable.

## WHAT I'D DO NEXT (not done — out of time budget)

The +1.55 vol-point premium at t = 2.59 is the only live signal here. A **delta-hedged short
straddle** collects the same premium as a *variance* payoff rather than a *terminal-price*
payoff, which strips out most of the tail variance that killed the condor. That is a genuinely
different test and the data to run it is now on disk. Caveat before anyone gets excited: daily
delta-hedging means ~5 futures round trips per week, and NIFTY futures costs would have to be
charged in full — that is exactly the kind of toll that has killed every other lane.

## ARTEFACTS

- `quant/fetch_fo_bhavcopy.py` — F&O fetcher, both archive formats, resumable, throttled
- `quant/fo_vrp_analysis.py` — IV inversion + VRP measurement + condor simulation
- `quant/data/fo_bhavcopy/` — 535 daily files, 2024-07-01 → 2026-08-27, 3.4 GB
- `quant/data/nifty_weekly_vrp.csv` — 106 weekly expiries: spot, IV, RV, credit, P&L per variant

Legacy-format history back to 2023-01 is confirmed downloadable and would add ~370 sessions;
note it lacks `UndrlygPric`, so spot must come from the FUTIDX row or an external index series.
