# Task 3 Report: Calls and call detail

## Files modified
- `prototype/static/app/screens.js` — added `stamp`, `calls`, `outcomeLine`, `call`; exported `calls`, `call`, `stamp` on `window.TPScreens`
- `prototype/static/app/main.js` — added `loadCalls`, `loadCall`; extended `onShow` additively (kept `home`, added `rest` param)
- `tests/test_app_screens.py` — appended two new tests

## Step 1/2: Failing tests (before implementation)

Command:
```
python3 -m pytest tests/test_app_screens.py -q
```

Output:
```
...........FF                                                            [100%]
=================================== FAILURES ===================================
_______________ test_calls_screen_stamps_the_data_it_is_showing ________________

client = <FlaskClient <Flask 'prototype.app'>>

    def test_calls_screen_stamps_the_data_it_is_showing(client):
        """Outside market hours the list is stale; the page must say when."""
        js = client.get("/static/app/screens.js").get_data(as_text=True)
>       assert "as_of" in js
E       assert 'as_of' in '"use strict";\n\n/* One render function per screen. Each takes a node and a payload and builds\n   DOM -- no fetching... money: money, pct: pct, el: el, card: card,\n    rateLine: rateLine, callRow: callRow,\n    home: home\n  };\n})();\n'

tests/test_app_screens.py:129: AssertionError
______________ test_call_detail_distinguishes_open_from_resolved _______________

client = <FlaskClient <Flask 'prototype.app'>>

    def test_call_detail_distinguishes_open_from_resolved(client):
        """A live call must not imply an outcome that has not happened."""
        js = client.get("/static/app/screens.js").get_data(as_text=True)
        for token in ("outcome", "hit", "miss", "ungraded"):
>           assert token in js, token
E           AssertionError: outcome
E           assert 'outcome' in '"use strict";\n\n/* One render function per screen. Each takes a node and a payload and builds\n   DOM -- no fetching... money: money, pct: pct, el: el, card: card,\n    rateLine: rateLine, callRow: callRow,\n    home: home\n  };\n})();\n'

tests/test_app_screens.py:136: AssertionError
=========================== short test summary info ============================
FAILED tests/test_app_screens.py::test_calls_screen_stamps_the_data_it_is_showing
FAILED tests/test_app_screens.py::test_call_detail_distinguishes_open_from_resolved
2 failed, 11 passed in 3.10s
```

Both failures are for the right reason: the two new render functions and their
vocabulary (`as_of`, `outcome`, `hit`, `miss`, `ungraded`) did not exist yet in
`screens.js`.

## Step 3/4: Implementation

Added to `screens.js` verbatim per the brief: `stamp(iso)`, `calls(node, data)`,
`outcomeLine(c)`, `call(node, data)`. Exported `calls: calls, call: call, stamp: stamp`
alongside the existing exports.

Added to `main.js`: `loadCalls()` and `loadCall(id)` beside `loadHome()`. Extended
`onShow` by reading the **current** file first (it already had `if (section === "home")
loadHome();`), then appending two `else if` branches and adding the `rest` parameter
that `loadCall` needs. `home` was not touched or replaced.

## Vocabulary scan (manual, before running the full suite)

Checked `screens.js`, `main.js`, `app.css`, `app.html` for each banned token
(`v4`, `v5_size`, `composite_scorer`, `alpha-hunter`, `regime`, `orchestrator`,
`sprint`) with `grep -in`. No matches in any file.

## Step 5: Full suite (after implementation)

Command:
```
python3 -m pytest tests/ -q
```

Output:
```
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 70%]
........................................................................ [ 94%]
.................                                                        [100%]
305 passed in 5.16s
```

Before (baseline, prior to appending the two new tests): 303 passed.
After: 305 passed. Delta matches the 2 new tests exactly — no other test's
pass/fail status changed.

## Commit

```
git add prototype/static/app/screens.js prototype/static/app/main.js tests/test_app_screens.py
git commit -m "feat(app): the calls list and one call's reasoning ..."
```

SHA: `f55eb10`

## Final `onShow` chain (verify `home` survived)

```javascript
    onShow: function (section, rest) {
      if (section === "home") loadHome();
      else if (section === "calls") loadCalls();
      else if (section === "call") loadCall(rest && rest[0]);
    }
```

`home` is intact; `calls` and `call` were appended as `else if` branches, not
a replacement.

## Verification limits

