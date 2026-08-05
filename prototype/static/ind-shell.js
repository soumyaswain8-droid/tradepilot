/* ═══════════════════════════════════════════════════════════════════════════
   ind-shell.js — rebuild TradePilot's navigation in INDmoney's shape.
   2026-08-04

   THE PROBLEM: 13 asset tabs in one horizontal strip. On a 1440px screen the
   strip overflowed, "Wizard" was permanently clipped, and a "More" button existed
   only to hide the overflow. Thirteen equal peers also carry no hierarchy — F&O
   and Gainers are not the same kind of thing.

   INDmoney's answer, and the one adopted here: a narrow LEFT RAIL of sections,
   and a TOP BAR of pages within the selected section. Six rail entries instead of
   thirteen peers. Nothing overflows, and where you are is always visible.

   ADDITIVE, NOT A REWRITE. Every original .nav-tab button is MOVED, never
   recreated: the same DOM nodes, with the same data-tab attributes and the same
   listeners already bound to them, are re-parented into the sub-tab bar. Clicking
   a sub-tab therefore runs the app's existing handler untouched. Nothing here
   knows how tab switching works, which is precisely why it cannot break it.

   Its own <script> tag with no src — a src-bearing script element discards inline
   content entirely, which is how the US Market tab shipped blank on 2026-08-03.
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  /* Grouping is an information-architecture decision, not cosmetics. Thirteen flat
     tabs became six sections by asking what a person is actually doing:
       Markets    — browsing Indian equities (4 views of the same universe)
       F&O        — derivatives, its own world
       Funds      — pooled instruments: ETFs and mutual funds
       Commodities— non-equity: metals, energy, currency
       US Stocks  — a separate market with its own session and rules
       Lab        — tools that ACT rather than display: simulate, paper-trade, guide
     Portfolio is a link, not a tab — it is a whole page at /portfolio. */
  var SECTIONS = [
    { key: "markets", label: "Markets", tabs: ["stocks", "movers", "intraday", "aipicks"],
      icon: '<path d="M4 19V9m5 10V4m5 15v-7m5 7V7" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/>' },
    { key: "fno", label: "F&O", tabs: ["fno"],
      icon: '<path d="M4 15l5-5 4 4 7-8" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/><path d="M15 6h5v5" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>' },
    { key: "funds", label: "Funds", tabs: ["etfs", "mutualfunds"],
      icon: '<path d="M12 3v18M8 7h6a3 3 0 010 6H8m0 0h7" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"/>' },
    { key: "comm", label: "Commodities", tabs: ["commodities", "currencies"],
      icon: '<ellipse cx="12" cy="6" rx="7" ry="3" stroke="currentColor" stroke-width="2"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" stroke="currentColor" stroke-width="2"/>' },
    { key: "us", label: "US Stocks", tabs: ["usmarket"],
      icon: '<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="2"/><path d="M3.5 12h17M12 3.5c2.2 2.4 3.3 5.4 3.3 8.5s-1.1 6.1-3.3 8.5c-2.2-2.4-3.3-5.4-3.3-8.5S9.8 5.9 12 3.5z" stroke="currentColor" stroke-width="1.7"/>' },
    { key: "lab", label: "Lab", tabs: ["tradelab", "papertrade", "wizard"],
      icon: '<path d="M9.5 3v6.2L4.6 17a2 2 0 001.7 3h11.4a2 2 0 001.7-3l-4.9-7.8V3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><path d="M8.5 3h7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' }
  ];

  var LINKS = [
    { label: "Portfolio", href: "/portfolio",
      icon: '<rect x="3" y="6" width="18" height="14" rx="2.5" stroke="currentColor" stroke-width="2"/><path d="M3 10h18M8 6V4.5A1.5 1.5 0 019.5 3h5A1.5 1.5 0 0116 4.5V6" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' },
    { label: "Live", href: "/live",
      icon: '<circle cx="12" cy="12" r="3" fill="currentColor"/><path d="M5.6 5.6a9 9 0 000 12.8M18.4 5.6a9 9 0 010 12.8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>' },
    { label: "A/B", href: "/lab",
      icon: '<path d="M12 3l9 16H3l9-16z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>' }
  ];

  /* XSS: every innerHTML below is built ONLY from the SECTIONS and LINKS literals
     above — static icon paths and labels defined in this file. No network payload,
     no user input, and no engine data reaches markup here. Text taken FROM the page
     (sub-tab labels) goes through textContent, never innerHTML. */
  function svg(inner) {
    return '<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">' + inner + "</svg>";
  }

  function labelOf(btn) {
    // The original buttons hold an inline SVG plus a text node. Take only the text,
    // so the rail's sub-tabs read "Smart Picks" and not the SVG's markup.
    var t = "";
    btn.childNodes.forEach(function (n) {
      if (n.nodeType === 3) t += n.textContent;
    });
    return t.trim() || btn.getAttribute("data-tab");
  }

  function build() {
    var nav = document.querySelector("nav.nav");
    if (!nav || document.getElementById("indRail")) return;

    // index the original buttons by data-tab; they are MOVED, never cloned —
    // a clone would lose the listeners the app bound to the original node.
    var byTab = {};
    nav.querySelectorAll(".nav-tab").forEach(function (b) {
      var k = b.getAttribute("data-tab");
      if (k) byTab[k] = b;
    });
    if (!Object.keys(byTab).length) return;

    var rail = document.createElement("aside");
    rail.id = "indRail";
    rail.setAttribute("aria-label", "Sections");
    rail.innerHTML = '<div class="ind-brand" title="TradePilot">TP</div>';

    var sub = document.createElement("div");
    sub.id = "indSub";
    sub.setAttribute("role", "tablist");
    nav.parentNode.insertBefore(sub, nav.nextSibling);

    var current = null;

    function show(sec, clickFirst) {
      current = sec.key;
      rail.querySelectorAll(".ind-item").forEach(function (el) {
        el.classList.toggle("on", el.dataset.sec === sec.key);
        if (el.dataset.sec) el.setAttribute("aria-current", el.dataset.sec === sec.key ? "page" : "false");
      });
      sub.textContent = "";
      var present = sec.tabs.map(function (t) { return byTab[t]; }).filter(Boolean);
      present.forEach(function (btn) {
        btn.className = "st";                 // restyle in place; node identity kept
        btn.textContent = labelOf(btn);       // drop the old inline icon markup
        sub.appendChild(btn);
      });
      // A single-page section needs no tab strip — showing one lone tab is noise.
      sub.style.display = present.length > 1 ? "" : "none";
      if (clickFirst && present.length) present[0].click();
      syncActive();
    }

    function syncActive() {
      // Mirror whatever the app itself marked active, so the chrome follows the
      // app's state rather than trying to own it.
      sub.querySelectorAll(".st").forEach(function (b) {
        b.classList.toggle("on", b.classList.contains("active"));
      });
    }

    SECTIONS.forEach(function (sec) {
      if (!sec.tabs.some(function (t) { return byTab[t]; })) return;   // skip empty
      var b = document.createElement("button");
      b.className = "ind-item";
      b.dataset.sec = sec.key;
      b.type = "button";
      b.innerHTML = '<span class="ic">' + svg(sec.icon) + '</span><span class="lb">'
        + sec.label + "</span>";
      b.addEventListener("click", function () { show(sec, true); });
      rail.appendChild(b);
    });

    var sep = document.createElement("div");
    sep.className = "ind-sep";
    rail.appendChild(sep);

    LINKS.forEach(function (l) {
      var a = document.createElement("a");
      a.className = "ind-item";
      a.href = l.href;
      a.innerHTML = '<span class="ic">' + svg(l.icon) + '</span><span class="lb">'
        + l.label + "</span>";
      rail.appendChild(a);
    });

    var spacer = document.createElement("div");
    spacer.className = "ind-spacer";
    rail.appendChild(spacer);

    document.body.appendChild(rail);
    document.body.classList.add("ind-on");

    // Open whichever section owns the tab the app already has active, so a reload
    // lands where the user was rather than resetting to Markets.
    var activeTab = (nav.querySelector(".nav-tab.active") || {}).getAttribute
      ? nav.querySelector(".nav-tab.active").getAttribute("data-tab") : null;
    var start = SECTIONS.filter(function (s) {
      return activeTab && s.tabs.indexOf(activeTab) >= 0;
    })[0] || SECTIONS[0];
    show(start, false);
    if (!sub.querySelector(".st.active") && sub.querySelector(".st")) {
      sub.querySelector(".st").click();
    }

    // The app toggles .active on these buttons; mirror it into .on without
    // interfering. A MutationObserver keeps the chrome in sync no matter which
    // code path caused the change.
    new MutationObserver(syncActive).observe(sub, {
      subtree: true, attributes: true, attributeFilter: ["class"]
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", build);
  } else {
    build();
  }
})();
