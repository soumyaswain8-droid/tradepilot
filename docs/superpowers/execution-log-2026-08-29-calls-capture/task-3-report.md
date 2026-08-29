# Task 3 Report: The Resolver

## Files created
- `scripts/resolve-calls.py`
- `tests/test_resolve_calls.py`

Both created verbatim from the brief (`task-3-brief.md`), no deviations.

## Fixture sanity check against real data (before writing anything)

Command:
```
python3 -c "import sys;sys.path.insert(0,'.');from prototype import app_store;c=app_store.get_db();[print(dict(r)) for r in c.execute('SELECT symbol,side,published_at,price_at_call,target,stop,horizon,outcome FROM calls LIMIT 3')]"
```

Full output (all 10 real rows inspected, not just 3):
```
{'symbol': 'COFORGE', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 2014.6, 'target': 2079.07, 'stop': 1988.41, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'OFSS', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 12190.0, 'target': 12580.08, 'stop': 12031.53, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'INFY', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 1144.0, 'target': 1172.6, 'stop': 1132.56, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'LODHA', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 1274.0, 'target': 1305.85, 'stop': 1261.26, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'TECHM', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 1640.9, 'target': 1681.92, 'stop': 1624.49, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'MCX', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 3332.0, 'target': 3415.3, 'stop': 3298.68, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'TCS', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 2342.0, 'target': 2416.94, 'stop': 2311.55, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'HCLTECH', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 1316.1, 'target': 1349.0, 'stop': 1302.94, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'HINDZINC', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 622.0, 'target': 637.55, 'stop': 615.78, 'horizon': 'intraday', 'outcome': 'open'}
{'symbol': 'DIVISLAB', 'side': 'BUY', 'published_at': '2026-08-29T13:33:50', 'price_at_call': 9239.0, 'target': 9469.97, 'stop': 9146.61, 'horizon': 'intraday', 'outcome': 'open'}
```

Matches the brief's promise exactly: all `side='BUY'`, all `horizon='intraday'`, real non-NULL `target`/`stop`, all `outcome='open'`, `published_at` in `2026-08-29T13:33:50` form. Fixtures in `tests/test_resolve_calls.py` were used as given in the brief (which already matches this shape) — no changes needed.

## Step 2: run tests before implementation exists (expected to fail)

Command:
```
python3 -m pytest tests/test_resolve_calls.py -q
```

Full output:
```
==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_resolve_calls.py _________________
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/runner.py:341: in from_call
    result: Optional[TResult] = func()
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/runner.py:372: in <lambda>
    call = CallInfo.from_call(lambda: list(collector.collect()), "collect")
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/python.py:531: in collect
    self._inject_setup_module_fixture()
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/python.py:545: in _inject_setup_module_fixture
    self.obj, ("setUpModule", "setup_module")
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/python.py:310: in obj
    self._obj = obj = self._getobj()
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/python.py:528: in _getobj
    return self._importtestmodule()
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/python.py:617: in _importtestmodule
    mod = import_path(self.path, mode=importmode, root=self.config.rootpath)
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/pathlib.py:565: in import_path
    importlib.import_module(module_name)
../../../../../../anaconda3/lib/python3.11/importlib/__init__.py:126: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
<frozen importlib._bootstrap>:1204: in _gcd_import
    ???
<frozen importlib._bootstrap>:1176: in _find_and_load
    ???
<frozen importlib._bootstrap>:1147: in _find_and_load_unlocked
    ???
<frozen importlib._bootstrap>:690: in _load_unlocked
    ???
../../../../../../anaconda3/lib/python3.11/site-packages/_pytest/assertion/rewrite.py:178: in exec_module
    exec(co, module.__dict__)
tests/test_resolve_calls.py:27: in <module>
    resolve_calls = _load("resolve_calls", "scripts/resolve-calls.py")
tests/test_resolve_calls.py:23: in _load
    spec.loader.exec_module(mod)
<frozen importlib._bootstrap_external>:936: in exec_module
    ???
<frozen importlib._bootstrap_external>:1073: in get_code
    ???
<frozen importlib._bootstrap_external>:1130: in get_data
    ???
E   FileNotFoundError: [Errno 2] No such file or directory: '/Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/calls-capture/scripts/resolve-calls.py'
=========================== short test summary info ============================
ERROR tests/test_resolve_calls.py - FileNotFoundError: [Errno 2] No such file...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.15s
```

