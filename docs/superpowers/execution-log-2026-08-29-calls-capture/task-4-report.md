# Task 4 Report: Scheduling and visibility

## Ruling applied (overrides brief Step 6)

Did NOT write plists into `~/Library/LaunchAgents/` and did NOT run `launchctl load`.
Instead: both plists checked in as tracked templates under `deploy/launchd/`, with the
literal `/Users/YOURNAME` placeholder preserved (not substituted). `docs/CALLS_PIPELINE.md`
carries an "Installing the schedule" section with the `sed` + `cp`/redirect + `launchctl load`
commands for the user to run themselves, plus a note that both jobs need `prototype/app.py`
running since they read HTTP endpoints, not the DB or engine directly.

## Files created

- `scripts/calls-status.py` (executable, `chmod +x`)
- `tests/test_calls_status.py`
- `docs/CALLS_PIPELINE.md`
- `deploy/launchd/co.tradepilot.publish-calls.plist`
- `deploy/launchd/co.tradepilot.resolve-calls.plist`

No file outside the worktree was touched. Nothing was written to
`~/Library/LaunchAgents/` and `launchctl` was never invoked.

## Step 2: run tests before the implementation exists

```
$ python3 -m pytest tests/test_calls_status.py -q
```

```
==================================== ERRORS ====================================
_________________ ERROR collecting tests/test_calls_status.py __________________
...
E   FileNotFoundError: [Errno 2] No such file or directory: '/Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/calls-capture/scripts/calls-status.py'
=========================== short test summary info ============================
ERROR tests/test_calls_status.py - FileNotFoundError: [Errno 2] No such file ...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.13s
```

Failed for the right reason: collection error because `scripts/calls-status.py` did not
exist yet. Exit code 2.

## Step 4: run tests after the implementation exists

```
$ python3 -m pytest tests/test_calls_status.py -q
```

```
.....                                                                    [100%]
5 passed in 0.03s
```

## Full suite, before and after

Baseline (test_calls_status.py and calls-status.py temporarily moved out):

```
$ python3 -m pytest tests/ -q
........................................................................ [ 32%]
........................................................................ [ 65%]
........................................................................ [ 98%]
....                                                                     [100%]
220 passed in 3.09s
```

After (files restored):

```
$ python3 -m pytest tests/ -q
........................................................................ [ 32%]
........................................................................ [ 64%]
........................................................................ [ 96%]
.........                                                                [100%]
225 passed in 3.12s
```

220 before, 225 after (+5 new tests). Matches the corrected total noted in the task prompt
(219 in the plan's original arithmetic predates Tasks 2/3's fix-round test additions; 225 is
correct here).

## Real database: `python3 scripts/calls-status.py`

```
calls recorded    10  (10 open, 0 resolved)
hit rate          -- (nothing resolved yet)
covering          2026-08-29 to 2026-08-29  (1 trading days)
gaps              none
EXIT CODE: 0
```

Ten calls, all `open`, all published on a single day (`2026-08-29`), matching the "real
data already in the database" the brief described.

### Surprising: the one recorded day is a Saturday

`2026-08-29` is a **Saturday** (`datetime(2026,8,29).weekday() == 5`). The gap-detection
loop iterates the closed interval `[first_call, now]`; here `first_call == now == 2026-08-29`,
so the loop visits exactly one calendar day, and that day's `weekday() >= 5` excludes it from
gap consideration before it would ever be checked against `have`. Result: `gaps == []` and
exit code `0`, reported as clean, even though the underlying calls table holds data published
outside the trading week — i.e. this is dev/test data injected out-of-band, not output of the
09:20-weekday publish job actually firing. The status script's gap logic only verifies that
weekdays *within the observed range* are covered; it does not (and per the brief's spec,
was not asked to) flag that the range itself contains no weekday activity at all. Flagging
this plainly rather than glossing it, per instructions — this is not a bug in the
implementation (it matches the brief's spec and tests verbatim, including the weekend test
case `test_weekends_are_not_gaps`), but it means a clean `calls-status.py` exit on this
database should not be read as confirmation the *scheduled* job has ever run.

## Commit

```
$ git log --oneline -3
0d37551 feat(calls): make the pipeline observable, and schedule it
257f73e fix(calls): unknown horizon errs long, one bad quote doesn't abort the batch
d1cd47d feat(calls): resolve outcomes, and only when the horizon has passed
```

Commit SHA: `0d37551`

```
$ git commit -m "..."
[feat/calls-capture 0d37551] feat(calls): make the pipeline observable, and schedule it
 5 files changed, 267 insertions(+)
 create mode 100644 deploy/launchd/co.tradepilot.publish-calls.plist
 create mode 100644 deploy/launchd/co.tradepilot.resolve-calls.plist
 create mode 100644 docs/CALLS_PIPELINE.md
 create mode 100755 scripts/calls-status.py
 create mode 100644 tests/test_calls_status.py
```

## Verification: no side effects on the host machine

```
$ ls ~/Library/LaunchAgents/ | grep -i tradepilot
```
Lists only pre-existing `com.tradepilot.*` / `com.soumya.tradepilot-launch*` agents (all
predate this task — different label prefix, `com.` not `co.`). No `co.tradepilot.publish-calls`
or `co.tradepilot.resolve-calls` entry exists.

