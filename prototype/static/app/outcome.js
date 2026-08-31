/* The words a client reads about what happened to a call.

   Pure and node-testable on purpose. This is the one claim on the whole
   dashboard that must never be wrong: an open call must not imply a result,
   and a call whose outcome we do not recognise must not be reported as a
   loss. A substring test cannot check that, so this lives behind a module
   boundary where real tests can reach it. */
(function (root, factory) {
  "use strict";
  var api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.TPOutcome = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  function outcomeText(call) {
    var outcome = call && call.outcome;
    if (outcome === "open") {
      return "Still open -- no outcome yet.";
    }
    if (outcome === "ungraded") {
      return "Published without a target, so it is not graded and not counted.";
    }
    if (outcome === "hit") return "Hit";
    if (outcome === "miss") return "Missed";
    /* Anything else -- null, undefined, or a value added to the API later --
       is unknown, not a loss. Reporting "Missed" here would state a specific
       failure we cannot support. */
    return "Outcome not recorded.";
  }

  function outcomeKind(call) {
    var outcome = call && call.outcome;
    if (outcome === "hit") return "up";
    if (outcome === "miss") return "down";
    return "";
  }

  return { outcomeText: outcomeText, outcomeKind: outcomeKind };
});
