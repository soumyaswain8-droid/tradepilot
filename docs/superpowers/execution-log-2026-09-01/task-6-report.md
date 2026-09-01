# Task 6 report: the shell knows who you are

## Status
Done. All verification steps pass.

## What changed

### `prototype/static/app/api.js`
Added `me: function () { return json("/api/app/me"); }` alongside the
existing methods, using the file's existing internal `json()` helper (the
brief's snippet said `get`, but the file's actual helper is named `json` --
read the file first per the task instructions rather than trusting the
snippet literally). No new `fetch` call site was introduced.

### `prototype/static/app/main.js`
Added `loadWho()`, called once from `boot()`. It calls `window.TPApi.me()`;
on success it clears `#who` and appends the user id (via
`window.TPScreens.el`) plus a `<form method="post" action="/app/logout">`
containing a submit button styled as a link (`.who-out`). On rejection
(401 signed-out, or any other failure -- both get the same honest
treatment: claim nothing) it renders a plain `Sign in` link to `/app/login`.
Used the file's local `el(id)` helper as instructed. ES5 throughout, no
arrow functions, no `const`/`let`.

### `prototype/static/app.css`
Added `.who-out` so the Sign out button renders as inline text matching the
12px header, not a default chunky button.

### `docs/APP_MANUAL_CHECKS.md`
Two fixes:

1. **Broken seed data (not in the brief, caught by inspection).** Both
   seeded positions used the literal `"demo-user"`, which meant something
   only while `client_auth.current_user()` was a hardcoded stub. Task 3
   made the Book filter by the real signed-in user's id (now something
   like `u-8f21c4`), so those rows became invisible under any real account
   -- the seed still ran and exited 0, silently leaving the Book on
   "Nothing logged yet." instead of the priced/unpriced states the
   checklist exists to exercise. Fixed by:
   - Adding an explicit instruction to create an account first:
     `python3 scripts/add-client.py you@example.com`.
   - Replacing the hardcoded `"demo-user"` in both position tuples with
     `uid`, looked up via
     `cur.execute("SELECT id FROM users ORDER BY created_at LIMIT 1").fetchone()[0]`.
   - Adding a paragraph stating plainly that positions belong to an
     account now, and that a seed under a made-up id fails silently
     (exits 0, empty Book) rather than with an error.
   - Updated the Home checklist's forward-reference from "(see signed-out
     section below)" to "(see Signing out below)" to match the renamed
     section.

2. **Two edit-the-source procedures; removed one, kept the other, per the
   task instructions.**
   - Removed "## Checking the signed-out states" entirely -- it told the
     reader to edit `client_auth.py` and change `current_user()` to
     `return "demo-user"` / `return None`. That stub no longer exists;
     `current_user()` now reads a real session via
     `accounts.lookup_session()`. Replaced it with the brief's "###
     Signing out" section: click Sign out in the header, sign back in via
     `/app/login`, six checklist rows covering both directions and the
     wrong-password-vs-unknown-email uniformity check.
   - Left "## Checking the book-load-failure state" (the temporary `raise
     RuntimeError` inside `positions_list()`) completely untouched -- it
     is still the only way to force a 500 from `/api/app/positions` on
     demand, and remains valid.
   - Grepped the whole file afterward for `demo-user` and
     `client_auth.py`; no stale references remain outside the
     book-load-failure procedure's legitimate read of
     `client_auth.current_user()` as example code (not an edit
     instruction).

### `tests/test_app_screens.py`
Appended the three tests from the brief's Step 1, verbatim.

## Verification

1. `python3 -m pytest tests/ -q` -- **374 passed** (371 baseline + 3 new).
2. `node --test "tests/js/*.test.js"` (quoted glob, as instructed --
   the unquoted directory form dies with `MODULE_NOT_FOUND` on Node 22) --
   **18 passed**, 0 failed.
3. ES5 check:
   `grep -nE "=>|\bconst \b|\blet \b|\`" prototype/static/app/main.js prototype/static/app/api.js`
   -- one match, inside a `/* ... */` comment (`` `call` `` referring to the
   route name), nothing outside comments.
   `grep -rln "fetch(" prototype/static/app/` -- prints only `api.js`.
