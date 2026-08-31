# Task 6 report: the manual checklist

## Files

- Created: `docs/APP_MANUAL_CHECKS.md` (38 `☐` checkable items across six
  sections: Home, Calls and call detail, Track record, Book, Shell and
  responsiveness, and Checking the signed-out states)
- Modified: `tests/test_app_screens.py` (+1 test,
  `test_the_manual_checklist_exists_and_is_tracked`)

The brief's own checklist (16 items) predates Tasks 2-5, which added states
during review that it never saw: Home's fifth state (book-load-failure vs.
zero-positions), the unrecognised-outcome wording, the tally self-check row
("Not accounted for"), and two known-unfixed rendering quirks the controller
flagged (singular "All 1 resolved calls.", no nav highlight on call detail).
Per instructions, I used the brief's structure and tone but wrote the actual
38-item set reflecting what shipped, not what the brief described.

## Commands and output

Baseline:
```
$ python3 -m pytest tests/ -q
310 passed in 5.32s
```

Step 2 -- test added, file not yet created, confirming it fails:
```
$ python3 -m pytest tests/test_app_screens.py -q
...
AssertionError: assert False
 +  where False = <function exists ...>('.../docs/APP_MANUAL_CHECKS.md')
1 failed, 17 passed in 3.15s
```

After creating `docs/APP_MANUAL_CHECKS.md`:
```
$ python3 -m pytest tests/ -q
311 passed in 5.07s
```
(The brief's own "Verification" section predicted 312 passing / 20 new tests
across all six tasks -- also stale, from before the plan was trimmed during
review. The actual, current baseline handed to me was 310, and this task
adds exactly 1, landing at 311, which is what both runs above show.)

Node suite, unaffected:
```
$ node tests/js/outcome.test.js   # pass, 0 fail
$ node tests/js/route.test.js     # pass, 0 fail
```

## Walking the checklist

Port 5050 belongs to an unrelated process (someone else's `app.py`), so I
ran TradePilot on `127.0.0.1:5051` instead (`python3 -c "from prototype.app
import app; app.run(port=5051)"`), leaving 5050 untouched throughout.

I seeded `prototype/tradepilot_app.db` (gitignored, not committed) with
five calls -- one each of hit, miss, open, ungraded, and an outcome value
("expired") the renderer doesn't recognise -- and two positions, one priced
and one with no live quote. Using Playwright I walked every state in the
checklist: all five Home states, both resolvable and unrecognised outcome
text on call detail, the unknown-call-id fallback, Back-to-calls, the
"Recording since" label, the ungraded/tally rows on Track Record, Book's
provenance labels, "price unavailable" with cost basis, the Remove
confirm-dialog naming the symbol (cancelled it and confirmed the position
stayed), the bad-quantity form error, the 900px breakpoint (sidebar/tabbar
swap, KPI grid 1-col vs 2-col, computed via `getComputedStyle`), tab-bar/
content overlap (none, via bounding rects), and Back-navigation leaving a
freshly loaded `/app` (via `about:blank` -> `/app` -> back).

I specifically forced exactly one resolved call to verify the two
known-unfixed items in the browser rather than by inspection: the footer
read **"All 1 resolved calls."** exactly as flagged, and no nav entry was
highlighted while `#call/...` was showing. Both are now confirmed-real, not
assumed.

Signed-out states: edited `client_auth.py`'s `current_user()` to `return
None`, restarted the server, confirmed Home keeps calls/hit-rate and shows
"Sign in to see your book", Book shows "Sign in to see your book." with no
error, and Calls/Record are fully usable. Reverted the edit
(`git diff prototype/client_auth.py` shows no diff after revert) and
restarted again before finishing.

Cleaned up afterward: deleted the seeded calls/positions rows, killed the
5051 dev server, confirmed 5050's original process (PID 9983) was never
touched.

## Before/after test counts

- pytest: 310 -> 311 (1 new)
- node: 18 -> 18 (unchanged)

## Checklist item count

38 `☐` items in `docs/APP_MANUAL_CHECKS.md`.

## Commit

`d5d109e` -- "docs(app): the checks a green suite does not make"

## Anything surprising

- The brief's file itself was stale in two ways the task description
  already warned about (checklist content, and the "312 passing" count in
  its own Verification section) -- both confirmed and worked around as
  instructed.
- Both "known, unfixed" items the controller asked me to judge in the
  browser reproduced exactly as described when I engineered the precise
  data shape (one resolved call) needed to see them -- they were not
  visible in my first pass with two resolved calls, which shows why the
  checklist needs a live walk rather than a read of the code.
- `client_auth.py`'s stub gates five endpoints, not one; the file's own
  revert warning was necessary in practice, not just precautionary --
  Book, positions add/remove would all 401 if I'd forgotten to revert.

## Fix round 1

Four findings from the coordinator, all addressed.

**Finding 1 (critical) -- tally self-check row omitted.** My seed data
(`c-weird1`, outcome `"expired"`) put `counted = 4` against `total = 5`,
which renders a "Not accounted for" row in Track record's "How the calls
stand" -- and I watched it render during the original walk without writing
it down. Added both requested lines under Track record.

**Finding 2 -- shipped states with no line.** Added the ten requested lines
across Home (record-fetch-fails, calls-fetch-fails), Calls (empty list,
fetch failure), call detail (resolved call shows exit price + move),
Track record (empty since-line, empty resolved-calls), and Book (empty
list, server-rejected add). Verified each string against source before
adding it (`screens.js` / `main.js` grep), rather than trusting the
coordinator's wording blind -- all matched exactly.

**Finding 3 -- unwalkable on a fresh install.** Added a "Seeding the data"
section right after the intro, with the actual sqlite snippet I used during
the original walk (five calls covering hit/miss/open/ungraded/unrecognised,
one priced and one unpriced position), the one-resolved-call flip for the
singular-footer check, a note that `tradepilot_app.db` is gitignored, and
cleanup DELETEs.

**Finding 4 -- unsupported `bookFailed` claim.** Correct: I had walked
`bookFailed` from source, not from a browser. I reached it now the way the
finding suggested -- one temporary `raise RuntimeError(...)` at the top of
`positions_list()` in `prototype/client_api.py`, confirmed via `curl` (500)
and then in Playwright: the portfolio card read "Could not load your book
just now." Reverted the edit immediately; `git diff prototype/client_api.py`
is empty. Documented the mechanism as its own "Checking the
book-load-failure state" section in the checklist, mirroring the
signed-out section's format and revert warning, since `/api/app/positions`
has no natural path to a 500 and the next person needs the same edit to
see this state.

Verification:
```
$ python3 -m pytest tests/ -q
311 passed in 5.77s
```
Checklist grew from 38 to 49 `☐` items. `git status --porcelain` on
`prototype/client_api.py` and `prototype/client_auth.py`: both clean.
