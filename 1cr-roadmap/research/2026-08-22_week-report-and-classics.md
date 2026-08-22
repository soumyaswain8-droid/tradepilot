# Week 08-17..08-21 + the "Instagram model" investigation

## The week, without brokerage (as asked)

| Day | Trades | GROSS | (fees) | (net) |
|:--|--:|--:|--:|--:|
| Mon | 675 | −7,603 | 7,392 | −14,995 |
| Tue | 629 | −5,489 | 7,965 | −13,454 |
| Wed | 596 | +3,296 | 6,223 | −2,927 |
| Thu | 507 | +11,555 | 6,149 | +5,406 |
| Fri | 745 | +3,501 | 9,900 | −6,399 |
| **WEEK** | **3,152** | **+₹5,261** | 37,629 | −32,368 |

Gross positive; fees were **7.2× gross**. The engines find money and the toll takes it —
the campaign's diagnosis, again.

Standouts: v5_wide +11,923 gross (best, 273 trades). **v5_swing +5,308 gross on
SEVEN trades** — second-best engine in its debut week. COFORGE hit TARGET +3.78%;
3 of 7 verdicts green, worst −1.16%. v5_size: 124/300.

**Correction found while costing this report:** multi-day holds are CNC delivery —
STT 0.1% each side, ~0.24% round trip, ~3× the intraday rate we'd been applying to
v5_swing. Swing week-1 net is ~+₹3,260, not +₹4,677. Live accounting needs the fix.

## Left on the table (2,612 matched trades, yfinance bars)

| | ₹ |
|:--|--:|
| A. MFE ceiling (hindsight) | 182,961 |
| — inside STOPLOSS trades | **88,216 (48%)** |
| B. post-exit drift | **−11,300** (exits saved money ALL 5 days) |

The trail-arm-band pattern is now **7 measured days for 7**: roughly half the ceiling
sits in winners that round-tripped through stops, and exits themselves consistently
save money. Everything continues to point at the arm0.3/0.25 shadow.

## The reel: not a model — a directory

instagram.com/reel/DbbnO8DgXD0 = gittrend.io promoting a curated GitHub list
("97 libraries, 40+ strategies, 55 books"). No specific strategy to copy. Honest
translation of the ask: test the CANONICAL textbook systems those lists catalogue —
all daily-bar swing systems, which we had never tested (everything we killed was
intraday).

## The classics, 5 years of dailies, honest delivery costs, holdout from 2025

| Strategy | Train net/trade | **Holdout (2025+)** | t | Verdict |
|:--|--:|--:|--:|:--|
| sma_cross 20/50 | +1.36% | −0.22% | −1.77 | dead |
| RSI-2 (Connors) | +0.13% | −0.26% | −4.33 | dead |
| Bollinger reversion | +1.41% | +0.49% | +1.67 | near miss |
| **52-week-high breakout** | +9.81% | **+1.97%** | **+2.16** | **SURVIVES** |
| Momentum top-10 rotate | +4.64% | +0.77% | +0.83 | fails |

**hi52_break survives**: buy a 250-day-high close, trail 10% on closes. n=229 on the
holdout, +1.97%/trade after 0.24% costs, t=2.16.

**The caveat that matters — survivorship.** The universe is TODAY'S NIFTY-200 applied
backward; 2021-24 numbers are inflated by construction (today's members are
yesterday's winners — precisely what a 52w-high system loves). The verdict leans on
the 2025+ window where membership is approximately current, so the bias is small
THERE — but the honest next step is a rerun on the survivorship-free tooling in
quant/ before any capital-shaped decision.

## How our system differs from what those lists do

Same discipline (backtest → out-of-sample → costs), different battlefield. Our
intraday engines fight 0.5%-sized moves against a 0.08–0.11% toll — measured edge
0.05–0.09%, structurally under water. The classics ride multi-week 10–30% moves
against a 0.24% toll — the move-to-cost ratio is 40:1 instead of 5:1. That ratio,
not signal cleverness, is why hi52_break clears and five intraday families died.

## Next steps (per the standing gates)

1. Rerun hi52_break survivorship-free (quant/ validators) — before anything else.
2. If it holds: v5_hi52 paper lane at CNC costs, alongside v5_swing.
3. Fix v5_swing's fee model to 0.24% CNC.
4. v5_trail shadow still queued (7-of-7 days of trail-band evidence).
