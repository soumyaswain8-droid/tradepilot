# Task 2 Report — Embed mode for /floor and /team

## Status: DONE

## Files changed
- `prototype/app.py` — `/floor` and `/team` handlers now pass `embed=request.args.get("embed") == "1"` to `render_template`, with docstrings explaining the flag. Kept the existing function name `team_dashboard` (brief's example used `team_view`, but the brief explicitly says to keep the original handler's shape if it differs — no other code references the function name, confirmed via grep).
- `prototype/templates/floor.html` — brand span in the `.bar` div wrapped in `{% if not embed %}...{% endif %}`. Stats strip (`sTicks`, `sRate`, `sEsc`, `sSwap`, `sArm`, `sGap`, `sNow`) left untouched.
- `prototype/templates/team.html` — three changes:
  1. `<header>...</header>` block wrapped in `{% if not embed %}...{% endif %}`.
  2. `document.getElementById("ts").textContent = fmt(j.ts);` replaced with a null-guarded version (`var tsEl = ...; if (tsEl) tsEl.textContent = fmt(j.ts);`).
  3. `<script src="/static/pageswitch.js"></script>` wrapped in `{% if not embed %}...{% endif %}`.
- `tests/test_web_routes.py` — appended the 4 tests from the brief verbatim: `test_floor_embed_hides_brand`, `test_floor_without_embed_keeps_brand`, `test_team_embed_hides_header_and_pageswitch`, `test_team_without_embed_keeps_header`.

## Commands run (full output)

### Step 1/2 — tests appended, run before implementation (expect 2 fail, 2 pass)
```
$ python3 -m pytest tests/test_web_routes.py -v -k embed
tests/test_web_routes.py::test_floor_embed_hides_brand FAILED            [ 25%]
tests/test_web_routes.py::test_floor_without_embed_keeps_brand PASSED    [ 50%]
tests/test_web_routes.py::test_team_embed_hides_header_and_pageswitch FAILED [ 75%]
tests/test_web_routes.py::test_team_without_embed_keeps_header PASSED    [100%]
2 failed, 2 passed, 3 deselected in 3.07s
```
Both failures were `AssertionError: b"AGENT FLOOR</span>" not in r.data` / `b"<h1>...</h1>" not in r.data` — i.e. `?embed=1` was being ignored, exactly as expected.

### Step 5 — after implementation, full file
```
$ python3 -m pytest tests/test_web_routes.py -v
tests/test_web_routes.py::test_terminal_renders PASSED                   [ 14%]
tests/test_web_routes.py::test_floor_renders PASSED                      [ 28%]
tests/test_web_routes.py::test_team_renders PASSED                       [ 42%]
tests/test_web_routes.py::test_floor_embed_hides_brand PASSED            [ 57%]
tests/test_web_routes.py::test_floor_without_embed_keeps_brand PASSED    [ 71%]
tests/test_web_routes.py::test_team_embed_hides_header_and_pageswitch PASSED [ 85%]
tests/test_web_routes.py::test_team_without_embed_keeps_header PASSED    [100%]
7 passed in 3.03s
```

### Full suite (`tests/` only — see "Surprising" note below on why not bare `pytest`)
```
$ python3 -m pytest tests/
... (all files) ...
tests/test_web_routes.py .......                                        [ 92%]
tests/v7/test_engine_intraday.py ...                                     [ 94%]
tests/v7/test_regime_gate.py ....                                        [ 96%]
tests/v7/test_supertrend_flip.py ......                                  [100%]
176 passed in 3.37s
```
172 (baseline) + 4 new = 176. Matches exactly. Confirmed by running again post-commit — still 176 passed.

## curl verification (Step 6, all four URL variants)

Server started as a background process: `python3 prototype/app.py` (logged to `/tmp/tp-app3.log`), then killed with `pkill -f "prototype/app.py"` after verification — port 5050 confirmed free afterward.

| URL | Assertion | Result |
|---|---|---|
| `GET /team` | `<h1>TradePilot Quant Desk</h1>` present | FOUND (expected) |
| `GET /team` | `pageswitch.js` present | FOUND (expected) |
| `GET /team?embed=1` | `<h1>TradePilot Quant Desk</h1>` present | absent (expected) |
| `GET /team?embed=1` | `pageswitch.js` present | absent (expected) |
| `GET /team?embed=1` | `<title>` still carries "TradePilot Quant Desk" | `<title>TradePilot Quant Desk · Team</title>` kept (expected — only `<h1>` is guarded, matching the brief's own note that the `<title>` is untouched) |
| `GET /floor` | `AGENT FLOOR</span>` present | FOUND (expected) |
| `GET /floor?embed=1` | `AGENT FLOOR</span>` present | absent (expected) |
| `GET /floor?embed=1` | `id="sTicks"` present (stats strip kept) | FOUND (expected) |

Also spot-checked `GET /api/team/status` (the poll target for `team.html`'s `tick()`) returns valid JSON quickly — confirms the null-guarded `#ts` write path is exercised without error on a live server, not just in the test client.

**Note on live JS-console verification**: I have no browser tool available in this environment, so Step 6's "browser console shows no errors across ~20s of poll ticks" was verified by markup inspection (curl) plus confirming the underlying `/api/team/status` and `/api/floor/live` endpoints respond, rather than by watching a real browser console. The rendered HTML for both `?embed=1` variants is structurally correct (guarded elements absent, stats/data elements present), and the null-guard change is a direct, mechanical fix for the one JS line the brief flagged as unsafe under the header guard — but this was not observed running for 20 seconds in an actual browser tab.

## Commit
`39897b4` — `feat(floor,team): embed mode for framing inside the terminal`
4 files changed, 50 insertions(+), 7 deletions(-)

## Surprising / notable

1. **Port 5050 was already bound by a stale, orphaned process** (PID 20895, parent PID 1, started the previous day at 11:13:49) when I first tried to launch the server for Step 6. My first `python3 prototype/app.py` silently failed to bind ("Address already in use") but the background launch still reported "server up" because curl was hitting the *stale* process, which was serving pre-task-2 templates — so my first verification pass showed embed mode "not working" even though the code was correct. I confirmed this by checking `ps`/`lsof`, killed the stale PID, and restarted; the second run bound correctly and all four curl checks passed as expected. Worth flagging in case that orphaned process was left by an earlier task-2 attempt or another agent — I killed it since it was serving stale code and blocking verification of this task's fix.
2. **Bare `python3 -m pytest` (no path) fails to collect at all** — it picks up `scripts/test_baseline_protection.py`, which is not a real pytest module but a standalone script that calls `sys.exit()` at import time, aborting collection for the whole run with `SystemExit: 1`. Confirmed via `git stash` that this is pre-existing and unrelated to Task 2 (reproduces identically on the pre-task-2 commit). Used `python3 -m pytest tests/` for all suite-wide runs instead, which is what actually collects the 172 → 176 baseline the brief refers to.
3. `prototype/data/kite_cache/instruments_nse_2026-08-28.json` appeared as an untracked file after starting the server (a runtime cache write, unrelated to templates/routes). Left untracked/uncommitted — out of scope for this task.
4. Kept the `/team` handler's original function name `team_dashboard` rather than renaming to `team_view` as the brief's example showed, per the brief's own instruction ("If the existing `/team` handler body differs from the above, keep its original `render_template` arguments"). Verified via grep that nothing else in the codebase references the function name, so this is a safe, conservative choice.
