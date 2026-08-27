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
