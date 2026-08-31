# Client Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Five screens at `/app` that render the client dashboard from the eight endpoints already serving.

**Architecture:** One template (`app.html`) with five mount points, one stylesheet carrying the light/indigo tokens and a single 900px breakpoint, and three small ES5 modules — a thin API client, the screen renderers, and the boot/nav wiring. Hash routing reuses the terminal's already-tested `static/desk/route.js` rather than adding a second parser.

**Tech Stack:** Flask + Jinja templates, vanilla ES5 JavaScript (no framework, no build step), pytest 7.4.0. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-28-client-dashboard-design.md`

## Global Constraints

- **No new runtime dependencies.** No npm, no package.json, no CDN, no framework. Vanilla ES5: `var`, no arrow functions, no template literals, no `fetch` chaining beyond `.then`.
- **No engine names, no strategy internals, no agent vocabulary.** `v4`, `composite_scorer`, `v5_size`, `alpha-hunter`, "regime" must never appear in a rendered page. A call shows *what* and *why in plain terms*, never *which engine*.
- **Never render a missing price as zero.** A position with `price_unavailable: true` shows "price unavailable", never ₹0. The portfolio total shows how many holdings it excluded.
- **Never show a hit rate without its sample size.** `/api/app/record` ships `resolved`, `is_meaningful` and `meaningful_from` alongside `hit_rate` precisely so a page can be honest. A page rendering `since` and `hit_rate` without `resolved` is the misleading case the spec forbids.
- **`since` means "recording since", not "grading since"** — label it accordingly.
- **No close button on the Book.** Add and Remove only. Closing a position hides the only id that could reopen it, and no closed-positions view exists. (Controller decision, recorded in the spec's Deferred section.)
- **One breakpoint at 900px.** Sidebar above, bottom tab bar below. No tablet-specific third layout.
- JS style: 2-space indent, double-quoted strings, `"use strict"` at the top of every module.
- Python style: 4-space indent, double-quoted strings, docstrings on functions.
- Run tests as `python3 -m pytest tests/ -q` — always scope to `tests/`. A repo-wide run fails collection on a pre-existing unrelated file (`scripts/test_baseline_protection.py` raises SystemExit).

## Verified Facts About This Codebase

Checked against the running app on 2026-08-31. Do not re-derive, and do not trust any contradicting assumption.

**Exact response shapes the screens consume:**

```
GET /api/app/calls        -> {"calls": [ <call> ], "limit": 50, "as_of": "2026-08-31T09:55:47"}
GET /api/app/calls/<id>   -> <call>   (404 {"error": "no such call"} if unknown)
GET /api/app/record       -> {"total","resolved","hit","miss","ungraded","open",
                              "hit_rate","since","meaningful_from","is_meaningful"}
GET /api/app/positions    -> {"positions": [ <position> ], "totals": {...}}
GET /api/app/me           -> {"user_id","plan"}

<call>     = {id, symbol, side, published_at, price_at_call, score, signal,
              horizon, target, stop, outcome, outcome_price, outcome_at}
<position> = {id, user_id, symbol, qty, avg_price, opened_at, closed_at, exit_price,
              source, broker_ref, call_id, last_price, value, pnl, pnl_pct,
              price_unavailable}
<totals>   = {value, pnl, priced, unpriced}
```

| Fact | Value |
|:--|:--|
| `hit_rate` | `null` when `resolved` is 0 — never `0.0`. Must render as "not yet", never "0%". |
| `is_meaningful` | `resolved >= 100`. Currently `false` even at 100% hit rate over 1 call. |
| `since` | First call ever **recorded**, not first resolved. |
| `price_unavailable` | `true` means `last_price`, `value`, `pnl`, `pnl_pct` are all `null`. |
| `signal` | Plain English already, e.g. `"ORB breakout above 1408; Price +1.55% above VWAP"`. Render as-is. |
| `outcome` | `open` / `hit` / `miss` / `ungraded`. |
| Auth today | `current_user()` is a stub returning `"demo-user"`, so gated endpoints answer 200 in the browser. The signed-out states must still be built and are verified by forcing a 401 in the checklist. |
| Existing router | `prototype/static/desk/route.js` is pure and already covered by 12 node tests. `TPRoute.parse(hash, sections)`, `TPRoute.build(section, sub, rest)`, `TPRoute.viewIdFor(section, sub)`. **Reuse it.** |
| Terminal file sizes | `desk.html` 157 lines, `desk.css` 275, `desk.js` 495 — the yardstick for what "too big" looks like here. |
| Route to add | `/app`. `/` serves the terminal, `/classic` the old dashboard. Neither changes. |

## File Structure

| File | Responsibility |
|:--|:--|
| `prototype/templates/app.html` | **new** — the shell: header, sidebar, bottom nav, and five empty mount points. No inline JS. |
| `prototype/static/app.css` | **new** — light/indigo tokens, card and table primitives, and the single 900px breakpoint. |
| `prototype/static/app/api.js` | **new** — one function per endpoint, returning promises. The only place `fetch` appears. |
| `prototype/static/app/screens.js` | **new** — one render function per screen. Pure DOM building from a payload; no fetching. |
| `prototype/static/app/main.js` | **new** — boot, nav rendering, hash routing **through `TPRoute`** (`parse` and `build`, never a hand-rolled parser), and wiring screens to the API. |
| `prototype/app.py` | **modify, 1 line** — serve `/app`. |
| `prototype/client_api.py` | **modify, 1 line** — drop `user_id` from `POSITION_FIELDS`. |
| `tests/test_app_screens.py` | **new** — served-HTML and module-fetch assertions. |
| `docs/APP_MANUAL_CHECKS.md` | **new** — the browser checklist, because none of the rendering is testable here. |

**Why the render functions are separate from the fetching.** `screens.js` takes a payload and returns DOM. That is the only part with logic worth reading twice, and keeping `fetch` out of it means a future test harness (or a person in a console) can call a renderer with a fixture and see the output.

**What this plan can and cannot verify.** There is no DOM in the test environment and adding jsdom would breach the no-new-dependencies constraint. So the pytest suite proves the route serves, every module is actually fetchable (not merely referenced), and no banned vocabulary appears in the served HTML. Everything about rendering is verified by hand against `docs/APP_MANUAL_CHECKS.md`. That split is stated here so nobody mistakes a green suite for a working page.

---

### Task 1: The shell — route, template, stylesheet, navigation

**Files:**
- Create: `prototype/templates/app.html`
- Create: `prototype/static/app.css`
- Create: `prototype/static/app/main.js`
- Modify: `prototype/app.py` (one route)
- Create: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `window.TPRoute` from `/static/desk/route.js` — `parse(hash, sections)`, `build(section, sub, rest)`, `viewIdFor(section, sub)`.
- Produces:
  - `window.TPApp.SECTIONS` → array of `{id, label}` for the five screens.
  - `window.TPApp.go(section)` → shows one screen, hides the rest, updates nav.
  - `window.TPApp.boot()` → renders nav, wires `hashchange`, shows the screen named by the current hash.
  - Mount point ids: `view-home`, `view-calls`, `view-call`, `view-book`, `view-record`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_app_screens.py`:

