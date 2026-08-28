# Final Fix Wave Report — terminal-agent-floor

Branch: `feat/terminal-agent-floor`
Worktree: `/Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/terminal-agent-floor`
Date: 2026-08-28

## Scope

Applied all seven fixes from the final whole-branch review in one pass:

1. Added `test_all_terminal_modules_are_actually_served` to `tests/test_web_routes.py` — fetches `route.js`, `router.js`, `panes.js`, `desk.js` and asserts 200 + non-empty body for each, instead of grepping for `src=` substrings.
2. Added the async-failure caveat to the lifecycle-contract comment block in `prototype/static/desk/router.js` (inserted after the `unmount()` line, before "Every hook is wrapped.").
3. Seeded `views[viewId]._last = Date.now()` at the same moment `mounted[viewId] = true` is set in `router.js`'s `show()`, so the first 5s lifecycle tick does not immediately re-fire `refresh()`.
4. Reordered `desk.js`'s `DOMContentLoaded` handler: the `loadIndices` `setInterval` (60000ms, unchanged body/cadence) now runs before `window.TPRouter.boot()`, with the explanatory comment about shell furniture vs. a broken deploy.
5. Added the "Register BEFORE boot()" comment directly above `function register(` in `router.js`.
6. Corrected the factual error in `panes.js`'s header comment: verified real poll cadences (see below) and replaced the "poll once a second... ~3,600 requests an hour" claim with the actual numbers. The unmount-clears-src rationale is unchanged.
7. Created `docs/TERMINAL_MANUAL_CHECKS.md` — permanent checklist doc with the no-automated-coverage rationale, a `☐`-based checklist table of the seven manual checks, and an instruction to run it after any change under `prototype/static/desk/`.

## Real poll cadences found (Fix 6)

- `prototype/templates/team.html:120` — `const POLL_MS = 5000;`, driven by `setInterval(tick, POLL_MS)` at line 250 → **every 5s, ~720 requests/hour**.
- `prototype/templates/floor.html:330` — `setTimeout(poll, 2000)` inside the `poll()` function itself (recursive self-scheduling poll loop), first call at line 332 → **every 2s, ~1,800 requests/hour**.
- Combined: **~2,520 requests/hour**, not "once a second" / "~3,600 requests an hour" as the original comment claimed.

## Commands run and full output

### 1. Python test suite

```
$ cd /Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/terminal-agent-floor
$ python3 -m pytest tests/ -q
........................................................................ [ 39%]
........................................................................ [ 78%]
........................................                                 [100%]
184 passed in 3.65s
```

Expected 184 (183 + Fix 1's new test). Confirmed.

### 2. Node test suite

```
$ node --test tests/js/*.test.js
...
# tests 12
# suites 0
# pass 12
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 70.177625
```

12/12, unchanged from before the fix wave.

### 3. Diff self-check

```
$ git status --short
 M prototype/static/desk.js
 M prototype/static/desk/panes.js
 M prototype/static/desk/router.js
 M tests/test_web_routes.py
?? docs/TERMINAL_MANUAL_CHECKS.md
?? prototype/data/kite_cache/instruments_nse_2026-08-28.json   (pre-existing untracked cache file, unrelated to this task, left alone)
```

`git diff --stat`:
```
 prototype/static/desk.js        |  6 ++++--
 prototype/static/desk/panes.js  |  8 +++++---
 prototype/static/desk/router.js | 16 +++++++++++++++-
 tests/test_web_routes.py        | 16 ++++++++++++++++
 4 files changed, 40 insertions(+), 6 deletions(-)
```

Confirmed `prototype/static/desk/route.js` and `tests/js/route.test.js` were NOT touched (not in the diff, not in git status).

Full diff reviewed inline (see git log for the exact patch); manually verified all seven fixes are present:
- Fix 1: new test appended to `tests/test_web_routes.py` ✓
- Fix 2: async-failure caveat present in `router.js` lifecycle comment ✓
- Fix 3: `_last` seeding present in `router.js` `show()` ✓
- Fix 4: `desk.js` interval moved before `boot()` ✓
- Fix 5: register-before-boot comment present above `function register(` ✓
- Fix 6: `panes.js` header comment corrected with real cadences ✓
- Fix 7: `docs/TERMINAL_MANUAL_CHECKS.md` created ✓

### 4. Server verification (port 5051, NOT the user's 5050)

Started the Flask app object directly (without touching `prototype/app.py`'s hardcoded `port=5050` in its `__main__` block) via:

```
$ cd prototype
$ nohup python3 -c "
import app as app_module
app_module.app.run(host='127.0.0.1', port=5051, debug=False, threaded=True)
" > /tmp/tp-verify-5051.log 2>&1 &
PID=29440
```

Startup log:
```
[ENGINE] v2 ensemble loaded (XGBoost + LightGBM)
[ENGINE] v3 regime-aware engine loaded
[ENGINE] v4 composite scorer loaded
 * Serving Flask app 'app'
 * Debug mode: off
WARNING: This is a development server. Do not use it in a production deployment. Use a production WSGI server instead.
 * Running on http://127.0.0.1:5051
Press CTRL+C to quit
```

Curl checks:
```
/static/desk/route.js -> HTTP 200, 1592 bytes
/static/desk/router.js -> HTTP 200, 7130 bytes
/static/desk/panes.js -> HTTP 200, 1484 bytes
/static/desk.js -> HTTP 200, 23364 bytes
```

All four 200, all non-empty.

Killed the verification server:
```
$ kill 29440
```
Confirmed 5051 no longer responding (curl returned empty/000 after kill) and port 5050 (the user's own server, PID 20862) was never touched — still listed via `lsof -i :5050` as LISTEN, untouched by this session.

## Checks requiring a browser (NOT verified by this session)

`docs/TERMINAL_MANUAL_CHECKS.md` was created but its checklist items were NOT executed — none of the seven manual checks were run in an actual browser this session:

1. `/` opens on Desk with no sub-tab bar visible — NOT verified (browser required)
2. Agent Floor shows two sub-tabs and both panes load, no duplicate header/nav pill in frame — NOT verified (browser required)
3. Leaving Agent Floor stops `api/floor/live` / `api/team/status` traffic (DevTools Network); returning resumes it — NOT verified (browser + DevTools required)
4. `#market/TITAN/5y` opens the TITAN drawer at 5y range — NOT verified (browser required)
5. `#agents/floor` deep-links straight to Live Floor — NOT verified (browser required)
6. Back button once from a freshly loaded `/` leaves the terminal, does not trap on `#desk` — NOT verified (browser required)
7. `/team` and `/floor` standalone with own chrome, no console errors across two poll cycles — NOT verified (browser + console required)

Only the automated pytest/node suites and the raw HTTP module-serving check (curl, not a browser) were run. The `docs/TERMINAL_MANUAL_CHECKS.md` checklist remains open for a human (or a future browser-tooled agent) to execute.

## Commit

All changes (excluding `.superpowers/`, which is gitignored) committed as one commit. See git log for SHA.
