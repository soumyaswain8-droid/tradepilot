# Task 2 Report: Calls and call detail

## Files created / modified
- Created: `tests/test_client_api_calls.py` (11 tests, verbatim from brief)
- Modified: `prototype/client_api.py` (added `open_store()`, `CALL_FIELDS`, `shape_call()`, `DEFAULT_CALL_LIMIT`/`MAX_CALL_LIMIT`, `calls_list()` at `GET /calls`, `call_detail()` at `GET /calls/<call_id>`; added imports `datetime`, `request`, `app_store`)
- Modified: `prototype/client_auth.py` (`PUBLIC_ENDPOINTS` populated with `client_api.calls_list` and `client_api.call_detail`)
- **Did not touch** `prototype/app.py` (per instructions)

## Commands and output

### Baseline (before any changes)
```
$ python3 -m pytest tests/ -q
........................................................................ [ 29%]
........................................................................ [ 59%]
........................................................................ [ 88%]
............................                                             [100%]
244 passed in 5.13s
```

### Step 2: run new tests before implementation exists (expected to fail)
```
$ python3 -m pytest tests/test_client_api_calls.py -q
...
E       AttributeError: <module 'prototype.client_api' from '.../prototype/client_api.py'> has no attribute 'open_store'
...
=========================== short test summary info ============================
ERROR tests/test_client_api_calls.py::test_empty_table_returns_an_empty_list_not_an_error
ERROR tests/test_client_api_calls.py::test_calls_are_returned_newest_first
ERROR tests/test_client_api_calls.py::test_a_call_carries_its_plain_english_reason
ERROR tests/test_client_api_calls.py::test_no_engine_vocabulary_leaks_to_a_client
ERROR tests/test_client_api_calls.py::test_call_detail_returns_one_call
ERROR tests/test_client_api_calls.py::test_unknown_call_id_404s_without_leaking
ERROR tests/test_client_api_calls.py::test_an_open_call_reports_no_outcome
ERROR tests/test_client_api_calls.py::test_a_resolved_call_reports_its_outcome
ERROR tests/test_client_api_calls.py::test_calls_response_is_bounded_by_default
ERROR tests/test_client_api_calls.py::test_a_client_cannot_request_the_whole_table
ERROR tests/test_client_api_calls.py::test_calls_endpoint_is_public
11 errors in 10.78s
```
All 11 failed for the expected reason: the `store` fixture's `monkeypatch.setattr(client_api, "open_store", ...)` raised `AttributeError` because `open_store` did not exist yet.

### Step 4: run new tests after implementation
```
$ python3 -m pytest tests/test_client_api_calls.py -q
...........                                                              [100%]
11 passed in 4.31s
```

### Step 5: full suite
```
$ python3 -m pytest tests/ -q
........................................................................ [ 28%]
........................................................................ [ 56%]
........................................................................ [ 84%]
.......................................                                  [100%]
255 passed in 4.83s
```

