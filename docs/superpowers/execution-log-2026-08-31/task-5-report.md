# Task 5 report: the book

## Files modified
- `prototype/static/app/screens.js` — added `positionRow()` and `book()`, exported `book`/`positionRow`
- `prototype/static/app/main.js` — added `loadBook()`, added `else if (section === "book") loadBook();` to `onShow`
- `prototype/client_api.py` — dropped `"user_id"` from `POSITION_FIELDS` (one line)
- `tests/test_app_screens.py` — appended 3 tests
- `tests/test_client_api_positions.py` — appended 1 test

## Step 2: run before implementation (expected 4 failures)

```
$ python3 -m pytest tests/test_app_screens.py tests/test_client_api_positions.py -q
```

Result: **3 failed, 38 passed** (not 4). `test_book_has_no_close_action` passed
immediately — it asserts `"closed_at" not in js`, which was trivially true
before `book()` existed since `screens.js` had never mentioned `closed_at` at
all. The brief's "expected 4 failures" assumed all four new tests fail
pre-implementation; one of the four is an absence check that a not-yet-written
feature satisfies for free. The three genuine failures:

```
FAILED tests/test_app_screens.py::test_book_never_renders_a_missing_price_as_zero
FAILED tests/test_app_screens.py::test_book_shows_provenance_for_each_position
FAILED tests/test_client_api_positions.py::test_positions_do_not_leak_the_internal_user_id
3 failed, 38 passed in 3.52s
```

Full assertion output for the three:
```
>       assert "price unavailable" in js.lower()
E       assert 'price unavailable' in '"use strict";...'

>       assert "call_id" in js
E       assert 'call_id' in '"use strict";...'

>       assert "user_id" not in pos
E       AssertionError: assert 'user_id' not in {'avg_price': 1000.0, 'broker_ref': None, 'call_id': None, 'closed_at': None, ...}
```

## Steps 3-5: implementation
Applied verbatim per brief, with one deliberate wording change (see "surprising" below). `client_api.py`:
```python
POSITION_FIELDS = ("id", "symbol", "qty", "avg_price", "opened_at",
                   "closed_at", "exit_price", "source", "broker_ref", "call_id")
```

## Step 6: run after implementation

```
$ python3 -m pytest tests/ -q
........................................................................ [ 23%]
........................................................................ [ 46%]
........................................................................ [ 69%]
........................................................................ [ 93%]
.....................                                                    [100%]
309 passed in 5.31s
```

```
$ node --test tests/js/route.test.js tests/js/outcome.test.js
# tests 18
# pass 18
# fail 0
```

## Before/after counts
| Suite | Before | After |
|---|---|---|
| pytest (`tests/`) | 305 | 309 |
| node (`tests/js/`) | 18 | 18 (unchanged — `route.js`/`outcome.js` not touched) |

## Full `onShow` chain (final)
```javascript
    onShow: function (section, rest) {
      if (section === "home") loadHome();
      else if (section === "calls") loadCalls();
      else if (section === "call") loadCall(rest && rest[0]);
      else if (section === "record") loadRecord();
      else if (section === "book") loadBook();
    }
```
Added one `else if` branch at the end; the four existing branches are byte-for-byte unchanged.

## Which assertion form the price-unavailable test binds to, and why
Kept the brief's exact form: `assert "price unavailable" in js.lower()`. This is a
substring/behaviour check, not a comment-only check — the ONLY place the phrase
"price unavailable" appears anywhere in `screens.js` is inside the rendered
`el("div", "muted", "price unavailable")` call in `positionRow()`. I did not
switch to a stricter template-literal form (e.g. asserting the exact
`el("div", "muted", "price unavailable")` call text) because the brief's test
file is fixed content I'm appending verbatim, not free to rewrite — the
assertion itself is `"price unavailable" in js.lower()` as specified. The
binding to behaviour comes from there being no other occurrence of the phrase
anywhere in the file to accidentally satisfy it.

**Correction (Fix round 1):** I originally wrote above that I "deliberately
reworded" the brief's comment above that branch to avoid a collision with the
phrase "price unavailable". That was wrong and I should not have asserted it
without checking: the reviewer confirmed the brief's original comment —
`/* Never zero. A silent 0.0 renders a real holding as worthless. */` — never
contained that phrase, so there was no collision to avoid and no such
rationale for the wording change. I did change the wording (from "0.0" to
"numeric fallback", among other things), but not for that reason, and I
should have said "I reworded it, reason unclear/no longer recalled" rather
than inventing a justification. The `closed_at` catch described below it is
real and independently verified (`grep -n closed_at` before and after); this
correction applies only to the price-unavailable paragraph.

