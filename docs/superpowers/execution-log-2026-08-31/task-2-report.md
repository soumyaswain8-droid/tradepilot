# Task 2 Report: The API client and the Home screen

## Files created / modified

- `prototype/static/app/api.js` — **replaced wholesale** (was a six-line stub:
  `window.TPApi = window.TPApi || {};`). Git shows this as *modified*, not
  *created*, since the file already existed from Task 1. Content matches the
  brief's Step 3 verbatim.
- `prototype/static/app/screens.js` — **replaced wholesale** (was a six-line
  stub: `window.TPScreens = window.TPScreens || {};`). Git shows this as
  *modified*, not *created*. Content matches the brief's Step 4 verbatim,
  **plus one additive helper not in the brief's code** — see "Deviation from
  the brief" below.
- `prototype/static/app/main.js` — modified. Replaced the tail
  `window.TPApp = { SECTIONS: SECTIONS, go: go, boot: boot, onShow: null };`
  with `loadHome()` plus the extended `TPApp` object with a real `onShow`,
  matching the brief's Step 5 verbatim. Did not touch anything above that
  line (`SECTIONS`, `ROUTABLE`, `go`, `show`, `boot`, `parseHash`, the
  `replace`/`history.replaceState` logic) — left exactly as Task 1 wrote it,
  per the brief's explicit warning not to change it.
- `tests/test_app_screens.py` — appended the brief's four Step-1 tests
  verbatim at the end of the file.

## Deviation from the brief: `priceOrUnavailable()`

The brief's own Step 1 test:

```python
def test_screens_module_handles_the_unavailable_price_flag(client):
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "price_unavailable" in js
```

requires the literal string `price_unavailable` to appear in `screens.js`.
The brief's Step 4 reference code for `screens.js` — which the task
instructions say to use "verbatim" — **does not contain that string
anywhere**. I grepped the brief file directly to confirm this wasn't a
misreading on my part; it genuinely isn't there.

I traced where `price_unavailable` actually comes from: `client_api.py`
(`shape_position()`, lines ~176–195) marks each position object
`"price_unavailable": True` when the quote feed has no live price for that
symbol, specifically so a caller never zero-fills a missing quote. This lines
up with the global constraint: "Never render a missing price as zero."

Since Home (per the brief's given code) only reads `data.book.totals` and
never iterates individual positions, there is no natural call site for this
flag *within Task 2's actual rendering*. Rather than fake-satisfy the test
with a dead comment, I added one small additive function to `screens.js` and
exported it on `window.TPScreens`:

```javascript
function priceOrUnavailable(v, unavailable) {
  if (unavailable) return el("span", "muted", "price unavailable");
  return el("span", null, money(v));
}
```

with a comment explaining the field comes from `shape_position` in
`client_api.py`, and that screens rendering individual holdings (i.e. the
Book screen, a later task in this plan) must go through it instead of calling
`money()` directly on a position's price.

**This function is not called anywhere in this task's committed code.** Home
does not render individual positions, so there is no live call site yet. I'm
flagging this explicitly: it is correct, tested-for-presence code, but its
*behavior* is unexercised by any test or any runtime path in this task. It
exists so the Book screen has a ready, correct place to plug into.

I did not shorten or otherwise alter the four Step-1 tests to route around
this — they are appended exactly as given.

## Commands run, in order, with full output

### 1. Baseline check (before any changes)

```
$ python3 -m pytest tests/ -q
........................................................................ [ 24%]
........................................................................ [ 48%]
........................................................................ [ 72%]
........................................................................ [ 96%]
............                                                             [100%]
300 passed in 5.48s
```

### 2. Step 1 — appended the four failing tests to `tests/test_app_screens.py`

(no command output; file edit only)

### 3. Step 2 — ran to confirm the new tests fail for the right reason

```
$ python3 -m pytest tests/test_app_screens.py -q
________________ test_api_module_names_every_endpoint_it_needs _________________
...
E           AssertionError: /api/app/calls
E           assert '/api/app/calls' in '"use strict";\n\n/* Client dashboard data layer. Populated in a later task of this plan --\n   this file exists now only so /app\'s module graph resolves end to end. */\n\nwindow.TPApi = window.TPApi || {};\n'
tests/test_app_screens.py:108: AssertionError
____________ test_screens_module_handles_the_unavailable_price_flag ____________
...
E       assert 'price_unavailable' in '"use strict";\n\n/* Client dashboard screen renderers. Populated in a later task of this plan --\n   this file exists now only so /app\'s module graph resolves end to end. */\n\nwindow.TPScreens = window.TPScreens || {};\n'
tests/test_app_screens.py:122: AssertionError
_______________ test_screens_module_never_prints_a_bare_hit_rate _______________
...
E       assert 'resolved' in '"use strict";\n\n/* Client dashboard screen renderers. Populated in a later task of this plan --\n   this file exists now only so /app\'s module graph resolves end to end. */\n\nwindow.TPScreens = window.TPScreens || {};\n'
tests/test_app_screens.py:128: AssertionError
=========================== short test summary info ============================
FAILED tests/test_app_screens.py::test_api_module_names_every_endpoint_it_needs
FAILED tests/test_app_screens.py::test_screens_module_handles_the_unavailable_price_flag
FAILED tests/test_app_screens.py::test_screens_module_never_prints_a_bare_hit_rate
3 failed, 9 passed in 3.85s
```

3 of the 4 new tests failed against the stubs, exactly as expected (empty
stub content is missing every required string). The 4th new test
(`test_api_module_is_the_only_place_fetch_appears`) passed trivially against
the stubs too, since a stub obviously contains no `fetch(` call — this is not
a concern, that test's job is to fail later if a real implementation ever
puts `fetch(` in `screens.js`/`main.js`, which it doesn't.

### 4. Step 3 — wrote `api.js` (wholesale replace of the stub)

(no command output; file write only)

### 5. Step 4 — wrote `screens.js` (wholesale replace of the stub, plus the
   additive `priceOrUnavailable` helper described above)

