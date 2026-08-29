# Task 1 Report: The auth seam, the guard, and the enumeration test

## Files created / modified

- Created: `prototype/client_auth.py`
- Created: `prototype/client_api.py`
- Modified: `prototype/app.py` (4 lines added, 0 removed)
- Created: `tests/test_client_auth.py`

## Correction applied

Per the controller's override, `PUBLIC_ENDPOINTS` was declared as `frozenset()`
and `GATED_ENDPOINTS` as `frozenset({"client_api.me"})` in `client_auth.py`,
instead of the brief's full eight-endpoint registries (which name endpoints
that don't exist until Tasks 2-4 and would fail
`test_registries_name_only_real_endpoints`).

## Commands and output

### Step 0: Baseline test count (before any changes)

```
$ cd /Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/client-api
$ python3 -m pytest tests/ -q
........................................................................ [ 30%]
........................................................................ [ 61%]
........................................................................ [ 92%]
..................                                                       [100%]
234 passed in 9.19s
```

### Step 1: Write the failing tests

Created `tests/test_client_auth.py` verbatim from the brief.

### Step 2: Run to verify they fail

```
$ python3 -m pytest tests/test_client_auth.py -q
==================================== ERRORS ====================================
__________________ ERROR collecting tests/test_client_auth.py __________________
ImportError while importing test module '.../tests/test_client_auth.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
../../../../../../anaconda3/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests/test_client_auth.py:17: in <module>
    from prototype import client_auth
E   ImportError: cannot import name 'client_auth' from 'prototype' (.../prototype/__init__.py)
=========================== short test summary info ============================
ERROR tests/test_client_auth.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.06s
```

Failed for the right reason: `prototype.client_auth` does not exist yet. (The
brief predicted `ModuleNotFoundError`; the actual error is `ImportError`
because `prototype/__init__.py` exists and imports partially succeed before
failing to find the `client_auth` attribute/submodule — same root cause,
different exception subclass.)

### Step 3: Write the auth seam

Created `prototype/client_auth.py` with the corrected (task-1-scoped)
registries as specified in the controller's correction above. Everything
else (docstrings, `current_user()`, `install_guard()`) verbatim from the
brief.

### Step 4: Write the blueprint with `/api/app/me`

Created `prototype/client_api.py` verbatim from the brief.

### Step 5: Register the blueprint in `app.py`

Inserted the four lines after the existing app-setup block (`app = Flask(...)`,
`CORS(...)`, `app.config["TEMPLATES_AUTO_RELOAD"] = True`), immediately before
`def get_model_meta():`. Placed after all three setup statements (not
immediately after the bare `Flask()` call) so the app object is fully
configured before the blueprint registration and guard installation run
against it. No existing line was reordered, reformatted, or removed.

### `git diff prototype/app.py` (exact output)

```
diff --git a/prototype/app.py b/prototype/app.py
index 92e5540..3d3c6a4 100644
--- a/prototype/app.py
+++ b/prototype/app.py
@@ -53,6 +53,10 @@ app = Flask(__name__,
 CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*", "https://tradepilot.onrender.com"])  # Restricted CORS
 app.config["TEMPLATES_AUTO_RELOAD"] = True  # pick up template edits without a process restart (debug stays off)
 
+from prototype import client_auth                        # noqa: E402
+from prototype.client_api import bp as _client_api_bp    # noqa: E402
+app.register_blueprint(_client_api_bp)
+client_auth.install_guard(app)
 
 def get_model_meta():
     # Prefer v2 meta
```

`git diff --numstat prototype/app.py` confirms: `4  0  prototype/app.py`
— four lines added, zero removed, as required.

### Step 6: Run to verify they pass

```
$ python3 -m pytest tests/test_client_auth.py -q
........                                                                 [100%]
8 passed in 4.49s
```

### Step 7: Confirm the whole suite still passes

```
$ python3 -m pytest tests/ -q
........................................................................ [ 29%]
........................................................................ [ 59%]
........................................................................ [ 89%]
..........................                                               [100%]
242 passed in 5.79s
```

### Step 8: Commit

```
$ git add prototype/client_auth.py prototype/client_api.py prototype/app.py tests/test_client_auth.py
$ git commit -m "feat(client-api): the auth boundary, and a test that enumerates it ..."
[feat/client-api 98f8921] feat(client-api): the auth boundary, and a test that enumerates it
 4 files changed, 142 insertions(+)
 create mode 100644 prototype/client_api.py
 create mode 100644 prototype/client_auth.py
 create mode 100644 tests/test_client_auth.py
```

## Test counts

| Stage | Count |
|---|---|
| Before (full suite, no changes) | 234 passed |
| New test file alone (after implementation) | 8 passed |
| After (full suite) | 242 passed |

## Commit SHA

`98f89218a1d4233a17f609eea93857dc0b0339b4`

## Anything surprising

1. The brief predicted a `ModuleNotFoundError` for the pre-implementation
   failing run; the actual exception was `ImportError` (same root cause —
   `prototype.client_auth` doesn't exist — different exception class because
   `prototype/__init__.py` exists as a real package). Not a blocker, noted
   for accuracy.