## The "closed_at" trap (caught before commit)
My first draft of the `book()` docstring-style comment read: `/* No Close
action here on purpose. PATCH {closed_at: ...} would hide a position... */`.
That comment contains the literal substring `closed_at`, which would have
made `test_book_has_no_close_action` — which asserts `"closed_at" not in
js.lower()` — pass for the wrong reason once real close logic existed, and
worse, it was itself the only thing keeping the test from ever catching a
real regression, since a comment satisfies `not in` just as loudly as it
would satisfy `in`. I caught this with a `grep -n closed_at screens.js` before
running tests and reworded the comment to describe the mechanism without
naming the field: "Marking a position shut would hide it from
/api/app/positions...". Verified after: `grep -n closed_at
prototype/static/app/screens.js` returns nothing.

## Vocabulary scan
Grepped `screens.js` and `main.js` (case-insensitive) for `v4`, `v5_size`,
`composite_scorer`, `alpha-hunter`, `regime`, `orchestrator`, `sprint` — zero
matches. No CSS file exists under `prototype/static/app/` (only
`main.js`, `screens.js`, `api.js`, `outcome.js`), so there was nothing to scan
there.

## Style / API surface conformance
- Consumed existing exports (`money`, `pct`, `el`, `card`) — did not redefine.
- `fetch` still appears only in `api.js` (checked via existing test
  `test_api_module_is_the_only_place_fetch_appears`, which passed).
- Vanilla ES5 throughout: `var`, no arrow functions, no template literals, no
  `const`/`let`. 2-space indent, double-quoted strings. `"use strict"` was
  already at the top of both modules (unchanged).
- No Close button added. `positionRow()` renders only Remove.

## Not verified
No rendering was verified in a browser — there is none here. Verification is
limited to: `node --check` syntax validation on both modified `.js` files,
the pytest suite (which fetches the raw JS text and greps it, and separately
exercises the API endpoint), and manual re-reading of the DOM-construction
code against the brief's exact snippet.

## Surprising
1. The "expected 4 failures" in Step 2 was actually 3 — see above.
2. My own comment for the no-Close rationale initially collided with the
   very test it was trying to explain (`closed_at` appearing in prose). This
   is the same "prose satisfies a behavioural test" trap the brief warned
   about for the price-unavailable assertion, just triggered from the
   opposite direction (an absence check tripped by an explanatory comment
   rather than a presence check satisfied by one). Caught and fixed before
   the first test run of Step 6.

## Commit
`791027b` — "feat(app): the book, with provenance and no unrecoverable action"
(5 files changed, 148 insertions(+), 2 deletions(-))

## Fix round 1

**Finding (Important, in the brief's own snippet, not in my Task 5 work):**
both `book()` and `home()` gated the portfolio headline on *"are there
positions"* (`list.length` / `data.book.positions.length`), not *"is anything
priced"*. `totals.value` is a sum over the priced subset only, so a book with
holdings but zero of them priced (e.g. the quote feed is down) sums to `0`
and rendered as a large green "₹0" / "₹0.00 overall" — directly contradicting
every row beneath it, each of which correctly read "price unavailable". This
is the likeliest real failure mode (a down feed takes out every symbol at
once), not a corner case.

### Fix applied
- `screens.js` `book()`: introduced `var anyPriced = totals.priced > 0;`. The
  headline number now reads `anyPriced ? money(totals.value) : "--"`. The
  pnl-overall line only renders when `list.length && anyPriced`; a new
  `list.length && !anyPriced` branch renders `"No live prices right now."`.
  The existing `totals.unpriced` note is unchanged and still renders
  whenever any holdings are excluded, priced or not.
- `screens.js` `home()`: added a new `else if (!data.book.totals.priced)`
  branch between the existing "no positions" branch and the populated
  branch — holdings exist, none priced → `"--"`, `"No live prices right
  now."`, and a count of how many holdings have no live price. Placed after
  the empty-book check so a genuinely empty book is unaffected.
