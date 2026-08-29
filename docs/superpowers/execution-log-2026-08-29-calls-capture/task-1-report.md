# Task 1 Report: The Store and Its Schema

## Files Created

- `prototype/app_store.py` — SQLite store module with DB_PATH, get_db(), init_db()
- `tests/test_app_store.py` — 7 schema and idempotency tests

## Steps Followed

### Step 1: Write the failing tests ✓
Created `tests/test_app_store.py` with exact code from brief.

### Step 2: Run to verify they fail ✓
```bash
$ python3 -m pytest tests/test_app_store.py -q
==================================== ERRORS ====================================
___________________ ERROR collecting tests/test_app_store.py ___________________
ImportError while importing test module '...tests/test_app_store.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
../../../../../../anaconda3/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level=0], level)
tests/test_app_store.py:17: in <module>
    from prototype import app_store
E   ImportError: cannot import name 'app_store' from 'prototype'
=========================== short test summary info ============================
1 error in 0.06s
```

Expected: collection error — `ImportError: cannot import name 'app_store'`. ✓

### Step 3: Write the store ✓
Created `prototype/app_store.py` with exact code from brief:
- DB_PATH pointing to `prototype/tradepilot_app.db` (separate from analytics DB)
- get_db(path=None) with WAL, busy_timeout=5000, row_factory=sqlite3.Row, foreign_keys=ON
- init_db(conn) creating both tables (calls, positions) and indexes
- Unique index `ux_calls_symbol_day` on (symbol, date(published_at))
- Foreign key constraint on positions.call_id referencing calls.id

### Step 4: Run to verify they pass ✓
```bash
$ python3 -m pytest tests/test_app_store.py -q
.......                                                                  [100%]
7 passed in 0.03s
```

All 7 tests pass. ✓

### Step 5: Confirm the whole suite still passes ✓
```bash
$ python3 -m pytest tests/ -q
........................................................................ [ 37%]
........................................................................ [ 75%]
...............................................                          [100%]
191 passed in 3.72s
```

Before: 184 passing
After: 191 passing (184 existing + 7 new) ✓

### Step 6: Commit ✓
```bash
$ git add prototype/app_store.py tests/test_app_store.py
$ git commit -m "feat(store): the calls and positions store
...
[feat/calls-capture b25c764] feat(store): the calls and positions store
 2 files changed, 163 insertions(+)
 create mode 100644 prototype/app_store.py
 create mode 100644 tests/test_app_store.py
```

Commit SHA: `b25c764`

## Test Results

| Metric | Value |
|--------|-------|
| Tests before implementation | 184 passing |
| New tests written | 7 |
| Tests after implementation | 191 passing |
| Failures encountered | 0 |

## Tests Overview

The 7 new tests verify:
1. **test_both_tables_exist** — calls and positions tables created
2. **test_init_db_is_idempotent** — schema safe to run on every boot
3. **test_foreign_keys_are_enforced** — PRAGMA foreign_keys=ON is set, constraint violation on foreign key insert
4. **test_duplicate_call_same_symbol_same_day_is_rejected** — unique index prevents duplicate calls same symbol/day
5. **test_same_symbol_next_day_is_allowed** — same symbol on different days are separate calls
6. **test_outcome_defaults_to_open** — outcome column defaults to 'open'
7. **test_real_db_path_is_not_the_analytics_db** — DB_PATH points to tradepilot_app.db, not analytics file

## Key Design Points

- **Separate database file**: `prototype/tradepilot_app.db` intentionally separate from `tradepilot_analytics.db`. Analytics is disposable/rebuildable; calls is the product record.
- **Idempotency via constraint**: Unique index on (symbol, date(published_at)) enforces idempotency at the database level, not just a publishing job convention.
- **Connection pragmas**: WAL for concurrent readers, busy_timeout=5000 to prevent instant failure under write contention, row_factory=sqlite3.Row for mapping access, foreign_keys=ON for referential integrity.
- **Schema structure**: calls table with columns for all signal properties (signal, horizon, target, stop, score) + outcome tracking. positions table with user context and call reference.

## No Concerns

All steps executed as specified. Tests pass. Commit clean. Ready for Task 2.
