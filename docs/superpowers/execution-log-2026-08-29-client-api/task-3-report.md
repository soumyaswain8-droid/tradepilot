# Task 3 Report: The track record endpoint

## Files modified
- `prototype/client_api.py` — added `MEANINGFUL_FROM` constant and `GET /api/app/record` endpoint (`client_api.record`)
- `prototype/client_auth.py` — added `"client_api.record"` to `PUBLIC_ENDPOINTS`
- `tests/test_client_api_record.py` — new, 8 tests

`prototype/app.py` was not touched, per instructions.

## Commands run

### Step 1/2: Write failing tests, run to confirm they fail

```
$ cd /Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/client-api
$ python3 -m pytest tests/test_client_api_record.py -q
```
(before writing implementation, run as part of full-suite baseline check below — see full output)

Full-suite run before implementation (baseline + new failing tests):

```
$ python3 -m pytest tests/ -q
...
E        +  where 404 = <WrapperTestResponse streamed [404 NOT FOUND]>.status_code
E        +    where <WrapperTestResponse streamed [404 NOT FOUND]> = <bound method Client.get of <FlaskClient <Flask 'prototype.app'>>>('/api/app/record')
E        +      where <bound method Client.get of <FlaskClient <Flask 'prototype.app'>>> = <FlaskClient <Flask 'prototype.app'>>.get

tests/test_client_api_record.py:94: AssertionError
=========================== short test summary info ============================
FAILED tests/test_client_api_record.py::test_empty_record_is_not_an_error - T...
FAILED tests/test_client_api_record.py::test_hit_rate_is_none_not_zero_when_nothing_resolved
FAILED tests/test_client_api_record.py::test_hit_rate_counts_only_hits_and_misses
FAILED tests/test_client_api_record.py::test_ungraded_calls_are_excluded_from_the_rate
FAILED tests/test_client_api_record.py::test_small_samples_are_flagged_as_not_yet_meaningful
FAILED tests/test_client_api_record.py::test_since_reports_the_first_recorded_day
FAILED tests/test_client_api_record.py::test_empty_record_reports_since_as_none
FAILED tests/test_client_api_record.py::test_record_is_public - AssertionErro...
8 failed, 257 passed in 5.84s
```

All 8 new tests failed with 404 (`/api/app/record` not registered yet), exactly as expected. Baseline of 257 pre-existing tests passed, confirming they were undisturbed.

### Step 3: Implement the endpoint

Added `MEANINGFUL_FROM = 100` and the `record()` view to `prototype/client_api.py`, verbatim per the brief. Added `"client_api.record"` to `PUBLIC_ENDPOINTS` in `prototype/client_auth.py`.

### Step 4: Run new tests to verify they pass

```
$ python3 -m pytest tests/test_client_api_record.py -q
........                                                                 [100%]
8 passed in 3.39s
```

### Step 5: Full suite

```
$ python3 -m pytest tests/ -q
........................................................................ [ 27%]
........................................................................ [ 54%]
........................................................................ [ 81%]
.................................................                        [100%]
265 passed in 5.05s
```

## Before/after test counts
- Before: 257 passed, 8 failed (new tests only)
- After: 265 passed, 0 failed

## Endpoint registration confirmation
`"client_api.record"` was added to `PUBLIC_ENDPOINTS` in `prototype/client_auth.py`:

```python
PUBLIC_ENDPOINTS = frozenset({
    "client_api.calls_list",
    "client_api.call_detail",
    "client_api.record",
})
```

This satisfies `test_every_client_route_is_classified` and `test_record_is_public` (confirmed passing above).

## Commit
SHA: `d89ef13`
Message: `feat(client-api): the track record, honest about its own sample size` (with body explaining ungraded exclusion and sample-size honesty, plus a note about the `client_auth.py` public registration since that file was also touched)

Files in commit: `prototype/client_api.py`, `prototype/client_auth.py`, `tests/test_client_api_record.py` (132 insertions, 0 deletions — new file only touches additions elsewhere).

