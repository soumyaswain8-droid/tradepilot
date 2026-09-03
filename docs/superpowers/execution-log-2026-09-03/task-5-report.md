# Task 5 Report: Setting a password

## Status: DONE

## Commit
`084cf049deaa3e62a9b1a884063ee42c4566431b`

## What was built
- Appended `/app/set-password` (GET+POST) to the end of `prototype/accounts_web.py` (existing routes untouched: `/app/login`, `/app/logout`, `/app/signup`, `/app/forgot`).
- Created `prototype/templates/set-password.html` (new file).
- Appended 8 tests + `_invite` helper to `tests/test_signup_web.py` (existing 13 tests + `store`/`sent` fixtures untouched).

## Ordering preserved as specified
- 403 (foreign-origin check) runs before `consume_token`.
- Empty-password check runs before `consume_token`.
- `set_password` is only reached after a successful `consume_token`.
- `revoke_all_sessions` runs before `create_session` on the reset path.

## Test counts
- `tests/test_signup_web.py`: 22 passed (13 pre-existing + 8 new — brief expected 22, confirmed).
- Full suite `python3 -m pytest tests/ -q`: **429 passed** (brief's stated baseline of 420 was stale; no regressions, all prior routes intact).
- `node --test "tests/js/*.test.js"`: 18 passed, 0 failed.

## Step 6 — ordering proof (four lines)

**Probe 1 — move `revoke_all_sessions` to AFTER `create_session`:**
```
FAILED tests/test_signup_web.py::test_the_browser_completing_a_reset_is_left_signed_in
1 failed in 3.13s
```
Restored, re-ran:
```
1 passed in 3.02s
```

**Probe 2 — comment out `revoke_all_sessions` entirely:**
```
FAILED tests/test_signup_web.py::test_a_reset_ends_sessions_that_already_existed
1 failed in 3.03s
```
Restored, re-ran:
```
1 passed in 2.84s
```

Two different tests, two different failures, both went RED under their respective mutation and GREEN on restore. Neither stayed green.

## Route confirmation
```
@bp.route("/app/login", methods=["GET", "POST"])
@bp.route("/app/logout", methods=["POST"])
@bp.route("/app/signup", methods=["GET", "POST"])
@bp.route("/app/forgot", methods=["GET", "POST"])
@bp.route("/app/set-password", methods=["GET", "POST"])
```
All five present. `requirements.txt` byte-identical (no diff).

---

## Fix round 1

Findings 1+2 (token purpose ignored / uncaught race on `create_user`) fixed together in `/app/set-password`: after `consume_token` + the users-row lookup, two guards now refuse a redemption that disagrees with the token's `purpose` (`invite` redeemed against an existing account, `reset` redeemed against a deleted one) with `400`, and `create_user` is wrapped in `try/except ValueError` to answer `400` instead of 500 on a lost race. All existing ordering preserved: 403 and empty-password checks still precede `consume_token`; `revoke_all_sessions` still precedes `create_session`.

Finding 3: `test_an_invite_link_cannot_be_used_twice` now asserts `== 400` instead of `!= 302`.

Two tests added: `test_an_invite_is_refused_once_the_account_exists`, `test_a_reset_is_refused_when_the_account_is_gone`.

### Guard-binding proof
Guards removed, ran `test_an_invite_is_refused_once_the_account_exists`:
```
FAILED tests/test_signup_web.py::test_an_invite_is_refused_once_the_account_exists
assert r.status_code == 400
E       assert 302 == 400
1 failed in 3.11s
```
(302 confirms the silent reset succeeded — the second invite redeemed as a reset.) Restored, re-ran:
```
1 passed in 2.98s
```

### Full suite
`tests/test_signup_web.py`: 24 passed (22 + 2 new).
`python3 -m pytest tests/ -q`: **431 passed** (429 + 2 new).

Routes confirmed unchanged: `/app/login`, `/app/logout`, `/app/signup`, `/app/forgot`, `/app/set-password`. `requirements.txt` untouched.
