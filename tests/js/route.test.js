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
