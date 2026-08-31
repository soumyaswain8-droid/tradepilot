# Task 1 report — the client shell (route, template, stylesheet, navigation)

Worktree: `/Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/client-screens`
Branch: `feat/client-screens`
Commit: `85cf96f`

## Correction applied

The brief listed `TPRoute.viewIdFor` as an export of `/static/desk/route.js`. It does not
exist — the module (UMD, `window.TPRoute` in browser / CommonJS under node) exports exactly
`parse` and `build`. Nothing in this task's code calls `viewIdFor`; `main.js` builds mount
ids as `"view-" + section` itself, per the correction. `route.js` itself was not touched.

## Deviation from the brief's file list (and why)

The brief's "Files" section lists only `app.html`, `app.css`, `static/app/main.js`,
`app.py` (modify), and `tests/test_app_screens.py`. It does not list
`static/app/api.js` or `static/app/screens.js`. But:

- The template (given verbatim in Step 4) includes
  `<script src="/static/app/api.js" defer>` and `<script src="/static/app/screens.js" defer>`.
- The brief's own test file (`test_every_module_the_page_references_is_fetchable`,
  `test_module_order_is_load_bearing`) fetches both paths and asserts 200 + non-empty
  content, and asserts their position in the HTML relative to `main.js`.
- Step 7 states "Expected: 8 passed" for exactly this test file.

Without those two files existing and being non-empty, 3 of the 8 tests fail (one with a
`ValueError: substring not found` from `str.index`, not just an assertion failure). I
confirmed via `git log` and `find` that no `static/app/api.js` or `static/app/screens.js`
exist anywhere in the worktree's history. The plan's own ledger
(`.superpowers/sdd/2026-08-31-client-screens/progress.md`) confirms a later task in this
plan ("T2") is the one that populates `TPApi.*` and `TPScreens.*` — i.e. these files are
expected to exist by the end of Task 1 (empty/stub) and be filled in later, not created
later from scratch.

I created two minimal stub files, both `"use strict"`, both non-empty, both declaring
their namespace without behavior:

- `prototype/static/app/api.js` → `window.TPApi = window.TPApi || {};`
- `prototype/static/app/screens.js` → `window.TPScreens = window.TPScreens || {};`

This is the smallest change that makes the brief's own tests pass without inventing any
behavior beyond what a later task is expected to fill in. Flagging this explicitly since
it was not in the literal file list — a reviewer should confirm this matches the plan's
intent for Task 2 to build on.

## Files created

- `prototype/templates/app.html` (35 lines) — verbatim from brief Step 4
- `prototype/static/app.css` (124 lines) — verbatim from brief Step 5
- `prototype/static/app/main.js` (103 lines) — verbatim from brief Step 6
- `prototype/static/app/api.js` (6 lines) — stub, not in brief, see Deviation above
- `prototype/static/app/screens.js` (6 lines) — stub, not in brief, see Deviation above
- `tests/test_app_screens.py` (83 lines) — verbatim from brief Step 1

## Files modified

- `prototype/app.py` — added the `/app` route directly after the existing `/classic`
  route, verbatim from brief Step 3:

  ```python
  @app.route("/app")
  def client_app():
      """The client dashboard. Additive -- / and /classic are unchanged."""
      return render_template("app.html")
  ```

## Commands run, with full output

### Baseline (before any of this task's changes)

```
$ cd /Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/client-screens && python3 -m pytest tests/ -q
........................................................................ [ 49%]
........................................................................ [ 73%]
........................................................................ [ 98%]
....                                                                     [100%]
292 passed in 5.50s
```

### Step 2 — new tests written, run before any implementation (expected to fail)

```
$ python3 -m pytest tests/test_app_screens.py -q
FFFFF...                                                                 [100%]
=================================== FAILURES ===================================
____________________________ test_app_route_serves _____________________________
    def test_app_route_serves(client):
>       assert client.get("/app").status_code == 200
E       AssertionError: assert 404 == 200
______________ test_every_module_the_page_references_is_fetchable ______________
        for path in ("/static/desk/route.js", "/static/app/api.js",
                     "/static/app/screens.js", "/static/app/main.js",
                     "/static/app.css"):
            r = client.get(path)
>           assert r.status_code == 200, path
E           AssertionError: /static/app/api.js
E           assert 404 == 200
_______________________ test_all_five_mount_points_exist _______________________
        for view in ("view-home", "view-calls", "view-call", "view-book", "view-record"):
>           assert view in body, view
E           AssertionError: view-home
______________________ test_module_order_is_load_bearing _______________________
>       assert body.index("desk/route.js") < body.index("app/main.js")
E       ValueError: substring not found
_________________ test_the_router_is_reused_not_reimplemented __________________
        js = client.get("/static/app/main.js").get_data(as_text=True)
>       assert "TPRoute.parse" in js
E       AssertionError: assert 'TPRoute.parse' in '<!doctype html>\n<html lang=en>\n<title>404 Not Found</title>\n...'
=========================== short test summary info ============================
FAILED tests/test_app_screens.py::test_app_route_serves - AssertionError: ass...
FAILED tests/test_app_screens.py::test_every_module_the_page_references_is_fetchable
FAILED tests/test_app_screens.py::test_all_five_mount_points_exist - Assertio...
FAILED tests/test_app_screens.py::test_module_order_is_load_bearing - ValueEr...
FAILED tests/test_app_screens.py::test_the_router_is_reused_not_reimplemented
5 failed, 3 passed in 3.20s
```

