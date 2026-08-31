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
