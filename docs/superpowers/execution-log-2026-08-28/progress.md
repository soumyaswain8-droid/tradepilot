# SDD ledger — plan: docs/superpowers/plans/2026-08-28-terminal-foundation-agent-floor.md

Spec: docs/superpowers/specs/2026-08-27-terminal-agent-floor-design.md (read)
Worktree: .worktrees/terminal-agent-floor on feat/terminal-agent-floor
Baseline: 169 pytest passing at 2530cf0
Note: no TodoWrite tool in this session — this ledger is the sole progress record.

## Pre-flight conflict scan

### Cross-task rows (tasks sharing a file or interface)

| Pair | Produces → Consumes | Finding |
|:--|:--|:--|
| T1 → T2,T4,T5 | `tests/test_web_routes.py` created by T1, appended by T2/T4/T5 | OK. Append-only; no test redefined. |
| T1 ↔ T2 | `test_team_renders` vs `test_team_without_embed_keeps_header` | Both assert the `<h1>` on `/team`. Overlapping but not conflicting — T2's also asserts pageswitch. Left as-is. |
| T3 → T4 | `TPRoute.parse(hash, sections)` / `.build(s,sub,rest)` → `router.js` calls both | OK. Signatures match exactly. |
| T3 ↔ T4 | T3's test fixture gives `market` 3 subs; T4's real registry gives `market: subs:[]` | OK, and deliberate. The fixture tests the *rule*; the registry is Plan-1 config. Legacy `#market/TITAN/5y` still yields `rest:["TITAN","5y"]` under both. |
| T4 → T5 | `view-agents-quant`/`view-agents-floor` + `frameQuant`/`frameFloor` → `panes.js` | OK. Ids match. |
| T4 → T5 | `TPRouter.register` → `panes.js` calls it at script-exec time | OK. `defer` preserves document order: router.js before panes.js; desk.js registers + calls `boot()` in DOMContentLoaded, which fires after all deferred scripts. |
| T2 → T5 | `/team?embed=1`, `/floor?embed=1` → `panes.js` srcs | OK. Exact match. |
| **T4 ↔ T5** | T4 Step 4 adds the `panes.js` script tag; T5 creates the file | **CONFLICT — see Ruling 1.** |

### Task-internal rows (does each task's own text agree with itself?)

| Task | Finding |
|:--|:--|
| T1 | OK. Tests assert existing behaviour; Step 3 proves the harness fails honestly. |
| T2 | OK. Sentinels verified against `team.html:5`/`:82` and `floor.html` brand span. `#ts` line quoted verbatim from `team.html:233`. |
| T3 | OK. Hand-traced all 12 cases against the implementation, incl. `"#agents//floor/"` → filter(Boolean) → `["agents","floor"]`, and `parse("")` → first section. |
| **T4** | **CONFLICT — see Ruling 2.** `test_terminal_declares_three_sections` asserts `data-section="desk"` in the served HTML, but the nav is rendered by JS at runtime. The Flask test client never executes JS, so the served `<nav class="nav"></nav>` is empty and this test cannot pass. |
| T4 | Step 6's "delete the two setInterval blocks" then "keep a setInterval for loadIndices" reads contradictory but is explicit about the end state. No ruling needed. |
| T5 | OK. No `refresh`/`pollMs` — correct, the framed docs own their own loops. |

### Rulings

Ruling 1: Task 4 Step 4 MUST NOT add the `panes.js` script tag; Task 5 adds it together with the module. — Why: T4's own Step 8 requires "no console errors", but a script tag pointing at a file that will not exist until T5 emits a 404 in the console, making T4's acceptance criteria unsatisfiable. — Cost if wrong: none material; the tag lands one task later and T5's `test_panes_module_loaded` still covers it.

Ruling 2: Replace T4's `test_terminal_declares_three_sections` with a test that fetches `/static/desk/router.js` through the test client and asserts the three section ids appear in the served module. — Why: the original asserts on runtime-rendered DOM that a JS-less test client can never produce; it would fail against a correct implementation. Fetching the static asset tests the real artifact through the real server, which is the closest honest equivalent. — Cost if wrong: weaker coverage than a real DOM assertion; the browser checklist in Step 8 remains the backstop, and a headless-browser test could replace it later.