```python
"""The client dashboard's served surface.

None of the rendering is testable here -- there is no DOM, and adding one
would breach the no-new-dependencies constraint. What these tests can prove is
that the route serves, that every module referenced is actually fetchable, and
that operator vocabulary never reaches a client's page. Everything else lives
in docs/APP_MANUAL_CHECKS.md and is checked by hand.
"""
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def test_app_route_serves(client):
    assert client.get("/app").status_code == 200


def test_every_module_the_page_references_is_fetchable(client):
    """Fetch them, do not merely grep for the <script src>.

    A tag can name a file that 404s -- that is exactly how a tab shipped blank
    on 2026-08-03. Asserting the string appears in the HTML proves only that
    somebody typed it.
    """
    for path in ("/static/desk/route.js", "/static/app/api.js",
                 "/static/app/screens.js", "/static/app/main.js",
                 "/static/app.css"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert len(r.data) > 0, path


def test_all_five_mount_points_exist(client):
    body = client.get("/app").get_data(as_text=True)
    for view in ("view-home", "view-calls", "view-call", "view-book", "view-record"):
        assert view in body, view


def test_module_order_is_load_bearing(client):
    """route.js defines TPRoute; main.js uses it. Order is not cosmetic."""
    body = client.get("/app").get_data(as_text=True)
    assert body.index("desk/route.js") < body.index("app/main.js")
    assert body.index("app/api.js") < body.index("app/main.js")
    assert body.index("app/screens.js") < body.index("app/main.js")


def test_the_router_is_reused_not_reimplemented(client):
    """main.js must go through TPRoute, not hand-roll a second parser.

    route.js is pure and already carries twelve node tests. A second parser
    would be a second thing to get wrong, and the load-order test alone does
    not prove the dependency is actually used.
    """
    js = client.get("/static/app/main.js").get_data(as_text=True)
    assert "TPRoute.parse" in js
    assert "TPRoute.build" in js


def test_no_operator_vocabulary_reaches_the_page(client):
    """A client sees what was called, never which engine said so."""
    body = client.get("/app").get_data(as_text=True).lower()
    for word in ("v4", "v5_size", "composite_scorer", "alpha-hunter",
                 "regime", "orchestrator", "sprint"):
        assert word not in body, word


def test_the_terminal_and_classic_are_untouched(client):
    """/app is additive. Neither existing surface changes."""
    assert client.get("/").status_code == 200
    assert client.get("/classic").status_code == 200


def test_no_inline_script_in_the_template(client):
    """Every script tag is src-only. Inline JS cannot be cached or linted."""
    body = client.get("/app").get_data(as_text=True)
    for chunk in body.split("<script")[1:]:
        head = chunk.split(">")[0]
        assert "src=" in head, "inline <script> found: " + head[:60]
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/test_app_screens.py -q
```

Expected: failures — `/app` 404s.

- [ ] **Step 3: Add the route**

In `prototype/app.py`, directly after the existing `/classic` route, add:

```python
@app.route("/app")
def client_app():
    """The client dashboard. Additive -- / and /classic are unchanged."""
    return render_template("app.html")
```

- [ ] **Step 4: Write the template**

Create `prototype/templates/app.html`:

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TradePilot</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>

<header class="topbar">
  <div class="brand"><span class="mark"></span> TradePilot</div>
  <div class="who" id="who"></div>
</header>

<div class="shell">
  <nav class="sidenav" id="sidenav"></nav>

  <main class="content">
    <section class="view" id="view-home"></section>
    <section class="view" id="view-calls"></section>
    <section class="view" id="view-call"></section>
    <section class="view" id="view-book"></section>
    <section class="view" id="view-record"></section>
  </main>
</div>

<nav class="tabbar" id="tabbar"></nav>

<script src="/static/desk/route.js" defer></script>
<script src="/static/app/api.js" defer></script>
<script src="/static/app/screens.js" defer></script>
<script src="/static/app/main.js" defer></script>
</body>
</html>
```

- [ ] **Step 5: Write the stylesheet**

Create `prototype/static/app.css`:

```css
/* Client dashboard. Light ground, white cards, indigo accent -- the language
   Indian retail already trusts. One breakpoint at 900px: sidebar above,
   bottom tab bar below. There is deliberately no tablet-specific third
   layout; the middle one gets tested least and breaks quietest. */

:root {
  --bg: #F7F8FB;
  --card: #ffffff;
  --line: #E8EAF0;
  --line-soft: #F0F1F5;
  --ink: #12141C;
  --ink-2: #6B7280;
  --ink-3: #9AA0AE;
  --accent: #4f46e5;
  --accent-soft: #EEF0FE;
  --up: #16A34A;
  --up-soft: #DCFCE7;
  --down: #DC2626;
  --down-soft: #FEE2E2;
  --r: 12px;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
}

