# Task 4 Report — Router and lifecycle registry

Worktree: `/Users/soumyaswain/Documents/tinker/projects/tradepilot/.worktrees/terminal-agent-floor`
Branch: `feat/terminal-agent-floor`
Commit: `3425910c16d03ca737a5bd4303d4ff28c3fee77f`

## Rulings applied

- **Ruling 1** — added only three `<script src>` tags in `desk.html` (`route.js`,
  `router.js`, `desk.js`). Did NOT add a `panes.js` tag. Verified by curl that
  `/static/desk/panes.js` 404s and that it is not referenced anywhere in the
  served `/` markup.
- **Ruling 2** — replaced the brief's `test_terminal_declares_three_sections`
  (which asserts `data-section="desk"` in `GET /`, impossible since the nav is
  JS-rendered and the Flask test client executes no JS) with
  `test_router_declares_three_sections`, which fetches `/static/desk/router.js`
  and asserts the three section ids appear in the real served module.
  `test_terminal_loads_router_modules` asserts only `route.js`, `router.js`,
  `desk.js` (no `panes.js`), as instructed.

## Files changed

### `prototype/static/desk/router.js` (new, 147 lines)
Created verbatim from the brief's Step 3: `TPRouter` IIFE exposing
`SECTIONS`, `register(viewId, hooks)`, `go(section, sub, rest)`, `current()`,
`boot()`. Section registry: `desk` (flat), `market` (flat), `agents` (subs:
`quant` "Quant Desk", `floor` "Live Floor"). Every hook call is wrapped in
`guard()` — a thrown `mount` degrades that view's DOM to an error card and
never touches the nav or a sibling view. One 5s timer drives every
registered view's `refresh`, gated by `document.hidden`, visibility
(`.on` class), and each view's own `pollMs`.

### `prototype/templates/desk.html`
1. `<head>`: replaced the single `desk.js` script tag with three
   (`route.js`, `router.js`, `desk.js`, in that order, all `defer`, all
   `src`-only). Kept the existing "JS is a separate file BY RULE" comment
   above them, unmodified.
2. Replaced the hand-written `<nav class="nav">...</nav>` block (which held
   `data-tab="desk"`, `data-tab="market"`, and external links to `/decisions`
   and `/classic`) with an empty `<nav class="nav"></nav>` plus
   `<div class="subnav" id="subnav" style="display:none"></div>`, exactly as
   the brief specifies, plus the brief's "do not hand-edit links" comment.
   **Note:** the `/decisions` and `/classic` external nav links are gone from
   the terminal nav — the registry (`SECTIONS` in router.js) only declares
   `desk`, `market`, `agents`. This is the brief's literal Step 4 content; I
   did not add those links back since neither the brief nor the two rulings
   call for preserving them, and `SECTIONS` has no provision for external
   (non-hash) nav links. Flagging this as a surprise, see below.
3. Added the two Agent Floor pane `<section>` elements
   (`view-agents-quant` / `view-agents-floor`, each with an empty-`src`
   `<iframe>`) inside `<main>`, immediately after the Market section, exactly
   as written in the brief.

### `prototype/static/desk.css` (appended)
Added the `.subnav` sub-tab bar styles and `.view.pane.on` / `.paneframe`
iframe styles from the brief's Step 5, verbatim, after the existing
`.rstats b` rule (end of file).

### `prototype/static/desk.js`
**Removed:**
- The entire `switchTab(name)` function (the `/* ── tabs ── */` comment
  through its closing brace, 10 lines) — nav switching and view-class
  toggling now belong to `router.js`'s `show()`.
- The deep-link parsing block at the top of the boot handler (`var h = ...`
  through the `if (h[0] === "market") { ... }` block) — deep-link resolution
  (`#market/TITAN/5y`) is now handled inside the `market` view's `mount`
  hook via `window.TPRouter.current().rest`.
- The `.nav a[data-tab]` click-binding `forEach` loop — the router now owns
  nav rendering and click handling entirely (`renderNav()` in router.js).
- The two `setInterval` polling blocks at the end of the boot handler: the
  30000ms `loadDesk()` interval, and the 60000ms interval that combined
  `loadIndices()` with a conditional `loadMarket()`.
