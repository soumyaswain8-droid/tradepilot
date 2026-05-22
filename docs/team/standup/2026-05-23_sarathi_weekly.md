# Sarathi · Weekly Audit · Week of 2026-05-18

## Audit Tape (5 days)

| Date | BLOCK | WARN | OVERRIDE | Notes |
|------|------:|-----:|---------:|-------|
| 2026-05-18 (Mon) | 0 | 3 | 4 | Cold-start cache WARN x2, **post-hoc** v5 staleness-guard WARN (SARATHI-CDE), 4x CEO ML override |
| 2026-05-19 (Tue) | 0 | 2 | 4 | Cold-start cache WARN x2 (identical), 4x CEO ML override. Clean day. |
| 2026-05-20 (Wed) | 0 | 2 | 4 | Cold-start cache WARN x2. **Feed degradation begins — zero audit signal.** |
| 2026-05-21 (Thu) | 0 | 2 | 4 | Cold-start cache WARN x2. **v4 disaster day (4% WR) — zero pre-trade signal.** |
| 2026-05-22 (Fri) | 0 | 2 | 4 | Cold-start cache WARN x2. Feed still degraded — still no BLOCK. |
| **Total** | **0** | **11** | **20** | 5 days, 36 events, **0 BLOCKs** |

Ledger entries mirror the audit tape 1:1 (8/7/7/7/7). Decisions are consistent — there is no divergence between what Sarathi saw and what was ledgered.

## What Went Right
- Tape integrity: every preflight produced ledger + audit JSONL with consistent timestamps and rule-family labels. No silent drops.
- Monday staleness-guard incident *was* recorded (SARATHI-CDE, WARN, 09:10) within 5 minutes of the live fix — the audit chain works post-hoc.
- CEO ML overrides logged with `override_ok:true` and reason — clean accountability trail.

## What Went Wrong / Near-Misses
- **Monday v5 staleness-guard was a Sarathi miss.** Preflight at 08:50 returned WARN/OVERRIDE only on model files; it never executed the v5 startup path as a dry-run. The staleness-guard fired live at 09:10 with no pre-market warning. The 09:10 WARN is a *post-mortem entry*, not a save. **Verdict: Sarathi failure.**
- **Feed degradation is a 3-day BLOCK that didn't happen.** Wed-Fri showed >1000 → 2026 "price unavailable" entries. SARATHI-DAT logged the same boilerplate "Cache file not present (cold start)" WARN every single morning — the check is hard-wired to a cold-start branch and never re-evaluates intraday feed health. Three opportunities to escalate to BLOCK; zero taken.
- **Thursday's v4 disaster (4% WR, −₹3,856) had a structural tell** the audit didn't catch: feed degradation had been live for 24 hours and v5/v5_classic asymmetry had already inverted on Wednesday (v5 family beating v4 on a degrading feed is the canonical v4-overfit-to-clean-quote signature). There is no rule-family checking *relative model performance under feed-quality state* — so no warning was possible with the current rule set.
- **Cold-start WARN is noise, not signal.** Identical text 10 times in 5 days = a rule that has decayed into a no-op. It must either fire once at boot or be removed.

## Recommended Rule Additions (Sprint 2)

1. **SARATHI-DAT-002 "Feed Health Live Check"** — every 15 min during market hours, sample `price_unavailable` count over a 5-min window. If count > 100/window OR > 500/day, escalate WARN → BLOCK on v4 (which is most quote-sensitive). Wed-Fri this would have produced a Wed-10:00 BLOCK that protected Thursday's loss.
2. **SARATHI-CDE-002 "Engine Startup Dry-Run"** — preflight must execute the actual engine `boot()` for v5/v5_classic with a synthetic tick, not just file checks. Catches staleness-guard, missing model, deserialization regressions *before* 09:15 open. Closes the Monday miss class.
3. **SARATHI-PRF-001 "Asymmetry Inversion Alarm"** — if rolling 2-day P&L sign flips between v4 and v5-family (v4 best → v5 best on Wed, then reverts Thu), emit WARN at next preflight. Pairs with rule #1 — when feed-health degrades AND asymmetry inverts simultaneously, escalate to BLOCK on v4. Thursday's disaster had both flags up.

Lower-priority but related: retire the cold-start cache WARN or fire it only on the first boot of the day.

## Verdict

Sarathi this week was a recorder, not a risk officer. Tape is honest and complete — but 0 BLOCKs across a week that contained one live incident (Mon), three days of degraded feed (Wed-Fri), and one ₹3.8k disaster session (Thu) means the rule set is too narrow to do its job. The ML-override / cache-cold-start traffic is theatre; the rules that *would have mattered* (live feed health, engine dry-run, cross-model asymmetry) don't exist yet. Sprint 2 must add the three rules above before next Monday's open, otherwise the next degraded-feed week will look identical. Confidence in tape: high. Confidence in coverage: low.
