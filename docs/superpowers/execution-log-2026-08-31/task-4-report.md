# Task 4 Report: The track record

## Files modified
- `prototype/static/app/screens.js` (added `record(node, data)`, exported it)
- `prototype/static/app/main.js` (added `loadRecord()`, wired `record` into `onShow`)
- `tests/test_app_screens.py` (appended `test_record_screen_labels_since_as_recording_not_grading`)

## Working directory
`/Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/client-screens` (branch `feat/client-screens`, isolated worktree — parent checkout untouched).

## Step 0: baseline (before any change)

```
$ python3 -m pytest tests/ -q
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 71%]
........................................................................ [ 94%]
................                                                         [100%]
304 passed in 5.69s
```

## Step 1 & 2: failing test added, run to confirm it fails for the right reason

Appended the exact test from the brief to `tests/test_app_screens.py`.

```
$ python3 -m pytest tests/test_app_screens.py -q
............F                                                            [100%]
=================================== FAILURES ===================================
___________ test_record_screen_labels_since_as_recording_not_grading ___________

client = <FlaskClient <Flask 'prototype.app'>>

    def test_record_screen_labels_since_as_recording_not_grading(client):
        """`since` is the first call RECORDED, not the first resolved. ...
        js = client.get("/static/app/screens.js").get_data(as_text=True).lower()
>       assert "recording since" in js
E       assert 'recording since' in '"use strict";\n\n/* one render function per screen. ...'

tests/test_app_screens.py:142: AssertionError
=========================== short test summary info ============================
FAILED tests/test_app_screens.py::test_record_screen_labels_since_as_recording_not_grading
1 failed, 12 passed in 3.73s
```

