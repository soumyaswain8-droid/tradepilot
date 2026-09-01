# Task 3 Report: The trust boundary

## Status: DONE

## What changed

### `prototype/client_auth.py` (rewritten)
- `current_user()` now reads the `tp_session` cookie and resolves it through
  `accounts.lookup_session()` on a connection from a new `open_store()` seam
  (mirrors `client_api.open_store`), instead of returning the fixed
  `"demo-user"` stub.
- Added `COOKIE_NAME = "tp_session"` and `UNSAFE_METHODS = {"POST", "PUT",
  "PATCH", "DELETE"}`.
- `install_guard()` now also refuses an unsafe-method request on a gated
  endpoint whose `Origin` header is **present and mismatched** against
  `request.host_url`. A missing `Origin` passes through untouched (see
  `test_a_missing_origin_is_not_treated_as_foreign`).
- `PUBLIC_ENDPOINTS` and `GATED_ENDPOINTS` are untouched — same names, same
  contents.
- Module docstring updated to drop the "Project B does not exist yet" framing
  (accounts now exists) while keeping the registries-are-the-point
  explanation intact, per the brief.

### `prototype/app.py`
- Line 53's app-wide `CORS(app, origins=[...])` replaced with a scoped
  `CORS(app, resources={r"/api/(?!app/).*": {"origins": [...]}})`, exactly as
  written in the brief. **No adjustment was needed** — the negative-lookahead
  resource pattern matched flask-cors's dispatch correctly on the first try;
  all three `test_cors_scope.py` tests passed without any pattern changes.

