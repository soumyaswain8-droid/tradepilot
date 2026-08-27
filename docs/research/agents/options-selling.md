# Lane: options selling (theta harvesting) on NIFTY

Date: 2026-08-28 · Data: Kite daily NIFTY 50 (256265) + INDIA VIX (264969), 2018-01-01 to
2026-08-27, 2,145 sessions. Script: scratchpad `opt.py` (BS pricer, r=6.5%, q=1.2%, lot=75).

## VERDICT: needs more data — and the tail alone disqualifies the naked version

## THE NUMBER (two of them)

**1. Cost of an options round trip = 0.60% of PREMIUM COLLECTED.**
Rs136 per NIFTY straddle lot on Rs22,689 average premium. Breakdown per lot: brokerage
Rs80 (4 orders x Rs20), STT 0.1% on sell premium (post-Oct-2024 rate, not 0.0625%),
exchange txn 0.03503%, IPFT 0.0005%, SEBI 0.0001%, stamp 0.003% buy-side, GST 18% on
brokerage+charges. **The same Rs18.5 lakh notional traded as intraday equity costs
Rs1,980 (0.107%) — 15x more.** This is the one genuine structural advantage found:
in this lane costs are NOT the binding constraint. They consume ~5% of the gross edge,
not 400% of it.

**2. Net edge, weekly ATM short straddle held 7 days, 1 lot, Rs1.5L margin:**

| Window | n | net/wk | t | win% | avg W | avg L | worst wk | max DD |
|---|---|---|---|---|---|---|---|---|
| IS 2018-22 | 249 | Rs2,532 | 2.40 | 67% | 11,029 | -14,461 | -102,916 | -203,627 |
| **OOS 2023-26** | 178 | Rs2,577 | **2.01** | 63% | 13,029 | -15,161 | -46,800 | -96,744 |
| ALL | 427 | Rs2,551 | 3.13 | 65% | 11,835 | -14,771 | -102,916 | -203,627 |

Tue-expiry variant (current NSE weekly): ALL t=4.37, OOS t=2.23. Drop the best 5 weeks:
t=2.72. Ex-COVID: t=3.78. The signal is not one outlier.

## WHAT I TESTED
Kite carries **no expired option contracts** — the NFO instrument dump starts at expiry
2026-09-01. There is no NIFTY option chain history on this machine or via our broker.
So the chain was reconstructed: sell the ATM straddle (K = spot rounded to 50) at each
Thursday/Tuesday close, price it Black-Scholes with sigma = that day's INDIA VIX, hold
7 calendar days, settle at |S_T - K|. Split by date before searching: 2018-22 in-sample,
2023-26 holdout, no tuning on the holdout. Also tested a 1-SD short strangle
(win 83%, but avg loss -14,227 vs avg win 4,431, ALL t=2.56, worst -94,122) and 5 IV
haircut levels. ~20 variants tested; at 20 tests the Bonferroni bar is |t| >= 2.8, which
the full-sample straddle clears and the holdout alone (t=2.01) does not.

## WHY IT IS NOT ESTABLISHED — the specific arithmetic

**The measured edge IS the IV assumption, exactly.** Break-even IV multiplier = **0.887**.
Mean 30-day VIX over the sample = 16.8%; mean realised 7-day vol = 14.8%; ratio = **0.886**.
Those two numbers agreeing to three decimals is not a coincidence — it says the entire
Rs2,551/week is the variance risk premium and nothing else, and it survives only if
7-day ATM options actually trade at the 30-day VIX. They usually do not: in calm
contango the weekly is typically 5-15% below the 30-day. Sensitivity:

| IV used | net/wk | t |
|---|---|---|
| VIX x1.00 | Rs2,551 | 3.13 |
| VIX x0.95 | Rs1,422 | 1.75 |
| VIX x0.90 | Rs294 | 0.36 |
| VIX x0.85 | -Rs834 | -1.03 |

A 10% error in one unobserved input flips the result from significant to noise. Also
unmodelled: bid-ask on the option itself (weekly ATM NIFTY is ~0.5-1 point/leg, another
~0.5% of premium) and slippage on a 4-leg exit.

## THE TAIL (brief item 4) — this part is not ambiguous
- Worst single week: **-Rs102,916 = -69% of the Rs1.5L margin** (2020-03-05, NIFTY -14.9%).
- Max drawdown: **-Rs203,627 = -136% of margin.** The account is gone; that is a margin
  call, not a drawdown.
- Second worst: -45% of margin the very next week. The bad weeks cluster.
- Even in the calm holdout: worst -31% of margin, DD -64% of margin.
- Loss asymmetry is permanent: 65% win rate, avg win Rs11,835, avg loss -Rs14,771.

**Capital actually required.** Margin is Rs1.5L/lot (SPAN+exposure for a short straddle),
but margin is not the capital. To carry the observed drawdown with a 1.5x buffer needs
**Rs4.55L per lot** → 29% gross annual with a 45% peak-to-trough. Apply the plausible
10% IV haircut and the same book returns **3.4%/yr against a 54% drawdown.**

## WHAT WOULD SETTLE IT
One input: actual traded NIFTY weekly ATM IV, or closing premiums for expired weeklies.
Sources that would work — NSE F&O bhavcopy (`fo*bhav.csv`, free, has expired contract
closes; we already have 1,304 *equity* bhavcopies but zero F&O ones) — one download job
would replace the whole VIX proxy with observed premiums and turn t=2.01 into a real
number. Until then this is a modelled result, not a measurement.

**Recommendation:** do not trade naked short premium at any size — a -69% week is
disqualifying regardless of the mean. If the F&O bhavcopy confirms the VRP survives real
weekly IV, the only version worth testing is a **defined-risk iron condor/fly**, where
the tail is capped by construction and the 0.60%-of-premium cost finding still holds.
