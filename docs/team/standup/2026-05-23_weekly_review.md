# Weekly Review — Week of 2026-05-18 (Sprint 1 Live Week)

**Date:** 2026-05-23 (Saturday post-close)
**Compiled by:** Soumya + 3 agents (Sarathi · Alpha Hunter · Execution Analyst)
**Status:** Sprint 1 closing → Sprint 2 opens Monday

---

## TL;DR — Three Findings That Reframe the Project

1. **Realized exit slippage is ~210 bps — 20× our 10bps assumption.** After applying measured slippage, v5 and v5_classic are **break-even, not profitable**. The week's ~₹80k gross modeled P&L was eaten by ~₹87k of un-modeled execution cost. **The whole "what should our Sharpe be?" math has been off by an order of magnitude.**

2. **STOPLOSS exits are the killer** — 168 legs × +283 bps adverse = ₹49.5k weekly drag (57% of total cost). TARGET exits are actually favorable (−58 bps). One execution change (limit order + 3s TIF + market sweep on stops) could recover ~₹25k/week.

3. **Thursday's inversion was a stock-pick divergence, not signal divergence.** All three engines went 100% LONG. v4 took 46 mid-cap cyclicals (ADANIENSOL, ADANIENT, SAIL, FORTIS = ₹3,278 of v4's ₹3,856 loss) in bottom-quartile sectors. v5/v5_classic took large-cap defensives (PIIND, POWERINDIA, BOSCHLTD) and made money. **A sector-relative-strength gate would have killed ~30 of v4's 46 Thursday trades before entry.**

---

## The Numbers (Gross Modeled vs Cost-Corrected)

| Engine | Gross weekly | Modeled cost @12bps | Modeled net | **Measured slippage cost** | **Cost-corrected net** | Weekly Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| v4 | +₹17,373 | ~₹2k | +₹15,373 | **not measured** (S2-MAIN-002 deferred) | unknown | 0.74 |
| v5 | +₹1,698 | ~₹2k | small | ~₹44k adverse | **−₹1,047** | 0.24 → ~0 |
| v5_classic | +₹1,604 | ~₹2k | small | ~₹43k adverse | **~₹0** | 0.16 → ~0 |

`★ Insight ─────────────────────────────────────`
**v5 and v5_classic looked positive but were actually break-even.** v4's number is the only one we can still claim, but we don't yet know v4's true slippage because Sprint 1's slippage hook wasn't wired into v4 (S2-MAIN-002 deferred). At similar slippage, v4's +₹15k net could be closer to flat too.
`─────────────────────────────────────────────────`

---

## Day-by-Day This Week

| Day | v4 | v5 | v5_classic | Note |
|---|---:|---:|---:|---|
| Mon May 18 | +₹9,296 (69% WR) | −₹1,631 (34%) | −₹1,852 (23%) | v5 staleness-guard 10-min outage; fixed live |
| Tue May 19 | +₹1,931 (47%) | +₹890 (56%) | +₹966 (59%) | Clean morning, all engines positive |
| Wed May 20 | +₹5,048 (54%) | +₹790 (48%) | +₹482 (44%) | Feed degradation begins — quote cache missing |
| **Thu May 21** | **−₹3,856 (4%)** | +₹1,606 (16%) | +₹3,228 (23%) | **INVERSION**: v4 lost mid-cap cyclicals, v5 family caught large-cap defensives |
| Fri May 22 | +₹5,954 (49%) | −₹157 (46%) | −₹1,220 (44%) | Feed still degraded (2,026 "price unavailable" entries) |

---

## What Each Agent Found

### Sarathi (Risk/Audit)

**Tape stats:** 5 days · 0 BLOCK · 11 WARN · 20 OVERRIDE.

**Three misses identified:**
1. **Monday's v5 staleness-guard incident** — preflight passed but didn't dry-run engine startup. *(Already filed as S2-PM-001)*
2. **Feed degradation never escalated** — Wed/Thu/Fri all had "price unavailable" >1000 entries, Sarathi DAT only WARN'd. The rule should BLOCK once `(missing cache AND >30% per-symbol fallback failure rate)` persists past 09:30.
3. **Thursday's v4 disaster had a detectable signature** — Wednesday showed v4/v5 P&L gap inverting direction, and no rule was watching for it. A "cross-model asymmetry-inversion" alarm would have flagged Wednesday EOD → review window before Thursday open.