The 3 that passed before implementation (`test_no_operator_vocabulary_reaches_the_page`,
`test_the_terminal_and_classic_are_untouched`, `test_no_inline_script_in_the_template`)
pass vacuously/correctly against pre-existing routes (`/`, `/classic`) and a 404 body that
happens to contain no banned words and no `<script` tags — expected, not a concern.

### Step 7 — after implementation (expected: 8 passed)

```
$ python3 -m pytest tests/test_app_screens.py -q
........                                                                 [100%]
8 passed in 3.06s
```

### Step 8 — full suite

```
$ python3 -m pytest tests/ -q
........................................................................ [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
............                                                             [100%]
300 passed in 5.47s
```

## Test counts

- Before: 292 passed
- After: 300 passed (292 baseline + 8 new from `test_app_screens.py`)
- Matches the plan ledger's stated running total for Task 1 (292 + 8 = 300).

## Commit

```
$ git add prototype/templates/app.html prototype/static/app.css prototype/static/app/main.js \
    prototype/static/app/api.js prototype/static/app/screens.js prototype/app.py \
    tests/test_app_screens.py
$ git commit -m "feat(app): the client shell -- route, nav, and one breakpoint ..."
[feat/client-screens 85cf96f] feat(app): the client shell -- route, nav, and one breakpoint
 7 files changed, 363 insertions(+)
 create mode 100644 prototype/static/app.css
 create mode 100644 prototype/static/app/api.js
 create mode 100644 prototype/static/app/main.js
 create mode 100644 prototype/static/app/screens.js
 create mode 100644 prototype/templates/app.html
 create mode 100644 tests/test_app_screens.py
```

Commit SHA: `85cf96f`

## What I did not verify

There is no browser in this environment. Nothing here confirms the page renders, that the
sidebar/tab-bar breakpoint actually looks right at 900px, that navigation clicks work, or
that the CSS produces the intended visual result — none of that was tested and none of it
should be assumed from this report. The tests only prove: the route serves 200, all five
listed static assets are fetchable and non-empty, all five mount-point ids appear as
literal strings in the served HTML, script tags appear in the required load order, `main.js`
textually contains calls to `TPRoute.parse` and `TPRoute.build`, no banned operator-vocabulary
substrings appear in the lowercased HTML, `/` and `/classic` still serve 200, and every
`<script` tag in the served HTML has `src=` in its opening tag (no inline script). Anything
about actual on-screen appearance or interactive behavior is unverified and belongs to the
manual checklist (`docs/APP_MANUAL_CHECKS.md`, referenced in the test file's own docstring
but not created by this task).

## Nothing else surprising

`prototype/app.py` did not have a blank line between the `/classic` route and `/landing`
route in the original file (they were adjacent with no blank line); I preserved that
adjacency style for the new `/app` route relative to `/classic` (one blank line before,
matching the pattern used elsewhere in the file between routes) and left the pre-existing
lack-of-blank-line before `/landing` untouched.

## Fix round 1

Two review findings addressed. Files touched this round: `tests/test_app_screens.py` only
(no changes to `main.js`, `app.css`, `app.html`, or `prototype/app.py`).

### Finding: no change made (recorded per coordinator instruction)

`TPApp.SECTIONS` has four entries, not the five the brief's Interfaces section states.
Confirmed correct as-is: `call` is reachable via `ROUTABLE`/routing but intentionally has
no nav entry (`label: null`, excluded from `SECTIONS`). No code change made.

### Finding: `test_no_operator_vocabulary_reaches_the_page` fixed

Replaced with `test_no_operator_vocabulary_in_the_page_or_its_modules`, per the
coordinator's exact replacement text — now scans `/app`, `/static/app/main.js`,
`/static/app/api.js`, `/static/app/screens.js`, and `/static/app.css`, not just the
static HTML response. Docstring now states explicitly what it does not cover (banned
words arriving inside API data, guarded instead by `shape_call`'s field allowlist in
`prototype/client_api.py`).

**First run against our own files:** no words tripped. Pre-check
(`grep -inE "v4|v5_size|composite_scorer|alpha-hunter|regime|orchestrator|sprint"` across
`app.html`, `app.css`, `main.js`, `api.js`, `screens.js`) found zero matches, and the test
run confirmed it: 8/8 passed on the first run after the replacement, no wording changes
needed in any implementation file.

**Deliberate-failure check, both directions:**
- Appended `/* v4 score */` to `prototype/static/app/screens.js` (backed up first) and ran
  `test_no_operator_vocabulary_in_the_page_or_its_modules` alone: **FAILED**, with
  `AssertionError: ('/static/app/screens.js', 'v4')` — pinpointing the exact file and word.
- Restored `screens.js` from the backup (byte-identical to the version already committed
  in `85cf96f` — confirmed via `git status --short` showing no diff on that file) and
  re-ran the same test: **PASSED**. Full `tests/test_app_screens.py` also re-ran clean
  (8 passed) after the revert.

Both directions confirmed: the test binds.

### Finding: `test_module_order_is_load_bearing` fixed

Added an explicit presence check (`assert tag in body, "missing script tag: " + tag`) for
all four script tags before the `.index()` comparisons, per the coordinator's exact
replacement text. A missing tag now fails with `AssertionError: missing script tag: ...`
instead of an unhandled `ValueError: substring not found`.

### Verification

```
$ python3 -m pytest tests/ -q
........................................................................ [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
............                                                             [100%]
300 passed in 5.45s
```

300 passed — same count as before this round (one test replaced, one test hardened, none
added).

### Commit

Commit SHA: `070876e`
