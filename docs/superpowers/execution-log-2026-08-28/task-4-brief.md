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