No rendering was verified — there is no browser in this environment. All
verification is: (a) the two new tests pass by scanning the served JS text
for the required tokens, (b) the full suite (305 tests) passes, (c) a manual
grep confirmed no banned-vocabulary tokens appear in the modified files. DOM
behavior, click handlers, and visual layout for `TPScreens.calls` and
`TPScreens.call` were not exercised by any test or manual browser check, per
the brief's own note that this test file cannot exercise DOM (no browser,
and adding one would breach the no-new-dependencies constraint).

---

## Fix round 1

### Findings addressed
1. **`outcomeLine` reported any non-`"hit"` outcome as "Missed"** — including
   `null`, `undefined`, and unrecognised values — displaying a gain/loss
   percentage beside a fabricated "Missed" label.
2. **`test_call_detail_distinguishes_open_from_resolved` could not detect
   this** — it grepped for four substrings (`outcome`, `hit`, `miss`,
   `ungraded`) that any implementation of the feature contains regardless of
   correctness (`miss` matched the unrelated 404-branch variable name `miss`).

### Fix
- Created `prototype/static/app/outcome.js`: pure `outcomeText(call)` /
  `outcomeKind(call)` functions behind the same UMD wrapper `route.js` uses
  (`module.exports` under node, `window.TPOutcome` in a browser). Any outcome
  other than `"open"`, `"ungraded"`, `"hit"`, or `"miss"` now returns
  `"Outcome not recorded."` with no colour class, instead of being coerced
  into `"Missed"`.
- Created `tests/js/outcome.test.js` (6 tests): open never implies a result,
  ungraded explains itself, hit/miss are not interchangeable, an
  unrecognised outcome (`null`, `undefined`, `""`, `"pending"`, `"PENDING"`,
  `0`) is never reported as `"Missed"`, a missing call object does not
  throw, and colour tracks the outcome correctly.
- Rewrote `outcomeLine` in `screens.js` to call `window.TPOutcome.outcomeText`
  / `outcomeKind` and only append the price/percentage suffix when `kind` is
  non-empty (i.e. a real hit or miss) — price/percentage math (guarding
  `null` and zero) was otherwise untouched.
- Added `<script src="/static/app/outcome.js" defer></script>` to
  `prototype/templates/app.html`, before `app/screens.js` (which now calls
  into it) and after `app/api.js`.
- Added `/static/app/outcome.js` to the module list in
  `test_every_module_the_page_references_is_fetchable` and to the `surfaces`
  list in `test_no_operator_vocabulary_in_the_page_or_its_modules`.
- Deleted `test_call_detail_distinguishes_open_from_resolved` from
  `tests/test_app_screens.py` — its job now belongs to
  `tests/js/outcome.test.js`, which can actually fail.

### Verification

`node --test tests/js/*.test.js`:
```
1..18
# tests 18
# suites 0
# pass 18
# fail 0
# cancelled 0
# skipped 0
# todo 0
```
12 pre-existing (route.js) + 6 new (outcome.js) = 18, all passing.

`python3 -m pytest tests/ -q`:
```
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 71%]
........................................................................ [ 94%]
................                                                         [100%]
304 passed in 8.37s
```
305 (round 0 total) minus the one deleted test = 304, as expected.

### Inverted-ternary experiment (the whole point of this round)

Edited `outcome.js` in place: swapped the `hit`/`miss` return values so
`outcome === "hit"` returned `"Missed"` and `outcome === "miss"` returned
`"Hit"`. Ran `node --test tests/js/outcome.test.js`:
```
'Missed' !== 'Hit'
...
# tests 6
# pass 5
# fail 1
```
`hit and miss are not interchangeable` failed with `Expected 'Hit', got
'Missed'` — confirming the new test binds to real behavior, unlike the
deleted substring test.

Reverted the file (`diff` against the pre-edit copy showed no difference),
re-ran:
```
# tests 6
# pass 6
# fail 0
```
All 6 pass again.

### Vocabulary re-scan
Manually grepped `outcome.js`, `screens.js`, `main.js`, `app.html` for all
seven banned tokens (`v4`, `v5_size`, `composite_scorer`, `alpha-hunter`,
`regime`, `orchestrator`, `sprint`). No matches.

### Files touched this round
- `prototype/static/app/outcome.js` (new)
- `tests/js/outcome.test.js` (new)
- `prototype/static/app/screens.js` (modified: `outcomeLine` rewritten)
- `prototype/templates/app.html` (modified: new script tag)
- `tests/test_app_screens.py` (modified: fetchable list + vocabulary
  surfaces updated, dead test deleted)

`prototype/app.py`, `app.css`, and the shell's `go`/`boot`/`renderNav` were
not touched.