- The bare `loadDesk();` call that used to run immediately on
  `DOMContentLoaded` (was `loadIndices(); loadDesk();`) — desk data is now
  loaded once via the router's `mount` hook on the desk view (which fires
  during `TPRouter.boot()`, the default section). Keeping the old bare call
  would have double-fetched `/api/desk` on every page load. The brief only
  said to "keep `loadIndices()` and `tickClock()` where they are," not
  `loadDesk()`, so this follows that instruction precisely.

**Added** (replacing what was removed, in the boot handler, in lexical scope
inside the same `DOMContentLoaded` closure so `loadDesk`, `loadMarket`,
`openDrawer`, `RANGES`, `curRange` remain accessible):
```js
window.TPRouter.register("desk", {
  mount: loadDesk,
  refresh: loadDesk,
  pollMs: 30000
});
window.TPRouter.register("market", {
  mount: function () {
    loadMarket();
    var r = window.TPRouter.current().rest;
    if (r[0]) {
      if (r[1] && RANGES.indexOf(r[1].toLowerCase()) !== -1) curRange = r[1].toLowerCase();
      openDrawer(r[0].toUpperCase());
    }
  },
  refresh: loadMarket,
  pollMs: 60000
});
window.TPRouter.boot();

setInterval(function () {
  if (document.hidden) return;
  loadIndices();
}, 60000);
```
This is the brief's Step 6 snippet verbatim, plus the single-purpose
`loadIndices()` interval (market call stripped out, since the router now
drives market refresh via its own `pollMs`).

**Unchanged and preserved:** `tickClock()` + its 1s `setInterval`,
`loadIndices()`'s initial call at the top of the boot handler, all other
event bindings (`overlay`, `dClose`, `dModeCandle`/`dModeLine`,
`Escape` keydown, `mktSearch` input, `.fpill` click loop).

### `tests/test_web_routes.py`
Appended three tests (`test_router_declares_three_sections` per Ruling 2,
`test_terminal_has_subtab_bar`, `test_terminal_loads_router_modules` per
Ruling 1) after the existing seven. No existing test modified.

## Commands run, with output

### Baseline (before any edits)
```
$ python3 -m pytest tests/ -q
........................................................................ [ 40%]
........................................................................ [ 81%]
................................                                         [100%]
176 passed in 3.51s

$ node --test tests/js/*.test.js
...
1..12
# tests 12
# pass 12
# fail 0
```

### After implementation
```
$ python3 -m pytest tests/test_web_routes.py -v
tests/test_web_routes.py::test_terminal_renders PASSED                   [ 10%]
tests/test_web_routes.py::test_floor_renders PASSED                      [ 20%]
tests/test_web_routes.py::test_team_renders PASSED                       [ 30%]
tests/test_web_routes.py::test_floor_embed_hides_brand PASSED            [ 40%]
tests/test_web_routes.py::test_floor_without_embed_keeps_brand PASSED    [ 50%]
tests/test_web_routes.py::test_team_embed_hides_header_and_pageswitch PASSED [ 60%]
tests/test_web_routes.py::test_team_without_embed_keeps_header PASSED    [ 70%]
tests/test_web_routes.py::test_router_declares_three_sections PASSED     [ 80%]
tests/test_web_routes.py::test_terminal_has_subtab_bar PASSED            [ 90%]
tests/test_web_routes.py::test_terminal_loads_router_modules PASSED      [100%]
============================== 10 passed in 3.41s ==============================

$ python3 -m pytest tests/ -q
........................................................................ [ 40%]
........................................................................ [ 80%]
...................................                                      [100%]
179 passed in 3.27s

$ node --test tests/js/*.test.js
...
1..12
# tests 12
# pass 12
# fail 0
# cancelled 0
# skipped 0
# todo 0
```

**Test counts: pytest 176 → 179 (+3, as expected). Node 12 → 12 (unchanged, as
expected — route.js/route.test.js untouched).**

### Syntax check on new/modified JS
```
$ node --check prototype/static/desk/router.js && echo "router.js OK"
router.js OK
$ node --check prototype/static/desk.js && echo "desk.js OK"
desk.js OK
```

### Browser verification via curl (server started in background, killed after)

Started: `python3 prototype/app.py` in background, logged to `/tmp/tp-app4.log`.

```
$ curl -sS -o /dev/null -w "GET / -> %{http_code}\n" http://localhost:5050/
GET / -> 200
```