4. Seed check: ran the repaired snippet end to end against a throwaway
   copy of the schema (never touched `prototype/tradepilot_app.db`).
   Created an account via `accounts.create_user`, got id `u-9c93021b`,
   then ran the seed's `uid = ...ORDER BY created_at LIMIT 1...` lookup
   and both `INSERT OR REPLACE INTO positions` statements. Result: **2
   position rows** (`p-priced1`, `p-unpriced1`) both landed under
   `user_id = 'u-9c93021b'` -- the real account id, not a hardcoded one.

## Commit
See `git log -1` in the worktree after this report is written; commit
message follows the brief's Step 9 template plus a note on the checklist
seed-data fix.

---

## Fix round 1 of 5 (code review response)

### Finding 1 (Critical) -- `loadWho`'s failure branch claimed something it didn't know
Fixed to match the pattern `loadHome`'s book fetch and `loadBook` already use:
branch on `e.status === 401` for the genuine signed-out case (renders "Sign
in"); any other failure (500, dropped connection, bad JSON) now leaves
`#who` empty, with a comment explaining that's intentional -- offering
"Sign in" on an unrelated failure would be a claim about sign-in state a
failed request has no right to make.

**Deliberate-break check (no test, observed manually):** restored the
unconditional-render version (drop the `e.status === 401` branch, always
append the "Sign in" link on any rejection), re-read the code path. With
that version, a signed-in user whose `/api/app/me` fails with a 500 --
DB hiccup, dropped connection -- gets `#who` cleared and a bare "Sign in"
link rendered, identical to what a genuinely signed-out visitor sees. They
are still signed in (their session cookie is untouched), but the header
now falsely claims otherwise and invites them to sign in again. Reverted
to the fixed version; `tests/test_app_screens.py -q` back to 23 passed.

### Finding 2 (Important) -- header showed an opaque id, not an address
`/api/app/me` (`prototype/client_api.py`) now looks up the signed-in
user's email and returns it alongside `user_id`. `loadWho` renders
`m.email || m.user_id`, so a missing email degrades to the id rather than
blank. `test_me_returns_the_current_user` untouched and still passes
(asserts `user_id`/`plan`, neither removed). Added
`test_me_returns_the_signed_in_account_email` in `tests/test_client_auth.py`,
asserting the `signed_in` fixture's `priya@example.com` comes back.

### Finding 3 (Important) -- seed lookup picked the oldest account, not the new one
`docs/APP_MANUAL_CHECKS.md`: replaced `ORDER BY created_at LIMIT 1` (picks
the oldest row, contradicting the prose's promise) with a lookup by the
exact email the reader was just told to create:
`SELECT id FROM users WHERE lower(email) = lower(?)` bound to a
`YOUR_EMAIL = "you@example.com"` placeholder. Corrected the surrounding
prose to say plainly that positions belong to one account and that
seeding under the wrong one produces a silent empty Book.

**Verification against a throwaway DB with a pre-existing older user:**
- older (pre-existing) account id: `u-54d30117`
- newly created account id: `u-8b87da17`
- corrected seed picked uid `u-8b87da17` (the new one) -- confirmed
  `uid == new_uid` is True, `uid == old_uid` is False
- positions under the new account: 2; positions under the old account: 0

### Finding 4 (Minor) -- add-client.py's password prompts
Added a line after the `add-client.py` snippet noting it prompts for the
password twice (set + confirm) and does not echo input -- that is expected,
not a hang.

### Finding 5 (Minor) -- grep tests couldn't distinguish a form POST from a link
Added `test_signing_out_is_a_form_post_not_a_link` in
`tests/test_app_screens.py`, asserting both `out.method = "post"` and
`out.action = "/app/logout"` appear in the served `main.js`. A regression
to `<a href="/app/logout">` (the exact GET-via-`<img>` hazard the brief
warns about) would fail this test even though the earlier
`test_the_shell_offers_a_way_in_and_a_way_out` (action string only) would
still pass it.

### Re-verification
- `python3 -m pytest tests/ -q`: **376 passed** (374 + 2 new: email test,
  form-POST test)
- `node --test "tests/js/*.test.js"`: **18 passed**, 0 failed
- ES5 grep: one hit, inside the same pre-existing comment (`` `call` ``),
  nothing outside comments
- `fetch(` grep: only `api.js`
- `prototype/tradepilot_app.db` untouched throughout (checked mtime/git
  status before and after)

Files touched this round: `prototype/static/app/main.js`,
`prototype/client_api.py`, `docs/APP_MANUAL_CHECKS.md`,
`tests/test_app_screens.py`, `tests/test_client_auth.py`.
