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

