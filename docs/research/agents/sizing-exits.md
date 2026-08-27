# Lane: Position sizing & exit architecture

**VERDICT: not viable. This lane is closed, and it closes usefully — it proves the problem is entries.**

## THE NUMBER

Same entries, best possible exit rule out of 12 tested, **zero cost charged**:
**-1.07 bps gross per trade, n = 6,755, t = -0.31.** Every exit rule tested is negative
gross. Costs (10.7 bps) are not what kills the book — there is nothing there to kill.

Net, with the 0.107% round trip and a 5 bps slippage allowance on stop fills, the best rule
gives **-11.8 bps/trade, t = -3.40**.

## WHAT I TESTED

20,789 closed trades from `docs/paper-trades/*/2026-06-01..08-27.json` across 25 engines.
Baseline as traded: **Rs -77,593 total, -Rs4.49/trade, t = -3.22, 36.5% win rate.**
6,755 of them (Jul 1 – Aug 27, 162 symbols, 22 engines) have a 5-min intraday path in
`quant/data/panel_5min.pkl`, so their exits can be re-simulated bar by bar. Holding entry,
side, time and size fixed, I replaced the exit with: stops at 0.4/0.6/0.8/1.2/2.0%,
targets at 0.6/1.0/2.0%, trailing stops armed at 0.4–1.0% with 0.3–0.8% gaps, pure time
exits at 15/30/60/120 min, and hold-to-close. 33 variants in the first pass, 12 in the
gap-aware pass. Then fixed-rupee vs ATR-inverse sizing, and an N-consecutive-loss breaker.

## THE ARITHMETIC

**1. Exits barely matter.** Across all rules the mean net outcome spans only **5.1 bps**
(-11.8 best to -16.9 worst). Decomposing trade-level P&L variance: variation across exit
rules on the *same* entry accounts for **3.1%**; variation across entries accounts for
**96.9%**. Effort spent on exits is spent on 3% of the problem.

**2. The first pass was a fill artifact — worth recording.** With naive fills (stop
executes exactly at the stop price) the tight trailing stop showed **+13.2/trade, t=+2.75**
and looked like a discovery. Re-running with gap-aware fills (fill at the worse of the stop
level and the bar open, which is what actually happens when a 5-min bar's low is 1.2% below
entry) it becomes **-12.7 bps, t=-3.66**. The entire "improvement" was the simulator getting
a better price than the market offers. Anyone reporting a stop-loss backtest without this
correction is reporting the correction, not an edge.

**3. Out of sample it inverts anyway.** Split by date: July n=2,395, hold-to-close **+10.1
bps, t=+1.48**; August n=4,360, **-31.7 bps, t=-7.31**. The best rule fitted on July gives
**-25.0 bps t=-6.23** in August. 12 variants tested needs |t| ≥ 3.0 Bonferroni; nothing
positive reaches even |t| = 0.5.

**4. Sizing changes size, not sign.** ATR-inverse sizing (target 0.6% risk, capped
0.25x–3x) cuts the loss from Rs-136,151 to Rs-71,235 and max drawdown from Rs171,522 to
Rs75,339 — but annualised daily Sharpe goes **-4.63 → -6.25**. It is not improving
risk-adjusted return; it is shrinking a negative expectancy toward zero more reliably. The
textbook claim that vol-scaling improves risk-adjusted return assumes a positive edge. There
isn't one, so it just makes the losing more consistent.

**5. The loss-cutting rule is a random-trade remover.** Stop the engine-day after N
consecutive losses, versus a size-matched random subset of the same trades:

| N | trades kept | net | random control | edge vs random |
|--:|--:|--:|--:|--:|
| 2 | 1,624 / 17,292 | Rs -2,932 | Rs -7,287 | **+4,355** |
| 3 | 2,894 | Rs -15,600 | Rs -12,986 | -2,614 |
| 4 | 4,596 | Rs -24,471 | Rs -20,623 | -3,848 |
| 5 | 6,238 | Rs -41,058 | Rs -27,991 | -13,067 |

Only N=2 beats random, by Rs4,355 while deleting 91% of trading — and N=3,4,5 are all worse
than random, so there is no monotone effect. That is noise, not a circuit breaker.

## THE HONEST CEILING

Best exit rule + vol-scaled sizing + realistic slippage, on the SAME entries, Jul–Aug:
**Rs -81,776 net (August alone Rs -77,157), max drawdown Rs 89,784.** Fixed sizing is
Rs -198,753. There is no configuration of exits and sizing that makes these entries
profitable, because their gross drift is -1 to -6 bps before a single rupee of cost.

## CAVEATS

- Path data only covers Jul 1 – Aug 27 and 162 symbols (`panel_5min.pkl`);
  `prototype/data/intraday/` ends in May and cannot cover June onward. June entries are in
  the 20,789 baseline but not in the 6,755 exit re-simulation.
- The 25 engines share signal logic, so the 6,755 trades are far from independent. The
  reported t-stats are therefore *optimistic in magnitude* — which only strengthens a
  negative result.
- Trades are exit-reconstructed against 5-min OHLC. Intrabar sequencing is unknowable; I
  resolved it against the position (stop checked before target), which is the conservative
  choice.

## IMPLICATION FOR THE OTHER LANES

Do not spend more time on exit tuning, trailing stops, or position sizing. The signal these
engines produce has approximately zero — slightly negative — gross drift over any horizon
from 15 minutes to the close. Downstream optimisation has a ceiling of about 5 bps of
rearrangement on a distribution whose mean is already below zero. **All remaining effort
belongs on entries.**