## Progress

Task 1: implementer DONE (commit 7957366, 172 pytest passing, +3). Review dispatched.
Task 1: review clean (Spec ✅, quality approved, 0 Critical/Important).
Task 1: ⚠️ "honesty check not verifiable from diff" resolved by controller — ran the test client directly against /, /floor, /team: bodies 6482/17151/9804 bytes, real sentinels present, bogus sentinels absent. Assertions discriminate. Not a gap.
Task 1: complete (commits 2530cf0..7957366, review clean)
Task 2: dispatched (sonnet, BASE 7957366).
Task 2: implementer DONE (commit 39897b4, 176 pytest passing, +4). Review dispatched.
Task 2: environment notes (carry forward) — (a) repo-wide `python3 -m pytest` fails collection on PRE-EXISTING scripts/test_baseline_protection.py (SystemExit); always scope to `tests/`. Confirmed pre-existing via git stash, not introduced by this plan. (b) A stale orphaned server was squatting :5050 from an earlier session; killed. Verified none running before Task 2 review.
Task 2: review clean (Spec ✅, quality approved, 0 Critical/Important).
Task 2: ⚠️ "suite count / browser check not verifiable" resolved by controller — ran `pytest tests/ -q` => 176 passed, and 8/8 embed markup assertions verified via test client (h1+pageswitch absent under ?embed=1 and present without; floor brand absent but sTicks/sNow present). Not a gap.
Task 2: minor (deferred): /floor docstring em dash changed to double-hyphen — cosmetic diff noise copied from the brief, unrelated to the feature.
Task 2: complete (commits 7957366..39897b4, review clean)
Task 3: implementer DONE (commit c1b09ae). Node 12/12 pass (file form). pytest 176 (implementer misreported 169).
Task 3: Ruling: the plan's documented node command `node --test tests/js/` is WRONG for this environment — Node 22.15 resolves the directory as a CommonJS module and throws MODULE_NOT_FOUND before running any test. Canonical command is now `node --test tests/js/*.test.js` (glob), verified 12 tests / 12 pass. — Why: the directory form cannot work here, and the glob scales as more JS test files land, unlike naming a single file. — Cost if wrong: none material; strictly more portable than either alternative.
Task 3: report-quality concern — implementer substituted the working command without flagging the plan's broken one, and reported pytest 169 (the PARENT checkout's count) instead of the worktree's 176. Artifacts verified correct by controller regardless; report trust reduced, flagged to reviewer.
Task 3: review — Spec ✅, quality: changes needed. 2 Important + 1 Minor, ALL in the report file; code verified byte-identical to brief and tests confirmed to discriminate against both failure modes of the sub-matching rule.
Task 3: fix round 1/5 dispatched (resumed original implementer) — correct pytest count 169→176, disclose the node command substitution and why the brief's form is broken, and fix the "all 12 tests FAIL" overstatement (Node reports 1 aggregate load failure).
Task 3: fix round 1/5 complete (3 addressed, 0 open from round 1; commit c1b09ae..bb451ac). Verified by controller: node 12/12 via canonical glob, pytest 176, report narrative now accurate (fail-step describes the aggregate load failure; count reads 176; Was/Now audit records retained deliberately).
Task 3: NEW breakage introduced by the fix diff — `.superpowers/` is NOT gitignored in this repo, so commit bb451ac tracked task-3-report.md into the feature branch. The SDD workspace is disposable scratch (this skill deletes it at finish) and carries absolute paths + process detail that must not enter product history. Joins the open findings list for round 2.
Task 3: Ruling: `.superpowers/` must be added to .gitignore and the tracked report untracked via `git rm --cached`. — Why: the workspace is scratch the skill destroys at finish; leaving it tracked would produce a spurious deletion commit and pollute the branch with internal process artifacts. — Cost if wrong: none; the files remain on disk either way, only their git tracking changes.
Task 3: fix round 2/5 (4 addressed, 0 open — F1 pytest count, F2 command-substitution disclosure, F3 fail-step prose, F4 workspace untracked; commits c1b09ae..f630432). Re-review confirms no new breakage and all 13 workspace files intact on disk incl. progress.md.
Task 3: minor (deferred): branch carries an add-then-untrack pair (bb451ac adds scratch report, f630432 untracks it). Net tree at HEAD is clean — only .gitignore differs. Re-reviewer independently recommended leaving it rather than rewriting history; matches controller ruling. Squash is optional at branch-finish time.
Task 3: complete (commits 39897b4..f630432, review clean after 2 fix rounds)
Task 4: implementer DONE_WITH_CONCERNS (commit 3425910, pytest 179, node 12/12).
Task 4: Ruling: the registry-driven nav dropped the terminal's two external links (`/decisions` and `/classic`, previously rendered with the ↗ affordance). Controller confirmed the regression — zero references remain in desk.html or router.js. This is a real reachability regression, not cosmetic: /classic is the client surface that must stay reachable until project C absorbs it, and Decisions does not become a routed section until Plan 2. Fix = a SEPARATE `EXTERNAL` array in router.js rendered after SECTIONS, deliberately NOT part of SECTIONS so TPRoute never routes to a section with no view. — Why: one source of truth for the nav without letting non-routable entries enter the router's section table, where `#decisions` would resolve to a section with no registered view and render blank. — Cost if wrong: nav carries two links whose placement Plan 2 will revisit when Decisions becomes a real routed sub-tab.
Task 4: fix round 1/5 dispatched (resumed original implementer) — restore external links via EXTERNAL array.
--- NOTE: the entries below were lost to an ENOSPC (disk full) at the time of the Task 4 review and re-appended after the user freed space. Chronologically they belong immediately after the Task 4 fix round 1 line. ---
Task 4: fix round 1/5 (external-link regression addressed; commits 3425910..9e76397, pytest 180).
Task 4: review — Spec ✅ (all 3 rulings followed, all 7 checkpoints verified), quality approved with 1 Important.
Task 4: minor (deferred): [M2] `_last` not seeded at mount, so the first 5s tick fires refresh immediately — desk hits /api/desk twice on load, market twice on first switch. One-liner: set h._last = Date.now() alongside mounted[viewId] = true.
Task 4: minor (deferred): [M3] a failed mount is permanent and noisy — `mounted` is set BEFORE guard(), so the error card never re-mounts yet refresh keeps firing into the wiped DOM every pollMs.
Task 4: minor (deferred): [M4] boot() is itself unguarded — if route.js 404s, TPRouter.boot() throws inside desk.js's DOMContentLoaded handler and kills the 60s loadIndices interval declared after it. Moving the shell timer above boot() fixes it.
Task 4: minor (deferred): [M5] views registered AFTER boot() are invisible until the next go(). Works for Task 5 only because panes.js's listener is added before desk.js's — depends on script tag order and is undocumented.
Task 4: minor (deferred): [M6] esc() duplicated verbatim in router.js and desk.js; `.view.pane.on{display:block}` redundant with existing `.view.on` (desk.css:105). Both are brief-verbatim.
Task 4: DEFERRED CONCERN (final review + user): router.js has ZERO executable test coverage. All 4 new tests are byte-greps against served text; nothing exercises parse->go->show->mount. route.js is properly covered (12 node tests) because it is pure. Covering router.js needs a DOM (jsdom), which the no-new-dependencies constraint forbids. Ruling: accept the gap for Plan 1 and surface it to the user rather than silently adding a dependency. — Cost if wrong: a router regression ships green; the browser checklist is the only backstop.
Task 4: ENVIRONMENT — execution halted on ENOSPC (disk full) during this ledger write; no work lost, all commits intact at 9e76397. User freed space; 3.9Gi available on resume (project's own preflight gate wants >=5Gi).
Task 4: fix round 2/5 dispatched — Important: back-button trap (go() pushes a history entry when normalizing).
Task 4: fix round 2/5 (1 addressed, 0 open — back-button trap; commits 9e76397..a38bce4). Re-review: no new breakage. Traced: boot adds exactly ONE history entry (replaceState mutates in place and does not fire hashchange); the click->hashchange echo is caught by the `location.hash === hash` early-return before any second write; `#market/TITAN/5y` round-trips byte-identically so bookmarked URLs are never rewritten; missing-replaceState fallback degrades to the old behaviour, acceptable for an internal tool.
Task 4: complete (commits f630432..a38bce4, review clean after 2 fix rounds, 6 minors deferred)
Task 5: implementer DONE (commit b1754ac, pytest 183, node 12/12).
Task 5: review — Spec ✅, quality approved. Verified independently: view ids match router's viewIdFor(), register runs at IIFE time so the defer ordering holds, mount guard uses getAttribute consistently on BOTH read and write (mixing with the .src property would absolutise the URL and silently defeat the comparison), no refresh/pollMs so the router never double-drives the framed pollers.
Task 5: Ruling on the one Important (test coverage): PARKED, not fixed. The reviewer itself labels it plan-level, not an execution defect — the brief specified the test content verbatim, and none of the 3 new tests exercise panes.js at all (they assert Task 4's server-rendered markup, and would pass with panes.js deleted). Closing it needs a test DOM (jsdom), which this plan's no-new-dependencies constraint forbids. — Why: silently adding a dependency to satisfy a review finding would violate a stated global constraint; the honest move is to surface the gap to the user as scope for a follow-up. — Cost if wrong: a regression in panes.js (swapped ids, deleted unmount, an accidental pollMs) ships green; the browser checklist is the only backstop.
Task 5: minor (deferred): [M7] panes.js calls window.TPRouter.register unguarded at script-eval time — if router.js fails to load this throws an uncaught TypeError. Not a new failure class (desk.js already did the same), but the terminal now surfaces two uncaught errors instead of one.
Task 5: minor (deferred): [M8] the brief's Step 4 expected "13 pytest PASS" for test_web_routes.py; the file actually has 14 (11 pre-existing + 3 new). Plan arithmetic was wrong, implementation correct.
Task 5: complete (commits a38bce4..b1754ac, review clean, 1 parked + 2 minors deferred)
FINAL whole-branch review (opus, 9 commits, 2530cf0..b1754ac): CHANGES NEEDED. 0 Critical. 2 Important (I1 tests never fetch route.js/panes.js — deleting panes.js keeps all 183 green; I2 guard() catches sync throws only, async rejections never reach it). Deferred list triaged: [M2] and [M4] promoted to must-fix, [M3][M5][M6][M7] fine-to-defer, [M8] not a problem.
FINAL review agreed with the parked no-coverage ruling: "adding a dependency to satisfy a review finding, against a stated constraint, is exactly the move that should require the user's say-so."
FINAL review cross-task checks all clean: cold-load ordering correct (all 4 views registered before boot, nothing after); zero orphaned data-tab/switchTab references in the terminal; no endpoint driven twice (sole duplicate is [M2], a first-tick artefact not a second timer); nothing shipped that shouldn't (no absolute paths, debug logging, TODOs; .superpowers/ absent from the net file list); spec fidelity holds both directions with no Plan 2/3 leakage.
FINAL review, third independent vote to LEAVE the bb451ac/f630432 add-then-untrack pair unsquashed: "rewriting history to hide a self-corrected mistake is the wrong instinct in a repo whose ledger IS the audit trail."
FINAL review caught a factual error in MY OWN spec and in panes.js's comment: both claim the framed consoles poll "once a second" / "~3,600 req/hr". Real cadences are team.html POLL_MS=5000 and floor.html setTimeout(poll,2000). Rationale stands, numbers 2-5x overstated. Included in the fix wave.
FINAL fix wave dispatched (ONE agent, 7 items): I1 module-fetch test, I2 async caveat in lifecycle contract, M2 seed _last at mount, M4 hoist loadIndices above boot(), M5 register-before-boot comment, M-a correct the poll-rate claim, and a new durable docs/TERMINAL_MANUAL_CHECKS.md so the browser checklist outlives the disposable workspace.
FINAL fix wave: commit 9b9550c. Re-review verdict READY TO MERGE — all 7 items ADDRESSED, no new breakage. Reviewer independently re-derived the poll cadences (team 5000ms=720/hr exact; floor self-rescheduling setTimeout 2000ms, ~1800/hr and fractionally below once fetch latency is added, never above) and confirmed the correction is genuine rather than a wrong-number swap.
PLAN COMPLETE: 10 commits, 2530cf0..9b9550c. pytest 169 -> 184, node 0 -> 12.