2. My first attempt at the `app.py` edit inserted an extra blank line
   (matching the original two-blank-line PEP8 spacing before
   `def get_model_meta():`), which made `git diff --numstat` report 5 added
   lines instead of 4. Caught this via `--numstat` before committing and
   removed the extra blank line so the diff is exactly 4 added / 0 removed,
   matching the brief's explicit requirement.
3. No other files under `prototype/` or `tests/` needed changes. Nothing else
   in the repo imports `client_auth` or `client_api` yet, as stated in the
   task context.

---

## Fix round 1

Two Important findings from review, both defects in test code from the brief
(not implementation errors). One minor style fix.

### Finding 1 -- `_app_endpoints()` matched a substring, not a path segment

`str(r.rule).startswith("/api/app")` would sweep a future operator route like
`/api/apply` into the client registry. Fixed to match on a path boundary:

```python
if str(r.rule) == "/api/app" or str(r.rule).startswith("/api/app/")
```

Added `test_a_route_merely_starting_with_the_same_letters_is_not_swept_in`,
which registers `/api/apply` and `/api/app/thing` on a throwaway probe Flask
app and asserts only the latter is picked up.

### Finding 2 -- `test_the_operator_surface_is_untouched` could not detect the failure it was named for

The guard's `endpoint in GATED_ENDPOINTS and current_user() is None` short-
circuits on the second operand when `current_user` is never patched to
`None`, so the original test only proved `/api/indices` answers a signed-in
caller -- it would still pass if the guard gated every endpoint in the app.
Kept the original test and added
`test_the_operator_surface_stays_open_to_a_signed_out_caller`, which patches
`current_user` to `None` and asserts BOTH halves in that state: `/api/indices`
still 200, `/api/app/me` still 401. That pair is what actually demonstrates
scoping.

### Finding 3 (minor) -- missing docstring on `_guard_client_api`

Added: `"""Refuse a gated client endpoint when nobody is signed in."""`

### Files touched

- `tests/test_client_auth.py` -- boundary-matching predicate fix, 2 new tests
- `prototype/client_auth.py` -- 1-line docstring addition only

`prototype/app.py` and `prototype/client_api.py` were NOT touched, per
instruction.

### Commands and output

**Full suite after both fixes:**

```
$ python3 -m pytest tests/ -q
........................................................................ [ 29%]
........................................................................ [ 59%]
........................................................................ [ 88%]
............................                                             [100%]
244 passed in 4.59s
```

**Just the client-auth test file (10 = 8 original + 2 new):**

```
$ python3 -m pytest tests/test_client_auth.py -q
..........                                                               [100%]
10 passed in 4.63s
```

### Proving each new test actually catches its defect

Both checks were done empirically, not by reasoning alone -- by temporarily
reintroducing the pre-fix code in a scratch copy, running only the new test
against it, observing the failure, then restoring the fix and re-diffing to
confirm no permanent change leaked in.

**Boundary test vs. the old substring predicate:**

Swapped `_app_endpoints()` back to `str(r.rule).startswith("/api/app")` (no
boundary check) in a temp copy of the test file, then ran only the new test:

```
$ python3 -m pytest tests/test_client_auth.py::test_a_route_merely_starting_with_the_same_letters_is_not_swept_in -q
...
        found = _app_endpoints(probe)
        assert "_thing" in found
>       assert "_apply" not in found
E       AssertionError: assert '_apply' not in {'_apply', '_thing'}
tests/test_client_auth.py:73: AssertionError
1 failed in 3.43s
```

Confirmed FAIL against the old substring predicate, for the exact reason
Finding 1 describes: `/api/apply` gets swept into the client registry.

**Signed-out scoping test vs. a hypothetically broadened guard:**

Temporarily changed the guard condition in a scratch copy of
`client_auth.py` from `endpoint in GATED_ENDPOINTS and current_user() is
None` to just `current_user() is None` (simulating a guard that gates every
endpoint, not only `GATED_ENDPOINTS`), then ran the new test:

```
$ python3 -m pytest tests/test_client_auth.py::test_the_operator_surface_stays_open_to_a_signed_out_caller -q
...
        monkeypatch.setattr(client_auth, "current_user", lambda: None)
>       assert client.get("/api/indices").status_code == 200
E       AssertionError: assert 401 == 200
1 failed in 2.76s
```

Confirmed FAIL against the broadened guard. For contrast, ran the *original*
`test_the_operator_surface_is_untouched` against that same broadened guard:

```
$ python3 -m pytest tests/test_client_auth.py::test_the_operator_surface_is_untouched -q
.                                                                        [100%]
1 passed in 4.11s
```

It passed -- confirming Finding 2's point exactly: the original test cannot
detect a guard broadened to cover the whole app, and the new test can.

After both checks, restored the fixed files and confirmed the working tree
diff contained only the intended changes (`git diff --stat`):

```
 prototype/client_auth.py  |  1 +
 tests/test_client_auth.py | 42 ++++++++++++++++++++++++++++++++++++++++--
 2 files changed, 41 insertions(+), 2 deletions(-)
```

`prototype/app.py` and `prototype/client_api.py` showed zero diff.

### Test counts

| Stage | Count |
|---|---|
| Before fix round 1 | 242 passed |
| After fix round 1 | 244 passed |

