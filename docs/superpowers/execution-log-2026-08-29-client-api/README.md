# Execution log — client API layer

Working record of the subagent-driven execution that produced this branch
(`717a7d7..32fb250`, 10 commits, 234 → 292 tests). Preserved because it holds
what git history does not: the defects caught, and how.

Six of the ten commits are fixes. Every one came from a review finding rather
than a failing test, and every one was a defect in the *plan* that the code had
faithfully implemented. Those are the ones worth reading before writing the
next plan.

## Start here

`progress.md` — the ledger. Twelve rulings with their cost-if-wrong, the
pre-flight scan, three deferred minors, and the reasoning behind what was
deliberately not fixed.

## The four most instructive failures

**A task that could not pass its own tests.** The pre-flight scan caught that
Task 1 declared registries naming all eight endpoints while only one existed,
and its own test asserted every declared name matched a real route. Found
before any code was written, by comparing a task against itself.

**A test that passed vacuously.** `test_no_engine_vocabulary_leaks_to_a_client`
could not fail: against the schema of the day, `dict(row)` and `shape_call(row)`
produce identical output, so removing the allowlist entirely left it green. It
passed because the *fixture* contained no banned words, not because the code
filtered them. The fix tests the allowlist by adding a column to a throwaway
schema — and was verified by actually removing the allowlist and watching it go
red.

**Banker's rounding in the number the product is sold on.** `round(6.25, 1)` is
`6.2`; a calculator says `6.3`. Thirty-two divergent hit/resolved pairs at
`resolved ≤ 80`, the smallest denominator being 16 — precisely the range an
empty record passes through in its first weeks, when a sceptical customer is
most likely to check by hand.

**One door validated, the other not.** POST rejected a non-positive `qty`;
PATCH accepted anything. `PATCH {"qty": "abc"}` returned 200, and then every
subsequent `GET /positions` returned 500 — permanently. The client could brick
their own book, with the damage landing on a different endpoint from the one
that caused it.

## Contents

| File | What it is |
|:--|:--|
| `progress.md` | The ledger — rulings, pre-flight scan, deferred items. **Start here.** |
| `task-N-report.md` | Per-task implementer reports, including fix rounds |
| `final-fix-report.md` | The final review's five-item fix wave |
| `task-N-brief.md` | Task requirements as dispatched (extracts of the plan) |
| `review-*.diff` | Diffs handed to each reviewer (duplicates of git history — prunable) |

Intent lives in the spec and plan:

- `docs/superpowers/specs/2026-08-28-client-dashboard-design.md`
- `docs/superpowers/plans/2026-08-29-client-api-layer.md`

The constraints that must bind the screens plan are NOT here — they were moved
into the spec's `## Deferred from the API layer` section precisely because this
directory is disposable and that one is not.