**3 new Sarathi rules recommended for Sprint 2:**
- `SARATHI-DAT-005` — live feed-health, 15-min cadence, BLOCK on threshold
- `SARATHI-CDE-006` — engine startup dry-run inside preflight (= S2-PM-001 with new name)
- `SARATHI-PRF-001` — cross-model asymmetry-inversion alarm

### Alpha Hunter (Quant Research)

**Weekly Sharpe per engine (gross, pre-slippage):** v4 0.74 · v5 0.24 · v5_classic 0.16.

**Thursday inversion — stock-pick divergence, not signal divergence:**
- All 3 engines went 100% LONG (no asymmetry in direction)
- Only 7 symbols overlapped between v4 and v5_classic
- v4's losers: bottom-quartile sectors in a BEAR regime (metals, realty, utilities, infra)
- v5/v5_classic's winners: large-cap defensives (PIIND, POWERINDIA, BOSCHLTD, GRASIM)

**Sprint 3 first feature recommendation: `sector_relative_strength`**
- v4's Thursday losers were all bottom-quartile sectors
- A sector RS gate would have killed ~30 of v4's 46 Thursday trades before entry
- This matches our deep-research finding from Agent C (May-14)

**Surprise finding — Track A has a hidden cost:**
- WINNER_RE_ARM (the rule that made the April-22 ₹61k day) **cost v5 ~₹1,622 on Thursday** by blocking continuation re-entries on GVT&D / PIIND / GRASIM that v5_classic captured (no re-arm rule)
- The rule fires only on TARGET, never on STOPLOSS — but on a falling day, it suppresses good re-entries that should be allowed

### Execution Analyst (Slippage)

**The bombshell:** 419 exit legs captured this week. Mean adverse slippage:

| Engine | Legs | Mean bps | Median bps | P95 bps |
|---|---:|---:|---:|---:|
| v5 | 222 | +215 | +180 | +388 |
| v5_classic | 197 | +208 | +175 | +375 |

**By exit reason:**

| Reason | Legs | Mean bps | Behavior |
|---|---:|---:|---|
| TARGET | 187 | **−58 (favorable)** | We exit at our price → small positive slippage |
| TIME_EXIT | 64 | +95 (modest adverse) | Forced exit, modest cost |
| **STOPLOSS** | **168** | **+283 (THE killer)** | **57% of total weekly cost** |

**By trade size:** No effect — all trades are <₹50k. Size is not the lever.

**Cost-corrected weekly P&L** (v5 only, v4 not instrumented):
- v5 gross +₹1,698 → net **−₹1,047**
- v5_classic gross +₹1,604 → net **~₹0**

**Sprint 2 recommendation:** replace STOPLOSS market-on-touch with 2-tick limit + 3s TIF + market sweep fallback. Halving SL slippage recovers ~₹25k/week.

---

## Strategic Implications

### 1. The Sharpe-1.5 target needs revisiting

We set Sharpe 1.5 net of **10bps** in 6 months as the target (Synthesis option 1B, 2026-05-14). Reality: net of **210bps**. Either:
- Target stays 1.5, but assumed slippage moves to 100-150bps (still big), AND we execute the STOPLOSS fix
- OR target lowers to Sharpe 1.0 net 200bps if we can't fix execution

**Recommendation: keep 1.5 target, fix execution. The Sprint 2 STOPLOSS fix is the highest-leverage action available right now.**

### 2. v4's true cost is the biggest unknown

S2-MAIN-002 (wire slippage into v4) was originally medium priority. After this week, **promote to high**. We can't claim v4 is profitable without knowing its real cost. v4 trades more per day (avg 53 vs 49 vs 38) — same cost-per-trade → bigger absolute drag.

### 3. Track A WINNER_RE_ARM needs evaluation

It's been the cluster-day amplifier (April-22 ₹61k). But on Thursday, it BLOCKED ₹1,622 of v5 continuation trades that v5_classic caught. The rule has both an upside and downside, and we've only been measuring the upside. Sprint 2 should add measurement of "re-arm cost" days, and decide:
- Keep it as-is (current bet: cluster-day upside > continuation-block downside on average)
- Soften it (allow re-arm on TARGET OR on TIME_EXIT-flat)
- Drop it (revert to no re-arm; trade discipline via meta-label instead)

