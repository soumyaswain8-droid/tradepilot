# Final fix wave -- accounts-auth whole-branch review

Single fix wave closing out the review: 5 Important findings, 3 Minors. All
done in one pass, foreground, no new dependencies.

## Findings

**1. Sliding sessions did not slide.** `accounts_web.login()` set the
cookie's `max_age` to `SESSION_SLIDING_DAYS` (30) instead of
`SESSION_MAX_DAYS` (90), so a daily-active user's browser discarded the
cookie at day 30 even though the server-side row was still sliding and
valid. Fixed to use `SESSION_MAX_DAYS`, with a comment explaining why: the
cookie is transport, the row is the authority, and re-issuing `Set-Cookie`
on every gated response would tax every API call to track a lifetime the
server already tracks. Added `test_the_cookie_outlives_the_sliding_window_not_just_it`,
asserting the `Set-Cookie` header's `Max-Age` directly (the two prior
cookie tests only checked HttpOnly/SameSite/presence, never Max-Age --
that's why this shipped unnoticed).

**2. Disabling an account did not end its sessions.** `check_login` refused
disabled users but `lookup_session` never joined `users`, so an existing
cookie kept working for up to 90 days after disabling. Fixed by joining
`users` in `lookup_session` and refusing when `disabled_at IS NOT NULL`.
Added `test_disabling_an_account_ends_its_existing_sessions` in
`test_accounts.py`. RED/GREEN verified (see below).

**3. Two test modules read the live product database.** `test_accounts_web.py`'s
`store` fixture patched `client_auth.open_store` and `accounts_web.open_store`
but not `client_api.open_store`, so `/api/app/me` calls fell through to the
real `tradepilot_app.db`. Fixed with (a) the missing `client_api.open_store`
patch, and (b) a session-scoped autouse fixture in `conftest.py` that
repoints `app_store.DB_PATH` at a throwaway file for the whole run --
closing the class of bug regardless of which seam a future fixture misses.
One pre-existing test (`test_real_db_path_is_not_the_analytics_db`) asserted
on the live `app_store.DB_PATH` attribute and broke under the new session
fixture; rewrote it to reconstruct the production default from
`app_store.__file__` instead, so it tests the real constant rather than the
test-time disguise.

**4. Login CSRF was live.** `POST /app/login` had no Origin check --
`accounts_web` routes are correctly outside `GATED_ENDPOINTS` (a login page
needing a session would be a locked door with the key inside), and
SameSite=Lax can't help because signing in requires no cookie. Extracted
the guard's inline Origin comparison into `client_auth.foreign_origin()`,
reused it in the guard and in both `accounts_web` POST handlers (login,
logout), returning 403 when foreign. Added 3 tests: cross-site Origin on
login -> 403 + no cookie; matching Origin -> still signs in; missing
Origin -> still signs in.

**5. `docs/APP_MANUAL_CHECKS.md` was not walkable in order.** Added an
explicit "Sign in now" section immediately after seeding, before the first
screen section, so Book/Home checks stop looking like regressions when
signed out. Stated the precondition on the force-a-500 procedure (must be
signed in, or the guard's 401 fires before the `raise` and the described
text never appears). Promoted "Signing out" from `###` to `##` so it's a
sibling section, not a subsection of the book-failure procedure.

**Minor 6.** Two Origin tests in `test_client_auth.py` asserted `!= 403`,
which also passes on 401/500. Changed both to `== 201` (the real
`position_create` success status).

**Minor 7.** `test_401_body_leaks_nothing_internal` asserted substrings
against a response body that is always the guard's hardcoded
`{"error": "sign in to see this"}` literal -- the gated handler never runs,
so the assertion could not fail regardless of any real internal leak
elsewhere. Deleted (no natural code path in this app produces a real leak
to check against automatically; the equivalent manual procedure already
exists in Finding 5's doc).

**Minor 8.** Added `"` and `'` to `safe_next`'s rejected characters, so
`|urlencode` in the template is no longer the only thing standing between
`next` and an attribute break-out.

## Verification

- `python3 -m pytest tests/ -q` -> 380 passed (376 baseline + 5 new - 1
  deleted).
- `node --test "tests/js/*.test.js"` -> 18 passed.
- ES5 in `prototype/static/app/` and single-`fetch` in `api.js`: unchanged,
  confirmed -- no JS files touched this wave.

### Finding 3 proof

With all patches in place: full suite run, then
`prototype/tradepilot_app.db` checked directly -- `calls`, `positions`,
`users`, `sessions` all at 0 rows.

Then the (a) patch (`client_api.open_store` in `test_accounts_web.py`'s
`store` fixture) was temporarily removed, the full suite re-run (still 376
passing, since the app was already close to that pass count before this
wave's new tests), and the live database checked again: still 0 rows in
all four tables. This proves the session-scoped `conftest.py` fixture
alone -- independent of any single fixture's patches -- keeps the live
database untouched. The (a) patch was then restored; diff against the
pre-removal backup confirmed byte-identical restoration, and the full
380-test suite passed again afterward.

### Finding 4

Cross-site `Origin: https://evil.example.com` on `POST /app/login` ->
**403**, and no `tp_session` cookie was set (`Set-Cookie` header absent the
cookie name). Verified via
`test_login_csrf_a_cross_site_origin_is_refused`, run individually and as
part of the full suite.

### Finding 2 RED/GREEN

RED: with the `disabled_at` check temporarily removed from
`accounts.lookup_session`, `test_disabling_an_account_ends_its_existing_sessions`
failed:
```
E       AssertionError: assert 'u-b14e40d4' is None
E        +  where 'u-b14e40d4' = accounts.lookup_session(conn, token)
```
GREEN: check restored (diff against backup confirmed byte-identical), same
test:
```
tests/test_accounts.py::test_disabling_an_account_ends_its_existing_sessions PASSED [100%]
```

## Files changed

- `prototype/accounts.py` -- Finding 2 (disabled session join)
- `prototype/accounts_web.py` -- Finding 1 (cookie max_age), Finding 4
  (login/logout Origin check), Minor 8 (safe_next quotes)
- `prototype/client_auth.py` -- Finding 4 (`foreign_origin()` extraction)
- `tests/conftest.py` -- Finding 3(b) (session-scoped DB safety net)
- `tests/test_accounts.py` -- Finding 2 test
- `tests/test_accounts_web.py` -- Finding 1, Finding 3(a), Finding 4 tests
- `tests/test_app_store.py` -- fix for pre-existing test broken by 3(b)
- `tests/test_client_auth.py` -- Minor 6, Minor 7
- `docs/APP_MANUAL_CHECKS.md` -- Finding 5