.topbar {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 18px;
  background: var(--card);
  border-bottom: 1px solid var(--line);
}
.brand { display: flex; align-items: center; gap: 8px; font-weight: 700; letter-spacing: -.2px; }
.mark {
  width: 22px; height: 22px; border-radius: 7px;
  background: linear-gradient(135deg, var(--accent), #7c6bff);
}
.who { margin-left: auto; font-size: 12px; color: var(--ink-2); }

.shell { display: flex; align-items: flex-start; }

.sidenav { display: none; }
.sidenav a {
  display: block; padding: 8px 14px;
  color: var(--ink-2); text-decoration: none; font-size: 13px;
  border-left: 2px solid transparent;
}
.sidenav a.on {
  color: var(--accent); font-weight: 700;
  background: var(--accent-soft); border-left-color: var(--accent);
}

.content { flex: 1; padding: 14px; max-width: 980px; padding-bottom: 76px; }

.view { display: none; }
.view.on { display: block; }

.card {
  background: var(--card); border: 1px solid var(--line);
  border-radius: var(--r); padding: 14px; margin-bottom: 10px;
}
.card h2 { margin: 0 0 8px; font-size: 13px; letter-spacing: -.1px; }

.kpis { display: grid; grid-template-columns: 1fr; gap: 10px; }

.label { font-size: 10px; text-transform: uppercase; letter-spacing: .4px; color: var(--ink-2); }
.big { font-size: 24px; font-weight: 700; letter-spacing: -.7px; }
.up { color: var(--up); } .down { color: var(--down); }
.muted { color: var(--ink-2); font-size: 12px; }
.thin { color: var(--ink-3); font-size: 11px; }

.pill {
  font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 20px;
  background: var(--up-soft); color: #15803D;
}
.pill.sell { background: var(--down-soft); color: #B91C1C; }

.row {
  display: flex; align-items: center; gap: 9px;
  padding: 10px 0; border-bottom: 1px solid var(--line-soft);
}
.row:last-child { border-bottom: 0; }
.row .grow { flex: 1; min-width: 0; }
.row .name { font-weight: 600; }

.btn {
  font: inherit; font-size: 12px; padding: 7px 12px;
  border: 1px solid var(--line); border-radius: 8px;
  background: var(--card); color: var(--ink); cursor: pointer;
}
.btn.primary { background: var(--accent); border-color: var(--accent); color: #fff; font-weight: 600; }
.btn.quiet { color: var(--ink-2); }

.empty { padding: 22px 14px; text-align: center; color: var(--ink-2); }
.empty .big { font-size: 15px; color: var(--ink); margin-bottom: 4px; }

.tabbar {
  position: fixed; left: 0; right: 0; bottom: 0;
  display: flex; background: var(--card); border-top: 1px solid var(--line);
  padding: 7px 0;
}
.tabbar a {
  flex: 1; text-align: center; text-decoration: none;
  color: var(--ink-3); font-size: 10px;
}
.tabbar a.on { color: var(--accent); font-weight: 700; }

/* Above 900px: sidebar replaces the tab bar, KPIs go two-up. Below it, the
   page is a single column and the tab bar is the navigation. */
@media (min-width: 900px) {
  .sidenav {
    display: block; width: 150px; flex-shrink: 0;
    padding: 14px 0; position: sticky; top: 0;
  }
  .tabbar { display: none; }
  .content { padding: 18px; padding-bottom: 18px; }
  .kpis { grid-template-columns: 1fr 1fr; }
}
```

- [ ] **Step 6: Write the boot module**

Create `prototype/static/app/main.js`:

```javascript
"use strict";

/* Boot, navigation and routing for the client dashboard.
   Hash routing reuses window.TPRoute from /static/desk/route.js, which is pure
   and already covered by twelve node tests -- a second parser would be a
   second thing to get wrong. */

(function () {
  var SECTIONS = [
    { id: "home",   label: "Home" },
    { id: "calls",  label: "Calls" },
    { id: "book",   label: "Book" },
    { id: "record", label: "Record" }
  ];

  /* `call` has a mount point and a route but no nav entry -- it is reached by
     tapping a call, never from the navigation. */
  var ROUTABLE = SECTIONS.concat([{ id: "call", label: null }]);

  var cur = null;

  function el(id) { return document.getElementById(id); }

  function renderNav() {
    var side = el("sidenav");
    var tabs = el("tabbar");
    if (!side || !tabs) return;
    side.innerHTML = "";
    tabs.innerHTML = "";
    for (var i = 0; i < SECTIONS.length; i++) {
      var s = SECTIONS[i];
      var a = document.createElement("a");
      a.href = "#" + s.id;
      a.textContent = s.label;
      if (s.id === cur) a.className = "on";
      side.appendChild(a);

      var t = document.createElement("a");
      t.href = "#" + s.id;
      t.textContent = s.label;
      if (s.id === cur) t.className = "on";
      tabs.appendChild(t);
    }
  }

  function show(section, rest) {
    var all = ROUTABLE;
    for (var i = 0; i < all.length; i++) {
      var node = el("view-" + all[i].id);
      if (node) node.className = "view" + (all[i].id === section ? " on" : "");
    }
    if (window.TPApp.onShow) window.TPApp.onShow(section, rest || []);
  }

  function go(section, rest, replace) {
    var known = false;
    for (var i = 0; i < ROUTABLE.length; i++) {
      if (ROUTABLE[i].id === section) known = true;
    }
    if (!known) section = "home";
    cur = section;
    renderNav();
    show(section, rest);

    var hash = window.TPRoute.build(section, null, rest || []);
    if (location.hash === hash) return;
    /* Normalising must not push a history entry -- otherwise Back lands on the
       un-normalised URL, we normalise again, and the user is trapped. */
    if (replace && history.replaceState) history.replaceState(null, "", hash);
    else location.hash = hash;
  }

  /* Sections in the shape TPRoute expects. None of the client screens has
     sub-tabs, so every subs list is empty -- but going through TPRoute means
     one parser, already covered by twelve node tests, instead of two. */
  var ROUTE_SECTIONS = (function () {
    var out = [];
    for (var i = 0; i < ROUTABLE.length; i++) {
      out.push({ id: ROUTABLE[i].id, subs: [] });
    }
    return out;
  })();

  function parseHash() {
    var parsed = window.TPRoute.parse(location.hash, ROUTE_SECTIONS);
    return { section: parsed.section, rest: parsed.rest || [] };
  }

  function boot() {
    var p = parseHash();
    go(p.section, p.rest, true);
    window.addEventListener("hashchange", function () {
      var q = parseHash();
      go(q.section, q.rest, true);
    });
  }

  window.TPApp = { SECTIONS: SECTIONS, go: go, boot: boot, onShow: null };
})();

document.addEventListener("DOMContentLoaded", function () {
  window.TPApp.boot();
});
```

- [ ] **Step 7: Run to verify they pass**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: 8 passed.

- [ ] **Step 8: Confirm the whole suite still passes, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/templates/app.html prototype/static/app.css prototype/static/app/main.js prototype/app.py tests/test_app_screens.py
git commit -m "feat(app): the client shell -- route, nav, and one breakpoint

Sidebar above 900px, bottom tab bar below, no tablet-specific third layout.
Hash routing reuses the terminal's route.js rather than adding a second
parser: it is pure, already covered by twelve node tests, and a second one
would be a second thing to get wrong.

Normalising the hash uses replaceState, not assignment, so loading /app does
not push a history entry the Back button then bounces off."
```

---

### Task 2: The API client and the Home screen

**Files:**
- Create: `prototype/static/app/api.js`
- Create: `prototype/static/app/screens.js`
- Modify: `prototype/static/app/main.js` (wire `onShow`)
- Modify: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `window.TPApp.onShow`, mount point `view-home`.
- Produces:
  - `window.TPApi.calls(limit)` → promise of `{calls, limit, as_of}`
  - `window.TPApi.call(id)` → promise of one call, rejects on 404
  - `window.TPApi.record()` → promise of the record object
  - `window.TPApi.positions()` → promise of `{positions, totals}`, rejects with `{status: 401}` when signed out
  - `window.TPApi.addPosition(body)` / `window.TPApi.removePosition(id)`
  - `window.TPScreens.home(node, data)` where `data` is `{record, calls, book, signedOut}`
  - `window.TPScreens.money(n)` → `"₹12,48,300"`, and `window.TPScreens.pct(n)` → `"3.5%"`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_screens.py`:

```python
def test_api_module_names_every_endpoint_it_needs(client):
    """A screen that calls a path the module never defines fails silently."""
    js = client.get("/static/app/api.js").get_data(as_text=True)
    for path in ("/api/app/calls", "/api/app/record", "/api/app/positions"):
        assert path in js, path


def test_api_module_is_the_only_place_fetch_appears(client):
    """Keeping fetch out of the renderers is what makes them inspectable."""
    screens = client.get("/static/app/screens.js").get_data(as_text=True)
    main = client.get("/static/app/main.js").get_data(as_text=True)
    assert "fetch(" not in screens
    assert "fetch(" not in main


def test_screens_module_handles_the_unavailable_price_flag(client):
    """A missing quote must never render as zero."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "price_unavailable" in js


def test_screens_module_never_prints_a_bare_hit_rate(client):
    """The spec forbids a rate without its sample size."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "resolved" in js
    assert "is_meaningful" in js
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: failures — `/static/app/api.js` and `screens.js` 404.

- [ ] **Step 3: Write the API client**

Create `prototype/static/app/api.js`:

```javascript
"use strict";

/* The only place fetch appears. Every screen takes a payload and renders it,
   which keeps the rendering inspectable from a console with a fixture. */

(function () {
  function json(url, opts) {
    return fetch(url, opts || {}).then(function (r) {
      if (r.status === 401) return Promise.reject({ status: 401 });
      if (!r.ok) return Promise.reject({ status: r.status });
      return r.json();
    });
  }

  function post(url, body) {
    return json(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  }

  window.TPApi = {
    calls: function (limit) {
      return json("/api/app/calls?limit=" + (limit || 50));
    },
    call: function (id) {
      return json("/api/app/calls/" + encodeURIComponent(id));
    },
    record: function () {
      return json("/api/app/record");
    },
    positions: function () {
      return json("/api/app/positions");
    },
    addPosition: function (body) {
      return post("/api/app/positions", body);
    },
    removePosition: function (id) {
      return fetch("/api/app/positions/" + encodeURIComponent(id),
                   { method: "DELETE" }).then(function (r) {
        if (r.status === 401) return Promise.reject({ status: 401 });
        if (!r.ok && r.status !== 204) return Promise.reject({ status: r.status });
        return true;
      });
    }
  };
})();
```

- [ ] **Step 4: Write the screens module with Home**

Create `prototype/static/app/screens.js`:

```javascript
"use strict";

/* One render function per screen. Each takes a node and a payload and builds
   DOM -- no fetching, so a renderer can be driven from a console with a
   fixture. */

(function () {
  function money(n) {
    if (n === null || n === undefined) return "--";
    var neg = n < 0;
    var s = Math.round(Math.abs(n)).toString();
    /* Indian grouping: last three digits, then pairs. */
    var last3 = s.slice(-3);
    var rest = s.slice(0, -3);
    if (rest) last3 = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + last3;
    return (neg ? "-₹" : "₹") + last3;
  }

  function pct(n) {
    if (n === null || n === undefined) return "--";
    return (n > 0 ? "+" : "") + n.toFixed(1) + "%";
  }

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }

  function card(title) {
    var c = el("div", "card");
    if (title) c.appendChild(el("h2", null, title));
    return c;
  }

  /* The rate is never shown alone. resolved and is_meaningful ship in the same
     payload precisely so a page cannot honestly print 62% without also
     printing that it is eleven calls. */
  function rateLine(rec) {
    var wrap = el("div");
    if (rec.hit_rate === null) {
      wrap.appendChild(el("div", "big", "--"));
      wrap.appendChild(el("div", "muted", rec.total
        ? "nothing has resolved yet"
        : "no calls recorded yet"));
      return wrap;
    }
    wrap.appendChild(el("div", "big " + (rec.hit_rate >= 50 ? "up" : "down"),
                        rec.hit_rate.toFixed(1) + "%"));
    wrap.appendChild(el("div", "muted",
      rec.resolved + " resolved of " + rec.total + " recorded"));
    if (!rec.is_meaningful) {
      wrap.appendChild(el("div", "thin",
        "Too few to be meaningful -- we show a rate from " +
        rec.meaningful_from + "."));
    }
    return wrap;
  }

  function callRow(c, onOpen) {
    var row = el("div", "row");
    var grow = el("div", "grow");
    grow.appendChild(el("div", "name", c.symbol));
    grow.appendChild(el("div", "thin", c.signal || ""));
    row.appendChild(grow);

    var right = el("div");
    right.style.textAlign = "right";
    right.appendChild(el("div", null, money(c.price_at_call)));
    var pill = el("span", "pill" + (c.side === "SELL" ? " sell" : ""),
                  c.side + (c.score ? " " + Math.round(c.score) : ""));
    right.appendChild(pill);
    row.appendChild(right);

    if (onOpen) {
      row.style.cursor = "pointer";
      row.addEventListener("click", function () { onOpen(c.id); });
    }
    return row;
  }

  function home(node, data) {
    node.innerHTML = "";

    var kpis = el("div", "kpis");

    var value = card(null);
    value.appendChild(el("div", "label", "Your portfolio"));
    if (data.signedOut) {
      value.appendChild(el("div", "big", "--"));
      value.appendChild(el("div", "muted", "Sign in to see your book"));
    } else if (!data.book || !data.book.positions.length) {
      value.appendChild(el("div", "big", "--"));
      value.appendChild(el("div", "muted", "Log your first trade to see it here"));
    } else {
      var t = data.book.totals;
      value.appendChild(el("div", "big", money(t.value)));
      value.appendChild(el("div", "muted " + (t.pnl >= 0 ? "up" : "down"),
                           money(t.pnl) + " overall"));
      if (t.unpriced) {
        value.appendChild(el("div", "thin",
          t.unpriced + " holding(s) have no live price and are not counted"));
      }
    }
    kpis.appendChild(value);

    var rate = card(null);
    rate.appendChild(el("div", "label", "Hit rate"));
    rate.appendChild(rateLine(data.record));
    kpis.appendChild(rate);
    node.appendChild(kpis);

    var calls = card("Today's calls");
    if (!data.calls || !data.calls.calls.length) {
      calls.appendChild(el("div", "empty", "No calls published yet."));
    } else {
      for (var i = 0; i < Math.min(data.calls.calls.length, 5); i++) {
        calls.appendChild(callRow(data.calls.calls[i], data.onOpenCall));
      }
    }
    node.appendChild(calls);
  }

  window.TPScreens = {
    money: money, pct: pct, el: el, card: card,
    rateLine: rateLine, callRow: callRow, home: home
  };
})();
```

- [ ] **Step 5: Wire Home into the router**

At the bottom of `prototype/static/app/main.js`, before the closing `})();`, replace `window.TPApp = { ... }` with the same object plus this loader, and set `onShow`:

```javascript
  function loadHome() {
    var node = el("view-home");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    Promise.all([
      window.TPApi.record(),
      window.TPApi.calls(5),
      window.TPApi.positions().then(
        function (b) { return { book: b, signedOut: false }; },
        function (e) { return { book: null, signedOut: e && e.status === 401 }; })
    ]).then(function (r) {
      window.TPScreens.home(node, {
        record: r[0], calls: r[1], book: r[2].book,
        signedOut: r[2].signedOut,
        onOpenCall: function (id) { window.TPApp.go("call", [id]); }
      });
    }, function () {
      node.innerHTML = "";
      node.appendChild(window.TPScreens.el(
        "div", "empty", "Could not load. Reload the page."));
    });
  }

  window.TPApp = {
    SECTIONS: SECTIONS, go: go, boot: boot,
    onShow: function (section) {
      if (section === "home") loadHome();
    }
  };
```

Note the positions promise is caught individually rather than letting a 401 reject the whole `Promise.all` — a signed-out visitor must still see the calls and the hit rate, because that is the entire acquisition surface.

- [ ] **Step 6: Run to verify they pass**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: 12 passed.

- [ ] **Step 7: Confirm the whole suite passes, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/static/app/api.js prototype/static/app/screens.js prototype/static/app/main.js tests/test_app_screens.py
git commit -m "feat(app): the API client and the Home screen

Three states, not two: signed out, signed in with an empty book, and signed
in with holdings. A signed-out visitor still sees the calls and the hit rate
-- the positions promise is caught on its own rather than being allowed to
reject the whole batch, because that half is the acquisition surface.

The rate is never rendered alone. resolved, total and is_meaningful ship in
the same payload so the page cannot print a percentage without also printing
how few calls it stands on."
```

---

### Task 3: Calls and call detail

**Files:**
- Modify: `prototype/static/app/screens.js`
- Modify: `prototype/static/app/main.js`
- Modify: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `TPScreens.callRow`, `TPScreens.card`, `TPApi.calls`, `TPApi.call`.
- Produces:
  - `window.TPScreens.calls(node, data)` where `data` is `{calls, onOpenCall}`
  - `window.TPScreens.call(node, data)` where `data` is `{call, onBack}` or `{error: true}`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_screens.py`:

```python
def test_calls_screen_stamps_the_data_it_is_showing(client):
    """Outside market hours the list is stale; the page must say when."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "as_of" in js


def test_call_detail_distinguishes_open_from_resolved(client):
    """A live call must not imply an outcome that has not happened."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    for token in ("outcome", "hit", "miss", "ungraded"):
        assert token in js, token
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: 2 failures — `as_of` and the outcome tokens are absent.

- [ ] **Step 3: Add both renderers**

In `prototype/static/app/screens.js`, add before the `window.TPScreens = {...}` assignment:

```javascript
  function stamp(iso) {
    if (!iso) return "";
    return iso.replace("T", " ").slice(0, 16);
  }

  function calls(node, data) {
    node.innerHTML = "";
    var c = card("Published calls");
    var list = (data.calls && data.calls.calls) || [];
    if (!list.length) {
      c.appendChild(el("div", "empty", "No calls published yet."));
    } else {
      for (var i = 0; i < list.length; i++) {
        c.appendChild(callRow(list[i], data.onOpenCall));
      }
      /* Outside market hours this list is the last session's. Saying so is
         cheaper than a support question about why it has not moved. */
      c.appendChild(el("div", "thin", "As of " + stamp(data.calls.as_of)));
    }
    node.appendChild(c);
  }

  function outcomeLine(c) {
    if (c.outcome === "open") {
      return el("div", "muted", "Still open -- no outcome yet.");
    }
    if (c.outcome === "ungraded") {
      return el("div", "muted",
        "Published without a target, so it is not graded and not counted.");
    }
    var moved = (c.outcome_price !== null && c.price_at_call)
      ? ((c.outcome_price - c.price_at_call) / c.price_at_call) * 100 : null;
    var line = el("div", "muted " + (c.outcome === "hit" ? "up" : "down"),
      (c.outcome === "hit" ? "Hit" : "Missed") +
      (c.outcome_price !== null ? " at " + money(c.outcome_price) : "") +
      (moved !== null ? " (" + pct(moved) + ")" : ""));
    return line;
  }

  function call(node, data) {
    node.innerHTML = "";
    if (data.error || !data.call) {
      var miss = card(null);
      miss.appendChild(el("div", "empty", "That call could not be found."));
      var back0 = el("button", "btn", "Back to calls");
      back0.addEventListener("click", data.onBack);
      miss.appendChild(back0);
      node.appendChild(miss);
      return;
    }
    var c = data.call;
    var head = card(null);
    head.appendChild(el("div", "label", stamp(c.published_at)));
    head.appendChild(el("div", "big", c.symbol));
    head.appendChild(el("span", "pill" + (c.side === "SELL" ? " sell" : ""),
                        c.side + (c.score ? " " + Math.round(c.score) : "")));
    head.appendChild(outcomeLine(c));
    node.appendChild(head);

    var why = card("Why it fired");
    why.appendChild(el("div", null, c.signal || "No reason recorded."));
    node.appendChild(why);

    var levels = card("Levels published with the call");
    var rows = [["Price at call", money(c.price_at_call)],
                ["Target", c.target === null ? "none published" : money(c.target)],
                ["Stop", c.stop === null ? "none published" : money(c.stop)],
                ["Horizon", c.horizon || "--"]];
    for (var i = 0; i < rows.length; i++) {
      var r = el("div", "row");
      r.appendChild(el("div", "grow muted", rows[i][0]));
      r.appendChild(el("div", null, rows[i][1]));
      levels.appendChild(r);
    }
    node.appendChild(levels);

    var back = el("button", "btn quiet", "Back to calls");
    back.addEventListener("click", data.onBack);
    node.appendChild(back);
  }
```

Then add `calls: calls, call: call, stamp: stamp` to the `window.TPScreens` object.

- [ ] **Step 4: Wire both screens**

In `prototype/static/app/main.js`, add these loaders beside `loadHome`, and extend `onShow`:

```javascript
  function loadCalls() {
    var node = el("view-calls");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    window.TPApi.calls(50).then(function (c) {
      window.TPScreens.calls(node, {
        calls: c,
        onOpenCall: function (id) { window.TPApp.go("call", [id]); }
      });
    }, function () {
      node.innerHTML = "";
      node.appendChild(window.TPScreens.el(
        "div", "empty", "Could not load calls. Reload the page."));
    });
  }

  function loadCall(id) {
    var node = el("view-call");
    if (!node) return;
    var back = function () { window.TPApp.go("calls", []); };
    if (!id) { window.TPScreens.call(node, { error: true, onBack: back }); return; }
    node.innerHTML = "<div class='empty'>Loading…</div>";
    window.TPApi.call(id).then(function (c) {
      window.TPScreens.call(node, { call: c, onBack: back });
    }, function () {
      window.TPScreens.call(node, { error: true, onBack: back });
    });
  }
```

and in `onShow`:

```javascript
    onShow: function (section, rest) {
      if (section === "home") loadHome();
      else if (section === "calls") loadCalls();
      else if (section === "call") loadCall(rest && rest[0]);
    }
```

- [ ] **Step 5: Run to verify they pass, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/static/app/screens.js prototype/static/app/main.js tests/test_app_screens.py
git commit -m "feat(app): the calls list and one call's reasoning

A live call says it is still open rather than implying an outcome. An
ungraded call says it was published without a target and is not counted --
the same distinction the record endpoint makes, surfaced where a client can
see it rather than buried in an aggregate.

The list carries an as-of stamp because outside market hours it is the last
session's, and saying so is cheaper than the support question."
```

---

### Task 4: The track record

**Files:**
- Modify: `prototype/static/app/screens.js`
- Modify: `prototype/static/app/main.js`
- Modify: `tests/test_app_screens.py`

**Interfaces:**
- Consumes: `TPScreens.rateLine` and `TPScreens.stamp` (both from earlier tasks), `TPApi.record`, `TPApi.calls`.
- Produces: `window.TPScreens.record(node, data)` where `data` is `{record, calls}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_app_screens.py`:

```python
def test_record_screen_labels_since_as_recording_not_grading(client):
    """`since` is the first call RECORDED, not the first resolved.

    "Track record since January -- 62%" where the first call resolved in June
    overstates the record's age. The spec's Deferred section makes this a
    constraint on this screen, not on the API.
    """
    js = client.get("/static/app/screens.js").get_data(as_text=True).lower()
    assert "recording since" in js
```

- [ ] **Step 2: Run to verify it fails**

```bash
python3 -m pytest tests/test_app_screens.py -q
```

Expected: 1 failure — the phrase is absent.

- [ ] **Step 3: Add the renderer**

In `prototype/static/app/screens.js`, add before the exports:

```javascript
  function record(node, data) {
    node.innerHTML = "";
    var rec = data.record;

    var head = card("Track record");
    head.appendChild(rateLine(rec));
    /* "since" is the first call RECORDED, not the first resolved. Labelling it
       "recording since" keeps the page from implying the rate has been earned
       across that whole span. */
    head.appendChild(el("div", "thin", rec.since
      ? "Recording since " + rec.since
      : "Nothing recorded yet."));
    node.appendChild(head);

    var split = card("How the calls stand");
    var rows = [["Hit", rec.hit], ["Missed", rec.miss],
                ["Still open", rec.open],
                ["Ungraded (no target published)", rec.ungraded]];
    for (var i = 0; i < rows.length; i++) {
      var r = el("div", "row");
      r.appendChild(el("div", "grow muted", rows[i][0]));
      r.appendChild(el("div", null, rows[i][1]));
      split.appendChild(r);
    }
    split.appendChild(el("div", "thin",
      "Ungraded calls are excluded from the rate -- a call published without " +
      "a target has no standard to be graded against."));
    node.appendChild(split);

    var list = (data.calls && data.calls.calls) || [];
    var resolved = [];
    for (var j = 0; j < list.length; j++) {
      if (list[j].outcome === "hit" || list[j].outcome === "miss") {
        resolved.push(list[j]);
      }
    }
    var recent = card("Resolved calls");
    if (!resolved.length) {
      recent.appendChild(el("div", "empty", "Nothing has resolved yet."));
    } else {
      for (var k = 0; k < resolved.length; k++) {
        var c = resolved[k];
        var row = el("div", "row");
        var grow = el("div", "grow");
        grow.appendChild(el("div", "name", c.symbol));
        grow.appendChild(el("div", "thin", stamp(c.published_at)));
        row.appendChild(grow);
        row.appendChild(el("div", "muted " + (c.outcome === "hit" ? "up" : "down"),
                           c.outcome === "hit" ? "Hit" : "Missed"));
        recent.appendChild(row);
      }
    }
    node.appendChild(recent);
  }
```

Add `record: record` to the exports.

- [ ] **Step 4: Wire it**

In `prototype/static/app/main.js`:

```javascript
  function loadRecord() {
    var node = el("view-record");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    Promise.all([window.TPApi.record(), window.TPApi.calls(50)])
      .then(function (r) {
        window.TPScreens.record(node, { record: r[0], calls: r[1] });
      }, function () {
        node.innerHTML = "";
        node.appendChild(window.TPScreens.el(
          "div", "empty", "Could not load the record. Reload the page."));
      });
  }
```

and add `else if (section === "record") loadRecord();` to `onShow`.

- [ ] **Step 5: Run to verify it passes, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/static/app/screens.js prototype/static/app/main.js tests/test_app_screens.py
git commit -m "feat(app): the track record, labelled honestly

'Recording since' rather than a bare 'since'. The API's since field is the
first call recorded, not the first resolved, so a page saying 'since January
-- 62%' where the first call resolved in June overstates the record's age.
The spec makes that a constraint on this screen rather than on the API.

Ungraded calls are shown and explained rather than hidden: excluding them
from the rate is defensible, excluding them silently is not."
```

---

### Task 5: The book

**Files:**
- Modify: `prototype/static/app/screens.js`
- Modify: `prototype/static/app/main.js`
- Modify: `prototype/client_api.py` (one line — drop `user_id` from the payload)
- Modify: `tests/test_app_screens.py`
- Modify: `tests/test_client_api_positions.py`

**Interfaces:**
- Consumes: `TPApi.positions`, `TPApi.addPosition`, `TPApi.removePosition`.
- Produces: `window.TPScreens.book(node, data)` where `data` is `{book, signedOut, onAdd, onRemove}`.

**There is deliberately no close action.** `PATCH {"closed_at": ...}` hides a position from the only endpoint that can discover its id, and no closed-positions view exists — so closing is unrecoverable through the API. Add and Remove only. This is a recorded controller decision; do not add a Close button.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_app_screens.py`:

```python
def test_book_never_renders_a_missing_price_as_zero(client):
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "price unavailable" in js.lower()


def test_book_shows_provenance_for_each_position(client):
    """Which holdings came from a call, and which were the client's own."""
    js = client.get("/static/app/screens.js").get_data(as_text=True)
    assert "call_id" in js
    assert "your own" in js.lower()


def test_book_has_no_close_action(client):
    """Closing hides the only id that could reopen it. Add and Remove only."""
    js = client.get("/static/app/screens.js").get_data(as_text=True).lower()
    assert "closed_at" not in js
```

And append to `tests/test_client_api_positions.py`:

```python
def test_positions_do_not_leak_the_internal_user_id(client, store):
    """A client has no use for their own internal identifier.

    Harmless while it is a stub; once accounts land it is the app's internal
    key for that person, handed to the browser for no reason any screen needs.
    """
    _post(client)
    pos = client.get("/api/app/positions").get_json()["positions"][0]
    assert "user_id" not in pos
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_app_screens.py tests/test_client_api_positions.py -q
```

Expected: 4 failures.

- [ ] **Step 3: Drop `user_id` from the API payload**

In `prototype/client_api.py`, remove `"user_id"` from `POSITION_FIELDS` so it reads:

```python
POSITION_FIELDS = ("id", "symbol", "qty", "avg_price", "opened_at",
                   "closed_at", "exit_price", "source", "broker_ref", "call_id")
```

Queries still scope by `user_id` — only the response stops carrying it.

- [ ] **Step 4: Add the renderer**

In `prototype/static/app/screens.js`, add before the exports:

```javascript
  function positionRow(p, onRemove) {
    var row = el("div", "row");
    var grow = el("div", "grow");
    grow.appendChild(el("div", "name", p.symbol));
    grow.appendChild(el("div", "thin",
      p.call_id ? "from a TradePilot call" : "your own idea"));
    row.appendChild(grow);

    var right = el("div");
    right.style.textAlign = "right";
    if (p.price_unavailable) {
      /* Never zero. A silent 0.0 renders a real holding as worthless. */
      right.appendChild(el("div", "muted", "price unavailable"));
      right.appendChild(el("div", "thin",
        p.qty + " @ " + money(p.avg_price)));
    } else {
      right.appendChild(el("div", null, money(p.value)));
      right.appendChild(el("div", "thin " + (p.pnl >= 0 ? "up" : "down"),
                           money(p.pnl) + " (" + pct(p.pnl_pct) + ")"));
    }
    row.appendChild(right);

    var rm = el("button", "btn quiet", "Remove");
    rm.addEventListener("click", function () { onRemove(p.id, p.symbol); });
    row.appendChild(rm);
    return row;
  }

  function book(node, data) {
    node.innerHTML = "";
    if (data.signedOut) {
      var gate = card(null);
      gate.appendChild(el("div", "empty", "Sign in to see your book."));
      node.appendChild(gate);
      return;
    }

    var list = (data.book && data.book.positions) || [];
    var totals = (data.book && data.book.totals) || {};

    var head = card(null);
    head.appendChild(el("div", "label", "Your portfolio"));
    head.appendChild(el("div", "big", list.length ? money(totals.value) : "--"));
    if (list.length) {
      head.appendChild(el("div", "muted " + (totals.pnl >= 0 ? "up" : "down"),
                           money(totals.pnl) + " overall"));
      if (totals.unpriced) {
        head.appendChild(el("div", "thin", totals.unpriced +
          " holding(s) have no live price and are not included in this total"));
      }
    }
    node.appendChild(head);

    var c = card("Positions");
    if (!list.length) {
      c.appendChild(el("div", "empty", "Nothing logged yet."));
    } else {
      for (var i = 0; i < list.length; i++) {
        c.appendChild(positionRow(list[i], data.onRemove));
      }
    }
    node.appendChild(c);

    var form = card("Log a trade");
    var sym = el("input", "btn"); sym.placeholder = "Symbol, e.g. CIPLA";
    var qty = el("input", "btn"); qty.placeholder = "Quantity"; qty.type = "number";
    var px = el("input", "btn"); px.placeholder = "Average price"; px.type = "number";
    var add = el("button", "btn primary", "Add to my book");
    var err = el("div", "thin");
    add.addEventListener("click", function () {
      err.textContent = "";
      data.onAdd({ symbol: sym.value, qty: Number(qty.value),
                   avg_price: Number(px.value) }, function (message) {
        err.textContent = message;
      });
    });
    form.appendChild(sym); form.appendChild(qty);
    form.appendChild(px); form.appendChild(add); form.appendChild(err);
    node.appendChild(form);
  }
```

Add `book: book, positionRow: positionRow` to the exports.

- [ ] **Step 5: Wire it**

In `prototype/static/app/main.js`:

```javascript
  function loadBook() {
    var node = el("view-book");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    window.TPApi.positions().then(function (b) {
      window.TPScreens.book(node, {
        book: b, signedOut: false,
        onAdd: function (body, onError) {
          if (!body.symbol || !(body.qty > 0) || !(body.avg_price > 0)) {
            onError("Enter a symbol, a positive quantity and a positive price.");
            return;
          }
          window.TPApi.addPosition(body).then(loadBook, function () {
            onError("That could not be added. Check the values and try again.");
          });
        },
        onRemove: function (id, symbol) {
          if (!window.confirm("Remove " + symbol + " from your book?")) return;
          window.TPApi.removePosition(id).then(loadBook, function () {
            window.alert("That could not be removed. Reload and try again.");
          });
        }
      });
    }, function (e) {
      window.TPScreens.book(node, { signedOut: e && e.status === 401 });
    });
  }
```

and add `else if (section === "book") loadBook();` to `onShow`.

- [ ] **Step 6: Run to verify they pass, then commit**

```bash
python3 -m pytest tests/ -q
git add prototype/static/app/screens.js prototype/static/app/main.js prototype/client_api.py tests/test_app_screens.py tests/test_client_api_positions.py
git commit -m "feat(app): the book, with provenance and no unrecoverable action

Every position says whether it came from a TradePilot call or was the
client's own idea -- the split the spec calls the most valuable number in the
product, now visible rather than merely derivable.

A holding with no live quote reads 'price unavailable' and shows its cost
basis. It never reads zero, and the portfolio total says how many holdings it
left out.

There is no Close button. Closing hides the only id that could reopen the
position and no closed-positions view exists, so it is unrecoverable through
the API. Add and Remove only until that view exists.

Also drops user_id from the positions payload: a client has no use for their
own internal identifier, and once accounts land it is a real key."
```

---

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