Failed for the right reason: `scripts/resolve-calls.py` does not exist yet (collection error, `FileNotFoundError`).

## Baseline count (before, excluding the new test file since it can't collect)

Command:
```
python3 -m pytest tests/ -q --ignore=tests/test_resolve_calls.py
```

Output:
```
........................................................................ [ 34%]
........................................................................ [ 69%]
..............................................................           [100%]
206 passed in 3.45s
```

**Before: 206 passed.**

## Step 3: implementation

Created `scripts/resolve-calls.py` verbatim from the brief. Key points already covered in the brief's docstrings and reproduced faithfully:
- `HORIZON_DAYS = {"intraday": 1, "swing": 7, "investment": 30}`
- `is_elapsed(published_at, horizon, now)` — pure, `now` is always passed in, never read from the clock.
- `classify(side, price_at_call, outcome_price, target)` — four parameters, no `stop`. Strict target-reach rule for `hit`; falls back to price_at_call comparison (strict, not `>=`) when `target is None`.
- `due_calls(conn, now)` — selects `outcome='open'` rows and filters by `is_elapsed`.
- `apply_outcome(conn, call_id, outcome_price, outcome, now)` — writes all three outcome fields in one UPDATE, commits.
- `fetch_price(symbol)` — reads `data.get("price") or data.get("current_price")` from `TP_QUOTE_URL % symbol` (default `http://127.0.0.1:5050/api/stock/%s`).
- `main()` — wraps everything in try/except, logs `RESOLVE FAILED ...` to stderr and returns 1 on any exception; on success prints `resolved N call(s), M left open for want of a price` and returns 0. A missing price increments `skipped`, never calls `apply_outcome`, leaving the call `open`.

## Step 4: run new tests after implementation (expected 13 passed)

Command:
```
python3 -m pytest tests/test_resolve_calls.py -q
```

Output:
```
.............                                                            [100%]
13 passed in 0.05s
```

**13 passed**, as expected.

## Step 5: full suite

Command:
```
python3 -m pytest tests/ -q
```

Output:
```
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 98%]
...                                                                      [100%]
219 passed in 3.61s
```

**After: 219 passed** (206 baseline + 13 new = 219, matches exactly).

Scoped to `tests/` throughout, per instructions — a bare repo-wide run would fail collection on the pre-existing, unrelated `scripts/test_baseline_protection.py` (raises `SystemExit`), which is not part of this task and was left untouched.

## Real-rows demonstration (the most valuable check — no server needed)

Ran `due_calls(conn, now)` against the live production DB (10 real rows published today, `2026-08-29T13:33:50`, all `horizon='intraday'`) with two different clocks: the real current time, and a clock two days ahead.

Script:
```python
import sys, importlib.util, os
from datetime import datetime, timedelta
sys.path.insert(0, '.')
from prototype import app_store

spec = importlib.util.spec_from_file_location('resolve_calls', 'scripts/resolve-calls.py')
resolve_calls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(resolve_calls)

conn = app_store.get_db()
now = datetime.now().isoformat(timespec='seconds')
two_days_ahead = (datetime.now() + timedelta(days=2)).isoformat(timespec='seconds')

due_today = resolve_calls.due_calls(conn, now)
due_future = resolve_calls.due_calls(conn, two_days_ahead)

print('now =', now)
print('due_calls(conn, now) count =', len(due_today))
print('due_calls(conn, now) ids   =', [r['id'] for r in due_today])
print()
print('two_days_ahead =', two_days_ahead)
print('due_calls(conn, two_days_ahead) count =', len(due_future))
print('due_calls(conn, two_days_ahead) symbols =', [r['symbol'] for r in due_future])
conn.close()
```

Full output:
```
now = 2026-08-29T13:45:59
due_calls(conn, now) count = 0
due_calls(conn, now) ids   = []

two_days_ahead = 2026-08-31T13:45:59
due_calls(conn, two_days_ahead) count = 10
due_calls(conn, two_days_ahead) symbols = ['COFORGE', 'OFSS', 'INFY', 'LODHA', 'TECHM', 'MCX', 'TCS', 'HCLTECH', 'HINDZINC', 'DIVISLAB']
```

