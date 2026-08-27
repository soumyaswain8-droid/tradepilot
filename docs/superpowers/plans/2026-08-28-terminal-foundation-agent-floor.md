# Terminal Foundation and Agent Floor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the TradePilot terminal a two-level section/sub-tab router and mount the two Agent Floor screens (`/team`, `/floor`) inside it as lazy iframe panes.

**Architecture:** A pure, dependency-free hash parser (`route.js`) is testable under Node with no DOM. A thin router (`router.js`) owns the nav, the section/sub-tab DOM, and a lifecycle registry that views opt into. `panes.js` drives the two iframes, setting `src` on show and `about:blank` on hide so their one-second poll loops die with the tab. `desk.js` stops owning navigation and registers its two existing views with the router instead.

**Tech Stack:** Flask 2.2.2 (server, Jinja templates), vanilla ES5-style JS in IIFEs (no build step, no bundler), pytest 7.4.0 (routes and markup), Node 22 built-in test runner (pure JS logic — no `package.json`, no npm install).

**Spec:** `docs/superpowers/specs/2026-08-27-terminal-agent-floor-design.md`

## Global Constraints

These come from the spec and from the contract documented at the top of `prototype/static/desk.js`. Every task's requirements implicitly include this section.

- **JS never rides inline in a `<script src>` tag.** On 2026-08-03 a tab shipped blank because its logic was appended inside a `<script src>` element, whose inline content the browser silently discards. Every script tag is either `src`-only or content-only, never both.
- **Every interpolated value passes `esc()`** or a numeric formatter before reaching markup. The score feed is fed by yfinance plus an NSE roster that has already served 30 symbols nobody asked for.
- **Polling pauses when the tab is hidden** — guard every interval with `if (document.hidden) return;`.
- **A failing view degrades its own card only.** It never blocks a sibling, never throws past the router, never blanks the tab.
- **No new runtime dependencies.** No npm install, no `package.json`, no CDN additions. Node's test runner is built in; pytest and Flask are already installed.
- **Existing deep links must keep working.** `#market`, `#market/RELIANCE` and `#market/TITAN/5y` are live bookmark formats.
- **`/floor` and `/team` remain directly reachable** as standalone full pages. They are iframe targets, not replacements.
- Python style: this codebase uses 4-space indent, double-quoted strings, and docstrings on route handlers. Match it.
- JS style: ES5-compatible, IIFE-wrapped, `"use strict"`, 2-space indent. Match `desk.js`.

## File Structure

| File | Responsibility |
|:--|:--|
| `prototype/static/desk/route.js` | **new** — pure hash parse/build. No DOM, no globals. Dual-export so Node can require it. |
| `prototype/static/desk/router.js` | **new** — nav rendering, section/sub-tab DOM switching, lifecycle registry. |
| `prototype/static/desk/panes.js` | **new** — iframe mount/unmount for the two Agent Floor panes. |
| `prototype/static/desk.js` | **modify** — drop `switchTab`, register `desk` and `market` views with the router. |
| `prototype/templates/desk.html` | **modify** — registry-driven nav, sub-tab bar, two iframe panes, new script tags. |
| `prototype/static/desk.css` | **modify** — sub-tab bar and iframe pane styles. |
| `prototype/templates/floor.html` | **modify** — `?embed=1` hides the brand span only. |
| `prototype/templates/team.html` | **modify** — `?embed=1` hides the header and skips `pageswitch.js`. |
| `prototype/app.py` | **modify** — pass `embed` into both templates. |
| `tests/conftest.py` | **new** — Flask test client fixture. |
| `tests/test_web_routes.py` | **new** — route, markup and embed-mode assertions. |
| `tests/js/route.test.js` | **new** — Node tests for the pure hash parser. |

---

### Task 1: Web-layer test harness

The `tests/` directory holds 14 files, all engine and strategy logic. There is no Flask test client anywhere in the repo, so nothing that follows can be test-driven until this exists. This task builds the harness and proves it against routes that already work.

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_web_routes.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a pytest fixture `client` — a `flask.testing.FlaskClient` for `prototype.app.app`. Every later task's tests take `client` as their first argument.

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
"""Shared fixtures for the web-layer tests.

The Flask app lives in prototype/app.py and inserts its own directory onto
sys.path at import time, so importing it requires the repo root on sys.path.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture(scope="session")
def flask_app():
    """The prototype Flask application, configured for testing."""
    from prototype.app import app
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(flask_app):
    """A test client. Use client.get(path) -- no network, no live server."""
    return flask_app.test_client()
```

Create `tests/test_web_routes.py`:

```python
"""Web-layer coverage.

