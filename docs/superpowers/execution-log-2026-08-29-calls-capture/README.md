# Execution log — calls capture pipeline

Working record of the subagent-driven execution that produced this branch
(`272622e..91f8e48`, 9 commits, 184 → 234 tests). Preserved because it holds
what git history does not: **the defects that were caught, and how.**

Five of the nine commits are fixes, and every one came from a review finding
rather than a test failure. Four of those findings were defects in the *plan*,
not the implementation — the plan was wrong and the code faithfully implemented
it. Those are the ones worth reading about before writing the next plan.

## Start here

`progress.md` — the ledger. Every ruling with its cost-if-wrong, the pre-flight
scan, four deferred minors, and the three findings deliberately left unfixed.

## The two most instructive failures

**A fixture that agreed with broken code.** Task 2's ten tests all passed
against a mapping that recorded every BUY as a SELL and dropped every price
level, because the fixture in the plan encoded the *same* wrong assumption as
the implementation. Fixture and code agreed with each other and both disagreed
with the live endpoint. No unit test could see it; only running the job against
the real API and reading the rows exposed it. See `task-2-report.md`.

**One key name, three engines.** The final review found `build_rows` read only
v4's `stopLoss`/`target`. The v2 and v1 engines emit `stop_loss_pct`/
`target_pct`, and `app.py` falls back between them on ImportError — so on the
fallback path every call was captured with no levels, and the resolver silently
switched to a softer grading rule. The same +0.5% move graded `miss` against a
real target and `hit` without one, pooled into one published percentage. Each
per-task review saw only one engine's shape. See `final-fix-report.md`.

## Contents

| File | What it is |
|:--|:--|
| `progress.md` | The ledger — rulings, scan, deferred items. **Start here.** |
| `task-N-report.md` | Per-task implementer reports, including fix rounds |
| `final-fix-report.md` | The final review's five-item fix wave |
| `task-N-brief.md` | Task requirements as dispatched (extracts of the plan) |
| `review-*.diff` | Diffs handed to each reviewer (duplicates of git history — prunable) |

Intent lives in the spec and plan:

- `docs/superpowers/specs/2026-08-28-client-dashboard-design.md`
- `docs/superpowers/plans/2026-08-28-calls-capture-pipeline.md`

## Known, unfixed, deliberate

Three findings were left for a human decision and are NOT bugs to discover
later — they are recorded choices:

1. **No market-holiday calendar.** Indian holidays are weekdays, so the first
   one makes `calls-status` exit 1 permanently and the alert becomes noise.
   Nothing schedules `calls-status` either.
2. **Entry and exit priced by different engines.** `price_at_call` comes from
   `/api/picks` (v4, intraday); `outcome_price` from `/api/stock/<sym>` (v2,
   daily bars).
3. **No trading-day guard on the publish job.** The Mon–Fri schedule is the only
   thing stopping a weekend capture, and it does not cover holidays.
