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

Start the app, seed it with the data below, open `http://localhost:5050/app`,
and work down.

## Seeding the data

Most of these checks are unreachable on a fresh install. Reading "the hit
rate never appears without its sample size" off an empty database proves
nothing -- there is nothing to be wrong yet. The specific states below need
specific rows: all five call outcomes side by side, one call whose outcome
value the renderer does not recognise, and one position with no live quote.

This writes to `prototype/tradepilot_app.db`, which is gitignored -- it is
never committed, and there is nothing to revert in git. Run this after the
app has created the database once (so the tables exist):

```python
import sqlite3, datetime

con = sqlite3.connect("prototype/tradepilot_app.db")
cur = con.cursor()
now = datetime.datetime.utcnow()
iso = lambda dt: dt.strftime("%Y-%m-%dT%H:%M:%S")

calls = [
    # id, symbol, side, published_at, price_at_call, score, signal, horizon,
    # target, stop, outcome_price, outcome_at, outcome
    ("c-hit1", "TCS", "BUY", iso(now - datetime.timedelta(days=1)), 3800.0,
     82, "momentum breakout", "1w", 3900.0, 3750.0, 3950.0, iso(now), "hit"),
    ("c-miss1", "INFY", "BUY", iso(now - datetime.timedelta(days=2)), 1500.0,
     65, "trend reversal", "1w", 1550.0, 1470.0, 1460.0, iso(now), "miss"),
    ("c-open1", "RELIANCE", "BUY", iso(now - datetime.timedelta(hours=3)),
     2900.0, 71, "volume surge", "3d", 3000.0, 2850.0, None, None, "open"),
    ("c-ungraded1", "CIPLA", "SELL", iso(now - datetime.timedelta(hours=1)),
     1400.0, 58, "sector weakness, no clear target", "2d", None, None,
     None, None, "ungraded"),
    # An outcome value the renderer does not recognise. This is what makes
    # the "Not accounted for" row in Track record appear -- see below.
    ("c-weird1", "HDFCBANK", "BUY", iso(now - datetime.timedelta(days=3)),
     1600.0, 60, "test of unrecognised outcome", "1w", 1650.0, 1570.0,
     None, None, "expired"),
]
for c in calls:
    cur.execute("""INSERT OR REPLACE INTO calls
        (id, symbol, side, published_at, price_at_call, score, signal, horizon,
         target, stop, outcome_price, outcome_at, outcome)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", c)

positions = [
    # id, user_id, symbol, qty, avg_price, opened_at, closed_at, exit_price,
    # source, broker_ref, call_id
    ("p-priced1", "demo-user", "TCS", 10, 3800.0,
     iso(now - datetime.timedelta(days=1)), None, None, "call", None, "c-hit1"),
    # A symbol with no live quote -- exercises "price unavailable".
    ("p-unpriced1", "demo-user", "ZZZNOPRICE", 5, 500.0,
     iso(now - datetime.timedelta(hours=2)), None, None, "manual", None, None),
]
for p in positions:
    cur.execute("""INSERT OR REPLACE INTO positions
        (id, user_id, symbol, qty, avg_price, opened_at, closed_at, exit_price,
         source, broker_ref, call_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""", p)
con.commit()
```

To see the singular-footer quirk in Track record (below), you additionally
need **exactly one** resolved call -- temporarily flip `c-miss1`'s outcome
back to `"open"`:
```python
cur.execute("UPDATE calls SET outcome='open', outcome_price=NULL, "
            "outcome_at=NULL WHERE id='c-miss1'")
con.commit()
```
and restore it (`outcome='miss', outcome_price=1460.0,
outcome_at='2026-08-29T00:00:00'`) once that check is done.

**Clear the seed afterwards** so it doesn't linger in a database you may
share with other manual testing:
```python
cur.execute("DELETE FROM calls WHERE id IN "
            "('c-hit1','c-miss1','c-open1','c-ungraded1','c-weird1')")
cur.execute("DELETE FROM positions WHERE id IN "
            "('p-priced1','p-unpriced1')")
con.commit()
```

## Home

Home has five distinct states. Every one needs to be seen at least once, not
inferred from the others -- each is its own branch in `screens.js` and a bug
in one does not show up while checking another.

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | Home loads with no console errors, and shows the hit rate and today's calls |
| ☐ | Signed out: portfolio card reads "Sign in to see your book" -- calls and hit rate still show (see signed-out section below) |
| ☐ | Book endpoint failing (a 500, not a 401): portfolio card reads "Could not load your book just now." and does **not** say "Log your first trade" (see book-load-failure section below for how to force this) |
| ☐ | Zero positions: portfolio card reads "Log your first trade to see it here", not ₹0 |
| ☐ | Positions exist but none are priced: shows "--" and "No live prices right now.", never ₹0 |
| ☐ | Positions exist and are priced: shows the real value and P&L, coloured up/down correctly |
| ☐ | The hit rate never appears without its sample size beside it |
| ☐ | If `/api/app/record` fails, the rate card reads "Could not load the record." and the calls list still renders |
| ☐ | If `/api/app/calls` fails, the calls card says so and the rate still renders |

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
| ☐ | With no calls published, the list reads "No calls published yet." |
| ☐ | If the fetch fails, it reads "Could not load calls. Reload the page." |
| ☐ | A resolved call shows "Hit"/"Missed" with its exit price and percentage move |

:::

## Track record

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | The label reads "Recording since ...", never a bare "Since ..." |
| ☐ | The hit rate never appears without its sample size beside it |
| ☐ | With fewer than 100 resolved calls, the page says so explicitly ("Too few to be meaningful...") |
| ☐ | Ungraded calls are shown in the breakdown and explained, not hidden |
| ☐ | With a call whose `outcome` is an unrecognised value, a "Not accounted for" row appears in "How the calls stand" with the right count |
| ☐ | With all outcomes recognised, that row is absent entirely |
| ☐ | On an empty record the since-line reads "Nothing recorded yet.", never "Recording since null" |
| ☐ | With nothing resolved, "Resolved calls" reads "Nothing has resolved yet." |
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
| ☐ | With no positions logged, the list reads "Nothing logged yet." |
| ☐ | A server-rejected add (e.g. a symbol of only spaces) shows "That could not be added. Check the values and try again." -- a different message from the client-side validation error |

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

## Checking the book-load-failure state

`/api/app/positions` has no natural way to return a 500 -- there is no code
path in this codebase that fails it that way on demand. To see the
`bookFailed` branch on Home (distinct from the zero-positions and
signed-out branches, and the only one of Home's five states that needs a
code edit rather than seed data or a stub flip):

1. Open `prototype/client_api.py` and add one line at the top of
   `positions_list()`, directly after its docstring:
   ```python
   def positions_list():
       """The signed-in user's open book, marked to market."""
       raise RuntimeError("TEMP: manual-check forced failure")
       user = client_auth.current_user()
       ...
   ```
2. Restart the app and reload `/app`. The portfolio card should read
   "Could not load your book just now." -- not "Log your first trade".
3. **Revert the edit before doing anything else.** Remove the `raise` line
   and restart the app. Leaving it in place breaks every other Book and
   Home check in this file, and `positions_list` backs three other gated
   endpoints' worth of manual testing besides.

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