Before this file the entire Flask surface -- roughly 70 routes -- was
untested. The terminal already shipped one blank tab on 2026-08-03 because a
script was silently discarded; these tests exist so that class of bug fails
in CI rather than in the browser.
"""


def test_terminal_renders(client):
    """GET / returns the terminal shell."""
    r = client.get("/")
    assert r.status_code == 200
    assert b"TRADEPILOT" in r.data


def test_floor_renders(client):
    """GET /floor returns the Agent Floor console."""
    r = client.get("/floor")
    assert r.status_code == 200
    assert b"Market Scan" in r.data


def test_team_renders(client):
    """GET /team returns the Quant Desk."""
    r = client.get("/team")
    assert r.status_code == 200
    assert b"<h1>TradePilot Quant Desk</h1>" in r.data
```

- [ ] **Step 2: Run the tests to verify the harness reports honestly**

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/test_web_routes.py -v
```

Expected: all three PASS. These assert existing behaviour, so a failure here means the harness is broken (import error, wrong sentinel), not the app. Fix the harness before continuing.

If the import fails with `ModuleNotFoundError: No module named 'prototype'`, confirm `prototype/__init__.py` exists; if it does not, create an empty one and re-run.

- [ ] **Step 3: Verify the harness catches a real failure**

Temporarily change the sentinel in `test_terminal_renders` from `b"TRADEPILOT"` to `b"THIS_STRING_IS_NOT_IN_THE_PAGE"` and re-run:

```bash
python3 -m pytest tests/test_web_routes.py::test_terminal_renders -v
```

Expected: FAIL with an assertion error. This confirms the test is actually reading the response body rather than passing vacuously. Revert the sentinel to `b"TRADEPILOT"` and re-run to confirm PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_web_routes.py
git commit -m "test(web): first coverage for the Flask surface

Seventy routes, zero tests. The terminal shipped a blank tab on 2026-08-03
because a script tag was silently discarded and nothing caught it. This is
the harness that makes that class of bug fail before the browser does."
```

---

### Task 2: Embed mode for /floor and /team

The two Agent Floor screens supply their own brand chrome, which is redundant once the terminal frames them. `team.html` additionally loads `pageswitch.js` — the floating operator nav — which must not appear inside a pane. `floor.html` does **not** load `pageswitch.js`; only its brand span needs hiding, and its stats strip (ticks, rate, escalations, armed, gaps) must be kept because that data is the point of the screen.

**Files:**
- Modify: `prototype/app.py:121-125` (the `/floor` handler) and `prototype/app.py:3094-3098` (the `/team` handler)
- Modify: `prototype/templates/floor.html` (the `.bar` block near the top of `<body>`)
- Modify: `prototype/templates/team.html` (the `<header>` block, and line 249)
- Modify: `tests/test_web_routes.py`

**Interfaces:**
- Consumes: the `client` fixture from Task 1.
- Produces: `GET /floor?embed=1` and `GET /team?embed=1` render without brand chrome. Task 5's iframes point at exactly these URLs.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_routes.py`:

```python
def test_floor_embed_hides_brand(client):
    """?embed=1 drops the brand span; the stats strip must survive."""
    r = client.get("/floor?embed=1")
    assert r.status_code == 200
    assert b"AGENT FLOOR</span>" not in r.data
    assert b'id="sTicks"' in r.data          # stats strip kept


def test_floor_without_embed_keeps_brand(client):
    """The standalone page is unchanged."""
    r = client.get("/floor")
    assert b"AGENT FLOOR</span>" in r.data


def test_team_embed_hides_header_and_pageswitch(client):
    """?embed=1 drops the header and must not load the operator nav."""
    r = client.get("/team?embed=1")
    assert r.status_code == 200
    # Match the <h1>, not the bare string: team.html:5 also carries
    # "TradePilot Quant Desk" in its <title>, which embed mode keeps.
    assert b"<h1>TradePilot Quant Desk</h1>" not in r.data
    assert b"pageswitch.js" not in r.data


def test_team_without_embed_keeps_header(client):
    """The standalone page is unchanged."""
    r = client.get("/team")
    assert b"<h1>TradePilot Quant Desk</h1>" in r.data
    assert b"pageswitch.js" in r.data
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_web_routes.py -v -k embed
```

Expected: `test_floor_embed_hides_brand` and `test_team_embed_hides_header_and_pageswitch` FAIL (the brand and pageswitch are still present — `?embed=1` is currently ignored). The two `without_embed` tests PASS.

- [ ] **Step 3: Pass the flag from Flask**

In `prototype/app.py`, replace the `/floor` handler:

```python
@app.route("/floor")
def floor_view():
    """Live console for the agent floor -- what each agent is watching, right now.

    ?embed=1 strips the brand span so the console can be framed inside the
    terminal, which supplies its own chrome. The stats strip stays: it is the
    point of the screen.
    """
    return render_template("floor.html", embed=request.args.get("embed") == "1")
```

and the `/team` handler:

```python
@app.route("/team")
def team_view():
    """Quant desk -- agent roster, pending tasks, audit log.

    ?embed=1 strips the header and skips pageswitch.js, which must never
    render inside a terminal pane.
    """
    return render_template("team.html", embed=request.args.get("embed") == "1")
```

`request` is already imported at `prototype/app.py:6`. If the existing `/team` handler body differs from the above, keep its original `render_template` arguments and add only the `embed=` keyword.

- [ ] **Step 4: Guard the markup**

In `prototype/templates/floor.html`, wrap the brand span inside the `.bar` div:

```jinja
{% if not embed %}<span class="brand">TRADE<b>PILOT</b> · AGENT FLOOR</span>{% endif %}
```

In `prototype/templates/team.html`, wrap the whole `<header>` element:

```jinja
{% if not embed %}
<header>
  <h1>TradePilot Quant Desk</h1>
  <div class="meta">
    <span id="ts">—</span>
    &nbsp;·&nbsp;
    <a class="nav-link" href="/team/sarathi">Sarathi Ledger</a>
    &nbsp;·&nbsp;
    <a class="nav-link" href="/live">Live Engines</a>
  </div>
</header>
{% endif %}
```

`team.html` writes a timestamp into `#ts`, which no longer exists in embed mode. At line 249, guard the pageswitch include and leave the page's own script untouched:

```jinja
{% if not embed %}<script src="/static/pageswitch.js"></script>{% endif %}
```

`team.html:233` writes to `#ts` unconditionally. Replace that exact line:

```js
    document.getElementById("ts").textContent = fmt(j.ts);
```

with:

```js
    var tsEl = document.getElementById("ts");
    if (tsEl) tsEl.textContent = fmt(j.ts);
```

Only the null guard is new — `fmt(j.ts)` is unchanged. Without this the poll tick throws a TypeError every second in embed mode and the pane stops updating, which presents as "the pane loaded once and froze".

- [ ] **Step 5: Run the tests to verify they pass**

```bash
python3 -m pytest tests/test_web_routes.py -v
```

Expected: all seven PASS.

- [ ] **Step 6: Verify in the browser**

```bash
python3 prototype/app.py
```

Open `http://localhost:5050/team?embed=1`. Expected: no header, no floating nav pill, KPI strip and agent grid render normally, and the browser console shows **no errors** across at least two poll ticks (roughly 20 seconds). Then open `http://localhost:5050/team` and confirm the header and nav pill are back. Repeat for `/floor?embed=1` — the stats strip must still update.

- [ ] **Step 7: Commit**

```bash
git add prototype/app.py prototype/templates/floor.html prototype/templates/team.html tests/test_web_routes.py
git commit -m "feat(floor,team): embed mode for framing inside the terminal

?embed=1 drops the brand chrome each page supplies for itself, and stops
team.html loading the operator nav pill -- which has no business rendering
inside a pane. floor.html keeps its stats strip: ticks, rate, escalations
and armed are the screen, not decoration.

Also null-guards team.html's #ts write, which the header guard removes."
```

---

### Task 3: Pure hash routing logic

The router's parsing rules are the one place a mistake silently breaks live bookmarks. Isolating them as pure functions makes them properly testable under Node's built-in runner — no DOM, no dependencies, no `package.json`.

**Files:**
- Create: `prototype/static/desk/route.js`
- Create: `tests/js/route.test.js`

**Interfaces:**
- Consumes: nothing.
- Produces: a `TPRoute` object exposed as `window.TPRoute` in the browser and via `module.exports` under Node, with:
  - `TPRoute.parse(hash, sections)` → `{ section: string, sub: string|null, rest: string[] }`
  - `TPRoute.build(section, sub, rest)` → `string` beginning with `#`
  - `sections` is an array of `{ id: string, label: string, subs: Array<{id: string, label: string}> }`. A section with `subs: []` is flat and always parses to `sub: null`.

- [ ] **Step 1: Write the failing tests**

Create `tests/js/route.test.js`:

```js
"use strict";
const test = require("node:test");
const assert = require("node:assert");
const TPRoute = require("../../prototype/static/desk/route.js");

const SECTIONS = [
  { id: "desk",   label: "Desk",        subs: [] },
  { id: "market", label: "Market",      subs: [{ id: "india", label: "India" },
                                               { id: "fno",   label: "F&O" },
                                               { id: "us",    label: "US" }] },
  { id: "agents", label: "Agent Floor", subs: [{ id: "quant", label: "Quant Desk" },
                                               { id: "floor", label: "Live Floor" }] },
];

test("empty hash falls back to the first section", () => {
  assert.deepStrictEqual(TPRoute.parse("", SECTIONS),
    { section: "desk", sub: null, rest: [] });
});

test("bare section resolves to its default sub", () => {
  assert.deepStrictEqual(TPRoute.parse("#agents", SECTIONS),
    { section: "agents", sub: "quant", rest: [] });
});

test("explicit sub is honoured", () => {
  assert.deepStrictEqual(TPRoute.parse("#agents/floor", SECTIONS),
    { section: "agents", sub: "floor", rest: [] });
});

test("flat section takes no sub", () => {
  assert.deepStrictEqual(TPRoute.parse("#desk", SECTIONS),
    { section: "desk", sub: null, rest: [] });
});

test("legacy deep link treats an unknown segment as payload", () => {
  // #market/TITAN/5y predates sub-tabs. TITAN is not a sub, so it is a symbol
  // against the default sub. Breaking this breaks live bookmarks.
  assert.deepStrictEqual(TPRoute.parse("#market/TITAN/5y", SECTIONS),
    { section: "market", sub: "india", rest: ["TITAN", "5y"] });
});

test("known sub is not mistaken for payload", () => {
  assert.deepStrictEqual(TPRoute.parse("#market/fno", SECTIONS),
    { section: "market", sub: "fno", rest: [] });
});

test("sub plus payload", () => {
  assert.deepStrictEqual(TPRoute.parse("#market/india/TITAN/5y", SECTIONS),
    { section: "market", sub: "india", rest: ["TITAN", "5y"] });
});

test("unknown section falls back to the first", () => {
  assert.deepStrictEqual(TPRoute.parse("#nonsense", SECTIONS),
    { section: "desk", sub: null, rest: [] });
});

test("leading hash is optional", () => {
  assert.deepStrictEqual(TPRoute.parse("agents/floor", SECTIONS),
    { section: "agents", sub: "floor", rest: [] });
});

test("trailing and doubled slashes are ignored", () => {
  assert.deepStrictEqual(TPRoute.parse("#agents//floor/", SECTIONS),
    { section: "agents", sub: "floor", rest: [] });
});

test("build round-trips through parse", () => {
  const h = TPRoute.build("market", "india", ["TITAN", "5y"]);
  assert.strictEqual(h, "#market/india/TITAN/5y");
  assert.deepStrictEqual(TPRoute.parse(h, SECTIONS),
    { section: "market", sub: "india", rest: ["TITAN", "5y"] });
});

test("build omits a null sub", () => {
  assert.strictEqual(TPRoute.build("desk", null, []), "#desk");
});
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd ~/Documents/tinker/projects/tradepilot
node --test tests/js/
```

Expected: every test FAILS with `Cannot find module '../../prototype/static/desk/route.js'`.

- [ ] **Step 3: Write the minimal implementation**

Create `prototype/static/desk/route.js`:

```js
/* route.js — pure hash routing for the terminal. No DOM, no globals, no deps.
   Kept separate from router.js precisely so it can be tested under Node:
   these rules are the one place a mistake silently breaks live bookmarks.

   Hash grammar:  #section[/sub][/rest...]
   Segment 2 is a sub-tab only if it matches one of that section's sub ids.
   Anything else is payload against the default sub — which is what keeps
   the pre-sub-tab links (#market/TITAN/5y) working. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TPRoute = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function findSection(id, sections) {
    for (var i = 0; i < sections.length; i++) {
      if (sections[i].id === id) return sections[i];
    }
    return null;
  }

  function parse(hash, sections) {
    var segs = String(hash || "").replace(/^#/, "").split("/").filter(Boolean);
    var section = findSection(segs[0], sections) || sections[0];
    var subs = section.subs || [];
    var rest = segs.slice(1);
    var sub = null;

    if (subs.length) {
      sub = subs[0].id;
      if (rest.length && findSection(rest[0], subs)) {
        sub = rest[0];
        rest = rest.slice(1);
      }
    }
    return { section: section.id, sub: sub, rest: rest };
  }

  function build(section, sub, rest) {
    var parts = [section];
    if (sub) parts.push(sub);
    return "#" + parts.concat(rest || []).join("/");
  }

  return { parse: parse, build: build };
});
```

`findSection` is reused to look up sub ids because a sub has the same `{ id }` shape. That is deliberate, not an accident — do not duplicate it.

- [ ] **Step 4: Run to verify they pass**

```bash
node --test tests/js/
```

Expected: `pass 12`, `fail 0`.

- [ ] **Step 5: Commit**

```bash
git add prototype/static/desk/route.js tests/js/route.test.js
git commit -m "feat(terminal): pure hash router, tested under node

Section/sub-tab routing with one rule worth stating plainly: segment two is
a sub-tab only if it matches a known sub id, otherwise it is payload. That
is what keeps #market/TITAN/5y -- a live bookmark format that predates
sub-tabs -- resolving to the default sub instead of 404-ing into nothing.

Twelve cases under node's built-in runner. No package.json, no npm."
```

---

### Task 4: Router and lifecycle registry

Wires `route.js` to the DOM: renders the nav from a section registry, switches views, and gives each view `mount` / `refresh` / `unmount` hooks. `desk.js` hands over navigation and becomes a registrant like any other view.

The nav declares only sections that have content — Desk, Market, Agent Floor. Research and Portfolio arrive in Plan 2. A section with fewer than two sub-tabs renders no sub-tab bar.

**Files:**
- Create: `prototype/static/desk/router.js`
- Modify: `prototype/templates/desk.html` (the `<nav class="nav">` block and the script tags in `<head>`)
- Modify: `prototype/static/desk.css` (append)
- Modify: `prototype/static/desk.js` (the `switchTab` function and the boot block)
- Modify: `tests/test_web_routes.py`

**Interfaces:**
- Consumes: `TPRoute.parse` and `TPRoute.build` from Task 3.
- Produces: `window.TPRouter` with:
  - `TPRouter.SECTIONS` → the section registry array, shape as defined in Task 3.
  - `TPRouter.register(viewId, hooks)` where `hooks` is `{ mount?: fn, refresh?: fn, unmount?: fn, pollMs?: number }` and `viewId` matches a DOM element with id `view-<viewId>`.
  - `TPRouter.go(section, sub, rest)` → switches view and updates the hash.
  - `TPRouter.current()` → `{ section, sub, rest }`.
  - Task 5 calls `TPRouter.register` for the two Agent Floor panes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_routes.py`:

```python
def test_terminal_declares_three_sections(client):
    """Nav is registry-driven; these three ship in Plan 1."""
    r = client.get("/")
    for section in (b"data-section=\"desk\"",
                    b"data-section=\"market\"",
                    b"data-section=\"agents\""):
        assert section in r.data


def test_terminal_has_subtab_bar(client):
    """The sub-tab bar element must exist even when empty."""
    assert b'id="subnav"' in client.get("/").data


def test_terminal_loads_router_modules(client):
    """Every module is referenced by a src-only script tag.

    This is the direct regression test for the 2026-08-03 blank tab: a
    script referenced but never loaded, or loaded with discarded inline
    content, is exactly how that shipped.
    """
    body = client.get("/").data
    for src in (b"/static/desk/route.js",
                b"/static/desk/router.js",
                b"/static/desk.js"):
        assert src in body
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_web_routes.py -v -k "section or subtab or router_modules"
```

Expected: all three FAIL — the terminal still has the old four-link flat nav.

- [ ] **Step 3: Write the router**

Create `prototype/static/desk/router.js`:

```js
/* router.js — nav, section/sub-tab switching, and the view lifecycle.
   Parsing lives in route.js (pure, node-tested); this file owns the DOM.

   Lifecycle contract:
     mount()    once, the first time a view becomes visible
     refresh()  on tick, only while visible and the document is not hidden
     unmount()  on hide -- iframe panes only; ported views keep their state

   Every hook is wrapped. A view that throws degrades itself to an error card
   and never takes the shell, the nav, or a sibling view down with it. */
(function () {
  "use strict";

  var SECTIONS = [
    { id: "desk",   label: "Desk",        subs: [] },
    { id: "market", label: "Market",      subs: [] },
    { id: "agents", label: "Agent Floor", subs: [{ id: "quant", label: "Quant Desk" },
                                                 { id: "floor", label: "Live Floor" }] }
  ];

  var views = {};     // viewId -> hooks
  var mounted = {};   // viewId -> true
  var cur = { section: null, sub: null, rest: [] };

  function $(id) { return document.getElementById(id); }

  /* A view id is "section" for flat sections, "section-sub" otherwise. */
  function viewIdFor(section, sub) { return sub ? section + "-" + sub : section; }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function guard(viewId, hookName) {
    var hooks = views[viewId];
    if (!hooks || typeof hooks[hookName] !== "function") return;
    try {
      hooks[hookName]();
    } catch (e) {
      if (window.console) console.error("view " + viewId + "." + hookName, e);
      var el = $("view-" + viewId);
      if (el && hookName === "mount") {
        el.innerHTML = '<div class="card"><h3>This view failed to load</h3>' +
          '<div class="sub">' + esc(e && e.message || e) + '</div></div>';
      }
    }
  }

  function renderNav() {
    var nav = document.querySelector(".nav");
    if (!nav) return;
    nav.innerHTML = "";
    SECTIONS.forEach(function (s) {
      var a = document.createElement("a");
      a.setAttribute("data-section", s.id);
      a.textContent = s.label;
      a.href = "#" + s.id;
      a.addEventListener("click", function (e) { e.preventDefault(); go(s.id, null, []); });
      nav.appendChild(a);
    });
  }

  function renderSubnav(section, sub) {
    var bar = $("subnav");
    if (!bar) return;
    var s = null;
    SECTIONS.forEach(function (x) { if (x.id === section) s = x; });
    var subs = (s && s.subs) || [];
    bar.innerHTML = "";
    bar.style.display = subs.length > 1 ? "flex" : "none";
    subs.forEach(function (t) {
      var a = document.createElement("a");
      a.setAttribute("data-sub", t.id);
      a.textContent = t.label;
      a.href = "#" + section + "/" + t.id;
      if (t.id === sub) a.className = "on";
      a.addEventListener("click", function (e) { e.preventDefault(); go(section, t.id, []); });
      bar.appendChild(a);
    });
  }

  function show(section, sub) {
    var target = viewIdFor(section, sub);
    Object.keys(views).forEach(function (viewId) {
      var el = $("view-" + viewId);
      if (!el) return;
      var on = viewId === target;
      el.classList.toggle("on", on);
      if (on) {
        if (!mounted[viewId]) { mounted[viewId] = true; guard(viewId, "mount"); }
      } else if (mounted[viewId] && views[viewId] && views[viewId].unmount) {
        guard(viewId, "unmount");
        mounted[viewId] = false;
      }
    });
    document.querySelectorAll(".nav a[data-section]").forEach(function (a) {
      a.classList.toggle("on", a.getAttribute("data-section") === section);
    });
  }

  function go(section, sub, rest) {
    var parsed = window.TPRoute.parse(
      window.TPRoute.build(section, sub, rest || []), SECTIONS);
    cur = parsed;
    renderSubnav(parsed.section, parsed.sub);
    show(parsed.section, parsed.sub);
    var hash = window.TPRoute.build(parsed.section, parsed.sub, parsed.rest);
    if (location.hash !== hash) location.hash = hash;
  }

  function register(viewId, hooks) { views[viewId] = hooks || {}; }
  function current() { return { section: cur.section, sub: cur.sub, rest: cur.rest.slice() }; }

  function boot() {
    renderNav();
    var p = window.TPRoute.parse(location.hash, SECTIONS);
    go(p.section, p.sub, p.rest);

    window.addEventListener("hashchange", function () {
      var q = window.TPRoute.parse(location.hash, SECTIONS);
      go(q.section, q.sub, q.rest);
    });

    /* One timer drives every view. Each hook declares its own cadence, so a
       60s view is not woken by a 30s neighbour. */
    setInterval(function () {
      if (document.hidden) return;
      var now = Date.now();
      Object.keys(views).forEach(function (viewId) {
        var h = views[viewId];
        if (!mounted[viewId] || !h || typeof h.refresh !== "function") return;
        var el = $("view-" + viewId);
        if (!el || !el.classList.contains("on")) return;
        var every = h.pollMs || 60000;
        if (now - (h._last || 0) < every) return;
        h._last = now;
        guard(viewId, "refresh");
      });
    }, 5000);
  }

  window.TPRouter = {
    SECTIONS: SECTIONS, register: register, go: go, current: current, boot: boot
  };
})();
```

- [ ] **Step 4: Replace the nav markup**

In `prototype/templates/desk.html`, replace the whole `<nav class="nav">` block with an empty nav plus a sub-tab bar. The router fills both:

```html
<!-- Nav and sub-tabs are rendered from TPRouter.SECTIONS. Do not hand-edit
     links here: a link the registry does not know about routes to nothing. -->
<nav class="nav"></nav>
<div class="subnav" id="subnav" style="display:none"></div>
```

In the same file's `<head>`, replace the single `desk.js` script tag with four. Order matters — `route.js` before `router.js`, and `defer` preserves it:

```html
<script src="/static/desk/route.js" defer></script>
<script src="/static/desk/router.js" defer></script>
<script src="/static/desk/panes.js" defer></script>
<script src="/static/desk.js" defer></script>
```

Leave the existing comment above these tags in place — it records why inline content is banned here.

Create the pane container now so Task 5 has somewhere to mount. Add these two sections inside `<main class="main">`, after the Market section:

```html
<!-- ═══ AGENT FLOOR ═══ -->
<section class="view pane" id="view-agents-quant">
  <iframe class="paneframe" id="frameQuant" title="Quant Desk" src=""></iframe>
</section>
<section class="view pane" id="view-agents-floor">
  <iframe class="paneframe" id="frameFloor" title="Live Floor" src=""></iframe>
</section>
```

The Desk and Market sections keep their existing ids `view-desk` and `view-market`, which already match `viewIdFor()` for flat sections. Do not rename them.

- [ ] **Step 5: Style the sub-tab bar and panes**

Append to `prototype/static/desk.css`:

```css
/* ── sub-tabs ───────────────────────────────────────────────────────────── */
.subnav {
  display: flex; gap: 2px; padding: 0 16px;
  background: var(--bg); border-bottom: 1px solid var(--line);
}
.subnav a {
  padding: 7px 12px 6px; font-size: 11px; font-weight: 600;
  color: var(--dim); text-decoration: none; letter-spacing: .3px;
  border-bottom: 2px solid transparent; cursor: pointer;
}
.subnav a:hover { color: var(--ink); }
.subnav a.on { color: var(--ink); border-bottom-color: var(--acc); }

/* ── iframe panes ───────────────────────────────────────────────────────── */
/* The framed consoles set their own body height, so the frame must be given
   an explicit one -- a percentage height against an auto-height parent
   collapses to zero and the pane renders as a 0px sliver. */
.view.pane.on { display: block; }
.paneframe {
  display: block; width: 100%; height: calc(100vh - 132px);
  min-height: 520px; border: 0; background: var(--bg);
}
```

- [ ] **Step 6: Hand navigation over from desk.js**

In `prototype/static/desk.js`, delete the `switchTab` function entirely (it spans the `/* ── tabs ── */` comment through its closing brace).

In the boot block, delete the nav click-binding loop and the two `setInterval` polling blocks at the end, then register the two views instead. Replace the deep-link block and the loop that binds `.nav a[data-tab]` with:

```js
    /* Navigation and polling now belong to TPRouter. This file owns two
       views and nothing else. */
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
```

Keep `loadIndices()` and `tickClock()` where they are — the index strip and clock are shell furniture, not view state, and must keep running on every tab. Keep the `setInterval` that refreshes `loadIndices()` but strip the market call out of it, since the router now owns that:

```js
    setInterval(function () {
      if (document.hidden) return;
      loadIndices();
    }, 60000);
```

- [ ] **Step 7: Run every test**

```bash
python3 -m pytest tests/test_web_routes.py -v && node --test tests/js/
```

Expected: 10 pytest PASS, 12 node PASS.

- [ ] **Step 8: Verify in the browser**

```bash
python3 prototype/app.py
```

Check each, expecting no console errors throughout:

1. `http://localhost:5050/` → Desk renders, "Desk" is the active nav item, no sub-tab bar visible.
2. Click **Market** → market table loads, hash becomes `#market`.
3. Click **Agent Floor** → sub-tab bar appears with "Quant Desk" and "Live Floor"; panes are empty (Task 5 fills them).
4. `http://localhost:5050/#market/TITAN/5y` → **the legacy bookmark test.** Market opens with the TITAN drawer at 5y range.
5. Browser back button → returns to the previous section.

- [ ] **Step 9: Commit**

```bash
git add prototype/static/desk/router.js prototype/templates/desk.html prototype/static/desk.css prototype/static/desk.js tests/test_web_routes.py
git commit -m "feat(terminal): two-level router with a view lifecycle

The nav is now rendered from a registry rather than hand-written links, so
adding a section is a one-line change and a link the router does not know
about cannot exist. Views opt into mount/refresh/unmount and declare their
own poll cadence; one timer drives all of them and skips anything hidden.

Every hook is wrapped -- a view that throws degrades to an error card
instead of taking the shell down with it.

desk.js hands over navigation and becomes a registrant like any other view."
```

---

### Task 5: Agent Floor panes

Mounts the two consoles. `src` is set on show and cleared on hide, which is what stops two one-second poll loops running behind a tab nobody is looking at — roughly 3,600 needless requests an hour against `/api/floor/live` and `/api/team/status`.

**Files:**
- Create: `prototype/static/desk/panes.js`
- Modify: `tests/test_web_routes.py`

**Interfaces:**
- Consumes: `TPRouter.register` from Task 4; the `?embed=1` URLs from Task 2.
- Produces: nothing further depends on this.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_web_routes.py`:

```python
def test_agent_floor_panes_exist(client):
    """Both panes are in the shell."""
    body = client.get("/").data
    assert b'id="view-agents-quant"' in body
    assert b'id="view-agents-floor"' in body


def test_agent_floor_frames_ship_empty(client):
    """Frames must have no src in the served HTML.

    A hardcoded src would load and start polling both consoles on every
    page load, whether or not anyone opens the section.
    """
    body = client.get("/").data
    # Assert the behaviour, not the attribute order: no framed URL may appear
    # in the served HTML at all. panes.js sets src at mount time.
    assert b"/team?embed=1" not in body
    assert b"/floor?embed=1" not in body
    assert b'id="frameQuant"' in body
    assert b'id="frameFloor"' in body


def test_panes_module_loaded(client):
    assert b"/static/desk/panes.js" in client.get("/").data
```

- [ ] **Step 2: Run to verify the third fails**

```bash
python3 -m pytest tests/test_web_routes.py -v -k "pane or frame"
```

Expected: the first two PASS (Task 4 added the markup), `test_panes_module_loaded` FAILS — the script tag exists but the file does not, so Flask serves the reference while the browser 404s. That mismatch is the point of the test.

- [ ] **Step 3: Write the panes module**

Create `prototype/static/desk/panes.js`:

```js
/* panes.js — the two Agent Floor consoles, framed.

   Why iframes: /floor and /team are self-contained documents that assume they
   own the browser. floor.html sets body{overflow:hidden}, paints scanlines via
   body::after and sizes a canvas to the viewport; team.html styles bare
   header/main/section selectors. All three stylesheets also define --bg,
   --panel and --green with DIFFERENT values, so concatenating them would let
   last-one-wins quietly restyle whichever loaded first. A frame is a document
   boundary, which is exactly the isolation those two need.

   Why unmount clears src: both poll once a second. Left mounted behind a
   hidden tab that is ~3,600 requests an hour for a screen nobody is looking
   at. about:blank tears the document down and takes its timers with it. */
(function () {
  "use strict";

  function pane(viewId, frameId, src) {
    window.TPRouter.register(viewId, {
      mount: function () {
        var f = document.getElementById(frameId);
        if (f && f.getAttribute("src") !== src) f.setAttribute("src", src);
      },
      unmount: function () {
        var f = document.getElementById(frameId);
        if (f) f.setAttribute("src", "about:blank");
      }
    });
  }

  pane("agents-quant", "frameQuant", "/team?embed=1");
  pane("agents-floor", "frameFloor", "/floor?embed=1");
})();
```

There is no `refresh` hook and no `pollMs`. The framed documents run their own poll loops; the router must not also drive them.

- [ ] **Step 4: Run every test**

```bash
python3 -m pytest tests/test_web_routes.py -v && node --test tests/js/
```

Expected: 13 pytest PASS, 12 node PASS.

- [ ] **Step 5: Verify the panes in the browser**

```bash
python3 prototype/app.py
```

1. Open `http://localhost:5050/#agents` → Quant Desk loads inside the pane, no duplicate header, no floating nav pill.
2. Click **Live Floor** → the floor console loads with its radar drawing and stats strip live.
3. Open DevTools → **Network**, filter to `floor/live`. Click back to **Quant Desk**. Expected: `api/floor/live` requests **stop entirely** within a second or two. This is the unmount working; if they continue, `src` is not being cleared.
4. Click **Desk**. Expected: both `api/floor/live` and `api/team/status` are silent.
5. Return to **Agent Floor** → the pane reloads and resumes.
6. Reload the browser on `#agents/floor` → it opens directly on Live Floor.

- [ ] **Step 6: Commit**

```bash
git add prototype/static/desk/panes.js tests/test_web_routes.py
git commit -m "feat(terminal): mount the agent floor as lazy panes

Quant Desk and Live Floor now live under one Agent Floor section. They are
framed rather than ported because both assume they own the document -- and
because desk.css, team.html and floor.html each define --bg, --panel and
--green with different values, so merging them would let last-one-wins
restyle whichever loaded first.

Hiding a pane sets src to about:blank, which tears the document down and
takes its one-second poller with it. Left mounted, the two of them are
~3,600 requests an hour against a screen nobody is looking at."
```

---

## Verification

Run both suites from the repo root:

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/test_web_routes.py -v
node --test tests/js/
```

Expected: **13 pytest passing, 12 node passing, 0 failures.**

The plan is complete when, in addition, all of the following hold in a browser against `python3 prototype/app.py`:

| | Check |
|:---:|:--|
| ☐ | `/` opens on Desk with no sub-tab bar |
| ☐ | Agent Floor shows two sub-tabs and both panes load |
| ☐ | Leaving Agent Floor stops all `api/floor/live` and `api/team/status` traffic |
| ☐ | `#market/TITAN/5y` still opens the TITAN drawer at 5y |
| ☐ | `#agents/floor` deep-links straight to Live Floor |
| ☐ | `/team` and `/floor` still work standalone, with their own chrome |
| ☐ | No console errors on any tab across two poll cycles |

## Not in this plan

Plan 2 adds the Research and Portfolio sections by absorbing `/lab`, `/decisions`, `/portfolio` and `/fleet`, and converts those routes to redirects. Plan 3 extracts F&O, US Market, Trade Lab and Ask out of `index.html` — the work that shrinks `/classic` for project C — and retires `pageswitch.js`. Neither authentication nor the client redesign belongs to any of the three; those are projects B and C.
