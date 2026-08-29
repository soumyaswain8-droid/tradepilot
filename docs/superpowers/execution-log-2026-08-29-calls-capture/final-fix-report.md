# Final fix wave — calls-capture pipeline

Branch: `feat/calls-capture`
Applied from: `/Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/calls-capture`

All five review items applied in one pass, plus deletion of the 10 dev rows
seeded into the real database.

## FIX 1 (CRITICAL) — publish job only understood v4's payload spelling

`scripts/publish-calls.py`, `build_rows()`: now reads `stopLoss`/`target` (v4)
first, falling back to `stop_loss_pct`/`target_pct` (v2/v1) when the v4 keys
are absent. Verified against the actual engine source:

```
prototype/v4/composite_scorer.py:413-414   "stopLoss": sl,          "target": target
prototype/trading_engine.py:441            "stop_loss_pct": sl_pct, "target_pct": target_pct
prototype/ai_scorer.py:262-263             "stop_loss_pct": sl_pct, "target_pct": target_pct
```

Tests added (`tests/test_publish_calls.py`):
- `test_v2_shaped_pick_produces_the_same_levels_via_pct_suffixed_keys`
- `test_both_spellings_present_prefers_the_v4_names`

## FIX 2 (CRITICAL) — eliminated the second, unlabelled grading rule

`scripts/resolve-calls.py`:
- `classify()` no longer has a no-target fallback. It now requires `target`
  and raises `ValueError` if it is `None`.
- `main()` marks a due call with `target IS NULL` as outcome `ungraded`
  (recording `outcome_price`), incrementing a new `ungraded` counter, and
  never calls `classify()` for it.
- Module docstring rewritten to describe the actual contract (target
  required; no-target calls are `ungraded` and excluded).

`scripts/calls-status.py`, `summarise()`:
- New `ungraded` key (count of `outcome = 'ungraded'` rows), excluded from
  `resolved` (`resolved` stays `hit + miss`, unchanged) and from `hit_rate`.
- `main()` prints `ungraded          N  (published without a target -- not
  counted)` when `s["ungraded"] > 0`.

Tests replaced (`tests/test_resolve_calls.py`):
- `test_call_with_no_target_grades_against_the_call_price` and
  `test_flat_is_never_a_hit_when_there_was_no_target` removed (asserted the
  old fallback contract).
- Added `test_classify_raises_when_target_is_none` and
  `test_due_call_with_no_target_is_marked_ungraded` (asserts `main()` writes
  `outcome='ungraded'`, `outcome_price` set, via a reopened on-disk db since
  `main()` closes its own connection).

Test added (`tests/test_calls_status.py`):
- `test_summarise_excludes_ungraded_rows_from_hit_rate` — 1 hit, 1 miss, 1
  ungraded → `hit_rate == 50.0`, `resolved == 2`, `ungraded == 1`.

## FIX 3 (Important) — a failed picks call no longer reports success

`scripts/publish-calls.py`, `fetch_picks()`: after parsing the JSON body, if
`payload.get("error")` is truthy, raises `RuntimeError`. This is checked
regardless of HTTP status, because `app.py:2839-2840` returns **HTTP 200**
with `{"picks": [], "error": str(e)}` on scoring failure — a 200 alone never
meant success.

An honest empty-picks day (no `error` key) is unaffected — still returns the
payload and `build_rows`/`insert_rows` insert nothing without raising.

Tests added:
- `test_fetch_picks_raises_when_payload_carries_an_error_key`
- `test_fetch_picks_does_not_raise_on_an_honest_empty_picks_list`

## FIX 4 (Important) — calls-status now alerts on a broken resolver

`scripts/calls-status.py`:
- Added local `HORIZON_DAYS = {"intraday": 1, "swing": 7, "investment": 30}`
  and `_FALLBACK_DAYS = max(HORIZON_DAYS.values())`, mirroring
  `resolve-calls.py`'s table (defined locally rather than imported from the
  hyphenated filename, per instruction).
- `summarise()` now selects `horizon` and computes a new `overdue` key: count
  of `outcome = 'open'` rows whose horizon has elapsed as of `now`, using the
  same elapsed-check arithmetic as the resolver.
- `main()` prints `OVERDUE           N call(s) past their horizon still open
  -- is the resolver running?` and returns 1 when `overdue > 0`, independent
  of the missing-weekday check (`rc` is set to 1 by either condition without
  short-circuiting the other).

Tests added:
- `test_main_flags_overdue_open_call_and_exits_nonzero`
- `test_main_does_not_flag_open_call_still_inside_its_horizon`

Also demonstrated live against a **throwaway** database (see Verification
below, not the real db).

## FIX 5 (Important) — docs/docstring now describe the method honestly

Method unchanged (still a single spot-price comparison at resolution time,
not an intraday high/low check) — only the wording changed, in two places:

- `scripts/resolve-calls.py` module docstring: states the hit rule is decided
  by the price *at resolution time*, and that a call which touched the target
  intraday and gave it back grades a miss. Adds the sentence that this is
  deliberately conservative — it can understate the hit rate but never
  overstate it.
- `docs/CALLS_PIPELINE.md`, "Rules that must not be relaxed": same wording,
  plus a line documenting that a no-target call is `ungraded` and excluded
  rather than graded softly (FIX 2). The jobs table and "Checking it is
  alive" section also now mention the overdue alert (FIX 4).

