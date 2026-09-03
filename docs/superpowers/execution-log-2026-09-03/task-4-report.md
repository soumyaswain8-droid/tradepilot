# Task 4 report: Signup and forgot

## Status: DONE

## Commit
`80883a0fcab52b6efeb8f3076954af88835e1b4b` — "feat(auth): public waitlist and password-reset request"

## What was done
- Extended `prototype/accounts_web.py` (appended, not rewritten): added `import secrets`,
  added `current_app` to the flask import, added `mailer` to the prototype import (single
  import statements each, no duplicates), and added `WAITLIST_ACK`, `FORGOT_ACK`,
  `send_mail(to, subject, body)`, `reset_body(token)`, and the `/app/signup` and
  `/app/forgot` routes, verbatim per the brief.
- Created `prototype/templates/signup.html` and `prototype/templates/forgot.html`.
- Created `tests/test_signup_web.py` verbatim per the brief, with the `store` fixture
  patching `open_store` on all three seams (`client_auth`, `accounts_web`, `client_api`).

## Step 2 (pre-implementation): confirmed failing
3 failed / 10 errors (404s and `AttributeError: no attribute 'send_mail'`), as expected —
routes did not exist yet.

## Step 5: route tests after implementation
`python3 -m pytest tests/test_signup_web.py -q` → **13 passed**

## Step 6: RED/GREEN proof that the identical-response test binds
Temporarily made the `forgot` unknown-address branch render `done=False` (via an `unknown`
flag) instead of always `done=True`.

- RED: `python3 -m pytest tests/test_signup_web.py::test_forgot_answers_the_same_whether_or_not_the_account_exists -q`
  → **1 failed** — diff showed the known-account response rendering the `<div class="empty">...ack</div>` block while the unknown-address response rendered the full form (`<p class="thin">...</p><form>...`).
- Restored the route to always render `done=True` regardless of whether the address matched an account.
- GREEN: same test → **1 passed**; full file re-run → **13 passed**.

## Step 7: full suite
`python3 -m pytest tests/ -q` → **420 passed** (was 407 before this task; 407 + 13 new = 420, no regressions, no skips).

## Verification of untouched surfaces
- `/app/login` and `/app/logout` code unchanged (only appended after them); their tests
  still pass: `pytest tests/ -q -k "login or logout"` → **8 passed**.
- `requirements.txt` — no diff (byte-identical).
- No JavaScript added; both pages are server-rendered Jinja forms with plain POSTs.
- Both POST routes call `client_auth.foreign_origin()` first and return 403 when true
  (covered by `test_signup_from_a_foreign_origin_is_refused` and
  `test_forgot_from_a_foreign_origin_is_refused`, both passing).
- `/app/forgot` never reveals mail failures to the visitor: on `send_mail` raising, the
  exception is caught, logged via `current_app.logger.exception`, and the ordinary
  `FORGOT_ACK` acknowledgement is still rendered with status 200
  (`test_forgot_still_answers_normally_when_mail_fails` passes).
- Deferred/no-action item acknowledged, not touched: `mailer`'s per-operation (not
  overall) SMTP timeout, which could hold a `/app/forgot` POST for ~80s under a hung
  mail server.

No blockers, no deviations from the brief's exact code.

## Fix round 1 of 5

Critical timing side-channel on `/app/forgot` (known address triggers a synchronous
SMTP round-trip; unknown does a single SELECT) was **ruled deferred to the deploy
gate** by the coordinator — not attempted, mailer not restructured.

### Finding 1 — narrowed the `except Exception` guard
In `forgot()`, `reset_body(token)` is now called outside the `try`, so only
`send_mail(...)` is guarded. A bug in `reset_body` (bad `%` format, missing arg) will
now raise normally instead of being mislabelled as a delivery failure. Comment
explaining why the failure is invisible to the visitor was kept.

### Finding 2 — strengthened the foreign-origin test
`test_forgot_from_a_foreign_origin_is_refused` now also asserts
`SELECT COUNT(*) FROM auth_tokens` is 0, matching its signup sibling's waitlist-count
assertion.

### Proof the strengthened test binds
Mutated `forgot()` to move the `client_auth.foreign_origin()` check to after
`accounts.issue_token(...)` (before `restoring`):

- RED: `python3 -m pytest tests/test_signup_web.py::test_forgot_from_a_foreign_origin_is_refused -q`
  → **1 failed** — `assert store.execute("SELECT COUNT(*) FROM auth_tokens").fetchone()[0] == 0` failed
  with `assert 1 == 0` (the 403 assertion still passed; only the token-count assertion caught it).
- Restored the origin check to its original position (before any DB reads).
- GREEN: same test → **1 passed**.

### Re-verification
- `python3 -m pytest tests/test_signup_web.py -q` → 13 passed
- `python3 -m pytest tests/ -q` → **420 passed** (unchanged from before this round; no regressions)
- `python3 -m pytest tests/ -q -k "login or logout"` → 8 passed — `/app/login` and
  `/app/logout` untouched and intact.
