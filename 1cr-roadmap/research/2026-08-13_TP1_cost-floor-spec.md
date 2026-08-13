# TP-1 — Model the true achievable cost floor

*Next piece of work. Ahead of any further engine tuning.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Status** | Specified — not started |
| **Priority** | P0 — gates every other trading decision |
| **Created** | 2026-08-13 |
| **Supersedes** | Nothing. Extends `2026-08-10_week1-falsification-result.md` §"Attack cost" |

:::

---

## Why this is first

This is not an outside recommendation. It is the action item this project's own
week-1 falsification gate wrote down and did not yet execute:

> Three unrelated methodologies converge on 0.05–0.09% gross against a 0.120%
> toll. The binding constraint is **not signal discovery — it is cost**.
> …Realistic floor is perhaps 8–10 bps… **Worth costing precisely rather than
> assuming.**

Every open engine question is downstream of one unknown number. Right now the
project compares a *measured* +0.05–0.09% gross against an *assumed* 0.120%
toll. If the true achievable floor is 8 bps, some sleeves are viable. If it is
11 bps, most of the trading roadmap is theatre and the honest move is to stop
tuning and say so.

Costing this precisely takes roughly half a day. Continuing to tune the engine
without it risks spending weeks optimising against a number nobody has measured.

---

## Objective

Produce **one number with a defensible derivation**: the break-even gross return
per round trip that the engine must beat, at the position sizes actually traded,
under the cheapest broker configuration realistically available.

Plus the sensitivity around it: how that number moves with position size, broker,
and holding period.

---

## Method

### 1. Decompose the toll into its statutory and negotiable parts

| Component | Nature | Notes |
|:--|:--|:--|
| STT | Statutory | 0.025% on the sell side (intraday equity) |
| Exchange transaction charge | Statutory | NSE rate, per side |
| SEBI turnover fee | Statutory | Negligible but include |
| Stamp duty | Statutory | Buy side, state-dependent |
| GST | Statutory | On brokerage + exchange charges |
| Brokerage | **Negotiable** | Flat-fee vs percentage — the lever |
| Slippage | **Empirical** | Must be measured, not assumed |

Only brokerage and slippage are controllable. Establish the statutory floor
first — that is the number below which nothing can go.

### 2. Measure slippage rather than assuming it

Slippage is the component most likely to be wrong in the current 0.120%
assumption. Derive it from the engine's own fill data, segmented by:

- position size band (the `v5_size` ₹66,667 threshold is the live hypothesis)
- time of day (open auction vs midday liquidity are different regimes)
- instrument liquidity band (the 837-stock screened universe already exists)

### 3. Model the brokerage cliff

The `v5_size` hypothesis is that crossing ₹66,667 per position converts a flat
₹20 brokerage into <0.03% effective. Verify arithmetically, then confirm against
realised statements — the modelled and billed numbers must agree before the
result is trusted.

### 4. Publish the break-even table

Output a table of break-even gross by (position size × broker × side count), and
state which cells the engine's measured +0.05–0.09% gross actually clears.

---

## Deliverable

A single document containing:

1. The statutory floor, itemised and sourced.
2. Measured slippage by size/time/liquidity band, with sample sizes.
3. The break-even gross table.
4. A one-paragraph verdict: **which sleeves, if any, clear the floor with margin.**

---

## Decision gate — write the criteria before running

This project's recurring failure mode is unvalidated changes drifting into the
baseline and causing the next regression. So the verdict criteria are fixed here,
before the work starts:

| Outcome | Meaning | Action |
|:--|:--|:--|
| Floor ≤ 8 bps and a sleeve clears with ≥2 bps margin | Cost is beatable at size | Proceed to that sleeve's ship-gate |
| Floor 8–10 bps, no sleeve clears with margin | Cost dominates | Stop engine tuning. Re-scope to low-frequency sleeves only |
| Floor > 10 bps | Intraday cash equity is structurally unprofitable here | Stop. Escalate to a strategy decision, not an engineering one |

"No sleeve clears" is a **valid and useful result.** It is not a failure of the
work; it is the work succeeding.

---

## Explicitly out of scope

- Any new signal, predicate or entry filter. The week-1 gate already falsified
  the SMC/ICT family (`fvg`, `order_block`, `amd_phase`, `liquidity_sweep`,
  `opening_range`, `mtf_alignment`) over 145,500 simulated trades; the best
  7-of-10 confluence bucket netted −0.0364%. Do not reopen it here.
- Model retraining. The v4 and v5 regressions both trace to retrains landing
  without a pre-committed verdict.
- Anything touching the live engine's behaviour. This is measurement only.

---

## Companion track — run in a separate lane

The go-to-market work does **not** depend on the trading edge existing, and must
not be scheduled behind it. Its value proposition is the trust stack:

- exchange registration
- funds remain in the customer's own demat
- no lock-in
- a full reasoning trail for every decision

That proposition is honest and sellable whether or not TP-1 returns a viable
floor. Running it in the same lane as engine work has repeatedly meant it stalls
whenever the engine stalls.

**Compliance guardrail:** SEBI restricts performance and return claims for
regulated financial promotion, and the Oct-2024 finfluencer circular bars
regulated intermediaries from associating with unregistered promoters. No
GTM copy should reference returns until the registration position and a
machine-verified track record are both settled. Verify current text before any
public claim.
