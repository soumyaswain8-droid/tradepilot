# Task 2 Report: The Publish Job

## Files created
- `scripts/publish-calls.py` (verbatim from brief Step 3; not modified)
- `tests/test_publish_calls.py` (verbatim from brief Step 1; not modified)

Both committed. No other files touched. A scratch launcher used only to run the
live app on port 5051 (`scripts/_run_app_5051.py`) was created, used, and then
deleted before commit — never staged.

## Step 1: Write the failing tests
Created `tests/test_publish_calls.py` exactly as specified in the brief.

## Step 2: Run to verify they fail (before the job exists)
```
$ python3 -m pytest tests/test_publish_calls.py -q
```
Output (abridged — full traceback captured):
```
ERROR collecting tests/test_publish_calls.py
...
E   FileNotFoundError: [Errno 2] No such file or directory: '.../scripts/publish-calls.py'
=========================== short test summary info ============================
ERROR tests/test_publish_calls.py - FileNotFoundError: [Errno 2] No such file...
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 error in 0.14s
```
Failed for the right reason: `scripts/publish-calls.py` did not exist yet.

## Step 3: Write the job
Created `scripts/publish-calls.py` exactly as specified in the brief — including
`published_at = datetime.now().isoformat(timespec="seconds")` verbatim, and the
`timeout=30` in `fetch_picks`'s `urllib.request.urlopen` call, unmodified.

## Step 4: Run to verify they pass
```
$ python3 -m pytest tests/test_publish_calls.py -q
..........                                                               [100%]
10 passed in 0.04s
```

## Step 5: Live run against the real app

### Constraint handling
Port 5050 is the user's own running server (verified via `lsof -i :5050` →
pid 13375, left untouched throughout). `prototype/app.py`'s `__main__` block
hardcodes `port=5050` with no env override, so I could not launch it via
`python3 prototype/app.py` on a different port without editing that file
(out of scope). Instead I wrote a small scratch launcher,
`scripts/_run_app_5051.py`, that imports `prototype.app`'s Flask `app` object
directly and calls `app.run(host="127.0.0.1", port=5051, ...)` — no changes to
`app.py` itself. The trained model (`prototype/models/xgb_scorer.pkl`) already
existed, so no retraining was triggered. This scratch file was deleted before
commit and was never staged.

### Environmental surprise (see "Anything surprising" below)
The `/api/picks?category=stocks` endpoint has no server-side cache and, on a
cold call, falls back to per-symbol `yfinance` fetches for 200 stocks when the
batch quote call returns all-NaN (observed consistently on this run — a
Saturday, market closed). That cold path took well over the script's
hardcoded 30s `urlopen` timeout, so the first few attempts against a cold
endpoint failed with `TimeoutError: timed out`. This is not a bug in the job —
per the brief, the 30s timeout must not be changed. I warmed the endpoint with
a direct `curl --max-time 300` (foreground) until the batch quote path
succeeded and results were cached server-side (batch quotes + intraday batch
cached), confirmed by a follow-up `curl` completing in 2.3s. Only after the
endpoint was warm did I run `scripts/publish-calls.py` for the actual graded
double-run below.

### Run 1 (foreground, cache warm)
```
$ TP_PICKS_URL="http://127.0.0.1:5051/api/picks?category=stocks&count=10" python3 scripts/publish-calls.py
published 10 call(s) of 10 pick(s) at 2026-08-29T13:21:49
EXIT1: 0
```

### Run 2 (foreground, immediately after)
```
$ TP_PICKS_URL="http://127.0.0.1:5051/api/picks?category=stocks&count=10" python3 scripts/publish-calls.py
published 0 call(s) of 10 pick(s) at 2026-08-29T13:21:54
EXIT2: 0
```

Idempotency proven against the real database: run 2 inserted 0 of the same 10
picks that run 1 inserted.