## Anything surprising
Nothing surprising. The brief's code was copy-paste-ready and matched the existing `calls` table schema and `open_store()` seam exactly. The only deviation from the brief's suggested commit message was adding one clause noting the `client_auth.py` change, since the brief's message only mentioned `client_api.py` and the test file but the task also required (and the brief itself instructed) editing `client_auth.py` to register the endpoint as public.

## Fix round 1

Two Important findings from review, both defects in the brief's own reference code (implementation was verified correct as delivered).

### Finding 1: `round()` is round-half-to-even

`round(100.0 * hit / resolved, 1)` uses Python's banker's rounding, which diverges from calculator arithmetic at exact half-way ties (e.g. `round(6.25, 1) == 6.2`, not `6.3`). Replaced with a `_rate(hit, resolved)` helper that builds a `Decimal` from the integer numerator/denominator (avoiding binary-float error before rounding) and quantizes with `ROUND_HALF_UP`:

```python
def _rate(hit, resolved):
    if not resolved:
        return None
    exact = Decimal(100 * hit) / Decimal(resolved)
    return float(exact.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))
```

Added `from decimal import Decimal, ROUND_HALF_UP` to imports; `hit_rate` field now calls `_rate(hit, resolved)`.

Added two tests: `test_hit_rate_rounds_half_up_like_a_calculator` (1 hit of 16 resolved) and `test_hit_rate_is_still_none_when_nothing_resolved`.

### Finding 2: `is_meaningful` threshold was untested against the total/resolved distinction

`resolved >= MEANINGFUL_FROM` was already correct, but nothing in the original 8 tests would catch a regression to `len(rows) >= MEANINGFUL_FROM` (every existing fixture has `total == resolved`). Added `test_a_large_but_mostly_unresolved_record_is_not_meaningful` (120 total calls, only 3 resolved) to pin this.

### Verification commands and output

Full suite after fix:
```
$ python3 -m pytest tests/ -q
........................................................................ [ 26%]
........................................................................ [ 53%]
........................................................................ [ 80%]
....................................................                     [100%]
268 passed in 5.96s
```
265 (prior) + 3 new = 268 passed. Confirmed.

1-of-16 exact value, checked directly against the helper:
```
$ python3 -c "
from prototype.client_api import _rate
print('1/16:', _rate(1, 16))
print('nothing resolved:', _rate(0, 0))
print('resolved=0 explicit:', _rate(5, 0))
"
1/16: 6.3
nothing resolved: None
resolved=0 explicit: None
```
`hit_rate` for 1 hit of 16 resolved is exactly `6.3`. Both no-data cases (`resolved == 0`) still return `None`, not `0.0` — the helper did not regress this.

`is_meaningful` experiment — run as fresh `pytest` subprocesses with `prototype/__pycache__` and `tests/__pycache__` cleared between each:

- **Correct** (`resolved >= MEANINGFUL_FROM`): fresh run of `test_a_large_but_mostly_unresolved_record_is_not_meaningful` → **1 passed**.
- **Buggy variant** (temporarily changed to `len(rows) >= MEANINGFUL_FROM`, pycache cleared, fresh subprocess): same test → **1 failed**, `AssertionError: assert True is False` on `body["is_meaningful"] is False`. Confirms the new test catches this exact regression.
- Reverted to `resolved >= MEANINGFUL_FROM` (pycache cleared again), fresh run → **1 passed**. Full suite re-run afterward: **268 passed**.

### Files touched in this round
- `prototype/client_api.py` — `_rate()` helper, `Decimal`/`ROUND_HALF_UP` import, `hit_rate` now calls `_rate(hit, resolved)`.
- `tests/test_client_api_record.py` — 3 new tests appended.

No other files touched. `prototype/app.py` and the auth registries were not modified in this round.

### Commit
SHA: `1baa9a1`
Message: `fix(client-api): half-up rounding for hit_rate, pin is_meaningful to resolved`
