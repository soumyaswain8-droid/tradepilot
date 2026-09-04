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

  /* Stroke icons for the phone tab bar, copied from HomePhone.dc.html. One
     path string per section; the svg wrapper is built below. */
  var ICONS = {
    home:   [["path", { d: "M3 11l9-8 9 8v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" }]],
    calls:  [["path", { d: "M4 19h16M6 15l4-5 4 3 5-7" }]],
    book:   [["path", { d: "M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM8 7h8M8 11h8M8 15h5" }]],
    record: [["circle", { cx: "12", cy: "12", r: "9" }], ["path", { d: "M12 7v5l3 2" }]]
  };
  var SVG_NS = "http://www.w3.org/2000/svg";

  function icon(id) {
    var svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    var parts = ICONS[id] || [];
    for (var i = 0; i < parts.length; i++) {
      var node = document.createElementNS(SVG_NS, parts[i][0]);
      var attrs = parts[i][1];
      for (var k in attrs) {
        if (attrs.hasOwnProperty(k)) node.setAttribute(k, attrs[k]);
      }
      svg.appendChild(node);
    }
    return svg;
  }

  /* The current section is `call` when a call is open; the Calls tab stays
     lit so the user can see where they are in the product. */
  function navCurrent() { return cur === "call" ? "calls" : cur; }

  /* Top tabs (desktop) and bottom tabs (phone) come from the same list, and
     both hrefs go through TPRoute.build -- one list, one parser, so the two
     bars cannot disagree about where a tab leads. CSS decides which one is
     visible at a given width. */
  function renderNav() {
    var top = el("tabs");
    var bottom = el("tabbar");
    if (!top || !bottom) return;
    top.innerHTML = "";
    bottom.innerHTML = "";
    var on = navCurrent();
    for (var i = 0; i < SECTIONS.length; i++) {
      var s = SECTIONS[i];
      var href = window.TPRoute.build(s.id, null, []);

      var a = document.createElement("a");
      a.href = href;
      a.textContent = s.label;
      a.className = "tab" + (s.id === on ? " on" : "");
      if (s.id === on) a.setAttribute("aria-current", "page");
      top.appendChild(a);

      var t = document.createElement("a");
      t.href = href;
      t.className = "tabm" + (s.id === on ? " on" : "");
      if (s.id === on) t.setAttribute("aria-current", "page");
      t.appendChild(icon(s.id));
      t.appendChild(document.createTextNode(s.label));
      bottom.appendChild(t);
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
    loadWho();
  }

  /* Fills the header's #who -- signed in, it names the account and offers a
     way out; signed out, it offers a way in. Nothing else on the page reads
     identity, so this is the one place the shell claims to know who is
     looking at it. */
  function loadWho() {
    var node = el("who");
    if (!node) return;
    var avatar = el("avatar");
    window.TPApi.me().then(function (m) {
      node.innerHTML = "";
      var who = m.email || m.user_id || "";
      if (avatar) avatar.textContent = (String(who).charAt(0) || "·").toUpperCase();
      var name = window.TPScreens.el("span", "thin", who);
      var out = document.createElement("form");
      out.method = "post";
      out.action = "/app/logout";
      out.style.display = "inline";
      var b = document.createElement("button");
      b.type = "submit";
      b.className = "who-out";
      b.textContent = "Sign out";
      out.appendChild(b);
      node.appendChild(name);
      node.appendChild(out);
    }, function (e) {
      node.innerHTML = "";
      if (e && e.status === 401) {
        var a = document.createElement("a");
        a.href = "/app/login";
        a.textContent = "Sign in";
        node.appendChild(a);
        return;
      }
      /* Any other failure -- 500, a dropped connection, bad JSON -- tells us
         nothing about whether they are signed in. Offering "Sign in" would be
         a claim built on a request that failed, which is the mistake this
         codebase has now made three times. Say nothing instead: Home's book
         card still carries a working link for a signed-out visitor. */
    });
  }

  /* A rejected promise loses its value. Swallow the rejection here and hand
     home() null instead, so one bad endpoint cannot take the whole page down
     -- a signed-out visitor must still see the calls and the rate, since
     that half is the entire acquisition surface. */
  function soft(p) {
    return p.then(function (v) { return v; }, function () { return null; });
  }

  function loadHome() {
    var node = el("view-home");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    Promise.all([
      soft(window.TPApi.record()),
      soft(window.TPApi.calls(5)),
      window.TPApi.positions().then(
        function (b) { return { book: b, signedOut: false, failed: false }; },
        function (e) {
          /* A 401 means signed out. Anything else means we could not tell --
             and "log your first trade" is a claim about their account we have
             no right to make when the request simply failed. */
          return { book: null, signedOut: !!(e && e.status === 401),
                   failed: !(e && e.status === 401) };
        })
    ]).then(function (r) {
      window.TPScreens.home(node, {
        record: r[0], calls: r[1], book: r[2].book,
        signedOut: r[2].signedOut, bookFailed: r[2].failed,
        onOpenCall: function (id) { window.TPApp.go("call", [id]); }
      });
    }, function () {
      node.innerHTML = "";
      node.appendChild(window.TPScreens.el(
        "div", "empty", "Could not load. Reload the page."));
    });
  }

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

  function loadBook() {
    var node = el("view-book");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    window.TPApi.positions().then(function (b) {
      window.TPScreens.book(node, {
        book: b, signedOut: false, failed: false,
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
      /* Same three-state shape as loadHome's book fetch: a 401 means signed
         out. Anything else means we could not tell, and "Nothing logged
         yet." is a claim about their holdings a failed request has no right
         to make -- so it gets its own branch instead of folding into
         signedOut, which would render the same wrong claim under a
         different cause. */
      window.TPScreens.book(node, {
        book: null,
        signedOut: !!(e && e.status === 401),
        failed: !(e && e.status === 401)
      });
    });
  }

  function loadRecord() {
    var node = el("view-record");
    if (!node) return;
    node.innerHTML = "<div class='empty'>Loading…</div>";
    /* The record itself is this screen's entire purpose; a failed calls(50)
       must not take the whole screen down over the "Resolved calls" list
       underneath it. Plain soft() is not enough here: it collapses "the
       fetch failed" and "the fetch succeeded with nothing" to the same
       null, and record() cannot tell a real empty resolved-list from a
       broken fetch -- it would print "Nothing has resolved yet." next to a
       tally that says otherwise. Convert the rejection into a resolved
       value that carries which case it is, the same shape loadBook already
       gives book(). */
    Promise.all([
      window.TPApi.record(),
      window.TPApi.calls(50).then(
        function (c) { return { calls: c, failed: false }; },
        function () { return { calls: null, failed: true }; })
    ]).then(function (r) {
        window.TPScreens.record(node, {
          record: r[0], calls: r[1].calls, callsFailed: r[1].failed
        });
      }, function () {
        node.innerHTML = "";
        node.appendChild(window.TPScreens.el(
          "div", "empty", "Could not load the record. Reload the page."));
      });
  }

  window.TPApp = {
    SECTIONS: SECTIONS, go: go, boot: boot,
    onShow: function (section, rest) {
      if (section === "home") loadHome();
      else if (section === "calls") loadCalls();
      else if (section === "call") loadCall(rest && rest[0]);
      else if (section === "record") loadRecord();
      else if (section === "book") loadBook();
    }
  };
})();

document.addEventListener("DOMContentLoaded", function () {
  window.TPApp.boot();
});