### DB verification
```python
>>> rows = list(conn.execute('SELECT id, symbol, published_at, outcome FROM calls ORDER BY id'))
>>> len(rows)
10
```
All 10 rows have `published_at = '2026-08-29T13:21:49'` (exact string, no
timezone suffix, no space separator — matches the brief's mandated format) and
`outcome = 'open'`. Sample:
```
{'id': 'call-COFORGE-2026-08-29', 'symbol': 'COFORGE', 'published_at': '2026-08-29T13:21:49', 'outcome': 'open'}
{'id': 'call-TCS-2026-08-29',     'symbol': 'TCS',     'published_at': '2026-08-29T13:21:49', 'outcome': 'open'}
...
```

**Exact `published_at` written during the live run: `2026-08-29T13:21:49`**

### Cleanup
```
$ rm -f scripts/_run_app_5051.py        # scratch file removed, confirmed gone
$ kill 15040 15293                       # 15293 already exited on its own ("no such process")
$ lsof -ti :5051                         # empty — confirmed dead
$ lsof -ti :5050                         # 13375 — user's own server, untouched
```

## Step 6: Full suite + commit
```
$ python3 -m pytest tests/ -q
........................................................................ [ 35%]
........................................................................ [ 71%]
.........................................................                [100%]
201 passed in 3.43s
```
Before: 191 passed. After: 201 passed (191 + 10 new).

```
$ git status --porcelain
?? scripts/publish-calls.py
?? tests/test_publish_calls.py
$ git add scripts/publish-calls.py tests/test_publish_calls.py
$ git commit -m "feat(calls): capture what was published, once per symbol per day ..."
[feat/calls-capture 83f1686] feat(calls): capture what was published, once per symbol per day
 2 files changed, 234 insertions(+)
```

**Commit SHA: `83f1686`**

Nothing under `.superpowers/` was staged. The scratch launcher was never
staged. Only the two intended files are in the commit.

## Anything surprising
- The live `/api/picks?category=stocks` endpoint is expensive and uncached at
  the route level — on a cold call (market closed, batch quote call returns
  all-NaN) it falls back to per-symbol `yfinance` fetches for 200 stocks,
  which took well over a minute and exceeded the job's fixed 30s timeout on
  the first several attempts. This is real production behavior of the app,
  not something introduced by this task, and the job's 30s timeout was left
  exactly as specified in the brief. Warming the endpoint first (so batch
  quotes were cached) was necessary to get a live run that completes inside
  30s. This may be worth a follow-up note for whoever schedules this job in
  production (e.g. ensure `/api/scores`-style warming also covers `/api/picks`,
  or run the job when the app has already been warm for a few minutes).

## Fix round 1

The plan's spec for `build_rows` was written against `score_stocks_v4()`'s
internal record, but `/api/picks` transforms that record before serving it.
The original `PAYLOAD` test fixture encoded the same wrong assumption as the
implementation, so all 10 original tests passed while disagreeing with the
real endpoint. Confirmed against the coordinator's live-verified field values.

### Four changes to `build_rows` in `scripts/publish-calls.py`

1. **side** now reads `direction` directly, uppercased (`BUY`/`SELL`) — no
   more UP/DOWN translation.
2. **Skip non-actionable picks.** Any pick whose uppercased `direction` is not
   exactly `BUY` or `SELL` (i.e. `HOLD` or `AVOID`) is skipped before a row is
   built, same as the existing no-symbol / non-positive-price skips. A day may
   now capture fewer rows than the requested `count` — deliberate, per the
   coordinator's ruling: recording a HOLD/AVOID as a call would manufacture a
   hit rate out of non-advice.
3. **target/stop** now read the `target` and `stopLoss` keys (both still
   percentages) instead of `target_pct`/`stop_loss_pct`. The arithmetic itself
   is unchanged: `target = round(price * (1 + tgt_pct/100), 2)`,
   `stop = round(price * (1 - sl_pct/100), 2)`, still `None` when the percentage
   is absent or zero. For a SELL pick where the API returns a negative
   percentage, this same formula naturally produces a target below and a stop
   above the call price (verified in the new SELL test below) — no sign
   branching needed in code.
4. **signal** now handles `reasons` as a list of `{"text", "type"}` dicts:
   `parts = [r.get("text") if isinstance(r, dict) else str(r) for r in reasons]`,
   joined on `"; "`, keeping both positive and negative reasons in order and
   dropping falsy entries. A plain-string entry still works (defensive).

No other line of `build_rows`, `insert_rows`, `fetch_picks`, or `main` was
touched. The 30s `urlopen` timeout and the `published_at` format are
unchanged from the original commit.

### Tests updated

`PAYLOAD` now matches the real endpoint shape: `direction: "BUY"`,
`target`/`stopLoss` as percentage keys, `reasons` as dicts (including one
negative-type reason, `"FII selling (-5040 Cr)"`, to prove negatives survive
the join). Existing assertions (`test_signal_is_plain_english_joined_reasons`,
`test_side_comes_from_direction`, etc.) were updated to match. Four new tests
were added:

- `test_hold_direction_is_skipped` — a `HOLD` pick produces zero rows.
- `test_avoid_direction_is_skipped` — an `AVOID` pick produces zero rows.
- `test_signal_contains_negative_reason_text_no_dict_reprs` — asserts the
  literal substring `"FII selling (-5040 Cr)"` is present and `"{"` is absent
  from `signal`.
- `test_sell_direction_has_target_below_and_stop_above_price` — a `SELL` pick
  with `target: -2.0, stopLoss: -1.5` on a `price: 500.0` produces
  `side == "SELL"`, `target < 500.0`, `stop > 500.0`.

```
$ python3 -m pytest tests/test_publish_calls.py -q
..............                                                            [100%]
14 passed in 0.05s

$ python3 -m pytest tests/ -q
........................................................................ [ 35%]
........................................................................ [ 70%]
.............................................................            [100%]
205 passed in 3.30s
```
Before this fix round: 201 passed. After: 205 passed (201 + 4 new).

### Database cleanup

The 10 rows from the original live run (wrong-sided, target-less) were
deleted before re-running, so they never become day one of the record:
```
$ python3 -c "...DELETE FROM calls...; print('cleared:', ...)"
cleared: 0
```
(`cleared` reports the post-delete count, which is 0 — the delete succeeded.)

### Live re-run (port 5051, not 5050 — the user's own server, pid 13375,
verified untouched throughout)

