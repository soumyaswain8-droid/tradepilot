### Task 6: The manual checklist

Nothing in this plan verifies rendering. This task writes down what must be checked by hand, in a tracked file, so the gap is visible rather than assumed.

**Files:**
- Create: `docs/APP_MANUAL_CHECKS.md`
- Modify: `tests/test_app_screens.py`

- [ ] **Step 1: Write the failing test**

```python
def test_the_manual_checklist_exists_and_is_tracked(client):
    """The rendering is unverifiable here; the checklist is the backstop.

    A backstop nobody can find is not a backstop, so its existence is pinned
    by a test rather than left to memory.
    """
    path = os.path.join(REPO_ROOT, "docs", "APP_MANUAL_CHECKS.md")
    assert os.path.exists(path)
    body = open(path, encoding="utf-8").read()
    assert "☐" in body
    assert "/app" in body
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: 1 failure — the file does not exist.

- [ ] **Step 3: Write the checklist**

Create `docs/APP_MANUAL_CHECKS.md`:

```markdown
# /app — manual checks

None of the client dashboard's rendering is covered by an automated test.
There is no DOM in the test environment, and adding one would breach the
no-new-dependencies constraint this codebase holds. The pytest suite proves
the route serves, every module is fetchable, and no operator vocabulary
reaches the page. Everything below is checked by hand.

Run this after any change under `prototype/static/app/`, `prototype/static/app.css`
or `prototype/templates/app.html`.

Start the app, open `http://localhost:5050/app`, and work down.

| | Check |
|:---:|:--|
| ☐ | Home loads with no console errors, and shows the hit rate and today's calls |
| ☐ | With no positions logged, the portfolio card reads "Log your first trade", not ₹0 |
| ☐ | The hit rate never appears without its sample size beside it |
| ☐ | With fewer than 100 resolved calls, the page says so explicitly |
| ☐ | Tapping a call opens its detail; Back to calls returns |
| ☐ | An open call says "Still open", never implying an outcome |
| ☐ | Track record says "Recording since", not "Since" |
| ☐ | Ungraded calls are shown and explained, not hidden |
| ☐ | Book: adding a position with a bad quantity shows an error, not a crash |
| ☐ | Book: a position with no live price reads "price unavailable", never ₹0 |
| ☐ | Book: each position says "from a TradePilot call" or "your own idea" |
| ☐ | Book: there is no Close button — only Remove, and it confirms first |
| ☐ | Narrow the window below 900px: the sidebar is replaced by a bottom tab bar |
| ☐ | Widen past 900px: the sidebar returns and the KPI cards go two-up |
| ☐ | Pressing Back once from a freshly loaded `/app` leaves the app |
| ☐ | `/` still serves the terminal and `/classic` still serves the old dashboard |

## Checking the signed-out states

`current_user()` is a stub that always returns a user, so the browser cannot
reach the signed-out states normally. To check them, edit
`prototype/client_auth.py` to `return None`, reload, and confirm:

| | Check |
|:---:|:--|
| ☐ | Home still shows the calls and the hit rate — the acquisition surface works |
| ☐ | Home's portfolio card reads "Sign in to see your book" |
| ☐ | Book reads "Sign in to see your book" rather than erroring |
| ☐ | Calls and Track record are fully usable |

**Revert that edit afterwards.**
```

- [ ] **Step 4: Run to verify it passes, then commit**

```bash
python3 -m pytest tests/ -q
git add docs/APP_MANUAL_CHECKS.md tests/test_app_screens.py
git commit -m "docs(app): the checks a green suite does not make

Nothing in this plan verifies rendering -- no DOM, and jsdom would breach the
no-new-dependencies constraint. This is the backstop, and its existence is
pinned by a test so it cannot quietly rot.

It includes the signed-out states, which the browser cannot reach while
current_user() is a stub, along with the two-line edit that exposes them."
```

---

## Verification

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/ -q
```

Expected: **312 passing** (292 existing + 20 new: 8 + 4 + 2 + 1 + 4 + 1).

The plan is complete when all of the following also hold:

| | Check |
|:---:|:--|
| ☐ | `curl localhost:5050/app` returns 200 |
| ☐ | All four modules and the stylesheet return 200 when fetched directly |
| ☐ | `docs/APP_MANUAL_CHECKS.md` exists and every box has been walked at least once |
| ☐ | `/` and `/classic` still serve, unchanged |
| ☐ | No response from `/app` contains `v4`, `composite_scorer`, or `regime` |
| ☐ | `git diff prototype/app.py` shows one route added and nothing else |

## Not in this plan

**`/classic` is not redirected.** The spec says it redirects to `/app` once the
five screens are complete. Redirecting a working page to one that has never been
opened in a browser is a decision for after the manual checklist has been walked,
not a step inside the plan that builds it.

**No closed-positions view.** Recorded in the spec's Deferred section. Until it
exists the Book has no Close button, so nothing accumulates rows nobody can see.

**Accounts remain deferred.** `current_user()` still returns a fixed id. The
signed-out states are built and checkable, but not reachable in a browser without
a two-line edit.