Served `/` markup — nav/subnav/pane elements and script tags:
```
7:<link rel="stylesheet" href="/static/desk.css">
11:<script src="/static/desk/route.js" defer></script>
12:<script src="/static/desk/router.js" defer></script>
13:<script src="/static/desk.js" defer></script>
51:<nav class="nav"></nav>
52:<div class="subnav" id="subnav" style="display:none"></div>
123:  <section class="view pane" id="view-agents-quant">
124:    <iframe class="paneframe" id="frameQuant" title="Quant Desk" src=""></iframe>
126:  <section class="view pane" id="view-agents-floor">
127:    <iframe class="paneframe" id="frameFloor" title="Live Floor" src=""></iframe>
```

Static asset status codes:
```
/static/desk/route.js -> 200
/static/desk/router.js -> 200
/static/desk.js -> 200
/static/desk/panes.js -> 404   (expected — confirms it is genuinely absent;
                                 also confirmed above that / never references it)
```

router.js content check (confirms the registry the JS-executing tests can't see):
```
15:    { id: "desk",   label: "Desk",        subs: [] },
16:    { id: "market", label: "Market",      subs: [] },
17:    { id: "agents", label: "Agent Floor", subs: [{ id: "quant", label: "Quant Desk" },
```

Sanity checks on routes/assets untouched by this task:
```
/floor?embed=1 -> 200
/team?embed=1 -> 200
/static/desk.css -> 200
(grep -c "subnav\|paneframe" on served desk.css) -> 5
```

Server access log for the above requests showed clean 200s (and the one
expected 404 for my own explicit panes.js probe) with no Flask-side
exceptions or tracebacks.

Server stopped:
```
$ pkill -f "python3 prototype/app.py"; pgrep -f "prototype/app.py" || echo "server stopped, no processes remain"
server stopped, no processes remain
```

## Step 8 browser checks — verification status

The brief's Step 8 lists 5 checks that assume a real browser executing JS,
clicking elements, and reading `location.hash` / back-button state. I have
no browser in this environment. What I verified instead, and what remains
genuinely unverified:

1. "`/` → Desk renders, 'Desk' is the active nav item, no sub-tab bar
   visible." — **Partially verified.** Confirmed via markup that the empty
   `<nav>`/`<div id="subnav" style="display:none">` shell is served, that
   `view-desk` still carries `class="view on"` (unchanged from before), and
   traced `router.js`'s `boot()` → `go()` → `renderNav()` / `show()` /
   `renderSubnav()` logic by reading the code (subnav `display` only becomes
   `flex` when `subs.length > 1`, which is true only for `agents`). **NOT
   verified**: that the browser actually paints "Desk" as the active/`on`
   nav link, or that no JS console errors occur during real execution.
2. "Click Market → market table loads, hash becomes `#market`." — **NOT
   verified.** No browser to click with. Traced the click handler
   (`renderNav()`'s `addEventListener("click", ...) → go(s.id, null, [])`)
   and confirmed `go()` sets `location.hash` when it differs from the
   current one — logically sound by code reading, not observed running.
3. "Click Agent Floor → sub-tab bar appears with 'Quant Desk' and 'Live
   Floor'; panes are empty." — **NOT verified** in a running browser. Static
   check: `router.js`'s `agents` section has two subs with those exact
   labels, `renderSubnav()` builds `<a data-sub>` elements from them, and the
   two pane `<section>` elements in `desk.html` have empty `src=""` iframes
   as shipped (Task 5 fills them).
4. "`#market/TITAN/5y` deep link → Market opens with TITAN drawer at 5y." —
   **NOT verified in a browser**, but traced through code by hand:
   `TPRoute.parse("#market/TITAN/5y", SECTIONS)` → market section has
   `subs: []` so `sub` stays `null`, `rest = ["TITAN", "5y"]`; `boot()` calls
   `go("market", null, ["TITAN","5y"])`; `show()` mounts the `market` view
   for the first time, calling the registered `mount` hook, which reads
   `window.TPRouter.current().rest` → `["TITAN","5y"]`, sets `curRange =
   "5y"` (in `RANGES`) and calls `openDrawer("TITAN")`. This mirrors the
   original hand-written deep-link block's behavior exactly, but I did not
   observe it execute.
5. "Browser back button → returns to previous section." — **NOT verified.**
   This depends on browser history/hashchange behavior
   (`window.addEventListener("hashchange", ...)` in `router.js`), which
   cannot be exercised without a real browser back-button press.

In short: markup correctness, asset resolution (200s / no stray 404s from
the served page), server-side stability under repeated requests, and JS
syntax validity are verified. Actual DOM rendering, click-driven state
transitions, and browser history navigation are NOT verified — they require
a browser, which this environment does not have.

## Anything surprising

- The pre-existing nav had **four** links, not the "flat four-link nav" the
  brief's Step 2 comment implies as being fully replaced by three registry
  sections: `data-tab="desk"`, `data-tab="market"` (both SPA tabs), plus two
  plain `<a href>` links to `/decisions` and `/classic` (separate full-page
  routes, marked with a `↗` external-link glyph, not part of the SPA at
  all). The brief's literal Step 4 replacement (empty `<nav>` + `<div
  id="subnav">`) removes all four, and `SECTIONS` in `router.js` only
  re-adds `desk`, `market`, `agents` as router-driven links. The `/decisions`
  and `/classic` full-page destinations are no longer reachable from the
  terminal's nav bar at all after this task. I implemented exactly what the
  brief specifies (word-for-word, including its own comment about not
  hand-editing nav links), since neither of the two rulings addresses this
  and the router has no mechanism for a non-hash external link in
  `SECTIONS`. Flagging this for the controller/reviewer since it's a
  functional change beyond "wire up the Agent Floor" — those two pages may
  be intentionally deprecated in this migration, or may need a different
  home (e.g., a footer link) in a later task.
- One untracked file, `prototype/data/kite_cache/instruments_nse_2026-08-28.json`,
  was present in the worktree before I touched anything (a market-data cache
  artifact written by the app itself, unrelated to this task). I left it
  untouched and did not stage it.
- No other surprises — the brief's Step 3 router.js code, Step 5 CSS, and
  Step 6 desk.js snippet all applied cleanly with no adaptation needed
  beyond the two explicit rulings.

---

## Fix round 1

**Concern addressed:** concern 1 from the initial report — the terminal's
literal Step 4 nav replacement had dropped the `/decisions` and `/classic`
external links entirely, making `/classic` (the client-facing surface that
must stay reachable) and `/decisions` unreachable from the terminal nav.

**Coordinator's confirmed ruling, implemented exactly as specified:**

### `prototype/static/desk/router.js`

Added a new `EXTERNAL` array immediately after `SECTIONS`, deliberately kept
out of the routed registry:
```js
  /* External destinations. Deliberately NOT in SECTIONS: TPRoute matches by
     section id, so an entry here would let "#classic" resolve to a section
     with no registered view and render a blank tab. These are plain links,
     never routed. */
  var EXTERNAL = [
    { label: "Decisions", href: "/decisions" },
    { label: "Classic",   href: "/classic" }
  ];
```

Extended `renderNav()` to render these after the section links, built via
DOM nodes (no `innerHTML`), reusing the existing `.ext` CSS class — no new
CSS added:
```js
    EXTERNAL.forEach(function (x) {
      var a = document.createElement("a");
      a.href = x.href;
      a.appendChild(document.createTextNode(x.label + " "));
      var ext = document.createElement("span");
      ext.className = "ext";
      ext.textContent = "↗";
      a.appendChild(ext);
      nav.appendChild(a);
    });
```
These entries carry no `data-section` attribute and no click handler — they
are ordinary `<a href>` links and navigate as full page loads, exactly as
the original hand-written nav links did.

Confirmed `EXTERNAL` is never passed to `TPRoute.parse` — all three call
sites (`go()`, and both places inside `boot()`) pass `SECTIONS`:
```
123:    var parsed = window.TPRoute.parse(
124:      window.TPRoute.build(section, sub, rest || []), SECTIONS);
137:    var p = window.TPRoute.parse(location.hash, SECTIONS);
141:      var q = window.TPRoute.parse(location.hash, SECTIONS);
```

`route.js` and `tests/js/route.test.js` were not touched.

### `tests/test_web_routes.py`

Appended, after `test_terminal_loads_router_modules`:
```python
def test_router_keeps_external_links(client):
    """The nav is registry-rendered, so external destinations must be declared
    in the module. /classic is the client-facing surface and must stay
    reachable from the terminal until it is absorbed."""
    r = client.get("/static/desk/router.js")
    assert r.status_code == 200
    assert b'href: "/decisions"' in r.data
    assert b'href: "/classic"' in r.data
```

### Commands run, with full output

```
$ python3 -m pytest tests/test_web_routes.py -v
============================= test session starts ==============================
platform darwin -- Python 3.11.5, pytest-7.4.0, pluggy-1.0.0
collecting ... collected 11 items

tests/test_web_routes.py::test_terminal_renders PASSED                   [  9%]
tests/test_web_routes.py::test_floor_renders PASSED                      [ 18%]
tests/test_web_routes.py::test_team_renders PASSED                       [ 27%]
tests/test_web_routes.py::test_floor_embed_hides_brand PASSED            [ 36%]
tests/test_web_routes.py::test_floor_without_embed_keeps_brand PASSED    [ 45%]
tests/test_web_routes.py::test_team_embed_hides_header_and_pageswitch PASSED [ 54%]
tests/test_web_routes.py::test_team_without_embed_keeps_header PASSED    [ 63%]
tests/test_web_routes.py::test_router_declares_three_sections PASSED     [ 72%]
tests/test_web_routes.py::test_terminal_has_subtab_bar PASSED            [ 81%]
tests/test_web_routes.py::test_terminal_loads_router_modules PASSED      [ 90%]
tests/test_web_routes.py::test_router_keeps_external_links PASSED        [100%]

============================== 11 passed in 7.19s ==============================

$ python3 -m pytest tests/ -q
........................................................................ [ 40%]
........................................................................ [ 80%]
....................................                                     [100%]
180 passed in 7.30s

$ node --test tests/js/*.test.js
...
1..12
# tests 12
# pass 12
# fail 0
# cancelled 0
# skipped 0
# todo 0
```

**Test counts: pytest 179 → 180 (+1, exactly this new test). Node 12 → 12
(unchanged — route.js/route.test.js untouched, as required).**

### Browser/server verification (background, then killed)

Started `python3 prototype/app.py` in the background
(`/tmp/tp-app4-fix1.log`). First `curl` attempt raced the server's startup
and returned connection-refused; a retry a few seconds later (server process
was confirmed already running via `pgrep`) succeeded — no code issue, purely
a timing gap on my end between backgrounding the process and the first
probe.

```
$ curl -sS -o /dev/null -w "GET / -> %{http_code}\n" http://localhost:5050/
GET / -> 200

$ curl -sS http://localhost:5050/static/desk/router.js | grep -n 'EXTERNAL\|href: "/decisions"\|href: "/classic"\|Decisions\|Classic'
25:  var EXTERNAL = [
26:    { label: "Decisions", href: "/decisions" },
27:    { label: "Classic",   href: "/classic" }
72:    EXTERNAL.forEach(function (x) {

$ curl -sS -o /dev/null -w "/decisions -> %{http_code}\n" http://localhost:5050/decisions
/decisions -> 200
$ curl -sS -o /dev/null -w "/classic -> %{http_code}\n" http://localhost:5050/classic
/classic -> 200

$ node --check prototype/static/desk/router.js && echo "router.js syntax OK"
router.js syntax OK
```

Server access log for this window showed clean 200s only, no exceptions:
```
127.0.0.1 - - [28/Aug/2026 01:06:53] "GET / HTTP/1.1" 200 -
127.0.0.1 - - [28/Aug/2026 01:06:59] "GET /static/desk/router.js HTTP/1.1" 200 -
127.0.0.1 - - [28/Aug/2026 01:06:59] "GET /decisions HTTP/1.1" 200 -
127.0.0.1 - - [28/Aug/2026 01:06:59] "GET /classic HTTP/1.1" 200 -
```

Server stopped:
```
$ pkill -f "python3 prototype/app.py"; pgrep -f "prototype/app.py" || echo "server stopped, no processes remain"
server stopped, no processes remain
```

### `TPRoute.parse` isolation — confirmed

`grep -n "TPRoute.parse\|TPRoute.build" prototype/static/desk/router.js`
shows all `TPRoute.parse` calls pass `SECTIONS` as the second argument;
`EXTERNAL` appears only at its declaration and in the `renderNav()` loop
that builds the plain links. `EXTERNAL` is never passed to `TPRoute.parse`
or `TPRoute.build` anywhere.

### Scope discipline

Only `prototype/static/desk/router.js` and `tests/test_web_routes.py` were
touched in this fix round. `route.js`, `tests/js/route.test.js`, `desk.js`,
`desk.html`, and `desk.css` were not modified. No CSS was added — the
existing `.nav a .ext` rule is reused as instructed.

---

## Fix round 2

**Concern addressed:** the Important finding from Task 4 review — a
back-button trap in `go()`. `go()` unconditionally wrote `location.hash`
whenever it differed from the computed hash, including when the router was
merely normalizing on boot or reacting to a `hashchange` the browser had
already recorded (not a user click). Loading `/` with no hash normalized to
`#desk` and pushed a history entry; pressing Back returned to `/`, which
fired `hashchange`, which re-ran `go()`, which pushed `#desk` again — the
user could not leave the terminal with a single Back press. The old
`switchTab()` never touched `location.hash` at all, so this was a new
regression introduced by Task 4, in a tool used daily.

**Coordinator's confirmed fix, implemented exactly as specified:**

### `prototype/static/desk/router.js`

`go()` gained a fourth parameter, `replace`. When set (and
`history.replaceState` exists), normalization now calls
`history.replaceState(null, "", hash)` instead of assigning
`location.hash` — this updates the URL bar without creating a history
entry:
```js
  function go(section, sub, rest, replace) {
    var parsed = window.TPRoute.parse(
      window.TPRoute.build(section, sub, rest || []), SECTIONS);
    cur = parsed;
    renderSubnav(parsed.section, parsed.sub);
    show(parsed.section, parsed.sub);
    var hash = window.TPRoute.build(parsed.section, parsed.sub, parsed.rest);
    if (location.hash === hash) return;
    /* Normalizing (boot, or reacting to a hashchange the browser already
       recorded) must NOT create a history entry -- otherwise Back lands on the
       un-normalized URL, we normalize again, and the user is trapped. Only a
       deliberate click pushes. */
    if (replace && history.replaceState) history.replaceState(null, "", hash);
    else location.hash = hash;
  }
```

Both places inside `boot()` where the router reacts rather than the user
navigates now pass `true`:
```js
  function boot() {
    renderNav();
    var p = window.TPRoute.parse(location.hash, SECTIONS);
    go(p.section, p.sub, p.rest, true);

    window.addEventListener("hashchange", function () {
      var q = window.TPRoute.parse(location.hash, SECTIONS);
      go(q.section, q.sub, q.rest, true);
    });
```

The two click handlers — the section links built in `renderNav()` and the
sub-tab links built in `renderSubnav()` — are unchanged and call `go(...)`
with no fourth argument, so a real click still pushes a history entry and
Back returns to the previously viewed tab.

### Four `go(` call sites — confirmed by grep

```
$ grep -n "go(" prototype/static/desk/router.js
69:      a.addEventListener("click", function (e) { e.preventDefault(); go(s.id, null, []); });
98:      a.addEventListener("click", function (e) { e.preventDefault(); go(section, t.id, []); });
122:  function go(section, sub, rest, replace) {
144:    go(p.section, p.sub, p.rest, true);
148:      go(q.section, q.sub, q.rest, true);
```
Excluding the definition at line 122, exactly four call sites:
- Line 69 (`renderNav` click handler) — **no flag** (user click, pushes)
- Line 98 (`renderSubnav` click handler) — **no flag** (user click, pushes)
- Line 144 (`boot()` initial normalization) — **`true`** (replace)
- Line 148 (`boot()` hashchange listener) — **`true`** (replace)

Matches the coordinator's spec exactly.

`route.js` and `tests/js/route.test.js` were NOT touched:
```
$ git diff --stat -- prototype/static/desk/route.js tests/js/route.test.js
(no output — both files unmodified)
```

### Commands run, with full output

```
$ python3 -m pytest tests/ -q
........................................................................ [ 40%]
........................................................................ [ 80%]
....................................                                     [100%]
180 passed in 3.05s

$ node --test tests/js/*.test.js
...
1..12
# tests 12
# pass 12
# fail 0
# cancelled 0
# skipped 0
# todo 0
```

**Test counts: pytest 180 (unchanged, as expected — this is a behavioural
fix that no headless test without a DOM/browser can exercise). Node 12/12
(unchanged, as expected — route.js untouched).**

### Browser/server verification (background, then killed)

**Surprise / deviation from the exact prescribed command:** `python3
prototype/app.py` in this worktree failed to bind — port 5050 was already
held by an unrelated, pre-existing `python3 app.py` process (PID 20862,
started 08:29:11 today, `cwd` =
`/Users/soumyaswain/Documents/tinker/projects/tradepilot/prototype` — the
**parent checkout**, not this worktree, and not started by me in this
session). My first `nohup ... app.py &` silently exited with "Address
already in use"; a subsequent `curl / -> 200` was unknowingly hitting that
other, unrelated process (which is why `/static/desk/router.js` on port 5050
then returned 404 — it's a different app.py entirely). Per my instructions
("Do NOT touch the parent checkout"), I did not kill that process. Instead,
since `app.run(...)` in `prototype/app.py` is guarded by
`if __name__ == "__main__":`, I imported this worktree's Flask `app` object
directly in a one-line Python snippet and served it on port **5051**,
touching no file:

```
$ nohup python3 -c "
import sys, os
sys.path.insert(0, os.getcwd())
from prototype.app import app
app.run(host='127.0.0.1', port=5051, debug=False, threaded=True)
" > /tmp/tp-app4-fix2-p5051.log 2>&1 &

$ curl -sS -o /dev/null -w "GET / -> %{http_code}\n" http://localhost:5051/
GET / -> 200

$ curl -sS http://localhost:5051/static/desk/router.js | grep -n "history.replaceState\|function go(section, sub, rest, replace)\|go(p.section, p.sub, p.rest, true)\|go(q.section, q.sub, q.rest, true)"
122:  function go(section, sub, rest, replace) {
134:    if (replace && history.replaceState) history.replaceState(null, "", hash);
144:    go(p.section, p.sub, p.rest, true);
148:      go(q.section, q.sub, q.rest, true);

$ curl -sS http://localhost:5051/static/desk/router.js -o /tmp/served-router-p5051.js
$ node --check /tmp/served-router-p5051.js && echo "served router.js syntax OK"
served router.js syntax OK
```

Server access log for this window showed clean 200s only:
```
127.0.0.1 - - [28/Aug/2026 08:37:58] "GET / HTTP/1.1" 200 -
127.0.0.1 - - [28/Aug/2026 08:38:04] "GET /static/desk/router.js HTTP/1.1" 200 -
127.0.0.1 - - [28/Aug/2026 08:38:04] "GET /static/desk/router.js HTTP/1.1" 200 -
```

My verification server on port 5051 was stopped; the unrelated pre-existing
process on port 5050 was left untouched:
```
$ lsof -ti :5051 | xargs -r kill
$ lsof -i :5051 2>/dev/null || echo "port 5051 clear, worktree server stopped"
port 5051 clear, worktree server stopped

$ lsof -i :5050 2>/dev/null | grep LISTEN
python3.1 20862 soumyaswain    3u  IPv4 ... TCP localhost:mmcc (LISTEN)
```
That PID belongs to the parent checkout and predates this session; it was
not started or touched by this fix round.

### Back-button behaviour — explicitly NOT verified

The actual fix (does pressing Back in a real browser now leave the
terminal on the first press, instead of re-trapping on `#desk`) was **NOT
verified** — this environment has no browser, and `history.replaceState`
vs. `location.hash` assignment, along with the browser's session-history
stack and the Back button itself, cannot be exercised via `curl` or Node's
`vm`/`--check`. What I verified is strictly: (a) the patched source and the
served module contain `history.replaceState` and the `replace` parameter
exactly as specified, (b) all four `go(` call sites carry the flag in
exactly the two places the coordinator specified and omit it in the two
click handlers, (c) the file is syntactically valid JS, and (d) the
existing automated test suites are unaffected. This is a code-trace-only
verification of the Important finding, not an observed browser fix.

### Scope discipline

Only `prototype/static/desk/router.js` was touched in this fix round —
exactly the file and the two functions (`go()`, `boot()`) named in the
ruling. No other file was modified. The five Minor findings from the Task 4
review were left untouched, as instructed.
