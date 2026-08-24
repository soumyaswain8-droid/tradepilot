# Sarathi Chart-Reading Playbook

The reference the agent lane reads before every decision. Two halves: the standard
technical vocabulary (so the agent speaks the language of the charts), and **our own
measured results** (so it never trusts a concept our data already refuted).

---

## PART 1 — What we MEASURED (this outranks every textbook below)

Falsification run, 2026-08-10: 145,500 simulated trades, 201 symbols, each predicate
tested against a random entry in the same stock on the same day.

| Concept | Our measured result | How the agent must treat it |
|:--|:--|:--|
| SMT divergence (stock vs index) | **best of 10**, +0.051% gross | Worth citing. Still didn't clear the toll alone. |
| Short-term reversal (5-day loser) | 2nd best, +0.057% | Worth citing |
| Order block | mid-pack, +0.002% | Weak. Never the primary reason. |
| FVG (fair value gap) | −0.007% | Weak |
| AMD phase | −0.016% | Weak |
| Liquidity sweep + reclaim | −0.017% | Weak — despite being the most defensible in theory |
| Opening-range break | −0.026% | Weak |
| **MTF alignment** | **9th of 10**, −0.049% | My prior said "strong evidence". The data said no. |
| Index-futures lead | worst, −0.069% | Avoid |

**Confluence was the one real finding**: gross edge rose monotonically with the number
of agreeing predicates — −0.16% at 1 agreeing, **+0.084% at 7** — across eight buckets
of thousands. *Agreement between independent reads is the signal; any single concept
is not.*

Also measured, and load-bearing:
- **Trading WITH daily bias lost** (−0.039%) while **against it gained** (+0.003%).
  At intraday horizons this market **mean-reverts; it does not trend**. Momentum
  language ("it's breaking out, chase it") is contradicted by our own data.
- **Exits saved money on 7 of 7 measured days.** Post-exit drift was negative every
  time. Cutting is rarely the mistake here; *not arming the trail* was.
- **Winners round-trip through stops**: ~48% of all money left on the table sat in
  trades that were profitable at their peak, because the trail arms at +1.0% while
  the average trade's best moment is only +0.495%.

---

## PART 2 — The vocabulary (standard TA, stated precisely)

### Candles — what a single bar actually says
- **Body** = open→close (conviction). **Wick** = rejection of that price.
- **Long lower wick at support** = buyers defended. **Long upper wick at resistance**
  = sellers defended. The wick matters more than the body at a *level*.
- **Doji / spinning top** = balance, not reversal. Only meaningful AT a level.
- **Engulfing** = the later body swallows the prior; strongest at a swing point,
  meaningless mid-range.
- **Marubozu** (no wicks) = one side controlled the entire period.
- Context rule: **no candle means anything without a level and a preceding trend.**

### Structure — the skeleton
- **Swing high/low**: a high with lower highs each side (and converse). One fractal
  definition, used consistently.
- **Higher highs + higher lows** = uptrend. Lower highs + lower lows = downtrend.
  Anything else = range, and ranges are the default state.
- **BOS (break of structure)**: price closes beyond the last swing in trend
  direction — continuation.
- **CHoCH (change of character)**: the first failure to make a new swing, then a
  break the other way — the earliest structural warning of a turn.
- **Protected high/low**: the swing that produced the most recent BOS. Losing it
  invalidates the structure that justified the trade — this is where a stop belongs,
  not at an arbitrary percentage.

### Levels — where orders actually rest
- **PDH/PDL** (prior day high/low), **PWH/PWL** (prior week): the most-watched
  intraday levels in Indian equities.
- **Equal highs / equal lows**: two or more swings at the same price = resting stop
  orders = a liquidity pool. Price is drawn to them.
- **Liquidity sweep**: price pierces the pool, triggers the stops, then closes back
  inside. The *reclaim* is the signal, not the pierce.
- **VWAP**: the institutional reference. Above = buyers in control on the day.
- **Round numbers** (100/500/1000): real in Indian retail flow.

### Imbalance
- **FVG / fair value gap**: three-candle pattern where candle 1's high < candle 3's
  low (bullish). The gap is unfilled trade; price often revisits it.
- **Order block**: last opposing candle before a displacement leg that broke
  structure. Our weakest measured concept — cite only as confluence, never alone.

### Volume — the honesty check on every pattern
- Breakout on **rising volume** = participation. On falling volume = suspect.
- **Climax volume** with a long wick at an extreme = exhaustion, not continuation.
- Volume dry-up in a range = coiling; expansion usually follows.

### Multi-timeframe
- Daily = the map. 15m = the setup. 5m = the trigger.
- Our data says MTF *alignment* did not pay. Use higher timeframes to know **where
  you are** (near a level? mid-range?), not as a directional vote.

---

## PART 3 — The decision procedure the lane must follow

For each candidate, answer in order. **If step 1 or 2 fails, there is no trade.**

1. **WHERE IS PRICE?** Name the nearest level above and below, and the distance.
   Mid-range = no trade. The edge lives at levels, not in the middle.
2. **WHAT IS THE STRUCTURE?** Uptrend / downtrend / range on the 15m, with the
   protected level named. No nameable structure = no trade.
3. **WHAT IS THE TRIGGER?** A specific event: swept PDL and reclaimed / rejected VWAP
   with a long wick / CHoCH after a failed high. "It looks bullish" is not a trigger.
4. **WHAT SAYS I'M WRONG?** The invalidation price, named BEFORE entry. That price is
   the stop; risk = entry − stop.
5. **HOW MANY INDEPENDENT READS AGREE?** Count them. Our measured confluence gradient
   says fewer than 4 agreeing reads is not worth the toll.
6. **WHAT IS THE REWARD?** Distance to the next opposing level ÷ risk. Below 1.5R,
   skip — the toll eats thin R.

**Confidence must be stated (0–1) and the trade skipped below 0.6.** A day with no
trade is a valid, and often correct, output.

---

## PART 4 — Honest limits of an agent reading charts

- Chart reading is **pattern recognition on noisy data**, and every mechanical
  version of these patterns failed our cost gate. The open question is whether
  holistic, context-aware reading does better than mechanised predicates. Unproven.
- The agent sees a snapshot; it cannot feel order flow.
- Hindsight is seductive: on any historical chart every pattern looks obvious. The
  only honest test is calling it **before** the next bar exists — which is exactly
  what this lane does.
- **The gate**: ≥20 agent-called trades, net positive after 0.106% fees, beating a
  random-entry control on the same names and days. Fails that → the lane closes,
  like the six theses before it.
