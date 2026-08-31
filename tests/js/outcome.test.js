"use strict";
const test = require("node:test");
const assert = require("node:assert");
const TPOutcome = require("../../prototype/static/app/outcome.js");

test("an open call never implies a result", () => {
  assert.match(TPOutcome.outcomeText({ outcome: "open" }), /Still open/);
});

test("an ungraded call explains why it is not counted", () => {
  const t = TPOutcome.outcomeText({ outcome: "ungraded" });
  assert.match(t, /without a target/);
  assert.match(t, /not counted/);
});

test("hit and miss are not interchangeable", () => {
  assert.strictEqual(TPOutcome.outcomeText({ outcome: "hit" }), "Hit");
  assert.strictEqual(TPOutcome.outcomeText({ outcome: "miss" }), "Missed");
});

test("an unrecognised outcome is not reported as a loss", () => {
  // The whole point: null must not read as "Missed" beside a gain.
  for (const bad of [null, undefined, "", "pending", "PENDING", 0]) {
    const t = TPOutcome.outcomeText({ outcome: bad });
    assert.strictEqual(t, "Outcome not recorded.", JSON.stringify(bad));
    assert.doesNotMatch(t, /Missed/);
  }
});

test("a missing call object does not throw", () => {
  assert.strictEqual(TPOutcome.outcomeText(null), "Outcome not recorded.");
  assert.strictEqual(TPOutcome.outcomeText(undefined), "Outcome not recorded.");
});

test("colour follows the outcome, and unknown gets none", () => {
  assert.strictEqual(TPOutcome.outcomeKind({ outcome: "hit" }), "up");
  assert.strictEqual(TPOutcome.outcomeKind({ outcome: "miss" }), "down");
  assert.strictEqual(TPOutcome.outcomeKind({ outcome: "open" }), "");
  assert.strictEqual(TPOutcome.outcomeKind({ outcome: null }), "");
});
