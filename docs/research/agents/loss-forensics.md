# Loss Forensics — can the losses be filtered out?

**VERDICT: not viable. The losses are irreducible.**
No ex-ante filter separates winners from losers out-of-sample. Two filters that looked
spectacular were both leakage; both are documented below so nobody rediscovers them.

## THE NUMBER

Jun 1 – Aug 27 2026, 20,771 closed trades, 25 engine variants, Rs495M turnover.

| | net | bps of turnover |
|:--|--:|--:|
| Gross P&L | **+193,787** | **+3.91** |
| Costs charged | -339,464 | -6.86 |
| **Net** | **-145,678** | **-2.94** |

t(trade) = -5.44, t(day) = -1.94 (58 days), max DD -253,779.
Monthly: Jun -0.6 bps → Jul -2.1 → **Aug -4.4**. It is getting worse, not converging.

**The gross edge is real and the toll is bigger.** Gross t(trade) = +7.24, t(day) = +2.62.
The engine picks direction better than chance. It earns 3.9 bps per rupee of turnover and
pays 6.9. That is the entire finding. There is no bad-trade subset to excise — there is a
2x cost gap.

## WHAT I TESTED

Segmented all 20,771 trades by exit reason, entry-time bucket, holding period, LONG/SHORT,
score decile, symbol-frequency quartile, day of week, entry-price band, pool, stop distance,
overnight carry, and market direction. Then ran **56 ex-ante filters**, fitted on Jun–Jul
(n=10,058) and verified on August (n=10,713), never tuning on the holdout.

**Zero of 56 filters produce a positive holdout bps.** Best train filter (drop price>1000,
+0.40 bps train) does **-7.58 bps** in August. Correlation between train improvement and
holdout improvement across all 56: **-0.037**. There is no signal to fit.

18 rows dropped as corrupt (cost field >5% of notional: v5_swing×16, real1k, v10).

## THE SEGMENTS

### Ex-post exit labels — large but unusable
| reason | n | %n | net | bps |
|:--|--:|--:|--:|--:|
| STOPLOSS | 5,737 | 27.6% | -389,664 | -25.1 |
| SIGNAL_FLIP | 4,774 | 23.0% | -121,171 | -10.9 |
| WRONGWAY_CUT | 460 | 2.2% | -90,945 | -85.0 |
| FLAT_FORCE_EXIT | 4,543 | 21.9% | -50,835 | -5.5 |
| TIME_EXIT | 3,864 | 18.6% | +77,145 | +9.0 |
| TARGET | 1,121 | 5.4% | +434,513 | +139.9 |

"Remove the stop-losses and you gain 390k" is the seductive line and it is meaningless —
the exit reason is the outcome, not a choice available at entry. Same for holding period
(<5m to 1h all negative, >4h +17 bps): fast exits are fast because they lost.

### Ex-ante — the real asymmetries
**SHORT is 2x worse than LONG per rupee**, and that is the only clean asymmetry:

| | n | %n | net | bps | mean/trade |
|:--|--:|--:|--:|--:|--:|
| SHORT | 7,181 | 34.6% | -83,201 | -4.30 | -11.59 |
| LONG | 13,590 | 65.4% | -62,477 | -2.07 | -4.60 |

Dropping every short still leaves **-62,477**. Necessary-but-nowhere-near-sufficient.

**The direction book is beta, not edge.** On the 34.6% of trades with index coverage:

| | LONG | SHORT |
|:--|--:|--:|
| Market UP day | +3.34 bps | -5.44 bps |
| Market DOWN day | **-18.58 bps** | +10.00 bps |

The book makes money only when it happens to be on the right side of the tape. That is
delta exposure with a 6.9 bps fee attached.

**Score is uninformative.** Ten deciles run -7.93, -6.37, +0.98, -5.38, -2.84, -1.69,
-1.31, +2.34, -1.53, -4.29 bps. No ordering, no threshold below which everything loses.
The score does not know what it is looking at.

