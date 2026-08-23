# Engine Graveyard — the fleet consolidation of 2026-08-23

Seventeen engines ran; three lanes survive. Every retired engine is listed with why
it was born, what it taught, and why it ends. Nothing is deleted — day files, state
and code remain on disk and in git; the launcher and watchdog simply no longer start
them. This document is the harvest.

## The verdict that drove this

Week 08-17..21: the fleet cycled **₹3.66 crore** of turnover to earn **+₹5,261 gross
(+0.014% of flow)** — and paid ₹39,026 in modelled fees doing it. Five independent
measurements over three weeks all landed on the same wall: intraday OHLCV-derived
signals cannot clear real costs on this market. Running thirteen variations of a
dead thesis is not diversification; it is paying the toll thirteen times.

## SURVIVORS (the roster from 2026-08-24)

| Lane | Why it lives |
|:--|:--|
| **v5_wide** | The only engine with a live net-positive track: +8,070 net this week, +2,486 last, best-4-of-8 sessions. The only engine whose *selection* differs (837-stock screened universe). Continues as the intraday lane and de-facto control. |
| **v5_swing** | Best return-on-turnover in the fleet (0.62%/deployment, 45× fleet average) on 7 trades. The move-to-cost ratio argument (40:1 vs intraday's 5:1) is the one structural insight nothing has killed. Gate: ~60 closed swings vs random-dip control at 0.24% CNC. |
| **real1k** | The reality lane: ₹1,000 of real cash, manual execution, measures actual fills/slippage/latency against every assumption the paper stack makes. |

Queued next (not started): the size lever applied to v5_wide's selection — merging
the two things that survived — and the order-book signal (13 sessions banked).

## RETIRED — with their lessons

**v5** (the primary, Apr–Aug) — 3 months of out-of-sample truth: WR decayed 77%→42%,
entry timing measurably worse than random (5/5 seeds, t 2.76–4.24), all six features
backward-looking. Its greatest service was being a stable control while everything
else was measured against it. *Lesson: an engine can be excellent infrastructure and
still have no edge.*

**v5_size** — CLOSED AT 124/300 with the structural half PROVEN: median ₹85–108k
positions pay 0.079% vs 0.106% — the fee cliff is real, banked, and portable to any
future lane. The signal half (would v5's signal net better at size) dies with v5's
signal: a question about a dead signal needs no answer. *Lesson: position size was
worth more than every signal improvement found in three months.*

**v5_classic** — the no-ML twin. Tracked v5 within noise all summer: the ML layer
was neither the edge nor the problem. *Lesson: blame data, not models.*

**v10** — the frozen April replica. Answered the founding myth: April's 77% WR was
in-sample ML memorisation (IC 0.006), not a recipe. Also donated two incidents that
became guards: the 08-53 stale-fill pre-open buy (→ SESSION-GUARD) and the poisoned
circuit-breaker carry-over. *Lesson: freeze a legend and it confesses.*

**v5_kite** — data-source A/B. Kite vs yfinance divergence: 0.00% on fills that
mattered; the licensed feed is 22× faster but not more profitable. Its job was a
question, the question is answered. *Lesson: feed quality was never the bottleneck.*

**v5_cut / v5_flip / v5_hold / v5_long** — exit-rule variants (early-cut, fast-flip,
hold-longer, long-only). Between them they mapped the exit space and none beat the
toll; v5_hold was the week's worst (−6,131 net). The one durable exit finding came
from the backtest harness instead (trail arms above the book's reach — arm0.3 paired
t=3.85). *Lesson: exits redistribute the loss; they do not create edge.*

**v5_chop / v5_rrg / v5_gate** — the regime family. The RRG sensor passed its Gate-1
(85/73) and the gates genuinely cut chop-day trades — but gating a zero-edge signal
yields zero, gated. The regime *sensors* are proven components, parked for reuse in
any future lane. *Lesson: risk gates preserve capital; they cannot mint it.*

**v5_1L / v5_cut_1L / v5_long_1L** — the small-capital shadows (₹1L pools, ₹1–2k
positions). Deepest inside the fee bracket, structurally unprofitable at any win
rate; they existed to model the original ₹12k live plan and proved it unviable.
*Lesson: below the cliff, size is destiny.*

**v4 / v5_2..v5_8 / v6 / v7_regime / v8 / v5_apr / v5_noml / v5_deploy / v5_pick /
v5_time** — already standby or long-retired scaffolding from earlier phases; formally
listed here so the graveyard is complete.

## What carries forward (the actual assets)

1. The **fee-cliff mechanics** (min(0.03%, ₹20) → size above ₹66,667) — proven.
2. The **falsification discipline** — pre-registered gates, holdouts, paired tests,
   random-entry controls, point-in-time universes. Six theses killed cleanly, zero
   capital burned.
3. The **guards** — session clock, disk gate, staleness validators, fire ledgers.
4. The **regime sensors** and **order-book collector** (13 sessions) as components.
5. Three weeks of honest per-engine out-of-sample record for any future comparison.