Failed for the expected reason: the phrase "recording since" was simply absent from `screens.js` (the renderer didn't exist yet).

## Step 3: implementation — `screens.js`

Added `record(node, data)` before the `window.TPScreens` export block, and added `record: record` to the export object. Deviated from the brief's literal code in one place per the task's constraint #2: instead of writing `list[j].outcome === "hit" || list[j].outcome === "miss"` and `c.outcome === "hit" ? "up" : "down"` inline, both the filter and the colour class go through `window.TPOutcome.outcomeKind(c)` — reusing the UMD module rather than re-deriving hit/miss logic a second time. Behaviourally identical (outcomeKind returns `"up"` for hit, `"down"` for miss, `""` otherwise), but the source of truth is the shared module.

`rateLine(rec)` and `stamp(iso)` reused as-is, per constraint #3 — not redefined.

## Step 4: wiring — `main.js`

Added `loadRecord()` (identical to the brief's version) and appended `else if (section === "record") loadRecord();` to the existing `onShow` chain, additively — did not replace or rewrite the block.

Full `onShow` chain after the change:

```javascript
    onShow: function (section, rest) {
      if (section === "home") loadHome();
      else if (section === "calls") loadCalls();
      else if (section === "call") loadCall(rest && rest[0]);
      else if (section === "record") loadRecord();
    }
```

## Step 5: run to verify it passes

```
$ python3 -m pytest tests/ -q
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 70%]
........................................................................ [ 94%]
.................                                                        [100%]
305 passed in 5.70s
```

304 -> 305 (exactly the +1 expected).

`tests/test_app_screens.py` alone (13 tests, includes the new one and the banned-vocabulary scan):

```
$ python3 -m pytest tests/test_app_screens.py -q -v
tests/test_app_screens.py .............                                  [100%]
============================== 13 passed in 2.77s
```

### Node suite (unchanged files, confirms no regression)

```
$ node --test tests/js/outcome.test.js tests/js/route.test.js
...
1..18
# tests 18
# suites 0
# pass 18
# fail 0
```

18 -> 18 (unchanged, as expected — `outcome.js` and `route.js` were not touched).

Note: `node --test tests/js/` (directory form) fails with `MODULE_NOT_FOUND` on this machine — pre-existing environment quirk unrelated to this task; running the two `.test.js` files explicitly is the working invocation and gives the correct 18/18.

## Commit

```
6e81465 feat(app): the track record, labelled honestly
```

3 files changed, 84 insertions(+), 1 deletion(-).

## Verification of the four "cannot know" constraints

1. **`onShow` additive** — confirmed above, one new `else if` branch, existing three untouched.
2. **`outcomeKind` reused for colour** — both the "is this resolved" filter and the "up"/"down" class in the resolved-calls list go through `window.TPOutcome.outcomeKind(c)`, no local `c.outcome === "hit"` re-derivation.
3. **Reused `rateLine`, `stamp`, `el`, `card`** — all reused, none redefined.
4. **Banned vocabulary** — `test_no_operator_vocabulary_in_the_page_or_its_modules` passes; no banned word (`v4`, `v5_size`, `composite_scorer`, `alpha-hunter`, `regime`, `orchestrator`, `sprint`) appears anywhere in the new code. Vocabulary used instead: "how the calls stand", "resolved calls", "recording since".

## Surprises / notes
- None substantive. The only deviation from the brief's literal snippet is the `outcomeKind`-based filter/colour logic described above (required by the task's own constraint #2, not a judgment call).
- No rendering was verified — there is no browser in this environment. Only the served-JS string assertions (pytest) and the pure-function node tests were run. `docs/APP_MANUAL_CHECKS.md` presumably covers visual verification, out of scope here.

## Fix round 1

Three defects found in review, all in the brief rather than in the implementation of it. Fixed all three, exactly as specified, in `prototype/static/app/screens.js` and `tests/test_app_screens.py` only. `main.js`, `outcome.js`, `api.js`, `app.html`, `app.css`, and `rateLine` were not touched.

**Finding 1 (tally exhaustive, list capped, nothing said so).** Added a `graded = rec.hit + rec.miss` and a footer line under "Resolved calls" (only when the list is non-empty) stating whether it shows all graded calls or the 50 most recent of a larger total.

**Finding 2 (tally never checked its own arithmetic).** Added `counted = rec.hit + rec.miss + rec.open + rec.ungraded` under "How the calls stand"; when it disagrees with `rec.total`, an extra "Not accounted for" row appears with the gap. Invisible when the sums agree, which they do today.

**Finding 3 (test satisfied by its own comment).** Rewrote `test_record_screen_labels_since_as_recording_not_grading` to assert the exact quoted template form `'"Recording since "'` (case-sensitive, with the opening quote and trailing space) and to assert `'"Since "'` is absent, so neither the explanatory comment nor a reverted bare label can satisfy it.

### Verification

```
$ python3 -m pytest tests/ -q
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 70%]
........................................................................ [ 94%]
.................                                                        [100%]
305 passed in 4.85s
```

305 (unchanged from before this round — one test rewritten, none added).

```
$ node --test tests/js/outcome.test.js tests/js/route.test.js
...
1..18
# tests 18
# pass 18
# fail 0
```

18 (unchanged).

### Bind experiment (proves the rewritten test actually binds to behaviour)

Temporarily changed the template string from `"Recording since " + rec.since` to `"Since " + rec.since` in `screens.js`, leaving the explanatory comment (which still reads "recording since" in prose) untouched:

```
$ python3 -m pytest tests/test_app_screens.py::test_record_screen_labels_since_as_recording_not_grading -q
...
>       assert '"Recording since "' in js
E       assert '"Recording since "' in '"use strict";\n...'
FAILED tests/test_app_screens.py::test_record_screen_labels_since_as_recording_not_grading
1 failed in 2.78s
```

Confirmed FAIL, for the right reason — the old test (a case-insensitive whole-file substring search for `"recording since"`, matching prose or code alike) would have PASSED this exact regression, because the comment two lines above the label still contains the phrase in lowercase prose.

Reverted the change:

```
$ python3 -m pytest tests/test_app_screens.py::test_record_screen_labels_since_as_recording_not_grading -q
.                                                                        [100%]
1 passed in 2.68s

$ python3 -m pytest tests/ -q
...
305 passed in 4.85s
```

Confirmed PASS again, full suite still 305.

### Footer line for "Resolved calls" (point 3)

- **Live record** (`hit: 1, miss: 0`, one call in the list): `graded = 1`, `resolved.length = 1`, `1 < 1` is false, so the branch renders: **"All 1 resolved calls."**
- **Hypothetical** (120 resolved total, 50-cap list returns 50): `graded = 120`, `resolved.length = 50`, `50 < 120` is true, so it renders: **"Showing the 50 most recent of 120 resolved calls."**

### Commit
`5f86df1` — "fix(app): honest record footer, tally self-check, test binds to behaviour"