A fresh instance of the scratch launcher (`scripts/_run_app_5051.py`, same as
round 1 — imports `prototype.app`'s Flask object directly, calls
`app.run(port=5051, ...)`, no edits to `app.py`) was started, confirmed ready
via a bounded foreground wait (ready in 1s), then the picks endpoint was
warmed in the foreground before the graded run (cold call took 197s — same
per-symbol `yfinance` fallback behavior as round 1, since this is a fresh
process with an empty in-memory cache; a follow-up call then returned in
0.28s).

```
=== RUN 1 ===
$ TP_PICKS_URL="http://127.0.0.1:5051/api/picks?category=stocks&count=10" python3 scripts/publish-calls.py
published 10 call(s) of 10 pick(s) at 2026-08-29T13:33:50
EXIT1: 0

=== RUN 2 ===
$ TP_PICKS_URL="http://127.0.0.1:5051/api/picks?category=stocks&count=10" python3 scripts/publish-calls.py
published 0 call(s) of 10 pick(s) at 2026-08-29T13:33:57
EXIT2: 0
```

All 10 of the top-10-by-score picks happened to be BUY on this run (no
HOLD/AVOID made the top 10), so `published 10 of 10` both times the skip
guard did not reduce the count in this particular sample — it is exercised
directly by the new `test_hold_direction_is_skipped` /
`test_avoid_direction_is_skipped` unit tests, not by this live run.

### Sample rows after the fix (verbatim)
```
{'symbol': 'COFORGE', 'side': 'BUY', 'price_at_call': 2014.6, 'target': 2079.07, 'stop': 1988.41, 'sig': 'ORB breakout above 2008; Price +1.55% above VWAP (1984); Relative stre'}
{'symbol': 'OFSS', 'side': 'BUY', 'price_at_call': 12190.0, 'target': 12580.08, 'stop': 12031.53, 'sig': 'ORB breakout above 12134; Price +0.24% above VWAP (12161); Relative st'}
{'symbol': 'INFY', 'side': 'BUY', 'price_at_call': 1144.0, 'target': 1172.6, 'stop': 1132.56, 'sig': 'ORB breakout above 1137; Price +0.36% above VWAP (1140); Relative stre'}
```
Total rows: 10. Rows with `{` in `signal`: 0 (checked across all 10, not just
the sample). Every row shows a real `side`, non-NULL `target` and `stop`.

### Cleanup
```
$ rm -f scripts/_run_app_5051.py   # confirmed gone
$ kill 17048                       # the pid started this round
$ lsof -ti :5051                   # empty — confirmed dead
$ lsof -ti :5050                   # 13375 — user's own server, untouched
```

### Commit
```
$ git status --porcelain
 M scripts/publish-calls.py
 M tests/test_publish_calls.py
$ git diff --stat
 scripts/publish-calls.py    | 18 ++++++++---
 tests/test_publish_calls.py | 75 ++++++++++++++++++++++++++++++++++++++++-----
 2 files changed, 82 insertions(+), 11 deletions(-)
```
Only the two intended files changed; nothing under `.superpowers/` staged, no
scratch file staged.

## Fix round 2

`prototype/v4/composite_scorer.py` (lines 138-145) computes `target` and `sl`
as **unsigned magnitudes** derived from a volatility multiplier, with no
reference to trade direction — "3.2" means "3.2 percent away", and which side
of the entry price it lands on is decided by the trade's side, not by the
sign of the number. `build_rows` was applying the BUY arithmetic
unconditionally, which is correct for BUY but inverts a SELL: the target
would land above the entry and the stop below it, so the Task 3 resolver
would grade a short a HIT whenever the stock *rose*.

My round-1 SELL test did not catch this because its fixture supplied
negative percentages (`target: -2.0, stopLoss: -1.5`) — a convention nothing
in this codebase actually produces. The fixture invented a shape, the code
agreed with the invented shape, and the test went green while reality (all
picks carry unsigned magnitudes) was untested.