## Dev rows deleted from the real database

The 10 rows captured Saturday 2026-08-29 at 13:33 (market shut, stale Friday
close as `price_at_call`) were deleted from the real db — see Verification
step 2 below for the before/after count and the command used.

No trading-day guard was added to the publish job (see "What was NOT
changed" below).

---

## Verification

### 1. Full test suite

```
$ python3 -m pytest tests/ -q
........................................................................ [ 30%]
........................................................................ [ 61%]
........................................................................ [ 92%]
..................                                                       [100%]
234 passed in 3.57s
```

234 = 227 baseline + 7 net new (4 in test_publish_calls.py, 3 in
test_calls_status.py; test_resolve_calls.py replaced 2 old tests with 2 new
ones, net 0). Re-ran once more after the DB deletion step, same result:

```
$ python3 -m pytest tests/ -q
........................................................................ [ 30%]
........................................................................ [ 61%]
........................................................................ [ 92%]
..................                                                       [100%]
234 passed in 3.12s
```

### 2. Real database emptied

```
$ python3 -c "import sys;sys.path.insert(0,'.');from prototype import app_store;c=app_store.get_db();print('before:', list(c.execute('SELECT COUNT(*) FROM calls'))[0][0])"
before: 10

$ python3 -c "import sys;sys.path.insert(0,'.');from prototype import app_store;c=app_store.get_db();c.execute('DELETE FROM calls');c.commit();print('remaining:', list(c.execute('SELECT COUNT(*) FROM calls'))[0][0])"
remaining: 0
```

Confirmed `calls-status.py` now takes the "never run" branch against the
real (now empty) database:

```
$ python3 scripts/calls-status.py; echo "EXIT CODE: $?"
NO CALLS EVER RECORDED -- the publish job has not run successfully even once.
Check that prototype/app.py is running, then run scripts/publish-calls.py by hand.
EXIT CODE: 1
```

This is correct — there are genuinely no calls in the record right now.

### 3. FIX 4 demonstrated against a THROWAWAY database

Used `/tmp/tp-fix4-demo/throwaway.db`, not the real one. Captured the
original `app_store.get_db` under `orig_get_db` before monkeypatching (a
lambda that called `app_store.get_db` directly would have recursed
infinitely, per the task's own warning).

Script (`/tmp/tp-fix4-demo/demo.py`):

```python
import sys, os
sys.path.insert(0, "<repo>")
import importlib.util
from datetime import datetime, timedelta
from prototype import app_store

spec = importlib.util.spec_from_file_location("calls_status", "<repo>/scripts/calls-status.py")
calls_status = importlib.util.module_from_spec(spec)
spec.loader.exec_module(calls_status)

db_path = "/tmp/tp-fix4-demo/throwaway.db"
if os.path.exists(db_path):
    os.remove(db_path)

conn = app_store.get_db(db_path)
app_store.init_db(conn)

published = (datetime.now() - timedelta(days=3)).isoformat(timespec="seconds")
conn.execute(
    "INSERT INTO calls (id, symbol, side, published_at, price_at_call, horizon, outcome)"
    " VALUES (?,?,?,?,?,?,?)",
    ("demo1", "DEMO", "BUY", published, 1000.0, "intraday", "open"))
conn.commit()

orig_get_db = app_store.get_db
calls_status.app_store.get_db = lambda path=None: orig_get_db(db_path)
calls_status.app_store.init_db = lambda c: None

rc = calls_status.main()
print("RETURN CODE:", rc)
```

Output:

```
calls recorded    1  (1 open, 0 resolved)
hit rate          -- (nothing resolved yet)
covering          2026-08-26 to 2026-08-26  (1 day with calls)
MISSING DAYS      2: 2026-08-27, 2026-08-28
OVERDUE           1 call(s) past their horizon still open -- is the resolver running?
RETURN CODE: 1
```

Confirms: an open `intraday` call published 3 days ago is flagged overdue,
the alert message prints, and `main()` returns 1. (The unrelated
`MISSING DAYS` line is expected — only one call exists in this throwaway db,
so the days between it and today read as gaps too; the task only required
demonstrating the overdue path, which the `OVERDUE` line and `rc == 1`
confirm.)

---

## What was NOT changed (explicit)

- **No trading-day / market-holiday guard added to `publish-calls.py`.** The
  dev rows were deleted from the real db, but the underlying gap — the
  publish job will happily write rows on a day the market is shut, using a
  stale last-close price — is still there. Needs a market-holiday calendar
  and is a decision for the user, not this fix wave.
- **No market-holiday handling anywhere else** (e.g. in `calls-status.py`'s
  gap detection, which already excludes weekends but not market holidays).
- **The quote-source mismatch is unchanged.** `resolve-calls.py` still reads
  a live quote via `TP_QUOTE_URL` (`/api/stock/%s`) as `outcome_price`, which
  is a different data path from `price_at_call` in `publish-calls.py`
  (`/api/picks`). No reconciliation between the two was added.
- **The grading method itself (FIX 5) was not changed** — only the wording.
  It is still a single spot-price sample at resolution time, not an intraday
  high/low check. That would need intraday high/low data and is a larger
  change than this wave.
- `prototype/app.py`, `prototype/app_store.py`, and the launchd plists were
  not touched, per instruction.