Confirms exactly the predicted behaviour: with today's real clock, none of the 10 open intraday calls are due (they were published earlier the same day and `intraday` requires a full day elapsed) — the resolver correctly refuses to grade them early. With a clock two days ahead, all 10 become due. No production rows were mutated (`apply_outcome` was never called in this demonstration — only `due_calls`, which is read-only).

## Commit

```
[feat/calls-capture d1cd47d] feat(calls): resolve outcomes, and only when the horizon has passed
 2 files changed, 228 insertions(+)
 create mode 100644 scripts/resolve-calls.py
 create mode 100644 tests/test_resolve_calls.py
```

SHA: `d1cd47d`

## Anything surprising

Nothing surprising. Unlike Task 2, the brief's fixtures for this task were verified against the real 10 rows in the database *before* implementing and matched exactly (all BUY, all intraday, real non-NULL target/stop, all open, correct `published_at` format) — no fixture/implementation collusion risk found. The brief's code was used verbatim per instructions and all tests passed on the first run with no fix rounds needed.

---

## Fix round 1

Coordinator review approved the implementation as correct against the brief, then raised two Important findings that are defects in the plan itself, not in this implementation of it.

### Finding 1 — horizon fallback erred toward the unsafe direction

`is_elapsed` fell back to `HORIZON_DAYS["intraday"]` (1 day, the shortest window) for any horizon string not in `HORIZON_DAYS`. Since `publish-calls.py` writes `horizon` straight from the scorer payload with no whitelist, a new horizon type added to the scorer but not mirrored into `HORIZON_DAYS` would silently grade a call meant to run 30 days after only 1 — resolving it against a price snapshot up to 29 days early, with `main()` reporting full success. That directly violates the spec's core invariant that a call inside its horizon is never counted.

**Fix**: added `_FALLBACK_DAYS = max(HORIZON_DAYS.values())` (currently 30, from `investment`) and changed `is_elapsed`'s `.get()` default from `HORIZON_DAYS["intraday"]` to `_FALLBACK_DAYS`. An unrecognised horizon now resolves late (or never, if no `now` value is ever far enough ahead) instead of early — a safe, visible failure mode (calls stuck `open`) rather than a silent one. Also added the naive-local ISO-8601 contract to `is_elapsed`'s docstring per the coordinator's note, closing a Minor finding at the same time.

