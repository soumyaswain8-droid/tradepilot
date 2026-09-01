# Task 4 Report: The login page

## Status: DONE

## Commit
`4bcf61b` — feat(auth): server-rendered sign-in and sign-out

## Files
- Created `prototype/accounts_web.py` — blueprint with `GET/POST /app/login`, `POST /app/logout`, `safe_next()`, module-local `open_store()`.
- Created `prototype/templates/login.html` — server-rendered, no `<script`.
- Modified `prototype/app.py` — registered `_accounts_web_bp` immediately after `app.register_blueprint(_client_api_bp)` (which is at line 66 in this worktree, not lines 56-60 as the brief's stale numbering said — verified by locating the exact line text before editing).
- Created `tests/test_accounts_web.py` — 16 tests (2 parametrized cases: 4 hostile `next` targets + 3 benign).

## Step 2 (pre-implementation): confirmed failing
`ModuleNotFoundError`-equivalent: `ImportError: cannot import name 'accounts_web' from 'prototype'` — expected, matches brief.

## Step 6: tests pass
`python3 -m pytest tests/test_accounts_web.py -q` → **16 passed**

## Full suite
`python3 -m pytest tests/ -q` → **360 passed** (was 344 before this task; +16 new).

## Enumeration tests (tests/test_client_auth.py) — all still green
```
test_every_client_route_is_classified PASSED
test_no_endpoint_is_both_public_and_gated PASSED
test_registries_name_only_real_endpoints PASSED
test_a_route_merely_starting_with_the_same_letters_is_not_swept_in PASSED
```
`/app/login` and `/app/logout` are not under `/api/app`, so they never entered `PUBLIC_ENDPOINTS`/`GATED_ENDPOINTS` and the registries needed no edits — as expected, none were made.

## No-JavaScript check
Rendered `/app/login` body: `"<script" in body.lower()` → `False`. Confirmed via a live Flask test client render, not just the template source.

## Step 7: open-redirect test binds (the part that matters most)

Broke `safe_next` to `return target or "/app"`. Ran:
```
python3 -m pytest tests/test_accounts_web.py -q -k test_next_cannot_send_you_off_site -v
```
RED — all 4 hostile cases failed:
```
FAILED tests/test_accounts_web.py::test_next_cannot_send_you_off_site[https://evil.example.com/phish]
FAILED tests/test_accounts_web.py::test_next_cannot_send_you_off_site[//evil.example.com/phish]
FAILED tests/test_accounts_web.py::test_next_cannot_send_you_off_site[http://evil.example.com]
FAILED tests/test_accounts_web.py::test_next_cannot_send_you_off_site[\\\\evil.example.com]
4 failed, 12 deselected in 0.16s
```

Restored `safe_next` to the guarded implementation. Ran the same selection:
```
tests/test_accounts_web.py ....                                          [100%]
4 passed, 12 deselected in 0.10s
```
GREEN. All four hostile shapes bind correctly to the test.

Then re-ran the full `test_accounts_web.py` (16 passed) and the full suite (360 passed) post-restore to confirm no residual damage.

## Notes
- `client_auth.COOKIE_NAME` used throughout, never the literal `"tp_session"`.
- `accounts_web.open_store()` kept fully separate from `client_auth.open_store()` per the brief — tests monkeypatch both independently, pointing at the same throwaway DB.
- `secure=request.is_secure` left as-is (not hardened to always-on) per the brief's explicit warning about silent local-HTTP login failure.
- `accounts.revoke_session(conn, None)` is a no-op (checked source before relying on it) — `logout()` calling it with no cookie present is safe.
- `requirements.txt` untouched (`git diff --stat -- requirements.txt` empty).
- No subagents dispatched; no `run_in_background`; nothing added under `.superpowers/` to the commit.

---

## Fix round 1 of 5

### Finding 1 (Critical) — `safe_next` control-character bypass

Added 4 hostile cases to `test_next_cannot_send_you_off_site` (exact strings, real control
characters): `"/\t/evil.example.com"`, `"/\n/evil.example.com"`, `"/\r/evil.example.com"`,
`"/ev\til.example.com"`.

**Proof 1 — bind check, run BEFORE fixing `safe_next`:**
```
FAILED tests/test_accounts_web.py::test_next_cannot_send_you_off_site[/\t/evil.example.com]
FAILED tests/test_accounts_web.py::test_next_cannot_send_you_off_site[/\n/evil.example.com]
FAILED tests/test_accounts_web.py::test_next_cannot_send_you_off_site[/\r/evil.example.com]
FAILED tests/test_accounts_web.py::test_next_cannot_send_you_off_site[/ev\til.example.com]
4 failed, 4 passed, 12 deselected
```
All four RED as expected — confirms the tests bind to the real bypass, not a vacuous check.

Applied the fix (reject any char with `ord(ch) < 0x20 or ord(ch) == 0x7f`, additive to all
existing checks). Re-ran the full hostile + benign parametrised set:
```
11 passed, 9 deselected
```
GREEN — all 8 hostile shapes rejected, all 3 benign paths kept unchanged.

### Finding 2 (Important) — `test_logging_out_revokes_the_session` couldn't fail

Renamed the original test to `test_logging_out_clears_the_cookie` (it only proves the
cookie-jar half). Added `test_logout_revokes_server_side_not_just_the_cookie`, which re-presents
the same raw token via `client.set_cookie(...)` after logout, bypassing the jar's own cookie-drop
behavior.

**Proof 2 — stub `accounts.revoke_session` to a no-op (`return` as the first line), run the new
test:**
```
FAILED tests/test_accounts_web.py::test_logout_revokes_server_side_not_just_the_cookie
AssertionError: assert 200 == 401
1 failed, 20 deselected
```
RED — with revocation stubbed out, the second `/api/app/me` call still succeeds (200), proving
the test genuinely depends on the DELETE happening server-side.

Restored `accounts.py` (`git diff --stat -- prototype/accounts.py` empty afterward) and re-ran:
```
1 passed, 20 deselected
```
GREEN.

### Full suite
`python3 -m pytest tests/ -q` → **365 passed** (was 360; +5: four new hostile `safe_next` cases,
one new logout test).

### Commit
`bfda7f0` (see next commit in this branch) — fix(auth): reject control characters in safe_next;
prove logout revokes server-side

No subagents. No `run_in_background`. Nothing under `.superpowers/` staged.
