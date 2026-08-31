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