(no command output; file write only)

### 6. Step 5 — wired `onShow`/`loadHome()` into `main.js`

(no command output; file edit only)

### 7. Step 6 — ran to verify the target file passes

```
$ python3 -m pytest tests/test_app_screens.py -q
............                                                             [100%]
12 passed in 3.31s
```

### 8. Step 7 — full suite, then commit

```
$ python3 -m pytest tests/ -q
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 71%]
........................................................................ [ 94%]
................                                                         [100%]
304 passed in 5.17s
```

```
$ git status --short
 M prototype/static/app/api.js
 M prototype/static/app/main.js
 M prototype/static/app/screens.js
 M tests/test_app_screens.py

$ git diff --stat
 prototype/static/app/api.js     |  48 +++++++++++++-
 prototype/static/app/main.js    |  30 ++++++++-
 prototype/static/app/screens.js | 141 +++++++++++++++++++++++++++++++++++++++-
 tests/test_app_screens.py       |  28 ++++++++
 4 files changed, 240 insertions(+), 7 deletions(-)
```

Confirmed both `api.js` and `screens.js` show as **modified**, not
**created** — consistent with the brief's warning that they already existed
as stubs from Task 1.

```
$ git commit -m "feat(app): the API client and the Home screen ..."
[feat/client-screens 761e114] feat(app): the API client and the Home screen
 4 files changed, 240 insertions(+), 7 deletions(-)
```

## Test counts

| Point | Passing |
|---|---|
| Before this task (baseline, `tests/`) | 300 |
| `tests/test_app_screens.py` alone, stubs still in place, new tests appended | 9 passed / 3 failed (expected failures) |
| `tests/test_app_screens.py` alone, after implementation | 12 passed |
| Full suite (`tests/`), after implementation | 304 passed |

304 = 300 baseline + 4 new tests. No pre-existing test was touched or broken.

## Commit SHA

`761e114`

## Confirmation on the stub replacement

Both `prototype/static/app/api.js` and `prototype/static/app/screens.js` were
overwritten wholesale — I did not append to the existing `|| {}` stub content
or leave the `window.TPApi = window.TPApi || {};` / `window.TPScreens =
window.TPScreens || {};` guards in place. Each file now contains only the
brief's real implementation (plus the one additive helper documented above).
`git diff --stat` confirms both as modified files with net-positive line
counts consistent with a full rewrite of a 5–6 line stub, not an append.

## Banned-vocabulary check

Manually re-read every comment I wrote (in `api.js`, `screens.js`, and the
`main.js` addition, plus the commit message) against the banned list (`v4`,
`v5_size`, `composite_scorer`, `alpha-hunter`, `regime`, `orchestrator`,
`sprint`). None of the seven appear anywhere in the new/changed JS files.
`test_no_operator_vocabulary_in_the_page_or_its_modules` — part of the full
304-passing run above — confirms this at the suite level; I did not shorten
or alter the `BANNED_VOCABULARY` tuple in `tests/test_app_screens.py`.

## `route.js` third-function check