**Day of week / entry time / price band**: Mon +1.13 vs Wed -5.43 bps; 09:15–10:00 +1.66 vs
10:00–11:00 -5.96 bps; price >3,000 -6.92 vs 1k–3k -0.22 bps. All flip or vanish in August.
Twelve Wednesdays is not a sample.

**Trade shape**: 36.3% win rate, payoff 1.51. The worst 5% of trades carry 40% of all
losses — but nothing observable at entry identifies them.

## THE TWO TRAPS (both fatal, both caught)

**1. Symbol-frequency filter.** Keeping only the top-frequency quartile of symbols showed
+4.70 bps train and **+4.68 bps holdout** — a suspiciously perfect match. It was: the
quartile boundaries were computed on the *full* period including August. Recomputed on
Jun–Jul only and applied forward, the kept symbols do **-6.62 bps in August** (n=6,019,
t=-7.09). The filter has no forward value at all.

**2. Stop-distance filter.** `sl_dist >= 1.3%` gave +23.13 bps train and **+16.36 bps in
August**, t(day)=3.01. At `>=1.8%`: +79.97 bps. This is pure look-ahead. `sl_price` in the
snapshot is the **trailed** stop, not the entry stop:

| sl_dist | n | still protective | trailing_activated | win rate |
|:--|--:|--:|--:|--:|
| >=0.9% | 9,462 | 82% | 18% | 35% |
| >=1.3% | 3,115 | 68% | 32% | 47% |
| >=1.8% | 568 | **26%** | **74%** | **78%** |

Filtering on wide stop distance is filtering on "the trade won and the stop chased it."
Restrict to genuinely protective stops (still on the losing side of entry) and wide stops
are the *worst* cohort in the book: **-22.3 bps train, -23.9 bps August**.

## BEST ACHIEVABLE

**Nothing. The June–August record stands at -145,678 net = -2.94 bps (-0.029%) of
Rs495M turnover.** No combination of the 56 filters improves it out-of-sample.

The only lever that moves the arithmetic is cost, not selection. Charging the INTRADAY
pool the statutory floor only (0.036% round trip, i.e. zero brokerage — not achievable,
but as a bound):

| | net | bps | t(day) |
|:--|--:|--:|--:|
| Intraday, actual costs | -104,566 | -3.46 | — |
| Intraday, zero brokerage | +18,900 | +0.63 | 0.39 |
| — Jun–Jul | +43,117 | +3.18 | 1.30 |
| — Aug | -24,218 | -1.45 | -0.71 |

Even with brokerage set to zero the book is +0.63 bps at t=0.39 and already negative in
the holdout month. The gross edge is not large enough to survive even the statutory floor
with any confidence.

## WHY IT FAILED — the arithmetic

3.91 bps gross per rupee of turnover. 6.86 bps of cost. The gap is 2.95 bps and it is
structural, not concentrated in a removable cohort — every ex-ante slice of the book
(long, short, morning, afternoon, high score, low score, cheap, expensive) sits between
-7 and +2 bps, i.e. all of them straddle or sit below the toll. There is no fat tail of
identifiably-bad trades to cut; there is a thin, uniform, sub-cost edge spread across
20,771 trades.

**Implication for the fleet: the losses are not an execution or filtering problem. Cutting
trades cannot fix it. Either the gross edge roughly triples, or turnover falls by ~60%
while keeping the same gross rupees, or the strategy is dead.**

---
*Caveats: (1) the 25 engine variants trade the same names on the same days, so effective
independent n is far below 20,771 — day-clustered t-stats are quoted throughout and are
the ones to trust. (2) Index direction covers only 34.6% of trades (`^NSEI.csv` ends
mid-period). (3) Costs are as recorded by each engine; v5_classic and v10 (3,480 trades)
lacked a cost field and were charged the brief's model.*
