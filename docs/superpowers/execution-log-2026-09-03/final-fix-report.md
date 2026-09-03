# Final fix wave -- accounts-signup

One wave, all 9 findings from the final whole-branch review (2 Critical, 5
Important, 2 triage-to-fix). Branch `feat/accounts-signup`, starting HEAD
`8e9a1be`.

## Critical 1 -- nothing stopped the suite sending real mail

Added `tests/conftest.py::_never_send_real_mail`, a session-wide autouse
fixture patching `mailer._smtp_transport` to a function that raises
`AssertionError`. Same shape as the existing `_never_touch_the_real_database`
net, for the same reason: a seam patched per-fixture (the `sent` fixture) is
a seam someone eventually forgets, and this side effect leaves the machine.

**Proof.** Removed the `sent` argument from
`test_forgot_mails_a_reset_link_to_a_real_account` and ran it with
`SMTP_USER`/`SMTP_PASS` set in the environment (without credentials present,
`mailer.send` raises its own `RuntimeError` before ever reaching the
transport, which would not have exercised the net). Captured log:

```
File ".../tests/conftest.py", line 46, in refuse
    raise AssertionError(
AssertionError: a test reached the real SMTP transport -- pass transport= or patch accounts_web.send_mail
```

Restored the test file (`git diff` clean afterward).

## Critical 2 -- `test_a_live_invite_renders_the_form` could not fail

`<title>Set your password -- TradePilot</title>` sits outside the
`{% if not live %}` branch, so `b"password" in r.data.lower()` passed on the
dead-link page too. Changed the assertion to check the form fields
(`name="password"`, `name="t"`), which only the live branch renders.

**Proof.** Made `accounts.peek_token` always return `None` and reran the
test:

```
E       assert b'name="password"' in b'<!doctype html>...<h1>That link is no longer valid</h1>...'
1 failed, 23 deselected
```

Restored `accounts.py`; reran -- `1 passed`.

## Important 3 -- expired invite was terminal

`cmd_approve` refused any waitlist row not matching `approved_at IS NULL`
forever, contradicting the "72 hours, then back to pending" spec. Rewrote
the guard: select the row unconditionally, refuse only when
`waitlist.user_id` is already set, when a `users` row exists for the
address, or when a live unexpired invite token exists. Re-approval issues a
fresh token and updates `approved_at`. New tests: re-approve after expiry
succeeds; re-approve while live is refused; approve after completion is
refused.

## Important 4 -- two notions of the site URL

Added `accounts_web._base_url()`, preferring `TRADEPILOT_URL` (same env var
`scripts/waitlist.py` already reads) and falling back to
`request.host_url`. `reset_body` now calls it. New test asserts the reset
link's host follows `TRADEPILOT_URL` when set.

## Important 5 -- the concurrency proof

Wrote a real one: `test_two_threads_racing_to_consume_the_same_token_only_one_wins`
in `tests/test_auth_tokens.py`. 200 tokens, each raced by two OS threads on
independent `sqlite3` connections to the same file, released from a
`threading.Barrier` so both are inside `consume_token` concurrently; asserts
exactly one thread wins per token. Ran 5x clean, ~0.7-1.0s each.

**Proof it's real, not lucky.** Swapped in a naive read-then-write split
implementation of `consume_token` (select, sleep, then update) and reran --
failed on the very first token: `got [('invite', ...), ('invite', ...)]`
(both threads won). Restored the real implementation; reran -- `12 passed`.
Shipped the real test, not the sequential fallback.

## Important 6 -- orphan token on failed send

`cmd_approve` now deletes the just-issued token
(`DELETE FROM auth_tokens WHERE token_hash = ?`) before returning non-zero
on a failed send. Strengthened `test_a_failed_send_leaves_the_row_pending`
to also assert `auth_tokens` count is 0.

## Important 7 -- completed invite still "waiting"

`set_password`'s invite-completion branch now sets `approved_at` alongside
`user_id` (`UPDATE waitlist SET user_id = ?, approved_at = ? WHERE
lower(email) = lower(?)`), so a duplicate waitlist row for the same address
no longer sits under "waiting" forever. New test seeds two waitlist rows for
one address, completes the invite, asserts zero rows remain with
`approved_at IS NULL` for that address.

## Triage 8 -- `issue_token` unguarded in `/app/forgot`

Wrapped `accounts.issue_token` in its own try/except inside `forgot()`,
logging and falling through to the ordinary acknowledgement on failure --
closing the 500-vs-200 oracle for a DB failure on the known-account branch.
Left `reset_body()` outside any guard, preserving commit `2978d91`'s
intentional design: a bug in the pure formatter should raise, not be
mislabelled a delivery failure. New test patches `accounts.issue_token` to
raise and confirms 200 + the ordinary ack + no mail sent.

## Triage 9 -- unfalsifiable hash test

`test_setting_a_password_stores_a_hash_not_the_password` now also asserts
`check_password_hash(stored, "new password") is True` and
`check_password_hash(stored, "old password") is False`, not just absence of
the literal string.

## Minor 10 -- wrong `live` on empty password

`/app/set-password`'s empty-password branch now opens the store and passes
the real `accounts.peek_token(conn, token) is not None` instead of a
hardcoded `True`.

## Verification

- `python3 -m pytest tests/ -q` -> **447 passed** (440 + 7 new/split tests)
- `node --test "tests/js/*.test.js"` -> **18 pass, 0 fail**
- All 5 routes present in `prototype/accounts_web.py`
  (`/app/login`, `/app/logout`, `/app/signup`, `/app/forgot`,
  `/app/set-password`)
- `requirements.txt` unchanged
- Both Critical proofs captured above, each restored to green/clean before
  moving on
