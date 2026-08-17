# Exit-capture backtest — can a different exit keep the giveback?

**Question** (from today's autopsy): ₹23.6k of the day's ₹38.2k in-trade ceiling sat
in trades that were profitable at peak, then rode through their stop. Could a
different exit rule have kept it?

**Method**: entries held EXACTLY as the engines took them (symbol, time, side, price,
stop, target from the trade record); only the exit rule replayed. 9 policies, paired
per-trade deltas against the baseline replay (simulator bias cancels in the pair).
60-day 5m bar cache, stop-fills-first pessimism. Kill gate fixed in advance:
paired t>2, n≥300, at both fee rates. Sanity: replay-vs-booked corr 0.74.

## The diagnosis — why the money is left

**Average MFE per v5 trade is 0.495%. The trail arms at 1.0%.**
The average winner never reaches the arm point, so the trailing stop never activates
on the typical trade — baseline captures **9.7%** of available MFE. The rule isn't
badly tuned; it's tuned for a book that doesn't exist.

## Results (full window, v5, n≈2,400 paired)

| Policy | capture | Δ/trade vs baseline | t(paired) | net @0.079% |
|:--|--:|--:|--:|--:|
| baseline arm1.0/step0.5 | 9.7% | — | — | −0.0305% |
| **arm0.3/step0.25** | **18.8%** | **+0.0451%** | **3.85** | **+0.0146%** |
| arm0.5/step0.25 | 16.5% | +0.0334% | 3.44 | +0.0029% |
| arm0.75/step0.25 | 13.3% | +0.0175% | 2.89 | −0.0130% |
| atr 1.5A/0.75A | 13.4% | +0.0181% | 2.17 | −0.0124% |
| be@0.4 / be@0.6 | 11%/10% | +0.007/+0.003 | 0.80/0.43 | killed |
| no-trail | 7.4% | −0.0116% | −2.51 | killed |

**Independent replication on v5_cut** (different engine, different selection):
arm0.3/step0.25 again best, +0.0436%/trade, t=2.71. Same ordering. This is NOT the
mean-reversion pattern (which evaporated at full sample) — smoke → full → second
engine all agree.

Also learned: **no-trail is WORSE than baseline** (−0.0116, t=−2.51) — trailing as a
mechanism helps; only the arm threshold is wrong. And breakeven-early policies fail
(the POWERINDIA shakeout, now measured: be@0.4 adds only +0.0065, t=0.80).

## What it would have meant

arm0.3/step0.25 roughly **doubles MFE capture (9.7% → 18.8%)** and adds
**+4.5 bps/trade**. On v5's ~50 trades/day ≈ ₹350k turnover that is roughly
**+₹150–160/day per engine**, and it turns v5's real trades **net-positive at size
fees** (+0.0146%) for the first time under any tested exit. It does NOT recover the
whole ceiling — nothing can; ~19% capture is what an exit rule buys.

## Verdict per the gate

Survivor. **A survivor earns a shadow engine, not a live change.** Next step
(tomorrow): make `TRAILING_TRIGGER_PCT`/`TRAILING_STEP_PCT` env-overridable
(default unchanged — same precedented pattern as TOTAL_CAPITAL) and run `v5_trail`
= arm0.3/step0.25 as a shadow against live v5. Everything else stays untouched.