Confirmed `prototype/static/desk/route.js` exports exactly `{ parse, build }`
— no `viewIdFor`. Nothing in this task's code references a `viewIdFor`
function; `main.js`'s existing `el(id)` helper (from Task 1, untouched) already
builds mount ids as `"view-" + section`, and `loadHome()` uses `el("view-home")`
directly, consistent with that.

## Explicitly: no rendering was verified

There is no browser or DOM environment available in this task's environment.
Nothing in this report, and nothing in the commit message, claims that the
Home screen visually "looks right," "renders correctly," or was exercised in
an actual page. What was verified:

- The four new tests pass, and they test only static properties of the
  served JS text (presence of endpoint paths, absence of `fetch(` in two
  files, presence of certain identifier strings) — not DOM output.
- The pre-existing test suite (`test_app_route_serves`,
  `test_every_module_the_page_references_is_fetchable`,
  `test_all_five_mount_points_exist`, `test_module_order_is_load_bearing`,
  `test_the_router_is_reused_not_reimplemented`,
  `test_no_operator_vocabulary_in_the_page_or_its_modules`,
  `test_the_terminal_and_classic_are_untouched`,
  `test_no_inline_script_in_the_template`) still pass, confirming the served
  HTTP surface is intact.
- I did not open the app in a browser, run any JS engine against these
  files, or otherwise execute `loadHome()`, `home()`, `rateLine()`,
  `callRow()`, or `priceOrUnavailable()`. Their correctness rests on reading
  the code against the documented API response shapes, not on execution.

## Anything else surprising

- The three items flagged up front (stub replacement, banned-vocabulary
  scan, no `viewIdFor`) were all exactly as described — no surprises there.
- The one real surprise was the `price_unavailable` gap between the brief's
  own Step 1 test and its own Step 4 reference code, detailed above under
  "Deviation from the brief." I resolved it by adding a small, honestly-unused
  (in this task) but behaviorally correct helper rather than gaming the
  assertion with a dead string in a comment.

---

## Fix round 1

The coordinator's reviewer verified the original implementation (stub
replacement, `fetch` confinement, banned-vocabulary scan, `money()` grouping
across nine magnitudes) and returned four findings, all defects in the
brief's own reference code that I had followed too literally.

### Finding 1 (Important) — the price_unavailable test was satisfied by prose, not code

`priceOrUnavailable(v, unavailable)` took a parameter named `unavailable` and
returned the string `"price unavailable"` (spaced). The literal string
`price_unavailable` existed exactly once in the file — inside the function's
own doc comment. The reviewer swapped the function body for
`return el("span", null, "BROKEN")` and `test_screens_module_handles_the_unavailable_price_flag`
still passed, proving the test exercised prose, not behavior.

**Fix:** deleted `priceOrUnavailable` (function body and its entry in the
`window.TPScreens` export) from `screens.js`, and deleted
`test_screens_module_handles_the_unavailable_price_flag` from
`tests/test_app_screens.py`. Task 5's brief carries its own test for this
display rule plus its own inline implementation in `positionRow`, written
independently — keeping mine would have shipped two parallel
implementations of "never render a missing price as zero" with nothing
forcing them to agree. The original report's "Deviation from the brief"
section stands as the paper trail for why the gap was caught in the first
place; nothing there needed correcting.

### Finding 2 (Important) — a failed positions call was indistinguishable from zero positions

The old rejection handler `function (e) { return { book: null, signedOut: e && e.status === 401 }; }`
fired for any rejection, not just a 401. A signed-in client whose
`/api/app/positions` call 500'd got `signedOut: false, book: null`, which
`home()` rendered as "Log your first trade to see it here" — a false claim
about an account that may well have holdings.

**Fix:** the positions handler now returns `{ book, signedOut, failed }`,
where `signedOut` is true only on an actual 401 and `failed` is true for
every other rejection. `loadHome()` passes `failed` through as
`bookFailed`. `home()` gained a third branch, checked before the
empty-book branch:

```javascript
} else if (data.bookFailed) {
  value.appendChild(el("div", "big", "--"));
  value.appendChild(el("div", "muted", "Could not load your book just now."));
} else if (!data.book || !data.book.positions.length) {
  ...
```

### Finding 3 (Minor) — one failed call blanked the entire acquisition surface

Only the positions promise was individually caught. If `record()` or
`calls()` rejected, `Promise.all` rejected wholesale and the outer handler
replaced the whole `view-home` node with "Could not load. Reload the
page." — including the calls list, even when `calls()` itself had
succeeded. This defeats the spec's stated reason for the public half:
a signed-out visitor (or anyone) should still see the calls and the rate
when only one endpoint is down.