### `tests/test_client_auth.py`
- Added the `signed_in` fixture, but **with the dispatch's stated correction
  applied** (this patch is not in the brief file itself -- it came from the
  coordinator's dispatch instructions): it patches both
  `client_auth.open_store` *and* `client_api.open_store` at the same tmp
  path. Only patching the former would have let
  `test_a_missing_origin_is_not_treated_as_foreign`'s POST reach the real
  view and write into `prototype/tradepilot_app.db`.
- Replaced `test_gated_endpoint_allows_a_user` and
  `test_me_returns_the_current_user` to use `signed_in` instead of the stub
  identity.
- Added `test_no_cookie_means_no_user`, `test_a_forged_token_means_no_user`,
  `test_an_unsafe_method_from_a_foreign_origin_is_refused`,
  `test_a_missing_origin_is_not_treated_as_foreign`, exactly as specified.

### `tests/test_cors_scope.py` (new)
- Created verbatim per the brief's Step 5.

### `tests/test_client_api_positions.py` (not named in the brief — see below)
Running the full suite after Step 8 turned up 23 failures here, all in one
family: every test that calls the module's `_post(client, ...)` helper was
relying on the old always-`"demo-user"` stub, and with a real cookie-backed
`current_user()` these gated POST/PATCH/DELETE/GET calls now correctly 401.
This is exactly the "neighbouring tests that assumed the old stub identity"
case flagged in my instructions, so I fixed it by signing in rather than
weakening any assertion:
- The `store` fixture now also depends on `client`, creates a real user via
  `accounts.create_user`, starts a real session via `accounts.create_session`,
  and sets the `tp_session` cookie on the shared test client — so every
  `_post(client, ...)` call in this file authenticates as that user, same as
  a browser would.
- It also patches `client_auth.open_store` (not just `client_api.open_store`)
  to the same tmp db path, for the same reason the corrected `signed_in`
  fixture does — the guard's `current_user()` call needs to see the same
  users/sessions tables as the positions writes.
- One test, `test_another_user_cannot_delete_your_position`, hardcoded the
  literal string `"demo-user"` as the original owner's id for its final
  assertion. Since `accounts.create_user` generates a real `u-xxxxxxxx` id,
  I replaced the hardcoded literal with a lookup (`store.execute("SELECT id
  FROM users").fetchone()["id"]`) rather than inventing or weakening
  anything.
- All other tests in this file that monkeypatch `client_auth.current_user`
  directly (`test_one_user_never_sees_anothers_book`,
  `test_positions_are_gated`, `test_another_user_cannot_patch_your_position`,
  etc.) needed no changes — they override the function itself and are
  unaffected by the cookie mechanism.

No other test files needed changes.

## CORS pattern outcome
Used exactly as given in the brief:
```python
CORS(app, resources={r"/api/(?!app/).*": {
    "origins": ["http://localhost:*", "http://127.0.0.1:*",
                "https://tradepilot.onrender.com"]}})
```
No adjustment was required.

## Verification
- `pytest tests/test_client_auth.py -q` → 14 passed (Step 4)
- `pytest tests/test_cors_scope.py tests/test_client_auth.py -q` → 17 passed
  (Step 8)
- `pytest tests/ -q` → **342 passed** (Step 9; baseline was 335, +4 new
  client_auth tests, +3 new CORS tests)
- The four enumeration tests (`test_every_client_route_is_classified`,
  `test_no_endpoint_is_both_public_and_gated`,
  `test_registries_name_only_real_endpoints`,
  `test_a_route_merely_starting_with_the_same_letters_is_not_swept_in`) all
  still pass — confirmed with a targeted `-k` run.
- `requirements.txt` untouched (`git diff requirements.txt` empty).
- `prototype/tradepilot_app.db` (gitignored, live product database)
  untouched by the run — confirmed no diff/mtime change tied to test
  execution, since every test now points at a `tmp_path` database via the
  `open_store` seams.

## Commit
`git add prototype/client_auth.py prototype/app.py tests/test_client_auth.py tests/test_cors_scope.py tests/test_client_api_positions.py`
then committed (see SHA in final report message).

---

## Fix round 1

### FINDING 1 (Important) — Origin scheme mismatch behind TLS-terminating proxy

`current_user()`'s guard compared the full `Origin` header against
`request.host_url.rstrip("/")`. In production, behind the TLS-terminating
proxy implied by `https://tradepilot.onrender.com` in the CORS list, Flask
sees `http://` internally while the browser sends `Origin: https://...` —
scheme mismatch, every signed-in write 403s.

Fixed in `prototype/client_auth.py` by comparing hosts, not full origins,
via `urlparse(origin).netloc != request.host`. Added `from urllib.parse
import urlparse`. Deliberately did **not** add `ProxyFix` or any
`X-Forwarded-*` handling, per instruction — it's spoofable unless the proxy
overwrites it, and it would touch all ~70 operator routes to fix one check.
The missing-Origin pass-through is unchanged.

Added `test_a_matching_host_with_a_different_scheme_is_accepted` to
`tests/test_client_auth.py`, using `Origin: https://localhost` — matching
`request.host` under the test client, confirmed directly (see below), not
guessed. `test_an_unsafe_method_from_a_foreign_origin_is_refused` and
`test_a_missing_origin_is_not_treated_as_foreign` needed no changes — neither
references the full URL, only a foreign host or no Origin at all.

**`request.host` under the test client is `'localhost'`** (confirmed via a
`before_request` probe on the real app; `request.host_url` was
`'http://localhost/'`).

### FINDING 2 (Minor) — CORS lookahead missed the bare path

`prototype/app.py`'s resource pattern tightened from `r"/api/(?!app/).*"` to
`r"/api/(?!app(/|$)).*"`. Verified directly against both patterns:

| path | old | new |
|---|---|---|
| `/api/app` | matches (bug) | excluded |
| `/api/app/` | excluded | excluded |
| `/api/app/positions` | excluded | excluded |
| `/api/apple` | matches | matches (unaffected) |
| `/api/indices` | matches | matches (unaffected) |

Also confirmed live: a probe route at `/api/apple` still returns the
`Access-Control-Allow-Origin` header with the new pattern.

### FINDING 3 (Minor) — gated CORS test only covered the 401 path

Added `test_the_gated_client_api_carries_no_cors_headers_when_signed_in` to
`tests/test_cors_scope.py`, asserting the header's absence on a real 200
response from `/api/app/positions`. Required a `signed_in` fixture local to
that file (mirrors the one in `test_client_auth.py`, including the
`client_api.open_store` patch) since fixtures aren't shared across test
modules without a conftest change, which wasn't asked for.

### Citation correction
Fixed the earlier report text that attributed the `client_api.open_store`
patch in the `signed_in` fixture to "the brief's stated correction" — that
patch came from the coordinator's dispatch instructions, not from the brief
file itself, which does not contain it.

### Verification

- `python3 -m pytest tests/ -q` → **344 passed** (342 + 2 new: the scheme
  test in `test_client_auth.py`, the signed-in CORS test).
- Four registry-enumeration tests confirmed green via targeted `-k` run.
- Deliberate break/restore of Finding 1's fix:
  - **RED**: reverted to `origin != request.host_url.rstrip("/")` →
    `tests/test_client_auth.py::test_a_matching_host_with_a_different_scheme_is_accepted`
    → `1 failed, 14 deselected` (`assert 403 != 403`).
  - **GREEN**: restored `urlparse(origin).netloc != request.host` → same
    test → `1 passed, 14 deselected`.
  - Post-restore: `client_auth.py` byte-identical to the fixed version
    (diff clean); full suite re-run → 344 passed;
    `test_an_unsafe_method_from_a_foreign_origin_is_refused` (evil.example.com)
    independently re-confirmed still 403.

## Commit (fix round 1)
`git add prototype/app.py prototype/client_auth.py tests/test_client_auth.py tests/test_cors_scope.py`
then committed (see SHA in final report message).