**Test change**: replaced `test_unknown_horizon_falls_back_to_intraday` (which asserted the unsafe behaviour) with `test_unknown_horizon_falls_back_to_the_longest_window`, which asserts the opposite: at +2 days an unknown horizon is NOT yet elapsed (intraday would already be due at +2d, proving the fallback is not intraday), and at +31 days (past even `investment`'s 30) it IS elapsed. This is a replacement, not an addition — the brief's original test named an incorrect requirement and the spec (never count a call inside its horizon) overrides the plan.

### Finding 2 — one bad quote aborted the whole day's batch

`fetch_price` caught nothing. Any `URLError`, HTTP error, timeout, or malformed-value `float()` failure propagated out of the `for row in due_calls(...)` loop straight into `main()`'s outer `except Exception`, which stopped the run entirely — every other due call for that cycle went unattempted because of one symbol's quote failure. That's inconsistent with the already-graceful handling of a well-formed-but-missing price (`skipped += 1; continue`).

**Fix**: wrapped the per-row `fetch_price(row["symbol"])` call in its own `try/except` inside the loop. On failure it logs `  SYMBOL: price fetch failed (Type: msg)` to stderr, increments a new `failed` counter, and `continue`s to the next row — leaving that call `open` for the next cycle rather than aborting the batch. The outer `try/except` around the whole function body is unchanged and still catches genuinely fatal errors (e.g. the database being unopenable). `main()`'s summary line now reports `failed` too, and the function returns `1` if `failed` is non-zero (still loud/non-zero exit) even though the rest of the batch succeeded — `0` only when nothing failed.

**New test**: `test_one_failing_quote_does_not_abandon_the_rest` — three calls (AAA, BBB, CCC), `fetch_price` monkeypatched to raise for BBB and return a hit-worthy price for the other two, `app_store.get_db`/`init_db` monkeypatched so `main()` operates on the test's own on-disk tmp db. Since `main()` closes its connection on the way out (correct behaviour for the real CLI entry point), the test captures the original `app_store.get_db` before patching and reopens the same db file afterward to read back what `main()` actually wrote, rather than reusing the now-closed fixture connection. Confirms AAA and CCC resolved to `hit` while BBB stayed `open`, and `main()` returned `1`.

Two implementation snags surfaced while writing that test, both fixed within the test itself (no further changes to `resolve-calls.py` beyond the two findings above):
1. First attempt reused the fixture's `conn` object for post-`main()` assertions — failed with `sqlite3.ProgrammingError: Cannot operate on a closed database` because `main()` closes its connection. Fixed by reopening the same `tmp_path` db file via a fresh connection after `main()` returns.
2. Second attempt monkeypatched `resolve_calls.app_store.get_db` to call `app_store.get_db(db_path)` from inside the replacement itself — since `resolve_calls.app_store` **is** the same module object as `app_store`, this replaced the very function it was calling, causing infinite recursion (`RecursionError`). Fixed by capturing `orig_get_db = app_store.get_db` before patching, and calling that captured reference both inside the patched lambda and for the post-run verification connection.

### Verification

**1. Full suite**
```
python3 -m pytest tests/ -q
```
```
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 98%]
....                                                                     [100%]
220 passed in 3.37s
```
**220 passed** — matches the predicted 219 + 1 (the horizon test was replaced in place, not added, and one new batch-resilience test was added: 219 - 0 net test-count change from the replacement + 1 new = 220).

Isolated resolver file also checked directly:
```
python3 -m pytest tests/test_resolve_calls.py -q
```
```
..............                                                           [100%]
14 passed in 0.07s
```
(13 original minus the one replaced-in-place plus the one newly added = 14 in this file; 206 baseline + 14 = 220 overall, consistent.)

**2. Known horizons unaffected — still elapse at 1 / 7 / 30 days**
```python
pub = '2026-08-28T09:20:00'
resolve_calls.is_elapsed(pub, 'intraday',   '2026-08-29T09:20:00')  # +1d
resolve_calls.is_elapsed(pub, 'intraday',   '2026-08-29T09:19:00')  # +1d -1min
resolve_calls.is_elapsed(pub, 'swing',      '2026-09-04T09:20:00')  # +7d
resolve_calls.is_elapsed(pub, 'swing',      '2026-09-04T09:19:00')  # +7d -1min
resolve_calls.is_elapsed(pub, 'investment', '2026-09-27T09:20:00')  # +30d
resolve_calls.is_elapsed(pub, 'investment', '2026-09-27T09:19:00')  # +30d -1min
```
```
intraday @+1d  : True
intraday @-1min: False
swing    @+7d  : True
swing    @-1min: False
investment @+30d : True
investment @-1min: False
```
All three known horizons still elapse exactly at their documented boundary, boundary-inclusive, unaffected by the fallback change.

**3. Real-rows demonstration, re-run and confirmed unchanged**

All 10 real production rows carry `horizon='intraday'`, a KNOWN horizon, so the fallback change (which only affects unrecognised horizons) does not touch them.
```
now = 2026-08-29T13:53:31
due_calls(conn, now) count = 0
due_calls(conn, now) ids   = []

two_days_ahead = 2026-08-31T13:53:31
due_calls(conn, two_days_ahead) count = 10
due_calls(conn, two_days_ahead) symbols = ['COFORGE', 'OFSS', 'INFY', 'LODHA', 'TECHM', 'MCX', 'TCS', 'HCLTECH', 'HINDZINC', 'DIVISLAB']
```
Identical result to the pre-fix run: 0 due today, all 10 due two days ahead.

### Commit

```
git commit -m "fix(calls): unknown horizon errs long, one bad quote doesn't abort the batch"
```

Scope: `scripts/resolve-calls.py` and `tests/test_resolve_calls.py` only. `app_store.py`, `publish-calls.py`, and `classify` were not touched, per instruction. Nothing under `.superpowers/` was staged.
