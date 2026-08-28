/* router.js — nav, section/sub-tab switching, and the view lifecycle.
   Parsing lives in route.js (pure, node-tested); this file owns the DOM.

   Lifecycle contract:
     mount()    once, the first time a view becomes visible
     refresh()  on tick, only while visible and the document is not hidden
     unmount()  on hide -- iframe panes only; ported views keep their state

     Hooks must handle their own async failures. guard() catches synchronous
     throws only -- a rejected promise inside mount() never reaches it, so an
     async view that fails renders a blank pane instead of the error card.
     Every hook that awaits anything must carry its own .catch.

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

  /* External destinations. Deliberately NOT in SECTIONS: TPRoute matches by
     section id, so an entry here would let "#classic" resolve to a section
     with no registered view and render a blank tab. These are plain links,
     never routed. */
  var EXTERNAL = [
    { label: "Decisions", href: "/decisions" },
    { label: "Classic",   href: "/classic" }
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
        if (!mounted[viewId]) {
          mounted[viewId] = true;
          if (views[viewId]) views[viewId]._last = Date.now();
          guard(viewId, "mount");
        }
      } else if (mounted[viewId] && views[viewId] && views[viewId].unmount) {
        guard(viewId, "unmount");
        mounted[viewId] = false;
      }
    });
    document.querySelectorAll(".nav a[data-section]").forEach(function (a) {
      a.classList.toggle("on", a.getAttribute("data-section") === section);
    });
  }

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

  /* Register BEFORE boot(). boot() runs the first go(), and show() only
     iterates views registered by then -- a later registrant stays hidden
     until the next navigation. Script order in desk.html guarantees this:
     panes.js registers at IIFE time, desk.js registers inside its
     DOMContentLoaded handler and calls boot() last. */
  function register(viewId, hooks) { views[viewId] = hooks || {}; }
  function current() { return { section: cur.section, sub: cur.sub, rest: cur.rest.slice() }; }

  function boot() {
    renderNav();
    var p = window.TPRoute.parse(location.hash, SECTIONS);
    go(p.section, p.sub, p.rest, true);

    window.addEventListener("hashchange", function () {
      var q = window.TPRoute.parse(location.hash, SECTIONS);
      go(q.section, q.sub, q.rest, true);
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