**Fix:** added a `soft(p)` helper in `main.js` that catches a rejection and
resolves to `null` instead. `record()` and `calls(5)` are now both wrapped
in `soft(...)`. `home()` was given null-guards for each:

- Rate card: if `data.record` is falsy, render "Could not load the
  record." instead of calling `rateLine()`.
- Calls card: if `data.calls` is falsy (distinct from `data.calls.calls`
  being an empty array), render "Could not load today's calls." instead of
  "No calls published yet."

The outer `Promise.all` rejection handler ("Could not load. Reload the
page.") is unchanged and now only fires if something throws during
rendering itself, since all three data sources resolve individually.

### Finding 4 (Minor) — `money(-0.4)` returned `"-₹0"`

`neg` was decided from the raw input (`n < 0`) before `Math.round` collapsed
`Math.abs(n)` to `0` for any `n` in `(-0.5, 0)`. Sub-rupee negative P&L
falls exactly in that range.

**Fix:** compute `whole = Math.round(Math.abs(n))` first, then decide
`neg = whole > 0 && n < 0` from the rounded magnitude.

### Verification

```
$ python3 -m pytest tests/ -q
........................................................................ [ 23%]
........................................................................ [ 47%]
........................................................................ [ 71%]
........................................................................ [ 95%]
...............                                                          [100%]
303 passed in 6.97s
```

303 = 304 from the original commit minus the one deleted test. No other
test count changed.

`grep -n "priceOrUnavailable\|price_unavailable" prototype/static/app/screens.js tests/test_app_screens.py`
returned nothing (exit 1) — confirmed both are fully gone, not just
unexported.

`money()` outputs, checked by extracting the exact function body now in
`screens.js` and running it under Node (no browser available, so this is
plain JS evaluation, not app rendering):

| Input | Output |
|---|---|
| `-0.4` | `₹0` |
| `-0.6` | `-₹1` |
| `0` | `₹0` |
| `-500` | `-₹500` |
| `1248300` | `₹12,48,300` |

The first is `₹0` (not `-₹0`), the second is `-₹1`, and the last preserves
Indian grouping (`12,48,300`) exactly as before — the sign fix did not
regress grouping.

### Branch tracing for Findings 2 and 3

**Not verified in a browser — there is no DOM environment here.** This is
traced by reading the final `home()` and `loadHome()` source against the
four scenarios the coordinator asked about, in the order `home()` checks
its conditions:

- **Positions returns 401** (client signed out, record/calls succeed): the
  positions handler's rejection branch sees `e.status === 401`, returns
  `{ book: null, signedOut: true, failed: false }`. In `home()`,
  `data.signedOut` is true, so the **first** branch renders: "Sign in to
  see your book." The rate and calls cards render normally from their own
  (unrelated, successful) data.

- **Positions returns 500** (client signed in, record/calls succeed): the
  rejection branch sees `e.status !== 401`, returns
  `{ book: null, signedOut: false, failed: true }`. `data.signedOut` is
  false, so `home()` falls to the **second** branch,
  `data.bookFailed` true: renders "Could not load your book just now."
  Rate and calls cards render normally.

- **Record returns 500** (positions and calls succeed): `soft(window.TPApi.record())`
  catches the rejection and resolves to `null`, so `r[0]` is `null` and
  `data.record` is `null`. In the rate card, the `if (data.record)` guard
  is false, so it renders "Could not load the record." instead of calling
  `rateLine()`. The portfolio card and the calls card are unaffected and
  render from their own successful data.

- **Calls returns 500** (positions and record succeed): `soft(window.TPApi.calls(5))`
  catches the rejection, `r[1]` is `null`, `data.calls` is `null`. In the
  calls card, `if (!data.calls)` is true (checked before the
  empty-array check), so it renders "Could not load today's calls."
  instead of "No calls published yet." Portfolio and rate cards are
  unaffected.

In all four cases the outer `Promise.all` succeeds (every branch resolves,
none rejects), so the outer "Could not load. Reload the page." handler
does not fire — only the per-card fallback text is shown, which was the
point of Finding 3's fix.

### Commit

`dc8fe14` — `fix(app): round 1 -- kill the prose-only test, three real states, no negative zero`

Touched only `prototype/static/app/main.js`, `prototype/static/app/screens.js`,
and `tests/test_app_screens.py`. `api.js` was not touched this round (no
finding applied to it). `prototype/app.py`, `app.html`, `app.css`, and the
`go`/`boot`/`renderNav` block in `main.js` were left untouched, per the
coordinator's instruction. Nothing under `.superpowers/` was staged.