```
$ launchctl list | grep -i tradepilot
```
Same — only pre-existing agents. No entry for either new label. `launchctl` was never
invoked by this task.

## Plist validation

```
$ plutil -lint deploy/launchd/co.tradepilot.publish-calls.plist deploy/launchd/co.tradepilot.resolve-calls.plist
deploy/launchd/co.tradepilot.publish-calls.plist: OK
deploy/launchd/co.tradepilot.resolve-calls.plist: OK
```

Both plists use the exact XML from the brief (09:20 weekdays for publish, 18:30 weekdays for
resolve, `StandardOutPath`/`StandardErrorPath` to `/tmp/`), written out in full rather than
derived from one another, with the literal `/Users/YOURNAME` placeholder left unsubstituted
in `ProgramArguments`.

## Other notes

- Did not attempt the plan's "run `publish-calls.py` twice, expect N then 0" checklist item —
  out of scope for this task (that's exercising Task 2's script against the live server) and
  would have required starting `prototype/app.py`, which risked interfering with the user's
  running port 5050. Not run.
- `docs/CALLS_PIPELINE.md` body matches the brief verbatim except Step 6/scheduling section,
  which was replaced per the ruling.

---

## Fix round 1

The Saturday anomaly surfaced in the original report turned out to point at a real defect
in the brief's reference implementation, not just an interesting data quirk. Five findings
addressed, all confined to `scripts/calls-status.py`, `tests/test_calls_status.py`, and
`docs/CALLS_PIPELINE.md`. `app_store.py`, `publish-calls.py`, `resolve-calls.py`, the two
plists, and `summarise()`'s return keys were not touched.

### Finding 1 (critical) — empty database was invisible, permanently

`main()` now checks `s["total"] == 0` before the gap report and, if true, prints
`NO CALLS EVER RECORDED -- the publish job has not run successfully even once.` plus a
remediation hint, and returns 1. A pipeline that ran and then died self-corrects (the next
weekday shows up as a gap); a pipeline that never ran has no `first_call` to anchor the gap
loop, so without this branch it reported `gaps none` / exit 0 forever — identical to a year
of flawless running.

### Finding 2 (important) — `(N trading days)` mislabelled what was counted

`days_covered` counts distinct days with rows, not weekdays. Fixed the label, not the number,
per the finding's instruction (other code may read `days_covered`): the covering line now
reads `(%d day%s with calls)`, singular/plural correctly, with no "trading" claim.

### Finding 3 (important) — no test exercised `main()` or its exit code

Added `test_main_on_empty_store_is_loud_and_exits_nonzero` and
`test_main_with_a_missing_weekday_exits_nonzero`, both using `monkeypatch` on
`calls_status.app_store.get_db` / `init_db` and asserting `capsys` output plus the literal
return code from `calls_status.main()`. (Wired exactly as specified in the finding.)

### Finding 4 (important) — documentation overclaimed what a clean exit proves

Added a "What a clean exit does and does not mean" subsection under "Checking it is alive" in
`docs/CALLS_PIPELINE.md`, covering both the new empty-database behaviour and the
weekend-only-window caveat (naming the Saturday 2026-08-29 case explicitly).

### Finding 5 (minor) — missing docstrings

Added a one-line docstring to `main()` and to the three test functions that lacked one
(`test_empty_store_reports_zero_not_an_error`, `test_hit_rate_counts_only_resolved_calls`,
`test_weekends_are_not_gaps`).

### Verification

Full suite:

```
$ python3 -m pytest tests/ -q
........................................................................ [ 31%]
........................................................................ [ 63%]
........................................................................ [ 95%]
...........                                                              [100%]
227 passed in 3.32s
```

225 before this round, 227 after (+2 new `main()` tests), matching the expected count.

Real database (unchanged, still 10 open calls from 2026-08-29):

```
$ python3 scripts/calls-status.py
calls recorded    10  (10 open, 0 resolved)
hit rate          -- (nothing resolved yet)
covering          2026-08-29 to 2026-08-29  (1 day with calls)
gaps              none
EXIT CODE: 0
```

Confirms the real DB (10 rows) does NOT take the new empty branch, and shows the corrected
"day with calls" wording (singular, no "trading" overclaim) in place of the old
"1 trading days".

Empty branch, demonstrated against a throwaway `/tmp` database (never touched the real DB):

```
$ python3 -c "... calls_status.app_store.get_db = lambda path=None: _orig_get_db('/tmp/calls-status-empty-demo.db'); calls_status.main() ..."
NO CALLS EVER RECORDED -- the publish job has not run successfully even once.
Check that prototype/app.py is running, then run scripts/publish-calls.py by hand.
EXIT CODE: 1
```

(First attempt at this monkeypatch caused `RecursionError`: rebinding `calls_status.app_store.get_db`
mutates the shared `prototype.app_store` module object in-place, since `calls_status` and the demo
script both hold the same module object via `from prototype import app_store`. Fixed by capturing
the original `app_store.get_db` under a different name before rebinding, rather than having the
lambda call through the name it just replaced. The throwaway `/tmp` files were removed after the
demo ran.)

### Commit

```
$ git log --oneline -1
4bd948c
```