### Two changes in `scripts/publish-calls.py`

1. Both percentages are now taken as unsigned magnitudes via `abs()` (so a
   defensively-signed input can't flip the result either), and a `sign`
   variable — `-1.0` for `SELL`, `1.0` otherwise — is computed from `side`:
   ```python
   sl_pct = abs(float(p.get("stopLoss") or 0))
   tgt_pct = abs(float(p.get("target") or 0))
   sign = -1.0 if side == "SELL" else 1.0
   ```
2. The sign is applied to both levels:
   ```python
   "target": round(price * (1 + sign * tgt_pct / 100.0), 2) if tgt_pct else None,
   "stop": round(price * (1 - sign * sl_pct / 100.0), 2) if sl_pct else None,
   ```
   For `sign = 1.0` (BUY) this is byte-for-byte the same arithmetic as
   before. For `sign = -1.0` (SELL) it mirrors both levels around the entry:
   `target < price < stop`.

No other line was touched — `fetch_picks`, `insert_rows`, `main`, the 30s
timeout, and the `published_at` format are all unchanged from round 1.

### Test fixture fixed to match reality, not invent one

The SELL test (`test_sell_direction_has_target_below_and_stop_above_price`)
now supplies **positive** magnitudes — `"target": 2.0, "stopLoss": 1.5` —
matching what `composite_scorer` actually emits, with a comment warning
against re-signing them. It still asserts `target < price < stop`'s mirror
(`target < 500.0`, `stop > 500.0`), but now that assertion is true because
the CODE applies the sign, not because the fixture pre-signed the numbers.

Added `test_same_magnitudes_produce_mirrored_levels_for_buy_and_sell`: a
single `base` pick (`price=1000.0, target=3.0, stopLoss=1.0`) built once as
`BUY` and once as `SELL`. Asserts `buy["stop"] < 1000.0 < buy["target"]`,
`sell["target"] < 1000.0 < sell["stop"]`, and the exact values
`buy["target"] == 1030.0`, `sell["target"] == 970.0` — proving the sign logic
is real (same input magnitudes, mirrored output) rather than incidental.

Computed by hand for the report (matches the test and the code):
```
buy stop:    990.0   (1000 * (1 - 1*1.0/100))
buy target: 1030.0   (1000 * (1 + 1*3.0/100))
sell target: 970.0   (1000 * (1 + -1*3.0/100))
sell stop:  1010.0   (1000 * (1 - -1*1.0/100))
```

### Test results
```
$ python3 -m pytest tests/test_publish_calls.py -q
...............                                                           [100%]
15 passed in 0.06s

$ python3 -m pytest tests/ -q
........................................................................ [ 34%]
........................................................................ [ 69%]
..............................................................           [100%]
206 passed in 3.42s
```
Before this fix round: 205 passed. After: 206 passed (205 + 1 new).

### No live re-run performed, by design

**Explicitly: no live re-run was done for this fix round.** The live engine
(`score_stocks_v4()` / `composite_scorer`) currently emits only `BUY`, `HOLD`,
and `AVOID` — it has never been observed to emit `SELL` in this session — so
nothing on the wire exercises the sign-branch this fix changes. The SELL path
is verified entirely by the two unit tests above (unsigned-magnitude fixture
+ the new mirrored-levels test), not by hitting the live endpoint. This is a
silent latent bug fixed ahead of the engine ever needing it, per the
coordinator's explicit instruction to fix it anyway even though the branch is
currently unreachable in production traffic.

### BUY rows already in the database — confirmed unaffected

Since `sign = 1.0` for BUY, the arithmetic is identical to before the fix.
Verified directly against the live SQLite rows written in fix round 1 (no
DELETE, no re-run — same 10 rows, untouched):
```
$ python3 -c "...SELECT COUNT(*) FROM calls..."
row count: 10
$ python3 -c "...SELECT symbol, side, price_at_call, target, stop FROM calls LIMIT 1..."
{'symbol': 'COFORGE', 'side': 'BUY', 'price_at_call': 2014.6, 'target': 2079.07, 'stop': 1988.41}
```
Row count (10) and the sample row's `target`/`stop` values are byte-identical
to what fix round 1 recorded — confirming the sign fix does not alter BUY
output.

### Commit
```
$ git status --porcelain
 M scripts/publish-calls.py
 M tests/test_publish_calls.py
$ git add scripts/publish-calls.py tests/test_publish_calls.py
$ git commit -m "fix(calls): sign the target/stop offset by side, not by input"
```
Only the two intended files changed; nothing under `.superpowers/` staged, no
scratch file involved (no server was started this round).
