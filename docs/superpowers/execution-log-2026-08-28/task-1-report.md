# Task 1 Report: Web-Layer Test Harness

## Summary
Successfully created the Flask test harness for TradePilot's web surface. Built conftest.py with pytest fixtures and test_web_routes.py with three route tests. All baseline tests remain green (172 passed, +3 from this task). Honesty check passed: tests correctly detect failures and recover when fixed.

## Files Created

### 1. tests/conftest.py
- **Purpose**: Shared pytest fixtures for web-layer tests
- **Content**: Flask app fixture (session scope) and client fixture (function scope)
- **Key detail**: Manually adds repo root to sys.path to accommodate prototype/app.py's import-time path manipulation

### 2. tests/test_web_routes.py
- **Purpose**: Web-layer test coverage (previously 0)
- **Tests**:
  - `test_terminal_renders()`: GET / returns 200 with b"TRADEPILOT" sentinel
  - `test_floor_renders()`: GET /floor returns 200 with b"Market Scan" sentinel
  - `test_team_renders()`: GET /team returns 200 with b"<h1>TradePilot Quant Desk</h1>" sentinel

### 3. prototype/__init__.py
- **Purpose**: Python package initialization (was missing, required for import)
- **Content**: Empty (0 bytes)
- **Note**: Created because `from prototype.app import app` requires the prototype directory to be a package

## Commands and Output

### Step 1: Verify test files don't exist
```bash
$ ls -la tests/conftest.py tests/test_web_routes.py 2>&1
ls: tests/conftest.py: No such file or directory
ls: tests/test_web_routes.py: No such file or directory
```

### Step 2: Run the web routes tests (expected: 3 PASS)
```bash
$ python3 -m pytest tests/test_web_routes.py -v
============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-7.4.0, pluggy-1.0.0
cachedir: .pytest_cache
rootdir: /Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/terminal-agent-floor
plugins: hydra-core-1.3.2, anyio-1.0.0
collecting ... collected 3 items

tests/test_web_routes.py::test_terminal_renders PASSED                   [ 33%]
tests/test_web_routes.py::test_floor_renders PASSED                      [ 66%]
tests/test_web_routes.py::test_team_renders PASSED                       [100%]

============================== 3 passed in 3.26s ===============================
```

**Result**: All three tests PASS ✓

### Step 3: Honesty check - break and verify test detects failure

#### 3a. Temporarily change sentinel to invalid string
```python
# Changed line 14 from:
assert b"TRADEPILOT" in r.data
# To:
assert b"THIS_STRING_IS_NOT_IN_THE_PAGE" in r.data
```

#### 3b. Run the broken test (expected: FAIL)
```bash
$ python3 -m pytest tests/test_web_routes.py::test_terminal_renders -v
============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-7.4.0, pytest-7.4.0
collecting ... collected 1 item

tests/test_web_routes.py::test_terminal_renders FAILED                   [100%]

=================================== FAILURES ===================================
____________________________ test_terminal_renders _____________________________

client = <FlaskClient <Flask 'prototype.app'>>

    def test_terminal_renders(client):
        """GET / returns the terminal shell."""
        r = client.get("/")
        assert r.status_code == 200
>       assert b"THIS_STRING_IS_NOT_IN_THE_PAGE" in r.data
E       assert b'THIS_STRING_IS_NOT_IN_THE_PAGE' in b'<!DOCTYPE html>\n<html lang="en">\n...'

tests/test_web_routes.py:14: AssertionError
---------------------------- Captured stdout setup -----------------------------
[ENGINE] v2 ensemble loaded (XGBoost + LightGBM)
[ENGINE] v3 regime-aware engine loaded
[ENGINE] v4 composite scorer loaded
=========================== short test summary info ============================
FAILED tests/test_web_routes.py::test_terminal_renders - assert b'THIS_STRING...
============================== 1 failed in 2.84s ===============================
```

**Result**: Test FAILS with clear assertion error ✓

#### 3c. Revert sentinel to correct value
```python
# Changed back to:
assert b"TRADEPILOT" in r.data
```

#### 3d. Re-run the fixed test (expected: PASS)
```bash
$ python3 -m pytest tests/test_web_routes.py::test_terminal_renders -v
============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-7.4.0, pytest-7.4.0
collecting ... collected 1 item

tests/test_web_routes.py::test_terminal_renders PASSED                   [100%]

============================== 1 passed in 2.69s ===============================
```

**Result**: Test PASSES after fix ✓

### Step 4: Baseline test suite verification (expected: 172 passed = 169 + 3 new)
```bash
$ python3 -m pytest tests/ -q
........................................................................ [ 41%]
........................................................................ [ 83%]
............................                                             [100%]
172 passed in 3.02s
```

**Result**: Baseline green, +3 new tests accounted for ✓

### Step 5: Commit
```bash
$ git add tests/conftest.py tests/test_web_routes.py prototype/__init__.py
$ git commit -m "test(web): first coverage for the Flask surface

Seventy routes, zero tests. The terminal shipped a blank tab on 2026-08-03
because a script tag was silently discarded and nothing caught it. This is
the harness that makes that class of bug fail before the browser does."

[feat/terminal-agent-floor 7957366] test(web): first coverage for the Flask surface
 3 files changed, 55 insertions(+)
 create mode 100644 prototype/__init__.py
 create mode 100644 tests/conftest.py
 create mode 100644 tests/test_web_routes.py
```

**Commit SHA**: `7957366`

## Step 3 Honesty Check Details

✅ **Sentinel detection works correctly**
- Breaking the sentinel (changing to non-existent string) causes test to FAIL with clear assertion error
- Full response body is shown in the error output, confirming test is reading actual HTML
- The error message shows the expected vs. actual data comparison
- After reverting to correct sentinel, test immediately PASSES
- This confirms the harness is **not** passing vacuously — it is actively validating response content

## Surprises & Observations

1. **prototype/__init__.py was missing**: The import path `from prototype.app import app` required the prototype directory to be a valid Python package. Creating an empty __init__.py file was necessary and expected per the brief's instructions.

2. **Three routes already exist and work**: The Flask app has `/`, `/floor`, and `/team` routes already implemented with the expected sentinels in their HTML responses. The harness correctly validates existing behavior.

3. **Engine startup verbose output**: When the Flask app initializes, it prints engine load messages to stdout:
   - `[ENGINE] v2 ensemble loaded (XGBoost + LightGBM)`
   - `[ENGINE] v3 regime-aware engine loaded`
   - `[ENGINE] v4 composite scorer loaded`
   
   These are harmless and expected during test setup.

4. **No new dependencies required**: All testing infrastructure (pytest, Flask test client) was already available. No pip install needed.

## Status

✅ **COMPLETE** - All steps executed successfully, baseline maintained, honesty check passed.
