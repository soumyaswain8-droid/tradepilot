# /app -- manual checks

None of the client dashboard's rendering is covered by an automated test.
There is no DOM in the test environment, and adding one would breach the
no-new-dependencies constraint this codebase holds. The pytest suite in
`tests/test_app_screens.py` proves the route serves, every module it
references is actually fetchable, and no operator vocabulary reaches the
page. The one piece of screen logic that does sit behind a testable module
boundary is outcome wording -- `prototype/static/app/outcome.js` -- and it
is covered node-side by `tests/js/outcome.test.js`. Everything else below is
checked by hand, against this file, because it is the only backstop that
exists for it.

Run this after any change under `prototype/static/app/`, `prototype/static/app.css`
or `prototype/templates/app.html`.

Start the app, open `http://localhost:5050/app`, and work down.

## Home

Home has five distinct states. Every one needs to be seen at least once, not
inferred from the others -- each is its own branch in `screens.js` and a bug
in one does not show up while checking another.

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | Home loads with no console errors, and shows the hit rate and today's calls |
| ☐ | Signed out: portfolio card reads "Sign in to see your book" -- calls and hit rate still show (see signed-out section below) |
| ☐ | Book endpoint failing (a 500, not a 401): portfolio card reads "Could not load your book just now." and does **not** say "Log your first trade" |
| ☐ | Zero positions: portfolio card reads "Log your first trade to see it here", not ₹0 |
| ☐ | Positions exist but none are priced: shows "--" and "No live prices right now.", never ₹0 |
| ☐ | Positions exist and are priced: shows the real value and P&L, coloured up/down correctly |
| ☐ | The hit rate never appears without its sample size beside it |

:::

## Calls and call detail

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | The calls list carries an "As of ..." stamp |
| ☐ | Tapping a call opens its detail; "Back to calls" returns to the list, not to the previous site |
| ☐ | An `open` call reads "Still open -- no outcome yet." and never implies a result |
| ☐ | An `ungraded` call says it was published without a target and is not counted |
| ☐ | A call with an unrecognised outcome reads "Outcome not recorded." with no price appended |
| ☐ | An unknown call id (bad hash, e.g. `#call/does-not-exist`) shows "That call could not be found." with a working "Back to calls" |

:::

## Track record

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | The label reads "Recording since ...", never a bare "Since ..." |
| ☐ | The hit rate never appears without its sample size beside it |
| ☐ | With fewer than 100 resolved calls, the page says so explicitly ("Too few to be meaningful...") |
| ☐ | Ungraded calls are shown in the breakdown and explained, not hidden |
| ☐ | The "Resolved calls" footer states how many of how many are shown |
| ☐ | **Known, unfixed** -- judge in the browser: with exactly one resolved call, the footer reads "All 1 resolved calls." (no singular case). Confirm this is still the behaviour, not a regression into something worse |
| ☐ | **Known, unfixed** -- judge in the browser: viewing a call's detail page highlights no nav entry, because `call` deliberately has no nav slot. Confirm the nav does not show a stale/wrong section highlighted instead of none |

:::

## Book

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | Each position says "from a TradePilot call" or "your own idea" |
| ☐ | A position with no live price reads "price unavailable" and shows its cost basis (qty @ avg price), never ₹0 |
| ☐ | The portfolio total names how many holdings it excluded when some are unpriced |
| ☐ | There is no Close button anywhere on a position row -- only Remove |
| ☐ | Remove asks for confirmation first, naming the symbol, before anything happens |
| ☐ | Adding a position with a bad quantity (zero, negative, blank) shows an inline error, and does not crash or appear to succeed |
| ☐ | A failed Remove (e.g. network cut mid-request) leaves the position visible and says it could not be removed |

:::

## Shell and responsiveness

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | Narrow the window below 900px: the sidebar disappears and a bottom tab bar appears |
| ☐ | The bottom tab bar does not overlap the last row of content on any screen (scroll to the bottom of Book and Record and check) |
| ☐ | Widen past 900px: the sidebar returns, the tab bar disappears, and the KPI cards go two-up |
| ☐ | Pressing Back once from a freshly loaded `/app` leaves the app entirely -- it does not trap on a hash |
| ☐ | `/` still serves the terminal, unchanged |
| ☐ | `/classic` still serves the old dashboard, unchanged |
| ☐ | No console errors on any of the five screens |

:::

## Checking the signed-out states

`current_user()` in `prototype/client_auth.py` is a stub that always returns
a fixed user id, so a browser cannot reach the signed-out states through
normal use -- there is nothing to sign out of yet. To check them:

1. Open `prototype/client_auth.py` and change:
   ```python
   def current_user():
       return "demo-user"
   ```
   to:
   ```python
   def current_user():
       return None
   ```
2. Restart the app and reload `/app`.
3. Walk this table:

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | Home still shows the calls and the hit rate -- the acquisition surface works even signed out |
| ☐ | Home's portfolio card reads "Sign in to see your book" |
| ☐ | Book reads "Sign in to see your book." rather than erroring or showing a stale book |
| ☐ | Calls and Track record are fully usable, unaffected by sign-out state |

:::

4. **Revert the edit before doing anything else.** Change
   `client_auth.py` back to `return "demo-user"` and restart the app. Do not
   commit the stub in its signed-out form -- it gates five endpoints
   (`client_api.me`, `client_api.positions_list`, `client_api.position_create`,
   `client_api.position_update`, `client_api.position_delete`) and leaving it
   returning `None` breaks all of them for every other check in this file.