## Test counts
- Before: 244 passed
- After: 255 passed (244 + 11 new)
- (Note: the brief's own Step 5 text says "253 passed (242 + 11)" — that reflects an earlier expected baseline before Task 1's actual state. The task instructions given to me stated baseline 244 → 255, which matches what I actually measured both before and after. No discrepancy in outcome, just in the brief's stale arithmetic comment.)

## PUBLIC_ENDPOINTS confirmation
`prototype/client_auth.py` `PUBLIC_ENDPOINTS` is now:
```python
PUBLIC_ENDPOINTS = frozenset({
    "client_api.calls_list",
    "client_api.call_detail",
})
```
Both endpoint names from this task are registered as public. `test_every_client_route_is_classified` (part of the existing enumeration test suite, run as part of the 255-passing full suite) confirms no unclassified endpoint slipped through.

## Commit
```
f9c4c78 feat(client-api): serve published calls from the record
```
3 files changed, 194 insertions(+), 3 deletions(-). Message matches the brief's Step 6 text verbatim.

## Anything surprising
- The brief's own inline comment in Step 5 ("253 passed (242 + 11)") doesn't match the actual pre-task baseline (244), which matches what the task instructions I was given stated. This is a stale note inside the brief document itself, not a defect in the implementation — flagging for visibility only, no action taken since it doesn't affect the code or test outcomes.
- Everything else followed the brief exactly: no redesign of Task 1 interfaces, `app.py` untouched, `open_store()` defined as a named module-level function (not inlined) so the test fixture's monkeypatch works, `request` added to the existing flask import line rather than a new import line.
- `git commit` picked up all three intended files cleanly; `prototype/app.py` and `.superpowers/` were never staged.

## Fix round 1

Review found the implementation correct (endpoints, ordering, clamp, connection handling, registry updates all right). Three findings, all in test coverage / robustness, not logic deviation.

### Finding 1 (Important) -- `test_no_engine_vocabulary_leaks_to_a_client` passes vacuously
Added `test_a_column_added_later_cannot_leak_through_shape_call`, which `ALTER TABLE calls ADD COLUMN engine TEXT` on the per-test throwaway DB, inserts a row carrying `"v4-composite_scorer"` in that column, and asserts it never reaches the listing or detail response bodies (and is absent from the detail JSON's keys).

**dict(row) experiment -- performed, not just claimed:**
1. Backed up `prototype/client_api.py` to `/tmp/client_api.py.bak`.
2. Swapped both call sites (`shape_call(r)` -> `dict(r)` in `calls_list`, `shape_call(row)` -> `dict(row)` in `call_detail`).
3. Ran `python3 -m pytest tests/test_client_api_calls.py::test_a_column_added_later_cannot_leak_through_shape_call -q`.
   **Result: FAILED**, as expected --
   ```
   AssertionError: assert 'v4-composite_scorer' not in '{"as_of":"...",...}'
   'v4-composite_scorer' is contained here:
     "engine":"v4-composite_scorer","horizon":null,"id":"c1",...
   ```
4. Restored `prototype/client_api.py` from the backup (`cp /tmp/client_api.py.bak prototype/client_api.py`), confirmed via `git diff --stat` that only the Finding 2 change remained.
5. Re-ran the same test with `shape_call` restored: **1 passed**.

**Temp-DB confirmation:** the `store` fixture uses pytest's function-scoped `tmp_path` fixture -- `path = str(tmp_path / "api.db")` -- a fresh, unique directory per test invocation, never the real `prototype/tradepilot_app.db`. The `ALTER TABLE` in the new test runs only against that one test's throwaway file and is discarded with the temp directory after the test.

### Finding 2 (Minor) -- `open_store()` could leak a connection
Wrapped `app_store.init_db(conn)` in `try/except Exception: conn.close(); raise` inside `open_store()`, exactly as specified in the review. No behavioural change on the happy path (schema is `IF NOT EXISTS`, already applied) -- only closes the handle before re-raising if `init_db` ever fails.

### Finding 3 (Minor) -- clamp edges untested
Added `test_limit_edges_cannot_produce_an_empty_or_reversed_page`, asserting `?limit=0` and `?limit=-5` both clamp to `1`, and `?limit=10.5` falls back to the default (`50`).

### Commands and full-suite result
```
$ python3 -m pytest tests/test_client_api_calls.py -q
.............                                                            [100%]
13 passed in 3.98s

$ python3 -m pytest tests/ -q
........................................................................ [ 28%]
........................................................................ [ 56%]
........................................................................ [ 84%]
.........................................                                [100%]
257 passed in 7.60s
```

### Test counts
- Before fix round 1: 255 passed
- After fix round 1: 257 passed (255 + 2 new)

### Scope check
`git diff` before commit touched only `prototype/client_api.py` (the `open_store` try/except) and `tests/test_client_api_calls.py` (the two new tests). `prototype/app.py` and `prototype/client_auth.py`'s registries were not touched; nothing under `.superpowers/` was staged.

### Commit
```
9598874 fix(client-api): close leaked handle on init failure, test the allowlist and clamp edges
```
2 files changed, 41 insertions(+), 1 deletion(-).