### 4. Sector-relative-strength is now Sprint 3's confirmed first feature

Three independent signals point at it:
- Alpha Hunter's May-17 weekly audit recommended it as Sprint 3 first add
- This week's Thursday inversion would have been avoided by it
- Deep research (Agent C, May-14) flagged it in top-3 features

Sprint 3 = sector_relative_strength + OFI + Kyle's λ. Add the gate FIRST, then the predictive features.

---

## Sprint 2 Backlog Updates (additions)

Sprint 2 (TP-S2-001) currently has 8 tasks. Adding 4 from this review:

| New ID | Title | Priority | Origin |
|---|---|:--:|---|
| S2-EXEC-001 | STOPLOSS limit-order pattern (2-tick + 3s TIF + market sweep) | **high** | Execution Analyst — ~₹25k/wk recovery |
| S2-PM-008 | SARATHI-DAT-005 live feed-health BLOCK rule | **high** | Sarathi — 3-day feed degradation went uncaught |
| S2-PM-009 | SARATHI-PRF-001 cross-model asymmetry-inversion alarm | medium | Sarathi — Thursday early-warning |
| S2-EXEC-002 | Track A re-arm cost measurement | medium | Alpha Hunter — quantify upside vs downside |

**S2-MAIN-002 (v4 slippage wire) promoted to high priority** — we cannot evaluate v4 without it.

---

## What Went Right (Sprint 1's wins still hold)

- **Automation fired every day** — pmset wake, preflight, DAT, engines-on, mid-market, exec-eod, standup, backup
- **Sarathi audit log is the truth source** — every decision recorded, replayable. Made the Monday postmortem possible.
- **Slippage instrumentation surfaced the biggest finding** of the rebuild
- **CEO override system worked** — engines ran on the legacy model all week without surprise
- **Dashboard at /team gave visibility** — every status check this week was 5 seconds

---

## What Went Wrong (Sprint 2 addresses each)

- Monday: v5 staleness-guard outage (10 min) → **fixed live + S2-PM-001 backstops**
- Wed-Fri: feed degradation never escalated → **S2-PM-008 adds the rule**
- Thu: v4 disaster had detectable Wednesday signature, no alarm → **S2-PM-009 adds it**
- Whole week: STOPLOSS slippage 20× modeled → **S2-EXEC-001 is the fix**
- Whole week: v4 slippage unmeasured → **S2-MAIN-002 wires it**

---

## Override Countdown

`2026-07-15` — **53 days remaining.** Sprint 2 starts Monday, the override has 7.5 weeks left, and the rebuild has 5 full sprints to deliver.

---

## Honest Verdict

`★ Insight ─────────────────────────────────────`
**The system isn't broken — but it isn't profitable either.** Sprint 1 built the safety harness and surfaced the truth. This week's data tells us:

- We're NOT a Sharpe 1.5 system today. At realized slippage, v5 family is break-even and v4 is the only thing carrying ostensible P&L (which itself may shrink when v4's cost is measured).
- The headline path to profitability is **NOT a better model — it's better execution**. Halving STOPLOSS slippage with one engineering change (limit order + sweep) recovers more weekly P&L than any ML improvement we have planned in Sprints 3-7.
- The features-and-labels rebuild (triple-barrier, sector-RS, OFI, meta-label) is still the right direction — it just doesn't matter if execution destroys 200 bps per stop.

**Sprint 2 must lead with execution, not features.** The 8-week plan stays, but the FIRST week's #1 task moves from "triple-barrier labels" to "STOPLOSS limit-order pattern."
`─────────────────────────────────────────────────`

---

## Files this review references

- `/docs/team/standup/2026-05-23_sarathi_weekly.md` — Sarathi's full audit
- `/docs/research/weekly/2026-05-23_v4_vs_v5_analysis.md` — Alpha Hunter's full deep dive
- `/docs/exec/2026-05-23_weekly_slippage_review.md` — Execution Analyst's full review
- `/docs/team/backlog/sprint2.md` — Sprint 2 backlog (will be updated with the 4 new tasks)

---

*Compiled Saturday 2026-05-23 by Soumya + 3 LLM agents running in parallel. Total agent runtime ~6 minutes; this synthesis ~30 minutes.*
