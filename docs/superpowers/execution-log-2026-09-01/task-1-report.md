# Task 1 Report: Users Table and Password Checking

## Summary

**Status:** DONE

**Commit SHA:** d5e8273

**Test Count:** 12 passed

**Step 6 Observation:** 
- RED: `FAILED tests/test_accounts.py::test_an_unknown_email_returns_none_exactly_like_a_wrong_password` with `ValueError: no such user` raised when row is None
- GREEN: `12 passed in 2.72s` after restoring `if row is None: return None`

## What Was Built

1. **Schema Extension**: Added `users` table to `prototype/app_store.py` with columns for id, email, password_hash, created_at, disabled_at, failed_count, and locked_until. Added unique index on lower(email) for case-insensitive lookups.

2. **accounts.py Module**: Created new module with no Flask dependencies, providing:
   - `create_user(conn, email, password)`: Generates user ID with `u-{token_hex}` format, hashes password via werkzeug's default method, raises ValueError on duplicate email
   - `check_login(conn, email, password)`: Returns user ID on success, None on all failures (unknown email, wrong password, disabled, locked)
   - `LOCKOUT_THRESHOLD = 10`, `LOCKOUT_MINUTES = 15`

3. **Test Suite**: 12 comprehensive tests covering happy path, edge cases, case-insensitivity, password validation, account lockout, and enumeration protection.

## Key Observations

- Step 6 correctly identified that the enumeration test binds: breaking the code made the test fail RED, restoring made it GREEN. The test properly validates that login failure returns identical responses for both unknown emails and wrong passwords, preventing account enumeration.
- Werkzeug's default password hashing algorithm works as expected with `generate_password_hash` and `check_password_hash`.
- SQLite's Row factory correctly allows both `row["column"]` and `row[0]` access patterns.
- Lock expiration uses simple timestamp comparison with UTC timezone.

## Nothing Suspicious

All global constraints met:
- No new dependencies (werkzeug already in requirements.txt)
- All DDL uses `IF NOT EXISTS`
- Passwords use werkzeug's default hashing method
- Login failures indistinguishable to caller
- No build commands executed (pytest only)
- No subagents dispatched

---

## Fix Round 1: Lock Expiration Bug

**Brief Defect:** `check_login` never cleared `failed_count` when a lock expired, allowing attackers to maintain a hold on accounts with one request every 15 minutes, and leaving legitimate users a single-attempt window.

**Root Cause:** After checking if a lock is still in force, the code fell through to password validation without resetting the failure counter when the lock had expired. The stale `failed_count` from the database query would be used on the next wrong password attempt, re-triggering the lockout immediately.

**Test Evidence:**
- RED: `FAILED tests/test_accounts.py::test_an_expired_lock_restores_the_full_attempt_budget` with `AssertionError: assert None` (correct password refused after lock expiry + one failure attempt)
- GREEN: `tests/test_accounts.py::test_an_expired_lock_restores_the_full_attempt_budget PASSED` (test passes after fix)

**Fix Applied:** 
Added check after lock-still-in-force early return: if the lock EXISTS and has expired, clear both `failed_count` and `locked_until`, then re-fetch the row to use updated values for subsequent password validation. This preserves the early-return ordering and ensures expired locks grant full attempt budgets.

**Verification:**
- `test_a_lock_expires` still PASSED (existing lock expiration path unaffected)
- Full suite: `325 passed in 11.89s` (new test added to the 12 original account tests, plus 312 other pre-existing tests in the suite)

**Commit:** Updated `prototype/accounts.py` with lock-expiration reset logic.