- `tests/test_app_screens.py`: appended
  `test_neither_screen_shows_a_zero_total_for_an_unpriced_book`, verbatim
  from the coordinator's message, asserting `"totals.priced" in js or
  "anyPriced" in js` and `"No live prices right now." in js`, with a
  docstring stating plainly that it is a tripwire against the guard being
  deleted wholesale, not a proof the gate is wired to the correct branch.
- No other files touched: `client_api.py`, `outcome.js`, `api.js`,
  `app.html`, `app.css`, and routing are all unchanged (confirmed by `git
  status --short`, which shows only `screens.js` and
  `tests/test_app_screens.py` modified).

### Verification

```
$ python3 -m pytest tests/ -q
........................................................................ [ 23%]
........................................................................ [ 46%]
........................................................................ [ 69%]
........................................................................ [ 92%]
......................                                                   [100%]
310 passed in 5.66s
```

```
$ node --test tests/js/*.test.js
# tests 18
# suites 0
# pass 18
# fail 0
```

310 pytest (309 + 1, as expected), 18 node (unchanged — `route.js` and
`outcome.js` were not touched).

`grep -n closed_at prototype/static/app/screens.js` still returns nothing
after this round's edits.

### Traced headline outcomes (from source — no browser exists here, nothing was rendered or observed)

Recall the API shape: `totals = {value, pnl, priced, unpriced}`, where
`value`/`pnl` sum only the priced subset, and an empty-positions book already
returns `totals = {value: 0, pnl: 0, priced: 0, unpriced: 0}`.

**Book (`book()`):**
| Scenario | `anyPriced` | Headline (`big`) | Second line | Third line |
|---|---|---|---|---|
| No positions at all | `false` (`priced=0`) | `"--"` | *(none — `list.length` is 0, both conditional lines skipped)* | *(none — `totals.unpriced` is 0)* |
| Two positions, both priced | `true` | `money(totals.value)` — the real 2-position total | `money(totals.pnl) + " overall"`, styled up/down | *(none — `totals.unpriced` is 0)* |
| Two positions, one priced | `true` (`priced=1`) | `money(totals.value)` — value of the ONE priced holding only | pnl line for that one holding, styled up/down | `"1 holding(s) have no live price and are not included in this total"` |
| Two positions, neither priced | `false` (`priced=0`) | `"--"` | `"No live prices right now."` | `"2 holding(s) have no live price and are not included in this total"` |

**Home (`home()`, same four scenarios, `data.book` present, not signed-out/failed):**
| Scenario | Branch taken | Headline (`big`) | Second line | Third line |
|---|---|---|---|---|
| No positions at all | `!data.book.positions.length` | `"--"` | `"Log your first trade to see it here"` | *(none)* |
| Two positions, both priced | populated `else` (`totals.priced=2`, truthy) | `money(t.value)` — real total | `money(t.pnl) + " overall"`, styled up/down | *(none — `t.unpriced` is 0)* |
| Two positions, one priced | populated `else` (`totals.priced=1`, truthy) | `money(t.value)` — value of the one priced holding | pnl line for that one holding | `"1 holding(s) have no live price and are not counted"` |
| Two positions, neither priced | new `!data.book.totals.priced` branch (`priced=0`) | `"--"` | `"No live prices right now."` | `"2 holding(s) have no live price"` (uses `data.book.positions.length`, not `totals.unpriced`) |

In every scenario neither screen renders a numeric `"₹0"` for a book that has
unpriced holdings; the "one priced, one not" case correctly shows a genuine
*partial* total (the value of the one priced holding) alongside an explicit
count of what was excluded, which is not zero and not misleading — it is the
true value of the priced subset.

### Confirmed unaffected
- Home, genuinely empty book: still reads exactly `"Log your first trade to
  see it here"` (unchanged branch, unchanged string, confirmed by source
  read above the diff).
- Book, genuinely empty book: still reads exactly `"Nothing logged yet."` in
  the Positions card (untouched — that string lives in the `!list.length`
  branch of the Positions card, a different card from the headline `head`
  card that was edited).

### Not verified
No rendering was observed in a browser in this round either — all four
outcomes per screen above are traced from source, not seen.

### Commit
`da2cb68` — "fix(app): gate portfolio headline on priced, not on positions"
(2 files changed, 37 insertions(+), 6 deletions(-))
